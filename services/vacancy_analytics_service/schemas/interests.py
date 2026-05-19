"""Схемы ответов эндпоинта интересов (VK + LLM)."""
from pydantic import BaseModel


class InterestsResponse(BaseModel):
    vk_id: int
    professions: list[str]
