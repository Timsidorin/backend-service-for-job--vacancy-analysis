from pydantic_settings import BaseSettings
from typing import Dict


class Settings(BaseSettings):
    PROJECT_NAME: str = "API Gateway"
    HOST: str = "localhost"
    PORT: int = 8000

    # Маппинг сервисов
    SERVICE_ROUTES: Dict[str, str] = {
        "/api/v1/auth": "http://localhost:8005",
    }

    # Настройки для httpx
    REQUEST_TIMEOUT: int = 30
    MAX_KEEPALIVE_CONNECTIONS: int = 10
    MAX_CONNECTIONS: int = 100

    class Config:
        env_file = ".env"
        case_sensitive = True


configs = Settings()
