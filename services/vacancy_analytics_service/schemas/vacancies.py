"""Схемы ответов эндпоинта поиска вакансий."""
from pydantic import BaseModel


class VacancySearchItem(BaseModel):
    raw_uuid: str
    processed_uuid: str
    title: str | None
    description: str | None
    source: str | None
    domain: str | None
    employer: str | None
    city: str | None
    region: str | None
    salary_from: int | None
    salary_to: int | None
    published_at: str | None
    grade: str | None
    url: str | None


class VacancySearchResponse(BaseModel):
    total: int
    items: list[VacancySearchItem]
    limit: int
    offset: int
