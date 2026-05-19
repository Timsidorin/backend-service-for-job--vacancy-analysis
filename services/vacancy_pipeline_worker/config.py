"""Конфигурация Vacancy Pipeline Worker."""
from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # PostgreSQL
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DATABASE_USERNAME: str = "postgres"
    DATABASE_PASSWORD: str = "admin"
    DATABASE_NAME: str = "job_vacancy"

    # Kafka
    KAFKA_BOOTSTRAP_SERVERS: str = "localhost:9092"
    KAFKA_TOPIC_RAW: str = "vacancies.raw"
    KAFKA_TOPIC_PROCESSED: str = "vacancies.processed"
    KAFKA_TOPIC_EMBEDDED: str = "vacancies.embedded"

    # ClickHouse
    CLICKHOUSE_HOST: str = "localhost"
    CLICKHOUSE_PORT: int = 8123
    CLICKHOUSE_USER: str = "default"
    CLICKHOUSE_PASSWORD: str = "secret_password"
    CLICKHOUSE_DB: str = "vacancies"

    # OpenAI / Embeddings
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_BASE_URL: Optional[str] = None
    OPENAI_EMBEDDING_MODEL: str = "text-embedding-3-small"

    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[2] / ".env",
        extra="ignore",
    )

    @property
    def pg_dsn(self) -> str:
        return (
            f"postgresql://{self.DATABASE_USERNAME}:{self.DATABASE_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DATABASE_NAME}"
        )


configs = Settings()
