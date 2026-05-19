"""Схемы профиля соискателя (резюме)."""
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class CandidateProfileResponse(BaseModel):
    """Текущий сохранённый профиль (без сырого текста целиком — см. preview)."""

    user_uuid: UUID
    resume_file_name: str | None = None
    storage_path: str | None = None
    profile_json: dict = Field(default_factory=dict)
    extracted_text_preview: str | None = Field(
        None,
        description="Первые ~500 символов извлечённого текста (для проверки загрузки)",
    )
    has_embedding: bool = False
    updated_at: datetime | None = None


class ResumeUploadResponse(BaseModel):
    """Ответ после загрузки и обработки PDF."""

    message: str = "Резюме обработано и профиль сохранён"
    profile_json: dict = Field(default_factory=dict)
    skills_count: int = 0
