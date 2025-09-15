"""Shared fixtures for API tests."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.schemas import BatchCreate, JobCreate
from src.database.models import Batch, BatchStatus, JobPriority, JobStatus, ScrapingJob


@pytest.fixture
def mock_db_session():
    """Create a mock database session for API tests."""
    return AsyncMock(spec=AsyncSession)


@pytest.fixture
def sample_job():
    """Sample ScrapingJob instance with all required fields."""
    return ScrapingJob(
        id="sample-job-id-1",  # String UUID instead of integer
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
def sample_batch():
    """Sample Batch instance with all required fields."""
    return Batch(
        id="sample-batch-id-1",  # String UUID instead of integer
        name="Sample Batch",
        description="A sample batch",
        status=BatchStatus.PENDING.value,  # Use string value
        created_at=datetime.now(UTC),
        max_concurrent=10,
        continue_on_error=True,
        output_base_directory="batch_output/sample",
        # create_archives=False,  # Not a Batch model field
        # cleanup_after_archive=False,  # Not a Batch model field
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
        priority=JobPriority.HIGH.value,
        custom_slug="test-page-slug",
        max_retries=5,
        # timeout_seconds=60,  # Not a model field
        # skip_existing=True,  # Not a model field
        # converter_config={"preserve_images": True},  # Should be 'options'
        # processing_options={"clean_html": True},  # Not a model field
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
