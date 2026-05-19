"""Рекомендации вакансий: VK-профиль или профиль из PDF-резюме + pgvector + skill gap."""
from __future__ import annotations

import ast
import asyncio
import json
import logging
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from services.vacancy_analytics_service.config import configs
from services.vacancy_analytics_service.db import get_pg_connection_string
from services.vacancy_analytics_service.schemas.recommendations import (
    RecommendationsResponse,
    VacancyRecommendation,
)
from services.vacancy_analytics_service.services.auth import get_user_uuid_from_auth, get_vk_id_from_auth
from services.vacancy_analytics_service.services.embeddings import build_user_profile_text, get_embedding
from services.vacancy_analytics_service.services.skills_gap import (
    jaccard_skills,
    match_and_missing,
    normalize_skill_set,
    vacancy_key_skills_from_json,
)
from services.vacancy_analytics_service.services.vk_interests import get_professions_by_vk_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/analytics", tags=["Рекомендации"])
bearer_scheme = HTTPBearer()

SQL_VACANCY_ROWS = """
    SELECT
        p.uuid AS processed_uuid,
        r.uuid AS raw_uuid,
        r.title,
        r.description,
        p.domain,
        r.employer,
        r.city,
        r.salary_from,
        r.salary_to,
        r.url AS vacancy_url,
        p.skills,
        1 - (p.embedding <=> $1::vector) AS similarity
    FROM processed_vacancies p
    JOIN raw_vacancies r ON r.uuid = p.raw_vacancy_uuid
    WHERE p.embedding IS NOT NULL
    ORDER BY p.embedding <=> $1::vector
    LIMIT $2
"""


def _embedding_to_float_list(emb) -> list[float]:
    """
    Приводит значение столбца embedding к list[float].
    Без register_vector asyncpg часто отдаёт vector как строку '[...]';
    итерация по str даёт символы и ломает float().
    """
    if emb is None:
        raise ValueError("embedding is None")
    if hasattr(emb, "tolist"):
        emb = emb.tolist()
    if isinstance(emb, str):
        s = emb.strip()
        if not s:
            raise ValueError("empty embedding string")
        try:
            parsed = json.loads(s)
        except json.JSONDecodeError:
            try:
                parsed = ast.literal_eval(s)
            except (ValueError, SyntaxError) as e:
                raise ValueError(f"cannot parse embedding: {s[:80]}…") from e
        if not isinstance(parsed, list):
            raise TypeError(f"parsed embedding is not a list: {type(parsed)}")
        emb = parsed
    if isinstance(emb, memoryview):
        emb = list(emb)
    if not isinstance(emb, (list, tuple)):
        raise TypeError(f"unsupported embedding type: {type(emb)}")
    return [float(x) for x in emb]


def _row_to_vacancy(
    r,
    *,
    match_percent: int,
    matched_skills: list[str],
    missing_skills: list[str],
) -> VacancyRecommendation:
    desc = r["description"]
    url = r.get("vacancy_url")
    return VacancyRecommendation(
        processed_uuid=str(r["processed_uuid"]),
        raw_uuid=str(r["raw_uuid"]),
        title=r["title"],
        description=(desc or "")[:500] if desc else None,
        domain=r["domain"],
        employer=r["employer"],
        city=r["city"],
        salary_from=r["salary_from"],
        salary_to=r["salary_to"],
        similarity=round(float(r["similarity"]), 4),
        match_percent=match_percent,
        matched_skills=matched_skills,
        missing_skills=missing_skills,
        vacancy_url=str(url) if url else None,
    )


def _score_row_vk(r) -> tuple[int, list[str], list[str]]:
    sim = float(r["similarity"])
    mp = round(100 * max(0.0, min(1.0, sim)))
    return mp, [], []


def _score_row_resume(r, candidate_skills: list[str]) -> tuple[int, list[str], list[str]]:
    sim = float(r["similarity"])
    vac_skills = vacancy_key_skills_from_json(r["skills"])
    matched, missing = match_and_missing(candidate_skills, vac_skills)
    cset = normalize_skill_set(candidate_skills)
    vset = normalize_skill_set(vac_skills)
    jac = jaccard_skills(cset, vset)
    alpha = configs.RECOMMEND_HYBRID_ALPHA
    beta = configs.RECOMMEND_HYBRID_BETA
    final = alpha * sim + beta * jac
    mp = round(100 * max(0.0, min(1.0, final)))
    return mp, matched, missing


def _rank_rows(
    rows: list,
    *,
    source: Literal["vk", "resume"],
    candidate_skills: list[str],
    limit: int,
) -> list[VacancyRecommendation]:
    scored: list[tuple[float, object]] = []
    for r in rows:
        if source == "vk":
            mp, matched, missing = _score_row_vk(r)
            order_key = float(r["similarity"])
        else:
            mp, matched, missing = _score_row_resume(r, candidate_skills)
            sim = float(r["similarity"])
            vac_skills = vacancy_key_skills_from_json(r["skills"])
            cset = normalize_skill_set(candidate_skills)
            vset = normalize_skill_set(vac_skills)
            jac = jaccard_skills(cset, vset)
            order_key = configs.RECOMMEND_HYBRID_ALPHA * sim + configs.RECOMMEND_HYBRID_BETA * jac
        scored.append((order_key, (r, mp, matched, missing)))
    scored.sort(key=lambda x: x[0], reverse=True)
    out: list[VacancyRecommendation] = []
    for _, pack in scored[:limit]:
        r, mp, matched, missing = pack
        out.append(_row_to_vacancy(r, match_percent=mp, matched_skills=matched, missing_skills=missing))
    return out


@router.get("/recommendations", response_model=RecommendationsResponse, summary="Рекомендации вакансий")
async def get_recommendations(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    limit: int = Query(10, ge=1, le=50),
    source: Literal["vk", "resume"] = Query(
        "vk",
        description="Источник профиля: vk (интересы ВК) или resume (PDF-профиль из БД)",
    ),
):
    """Подбор вакансий по семантической близости; для resume — гибрид с пересечением навыков и skill gap."""
    try:
        import asyncpg
        from pgvector.asyncpg import register_vector
    except ImportError:
        raise HTTPException(status_code=503, detail="Требуется asyncpg и pgvector")

    if not configs.OPENAI_API_KEY:
        raise HTTPException(status_code=503, detail="OPENAI_API_KEY не задан")

    fetch_limit = min(150, max(limit * 3, limit))
    embedding: list[float]
    professions: list[str]
    candidate_skills: list[str] = []

    if source == "vk":
        if not configs.VK_ACCESS_TOKEN:
            raise HTTPException(status_code=503, detail="VK_ACCESS_TOKEN не задан (нужен для source=vk)")
        vk_id = await get_vk_id_from_auth(credentials.credentials)
        professions = await asyncio.to_thread(
            get_professions_by_vk_user,
            configs.VK_ACCESS_TOKEN,
            vk_id,
            api_key=configs.OPENAI_API_KEY,
            base_url=configs.OPENAI_BASE_URL,
            model=configs.OPENAI_INTERESTS_MODEL,
        )
        profile_text = build_user_profile_text(professions)
        if not profile_text.strip():
            professions = ["Маркетолог", "Дизайнер", "Разработчик", "Аналитик", "Менеджер"]
            profile_text = " ".join(professions)
        embedding = await asyncio.to_thread(
            get_embedding,
            profile_text,
            api_key=configs.OPENAI_API_KEY,
            base_url=configs.OPENAI_BASE_URL,
            model=configs.OPENAI_EMBEDDING_MODEL,
        )
        embedding = _embedding_to_float_list(embedding)
        logger.info(
            "recommendations vk: vk_id=%s professions=%s rows_fetch=%d",
            vk_id,
            professions[:5],
            fetch_limit,
        )
    else:
        user_uuid = await get_user_uuid_from_auth(credentials.credentials)
        conn_str = get_pg_connection_string()
        conn = await asyncpg.connect(conn_str)
        try:
            try:
                from pgvector.asyncpg import register_vector

                await register_vector(conn)
            except ImportError:
                pass
            row = await conn.fetchrow(
                """
                SELECT profile_json, embedding
                FROM candidate_profiles
                WHERE user_uuid = $1 AND embedding IS NOT NULL
                """,
                user_uuid,
            )
        finally:
            await conn.close()
        if not row:
            raise HTTPException(
                status_code=400,
                detail="Загрузите PDF-резюме (POST /api/v1/analytics/profile/resume) перед запросом source=resume",
            )
        pj = row["profile_json"]
        if isinstance(pj, str):
            try:
                pj = json.loads(pj)
            except json.JSONDecodeError:
                pj = {}
        if not isinstance(pj, dict):
            pj = {}
        skills = pj.get("skills") or []
        titles = pj.get("desired_titles") or []
        candidate_skills = [str(s) for s in skills if s and str(s).strip()]
        professions = [str(t) for t in titles if t and str(t).strip()]
        if candidate_skills:
            professions = professions + [s for s in candidate_skills[:10] if s not in professions]

        embedding = _embedding_to_float_list(row["embedding"])

    conn_str = get_pg_connection_string()
    conn = await asyncpg.connect(conn_str)
    try:
        await register_vector(conn)
        await conn.execute("SET statement_timeout = '30s'")
        await conn.execute("SET ivfflat.probes = 20")
        rows = await conn.fetch(SQL_VACANCY_ROWS, embedding, fetch_limit)
    except Exception as e:
        logger.exception("recommendations: DB query failed: %s", e)
        raise
    finally:
        await conn.close()

    vacancies = _rank_rows(rows, source=source, candidate_skills=candidate_skills, limit=limit)

    return RecommendationsResponse(
        professions=professions,
        profile_source=source,
        vacancies=vacancies,
    )


@router.get("/recommendations/debug", response_model=RecommendationsResponse, summary="Отладка рекомендаций")
async def get_recommendations_debug(limit: int = Query(10, ge=1, le=50)):
    """Тестовый поиск похожих вакансий без VK/OpenAI — проверяет работу pgvector."""
    try:
        import asyncpg
        from pgvector.asyncpg import register_vector
    except ImportError:
        raise HTTPException(status_code=503, detail="Требуется asyncpg и pgvector")

    conn_str = get_pg_connection_string()
    conn = await asyncpg.connect(conn_str)
    try:
        await register_vector(conn)
        await conn.execute("SET statement_timeout = '30s'")
        await conn.execute("SET ivfflat.probes = 20")
        ref_row = await conn.fetchrow(
            "SELECT embedding FROM processed_vacancies WHERE embedding IS NOT NULL LIMIT 1"
        )
        if not ref_row:
            return RecommendationsResponse(
                professions=["[debug: нет данных]"],
                profile_source="debug",
                vacancies=[],
            )
        ref_embedding = _embedding_to_float_list(ref_row["embedding"])
        rows = await conn.fetch(SQL_VACANCY_ROWS, ref_embedding, limit)
        logger.info("recommendations/debug: rows=%d", len(rows))
    finally:
        await conn.close()

    vacancies = _rank_rows(rows, source="vk", candidate_skills=[], limit=limit)
    return RecommendationsResponse(
        professions=["[debug: один вектор из БД]"],
        profile_source="debug",
        vacancies=vacancies,
    )
