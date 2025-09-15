"""Comprehensive tests for src/api/crud.py module.

This test module provides comprehensive coverage for all CRUD operations
in the API crud module to achieve 80%+ coverage as required.
"""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.crud import ContentResultCRUD, JobCRUD
from src.api.schemas import JobCreate, JobUpdate
from src.common.status import JobPriority, JobStatus
from src.database.models import ContentResult, ScrapingJob


class TestJobCRUD:
    """Test JobCRUD class methods."""

    @pytest.fixture
    def mock_db_session(self):
        """Create mock database session."""
        return AsyncMock(spec=AsyncSession)

    @pytest.fixture
    def job_create_data(self):
        """Sample job creation data."""
        return JobCreate(
            url="https://example.com/test-page",
            custom_slug="test-slug",
            priority=JobPriority.HIGH,
            output_directory="/custom/output",
            max_retries=5,
            options={"format": "html"},
        )

    @pytest.fixture
    def job_create_minimal(self):
        """Minimal job creation data."""
        return JobCreate(url="https://minimal.com/page")

    @pytest.fixture
    def job_update_data(self):
        """Sample job update data."""
        return JobUpdate(priority=JobPriority.LOW, max_retries=2, options={"new_option": "value"})

    @pytest.fixture
    def sample_job(self):
        """Sample ScrapingJob instance."""
        job_id = str(uuid4())
        return ScrapingJob(
            id=job_id,
            source_url="https://example.com/test",
            domain="example.com",
            slug="test",
            priority=JobPriority.NORMAL.value,
            status=JobStatus.PENDING.value,
            output_directory="converted_content/example.com_test",
            max_retries=3,
        )

    @pytest.mark.asyncio
    async def test_create_job_with_custom_slug(self, mock_db_session, job_create_data):
        """Test creating job with custom slug provided."""
        # Mock the publish_job_created function
        with patch("src.api.crud.publish_job_created", new_callable=AsyncMock) as mock_publish:
            # Setup flush mock to simulate database ID assignment
            async def mock_flush():
                # Simulate database assigning an ID
                job = mock_db_session.add.call_args[0][0]
                job.id = str(uuid4())

            mock_db_session.flush = AsyncMock(side_effect=mock_flush)

            result = await JobCRUD.create_job(mock_db_session, job_create_data)

            # Verify job properties
            assert result.source_url == str(job_create_data.url)
            assert result.domain == "example.com"
            assert result.slug == "test-slug"  # custom_slug used
            assert result.priority == JobPriority.HIGH.value
            assert result.output_directory == "/custom/output"
            assert result.max_retries == 5
            assert result.options == {"format": "html"}

            # Verify database interactions
            mock_db_session.add.assert_called_once()
            mock_db_session.flush.assert_called_once()

            # Verify event publishing
            mock_publish.assert_called_once()
            call_args = mock_publish.call_args[1]
            assert call_args["url"] == str(job_create_data.url)
            assert call_args["domain"] == "example.com"

    @pytest.mark.asyncio
    async def test_create_job_auto_generated_slug(self, mock_db_session, job_create_minimal):
        """Test creating job with auto-generated slug."""
        with patch("src.api.crud.publish_job_created", new_callable=AsyncMock):
            # Setup flush mock
            async def mock_flush():
                job = mock_db_session.add.call_args[0][0]
                job.id = str(uuid4())

            mock_db_session.flush = AsyncMock(side_effect=mock_flush)

            result = await JobCRUD.create_job(mock_db_session, job_create_minimal)

            assert result.domain == "minimal.com"
            assert result.slug == "page"  # Auto-generated from URL path
            assert result.output_directory == "converted_content/minimal.com_page"

    @pytest.mark.asyncio
    async def test_create_job_root_path_slug(self, mock_db_session):
        """Test creating job with root path generates 'index' slug."""
        job_data = JobCreate(url="https://example.com/")

        with patch("src.api.crud.publish_job_created", new_callable=AsyncMock):

            async def mock_flush():
                job = mock_db_session.add.call_args[0][0]
                job.id = str(uuid4())

            mock_db_session.flush = AsyncMock(side_effect=mock_flush)

            result = await JobCRUD.create_job(mock_db_session, job_data)

            assert result.slug == "index"
            assert result.output_directory == "converted_content/example.com_index"

    @pytest.mark.asyncio
    async def test_get_job_found(self, mock_db_session, sample_job):
        """Test getting job by ID when job exists."""
        job_id = sample_job.id

        # Mock query execution
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_job
        mock_db_session.execute.return_value = mock_result

        result = await JobCRUD.get_job(mock_db_session, job_id)

        assert result == sample_job
        mock_db_session.execute.assert_called_once()

        # Verify the query structure
        call_args = mock_db_session.execute.call_args[0][0]
        assert hasattr(call_args, "whereclause")

    @pytest.mark.asyncio
    async def test_get_job_not_found(self, mock_db_session):
        """Test getting job by ID when job doesn't exist."""
        job_id = str(uuid4())

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result

        result = await JobCRUD.get_job(mock_db_session, job_id)

        assert result is None
        mock_db_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_jobs_no_filters(self, mock_db_session):
        """Test getting jobs without filters."""
        sample_jobs = [MagicMock(), MagicMock()]

        # Mock jobs query result
        mock_jobs_result = MagicMock()
        mock_jobs_result.scalars.return_value.all.return_value = sample_jobs

        # Mock count query result
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 2

        mock_db_session.execute.side_effect = [mock_jobs_result, mock_count_result]

        jobs, total = await JobCRUD.get_jobs(mock_db_session)

        assert jobs == sample_jobs
        assert total == 2
        assert mock_db_session.execute.call_count == 2

    @pytest.mark.asyncio
    async def test_get_jobs_with_filters(self, mock_db_session):
        """Test getting jobs with status and domain filters."""
        sample_jobs = [MagicMock()]

        mock_jobs_result = MagicMock()
        mock_jobs_result.scalars.return_value.all.return_value = sample_jobs

        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 1

        mock_db_session.execute.side_effect = [mock_jobs_result, mock_count_result]

        jobs, total = await JobCRUD.get_jobs(
            mock_db_session, skip=10, limit=20, status=JobStatus.COMPLETED, domain="example.com"
        )

        assert jobs == sample_jobs
        assert total == 1
        assert mock_db_session.execute.call_count == 2

    @pytest.mark.asyncio
    async def test_get_jobs_zero_count(self, mock_db_session):
        """Test getting jobs when count returns None."""
        mock_jobs_result = MagicMock()
        mock_jobs_result.scalars.return_value.all.return_value = []

        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = None  # SQLAlchemy can return None

        mock_db_session.execute.side_effect = [mock_jobs_result, mock_count_result]

        jobs, total = await JobCRUD.get_jobs(mock_db_session)

        assert jobs == []
        assert total == 0  # Should default to 0 when None

    @pytest.mark.asyncio
    async def test_update_job_found(self, mock_db_session, sample_job, job_update_data):
        """Test updating job when job exists."""
        with patch.object(JobCRUD, "get_job", return_value=sample_job) as mock_get:
            result = await JobCRUD.update_job(mock_db_session, sample_job.id, job_update_data)

            assert result == sample_job
            assert sample_job.priority == JobPriority.LOW.value  # Enum converted to string
            assert sample_job.max_retries == 2
            assert sample_job.options == {"new_option": "value"}

            mock_get.assert_called_once_with(mock_db_session, sample_job.id)
            mock_db_session.flush.assert_called_once()
            mock_db_session.refresh.assert_called_once_with(sample_job)

    @pytest.mark.asyncio
    async def test_update_job_not_found(self, mock_db_session, job_update_data):
        """Test updating job when job doesn't exist."""
        job_id = str(uuid4())

        with patch.object(JobCRUD, "get_job", return_value=None) as mock_get:
            result = await JobCRUD.update_job(mock_db_session, job_id, job_update_data)

            assert result is None
            mock_get.assert_called_once_with(mock_db_session, job_id)
            mock_db_session.flush.assert_not_called()

    @pytest.mark.asyncio
    async def test_update_job_enum_conversion(self, mock_db_session, sample_job):
        """Test that enum values are properly converted to strings."""
        update_data = JobUpdate(priority=JobPriority.URGENT)

        with patch.object(JobCRUD, "get_job", return_value=sample_job):
            await JobCRUD.update_job(mock_db_session, sample_job.id, update_data)

            assert sample_job.priority == JobPriority.URGENT.value  # String value

    @pytest.mark.asyncio
    async def test_delete_job_found(self, mock_db_session, sample_job):
        """Test deleting job when job exists."""
        with patch.object(JobCRUD, "get_job", return_value=sample_job) as mock_get:
            with patch("src.api.crud.publish_job_deleted", new_callable=AsyncMock) as mock_publish:
                result = await JobCRUD.delete_job(mock_db_session, sample_job.id)

                assert result is True
                mock_get.assert_called_once_with(mock_db_session, sample_job.id)
                mock_db_session.delete.assert_called_once_with(sample_job)

                # Verify event publishing
                mock_publish.assert_called_once()
                call_args = mock_publish.call_args[1]
                assert call_args["job_id"] == sample_job.id
                assert call_args["url"] == sample_job.source_url
                assert call_args["domain"] == sample_job.domain

    @pytest.mark.asyncio
    async def test_delete_job_not_found(self, mock_db_session):
        """Test deleting job when job doesn't exist."""
        job_id = str(uuid4())

        with patch.object(JobCRUD, "get_job", return_value=None) as mock_get:
            result = await JobCRUD.delete_job(mock_db_session, job_id)

            assert result is False
            mock_get.assert_called_once_with(mock_db_session, job_id)
            mock_db_session.delete.assert_not_called()

    @pytest.mark.asyncio
    async def test_update_job_status_found(self, mock_db_session, sample_job):
        """Test updating job status when job exists."""
        with patch.object(JobCRUD, "get_job", return_value=sample_job) as mock_get:
            with patch(
                "src.api.crud.publish_job_status_update", new_callable=AsyncMock
            ) as mock_publish:
                result = await JobCRUD.update_job_status(
                    mock_db_session,
                    sample_job.id,
                    JobStatus.RUNNING,
                    error_message="Test error",
                    error_type="TestError",
                )

                assert result == sample_job
                assert sample_job.status == JobStatus.RUNNING.value
                assert sample_job.error_message == "Test error"
                assert sample_job.error_type == "TestError"
                assert sample_job.started_at is not None  # Should be set for RUNNING status

                mock_get.assert_called_once()
                mock_db_session.flush.assert_called_once()
                mock_db_session.refresh.assert_called_once()
                mock_publish.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_job_status_completion_timestamps(self, mock_db_session, sample_job):
        """Test that completion timestamps are set for terminal statuses."""
        with patch.object(JobCRUD, "get_job", return_value=sample_job):
            with patch("src.api.crud.publish_job_status_update", new_callable=AsyncMock):
                # Test COMPLETED status
                await JobCRUD.update_job_status(mock_db_session, sample_job.id, JobStatus.COMPLETED)

                assert sample_job.status == JobStatus.COMPLETED.value
                assert sample_job.completed_at is not None
                assert sample_job.success is True

    @pytest.mark.asyncio
    async def test_update_job_status_failure_timestamps(self, mock_db_session, sample_job):
        """Test that failure timestamps are set for FAILED status."""
        with patch.object(JobCRUD, "get_job", return_value=sample_job):
            with patch("src.api.crud.publish_job_status_update", new_callable=AsyncMock):
                await JobCRUD.update_job_status(mock_db_session, sample_job.id, JobStatus.FAILED)

                assert sample_job.status == JobStatus.FAILED.value
                assert sample_job.completed_at is not None
                assert sample_job.success is False

    @pytest.mark.asyncio
    async def test_update_job_status_no_status_change(self, mock_db_session, sample_job):
        """Test that events are not published when status doesn't change."""
        sample_job.status = JobStatus.RUNNING.value

        with patch.object(JobCRUD, "get_job", return_value=sample_job):
            with patch(
                "src.api.crud.publish_job_status_update", new_callable=AsyncMock
            ) as mock_publish:
                await JobCRUD.update_job_status(mock_db_session, sample_job.id, JobStatus.RUNNING)

                # Event should not be published if status didn't change
                mock_publish.assert_not_called()

    @pytest.mark.asyncio
    async def test_update_job_status_not_found(self, mock_db_session):
        """Test updating status when job doesn't exist."""
        job_id = str(uuid4())

        with patch.object(JobCRUD, "get_job", return_value=None):
            result = await JobCRUD.update_job_status(mock_db_session, job_id, JobStatus.FAILED)

            assert result is None


class TestContentResultCRUD:
    """Test ContentResultCRUD class methods."""

    @pytest.fixture
    def mock_db_session(self):
        """Create mock database session."""
        return AsyncMock(spec=AsyncSession)

    @pytest.fixture
    def sample_content_result(self):
        """Sample ContentResult instance."""
        return ContentResult(
            id=1,
            job_id=str(uuid4()),
            title="Test Content",
            meta_description="Test description",
            word_count=500,
            image_count=3,
            link_count=10,
        )

    @pytest.mark.asyncio
    async def test_get_content_result_found(self, mock_db_session, sample_content_result):
        """Test getting content result by ID when it exists."""
        result_id = sample_content_result.id

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_content_result
        mock_db_session.execute.return_value = mock_result

        result = await ContentResultCRUD.get_content_result(mock_db_session, result_id)

        assert result == sample_content_result
        mock_db_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_content_result_not_found(self, mock_db_session):
        """Test getting content result by ID when it doesn't exist."""
        result_id = 999

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result

        result = await ContentResultCRUD.get_content_result(mock_db_session, result_id)

        assert result is None
        mock_db_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_content_results_by_job(self, mock_db_session):
        """Test getting all content results for a job."""
        job_id = str(uuid4())
        content_results = [MagicMock(), MagicMock()]

        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = content_results
        mock_result.scalars.return_value = mock_scalars
        mock_db_session.execute.return_value = mock_result

        results = await ContentResultCRUD.get_content_results_by_job(mock_db_session, job_id)

        assert results == content_results
        mock_db_session.execute.assert_called_once()

        # Verify query includes job_id filter and ordering
        call_args = mock_db_session.execute.call_args[0][0]
        assert hasattr(call_args, "whereclause")

    @pytest.mark.asyncio
    async def test_get_content_results_by_job_empty(self, mock_db_session):
        """Test getting content results when none exist for job."""
        job_id = str(uuid4())

        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result.scalars.return_value = mock_scalars
        mock_db_session.execute.return_value = mock_result

        results = await ContentResultCRUD.get_content_results_by_job(mock_db_session, job_id)

        assert results == []
        mock_db_session.execute.assert_called_once()


class TestCRUDIntegration:
    """Integration tests for CRUD operations."""

    @pytest.fixture
    def mock_db_session(self):
        """Create mock database session for integration tests."""
        return AsyncMock(spec=AsyncSession)

    @pytest.mark.asyncio
    async def test_job_lifecycle(self, mock_db_session):
        """Test complete job lifecycle: create, get, update, delete."""
        # Create job
        job_data = JobCreate(url="https://lifecycle.com/test")

        with patch("src.api.crud.publish_job_created", new_callable=AsyncMock):
            with patch("src.api.crud.publish_job_deleted", new_callable=AsyncMock):
                # Mock flush to assign ID
                async def mock_flush():
                    job = mock_db_session.add.call_args[0][0]
                    job.id = str(uuid4())

                mock_db_session.flush = AsyncMock(side_effect=mock_flush)

                # Create job
                created_job = await JobCRUD.create_job(mock_db_session, job_data)
                assert created_job.source_url == str(job_data.url)

                # Mock get_job for subsequent operations
                with patch.object(JobCRUD, "get_job", return_value=created_job):
                    # Update job
                    update_data = JobUpdate(priority=JobPriority.HIGH)
                    updated_job = await JobCRUD.update_job(
                        mock_db_session, created_job.id, update_data
                    )
                    assert updated_job is not None

                    # Delete job
                    deleted = await JobCRUD.delete_job(mock_db_session, created_job.id)
                    assert deleted is True
