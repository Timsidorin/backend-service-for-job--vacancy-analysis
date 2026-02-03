"""
Точка входа в backend_archive
"""

from fastapi import FastAPI, APIRouter
from routing import auth_router
from core.config import configs
from core.create_base_app import create_base_app

app = create_base_app(configs)

app.include_router(auth_router.router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=configs.HOST, port=configs.PORT, reload=True)
