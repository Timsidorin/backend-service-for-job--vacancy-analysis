from typing import Optional
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from users_model import User
from users_schema import UserRegister
from security import *


class UserRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_user(self, user_data: UserRegister) -> Optional[User]:
        """Создание нового пользователя"""
        try:
            # Хешируем пароль
            hashed_password = get_password_hash(user_data.password)

            # Создаем пользователя
            new_user = User(username=user_data.username, password=hashed_password)

            self.session.add(new_user)
            await self.session.commit()
            await self.session.refresh(new_user)
            return new_user
        except IntegrityError:
            await self.session.rollback()
            return None
        except Exception as e:
            await self.session.rollback()
            raise e

    async def get_user_by_username(self, username: str) -> Optional[User]:
        """Получение пользователя по логину"""
        try:
            query = select(User).where(User.username == username)
            result = await self.session.execute(query)
            return result.scalar_one_or_none()
        except Exception as e:
            await self.session.rollback()
            raise e

    async def get_user_by_uuid(self, user_uuid: UUID) -> Optional[User]:
        """Получение пользователя по UUID"""
        try:
            query = select(User).where(User.uuid == user_uuid)
            result = await self.session.execute(query)
            return result.scalar_one_or_none()
        except Exception as e:
            await self.session.rollback()
            raise e

    async def authenticate_user(self, username: str, password: str) -> Optional[User]:
        """Аутентификация пользователя"""
        try:
            user = await self.get_user_by_username(username)
            if not user or not verify_password(password, user.password):
                return None
            return user
        except Exception as e:
            await self.session.rollback()
            raise e

    async def update_user_password(
        self, user_uuid: UUID, new_password: str
    ) -> Optional[User]:
        """Обновление пароля пользователя"""
        try:
            user = await self.get_user_by_uuid(user_uuid)
            if not user:
                return None

            hashed_password = get_password_hash(new_password)
            user.password = hashed_password

            await self.session.commit()
            await self.session.refresh(user)

            return user
        except Exception as e:
            await self.session.rollback()
            raise e

    async def delete_user(self, user_uuid: UUID) -> bool:
        """Удаление пользователя"""
        try:
            user = await self.get_user_by_uuid(user_uuid)
            if not user:
                return False

            await self.session.delete(user)
            await self.session.commit()

            return True
        except Exception as e:
            await self.session.rollback()
            raise e

    async def user_exists(self, username: str) -> bool:
        """Проверка существования пользователя по логину"""
        try:
            user = await self.get_user_by_username(username)
            return user is not None
        except Exception as e:
            await self.session.rollback()
            raise e
