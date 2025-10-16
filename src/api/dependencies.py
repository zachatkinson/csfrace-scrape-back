"""FastAPI dependencies for database sessions and common functionality."""

from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from ..constants import DATABASE_MAX_OVERFLOW, DATABASE_POOL_SIZE
from ..database.utils import get_database_url

# Database engine and session factory
# Best Practice: Configure connection pool for optimal async performance
engine = create_async_engine(
    get_database_url().replace("postgresql+psycopg://", "postgresql+asyncpg://"),
    echo=False,  # Set to True for SQL debugging
    pool_size=DATABASE_POOL_SIZE,
    max_overflow=DATABASE_MAX_OVERFLOW,
    pool_pre_ping=True,  # Verify connections before use
    pool_recycle=3600,  # Recycle connections after 1 hour
    pool_timeout=30,  # Timeout for getting connection from pool
    echo_pool=False,  # Set to True for pool debugging
)

async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db_session() -> AsyncGenerator[AsyncSession]:
    """Dependency to get database session.

    Best Practice: The async with context manager handles:
    - Session creation
    - Automatic commit on success
    - Automatic rollback on exception
    - Automatic session close

    Yields:
        AsyncSession: Database session for request
    """
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        # Session close is handled automatically by the context manager
        # No need for explicit close() call


# Type annotation for database session dependency
DBSession = Annotated[AsyncSession, Depends(get_db_session)]
