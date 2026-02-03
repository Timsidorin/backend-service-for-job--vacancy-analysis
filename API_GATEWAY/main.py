import uvicorn
import httpx
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import StreamingResponse, Response
from starlette.background import BackgroundTask
from config import configs
from middleware import LoggingMiddleware
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title=configs.PROJECT_NAME,
    docs_url="/docs",
    openapi_url="/openapi.json",
    description="API Gateway для микросервисной архитектуры"
)

app.add_middleware(LoggingMiddleware)


client = httpx.AsyncClient(
    timeout=configs.REQUEST_TIMEOUT,
    limits=httpx.Limits(
        max_keepalive_connections=configs.MAX_KEEPALIVE_CONNECTIONS,
        max_connections=configs.MAX_CONNECTIONS
    )
)


@app.on_event("shutdown")
async def shutdown_event():
    """Закрываем httpx клиент при остановке приложения"""
    await client.aclose()


def get_target_service(path: str) -> str:
    """
    Определяет целевой сервис на основе пути запроса

    Args:
        path: Путь запроса

    Returns:
        URL целевого сервиса

    """
    for route_prefix, service_url in configs.SERVICE_ROUTES.items():
        if path.startswith(route_prefix):
            return service_url

    raise HTTPException(
        status_code=404,
        detail=f"Сервис для пути '{path}' не найден"
    )


async def proxy_request(request: Request, path: str):
    try:
        target_service = get_target_service(path)

        # Надежное создание URL
        base_url = httpx.URL(target_service)
        target_url = base_url.copy_with(
            path=path,
            query=request.url.query.encode("utf-8") if request.url.query else None
        )

        logger.info(f"Proxying {request.method} to {target_url}")

        headers = dict(request.headers)
        headers.pop("host", None)
        headers["X-Forwarded-For"] = request.client.host if request.client else "unknown"

        rp_req = client.build_request(
            method=request.method,
            url=target_url,
            headers=headers,
            content=await request.body(),  # Важно: await получения тела
        )

        rp_resp = await client.send(rp_req, stream=True)

        return StreamingResponse(
            rp_resp.aiter_raw(),
            status_code=rp_resp.status_code,
            headers=dict(rp_resp.headers),
            background=BackgroundTask(rp_resp.aclose),
        )
    except Exception as e:
        # ... обработка ошибок
        logger.error(f"Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.api_route(
    "/api/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"]
)
async def api_gateway(request: Request, path: str):
    """
    Главный обработчик API Gateway.
    Проксирует все запросы к /api/* на соответствующие микросервисы.
    """
    full_path = f"/api/{path}"
    return await proxy_request(request, full_path)


@app.get("/health")
async def health_check():
    """Проверка здоровья API Gateway"""
    services_status = {}
    for route, service_url in configs.SERVICE_ROUTES.items():
        try:
            response = await client.get(f"{service_url}/health", timeout=5.0)
            services_status[route] = {
                "url": service_url,
                "status": "healthy" if response.status_code == 200 else "unhealthy",
                "status_code": response.status_code
            }
        except Exception as e:
            services_status[route] = {
                "url": service_url,
                "status": "unreachable",
                "error": str(e)
            }

    return {
        "gateway": "ok",
        "services": services_status
    }


@app.get("/")
async def root():
    """Корневой путь API Gateway"""
    return {
        "message": "API Gateway",
        "version": "1.0.0",
        "services": list(configs.SERVICE_ROUTES.keys())
    }

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=configs.HOST,
        port=configs.PORT,
        reload=True,
        log_level="info"
    )
