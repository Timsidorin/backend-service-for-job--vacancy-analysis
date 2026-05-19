"""HTTP-роуты Vacancy Collector Service."""
import logging
import os

import asyncpg
from fastapi import APIRouter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/mining", tags=["Mining"])


def _pg_dsn() -> str:
    return (
        f"postgresql://{os.getenv('DATABASE_USERNAME', 'postgres')}:"
        f"{os.getenv('DATABASE_PASSWORD', 'admin')}@"
        f"{os.getenv('DB_HOST', 'localhost')}:{os.getenv('DB_PORT', '5432')}/"
        f"{os.getenv('DATABASE_NAME', 'job_vacancy')}"
    )


@router.get("/health", summary="Проверка здоровья сервиса сбора")
async def health() -> dict:
    """Возвращает статус сервиса сбора вакансий."""
    return {"status": "ok"}


@router.get("/status", summary="Статус источников данных")
async def status() -> dict:
    """Возвращает последнее время обработки по каждому источнику."""
    try:
        conn = await asyncpg.connect(_pg_dsn())
    except Exception as exc:
        logger.error("status: DB connect failed: %s", exc)
        return {"db": "error", "error": str(exc)}

    try:
        rows = await conn.fetch(
            "SELECT source, last_published_at, last_url, updated_at FROM vacancy_sources_state"
        )
        data = [
            {
                "source": r["source"],
                "last_published_at": r["last_published_at"],
                "last_url": r["last_url"],
                "updated_at": r["updated_at"],
            }
            for r in rows
        ]
        return {"db": "ok", "sources": data}
    except Exception as exc:
        logger.error("status: vacancy_sources_state read failed: %s", exc)
        return {"db": "ok", "sources": [], "warning": "vacancy_sources_state not available"}
    finally:
        await conn.close()

