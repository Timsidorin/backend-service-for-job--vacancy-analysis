"""Профессиональные интересы по подпискам VK (LLM)."""
import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from services.vacancy_analytics_service.config import configs
from services.vacancy_analytics_service.schemas.interests import InterestsResponse
from services.vacancy_analytics_service.services.auth import get_vk_id_from_auth
from services.vacancy_analytics_service.services.vk_interests import get_professions_by_vk_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/analytics", tags=["Интересы"])
bearer_scheme = HTTPBearer()


@router.get("/interests", response_model=InterestsResponse, summary="Определение профессиональных интересов")
async def get_interests(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
):
    """Анализирует подписки VK пользователя и через LLM определяет профессиональные интересы."""
    if not configs.VK_ACCESS_TOKEN:
        raise HTTPException(status_code=503, detail="VK_ACCESS_TOKEN не задан")
    if not configs.OPENAI_API_KEY:
        raise HTTPException(status_code=503, detail="OPENAI_API_KEY не задан")

    vk_id = await get_vk_id_from_auth(credentials.credentials)

    try:
        professions = await asyncio.to_thread(
            get_professions_by_vk_user,
            configs.VK_ACCESS_TOKEN,
            vk_id,
            api_key=configs.OPENAI_API_KEY,
            base_url=configs.OPENAI_BASE_URL,
            model=configs.OPENAI_INTERESTS_MODEL,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Ошибка определения интересов: %s", e)
        raise HTTPException(status_code=500, detail="Ошибка при определении интересов")

    return InterestsResponse(vk_id=vk_id, professions=professions)
