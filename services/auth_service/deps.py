# deps.py
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from repository import UserRepository
from database import get_async_session
from sqlalchemy.ext.asyncio import AsyncSession
from config import configs

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

async def get_user_repository(session: AsyncSession = Depends(get_async_session)):
    return UserRepository(session)

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    repo: UserRepository = Depends(get_user_repository),
):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, configs.SECRET_KEY, algorithms=[configs.ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = await repo.get_user_by_email(email)
    if user is None:
        raise credentials_exception
    return user
