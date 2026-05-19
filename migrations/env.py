import os
import sys
from pathlib import Path

# Добавляем корень проекта в path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Загрузка .env (опционально)
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool
from alembic import context

# Metadata всех моделей (vacancies + auth)
from libs.db_models.vacancies import Base as VacanciesBase
from services.auth_service.core.database import Base as AuthBase
from services.auth_service.models.users_model import User  # регистрирует users в metadata

target_metadata = [VacanciesBase.metadata, AuthBase.metadata]

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# URL из переменных окружения (совместимо с auth_service)
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_USER = os.getenv("DATABASE_USERNAME", "postgres")
DB_PASS = os.getenv("DATABASE_PASSWORD", "admin")
DB_NAME = os.getenv("DATABASE_NAME", "job_vacancy")


def get_url():
    return f"postgresql+psycopg2://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"


def run_migrations_offline() -> None:
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = get_url()
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
