"""Схемы ответов эндпоинтов аналитики (ClickHouse)."""
from datetime import date
from typing import Optional

from pydantic import BaseModel


class StatsResponse(BaseModel):
    total_vacancies: int
    with_salary: int
    unique_employers: int


class DomainCount(BaseModel):
    domain: Optional[str] = None
    count: int


class GradeCount(BaseModel):
    grade: Optional[str] = None
    count: int


class SalaryStats(BaseModel):
    domain: Optional[str] = None
    grade: Optional[str] = None
    median_salary: Optional[int] = None
    avg_salary: Optional[float] = None
    count: int


class DateCount(BaseModel):
    date: date
    count: int


class SkillCount(BaseModel):
    skill: str
    count: int


class SourceCount(BaseModel):
    source: str
    count: int


class DomainGradeCount(BaseModel):
    domain: Optional[str] = None
    grade: Optional[str] = None
    count: int


class RegionCount(BaseModel):
    region: Optional[str] = None
    count: int
