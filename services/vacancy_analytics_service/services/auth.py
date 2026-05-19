"""Утилита для получения данных пользователя из auth service по JWT."""
from uuid import UUID

import httpx
from fastapi import HTTPException, status

from services.vacancy_analytics_service.config import configs


async def _get_me_json(token: str) -> dict:
    url = f"{configs.AUTH_SERVICE_URL}/api/v1/auth/me"
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.get(url, headers={"Authorization": f"Bearer {token}"})
    if r.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Не удалось получить данные пользователя из auth service",
        )
    return r.json()


async def get_user_uuid_from_auth(token: str) -> UUID:
    """Возвращает uuid пользователя по JWT."""
    data = await _get_me_json(token)
    uid = data.get("uuid")
    if not uid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="В ответе auth/me нет uuid",
        )
    return UUID(uid) if isinstance(uid, str) else uid


async def get_vk_id_from_auth(token: str) -> int:
    """Запрашивает /api/v1/auth/me и возвращает vk_id текущего пользователя."""
    data = await _get_me_json(token)
    vk_id = data.get("vk_id")
    if not vk_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="У пользователя не указан vk_id (задайте при регистрации)",
        )
    return int(vk_id)
