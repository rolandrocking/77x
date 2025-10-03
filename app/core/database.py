"""
Database connection and session management.
"""
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings

# Create async engine using settings
engine = create_async_engine(settings.DATABASE_URL, echo=False)

# Create async session factory
AsyncSessionLocal = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


async def get_db() -> AsyncSession:
    """Dependency to get database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    """Initialize database - migrations are handled by Alembic."""
    # With Alembic, we don't create tables here anymore
    # Tables are created and managed through migrations
    # This function is kept for backward compatibility
    pass