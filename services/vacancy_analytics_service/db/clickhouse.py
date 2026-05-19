"""ClickHouse клиент для analytics service."""
import clickhouse_connect
from clickhouse_connect.driver.client import Client

from services.vacancy_analytics_service.config import configs


def get_client() -> Client:
    return clickhouse_connect.get_client(
        host=configs.CLICKHOUSE_HOST,
        port=configs.CLICKHOUSE_PORT,
        username=configs.CLICKHOUSE_USER,
        password=configs.CLICKHOUSE_PASSWORD,
        database=configs.CLICKHOUSE_DB,
    )
