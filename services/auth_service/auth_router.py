from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from typing import Annotated

from services.auth_service.schemas.users_schema import UserRegister, UserResponse, Token
from services.auth_service.repository import UserRepository
from services.auth_service.utils.security import create_access_token
from services.auth_service.deps import get_current_user, get_user_repository

router = APIRouter()


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Регистрация нового пользователя",
)
async def register_user(
    user_data: UserRegister,
    user_repo: UserRepository = Depends(get_user_repository),
):
    """Создаёт учётную запись. Возвращает данные пользователя без пароля."""
    if await user_repo.user_exists(user_data.email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Пользователь с таким email уже существует",
        )

    new_user = await user_repo.create_user(user_data)
    if not new_user:
        raise HTTPException(status_code=500, detail="Ошибка создания пользователя")
    return new_user


@router.post("/login", response_model=Token, summary="Авторизация пользователя")
async def login_user(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    user_repo: UserRepository = Depends(get_user_repository),
):
    """Проверяет email/пароль и возвращает JWT-токен доступа."""
    user = await user_repo.authenticate_user(
        email=form_data.username,
        password=form_data.password
    )
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный email или пароль",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = create_access_token(
        data={"sub": user.email, "role": user.role.value}
    )
    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/me", response_model=UserResponse, summary="Текущий пользователь")
async def get_current_user_info(current_user=Depends(get_current_user)):
    """Возвращает профиль авторизованного пользователя по JWT-токену."""
    return current_user
