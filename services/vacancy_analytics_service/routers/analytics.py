"""Analytics API — агрегаты по вакансиям из ClickHouse."""
import asyncio
from datetime import date
from typing import Optional

from fastapi import APIRouter, Query

from services.vacancy_analytics_service.config import configs
from services.vacancy_analytics_service.db import get_client
from services.vacancy_analytics_service.db.clickhouse_queries import build_where
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

router = APIRouter(prefix="/api/v1/analytics", tags=["Аналитика"])


@router.get("/stats", response_model=StatsResponse, summary="Общая статистика по вакансиям")
async def get_stats(
    domain: Optional[str] = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
):
    """Количество вакансий, вакансии с зарплатой, уникальные работодатели."""
    client = get_client()
    client.database = configs.CLICKHOUSE_DB
    where_clause, params = build_where(domain=domain, date_from=date_from, date_to=date_to)

    def _query():
        total = client.query(
            f"SELECT count() as c FROM vacancies_analytics WHERE {where_clause}",
            parameters=params,
        )
        with_sal = client.query(
            f"SELECT count() as c FROM vacancies_analytics WHERE {where_clause} AND salary_typical IS NOT NULL",
            parameters=params,
        )
        employers = client.query(
            f"SELECT uniqExact(employer) as c FROM vacancies_analytics WHERE {where_clause}",
            parameters=params,
        )
        return (
            total.first_row[0] or 0,
            with_sal.first_row[0] or 0,
            employers.first_row[0] or 0,
        )

    total, with_salary, employers = await asyncio.to_thread(_query)
    return StatsResponse(
        total_vacancies=total,
        with_salary=with_salary,
        unique_employers=employers,
    )


@router.get("/by-domain", response_model=list[DomainCount], summary="Распределение по доменам")
async def get_by_domain(
    limit: int = Query(50, ge=1, le=100),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
):
    """Группировка вакансий по профессиональным доменам."""
    client = get_client()
    client.database = configs.CLICKHOUSE_DB
    where_clause, params = build_where(date_from=date_from, date_to=date_to)
    params["limit"] = limit

    def _query():
        return client.query(
            f"""
            SELECT domain, count() as count
            FROM vacancies_analytics
            WHERE {where_clause}
            GROUP BY domain
            ORDER BY count DESC
            LIMIT {{limit:UInt32}}
            """,
            parameters=params,
        )

    result = await asyncio.to_thread(_query)
    return [DomainCount(domain=r[0], count=r[1]) for r in result.result_rows]


@router.get("/by-grade", response_model=list[GradeCount], summary="Распределение по грейдам")
async def get_by_grade(
    domain: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=50),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
):
    """Группировка вакансий по уровням: Junior, Middle, Senior."""
    client = get_client()
    client.database = configs.CLICKHOUSE_DB
    where_clause, params = build_where(domain=domain, date_from=date_from, date_to=date_to)
    params["limit"] = limit

    def _query():
        return client.query(
            f"""
            SELECT grade, count() as count
            FROM vacancies_analytics
            WHERE {where_clause}
            GROUP BY grade
            ORDER BY count DESC
            LIMIT {{limit:UInt32}}
            """,
            parameters=params,
        )

    result = await asyncio.to_thread(_query)
    return [GradeCount(grade=r[0], count=r[1]) for r in result.result_rows]


@router.get("/salary", response_model=list[SalaryStats], summary="Статистика по зарплатам")
async def get_salary_stats(
    domain: Optional[str] = Query(None),
    grade: Optional[str] = Query(None),
    group_by: str = Query("domain", description="Группировка: domain или grade"),
    limit: int = Query(30, ge=1, le=100),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
):
    """Медиана и средняя зарплата с группировкой по домену или грейду."""
    client = get_client()
    client.database = configs.CLICKHOUSE_DB

    if group_by not in ("domain", "grade"):
        group_by = "domain"
    where_clause, params = build_where(domain=domain, grade=grade, date_from=date_from, date_to=date_to)
    where_clause = "(salary_typical IS NOT NULL AND salary_typical > 0) AND " + where_clause
    params["limit"] = limit

    def _query():
        return client.query(
            f"""
            SELECT
                {group_by},
                median(salary_typical) as median_salary,
                avg(salary_typical) as avg_salary,
                count() as count
            FROM vacancies_analytics
            WHERE {where_clause}
            GROUP BY {group_by}
            ORDER BY count DESC
            LIMIT {{limit:UInt32}}
            """,
            parameters=params,
        )

    result = await asyncio.to_thread(_query)
    rows = result.result_rows
    return [
        SalaryStats(
            domain=r[0] if group_by == "domain" else None,
            grade=r[0] if group_by == "grade" else None,
            median_salary=int(r[1]) if r[1] is not None else None,
            avg_salary=float(r[2]) if r[2] is not None else None,
            count=r[3],
        )
        for r in rows
    ]


@router.get("/trends", response_model=list[DateCount], summary="Динамика публикаций")
async def get_trends(
    domain: Optional[str] = Query(None),
    days: Optional[int] = Query(
        365,
        ge=1,
        le=3650,
        description="Глубина в днях (если не задан date_from)",
    ),
    date_from: Optional[date] = Query(
        None,
        description="Начало периода (отменяет параметр days)",
    ),
    date_to: Optional[date] = Query(None),
):
    """Количество публикаций вакансий по дням за указанный период."""
    client = get_client()
    client.database = configs.CLICKHOUSE_DB
    where_clause, params = build_where(domain=domain, date_from=date_from, date_to=date_to)

    # Если явно задан date_from, не режем период по days.
    extra_filter = ""
    if date_from is None and days is not None:
        params["days"] = days
        extra_filter = " AND published_date >= today() - {days:UInt32}"

    def _query():
        return client.query(
            f"""
            SELECT published_date as d, count() as count
            FROM vacancies_analytics
            WHERE {where_clause}{extra_filter}
            GROUP BY published_date
            ORDER BY published_date
            """,
            parameters=params,
        )

    result = await asyncio.to_thread(_query)
    return [DateCount(date=r[0], count=r[1]) for r in result.result_rows]


@router.get("/top-skills", response_model=list[SkillCount], summary="Топ навыков")
async def get_top_skills(
    domain: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
):
    """Самые востребованные навыки по частоте упоминаний в вакансиях."""
    client = get_client()
    client.database = configs.CLICKHOUSE_DB
    where_clause, params = build_where(domain=domain, date_from=date_from, date_to=date_to)
    where_clause = "(length(key_skills) > 0) AND " + where_clause
    params["limit"] = limit

    def _query():
        return client.query(
            f"""
            SELECT arrayJoin(key_skills) as skill, count() as count
            FROM vacancies_analytics
            WHERE {where_clause}
            GROUP BY skill
            ORDER BY count DESC
            LIMIT {{limit:UInt32}}
            """,
            parameters=params,
        )

    result = await asyncio.to_thread(_query)
    return [SkillCount(skill=r[0], count=r[1]) for r in result.result_rows]


@router.get("/by-region", response_model=list[RegionCount], summary="Распределение по регионам")
async def get_by_region(
    domain: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
):
    """Группировка вакансий по городам."""
    client = get_client()
    client.database = configs.CLICKHOUSE_DB
    where_clause, params = build_where(domain=domain, date_from=date_from, date_to=date_to)
    where_clause = "(city IS NOT NULL AND city != '') AND " + where_clause
    params["limit"] = limit

    def _query():
        return client.query(
            f"""
            SELECT city as region, count() as count
            FROM vacancies_analytics
            WHERE {where_clause}
            GROUP BY city
            ORDER BY count DESC
            LIMIT {{limit:UInt32}}
            """,
            parameters=params,
        )

    result = await asyncio.to_thread(_query)
    return [RegionCount(region=r[0], count=r[1]) for r in result.result_rows]


@router.get("/sources", response_model=list[SourceCount], summary="Распределение по источникам")
async def get_by_source(
    domain: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=50),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
):
    """Количество вакансий по источникам (hh.ru, avito и др.)."""
    client = get_client()
    client.database = configs.CLICKHOUSE_DB
    where_clause, params = build_where(domain=domain, date_from=date_from, date_to=date_to)
    params["limit"] = limit

    def _query():
        return client.query(
            f"""
            SELECT source, count() as count
            FROM vacancies_analytics
            WHERE {where_clause}
            GROUP BY source
            ORDER BY count DESC
            LIMIT {{limit:UInt32}}
            """,
            parameters=params,
        )

    result = await asyncio.to_thread(_query)
    return [SourceCount(source=r[0], count=r[1]) for r in result.result_rows]


@router.get("/domain-grade-matrix", response_model=list[DomainGradeCount], summary="Матрица домен-грейд")
async def get_domain_grade_matrix(
    source: Optional[str] = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
):
    """Перекрёстная таблица количества вакансий по доменам и грейдам."""
    client = get_client()
    client.database = configs.CLICKHOUSE_DB
    where_clause, params = build_where(source=source, date_from=date_from, date_to=date_to)

    def _query():
        return client.query(
            f"""
            SELECT domain, grade, count() as count
            FROM vacancies_analytics
            WHERE {where_clause}
            GROUP BY domain, grade
            ORDER BY domain, grade
            """,
            parameters=params,
        )

    result = await asyncio.to_thread(_query)
    return [
        DomainGradeCount(domain=r[0], grade=r[1], count=r[2])
        for r in result.result_rows
    ]

