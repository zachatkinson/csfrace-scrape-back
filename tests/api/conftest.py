"""API test configuration and fixtures."""

import asyncio
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from src.api.dependencies import get_db_session
from src.api.main import app
from src.database.models import Base, Batch, JobPriority, JobStatus, ScrapingJob

# Test database URL
TEST_DATABASE_URL = "sqlite+aiosqlite:///test.db"


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def test_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Create a test database session."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)

    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    # Create session
    TestSessionLocal = sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    async with TestSessionLocal() as session:
        yield session

    # Cleanup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest.fixture
def override_get_db(test_db_session):
    """Override the database dependency."""

    async def _get_test_db():
        yield test_db_session

    app.dependency_overrides[get_db_session] = _get_test_db
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def client(override_get_db) -> TestClient:
    """Create a test client."""
    return TestClient(app)


@pytest_asyncio.fixture
async def async_client(override_get_db) -> AsyncGenerator[AsyncClient, None]:
    """Create an async test client."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        yield client


@pytest_asyncio.fixture
async def sample_job(test_db_session: AsyncSession) -> ScrapingJob:
    """Create a sample scraping job for testing."""
    job = ScrapingJob(
        url="https://example.com/test-page",
        domain="example.com",
        slug="test-page",
        priority=JobPriority.NORMAL,
        status=JobStatus.PENDING,
        max_retries=3,
        timeout_seconds=30,
        skip_existing=False,
        output_directory="converted_content/example.com_test-page",  # Required field
    )
    test_db_session.add(job)
    await test_db_session.commit()
    await test_db_session.refresh(job)
    return job


@pytest_asyncio.fixture
async def sample_batch(test_db_session: AsyncSession) -> Batch:
    """Create a sample batch for testing."""
    batch = Batch(
        name="Test Batch",
        description="A test batch for API testing",
        total_jobs=2,
        max_concurrent=5,
        continue_on_error=True,
        output_base_directory="test_output",
        create_archives=False,
        cleanup_after_archive=False,
    )
    test_db_session.add(batch)
    await test_db_session.commit()
    await test_db_session.refresh(batch)
    return batch


@pytest.fixture
def job_create_data():
    """Sample job creation data."""
    return {
        "url": "https://example.com/new-page",
        "priority": "normal",
        "custom_slug": "new-test-page",
        "max_retries": 5,
        "timeout_seconds": 45,
        "skip_existing": True,
        "converter_config": {"preserve_images": True},
        "processing_options": {"clean_html": True},
    }


@pytest.fixture
def batch_create_data():
    """Sample batch creation data."""
    return {
        "name": "New Test Batch",
        "description": "A new batch created via API",
        "urls": [
            "https://example.com/page1",
            "https://example.com/page2",
            "https://example.com/page3",
        ],
        "max_concurrent": 3,
        "continue_on_error": False,
        "create_archives": True,
        "cleanup_after_archive": True,
        "batch_config": {"retry_failed": True},
    }
