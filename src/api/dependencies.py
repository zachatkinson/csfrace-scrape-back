"""FastAPI dependencies for database sessions and common functionality."""

from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from ..constants import DATABASE_MAX_OVERFLOW, DATABASE_POOL_SIZE
from ..database.utils import get_asyncpg_database_url

# Database engine and session factory
engine = create_async_engine(
    get_asyncpg_database_url(),
    echo=False,  # Set to True for SQL debugging
    pool_size=DATABASE_POOL_SIZE,
    max_overflow=DATABASE_MAX_OVERFLOW,
    pool_pre_ping=True,
)

async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db_session() -> AsyncGenerator[AsyncSession]:
    """Dependency to get database session.

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
        finally:
            await session.close()


# Type annotation for database session dependency
DBSession = Annotated[AsyncSession, Depends(get_db_session)]
