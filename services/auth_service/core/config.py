"""Конфигурация сервиса авторизации."""
import os
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Configs(BaseSettings):
    HOST: str = "localhost"
    PORT: int = 8005
    PROJECT_NAME: str = "Модуль авторизации"

    SECRET_KEY: str = Field(default="vacancy_analyt_job", env="SECRET_KEY")
    ALGORITHM: str = Field(default="HS256", env="ALGORITHM")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=60000, env="ACCESS_TOKEN_EXPIRE_MINUTES")

    DB_HOST: Optional[str] = Field(default="localhost", env="DB_HOST")
    DB_PORT: Optional[int] = Field(default=5432, env="DB_PORT")
    DB_USER: Optional[str] = Field(default="postgres", env="DATABASE_USERNAME")
    DB_NAME: Optional[str] = Field(default="job_vacancy", env="DATABASE_NAME")
    DB_PASS: Optional[str] = Field(default="admin", env="DATABASE_PASSWORD")

    model_config = SettingsConfigDict(
        env_file=os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".env"),
        extra="ignore",
    )


configs = Configs()


def get_db_url() -> str:
    return (
        f"postgresql+asyncpg://{configs.DB_USER}:{configs.DB_PASS}@"
        f"{configs.DB_HOST}:{configs.DB_PORT}/{configs.DB_NAME}"
    )
