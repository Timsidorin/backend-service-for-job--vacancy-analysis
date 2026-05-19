import logging
from contextlib import asynccontextmanager
from typing import Dict

import httpx
import uvicorn
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse
from starlette.background import BackgroundTask

from api_gateway.config import configs
from api_gateway.middleware import LoggingMiddleware

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

client: httpx.AsyncClient


@asynccontextmanager
async def lifespan(_app: FastAPI):
    global client
    client = httpx.AsyncClient(
        timeout=configs.REQUEST_TIMEOUT,
        limits=httpx.Limits(
            max_keepalive_connections=configs.MAX_KEEPALIVE_CONNECTIONS,
            max_connections=configs.MAX_CONNECTIONS,
        ),
    )
    yield
    await client.aclose()


app = FastAPI(
    title=configs.PROJECT_NAME,
    docs_url="/docs",
    openapi_url="/openapi.json",
    description="API Gateway для микросервисной архитектуры",
    lifespan=lifespan,
)

app.add_middleware(LoggingMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_target_service(path: str) -> str:
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
            content=await request.body(),
        )

        rp_resp = await client.send(rp_req, stream=True)

        return StreamingResponse(
            rp_resp.aiter_raw(),
            status_code=rp_resp.status_code,
            headers=dict(rp_resp.headers),
            background=BackgroundTask(rp_resp.aclose),
        )
    except Exception as e:
        logger.error(f"Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.api_route(
    "/api/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"],
    summary="Проксирование запросов к микросервисам",
)
async def api_gateway(request: Request, path: str):
    """Проксирует все запросы /api/* на соответствующие микросервисы."""
    full_path = f"/api/{path}"
    return await proxy_request(request, full_path)


@app.get("/health", summary="Проверка здоровья шлюза и сервисов")
async def health_check():
    """Проверяет доступность API Gateway и всех зарегистрированных сервисов."""
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


@app.get("/admin", response_class=HTMLResponse, summary="Панель мониторинга сервисов")
async def admin_dashboard():
    """HTML-дашборд со статусом сервисов и ссылками на Swagger."""
    rows: list[Dict[str, str]] = []
    for prefix, base_url in configs.SERVICE_ROUTES.items():
        # Имя сервиса по префиксу
        name = {
            "/api/v1/auth": "Auth Service",
            "/api/v1/ml": "ML Service",
            "/api/v1/analytics": "Analytics Service",
        }.get(prefix, prefix)

        # Проверяем health
        try:
            resp = await client.get(f"{base_url}/health", timeout=5.0)
            status = "healthy" if resp.status_code == 200 else f"unhealthy ({resp.status_code})"
        except Exception as e:
            status = f"unreachable ({e})"

        # Swagger и OpenAPI через gateway
        swagger_url = f"{prefix}/docs"
        openapi_url = f"{prefix}/openapi.json"

        rows.append(
            {
                "name": name,
                "prefix": prefix,
                "base_url": base_url,
                "status": status,
                "swagger": swagger_url,
                "openapi": openapi_url,
            }
        )

    rows_html = "\n".join(
        f"""
        <tr>
          <td>{r['name']}</td>
          <td><code>{r['prefix']}</code></td>
          <td>{r['status']}</td>
          <td><a href="{r['swagger']}" target="_blank">Swagger</a></td>
          <td><a href="{r['openapi']}" target="_blank">OpenAPI</a></td>
        </tr>
        """
        for r in rows
    )

    html = f"""
    <!doctype html>
    <html lang="ru">
    <head>
      <meta charset="utf-8" />
      <title>Service Dashboard</title>
      <style>
        body {{
          font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
          margin: 0;
          padding: 2rem;
          background: #0f172a;
          color: #e5e7eb;
        }}
        h1 {{
          margin-bottom: 1.5rem;
        }}
        table {{
          width: 100%;
          border-collapse: collapse;
          background: #020617;
          border-radius: 0.5rem;
          overflow: hidden;
        }}
        th, td {{
          padding: 0.75rem 1rem;
          border-bottom: 1px solid #1f2937;
          text-align: left;
        }}
        th {{
          background: #111827;
          font-weight: 600;
        }}
        tr:hover td {{
          background: #0b1120;
        }}
        a {{
          color: #38bdf8;
          text-decoration: none;
        }}
        a:hover {{
          text-decoration: underline;
        }}
        code {{
          background: #020617;
          padding: 0.1rem 0.3rem;
          border-radius: 0.25rem;
          font-size: 0.85rem;
        }}
      </style>
    </head>
    <body>
      <h1>Дашборд Сервисов</h1>
      <p>Gateway: <strong>http://{configs.HOST}:{configs.PORT}</strong></p>
      <table>
        <thead>
          <tr>
            <th>Сервис</th>
            <th>Префикс</th>
            <th>Статус</th>
            <th>Swagger</th>
            <th>OpenAPI</th>
          </tr>
        </thead>
        <tbody>
          {rows_html}
        </tbody>
      </table>
    </body>
    </html>
    """
    return HTMLResponse(content=html)


@app.get("/", summary="Информация о шлюзе")
async def root():
    """Корневой маршрут: версия и список зарегистрированных сервисов."""
    return {
        "message": "API Gateway",
        "version": "1.0.0",
        "services": list(configs.SERVICE_ROUTES.keys())
    }

if __name__ == "__main__":
    uvicorn.run(
        "api_gateway.main:app",
        host=configs.HOST,
        port=configs.PORT,
        reload=True,
        log_level="info",
    )
