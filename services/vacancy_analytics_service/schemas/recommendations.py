"""Схемы ответов эндпоинта рекомендаций (семантический поиск + skill gap)."""
from pydantic import BaseModel, Field


class VacancyRecommendation(BaseModel):
    processed_uuid: str
    raw_uuid: str
    title: str | None
    description: str | None
    domain: str | None
    employer: str | None
    city: str | None
    salary_from: int | None
    salary_to: int | None
    similarity: float = Field(description="Cosine similarity (0–1), семантическая близость")
    match_percent: int = Field(0, description="Итоговый процент соответствия (0–100), для резюме — гибрид")
    matched_skills: list[str] = Field(default_factory=list)
    missing_skills: list[str] = Field(default_factory=list, description="Навыки вакансии, которых нет у кандидата")
    vacancy_url: str | None = None


class RecommendationsResponse(BaseModel):
    professions: list[str] = Field(
        default_factory=list,
        description="Для VK — профессии из интересов; для резюме — desired_titles и/или навыки",
    )
    profile_source: str = Field("vk", description="Источник профиля: vk | resume")
    vacancies: list[VacancyRecommendation]
