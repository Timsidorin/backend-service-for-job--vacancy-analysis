from uuid import UUID
from typing import Optional
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, ConfigDict, EmailStr

class UserRole(str, Enum):
    USER = "user"
    ADMIN = "admin"
    ANALYST = "analyst"

class UserRegister(BaseModel):
    email: EmailStr = Field(..., description="Email пользователя")
    password: str = Field(
        ...,
        min_length=6,
        max_length=100,
        description="Пароль (минимум 6 символов)"
    )
    full_name: Optional[str] = Field(None, max_length=100, description="Полное имя")

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    """
    Схема для ответа API (без пароля!)
    """
    model_config = ConfigDict(from_attributes=True)

    uuid: UUID
    email: EmailStr
    full_name: Optional[str] = None
    role: UserRole
    is_active: bool
    created_at: datetime

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

class TokenData(BaseModel):
    """
    Данные, которые мы достаем из JWT токена
    """
    uuid: Optional[UUID] = None
    email: Optional[str] = None
    role: Optional[UserRole] = None
