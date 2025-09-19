"""FastAPI dependencies for database sessions and common functionality."""

from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from ..constants import DATABASE_MAX_OVERFLOW, DATABASE_POOL_SIZE
from ..database.utils import get_asyncpg_database_url


# Database connection holder for lazy initialization
class DatabaseConnections:
    """Holds database connections with lazy initialization."""

    def __init__(self):
        self._engine = None
        self._async_session = None

    @property
    def engine(self):
        """Get or create the async database engine."""
        if self._engine is None:
            self._engine = create_async_engine(
                get_asyncpg_database_url(),
                echo=False,  # Set to True for SQL debugging
                pool_size=DATABASE_POOL_SIZE,
                max_overflow=DATABASE_MAX_OVERFLOW,
                pool_pre_ping=True,
            )
        return self._engine

    @property
    def async_session(self):
        """Get or create the async session maker."""
        if self._async_session is None:
            self._async_session = async_sessionmaker(
                self.engine, class_=AsyncSession, expire_on_commit=False
            )
        return self._async_session


# Global connection instance
_db = DatabaseConnections()

# Export for backwards compatibility
engine = _db.engine
async_session = _db.async_session


async def get_db_session() -> AsyncGenerator[AsyncSession]:
    """Dependency to get database session.

    Yields:
        AsyncSession: Database session for request
    """
    async with _db.async_session() as session:
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
