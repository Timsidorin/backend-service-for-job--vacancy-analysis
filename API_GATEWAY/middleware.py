from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
import logging
import time

logger = logging.getLogger(__name__)


class LoggingMiddleware(BaseHTTPMiddleware):
    """Middleware для логирования всех запросов"""

    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        logger.info(
            f"Входящий запрос: {request.method} {request.url.path} "
            f"От {request.client.host if request.client else 'unknown'}"
        )

        response = await call_next(request)
        process_time = time.time() - start_time
        logger.info(
            f"Запрос выполнен: {request.method} {request.url.path} "
            f"Статус: {response.status_code} Time: {process_time:.2f}s"
        )
        response.headers["X-Process-Time"] = str(process_time)
        return response
