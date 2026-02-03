from typing import Optional
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from users_model import User
from users_schema import UserRegister
from security import get_password_hash, verify_password


class UserRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_user(self, user_data: UserRegister) -> Optional[User]:
        """Создание нового пользователя"""
        try:
            hashed = get_password_hash(user_data.password)
            new_user = User(
                email=user_data.email,
                hashed_password=hashed,
                full_name=user_data.full_name
            )

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

    async def get_user_by_email(self, email: str) -> Optional[User]:
        """Получение пользователя по Email (вместо username)"""
        query = select(User).where(User.email == email)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_user_by_uuid(self, user_uuid: UUID) -> Optional[User]:
        """Получение пользователя по UUID"""
        query = select(User).where(User.uuid == user_uuid)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def authenticate_user(self, email: str, password: str) -> Optional[User]:
        """Аутентификация пользователя"""
        # 1. Ищем по email
        user = await self.get_user_by_email(email)
        if not user or not verify_password(password, user.hashed_password):
            return None

        return user

    async def update_user_password(
            self, user_uuid: UUID, new_password: str
    ) -> Optional[User]:
        """Обновление пароля пользователя"""
        try:
            user = await self.get_user_by_uuid(user_uuid)
            if not user:
                return None
            user.hashed_password = get_password_hash(new_password)

            await self.session.commit()
            await self.session.refresh(user)
            return user
        except Exception as e:
            await self.session.rollback()
            raise e

    async def delete_user(self, user_uuid: UUID) -> bool:
        """Удаление пользователя (Soft Delete предпочтительнее)"""
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

    async def deactivate_user(self, user_uuid: UUID) -> bool:
        try:
            user = await self.get_user_by_uuid(user_uuid)
            if not user:
                return False

            user.is_active = False
            await self.session.commit()
            return True
        except Exception as e:
            await self.session.rollback()
            raise e

    async def user_exists(self, email: str) -> bool:
        """Проверка существования по email"""
        user = await self.get_user_by_email(email)
        return user is not None
