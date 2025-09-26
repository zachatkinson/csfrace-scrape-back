"""Shared fixtures for API tests."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.schemas import JobCreate
from src.database.models import JobPriority, JobStatus, ScrapingJob


@pytest.fixture
def mock_db_session():
    """Create a mock database session for API tests."""
    return AsyncMock(spec=AsyncSession)


@pytest.fixture
def sample_job():
    """Sample ScrapingJob instance with all required fields."""
    return ScrapingJob(
        id="sample-job-id-1",  # String UUID instead of integer
        user_id="test-user-id",  # Required field
        source_url="https://example.com/test",  # Required field
        domain="example.com",
        slug="test",
        status=JobStatus.PENDING.value,  # Use string value
        priority=JobPriority.NORMAL.value,  # Use string value
        created_at=datetime.now(UTC),
        retry_count=0,
        max_retries=3,
        # timeout_seconds=30,  # Not a model field
        output_directory="converted_content/test",
        # skip_existing=False,  # Not a model field
        success=False,
        images_downloaded=0,
    )


@pytest.fixture
def job_create_data():
    """Sample job creation data."""
    return JobCreate(
        url="https://example.com/test-page",
        priority=JobPriority.HIGH,
        custom_slug="test-page-slug",
        max_retries=5,
        options={"preserve_images": True},
    )
