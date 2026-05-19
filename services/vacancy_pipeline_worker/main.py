#!/usr/bin/env python3
"""
Vacancy Pipeline Worker — event-driven обработка вакансий через Kafka.

Топики:
  vacancies.raw       → process (извлечение навыков, грейда)
  vacancies.processed → embed   (построение эмбеддингов)
  vacancies.embedded  → sync    (синхронизация в ClickHouse)

Запуск:
    uv run python -m services.vacancy_pipeline_worker.main
"""
import asyncio
import json
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
except ImportError:
    pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("vacancy_pipeline_worker")

from aiokafka import AIOKafkaConsumer
from aiokafka.errors import KafkaError

from libs.messaging.kafka_client import KafkaClient
from services.vacancy_pipeline_worker.config import configs
from services.vacancy_pipeline_worker.handlers import handle_embed, handle_process, handle_sync


async def consume_raw(consumer: AIOKafkaConsumer, kafka: KafkaClient):
    """Читает vacancies.raw ({uuid}) и вызывает handle_process."""
    async for msg in consumer:
        try:
            payload = json.loads(msg.value)
        except json.JSONDecodeError:
            continue
        raw_uuid = payload.get("uuid")
        if not raw_uuid:
            continue
        try:
            await handle_process({"uuid": raw_uuid}, kafka)
        except Exception:
            logger.exception("Error processing raw vacancy %s", raw_uuid)


async def consume_processed(consumer: AIOKafkaConsumer, kafka: KafkaClient):
    """Читает vacancies.processed и вызывает handle_embed."""
    async for msg in consumer:
        try:
            payload = json.loads(msg.value)
        except json.JSONDecodeError:
            continue
        uuid_val = payload.get("uuid")
        if not uuid_val:
            continue
        try:
            await handle_embed({"uuid": uuid_val}, kafka)
        except Exception:
            logger.exception("Error embedding vacancy %s", uuid_val)


async def consume_embedded(consumer: AIOKafkaConsumer, kafka: KafkaClient):
    """Читает vacancies.embedded и вызывает handle_sync."""
    async for msg in consumer:
        try:
            payload = json.loads(msg.value)
        except json.JSONDecodeError:
            continue
        uuid_val = payload.get("uuid")
        if not uuid_val:
            continue
        try:
            await handle_sync({"uuid": uuid_val}, kafka)
        except Exception:
            logger.exception("Error syncing vacancy %s", uuid_val)


def _make_consumer(topic: str, group_id: str) -> AIOKafkaConsumer:
    return AIOKafkaConsumer(
        topic,
        bootstrap_servers=configs.KAFKA_BOOTSTRAP_SERVERS,
        group_id=group_id,
        auto_offset_reset="earliest",
        session_timeout_ms=30000,
        request_timeout_ms=40000,
    )


async def _start_consumer(topic: str, group_id: str, max_attempts: int = 30) -> AIOKafkaConsumer:
    """Создаёт и запускает consumer, пересоздавая объект при каждой неудачной попытке."""
    for attempt in range(1, max_attempts + 1):
        consumer = _make_consumer(topic, group_id)
        try:
            await asyncio.wait_for(consumer.start(), timeout=15.0)
            logger.info("Consumer for %s started (attempt %d)", topic, attempt)
            return consumer
        except Exception as e:
            try:
                await consumer.stop()
            except Exception:
                pass
            wait = min(5 * attempt, 30)
            logger.warning(
                "Consumer %s start failed (attempt %d/%d), retry in %ds: %s",
                topic, attempt, max_attempts, wait, e,
            )
            await asyncio.sleep(wait)
    raise RuntimeError("Consumer %s not available after %d attempts" % (topic, max_attempts))


async def run():
    kafka = KafkaClient(configs.KAFKA_BOOTSTRAP_SERVERS)
    consumers: list[AIOKafkaConsumer] = []

    try:
        await kafka.start()

        consumer_raw = await _start_consumer(configs.KAFKA_TOPIC_RAW, "pipeline-worker-raw")
        consumers.append(consumer_raw)

        consumer_processed = await _start_consumer(configs.KAFKA_TOPIC_PROCESSED, "pipeline-worker-embed")
        consumers.append(consumer_processed)

        consumer_embedded = await _start_consumer(configs.KAFKA_TOPIC_EMBEDDED, "pipeline-worker-sync")
        consumers.append(consumer_embedded)

        logger.info(
            "Pipeline worker started. Listening: %s, %s, %s",
            configs.KAFKA_TOPIC_RAW,
            configs.KAFKA_TOPIC_PROCESSED,
            configs.KAFKA_TOPIC_EMBEDDED,
        )

        await asyncio.gather(
            consume_raw(consumer_raw, kafka),
            consume_processed(consumer_processed, kafka),
            consume_embedded(consumer_embedded, kafka),
        )
    except (KafkaError, asyncio.CancelledError, KeyboardInterrupt) as e:
        if not isinstance(e, asyncio.CancelledError):
            logger.error("Stopping: %s", e)
    finally:
        for c in consumers:
            try:
                await c.stop()
            except Exception:
                pass
        try:
            await kafka.stop()
        except Exception:
            pass


def main():
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        logger.info("Pipeline worker stopped")


if __name__ == "__main__":
    main()
