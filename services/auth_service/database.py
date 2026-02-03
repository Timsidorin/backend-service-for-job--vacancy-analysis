from sqlalchemy.ext.asyncio import (
    create_async_engine,
    async_sessionmaker,
    AsyncAttrs,
    AsyncSession,
)
from sqlalchemy.orm import DeclarativeBase, declared_attr
from config import get_db_url

DATABASE_URL = get_db_url()

engine = create_async_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    future=True
)

async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)


class Base(AsyncAttrs, DeclarativeBase):
    __abstract__ = True
    @declared_attr.directive
    def __tablename__(cls) -> str:
        return f"{cls.__name__.lower()}s"


async def get_async_session() -> AsyncSession:
    async with async_session_maker() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
