"""
Kafka-клиент для pipeline вакансий.

Topics:
  vacancies.raw       — UUID новой сырой вакансии → process
  vacancies.processed — UUID обработанной вакансии → embed
  vacancies.embedded  — UUID → sync to ClickHouse
"""
import json
import logging
from uuid import UUID

from aiokafka import AIOKafkaProducer

logger = logging.getLogger(__name__)

TOPIC_RAW = "vacancies.raw"
TOPIC_PROCESSED = "vacancies.processed"
TOPIC_EMBEDDED = "vacancies.embedded"


class KafkaClient:
    def __init__(self, bootstrap_servers: str):
        self.bootstrap_servers = bootstrap_servers
        self._producer: AIOKafkaProducer | None = None

    async def start(self):
        self._producer = AIOKafkaProducer(
            bootstrap_servers=self.bootstrap_servers,
            value_serializer=lambda v: json.dumps(v, default=str).encode("utf-8"),
        )
        await self._producer.start()
        logger.info("Kafka producer started: %s", self.bootstrap_servers)

    async def stop(self):
        if self._producer:
            await self._producer.stop()
            self._producer = None
            logger.info("Kafka producer stopped")

    async def publish_vacancy_uuid(self, uuid: UUID, topic: str):
        if not self._producer:
            await self.start()
        payload = {"uuid": str(uuid)}
        await self._producer.send_and_wait(topic, value=payload)
        logger.info("Published to %s: %s", topic, payload)

    async def produce(self, topic: str, payload: dict):
        if not self._producer:
            await self.start()
        await self._producer.send_and_wait(topic, value=payload)
        logger.debug("Published to %s: %s", topic, payload)
