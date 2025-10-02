"""Test configuration and fixtures following pytest best practices.

This conftest.py follows official pytest recommendations:
- https://docs.pytest.org/en/stable/how-to/fixtures.html
- https://docs.pytest.org/en/stable/explanation/fixtures.html
- https://docs.pytest.org/en/stable/explanation/goodpractices.html

Provides shared fixtures for the entire test suite with proper scoping,
cleanup, and modular organization following audit_3.md standards.
"""

import os
import sys
import tempfile
from collections.abc import Generator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import asyncio
import pytest
import pytest_asyncio
from faker import Faker
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

# Add project root to Python path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Import all models at module level to ensure they're registered with SQLAlchemy metadata
# BEFORE any test_database_engine fixtures run (critical for pytest-xdist)
from src.database.models.auth import User  # noqa: F401, E402
from src.database.models.jobs import ContentResult, JobLog, ScrapingJob  # noqa: F401, E402

# Initialize faker with deterministic seed for reproducible tests
fake = Faker()
fake.seed_instance(12345)


# ============================================================================
# pytest Hooks and Configuration (Official Best Practice)
# ============================================================================


def pytest_configure(config):
    """Configure pytest with custom markers.

    Official pytest hook for registering custom markers.
    Ref: https://docs.pytest.org/en/stable/reference/reference.html#pytest.hookspec.pytest_configure
    """
    # Register custom markers as recommended by pytest
    config.addinivalue_line("markers", "unit: Unit tests")
    config.addinivalue_line("markers", "integration: Integration tests")
    config.addinivalue_line("markers", "e2e: End-to-end tests")
    config.addinivalue_line("markers", "performance: Performance tests")
    config.addinivalue_line("markers", "security: Security tests")
    config.addinivalue_line("markers", "database: Database-dependent tests")
    config.addinivalue_line("markers", "slow: Slow tests (>5 seconds)")


# ============================================================================
# Session-Scoped Fixtures (Run Once Per Test Session)
# ============================================================================


@pytest.fixture(scope="session")
def event_loop():
    """Provide event loop for async tests.

    Session-scoped for efficiency across all async tests.
    Ref: https://docs.pytest.org/en/stable/how-to/fixtures.html#scope-sharing-fixtures-across-classes-modules-packages-or-session
    """
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def faker_instance():
    """Provide faker instance with deterministic seed.

    Session-scoped to ensure consistent fake data across tests.
    """
    return fake


# ============================================================================
# Module-Scoped Fixtures (Run Once Per Test Module)
# ============================================================================


@pytest.fixture(scope="module")
def test_database_engine():
    """Provide PostgreSQL test database engine.

    Uses PostgreSQL for database parity with production (MANDATORY per TEST_BUILDING.md).
    Module-scoped for efficiency when multiple tests need database.

    Following TEST_BUILDING.md ZERO TOLERANCE: Tests MUST use same database as production.
    """
    # Models already imported at module level, just need Base for metadata
    from src.database.models.base import Base

    # Use PostgreSQL test database for database parity (MANDATORY)
    # TEST_BUILDING.md: Tests must use same database as production
    # Note: Using postgresql+psycopg for psycopg3 driver (modern async support)

    # CI can provide TEST_DATABASE_URL (unit shards) or DATABASE_URL (integration tests) or individual components
    test_db_url = os.environ.get("TEST_DATABASE_URL") or os.environ.get("DATABASE_URL")

    if not test_db_url:
        # Build URL from individual components (integration tests) or use defaults (local dev)
        db_host = os.environ.get("DATABASE_HOST", "localhost")
        db_port = os.environ.get("DATABASE_PORT", "5432")
        db_name = os.environ.get("DATABASE_NAME", "test_db")
        db_user = os.environ.get("DATABASE_USER", "postgres")
        db_password = os.environ.get("DATABASE_PASSWORD", "postgres")
        test_db_url = f"postgresql+psycopg://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"

    engine = create_engine(
        test_db_url,
        poolclass=StaticPool,  # Shared connection for all tests in module
        echo=False,  # Set to True for SQL debugging
    )

    # Create all tables (includes PostgreSQL enum creation via event listener)
    Base.metadata.create_all(engine)

    yield engine

    # Cleanup: Just dispose engine, don't drop tables (causes deadlocks with pytest-xdist)
    # Tables are dropped by test database recreation in CI
    engine.dispose()


# ============================================================================
# Function-Scoped Fixtures (Default Scope - Run Once Per Test Function)
# ============================================================================


@pytest.fixture
def temp_dir() -> Generator[Path]:
    """Provide temporary directory for tests.

    Function-scoped for test isolation. Uses yield for proper cleanup.
    Ref: https://docs.pytest.org/en/stable/how-to/fixtures.html#teardown-cleanup
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        yield Path(tmp_dir)


@pytest.fixture
def mock_session():
    """Provide mock database session for unit tests.

    Function-scoped to ensure clean mocks for each test.
    Uses spec parameter for better mock validation.
    """
    session = Mock(spec=Session)
    session.add = Mock()
    session.commit = Mock()
    session.rollback = Mock()
    session.refresh = Mock()
    session.query = Mock()
    session.execute = Mock()
    session.close = Mock()
    return session


@pytest.fixture
def test_session(test_database_engine):
    """Provide real database session for integration tests with nested transaction isolation.

    Uses SAVEPOINT (nested transactions) for proper isolation in parallel test execution.
    Each test runs in its own nested transaction that gets rolled back, preventing
    interference between pytest-xdist workers sharing the same database.

    This follows pytest best practices for database testing:
    https://docs.pytest.org/en/stable/how-to/fixtures.html#teardown-cleanup
    """
    # Models already imported at module level
    from sqlalchemy import event

    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_database_engine)
    connection = test_database_engine.connect()
    transaction = connection.begin()  # Start outer transaction
    session = TestingSessionLocal(bind=connection)

    # Begin nested transaction (SAVEPOINT) for test isolation
    nested = connection.begin_nested()

    # When session.commit() is called, only commit the SAVEPOINT, not the outer transaction
    @event.listens_for(session, "after_transaction_end")
    def restart_savepoint(session, transaction):
        if transaction.nested and not transaction._parent.nested:
            # Restart SAVEPOINT after each commit/rollback
            session.expire_all()
            session.begin_nested()

    try:
        yield session
    finally:
        # Always rollback to the SAVEPOINT - this undoes all changes made during the test
        # This ensures complete isolation between parallel tests
        session.close()
        transaction.rollback()  # Rollback outer transaction (undoes everything)
        connection.close()


# ============================================================================
# Autouse Fixtures (Automatically Applied)
# ============================================================================


@pytest.fixture(autouse=True, scope="session")
def setup_test_environment():
    """Set up test environment variables for all tests.

    Autouse + session scope ensures this runs once for entire test suite.
    Ref: https://docs.pytest.org/en/stable/how-to/fixtures.html#autouse-fixtures
    """

    # Store original environment to restore later
    original_env = os.environ.copy()

    # Set test environment variables
    # Following TEST_BUILDING.md: PostgreSQL for database parity (MANDATORY)
    test_env = {
        "ENVIRONMENT": "test",
        "LOG_LEVEL": "DEBUG",
        "DATABASE_URL": "postgresql+psycopg://postgres:postgres@localhost:5432/test_db",
        "REDIS_URL": "redis://localhost:6379/15",  # Test database
        "SECRET_KEY": "test-secret-key-not-for-production",
    }

    os.environ.update(test_env)
    yield

    # Restore original environment
    os.environ.clear()
    os.environ.update(original_env)


# ============================================================================
# Data Factory Fixtures (Following Factory Pattern)
# ============================================================================


@pytest.fixture
def user_factory(faker_instance):
    """Factory for creating test user data.

    Returns a factory function following the factory pattern.
    Uses faker_instance fixture for consistent data generation.
    """

    def _create_user_data(
        username: str | None = None,
        email: str | None = None,
        password: str | None = None,
        full_name: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Create user data dictionary with sensible defaults."""
        return {
            "id": str(uuid4()),
            "username": username or faker_instance.user_name(),
            "email": email or faker_instance.email(),
            "password": password or "Test123!@#",  # Meets security requirements
            "full_name": full_name or faker_instance.name(),
            "created_at": datetime.now(UTC),
            "is_active": True,
            **kwargs,
        }

    return _create_user_data


@pytest.fixture
def job_factory(faker_instance):
    """Factory for creating test job data.

    Returns a factory function for creating job test data.
    """

    def _create_job_data(
        source_url: str | None = None,
        user_id: str | None = None,
        priority: int = 5,
        max_retries: int = 3,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Create job data dictionary with sensible defaults."""
        return {
            "id": str(uuid4()),
            "source_url": source_url or faker_instance.url(),
            "user_id": user_id or str(uuid4()),
            "priority": priority,
            "max_retries": max_retries,
            "status": "pending",
            "created_at": datetime.now(UTC),
            "domain": faker_instance.domain_name(),
            **kwargs,
        }

    return _create_job_data


@pytest.fixture
def create_job(test_session, faker_instance):
    """Factory for creating ScrapingJob database objects.

    Following TEST_BUILDING.md Factory Pattern (MANDATORY).
    Returns a factory function for creating actual ScrapingJob ORM objects.

    Automatically creates a User if user_id is not provided (foreign key constraint).
    """
    from src.common.status import JobStatus

    def _create_job(
        source_url: str | None = None,
        status: JobStatus = JobStatus.PENDING,
        created_at: datetime | None = None,
        user_id: str | None = None,
        **kwargs: Any,
    ) -> ScrapingJob:
        """Create and persist a ScrapingJob object with sensible defaults."""
        # Create a user if user_id not provided (foreign key constraint)
        if user_id is None:
            user = User(
                id=str(uuid4()),
                username=faker_instance.user_name(),
                email=faker_instance.email(),
                full_name=faker_instance.name(),
                created_at=datetime.now(UTC),
            )
            test_session.add(user)
            test_session.flush()  # Get the user ID
            user_id = user.id

        # Convert JobStatus enum to its string value for PostgreSQL
        status_value = status.value if isinstance(status, JobStatus) else status

        job = ScrapingJob(
            id=str(uuid4()),
            source_url=source_url or faker_instance.url(),
            user_id=user_id,
            status=status_value,
            created_at=created_at or datetime.now(UTC),
            domain=faker_instance.domain_name(),
            **kwargs,
        )
        test_session.add(job)
        test_session.commit()
        return job

    return _create_job


class JobFactory:
    """Job factory for creating test data - MANDATORY Factory Pattern.

    Following TEST_BUILDING.md: Each factory call creates fresh test data.
    NO CACHING - violates test independence principle.
    """

    _faker = Faker()
    _faker.seed_instance(12345)

    @classmethod
    def _ensure_user_exists(cls, session, user_id=None):
        """Create a user in database for foreign key constraint.

        MANDATORY: Creates fresh user for each call (no caching).
        Returns user_id string to avoid DetachedInstanceError.
        """

        # If user_id provided, check if exists
        if user_id:
            user = session.query(User).filter_by(id=user_id).first()
            if user:
                return user.id

        # Create fresh user for this test (MANDATORY per TEST_BUILDING.md)
        new_user_id = user_id or str(uuid4())
        user = User(
            id=new_user_id,
            username=cls._faker.user_name(),
            email=cls._faker.email(),
            full_name=cls._faker.name(),
            created_at=datetime.now(UTC),
        )
        session.add(user)
        session.flush()  # Make visible in same transaction

        return new_user_id

    @classmethod
    def create_job_request(cls, session=None, **kwargs):
        """Create JobCreateRequest with sensible defaults.

        If session provided, ensures user_id exists in database.
        """
        from src.common.status import JobPriority
        from src.database.services.job_service import JobCreateRequest

        # Handle user_id - ensure it exists if session provided
        user_id = kwargs.get("user_id")
        if session and user_id is None:
            # _ensure_user_exists now returns user_id string directly
            user_id = cls._ensure_user_exists(session)
        elif user_id is None:
            user_id = str(uuid4())  # For non-database tests

        defaults = {
            "url": kwargs.get("url", cls._faker.url()),
            "output_directory": kwargs.get("output_directory", "/tmp/output"),
            "user_id": user_id,
            "priority": kwargs.get("priority", JobPriority.NORMAL),
            "max_retries": kwargs.get("max_retries", 3),
            "options": kwargs.get("options", {}),
            "batch_id": kwargs.get("batch_id"),
        }

        return JobCreateRequest(**defaults)

    @classmethod
    def create_scraping_job(cls, session, **kwargs):
        """Create and persist a ScrapingJob database object.

        MANDATORY: Always creates User if needed to satisfy foreign key constraint.
        """
        from src.common.status import JobStatus

        # Ensure user exists (MANDATORY for foreign key)
        user_id = kwargs.get("user_id")
        # _ensure_user_exists now returns user_id string directly
        user_id = cls._ensure_user_exists(session, user_id)

        # Get status value
        status = kwargs.get("status", JobStatus.PENDING)
        status_value = status.value if isinstance(status, JobStatus) else status

        # Get priority value
        priority = kwargs.get("priority", 5)

        # Prepare options with output_directory
        options = kwargs.get("options", {})
        if "output_directory" not in options:
            options["output_directory"] = "/tmp/output"

        job = ScrapingJob(
            id=str(uuid4()),
            user_id=user_id,
            source_url=kwargs.get("source_url", cls._faker.url()),
            domain=kwargs.get("domain", cls._faker.domain_name()),
            status=status_value,
            priority=priority,
            max_retries=kwargs.get("max_retries", 3),
            retry_count=kwargs.get("retry_count", 0),
            created_at=kwargs.get("created_at", datetime.now(UTC)),
            options=options,
            batch_id=kwargs.get("batch_id"),
        )

        session.add(job)
        session.commit()
        return job


# ============================================================================
# Security Testing Fixtures
# ============================================================================


@pytest.fixture(scope="module")
def security_payloads():
    """Common security test payloads for injection testing.

    Module-scoped since payload data is static and can be shared.
    """
    return {
        "sql_injection": [
            "' OR '1'='1",
            "'; DROP TABLE users; --",
            "1; SELECT * FROM users WHERE 't' = 't",
            "' UNION SELECT * FROM users --",
            "1' UNION SELECT NULL,NULL,NULL--",
        ],
        "xss": [
            "<script>alert('XSS')</script>",
            "javascript:alert('XSS')",
            "<img src=x onerror=alert('XSS')>",
            "';alert('XSS');//",
            "<svg onload=alert('XSS')>",
        ],
        "path_traversal": [
            "../../../etc/passwd",
            "..\\..\\..\\windows\\system32\\config\\sam",
            "/etc/passwd",
            "....//....//....//etc/passwd",
            "%2e%2e%2f%2e%2e%2f%2e%2e%2fetc%2fpasswd",
        ],
        "command_injection": [
            "; ls -la",
            "| whoami",
            "&& cat /etc/passwd",
            "$(cat /etc/passwd)",
            "`whoami`",
        ],
    }


# ============================================================================
# Performance Testing Fixtures
# ============================================================================


@pytest.fixture
def performance_timer():
    """Performance timer for benchmarking test operations.

    Function-scoped to provide fresh timer for each test.
    """
    import time

    class Timer:
        """Simple performance timer with context manager support."""

        def __init__(self):
            self.start_time = None
            self.end_time = None

        def start(self):
            """Start timing."""
            self.start_time = time.perf_counter()

        def stop(self):
            """Stop timing."""
            self.end_time = time.perf_counter()

        @property
        def elapsed(self) -> float:
            """Get elapsed time in seconds."""
            if self.start_time and self.end_time:
                return self.end_time - self.start_time
            return 0.0

        def __enter__(self):
            """Context manager entry."""
            self.start()
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            """Context manager exit."""
            self.stop()

    return Timer()


# ============================================================================
# Async Testing Fixtures
# ============================================================================


@pytest.fixture
async def async_mock_session():
    """Provide async mock database session for async tests.

    Function-scoped async fixture for testing async database operations.
    """
    session = AsyncMock(spec=Session)
    session.add = Mock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.refresh = AsyncMock()
    session.execute = AsyncMock()
    session.close = AsyncMock()
    return session


@pytest_asyncio.fixture
async def async_db_session():
    """Provide real PostgreSQL async database session for integration tests.

    Function-scoped async fixture for testing async database operations with PostgreSQL.
    MANDATORY: Uses PostgreSQL for database parity per TEST_BUILDING.md.
    """
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
    from sqlalchemy.orm import sessionmaker

    from src.database.models.base import Base

    # Use PostgreSQL test database for database parity (MANDATORY)
    database_url = os.environ.get(
        "TEST_DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/test_db"
    )

    # Create async engine
    engine = create_async_engine(
        database_url,
        echo=False,
        pool_pre_ping=True,
    )

    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Create async session factory
    async_session_factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    # Create and yield session
    async with async_session_factory() as session:
        try:
            yield session
        finally:
            # Rollback any uncommitted changes
            await session.rollback()

    # Cleanup: drop tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


# ============================================================================
# Parametrized Fixtures (For Data-Driven Testing)
# ============================================================================


@pytest.fixture(
    params=[
        {"priority": 1, "expected": "low"},
        {"priority": 5, "expected": "normal"},
        {"priority": 10, "expected": "high"},
    ]
)
def priority_test_data(request):
    """Parametrized fixture for testing priority handling.

    Demonstrates pytest's parametrize capability for data-driven tests.
    Ref: https://docs.pytest.org/en/stable/how-to/parametrize.html
    """
    return request.param


# ============================================================================
# Conditional Fixtures (Environment-Dependent)
# ============================================================================


@pytest.fixture
def redis_available():
    """Check if Redis is available for testing.

    Conditional fixture that skips tests if Redis is unavailable.
    """
    try:
        import redis

        client = redis.Redis(host="localhost", port=6379, db=15)
        client.ping()
        return True
    except Exception:
        pytest.skip("Redis not available for testing")


# ============================================================================
# Fixture Overrides (Demonstrating pytest's fixture override capability)
# ============================================================================


# Note: Fixtures can be overridden in test files or subdirectory conftest.py files
# This allows for test-specific or module-specific fixture customization
# while maintaining the base fixtures defined here.


# ============================================================================
# Testing Utilities (Not fixtures, but helpful for tests)
# ============================================================================


def assert_valid_uuid(uuid_string: str) -> bool:
    """Utility function to validate UUID strings."""
    from uuid import UUID

    try:
        UUID(uuid_string)
        return True
    except (ValueError, TypeError):
        return False


def assert_valid_timestamp(timestamp: datetime) -> bool:
    """Utility function to validate datetime objects."""
    return isinstance(timestamp, datetime) and timestamp.tzinfo is not None


# ============================================================================
# Documentation and Examples
# ============================================================================


# Example usage in test files:
#
# def test_user_creation(user_factory):
#     user_data = user_factory(username="test_user")
#     assert user_data["username"] == "test_user"
#
# def test_performance_operation(performance_timer):
#     with performance_timer:
#         # Perform operation to measure
#         time.sleep(0.1)
#     assert performance_timer.elapsed >= 0.1
#
# @pytest.mark.security
# def test_sql_injection_protection(security_payloads):
#     for payload in security_payloads["sql_injection"]:
#         # Test that system handles injection attempts
#         assert sanitize_input(payload) != payload
