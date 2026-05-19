"""Конфигурация API Gateway."""
from pathlib import Path
from typing import Dict

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "API Gateway"
    HOST: str = "localhost"
    PORT: int = 8000

    SERVICE_ROUTES: Dict[str, str] = {
        "/api/v1/auth": "http://localhost:8005",
        "/api/v1/ml": "http://localhost:8001",
        "/api/v1/analytics": "http://localhost:8002",
        "/api/v1/mining": "http://localhost:8003",
    }

    REQUEST_TIMEOUT: int = 30
    MAX_KEEPALIVE_CONNECTIONS: int = 10
    MAX_CONNECTIONS: int = 100
    CORS_ALLOW_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"

    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[1] / ".env",
        case_sensitive=True,
        extra="ignore",
    )


configs = Settings()
