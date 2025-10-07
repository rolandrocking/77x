from fastapi import Depends
from typing import Annotated

from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from app.core.config import settings


# Create database engine
async_engine = create_async_engine(
    settings.async_database_url,
    pool_size=15,  # Increase the base pool size
    max_overflow=15,  # Allow extra connections if needed
    pool_timeout=30,  # Time to wait before raising TimeoutError
    pool_recycle=180,
)

async_session_maker = async_sessionmaker(
    async_engine,
    class_=AsyncSession,
    expire_on_commit=False
)


async def get_async_session():
    async with async_session_maker() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise

AsyncDBSession = Annotated[AsyncSession, Depends(get_async_session)]