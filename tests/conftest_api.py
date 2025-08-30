"""Shared fixtures for API tests."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.schemas import BatchCreate, JobCreate
from src.database.models import Batch, JobPriority, JobStatus, ScrapingJob


@pytest.fixture
def mock_db_session():
    """Create a mock database session for API tests."""
    return AsyncMock(spec=AsyncSession)


@pytest.fixture
def sample_job():
    """Sample ScrapingJob instance with all required fields."""
    return ScrapingJob(
        id=1,
        url="https://example.com/test",
        domain="example.com",
        slug="test",
        status=JobStatus.PENDING,
        priority=JobPriority.NORMAL,
        created_at=datetime.now(timezone.utc),
        retry_count=0,
        max_retries=3,
        timeout_seconds=30,
        output_directory="converted_content/test",
        skip_existing=False,
        success=False,
        images_downloaded=0,
    )


@pytest.fixture
def sample_batch():
    """Sample Batch instance with all required fields."""
    return Batch(
        id=1,
        name="Sample Batch",
        description="A sample batch",
        status=JobStatus.PENDING,
        created_at=datetime.now(timezone.utc),
        max_concurrent=10,
        continue_on_error=True,
        output_base_directory="batch_output/sample",
        create_archives=False,
        cleanup_after_archive=False,
        total_jobs=2,
        completed_jobs=0,
        failed_jobs=0,
        skipped_jobs=0,
    )


@pytest.fixture
def job_create_data():
    """Sample job creation data."""
    return JobCreate(
        url="https://example.com/test-page",
        priority=JobPriority.HIGH,
        custom_slug="test-page-slug",
        max_retries=5,
        timeout_seconds=60,
        skip_existing=True,
        converter_config={"preserve_images": True},
        processing_options={"clean_html": True},
    )


@pytest.fixture
def batch_create_data():
    """Sample batch creation data."""
    return BatchCreate(
        name="Test Batch",
        description="A test batch",
        urls=["https://example.com/page1", "https://example.com/page2"],
        max_concurrent=5,
        continue_on_error=True,
        output_base_directory="test_batch_output",
    )
