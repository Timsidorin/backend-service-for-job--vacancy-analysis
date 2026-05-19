"""Профиль соискателя: загрузка PDF-резюме и просмотр сохранённого профиля."""
from __future__ import annotations

import asyncio
import json
import logging
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from services.vacancy_analytics_service.config import configs
from services.vacancy_analytics_service.db import get_pg_connection_string
from services.vacancy_analytics_service.schemas.candidate import (
    CandidateProfileResponse,
    ResumeUploadResponse,
)
from services.vacancy_analytics_service.services.auth import get_user_uuid_from_auth
from services.vacancy_analytics_service.services.embeddings import (
    build_candidate_profile_text,
    get_embedding,
)
from services.vacancy_analytics_service.services.pdf_resume import extract_text_from_pdf_bytes
from services.vacancy_analytics_service.services.resume_llm import structure_resume_profile

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/analytics", tags=["Профиль соискателя"])
bearer_scheme = HTTPBearer()


@router.post(
    "/profile/resume",
    response_model=ResumeUploadResponse,
    summary="Загрузить PDF-резюме",
)
async def upload_resume(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    file: UploadFile = File(..., description="PDF-файл резюме"),
):
    """Извлекает текст, структурирует профиль (LLM), строит эмбеддинг и сохраняет в БД."""
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Ожидается файл с расширением .pdf")
    if file.content_type and file.content_type not in ("application/pdf", "application/x-pdf"):
        # браузеры иногда шлют octet-stream
        if file.content_type != "application/octet-stream":
            pass

    data = await file.read()
    if len(data) > configs.MAX_RESUME_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Файл больше {configs.MAX_RESUME_BYTES // (1024 * 1024)} МБ",
        )
    if not data:
        raise HTTPException(status_code=400, detail="Пустой файл")

    if not configs.OPENAI_API_KEY:
        raise HTTPException(status_code=503, detail="OPENAI_API_KEY не задан")

    user_uuid = await get_user_uuid_from_auth(credentials.credentials)

    try:
        extracted = extract_text_from_pdf_bytes(data)
    except Exception as e:
        logger.exception("PDF extract failed: %s", e)
        raise HTTPException(status_code=400, detail="Не удалось прочитать PDF (возможен скан без OCR)")

    if not extracted.strip():
        raise HTTPException(status_code=400, detail="Из PDF не извлечён текст")

    profile_json = await asyncio.to_thread(
        structure_resume_profile,
        extracted,
        api_key=configs.OPENAI_API_KEY,
        base_url=configs.OPENAI_BASE_URL,
        model=configs.OPENAI_RESUME_MODEL,
    )

    if not isinstance(profile_json, dict):
        profile_json = {}

    profile_text = build_candidate_profile_text(profile_json)
    if not profile_text.strip():
        profile_text = extracted[:8000]

    embedding = await asyncio.to_thread(
        get_embedding,
        profile_text,
        api_key=configs.OPENAI_API_KEY,
        base_url=configs.OPENAI_BASE_URL,
        model=configs.OPENAI_EMBEDDING_MODEL,
    )
    embedding = [float(x) for x in embedding]

    configs.RESUME_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    safe_name = (file.filename or "resume.pdf").replace("..", "").replace("/", "_").replace("\\", "_")[:200]
    storage_path = configs.RESUME_UPLOAD_DIR / f"{user_uuid}_{safe_name}"
    storage_path.write_bytes(data)

    conn_str = get_pg_connection_string()
    try:
        import asyncpg
    except ImportError:
        raise HTTPException(status_code=503, detail="Требуется asyncpg")

    # asyncpg ожидает JSON-строку для jsonb, а не dict (иначе DataError: expected str, got dict)
    profile_json_str = json.dumps(profile_json, ensure_ascii=False)

    conn = await asyncpg.connect(conn_str)
    try:
        try:
            from pgvector.asyncpg import register_vector

            await register_vector(conn)
        except ImportError:
            pass

        await conn.execute(
            """
            INSERT INTO candidate_profiles (
                user_uuid, resume_file_name, mime_type, storage_path,
                extracted_text, profile_json, embedding, updated_at
            )
            VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7::vector, now())
            ON CONFLICT (user_uuid) DO UPDATE SET
                resume_file_name = EXCLUDED.resume_file_name,
                mime_type = EXCLUDED.mime_type,
                storage_path = EXCLUDED.storage_path,
                extracted_text = EXCLUDED.extracted_text,
                profile_json = EXCLUDED.profile_json,
                embedding = EXCLUDED.embedding,
                updated_at = now()
            """,
            user_uuid,
            safe_name,
            file.content_type or "application/pdf",
            str(storage_path),
            extracted,
            profile_json_str,
            embedding,
        )
    finally:
        await conn.close()

    skills = profile_json.get("skills") or []
    skills_count = len(skills) if isinstance(skills, list) else 0
    return ResumeUploadResponse(profile_json=profile_json, skills_count=skills_count)


@router.get("/profile", response_model=CandidateProfileResponse, summary="Текущий профиль соискателя")
async def get_profile(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
):
    """Возвращает сохранённый профиль (после загрузки резюме)."""
    user_uuid = await get_user_uuid_from_auth(credentials.credentials)

    try:
        import asyncpg
    except ImportError:
        raise HTTPException(status_code=503, detail="Требуется asyncpg")

    conn = await asyncpg.connect(get_pg_connection_string())
    try:
        row = await conn.fetchrow(
            """
            SELECT user_uuid, resume_file_name, storage_path, extracted_text, profile_json,
                   embedding IS NOT NULL AS has_embedding, updated_at
            FROM candidate_profiles
            WHERE user_uuid = $1
            """,
            user_uuid,
        )
    finally:
        await conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="Профиль не найден. Загрузите PDF-резюме.")

    ext = row["extracted_text"] or ""
    preview = ext[:500] + ("…" if len(ext) > 500 else "") if ext else None
    pj = row["profile_json"]
    if isinstance(pj, str):
        try:
            pj = json.loads(pj)
        except json.JSONDecodeError:
            pj = {}

    return CandidateProfileResponse(
        user_uuid=row["user_uuid"],
        resume_file_name=row["resume_file_name"],
        storage_path=row["storage_path"],
        profile_json=pj if isinstance(pj, dict) else {},
        extracted_text_preview=preview,
        has_embedding=bool(row["has_embedding"]),
        updated_at=row["updated_at"],
    )
