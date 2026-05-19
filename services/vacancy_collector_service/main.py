"""Vacancy Collector Service — сбор вакансий в реальном времени."""
import logging
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI

from libs.messaging.kafka_client import KafkaClient
from services.vacancy_collector_service.connectors.avito.main import AvitoConnector
from services.vacancy_collector_service.connectors.hh.main import HHConnector
from services.vacancy_collector_service.routers import mining_router
from services.vacancy_collector_service.services.mining import run_connector_cycle

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    kafka_servers = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
    kafka = KafkaClient(kafka_servers)
    try:
        await kafka.start()
    except Exception as e:
        logger.warning("Kafka unavailable, vacancies won't be published: %s", e)
        kafka = None

    app.state.kafka = kafka

    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        run_connector_cycle,
        trigger="interval",
        minutes=1,
        id="hh_connector_job",
        replace_existing=True,
        kwargs={"source": "hh.ru", "connector": HHConnector(), "kafka": kafka},
    )
    scheduler.add_job(
        run_connector_cycle,
        trigger="interval",
        minutes=1,
        id="avito_connector_job",
        replace_existing=True,
        kwargs={"source": "avito", "connector": AvitoConnector(), "kafka": kafka},
    )
    scheduler.start()
    app.state.scheduler = scheduler
    yield
    scheduler.shutdown(wait=False)
    if kafka:
        await kafka.stop()


app = FastAPI(
    title="Vacancy Collector Service",
    docs_url="/api/v1/mining/docs",
    openapi_url="/api/v1/mining/openapi.json",
    lifespan=lifespan,
)
app.include_router(mining_router)


@app.get("/health", summary="Проверка здоровья сервиса сбора")
async def health() -> dict:
    """Возвращает статус сервиса сбора вакансий."""
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("services.vacancy_collector_service.main:app", host="localhost", port=8003, reload=True)
