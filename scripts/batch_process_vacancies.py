#!/usr/bin/env python3
"""
Batch-обработка raw_vacancies → processed_vacancies.

Заполняет таблицу processed_vacancies: извлекает навыки (из raw_data.key_skills)
и уровень (grade) по title/description для всех сырых вакансий, которые ещё
не обработаны. Поддерживает все источники (hh, rabotaru, rvr, superjob).

Структура raw_data (после import_vacancies_csv): external_id, key_skills,
experience, requirements, raw_skills, role_name, source_type и др.

Использование:
    uv run python -m scripts.batch_process_vacancies
    uv run python -m scripts.batch_process_vacancies --limit 10000

Переменные окружения (или .env):
    DB_HOST, DB_PORT, DATABASE_USERNAME, DATABASE_PASSWORD, DATABASE_NAME
"""

import argparse
import asyncio
import json
import logging
import os
import sys
from pathlib import Path

# Добавляем корень проекта в path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Загрузка .env (если установлен python-dotenv)
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

# Настройки по умолчанию (совместимы с auth_service)
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_USER = os.getenv("DATABASE_USERNAME", "postgres")
DB_PASS = os.getenv("DATABASE_PASSWORD", "admin")
DB_NAME = os.getenv("DATABASE_NAME", "job_vacancy")

BATCH_SIZE = 5_000

# Только вакансии, для которых ещё нет записи в processed_vacancies
SQL_SELECT_UNPROCESSED = """
    SELECT r.uuid, r.title, r.description, r.full_text, r.raw_data
    FROM raw_vacancies r
    LEFT JOIN processed_vacancies p ON p.raw_vacancy_uuid = r.uuid
    WHERE p.uuid IS NULL
    ORDER BY r.uuid
    LIMIT $1
"""
SQL_SELECT_UNPROCESSED_AFTER = """
    SELECT r.uuid, r.title, r.description, r.full_text, r.raw_data
    FROM raw_vacancies r
    LEFT JOIN processed_vacancies p ON p.raw_vacancy_uuid = r.uuid
    WHERE p.uuid IS NULL AND r.uuid > $1
    ORDER BY r.uuid
    LIMIT $2
"""


def get_connection_string() -> str:
    return f"postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"


async def run(limit: int | None = None):
    try:
        import asyncpg
    except ImportError:
        logger.error("Требуется asyncpg: uv add asyncpg")
        sys.exit(1)

    try:
        from services.vacancy_ml_service.pipeline.processor import process_raw_vacancy
    except ImportError as e:
        logger.error("Ошибка импорта pipeline: %s", e)
        sys.exit(1)

    conn_str = get_connection_string()
    logger.info("Подключение к БД: %s@%s/%s", DB_USER, DB_HOST, DB_NAME)

    conn = await asyncpg.connect(conn_str)

    try:
        total_raw = await conn.fetchval("SELECT COUNT(*) FROM raw_vacancies")
        unprocessed = await conn.fetchval(
            """SELECT COUNT(*) FROM raw_vacancies r
               LEFT JOIN processed_vacancies p ON p.raw_vacancy_uuid = r.uuid
               WHERE p.uuid IS NULL"""
        )
        logger.info("Всего raw: %d, не обработано: %d", total_raw, unprocessed)

        if unprocessed == 0:
            logger.info("Нет необработанных вакансий.")
            return

        batch_limit = min(BATCH_SIZE, limit) if limit else BATCH_SIZE
        last_uuid = None
        total_processed = 0
        total_inserted = 0

        while True:
            if limit is not None and total_inserted >= limit:
                break
            fetch_size = batch_limit
            if limit is not None:
                fetch_size = min(batch_limit, limit - total_inserted)

            if last_uuid is None:
                rows = await conn.fetch(SQL_SELECT_UNPROCESSED, fetch_size)
            else:
                rows = await conn.fetch(SQL_SELECT_UNPROCESSED_AFTER, last_uuid, fetch_size)

            if not rows:
                break

            last_uuid = rows[-1]["uuid"]
            batch_to_insert = []
            for row in rows:
                raw_uuid = row["uuid"]
                title = row["title"] or ""
                description = row["description"] or ""
                full_text = row["full_text"]
                raw_data = row["raw_data"] or {}
                # raw_data из JSONB может прийти как строка (двойное кодирование при загрузке)
                if isinstance(raw_data, str):
                    try:
                        raw_data = json.loads(raw_data)
                    except json.JSONDecodeError:
                        raw_data = {}

                try:
                    skills, grade = process_raw_vacancy(
                        raw_vacancy_uuid=raw_uuid,
                        title=title,
                        description=description,
                        full_text=full_text,
                        raw_data=raw_data,
                    )
                except Exception as e:
                    logger.warning("Ошибка обработки %s: %s", raw_uuid, e)
                    continue

                # domain по правилам из rule_based_domains
                key_skills = skills.get("key_skills", []) if isinstance(skills, dict) else []
                skills_lower = [str(s).lower() for s in (key_skills if isinstance(key_skills, list) else [])]
                try:
                    from experiments.rule_based_domains import assign_domain
                    domain = assign_domain(skills_lower)
                except ImportError:
                    domain = "Общие/Универсальные"

                batch_to_insert.append((raw_uuid, json.dumps(skills, ensure_ascii=False), grade, domain))
                total_processed += 1

            if batch_to_insert:
                await conn.executemany(
                    """
                    INSERT INTO processed_vacancies (raw_vacancy_uuid, skills, grade_prediction, domain)
                    VALUES ($1, $2::jsonb, $3, $4)
                    ON CONFLICT (raw_vacancy_uuid) DO UPDATE SET
                        skills = EXCLUDED.skills,
                        grade_prediction = EXCLUDED.grade_prediction,
                        domain = EXCLUDED.domain
                    """,
                    batch_to_insert,
                )
                total_inserted += len(batch_to_insert)

            logger.info(
                "Батч: обработано %d, вставлено %d | всего: %d",
                len(rows),
                len(batch_to_insert),
                total_inserted,
            )

            if len(rows) < fetch_size:
                break

        logger.info("Готово. Обработано: %d, добавлено в processed: %d", total_processed, total_inserted)

    finally:
        await conn.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None, help="Макс. количество вакансий для обработки")
    args = parser.parse_args()
    asyncio.run(run(limit=args.limit))


if __name__ == "__main__":
    main()
