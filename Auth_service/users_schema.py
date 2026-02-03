# users_schema.py
from enum import Enum
from uuid import uuid4, UUID
from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict


class UserRegister(BaseModel):
    username: str = Field(
        ..., min_length=3, max_length=50, description="Логин пользователя"
    )
    password: str = Field(
        ..., min_length=5, max_length=100, description="Пароль, от 5 до 100 символов"
    )


class UserLogin(BaseModel):
    username: str
    password: str


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    uuid: UUID
    username: str
    registration_at: datetime


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    username: Optional[str] = None
