import logging
import os
from datetime import datetime
from typing import Optional, Tuple

import asyncpg

from libs.common.schemas.vacancy import RawVacancyCreate
from libs.messaging.kafka_client import TOPIC_RAW

logger = logging.getLogger(__name__)


async def save_vacancy(conn: asyncpg.Connection, vacancy_dto: RawVacancyCreate) -> Optional[str]:
    """Save vacancy to raw_vacancies and return UUID if inserted."""
    import json

    row = await conn.fetchrow(
        """
        INSERT INTO raw_vacancies (
            source, url, title, description, full_text,
            city, region, region_code,
            employer, salary_from, salary_to, currency,
            published_at, raw_data
        ) VALUES (
            $1, $2, $3, $4, $5,
            $6, $7, $8,
            $9, $10, $11, $12,
            $13, $14::jsonb
        )
        ON CONFLICT DO NOTHING
        RETURNING uuid
        """,
        vacancy_dto.source,
        vacancy_dto.url,
        vacancy_dto.title,
        vacancy_dto.description,
        vacancy_dto.full_text,
        vacancy_dto.city,
        vacancy_dto.region,
        vacancy_dto.region_code,
        vacancy_dto.employer,
        vacancy_dto.salary_from,
        vacancy_dto.salary_to,
        vacancy_dto.currency,
        vacancy_dto.published_at,
        json.dumps(vacancy_dto.raw_data, ensure_ascii=False, default=str),
    )

    if row:
        saved_uuid = str(row["uuid"])
        logger.info("Saved: %s — %s", saved_uuid, vacancy_dto.title)
        return saved_uuid
    return None


async def load_state(conn: asyncpg.Connection, source: str) -> Tuple[Optional[datetime], Optional[str]]:
    row = await conn.fetchrow(
        "SELECT last_published_at, last_url FROM vacancy_sources_state WHERE source = $1",
        source,
    )
    if not row:
        return None, None
    return row["last_published_at"], row["last_url"]


async def save_state(
    conn: asyncpg.Connection,
    source: str,
    last_published_at: Optional[datetime],
    last_url: Optional[str],
) -> None:
    await conn.execute(
        """
        INSERT INTO vacancy_sources_state (source, last_published_at, last_url)
        VALUES ($1, $2, $3)
        ON CONFLICT (source) DO UPDATE
        SET last_published_at = EXCLUDED.last_published_at,
            last_url = EXCLUDED.last_url,
            updated_at = now()
        """,
        source,
        last_published_at,
        last_url,
    )


async def run_connector_cycle(*, source: str, connector, kafka=None) -> None:
    """Run one collection cycle for a connector."""
    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_PORT = int(os.getenv("DB_PORT", "5432"))
    DB_USER = os.getenv("DATABASE_USERNAME", "postgres")
    DB_PASS = os.getenv("DATABASE_PASSWORD", "admin")
    DB_NAME = os.getenv("DATABASE_NAME", "job_vacancy")

    conn = await asyncpg.connect(f"postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}")

    try:
        since_published_at, _since_url = await load_state(conn, source)
        logger.info("Mining cycle for %s since %s", source, since_published_at)

        last_seen: Optional[datetime] = since_published_at
        last_url: Optional[str] = None

        async for vacancy in connector.collect_vacancies(since=since_published_at):
            saved_uuid = await save_vacancy(conn, vacancy)
            if saved_uuid:
                if kafka:
                    try:
                        await kafka.publish_vacancy_uuid(saved_uuid, topic=TOPIC_RAW)
                    except Exception:
                        logger.exception("Failed to publish %s to Kafka", saved_uuid)
                if vacancy.published_at:
                    if last_seen is None or vacancy.published_at > last_seen:
                        last_seen = vacancy.published_at
                    last_url = vacancy.url
                break

        if last_seen:
            await save_state(conn, source, last_seen, last_url)
    finally:
        await conn.close()
