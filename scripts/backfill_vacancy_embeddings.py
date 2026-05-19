#!/usr/bin/env python3
"""
Заполняет эмбеддингами таблицу processed_vacancies.embedding для всех обработанных вакансий.

Ранее использовалась отдельная таблица vacancy_embeddings; теперь храним вектор
непосредственно в processed_vacancies (pgvector).

Использование:
    uv run python -m scripts.backfill_vacancy_embeddings
    uv run python -m scripts.backfill_vacancy_embeddings --limit 1000   # тест на выборке

Переменные окружения: DB_*, OPENAI_API_KEY, OPENAI_BASE_URL (опционально)
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

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger(__name__)

PG_HOST = os.getenv("DB_HOST", "localhost")
PG_PORT = int(os.getenv("DB_PORT", "5432"))
PG_USER = os.getenv("DATABASE_USERNAME", "postgres")
PG_PASS = os.getenv("DATABASE_PASSWORD", "admin")
PG_NAME = os.getenv("DATABASE_NAME", "job_vacancy")

OPENAI_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_BASE = os.getenv("OPENAI_BASE_URL")
OPENAI_EMBEDDING_MODEL = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")

# Можно настраивать через ENV, по умолчанию довольно агрессивные значения.
# EMB_BATCH_SIZE * EMB_CONCURRENCY = сколько текстов одновременно летит в LLM.
BATCH_SIZE = int(os.getenv("EMB_BATCH_SIZE", "512"))
CONCURRENT_REQUESTS = int(os.getenv("EMB_CONCURRENCY", "10"))


def _get_key_skills(skills_val):
    if skills_val is None:
        return []
    if isinstance(skills_val, dict):
        ks = skills_val.get("key_skills", [])
    elif isinstance(skills_val, str):
        try:
            ks = json.loads(skills_val).get("key_skills", [])
        except json.JSONDecodeError:
            return []
    else:
        return []
    return [str(s) for s in (ks if isinstance(ks, list) else [])]


def _build_text(title, description, domain, key_skills):
    from services.vacancy_analytics_service.services.embeddings import build_vacancy_text
    return build_vacancy_text(title or "", description, domain, key_skills)


async def run(limit: int | None):
    try:
        import asyncpg
    except ImportError:
        logger.error("Требуется asyncpg")
        sys.exit(1)
    if not OPENAI_KEY:
        logger.error("OPENAI_API_KEY не задан")
        sys.exit(1)

    from services.vacancy_analytics_service.services.embeddings import get_embeddings_batch_async

    conn = await asyncpg.connect(
        f"postgresql://{PG_USER}:{PG_PASS}@{PG_HOST}:{PG_PORT}/{PG_NAME}"
    )
    try:
        await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
        from pgvector.asyncpg import register_vector
        await register_vector(conn)

        # Берём только те processed_vacancies, у которых ещё нет эмбеддинга.
        query = """
            SELECT p.uuid, r.title, r.description, p.domain, p.skills
            FROM processed_vacancies p
            JOIN raw_vacancies r ON r.uuid = p.raw_vacancy_uuid
            WHERE p.embedding IS NULL
            ORDER BY p.processed_at
        """
        if limit:
            query += f" LIMIT {limit}"
        rows = await conn.fetch(query)
        if not rows:
            logger.info("Нет вакансий для обработки")
            return

        logger.info("Обработаем %d вакансий (batch=%d, concurrent=%d)", len(rows), BATCH_SIZE, CONCURRENT_REQUESTS)

        sem = asyncio.Semaphore(CONCURRENT_REQUESTS)

        async def process_batch(start: int) -> list[tuple]:
            batch = rows[start : start + BATCH_SIZE]
            if not batch:
                return []
            texts = []
            uuids = []
            for r in batch:
                ks = _get_key_skills(r["skills"])
                text = _build_text(r["title"], r["description"], r["domain"], ks)
                texts.append(text)
                uuids.append(r["uuid"])
            async with sem:
                embeddings = await get_embeddings_batch_async(
                    texts,
                    api_key=OPENAI_KEY,
                    base_url=OPENAI_BASE or None,
                    model=OPENAI_EMBEDDING_MODEL,
                )
            return list(zip(uuids, embeddings))

        total = 0
        for start in range(0, len(rows), BATCH_SIZE * CONCURRENT_REQUESTS):
            tasks = [
                process_batch(start + i * BATCH_SIZE)
                for i in range(CONCURRENT_REQUESTS)
                if start + i * BATCH_SIZE < len(rows)
            ]
            results = await asyncio.gather(*tasks)
            for batch_result in results:
                if batch_result:
                    # batch_result: List[Tuple[uuid, embedding_vector]]
                    await conn.executemany(
                        """
                        UPDATE processed_vacancies
                        SET embedding = $2::vector
                        WHERE uuid = $1
                        """,
                        batch_result,
                    )
                    total += len(batch_result)
            logger.info("Обработано %d / %d", total, len(rows))
        logger.info("Готово. Всего эмбеддингов: %d", total)
    finally:
        await conn.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()
    asyncio.run(run(limit=args.limit))


if __name__ == "__main__":
    main()
