"""Testcontainers configuration for database tests following 2025 best practices.

This module provides shared fixtures for PostgreSQL test containers,
eliminating the need to skip tests when databases aren't available locally.
"""

import os
from collections.abc import Generator

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from testcontainers.postgres import PostgresContainer

from src.database.models import Base


@pytest.fixture(scope="session")
def postgres_container() -> Generator[PostgresContainer, None, None]:
    """Create a PostgreSQL test container for the entire test session.

    Following testcontainers best practices:
    - Use real PostgreSQL database instead of mocks for higher confidence
    - Session scope for performance - container reused across tests
    - Automatic cleanup when tests complete
    """
    # Skip containers if running in CI with existing PostgreSQL service
    if os.environ.get("DATABASE_URL") or os.environ.get("TEST_DATABASE_URL"):
        yield None
        return

    with PostgresContainer("postgres:13") as postgres:
        # Configure container for optimal test performance
        postgres.with_env("POSTGRES_INITDB_ARGS", "--auth-host=trust")
        yield postgres


@pytest.fixture(scope="session")
def postgres_engine(postgres_container):
    """Create SQLAlchemy engine connected to test container.

    Returns engine connected to either:
    - Test container (local development)
    - CI PostgreSQL service (GitHub Actions)
    """
    # Use CI database if available (service containers)
    if postgres_container is None:
        db_url = (
            os.environ.get("TEST_DATABASE_URL")
            or os.environ.get("DATABASE_URL")
            or "postgresql+psycopg://postgres:postgres@localhost:5432/test_db"
        )
    else:
        # Use testcontainer database
        db_url = postgres_container.get_connection_url().replace(
            "postgresql://", "postgresql+psycopg://"
        )

    engine = create_engine(db_url, echo=False)

    # Create all tables
    Base.metadata.create_all(engine)

    yield engine

    # Cleanup
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def postgres_session(postgres_engine):
    """Create database session with automatic cleanup between tests.

    Following testcontainers best practices:
    - Fresh session for each test (isolation)
    - Automatic rollback to prevent test pollution
    - Exception handling for reliable cleanup
    """
    SessionLocal = sessionmaker(bind=postgres_engine)
    session = SessionLocal()

    try:
        yield session
    finally:
        # Clean up data between tests
        session.rollback()

        # Truncate all tables to ensure complete isolation
        with postgres_engine.connect() as conn:
            # Get all table names
            result = conn.execute(
                text("""
                SELECT tablename FROM pg_tables
                WHERE schemaname = 'public'
                AND tablename != 'alembic_version'
            """)
            )
            tables = [row[0] for row in result]

            if tables:
                # Disable foreign key checks temporarily
                conn.execute(text("SET session_replication_role = 'replica'"))

                # Truncate all tables
                for table in tables:
                    conn.execute(text(f"TRUNCATE TABLE {table} CASCADE"))

                # Re-enable foreign key checks
                conn.execute(text("SET session_replication_role = 'origin'"))

                conn.commit()

        session.close()


@pytest.fixture
def testcontainers_db_service(postgres_engine):
    """Create DatabaseService instance using test container.

    This replaces the previous 'real_service' fixture that skipped tests.
    Now all database tests run with high confidence using real PostgreSQL.
    """
    from src.database.service import DatabaseService

    # Create service with test container engine
    service = DatabaseService._create_with_engine(postgres_engine)
    yield service

    # Cleanup handled by postgres_session fixture
