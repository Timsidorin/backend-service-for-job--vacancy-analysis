#!/usr/bin/env python3
"""
ETL: PostgreSQL (raw_vacancies + processed_vacancies) → ClickHouse (vacancies_analytics).

Использование:
    uv run python -m scripts.sync_to_clickhouse          # полная загрузка
    uv run python -m scripts.sync_to_clickhouse --incremental   # только новые (по processed_at)

После добавления domain: для полной пересинхронизации с domain — truncate таблицу
и выполните полную загрузку без --incremental.

Переменные окружения:
    DB_* — PostgreSQL
    CLICKHOUSE_HOST, CLICKHOUSE_PORT, CLICKHOUSE_USER, CLICKHOUSE_PASSWORD, CLICKHOUSE_DB
"""

import argparse
import asyncio
import json
import logging
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# PostgreSQL
PG_HOST = os.getenv("DB_HOST", "localhost")
PG_PORT = int(os.getenv("DB_PORT", "5432"))
PG_USER = os.getenv("DATABASE_USERNAME", "postgres")
PG_PASS = os.getenv("DATABASE_PASSWORD", "admin")
PG_NAME = os.getenv("DATABASE_NAME", "job_vacancy")

# ClickHouse
CH_HOST = os.getenv("CLICKHOUSE_HOST", "localhost")
CH_PORT = int(os.getenv("CLICKHOUSE_PORT", "8123"))
CH_USER = os.getenv("CLICKHOUSE_USER", "default")
CH_PASS = os.getenv("CLICKHOUSE_PASSWORD", "secret_password")
CH_DB = os.getenv("CLICKHOUSE_DB", "vacancies")

BATCH_SIZE = 20_000


def _ensure_dict(val):
    if val is None:
        return {}
    if isinstance(val, dict):
        return val
    if isinstance(val, str):
        try:
            return json.loads(val)
        except json.JSONDecodeError:
            return {}
    return {}


def _get_key_skills(skills_val):
    data = _ensure_dict(skills_val)
    ks = data.get("key_skills", [])
    return ks if isinstance(ks, list) else []


async def fetch_from_postgres(conn, last_processed_at=None, limit=BATCH_SIZE):
    """Читает raw JOIN processed из PostgreSQL батчами."""
    if last_processed_at is not None:
        return await conn.fetch(
            """
            SELECT
                r.uuid AS raw_uuid, p.uuid AS processed_uuid,
                r.source, r.title, r.description, r.city, r.region, r.region_code,
                r.employer, r.salary_from, r.salary_to, r.currency, r.published_at,
                p.skills, p.grade_prediction AS grade, p.domain, p.processed_at
            FROM raw_vacancies r
            INNER JOIN processed_vacancies p ON p.raw_vacancy_uuid = r.uuid
            WHERE p.processed_at > $1
            ORDER BY p.processed_at LIMIT $2
            """,
            last_processed_at,
            limit,
        )
    return await conn.fetch(
        """
        SELECT
            r.uuid AS raw_uuid, p.uuid AS processed_uuid,
            r.source, r.title, r.description, r.city, r.region, r.region_code,
            r.employer, r.salary_from, r.salary_to, r.currency, r.published_at,
            p.skills, p.grade_prediction AS grade, p.domain, p.processed_at
        FROM raw_vacancies r
        INNER JOIN processed_vacancies p ON p.raw_vacancy_uuid = r.uuid
        ORDER BY p.processed_at LIMIT $1
        """,
        limit,
    )


def row_to_clickhouse(row):
    """Преобразует строку PostgreSQL в кортеж для ClickHouse."""
    salary_from = row["salary_from"]
    salary_to = row["salary_to"]
    salary_typical = None
    if salary_from is not None and salary_to is not None:
        salary_typical = (salary_from + salary_to) // 2
    elif salary_from is not None:
        salary_typical = salary_from
    elif salary_to is not None:
        salary_typical = salary_to

    key_skills = _get_key_skills(row["skills"])
    published_at = row["published_at"]
    processed_at = row["processed_at"]
    domain = row.get("domain")

    return (
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
        published_at,
        key_skills,
        row["grade"],
        domain,
        processed_at,
    )


async def run(incremental: bool):
    try:
        import asyncpg
    except ImportError:
        logger.error("Требуется asyncpg")
        sys.exit(1)

    try:
        import clickhouse_connect
    except ImportError:
        logger.error("Требуется clickhouse-connect: uv add clickhouse-connect")
        sys.exit(1)

    pg_conn = await asyncpg.connect(
        f"postgresql://{PG_USER}:{PG_PASS}@{PG_HOST}:{PG_PORT}/{PG_NAME}"
    )

    ch_client = clickhouse_connect.get_client(
        host=CH_HOST,
        port=CH_PORT,
        username=CH_USER,
        password=CH_PASS,
        database="default",
    )

    # Создать БД и таблицу при первом запуске
    init_sql = ROOT / "infra" / "clickhouse" / "init.sql"
    if init_sql.exists():
        logger.info("Создаю БД и таблицу vacancies_analytics (IF NOT EXISTS)...")
        for stmt in init_sql.read_text(encoding="utf-8").split(";"):
            stmt = stmt.strip()
            if stmt:
                ch_client.command(stmt)

    ch_client.database = CH_DB

    last_processed_at = None
    if incremental:
        try:
            last = ch_client.query(f"SELECT max(processed_at) as m FROM {CH_DB}.vacancies_analytics")
            if last.result_rows and last.first_row[0]:
                last_processed_at = last.first_row[0]
                logger.info("Инкремент: после %s", last_processed_at)
        except Exception:
            pass

    total = 0
    while True:
        rows = await fetch_from_postgres(pg_conn, last_processed_at)
        if not rows:
            break

        data = [row_to_clickhouse(r) for r in rows]
        ch_client.insert(
            f"{CH_DB}.vacancies_analytics",
            data,
            column_names=[
                "raw_uuid", "processed_uuid", "source", "title", "description",
                "city", "region", "region_code", "employer",
                "salary_from", "salary_to", "salary_typical", "currency",
                "published_at", "key_skills", "grade", "domain", "processed_at",
            ],
        )
        total += len(data)
        last_processed_at = rows[-1]["processed_at"]
        logger.info("Загружено %d строк, всего: %d", len(data), total)

        if len(rows) < BATCH_SIZE:
            break

    await pg_conn.close()
    ch_client.close()
    logger.info("Готово. Всего загружено в ClickHouse: %d", total)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--incremental", action="store_true", help="Только новые записи")
    args = parser.parse_args()
    asyncio.run(run(incremental=args.incremental))


if __name__ == "__main__":
    main()
