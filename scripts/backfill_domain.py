#!/usr/bin/env python3
"""
Backfill domain для processed_vacancies по правилам из rule_based_domains.

Использование:
    uv run python -m scripts.backfill_domain

Переменные окружения: DB_HOST, DB_PORT, DATABASE_USERNAME, DATABASE_PASSWORD, DATABASE_NAME
"""

import asyncio
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

PG_HOST = os.getenv("DB_HOST", "localhost")
PG_PORT = int(os.getenv("DB_PORT", "5432"))
PG_USER = os.getenv("DATABASE_USERNAME", "postgres")
PG_PASS = os.getenv("DATABASE_PASSWORD", "admin")
PG_NAME = os.getenv("DATABASE_NAME", "job_vacancy")

BATCH_SIZE = 5_000


def extract_key_skills(skills_val):
    """Извлекает key_skills из JSONB (совместимо с rule_based_domains)."""
    import json
    if skills_val is None:
        return []
    if isinstance(skills_val, dict):
        ks = skills_val.get("key_skills", [])
    elif isinstance(skills_val, str):
        try:
            data = json.loads(skills_val)
            ks = data.get("key_skills", [])
        except json.JSONDecodeError:
            return []
    else:
        return []
    return [str(s).lower() for s in (ks if isinstance(ks, list) else [])]


def get_domain(skills_list: list) -> str:
    """Присваивает домен по правилам из rule_based_domains."""
    from experiments.rule_based_domains import assign_domain
    return assign_domain(skills_list)


async def run():
    try:
        import asyncpg
    except ImportError:
        logger.error("Требуется asyncpg: uv add asyncpg")
        sys.exit(1)

    conn = await asyncpg.connect(
        f"postgresql://{PG_USER}:{PG_PASS}@{PG_HOST}:{PG_PORT}/{PG_NAME}"
    )

    total_updated = 0
    last_uuid = None

    while True:
        if last_uuid is None:
            rows = await conn.fetch(
                """
                SELECT uuid, skills
                FROM processed_vacancies
                ORDER BY uuid
                LIMIT $1
                """,
                BATCH_SIZE,
            )
        else:
            rows = await conn.fetch(
                """
                SELECT uuid, skills
                FROM processed_vacancies
                WHERE uuid > $1
                ORDER BY uuid
                LIMIT $2
                """,
                last_uuid,
                BATCH_SIZE,
            )

        if not rows:
            break

        last_uuid = rows[-1]["uuid"]
        batch = []
        for r in rows:
            skills_list = extract_key_skills(r["skills"])
            domain = get_domain(skills_list)
            batch.append((domain, r["uuid"]))

        await conn.executemany(
            "UPDATE processed_vacancies SET domain = $1 WHERE uuid = $2",
            batch,
        )
        total_updated += len(batch)
        logger.info("Обновлено %d строк, всего: %d", len(batch), total_updated)

        if len(rows) < BATCH_SIZE:
            break

    await conn.close()
    logger.info("Готово. Всего обновлено domain: %d", total_updated)


def main():
    asyncio.run(run())


if __name__ == "__main__":
    main()
