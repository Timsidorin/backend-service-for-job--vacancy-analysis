from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4
from sqlalchemy import String, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from database import Base
import sqlalchemy as sa


class User(Base):
    """
    Таблица пользователя
    """

    __tablename__ = "users"

    uuid: Mapped[UUID] = mapped_column(
        sa.UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    password: Mapped[str] = mapped_column(String(100))
    registration_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
