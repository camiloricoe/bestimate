"""Database session management."""

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session, sessionmaker

from src.config import settings
from src.db.models import Base

# Async engine (for API and async workers)
async_engine = create_async_engine(settings.database_url, echo=False)
AsyncSessionLocal = async_sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)

# Sync engine (for Celery workers and scripts)
sync_engine = create_engine(settings.database_url_sync, echo=False)
SyncSessionLocal = sessionmaker(sync_engine, class_=Session, expire_on_commit=False)


async def init_db() -> None:
    """Create all tables."""
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


def init_db_sync() -> None:
    """Create all tables (sync version for scripts)."""
    Base.metadata.create_all(sync_engine)
