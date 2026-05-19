from pydantic import BaseModel

class VacancyAnalysisRequest(BaseModel):
    text: str
    
class VacancyAnalysisResponse(BaseModel):
    summary: str
    skills: list[str]
    salary_prediction: float | None = None
