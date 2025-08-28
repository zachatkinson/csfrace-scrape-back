"""FastAPI dependencies for database sessions and common functionality."""

from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from ..database.models import get_database_url

# Database engine and session factory
engine = create_async_engine(
    get_database_url().replace("postgresql+psycopg2://", "postgresql+asyncpg://"),
    echo=False,  # Set to True for SQL debugging
    pool_size=20,
    max_overflow=30,
    pool_pre_ping=True,
)

async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
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
