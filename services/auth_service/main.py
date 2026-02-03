# main.py
import uvicorn
from fastapi import FastAPI
from config import configs
from auth_router import router as auth_router

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

@app.get("/health")
async def health_check():
    return {"status": "ok"}

if __name__ == "__main__":
    uvicorn.run("main:app", host=configs.HOST, port=configs.PORT, reload=True)
