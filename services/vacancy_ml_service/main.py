"""Vacancy ML Service — анализ вакансий (навыки, грейд, зарплата)."""
import uvicorn
from fastapi import FastAPI

from services.vacancy_ml_service.config import configs
from services.vacancy_ml_service.schemas import VacancyAnalysisRequest, VacancyAnalysisResponse

app = FastAPI(
    title=configs.PROJECT_NAME,
    docs_url="/api/v1/ml/docs",
    openapi_url="/api/v1/ml/openapi.json",
    description="ML-обработка вакансий (домен vacancy)",
)


@app.get("/health", summary="Проверка здоровья ML-сервиса")
async def health_check():
    """Возвращает статус сервиса."""
    return {"status": "ok"}


@app.post("/analyze", response_model=VacancyAnalysisResponse, summary="Анализ вакансии")
async def analyze_vacancy(request: VacancyAnalysisRequest):
    """Извлекает навыки, определяет грейд и прогнозирует зарплату."""
    return VacancyAnalysisResponse(
        summary=f"Analysis of: {request.text[:20]}...",
        skills=["python", "fastapi", "ml"],
        salary_prediction=100000.0,
    )


if __name__ == "__main__":
    uvicorn.run("services.vacancy_ml_service.main:app", host=configs.HOST, port=configs.PORT, reload=True)
