"""PostgreSQL connection string для семантического поиска по pgvector."""
from services.vacancy_analytics_service.config import configs


def get_pg_connection_string() -> str:
    return (
        f"postgresql://{configs.DB_USER}:{configs.DB_PASS}"
        f"@{configs.DB_HOST}:{configs.DB_PORT}/{configs.DB_NAME}"
    )
