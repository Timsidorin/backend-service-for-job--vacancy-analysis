import sys
import os

current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from users_schema import UserRegister, UserResponse, UserLogin, Token
from repository import UserRepository
from database import get_async_session
from security import create_access_token, decode_access_token
from config import configs
from typing import Optional
from uuid import UUID

app = FastAPI(title=configs.PROJECT_NAME)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/auth/login")


def get_user_repository(
    session: AsyncSession = Depends(get_async_session),
) -> UserRepository:
    return UserRepository(session)


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    user_repository: UserRepository = Depends(get_user_repository),
):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = decode_access_token(token)
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except:
        raise credentials_exception

    user = await user_repository.get_user_by_username(username=username)
    if user is None:
        raise credentials_exception

    return user


@app.post(
    "/api/auth/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register_user(
    user_data: UserRegister,
    user_repository: UserRepository = Depends(get_user_repository),
):
    """Регистрация нового пользователя"""
    existing_user = await user_repository.get_user_by_username(user_data.username)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Пользователь с таким логином уже существует",
        )

    new_user = await user_repository.create_user(user_data)
    if not new_user:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка при создании пользователя",
        )

    return UserResponse.model_validate(new_user)


@app.post("/api/auth/login", response_model=Token)
async def login_user(
    form_data: OAuth2PasswordRequestForm = Depends(),
    user_repository: UserRepository = Depends(get_user_repository),
):
    """Авторизация пользователя"""
    user = await user_repository.authenticate_user(
        form_data.username, form_data.password
    )
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный логин или пароль",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(data={"sub": user.username})
    return {"access_token": access_token, "token_type": "bearer"}


@app.get("/api/auth/me", response_model=UserResponse)
async def get_current_user_info(current_user=Depends(get_current_user)):
    """Получение информации о текущем пользователе"""
    return UserResponse.model_validate(current_user)


@app.get("/api/users/{user_uuid}", response_model=UserResponse)
async def get_user_by_uuid(
    user_uuid: UUID,
    user_repository: UserRepository = Depends(get_user_repository),
    current_user=Depends(get_current_user),
):
    """Получение пользователя по UUID"""
    user = await user_repository.get_user_by_uuid(user_uuid)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Пользователь не найден"
        )

    return UserResponse.model_validate(user)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host=configs.HOST, port=configs.PORT, reload=True)
