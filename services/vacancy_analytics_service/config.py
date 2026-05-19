"""Конфигурация Vacancy Analytics Service."""
from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    PROJECT_NAME: str = "Vacancy Analytics Service"
    HOST: str = "localhost"
    PORT: int = 8002

    # PostgreSQL
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_USER: str = Field(default="postgres", validation_alias="DATABASE_USERNAME")
    DB_PASS: str = Field(default="admin", validation_alias="DATABASE_PASSWORD")
    DB_NAME: str = Field(default="job_vacancy", validation_alias="DATABASE_NAME")

    # ClickHouse
    CLICKHOUSE_HOST: str = "localhost"
    CLICKHOUSE_PORT: int = 8123
    CLICKHOUSE_USER: str = "default"
    CLICKHOUSE_PASSWORD: str = "secret_password"
    CLICKHOUSE_DB: str = "vacancies"

    AUTH_SERVICE_URL: str = "http://localhost:8005"

    # VK API
    VK_ACCESS_TOKEN: Optional[str] = None

    # LLM
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_BASE_URL: Optional[str] = None
    OPENAI_INTERESTS_MODEL: str = "qwen/qwen3-vl-flash"
    OPENAI_EMBEDDING_MODEL: str = "text-embedding-3-small"
    OPENAI_RESUME_MODEL: str = "gpt-4o-mini"

    # Резюме (PDF): каталог хранения относительно корня репозитория
    RESUME_UPLOAD_DIR: Path = Field(default=_ROOT / "uploads" / "resumes")
    MAX_RESUME_BYTES: int = 10 * 1024 * 1024  # 10 МБ

    # Гибридный скор рекомендаций (резюме): семантика + пересечение навыков
    RECOMMEND_HYBRID_ALPHA: float = 0.7
    RECOMMEND_HYBRID_BETA: float = 0.3

    model_config = SettingsConfigDict(
        env_file=_ROOT / ".env",
        extra="ignore",
    )


configs = Settings()
