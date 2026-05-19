import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import uvicorn
from fastapi import FastAPI
from services.auth_service.core.config import configs
from services.auth_service.auth_router import router as auth_router

app = FastAPI(
    title=configs.PROJECT_NAME,
    docs_url="/api/v1/auth/docs",
    openapi_url="/api/v1/auth/openapi.json"
)

app.include_router(
    auth_router,
    prefix="/api/v1/auth",
    tags=["Auth"]
)

@app.get("/health", summary="Проверка здоровья сервиса авторизации")
async def health_check():
    """Возвращает статус сервиса авторизации."""
    return {"status": "ok"}

if __name__ == "__main__":
    uvicorn.run(
        "services.auth_service.main:app",
        host=configs.HOST,
        port=configs.PORT,
        reload=True,
    )
