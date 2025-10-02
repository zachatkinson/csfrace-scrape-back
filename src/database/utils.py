"""Database utilities for shared operations."""

import os
from enum import Enum

import sqlalchemy.exc
from sqlalchemy import Connection, text
from sqlalchemy.dialects.postgresql import ENUM as PostgreSQLEnum

from src.core.logging_hierarchy import get_database_logger

from ..common.status import JobPriority, JobStatus

# Import for type checking only to avoid circular dependencies

logger = get_database_logger()


def create_postgresql_enums(
    connection: Connection,
    enum_definitions: list[tuple[str, type[Enum]]],
) -> None:
    """Create PostgreSQL enum types if they don't exist.

    This utility consolidates duplicate enum creation logic across the codebase
    following PostgreSQL best practices for concurrent execution.

    Args:
        connection: SQLAlchemy database connection
        enum_definitions: List of (enum_name, enum_class) tuples

    Raises:
        Exception: If enum creation fails for non-concurrent reasons
    """
    for enum_name, enum_class in enum_definitions:
        try:
            # Check if enum type already exists (PostgreSQL best practice)
            result = connection.execute(
                text("SELECT EXISTS(SELECT 1 FROM pg_type WHERE typname = :enum_name)"),
                {"enum_name": enum_name},
            ).scalar()

            if not result:
                # Create enum type using SQLAlchemy PostgreSQL dialect
                pg_enum = PostgreSQLEnum(enum_class, name=enum_name, create_type=True)
                pg_enum.create(connection, checkfirst=True)
                logger.debug("Created PostgreSQL enum type", enum_name=enum_name)
            else:
                logger.debug("PostgreSQL enum type already exists", enum_name=enum_name)

        except (sqlalchemy.exc.ProgrammingError, sqlalchemy.exc.IntegrityError) as e:
            # Handle concurrent enum creation gracefully (for parallel tests)
            error_msg = str(e).lower()
            if any(
                phrase in error_msg
                for phrase in [
                    "already exists",
                    "duplicate key",
                    "already exists and is not a constraint",
                    "constraint already exists",
                    "pg_type_typname_nsp_index",  # PostgreSQL type uniqueness constraint
                    "violates unique constraint",
                ]
            ):
                logger.debug("Enum type already exists (concurrent creation)", enum_name=enum_name)
                continue
            logger.error("Failed to create enum type", enum_name=enum_name, error=str(e))
            raise


def get_standard_enum_definitions() -> list[tuple[str, type[Enum]]]:
    """Get the standard enum definitions used across the application.

    Returns:
        List of (enum_name, enum_class) tuples for standard enums
    """
    enums: list[tuple[str, type[Enum]]] = [("jobstatus", JobStatus)]

    # Only add JobPriority if it was imported successfully
    if JobPriority is not None:
        enums.append(("jobpriority", JobPriority))

    return enums


def get_database_url() -> str:
    """Generate PostgreSQL database URL from environment variables.

    Returns:
        PostgreSQL database URL string for PostgreSQL 17.6+
    """
    # First check if DATABASE_URL is provided directly (Docker Compose sets this)
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        # Replace psycopg with asyncpg for async support if needed
        if "postgresql://" in database_url:
            return database_url.replace("postgresql://", "postgresql+psycopg://")
        return database_url

    # Fallback: build from individual environment variables
    host = os.getenv("DATABASE_HOST", "localhost")
    port = os.getenv("DATABASE_PORT", "5432")

    # Read from environment variables with proper defaults
    database = os.getenv("DATABASE_NAME", "scraper_db")
    username = os.getenv("DATABASE_USER", "postgres")  # Default to postgres superuser
    password = os.getenv("DATABASE_PASSWORD", "postgres")  # Default to postgres password

    return f"postgresql+psycopg://{username}:{password}@{host}:{port}/{database}"


def test_database_connection() -> bool:
    """Test database connection for startup scripts.

    Returns:
        True if database connection is successful

    Raises:
        Exception: If database connection fails
    """
    from sqlalchemy import create_engine

    try:
        database_url = get_database_url()
        logger.info("Testing database connection", database_url=database_url.split("@")[0] + "@***")

        engine = create_engine(database_url)
        with engine.connect() as connection:
            # Simple test query
            connection.execute(text("SELECT 1"))

        logger.info("Database connection successful")
        return True

    except Exception as e:
        logger.error("Database connection failed", error=str(e))
        raise
