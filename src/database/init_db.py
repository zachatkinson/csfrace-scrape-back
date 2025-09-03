"""Database initialization utilities with PostgreSQL enum safety."""

import logging

from sqlalchemy import create_engine, text
from sqlalchemy.dialects.postgresql import ENUM as PostgreSQLEnum

from .models import Base, JobPriority, JobStatus, get_database_url

logger = logging.getLogger(__name__)


async def init_db(engine=None) -> None:
    """Initialize the database with PostgreSQL enum safety for concurrent environments.

    Following PostgreSQL and SQLAlchemy best practices:
    1. Create enum types first with concurrent safety
    2. Create tables using checkfirst=True
    3. Handle duplicate enum creation gracefully

    Args:
        engine: Optional SQLAlchemy Engine. If None, creates engine from get_database_url().
                This enables dependency injection for testing (SQLAlchemy best practice).

    Reference: https://docs.sqlalchemy.org/en/20/dialects/postgresql.html#postgresql-enums
    """
    try:
        # Use provided engine or create one (dependency injection pattern)
        if engine is None:
            engine = create_engine(get_database_url(), echo=False)

        # Create enum types first with PostgreSQL best practices
        await _create_enums_safely(engine)

        # Create all tables using SQLAlchemy best practices
        Base.metadata.create_all(engine, checkfirst=True)

        logger.info("Database initialization completed successfully")

    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        raise


async def _create_enums_safely(engine) -> None:
    """Create PostgreSQL enum types safely for concurrent test execution.

    Uses PostgreSQL's transaction-safe enum creation pattern recommended
    in the official documentation.
    """
    enum_definitions = [
        ("jobstatus", JobStatus),
        ("jobpriority", JobPriority),
    ]

    with engine.connect() as conn:
        for enum_name, enum_class in enum_definitions:
            try:
                # Check if enum type already exists (PostgreSQL best practice)
                result = conn.execute(
                    text("SELECT EXISTS(SELECT 1 FROM pg_type WHERE typname = :enum_name)"),
                    {"enum_name": enum_name},
                ).scalar()

                if not result:
                    # Create enum type using SQLAlchemy PostgreSQL dialect
                    pg_enum = PostgreSQLEnum(enum_class, name=enum_name, create_type=True)
                    pg_enum.create(conn, checkfirst=True)
                    logger.debug(f"Created PostgreSQL enum type: {enum_name}")
                else:
                    logger.debug(f"PostgreSQL enum type already exists: {enum_name}")

            except Exception as e:
                error_msg = str(e).lower()
                # Handle concurrent enum creation conflicts gracefully
                if any(phrase in error_msg for phrase in ["already exists", "duplicate key"]):
                    logger.debug(f"Enum {enum_name} already exists (concurrent execution): {e}")
                else:
                    logger.warning(f"Unexpected error creating enum {enum_name}: {e}")
                    # Don't raise - let table creation proceed

        # Commit the transaction
        conn.commit()
