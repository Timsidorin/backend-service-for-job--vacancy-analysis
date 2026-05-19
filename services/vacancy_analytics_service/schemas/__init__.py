"""Pydantic-схемы ответов и запросов analytics API."""
from services.vacancy_analytics_service.schemas.analytics import (
    DateCount,
    DomainCount,
    DomainGradeCount,
    GradeCount,
    RegionCount,
    SalaryStats,
    SkillCount,
    SourceCount,
    StatsResponse,
)
from services.vacancy_analytics_service.schemas.interests import InterestsResponse
from services.vacancy_analytics_service.schemas.recommendations import (
    RecommendationsResponse,
    VacancyRecommendation,
)
from services.vacancy_analytics_service.schemas.vacancies import (
    VacancySearchItem,
    VacancySearchResponse,
)

__all__ = [
    "StatsResponse",
    "DomainCount",
    "GradeCount",
    "SalaryStats",
    "DateCount",
    "SkillCount",
    "SourceCount",
    "DomainGradeCount",
    "RegionCount",
    "InterestsResponse",
    "VacancyRecommendation",
    "RecommendationsResponse",
    "VacancySearchItem",
    "VacancySearchResponse",
]
