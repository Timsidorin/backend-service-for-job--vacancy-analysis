"""
Vacancy pipeline handlers: process → embed → sync.
"""
import json
import logging
from uuid import UUID

import asyncpg

from services.vacancy_pipeline_worker.config import configs

logger = logging.getLogger(__name__)


def _parse_json(val):
    if val is None:
        return {}
    if isinstance(val, dict):
        return val
    try:
        return json.loads(val) if isinstance(val, str) else {}
    except json.JSONDecodeError:
        return {}


def _key_skills(skills_val) -> list:
    data = _parse_json(skills_val)
    ks = data.get("key_skills", [])
    return ks if isinstance(ks, list) else []


async def handle_process(payload: dict, kafka_client) -> None:
    """Обрабатывает одну сырую вакансию и кладёт результат в processed_vacancies."""
    raw_uuid = UUID(payload["uuid"])
    logger.info("[process] start %s", raw_uuid)

    conn = await asyncpg.connect(configs.pg_dsn)
    try:
        row = await conn.fetchrow(
            "SELECT uuid, title, description, full_text, raw_data FROM raw_vacancies WHERE uuid = $1",
            raw_uuid,
        )
        if not row:
            logger.warning("[process] raw vacancy %s not found, skip", raw_uuid)
            return

        raw_data = _parse_json(row["raw_data"])
        from services.vacancy_ml_service.pipeline.processor import process_raw_vacancy

        skills, grade = process_raw_vacancy(
            raw_vacancy_uuid=raw_uuid,
            title=row["title"] or "",
            description=row["description"] or "",
            full_text=row["full_text"],
            raw_data=raw_data,
        )

        key_skills = skills.get("key_skills", []) if isinstance(skills, dict) else []
        skills_lower = [str(s).lower() for s in (key_skills if isinstance(key_skills, list) else [])]

        try:
            from experiments.rule_based_domains import assign_domain
            domain = assign_domain(skills_lower)
        except ImportError:
            domain = "Общие/Универсальные"

        result = await conn.fetchrow(
            """
            INSERT INTO processed_vacancies (raw_vacancy_uuid, skills, grade_prediction, domain)
            VALUES ($1, $2::jsonb, $3, $4)
            ON CONFLICT (raw_vacancy_uuid) DO UPDATE SET
                skills = EXCLUDED.skills,
                grade_prediction = EXCLUDED.grade_prediction,
                domain = EXCLUDED.domain
            RETURNING uuid
            """,
            raw_uuid,
            json.dumps(skills, ensure_ascii=False),
            grade,
            domain,
        )
        processed_uuid = result["uuid"]
        logger.info("[process] done %s → processed %s", raw_uuid, processed_uuid)

        await kafka_client.publish_vacancy_uuid(
            processed_uuid, topic=configs.KAFKA_TOPIC_PROCESSED
        )
    finally:
        await conn.close()


async def handle_embed(payload: dict, kafka_client) -> None:
    """Строит эмбеддинг для обработанной вакансии и кладёт в processed_vacancies.embedding."""
    processed_uuid = UUID(payload["uuid"])
    logger.info("[embed] start %s", processed_uuid)

    if not configs.OPENAI_API_KEY:
        logger.error("[embed] OPENAI_API_KEY not set, skip")
        return

    conn = await asyncpg.connect(configs.pg_dsn)
    try:
        await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
        from pgvector.asyncpg import register_vector
        await register_vector(conn)

        row = await conn.fetchrow(
            """
            SELECT p.uuid, r.title, r.description, p.domain, p.skills
            FROM processed_vacancies p
            JOIN raw_vacancies r ON r.uuid = p.raw_vacancy_uuid
            WHERE p.uuid = $1
            """,
            processed_uuid,
        )
        if not row:
            logger.warning("[embed] processed vacancy %s not found, skip", processed_uuid)
            return

        key_skills = _key_skills(row["skills"])
        from services.vacancy_analytics_service.services.embeddings import (
            build_vacancy_text,
            get_embeddings_batch_async,
        )

        text = build_vacancy_text(
            row["title"] or "",
            row["description"],
            row["domain"],
            [str(s) for s in key_skills[:50]],
        )

        embeddings = await get_embeddings_batch_async(
            [text],
            api_key=configs.OPENAI_API_KEY,
            base_url=configs.OPENAI_BASE_URL or None,
            model=configs.OPENAI_EMBEDDING_MODEL,
        )

        await conn.execute(
            """
            UPDATE processed_vacancies
            SET embedding = $2::vector
            WHERE uuid = $1
            """,
            processed_uuid,
            embeddings[0],
        )
        logger.info("[embed] done %s", processed_uuid)

        await kafka_client.publish_vacancy_uuid(
            processed_uuid, topic=configs.KAFKA_TOPIC_EMBEDDED
        )
    finally:
        await conn.close()


async def handle_sync(payload: dict, _kafka_client) -> None:
    """Синхронизирует одну обработанную вакансию в ClickHouse."""
    processed_uuid = UUID(payload["uuid"])
    logger.info("[sync] start %s", processed_uuid)

    conn = await asyncpg.connect(configs.pg_dsn)
    try:
        row = await conn.fetchrow(
            """
            SELECT
                r.uuid AS raw_uuid, p.uuid AS processed_uuid,
                r.source, r.title, r.description, r.city, r.region, r.region_code,
                r.employer, r.salary_from, r.salary_to, r.currency, r.published_at,
                p.skills, p.grade_prediction AS grade, p.domain, p.processed_at
            FROM raw_vacancies r
            INNER JOIN processed_vacancies p ON p.raw_vacancy_uuid = r.uuid
            WHERE p.uuid = $1
            """,
            processed_uuid,
        )
        if not row:
            logger.warning("[sync] processed vacancy %s not found, skip", processed_uuid)
            return

        salary_from = row["salary_from"]
        salary_to = row["salary_to"]
        salary_typical = None
        if salary_from is not None and salary_to is not None:
            salary_typical = (salary_from + salary_to) // 2
        elif salary_from is not None:
            salary_typical = salary_from
        elif salary_to is not None:
            salary_typical = salary_to

        key_skills = _key_skills(row["skills"])

        import clickhouse_connect

        ch = clickhouse_connect.get_client(
            host=configs.CLICKHOUSE_HOST,
            port=configs.CLICKHOUSE_PORT,
            username=configs.CLICKHOUSE_USER,
            password=configs.CLICKHOUSE_PASSWORD,
            database=configs.CLICKHOUSE_DB,
        )

        ch.insert(
            f"{configs.CLICKHOUSE_DB}.vacancies_analytics",
            [[
                str(row["raw_uuid"]),
                str(row["processed_uuid"]),
                row["source"] or "",
                (row["title"] or "")[:10000],
                (row["description"] or "")[:50000],
                row["city"],
                row["region"],
                row["region_code"],
                (row["employer"] or "")[:500],
                salary_from,
                salary_to,
                salary_typical,
                row["currency"],
                row["published_at"],
                key_skills,
                row["grade"],
                row["domain"],
                row["processed_at"],
            ]],
            column_names=[
                "raw_uuid", "processed_uuid", "source", "title", "description",
                "city", "region", "region_code", "employer",
                "salary_from", "salary_to", "salary_typical", "currency",
                "published_at", "key_skills", "grade", "domain", "processed_at",
            ],
        )
        ch.close()
        logger.info("[sync] done %s → ClickHouse", processed_uuid)
    finally:
        await conn.close()
