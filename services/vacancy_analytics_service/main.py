"""Vacancy Analytics Service — аналитический API поверх ClickHouse."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import uvicorn
from fastapi import FastAPI

from services.vacancy_analytics_service.config import configs
from services.vacancy_analytics_service.routers import analytics_router
from services.vacancy_analytics_service.routers.candidate import router as candidate_router
from services.vacancy_analytics_service.routers.interests import router as interests_router
from services.vacancy_analytics_service.routers.recommendations import router as recommendations_router
from services.vacancy_analytics_service.routers.vacancies import router as vacancies_router

app = FastAPI(
    title=configs.PROJECT_NAME,
    docs_url="/api/v1/analytics/docs",
    openapi_url="/api/v1/analytics/openapi.json",
    description="Аналитика вакансий на базе ClickHouse",
)

app.include_router(analytics_router)
app.include_router(candidate_router)
app.include_router(interests_router)
app.include_router(recommendations_router)
app.include_router(vacancies_router)


@app.get("/health", summary="Проверка здоровья аналитического сервиса", tags=["Служебное"])
async def health_check():
    """Проверяет доступность сервиса и подключение к ClickHouse."""
    from services.vacancy_analytics_service.db import get_client
    try:
        client = get_client()
        client.query("SELECT 1")
        ch_status = "ok"
    except Exception as e:
        ch_status = f"error: {e}"

    return {
        "status": "ok",
        "clickhouse": ch_status,
    }


if __name__ == "__main__":
    uvicorn.run(
        "services.vacancy_analytics_service.main:app",
        host=configs.HOST,
        port=configs.PORT,
        reload=True,
    )
