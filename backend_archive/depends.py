# core/dependencies.py
import boto3
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from jose import JWTError, jwt
from core.database import get_async_session
from models.users import User
from repositories.users_repository import UserRepository
from services.user_service import UserService
from core.config import configs, Configs

"""
Файл внедрения зависимостей
"""

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")


# === Репозитории ===

async def get_user_repository(
        session: AsyncSession = Depends(get_async_session),
) -> UserRepository:
    """Получение репозитория пользователей"""
    return UserRepository(session)


# === Сервисы ===

async def get_user_service(
        session: AsyncSession = Depends(get_async_session),
) -> UserService:
    """Получение сервиса пользователей"""
    repo = UserRepository(session)
    return UserService(repo)


# === Аутентификация ===

async def get_current_user(
        token: str = Depends(oauth2_scheme),
        user_repo: UserRepository = Depends(get_user_repository)
) -> User:
    """
    Получение текущего аутентифицированного пользователя

    Декодирует JWT токен и возвращает объект пользователя из БД
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Не удалось проверить учетные данные",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(
            token,
            configs.SECRET_KEY,
            algorithms=[configs.ALGORITHM]
        )
        user_identifier: str = payload.get("sub")
        if user_identifier is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    user = None
    if user_identifier.isdigit():
        user = await user_repo.get_by_id(int(user_identifier))
    if user is None:
        user = await user_repo.find_one_or_none(user_identifier)

    if user is None:
        raise credentials_exception

    return user

