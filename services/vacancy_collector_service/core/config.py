"""Конфигурация Data Mining Service."""
from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Configs(BaseSettings):
    GEO_TOKEN: str = Field(default="", env="GEO_TOKEN")

    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[2] / ".env",
        extra="ignore",
    )


configs = Configs()