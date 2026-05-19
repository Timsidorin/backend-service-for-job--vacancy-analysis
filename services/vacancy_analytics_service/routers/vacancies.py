"""Поиск вакансий с фильтрами (неточный поиск ILIKE)."""
import logging
from datetime import date
from typing import Optional

import asyncpg
from fastapi import APIRouter, HTTPException, Query

from services.vacancy_analytics_service.db import get_pg_connection_string
from services.vacancy_analytics_service.schemas.vacancies import (
    VacancySearchItem,
    VacancySearchResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/analytics", tags=["Вакансии"])


def _row_to_item(r) -> VacancySearchItem:
    desc = r["description"]
    return VacancySearchItem(
        raw_uuid=str(r["raw_uuid"]),
        processed_uuid=str(r["processed_uuid"]),
        title=r["title"],
        description=(desc or "")[:500] if desc else None,
        source=r["source"],
        domain=r["domain"],
        employer=r["employer"],
        city=r["city"],
        region=r["region"],
        salary_from=r["salary_from"],
        salary_to=r["salary_to"],
        published_at=r["published_at"],
        grade=r["grade"],
        url=r["url"],
    )


@router.get("/vacancies/search", response_model=VacancySearchResponse, summary="Поиск вакансий с фильтрами")
async def search_vacancies(
    q: Optional[str] = Query(None, description="Поиск по названию, описанию, работодателю"),
    city: Optional[str] = Query(None, description="Фильтр по городу"),
    region: Optional[str] = Query(None, description="Фильтр по региону"),
    source: Optional[str] = Query(None, description="Фильтр по источнику"),
    domain: Optional[str] = Query(None, description="Фильтр по домену"),
    employer: Optional[str] = Query(None, description="Фильтр по работодателю"),
    grade: Optional[str] = Query(None, description="Фильтр по грейду"),
    date_from: Optional[date] = Query(None, description="Дата публикации от"),
    date_to: Optional[date] = Query(None, description="Дата публикации до"),
    salary_from_min: Optional[int] = Query(None, description="Минимальная нижняя зарплата"),
    salary_to_max: Optional[int] = Query(None, description="Максимальная верхняя зарплата"),
    limit: int = Query(20, ge=1, le=100, description="Количество результатов"),
    offset: int = Query(0, ge=0, description="Смещение для пагинации"),
):
    """Полнотекстовый поиск вакансий с нечётким совпадением (ILIKE)."""
    # Собираем условия и параметры
    conditions = ["1=1"]
    params: list = []

    if q and q.strip():
        params.append(f"%{q.strip()}%")
        i = len(params)
        conditions.append(
            f"(r.title ILIKE ${i} OR r.description ILIKE ${i} "
            f"OR r.full_text ILIKE ${i} OR r.employer ILIKE ${i})"
        )

    for field, value in [
        ("r.city", city),
        ("r.region", region),
        ("r.source", source),
        ("p.domain", domain),
        ("r.employer", employer),
        ("p.grade_prediction", grade),
    ]:
        if value and value.strip():
            params.append(f"%{value.strip()}%")
            conditions.append(f"{field} ILIKE ${len(params)}")

    if date_from:
        params.append(str(date_from))
        conditions.append(f"r.published_at::date >= ${len(params)}")
    if date_to:
        params.append(str(date_to))
        conditions.append(f"r.published_at::date <= ${len(params)}")

    if salary_from_min is not None:
        params.append(salary_from_min)
        i = len(params)
        conditions.append(
            f"(r.salary_from >= ${i} OR r.salary_to >= ${i} "
            f"OR (r.salary_from IS NULL AND r.salary_to >= ${i}))"
        )
    if salary_to_max is not None:
        params.append(salary_to_max)
        i = len(params)
        conditions.append(
            f"(r.salary_to <= ${i} OR r.salary_from <= ${i} "
            f"OR (r.salary_to IS NULL AND r.salary_from <= ${i}))"
        )

    where = " AND ".join(conditions)
    base = f"""
        FROM raw_vacancies r
        INNER JOIN processed_vacancies p ON p.raw_vacancy_uuid = r.uuid
        WHERE {where}
    """

    try:
        conn = await asyncpg.connect(get_pg_connection_string())
    except Exception as e:
        logger.exception("vacancies/search connect: %s", e)
        raise HTTPException(status_code=500, detail=str(e))

    try:
        await conn.execute("SET statement_timeout = '30s'")

        total = await conn.fetchval(f"SELECT COUNT(*)::int {base}", *params)
        params.extend([limit, offset])
        n_limit, n_offset = len(params) - 1, len(params)

        rows = await conn.fetch(
            f"""
            SELECT r.uuid raw_uuid, p.uuid processed_uuid, r.title, r.description,
                   r.source, p.domain, r.employer, r.city, r.region,
                   r.salary_from, r.salary_to, r.published_at::text,
                   p.grade_prediction grade, r.url
            {base}
            ORDER BY r.published_at DESC NULLS LAST, r.parsed_at DESC
            LIMIT ${n_limit} OFFSET ${n_offset}
            """,
            *params,
        )
    except Exception as e:
        logger.exception("vacancies/search: %s", e)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await conn.close()

    return VacancySearchResponse(
        total=total or 0,
        items=[_row_to_item(r) for r in rows],
        limit=limit,
        offset=offset,
    )
