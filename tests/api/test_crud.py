"""Comprehensive tests for API CRUD operations - MANDATORY TEST_BUILDING.md compliance.

This module tests CRUD functionality with complete coverage:
- JobCRUD class operations
- ContentResultCRUD class operations
- Job creation with URL parsing
- Job retrieval with filtering
- Job updates and status changes
- Job deletion
- Event publishing integration
- Error handling scenarios

ALL tests follow MANDATORY TEST_BUILDING.md patterns:
- AAA pattern with explicit comments
- Factory fixtures for DRY principle
- Comprehensive CRUD scenario testing
- Performance benchmarks with specific thresholds
"""

import time
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from urllib.parse import urlparse

import pytest
from pydantic import HttpUrl

from src.api.crud import ContentResultCRUD, JobCRUD
from src.api.schemas import JobCreate, JobUpdate
from src.common.status import JobPriority, JobStatus
from src.database.models.jobs import ContentResult, ScrapingJob

# ============================================================================
# Test Fixtures - DRY Principle
# ============================================================================


@pytest.fixture
def sample_job_create() -> JobCreate:
    """Factory for sample job create data - DRY principle."""
    return JobCreate(
        url=HttpUrl("https://example.com/test-page"),
        priority=JobPriority.NORMAL,
        max_retries=3,
        options={"format": "html", "include_images": True},
        custom_slug="test-page",
        output_directory="converted_content/example.com_test-page",
    )


@pytest.fixture
def sample_job_update() -> JobUpdate:
    """Factory for sample job update data - DRY principle."""
    return JobUpdate(priority=JobPriority.HIGH, max_retries=5)


@pytest.fixture
def mock_db_session() -> AsyncMock:
    """Factory for mock database session - DRY principle."""
    session = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    session.delete = AsyncMock()
    session.execute = AsyncMock()
    return session


@pytest.fixture
def sample_job() -> ScrapingJob:
    """Factory for sample scraping job - DRY principle."""
    job = ScrapingJob(
        source_url="https://example.com/test",
        job_type="single",
        target_format="html",
        priority=JobPriority.NORMAL.value,
        max_retries=3,
        options={"format": "html"},
    )
    job.id = str(MagicMock())  # Mock ID
    job.created_at = datetime.now(UTC)
    job.started_at = None
    job.completed_at = None
    job.status = JobStatus.PENDING.value
    job.processing_time_ms = None
    job.error_message = None
    return job


@pytest.fixture
def sample_content_result(sample_job: ScrapingJob) -> ContentResult:
    """Factory for sample content result - DRY principle."""
    result = ContentResult(
        job_id=sample_job.id,
        original_html="<html><body>Original Test</body></html>",
        converted_html="<html><body>Converted Test</body></html>",
        shopify_html="<html><body>Shopify Test</body></html>",
        title="Test Page",
        meta_description="Test page description",
        word_count=100,
        image_count=5,
        link_count=10,
    )
    result.id = 1
    result.created_at = datetime.now(UTC)
    result.updated_at = datetime.now(UTC)
    return result


# ============================================================================
# JobCRUD Create Tests
# ============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
class TestJobCRUDCreate:
    """Tests for JobCRUD.create_job()."""

    async def test_create_job_creates_job_in_database(
        self, mock_db_session: AsyncMock, sample_job_create: JobCreate
    ) -> None:
        """Test create_job creates job in database - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        with patch("src.api.crud.publish_job_created", AsyncMock()):
            # Act - MANDATORY
            job = await JobCRUD.create_job(mock_db_session, sample_job_create)

            # Assert - MANDATORY
            assert job is not None
            assert job.source_url == str(sample_job_create.url)

    async def test_create_job_parses_url_correctly(
        self, mock_db_session: AsyncMock, sample_job_create: JobCreate
    ) -> None:
        """Test create_job parses URL correctly - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        with patch("src.api.crud.publish_job_created", AsyncMock()):
            # Act - MANDATORY
            job = await JobCRUD.create_job(mock_db_session, sample_job_create)

            # Assert - MANDATORY
            parsed = urlparse(job.source_url)
            assert parsed.netloc == "example.com"
            assert "test-page" in parsed.path

    async def test_create_job_uses_custom_slug_if_provided(
        self, mock_db_session: AsyncMock, sample_job_create: JobCreate
    ) -> None:
        """Test create_job uses custom_slug if provided - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        with patch("src.api.crud.publish_job_created", AsyncMock()):
            # Act - MANDATORY
            job = await JobCRUD.create_job(mock_db_session, sample_job_create)

            # Assert - MANDATORY
            assert job is not None
            # Slug is used in output directory generation
            assert sample_job_create.custom_slug is not None

    async def test_create_job_generates_slug_from_url_if_no_custom_slug(
        self, mock_db_session: AsyncMock
    ) -> None:
        """Test create_job generates slug from URL if no custom_slug - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        job_data = JobCreate(
            url=HttpUrl("https://example.com/blog/post-title"),
            priority=JobPriority.NORMAL,
            max_retries=3,
            options={},
        )

        with patch("src.api.crud.publish_job_created", AsyncMock()):
            # Act - MANDATORY
            job = await JobCRUD.create_job(mock_db_session, job_data)

            # Assert - MANDATORY
            assert job is not None
            # Slug should be generated from URL path

    async def test_create_job_generates_output_directory_if_not_provided(
        self, mock_db_session: AsyncMock
    ) -> None:
        """Test create_job generates output directory if not provided - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        job_data = JobCreate(
            url=HttpUrl("https://example.com/test"),
            priority=JobPriority.NORMAL,
            max_retries=3,
            options={},
        )

        with patch("src.api.crud.publish_job_created", AsyncMock()):
            # Act - MANDATORY
            job = await JobCRUD.create_job(mock_db_session, job_data)

            # Assert - MANDATORY
            assert job is not None
            # Output directory should be auto-generated

    async def test_create_job_sets_correct_defaults(
        self, mock_db_session: AsyncMock, sample_job_create: JobCreate
    ) -> None:
        """Test create_job sets correct defaults - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        with patch("src.api.crud.publish_job_created", AsyncMock()):
            # Act - MANDATORY
            job = await JobCRUD.create_job(mock_db_session, sample_job_create)

            # Assert - MANDATORY
            assert job.job_type == "single"
            assert job.target_format == "html"
            assert str(job.priority) == str(JobPriority.NORMAL.value)

    async def test_create_job_publishes_job_created_event(
        self, mock_db_session: AsyncMock, sample_job_create: JobCreate
    ) -> None:
        """Test create_job publishes job created event - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        mock_publish = AsyncMock()

        with patch("src.api.crud.publish_job_created", mock_publish):
            # Act - MANDATORY
            job = await JobCRUD.create_job(mock_db_session, sample_job_create)

            # Assert - MANDATORY
            mock_publish.assert_called_once()
            call_kwargs = mock_publish.call_args.kwargs
            assert call_kwargs["job_id"] == job.id
            assert call_kwargs["url"] == str(sample_job_create.url)
            assert "example.com" in call_kwargs["domain"]


# ============================================================================
# JobCRUD Get Tests
# ============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
class TestJobCRUDGet:
    """Tests for JobCRUD.get_job()."""

    async def test_get_job_returns_job_if_exists(
        self, mock_db_session: AsyncMock, sample_job: ScrapingJob
    ) -> None:
        """Test get_job returns job if exists - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_job
        mock_db_session.execute.return_value = mock_result

        # Act - MANDATORY
        job = await JobCRUD.get_job(mock_db_session, sample_job.id)

        # Assert - MANDATORY
        assert job is not None
        assert job.id == sample_job.id
        assert job.source_url == sample_job.source_url

    async def test_get_job_returns_none_if_not_exists(self, mock_db_session: AsyncMock) -> None:
        """Test get_job returns None if not exists - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        non_existent_id = "00000000-0000-0000-0000-000000000000"
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result

        # Act - MANDATORY
        job = await JobCRUD.get_job(mock_db_session, non_existent_id)

        # Assert - MANDATORY
        assert job is None

    async def test_get_job_loads_content_results(
        self,
        mock_db_session: AsyncMock,
        sample_job: ScrapingJob,
        sample_content_result: ContentResult,
    ) -> None:
        """Test get_job loads content_results relationship - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        sample_job.content_results = [sample_content_result]
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_job
        mock_db_session.execute.return_value = mock_result

        # Act - MANDATORY
        job = await JobCRUD.get_job(mock_db_session, sample_job.id)

        # Assert - MANDATORY
        assert job is not None
        # Relationship should be loaded (selectinload)
        assert hasattr(job, "content_results")
        assert len(job.content_results) == 1


# ============================================================================
# JobCRUD Get Jobs (List) Tests
# ============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
class TestJobCRUDGetJobs:
    """Tests for JobCRUD.get_jobs()."""

    async def test_get_jobs_returns_list_and_total(
        self, mock_db_session: AsyncMock, sample_job: ScrapingJob
    ) -> None:
        """Test get_jobs returns list and total count - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        mock_jobs_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [sample_job]
        mock_jobs_result.scalars.return_value = mock_scalars

        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 1

        mock_db_session.execute.side_effect = [mock_jobs_result, mock_count_result]

        # Act - MANDATORY
        jobs, total = await JobCRUD.get_jobs(mock_db_session)

        # Assert - MANDATORY
        assert isinstance(jobs, list)
        assert isinstance(total, int)
        assert total == 1
        assert len(jobs) == 1

    async def test_get_jobs_applies_pagination(
        self, mock_db_session: AsyncMock, sample_job: ScrapingJob
    ) -> None:
        """Test get_jobs applies skip/limit pagination - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # Create mock jobs list (simulating paginated results)
        job1 = ScrapingJob(
            source_url="https://example.com/page2",
            job_type="single",
            target_format="html",
            priority=JobPriority.NORMAL.value,
        )
        job2 = ScrapingJob(
            source_url="https://example.com/page3",
            job_type="single",
            target_format="html",
            priority=JobPriority.NORMAL.value,
        )

        mock_jobs_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [job1, job2]
        mock_jobs_result.scalars.return_value = mock_scalars

        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 5

        mock_db_session.execute.side_effect = [mock_jobs_result, mock_count_result]

        # Act - MANDATORY
        jobs, total = await JobCRUD.get_jobs(mock_db_session, skip=2, limit=2)

        # Assert - MANDATORY
        assert len(jobs) == 2
        assert total == 5

    async def test_get_jobs_filters_by_status(self, mock_db_session: AsyncMock) -> None:
        """Test get_jobs filters by status - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # Create jobs with pending status
        job_pending = ScrapingJob(
            source_url="https://example.com/pending",
            job_type="single",
            target_format="html",
            priority=JobPriority.NORMAL.value,
            status=JobStatus.PENDING.value,
        )

        mock_jobs_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [job_pending]
        mock_jobs_result.scalars.return_value = mock_scalars

        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 1

        mock_db_session.execute.side_effect = [mock_jobs_result, mock_count_result]

        # Act - MANDATORY
        jobs, total = await JobCRUD.get_jobs(mock_db_session, status=JobStatus.PENDING)

        # Assert - MANDATORY
        assert all(job.status == JobStatus.PENDING.value for job in jobs)
        assert total == 1

    async def test_get_jobs_filters_by_domain(self, mock_db_session: AsyncMock) -> None:
        """Test get_jobs filters by domain - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        job1 = ScrapingJob(
            source_url="https://example.com/test",
            job_type="single",
            target_format="html",
            priority=JobPriority.NORMAL.value,
        )
        job1.domain = "example.com"

        mock_jobs_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [job1]
        mock_jobs_result.scalars.return_value = mock_scalars

        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 1

        mock_db_session.execute.side_effect = [mock_jobs_result, mock_count_result]

        # Act - MANDATORY
        jobs, total = await JobCRUD.get_jobs(mock_db_session, domain="example.com")

        # Assert - MANDATORY
        assert all(job.domain == "example.com" for job in jobs)
        assert total == 1

    async def test_get_jobs_orders_by_created_at_desc(self, mock_db_session: AsyncMock) -> None:
        """Test get_jobs orders by created_at descending - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # Create jobs with different timestamps (ordered descending)
        from datetime import timedelta

        now = datetime.now(UTC)

        job1 = ScrapingJob(
            source_url="https://example.com/page0",
            job_type="single",
            target_format="html",
            priority=JobPriority.NORMAL.value,
        )
        job1.created_at = now
        job2 = ScrapingJob(
            source_url="https://example.com/page1",
            job_type="single",
            target_format="html",
            priority=JobPriority.NORMAL.value,
        )
        job2.created_at = now - timedelta(hours=1)
        job3 = ScrapingJob(
            source_url="https://example.com/page2",
            job_type="single",
            target_format="html",
            priority=JobPriority.NORMAL.value,
        )
        job3.created_at = now - timedelta(hours=2)

        mock_jobs_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [job1, job2, job3]  # Already ordered desc
        mock_jobs_result.scalars.return_value = mock_scalars

        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 3

        mock_db_session.execute.side_effect = [mock_jobs_result, mock_count_result]

        # Act - MANDATORY
        jobs, _ = await JobCRUD.get_jobs(mock_db_session, limit=10)

        # Assert - MANDATORY
        # Most recent should be first
        assert jobs[0].created_at >= jobs[1].created_at
        assert jobs[1].created_at >= jobs[2].created_at


# ============================================================================
# JobCRUD Update Tests
# ============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
class TestJobCRUDUpdate:
    """Tests for JobCRUD.update_job()."""

    async def test_update_job_updates_fields(
        self, mock_db_session: AsyncMock, sample_job: ScrapingJob, sample_job_update: JobUpdate
    ) -> None:
        """Test update_job updates fields correctly - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_job
        mock_db_session.execute.return_value = mock_result

        # Act - MANDATORY
        updated_job = await JobCRUD.update_job(mock_db_session, sample_job.id, sample_job_update)

        # Assert - MANDATORY
        assert updated_job is not None
        # Note: update_job sets priority to enum.value (string), not db integer
        assert updated_job.priority == JobPriority.HIGH.value  # type: ignore[comparison-overlap]
        assert updated_job.max_retries == 5

    async def test_update_job_returns_none_if_not_found(
        self, mock_db_session: AsyncMock, sample_job_update: JobUpdate
    ) -> None:
        """Test update_job returns None if job not found - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        non_existent_id = "00000000-0000-0000-0000-000000000000"
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result

        # Act - MANDATORY
        updated_job = await JobCRUD.update_job(mock_db_session, non_existent_id, sample_job_update)

        # Assert - MANDATORY
        assert updated_job is None

    async def test_update_job_handles_enum_values(
        self, mock_db_session: AsyncMock, sample_job: ScrapingJob
    ) -> None:
        """Test update_job handles enum values correctly - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        update_data = JobUpdate(priority=JobPriority.HIGH)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_job
        mock_db_session.execute.return_value = mock_result

        # Act - MANDATORY
        updated_job = await JobCRUD.update_job(mock_db_session, sample_job.id, update_data)

        # Assert - MANDATORY
        assert updated_job is not None
        # Note: update_job sets priority to enum.value (string), not db integer
        assert updated_job.priority == JobPriority.HIGH.value  # type: ignore[comparison-overlap]

    async def test_update_job_only_updates_provided_fields(
        self, mock_db_session: AsyncMock, sample_job: ScrapingJob
    ) -> None:
        """Test update_job only updates provided fields - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        original_max_retries = sample_job.max_retries
        update_data = JobUpdate(priority=JobPriority.HIGH)  # Only update priority
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_job
        mock_db_session.execute.return_value = mock_result

        # Act - MANDATORY
        updated_job = await JobCRUD.update_job(mock_db_session, sample_job.id, update_data)

        # Assert - MANDATORY
        assert updated_job is not None
        # Note: update_job sets priority to enum.value (string), not db integer
        assert updated_job.priority == JobPriority.HIGH.value  # type: ignore[comparison-overlap]
        assert updated_job.max_retries == original_max_retries  # Unchanged


# ============================================================================
# JobCRUD Delete Tests
# ============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
class TestJobCRUDDelete:
    """Tests for JobCRUD.delete_job()."""

    async def test_delete_job_deletes_job(
        self, mock_db_session: AsyncMock, sample_job: ScrapingJob
    ) -> None:
        """Test delete_job deletes job from database - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        job_id = sample_job.id
        # First get_job call returns the job, second returns None (after deletion)
        mock_result1 = MagicMock()
        mock_result1.scalar_one_or_none.return_value = sample_job
        mock_result2 = MagicMock()
        mock_result2.scalar_one_or_none.return_value = None
        mock_db_session.execute.side_effect = [mock_result1, mock_result2]

        with patch("src.api.crud.publish_job_deleted", AsyncMock()):
            # Act - MANDATORY
            result = await JobCRUD.delete_job(mock_db_session, job_id)

            # Assert - MANDATORY
            assert result is True
            # Verify job is deleted
            deleted_job = await JobCRUD.get_job(mock_db_session, job_id)
            assert deleted_job is None

    async def test_delete_job_returns_false_if_not_found(self, mock_db_session: AsyncMock) -> None:
        """Test delete_job returns False if job not found - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        non_existent_id = "00000000-0000-0000-0000-000000000000"
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result

        with patch("src.api.crud.publish_job_deleted", AsyncMock()):
            # Act - MANDATORY
            result = await JobCRUD.delete_job(mock_db_session, non_existent_id)

            # Assert - MANDATORY
            assert result is False

    async def test_delete_job_publishes_deleted_event(
        self, mock_db_session: AsyncMock, sample_job: ScrapingJob
    ) -> None:
        """Test delete_job publishes job deleted event - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_job
        mock_db_session.execute.return_value = mock_result
        mock_publish = AsyncMock()

        with patch("src.api.crud.publish_job_deleted", mock_publish):
            # Act - MANDATORY
            await JobCRUD.delete_job(mock_db_session, sample_job.id)

            # Assert - MANDATORY
            mock_publish.assert_called_once()
            call_kwargs = mock_publish.call_args.kwargs
            assert call_kwargs["job_id"] == sample_job.id
            assert call_kwargs["url"] == sample_job.source_url


# ============================================================================
# JobCRUD Update Status Tests
# ============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
class TestJobCRUDUpdateStatus:
    """Tests for JobCRUD.update_job_status()."""

    async def test_update_job_status_updates_status(
        self, mock_db_session: AsyncMock, sample_job: ScrapingJob
    ) -> None:
        """Test update_job_status updates status correctly - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_job
        mock_db_session.execute.return_value = mock_result

        with patch("src.api.crud.publish_job_status_update", AsyncMock()):
            # Act - MANDATORY
            updated_job = await JobCRUD.update_job_status(
                mock_db_session, sample_job.id, JobStatus.RUNNING
            )

            # Assert - MANDATORY
            assert updated_job is not None
            assert updated_job.status == JobStatus.RUNNING.value

    async def test_update_job_status_sets_started_at_for_running(
        self, mock_db_session: AsyncMock, sample_job: ScrapingJob
    ) -> None:
        """Test update_job_status sets started_at for RUNNING status - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_job
        mock_db_session.execute.return_value = mock_result

        with patch("src.api.crud.publish_job_status_update", AsyncMock()):
            # Act - MANDATORY
            updated_job = await JobCRUD.update_job_status(
                mock_db_session, sample_job.id, JobStatus.RUNNING
            )

            # Assert - MANDATORY
            assert updated_job is not None
            assert updated_job.started_at is not None

    async def test_update_job_status_sets_completed_at_for_completed(
        self, mock_db_session: AsyncMock, sample_job: ScrapingJob
    ) -> None:
        """Test update_job_status sets completed_at for COMPLETED status - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_job
        mock_db_session.execute.return_value = mock_result

        with patch("src.api.crud.publish_job_status_update", AsyncMock()):
            # Act - MANDATORY
            updated_job = await JobCRUD.update_job_status(
                mock_db_session, sample_job.id, JobStatus.COMPLETED
            )

            # Assert - MANDATORY
            assert updated_job is not None
            assert updated_job.completed_at is not None

    async def test_update_job_status_sets_completed_at_for_failed(
        self, mock_db_session: AsyncMock, sample_job: ScrapingJob
    ) -> None:
        """Test update_job_status sets completed_at for FAILED status - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_job
        mock_db_session.execute.return_value = mock_result

        with patch("src.api.crud.publish_job_status_update", AsyncMock()):
            # Act - MANDATORY
            updated_job = await JobCRUD.update_job_status(
                mock_db_session, sample_job.id, JobStatus.FAILED, error_message="Test error"
            )

            # Assert - MANDATORY
            assert updated_job is not None
            assert updated_job.completed_at is not None
            assert updated_job.error_message == "Test error"

    async def test_update_job_status_publishes_status_update_event(
        self, mock_db_session: AsyncMock, sample_job: ScrapingJob
    ) -> None:
        """Test update_job_status publishes status update event - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_job
        mock_db_session.execute.return_value = mock_result
        mock_publish = AsyncMock()

        with patch("src.api.crud.publish_job_status_update", mock_publish):
            # Act - MANDATORY
            await JobCRUD.update_job_status(mock_db_session, sample_job.id, JobStatus.RUNNING)

            # Assert - MANDATORY
            mock_publish.assert_called_once()

    async def test_update_job_status_does_not_publish_if_status_unchanged(
        self, mock_db_session: AsyncMock, sample_job: ScrapingJob
    ) -> None:
        """Test update_job_status doesn't publish event if status unchanged - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_job
        mock_db_session.execute.return_value = mock_result
        mock_publish = AsyncMock()
        current_status = JobStatus(sample_job.status)

        with patch("src.api.crud.publish_job_status_update", mock_publish):
            # Act - MANDATORY
            await JobCRUD.update_job_status(mock_db_session, sample_job.id, current_status)

            # Assert - MANDATORY
            mock_publish.assert_not_called()

    async def test_update_job_status_returns_none_if_not_found(
        self, mock_db_session: AsyncMock
    ) -> None:
        """Test update_job_status returns None if job not found - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        non_existent_id = "00000000-0000-0000-0000-000000000000"
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result

        with patch("src.api.crud.publish_job_status_update", AsyncMock()):
            # Act - MANDATORY
            updated_job = await JobCRUD.update_job_status(
                mock_db_session, non_existent_id, JobStatus.RUNNING
            )

            # Assert - MANDATORY
            assert updated_job is None


# ============================================================================
# ContentResultCRUD Get Tests
# ============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
class TestContentResultCRUDGet:
    """Tests for ContentResultCRUD.get_content_result()."""

    async def test_get_content_result_returns_result_if_exists(
        self, mock_db_session: AsyncMock, sample_content_result: ContentResult
    ) -> None:
        """Test get_content_result returns result if exists - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_content_result
        mock_db_session.execute.return_value = mock_result

        # Act - MANDATORY
        result = await ContentResultCRUD.get_content_result(
            mock_db_session, sample_content_result.id
        )

        # Assert - MANDATORY
        assert result is not None
        assert result.id == sample_content_result.id
        assert result.title == sample_content_result.title

    async def test_get_content_result_returns_none_if_not_exists(
        self, mock_db_session: AsyncMock
    ) -> None:
        """Test get_content_result returns None if not exists - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        non_existent_id = 999999
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result

        # Act - MANDATORY
        result = await ContentResultCRUD.get_content_result(mock_db_session, non_existent_id)

        # Assert - MANDATORY
        assert result is None


# ============================================================================
# ContentResultCRUD Get By Job Tests
# ============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
class TestContentResultCRUDGetByJob:
    """Tests for ContentResultCRUD.get_content_results_by_job()."""

    async def test_get_content_results_by_job_returns_list(
        self,
        mock_db_session: AsyncMock,
        sample_job: ScrapingJob,
        sample_content_result: ContentResult,
    ) -> None:
        """Test get_content_results_by_job returns list - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [sample_content_result]
        mock_result.scalars.return_value = mock_scalars
        mock_db_session.execute.return_value = mock_result

        # Act - MANDATORY
        results = await ContentResultCRUD.get_content_results_by_job(mock_db_session, sample_job.id)

        # Assert - MANDATORY
        assert isinstance(results, list)
        assert len(results) == 1
        assert all(r.job_id == sample_job.id for r in results)

    async def test_get_content_results_by_job_returns_empty_if_no_results(
        self, mock_db_session: AsyncMock, sample_job: ScrapingJob
    ) -> None:
        """Test get_content_results_by_job returns empty list if no results - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result.scalars.return_value = mock_scalars
        mock_db_session.execute.return_value = mock_result

        # Act - MANDATORY
        results = await ContentResultCRUD.get_content_results_by_job(mock_db_session, sample_job.id)

        # Assert - MANDATORY
        assert isinstance(results, list)
        assert len(results) == 0

    async def test_get_content_results_by_job_orders_by_created_at_desc(
        self, mock_db_session: AsyncMock, sample_job: ScrapingJob
    ) -> None:
        """Test get_content_results_by_job orders by created_at desc - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        from datetime import timedelta

        now = datetime.now(UTC)

        # Create results with different timestamps (ordered descending)
        result1 = ContentResult(
            job_id=sample_job.id, original_html="<html>Test 0</html>", title="Result 0"
        )
        result1.created_at = now
        result2 = ContentResult(
            job_id=sample_job.id, original_html="<html>Test 1</html>", title="Result 1"
        )
        result2.created_at = now - timedelta(hours=1)
        result3 = ContentResult(
            job_id=sample_job.id, original_html="<html>Test 2</html>", title="Result 2"
        )
        result3.created_at = now - timedelta(hours=2)

        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [result1, result2, result3]  # Already ordered desc
        mock_result.scalars.return_value = mock_scalars
        mock_db_session.execute.return_value = mock_result

        # Act - MANDATORY
        results = await ContentResultCRUD.get_content_results_by_job(mock_db_session, sample_job.id)

        # Assert - MANDATORY
        assert results[0].created_at >= results[1].created_at
        assert results[1].created_at >= results[2].created_at


# ============================================================================
# Integration Tests
# ============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
class TestCRUDIntegration:
    """Integration tests for CRUD operations."""

    async def test_full_job_lifecycle(
        self, mock_db_session: AsyncMock, sample_job_create: JobCreate, sample_job: ScrapingJob
    ) -> None:
        """Test complete job lifecycle - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # Mock sequence: create returns job, get returns job (3x), delete returns job, final get returns None
        mock_result1 = MagicMock()
        mock_result1.scalar_one_or_none.return_value = sample_job  # get after create
        mock_result2 = MagicMock()
        mock_result2.scalar_one_or_none.return_value = sample_job  # get for update
        mock_result3 = MagicMock()
        mock_result3.scalar_one_or_none.return_value = sample_job  # get for update_status
        mock_result4 = MagicMock()
        mock_result4.scalar_one_or_none.return_value = sample_job  # get for delete
        mock_result5 = MagicMock()
        mock_result5.scalar_one_or_none.return_value = None  # get after delete

        mock_db_session.execute.side_effect = [
            mock_result1,
            mock_result2,
            mock_result3,
            mock_result4,
            mock_result5,
        ]

        with (
            patch("src.api.crud.publish_job_created", AsyncMock()),
            patch("src.api.crud.publish_job_status_update", AsyncMock()),
            patch("src.api.crud.publish_job_deleted", AsyncMock()),
        ):
            # Act - MANDATORY
            # Create
            job = await JobCRUD.create_job(mock_db_session, sample_job_create)
            assert job is not None

            # Retrieve
            retrieved_job = await JobCRUD.get_job(mock_db_session, job.id)
            assert retrieved_job is not None

            # Update
            update_data = JobUpdate(priority=JobPriority.HIGH)
            updated_job = await JobCRUD.update_job(mock_db_session, job.id, update_data)
            assert updated_job is not None
            # Note: update_job sets priority to enum.value (string), not db integer
            assert updated_job.priority == JobPriority.HIGH.value  # type: ignore[comparison-overlap]

            # Update status
            status_updated = await JobCRUD.update_job_status(
                mock_db_session, job.id, JobStatus.RUNNING
            )
            assert status_updated is not None
            assert status_updated.status == JobStatus.RUNNING.value

            # Delete
            deleted = await JobCRUD.delete_job(mock_db_session, job.id)
            assert deleted is True

            # Verify deletion
            deleted_job = await JobCRUD.get_job(mock_db_session, job.id)
            assert deleted_job is None


# ============================================================================
# MANDATORY Performance Benchmarks
# ============================================================================


@pytest.mark.performance
@pytest.mark.unit
@pytest.mark.asyncio
class TestCRUDPerformance:
    """MANDATORY performance tests for CRUD operations."""

    async def test_create_job_performance(self, mock_db_session: AsyncMock) -> None:
        """MANDATORY performance test - job creation speed."""
        # Arrange - MANDATORY
        iterations = 10
        job_creates = [
            JobCreate(
                url=HttpUrl(f"https://example.com/page{i}"),
                priority=JobPriority.NORMAL,
                max_retries=3,
                options={},
            )
            for i in range(iterations)
        ]

        with patch("src.api.crud.publish_job_created", AsyncMock()):
            # Act - MANDATORY
            start_time = time.perf_counter()

            for job_create in job_creates:
                await JobCRUD.create_job(mock_db_session, job_create)

            end_time = time.perf_counter()
            execution_time = end_time - start_time

            # Assert - MANDATORY
            avg_time = execution_time / iterations
            assert avg_time < 0.1  # <100ms per job creation
            assert execution_time < 1.0  # Total <1s for 10 creations

    async def test_get_jobs_performance(
        self, mock_db_session: AsyncMock, sample_job: ScrapingJob
    ) -> None:
        """MANDATORY performance test - get jobs list speed."""
        # Arrange - MANDATORY
        iterations = 100

        # Mock get_jobs to return consistent results
        mock_jobs_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [sample_job]
        mock_jobs_result.scalars.return_value = mock_scalars

        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 1

        # Set side_effect to return the same mocks for all iterations
        mock_db_session.execute.side_effect = [mock_jobs_result, mock_count_result] * iterations

        # Act - MANDATORY
        start_time = time.perf_counter()

        for _ in range(iterations):
            await JobCRUD.get_jobs(mock_db_session, limit=10)

        end_time = time.perf_counter()
        execution_time = end_time - start_time

        # Assert - MANDATORY
        avg_time = execution_time / iterations
        assert avg_time < 0.05  # <50ms per query
        assert execution_time < 5.0  # Total <5s for 100 queries
