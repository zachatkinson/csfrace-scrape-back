"""Unit tests for jobs router endpoints."""

from datetime import UTC
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException, Request, status
from sqlalchemy.exc import SQLAlchemyError

from src.api.routers.jobs import (
    cancel_job,
    create_jobs,
    delete_job,
    get_job,
    list_jobs,
    retry_job,
    start_job,
    update_job,
)
from src.api.schemas import JobCreate, JobListResponse, JobResponse, JobUpdate
from src.database.models import JobPriority, JobStatus, ScrapingJob


class TestJobRouterEndpoints:
    """Test job router endpoint functions."""

    @pytest.fixture
    def mock_db_session(self):
        """Mock database session."""
        return AsyncMock()

    @pytest.fixture
    def job_create_data(self):
        """Sample job creation data."""
        return JobCreate(
            url="https://example.com/test-page",
            priority=JobPriority.HIGH.value,
            custom_slug="test-slug",
        )

    @pytest.fixture
    def job_update_data(self):
        """Sample job update data."""
        return JobUpdate(priority=JobPriority.LOW.value, max_retries=5)

    @pytest.fixture
    def sample_job(self):
        """Sample ScrapingJob instance."""
        from datetime import datetime

        return ScrapingJob(
            id="test-job-id-123",  # String UUID instead of integer
            source_url="https://example.com/test",  # Required field
            domain="example.com",
            slug="test",
            status=JobStatus.PENDING.value,  # Use string value
            priority=JobPriority.NORMAL.value,  # Use string value
            output_directory="converted_content/test",
            max_retries=3,
            retry_count=0,
            # Remove fields that don't exist in the model:
            # timeout_seconds=30,  # Not a model field
            # skip_existing=False,  # Not a model field
            success=False,
            images_downloaded=0,
            created_at=datetime.now(UTC),
        )

    @pytest.mark.asyncio
    async def test_create_job_success(self, mock_db_session, job_create_data, sample_job):
        """Test successful job creation."""
        with patch(
            "src.api.routers.jobs.JobCRUD.create_job", return_value=sample_job
        ) as mock_create:
            mock_background_tasks = MagicMock()
            mock_request = MagicMock(spec=Request)
            mock_request.client.host = "127.0.0.1"
            result = await create_job(
                mock_request, job_create_data, mock_background_tasks, mock_db_session
            )

            assert isinstance(result, JobResponse)
            assert result.id == sample_job.id
            assert result.url == sample_job.source_url
            assert result.domain == sample_job.domain

            mock_create.assert_called_once_with(mock_db_session, job_create_data)

    @pytest.mark.asyncio
    async def test_create_job_database_error(self, mock_db_session, job_create_data):
        """Test job creation with database error."""
        with patch("src.api.routers.jobs.JobCRUD.create_job") as mock_create:
            mock_create.side_effect = SQLAlchemyError("Database error")

            mock_background_tasks = MagicMock()
            mock_request = MagicMock(spec=Request)
            mock_request.client.host = "127.0.0.1"
            with pytest.raises(HTTPException) as exc_info:
                await create_job(
                    mock_request, job_create_data, mock_background_tasks, mock_db_session
                )

            assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
            assert "Database operation failed" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_list_jobs_success(self, mock_db_session):
        """Test successful job listing."""
        from datetime import datetime

        jobs = [
            ScrapingJob(
                id="test-job-1",  # String UUID instead of integer
                source_url="https://test1.com",  # Required field
                domain="test1.com",
                slug="test1",
                status=JobStatus.PENDING.value,  # Use string value
                priority=JobPriority.NORMAL.value,  # Use string value
                created_at=datetime.now(UTC),
                retry_count=0,
                max_retries=3,
                # timeout_seconds=30,  # Field not in model
                output_directory="converted_content/test1",
                # skip_existing=False,  # Field not in model
                success=False,
                images_downloaded=0,
            ),
            ScrapingJob(
                id="test-job-2",  # String UUID instead of integer
                source_url="https://test2.com",  # Required field
                domain="test2.com",
                slug="test2",
                status=JobStatus.PENDING.value,  # Use string value
                priority=JobPriority.NORMAL.value,  # Use string value
                created_at=datetime.now(UTC),
                retry_count=0,
                max_retries=3,
                # timeout_seconds=30,  # Field not in model
                output_directory="converted_content/test2",
                # skip_existing=False,  # Field not in model
                success=False,
                images_downloaded=0,
            ),
        ]

        with patch(
            "src.api.routers.jobs.JobCRUD.get_jobs", return_value=(jobs, 2)
        ) as mock_get_jobs:
            result = await list_jobs(
                mock_db_session,
                page=1,
                page_size=10,
                status_filter=JobStatus.PENDING,
                domain="test.com",
            )

            assert isinstance(result, JobListResponse)
            assert len(result.jobs) == 2
            assert result.total == 2
            assert result.page == 1
            assert result.page_size == 10
            assert result.total_pages == 1

            mock_get_jobs.assert_called_once_with(
                mock_db_session, skip=0, limit=10, status=JobStatus.PENDING, domain="test.com"
            )

    @pytest.mark.asyncio
    async def test_list_jobs_pagination_calculation(self, mock_db_session):
        """Test pagination calculation in job listing."""
        from datetime import datetime

        jobs = [
            ScrapingJob(
                id="test-pagination-job",  # String UUID instead of integer
                source_url="https://test.com",  # Required field
                domain="test.com",
                slug="test",
                status=JobStatus.PENDING.value,  # Use string value
                priority=JobPriority.NORMAL.value,  # Use string value
                created_at=datetime.now(UTC),
                retry_count=0,
                max_retries=3,
                # timeout_seconds=30,  # Field not in model
                output_directory="converted_content/test",
                # skip_existing=False,  # Field not in model
                success=False,
                images_downloaded=0,
            )
        ]

        with patch("src.api.routers.jobs.JobCRUD.get_jobs", return_value=(jobs, 25)):
            result = await list_jobs(mock_db_session, page=2, page_size=10)

            assert result.page == 2
            assert result.page_size == 10
            assert result.total == 25
            assert result.total_pages == 3  # ceil(25/10) = 3

    @pytest.mark.asyncio
    async def test_list_jobs_database_error(self, mock_db_session):
        """Test job listing with database error."""
        with patch("src.api.routers.jobs.JobCRUD.get_jobs") as mock_get_jobs:
            mock_get_jobs.side_effect = SQLAlchemyError("Database error")

            with pytest.raises(HTTPException) as exc_info:
                await list_jobs(mock_db_session, page=1, page_size=50)

            assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
            assert "Database operation failed" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_get_job_success(self, mock_db_session, sample_job):
        """Test successful job retrieval."""
        with patch("src.api.routers.jobs.JobCRUD.get_job", return_value=sample_job) as mock_get:
            result = await get_job("test-job-id-123", mock_db_session)

            assert isinstance(result, JobResponse)
            assert result.id == sample_job.id
            assert result.url == sample_job.source_url

            mock_get.assert_called_once_with(mock_db_session, "test-job-id-123")

    @pytest.mark.asyncio
    async def test_get_job_not_found(self, mock_db_session):
        """Test job retrieval when job doesn't exist."""
        with patch("src.api.routers.jobs.JobCRUD.get_job", return_value=None):
            with pytest.raises(HTTPException) as exc_info:
                await get_job("nonexistent-job-id", mock_db_session)

            assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
            assert "not found" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_get_job_database_error(self, mock_db_session):
        """Test job retrieval with database error."""
        with patch("src.api.routers.jobs.JobCRUD.get_job") as mock_get:
            mock_get.side_effect = SQLAlchemyError("Database error")

            with pytest.raises(HTTPException) as exc_info:
                await get_job("test-job-id", mock_db_session)

            assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
            assert "Database operation failed" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_update_job_success(self, mock_db_session, sample_job, job_update_data):
        """Test successful job update."""
        with patch(
            "src.api.routers.jobs.JobCRUD.update_job", return_value=sample_job
        ) as mock_update:
            result = await update_job("test-job-id-123", job_update_data, mock_db_session)

            assert isinstance(result, JobResponse)
            assert result.id == sample_job.id

            mock_update.assert_called_once_with(mock_db_session, "test-job-id-123", job_update_data)

    @pytest.mark.asyncio
    async def test_update_job_not_found(self, mock_db_session, job_update_data):
        """Test job update when job doesn't exist."""
        with patch("src.api.routers.jobs.JobCRUD.update_job", return_value=None):
            with pytest.raises(HTTPException) as exc_info:
                await update_job("nonexistent-job-id", job_update_data, mock_db_session)

            assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
            assert "not found" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_update_job_database_error(self, mock_db_session, job_update_data):
        """Test job update with database error."""
        with patch("src.api.routers.jobs.JobCRUD.update_job") as mock_update:
            mock_update.side_effect = SQLAlchemyError("Database error")

            with pytest.raises(HTTPException) as exc_info:
                await update_job("test-job-id", job_update_data, mock_db_session)

            assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
            assert "Database operation failed" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_delete_job_success(self, mock_db_session):
        """Test successful job deletion."""
        with patch("src.api.routers.jobs.JobCRUD.delete_job", return_value=True) as mock_delete:
            result = await delete_job("test-job-id-123", mock_db_session)

            assert result is None  # Endpoint returns None on success
            mock_delete.assert_called_once_with(mock_db_session, "test-job-id-123")

    @pytest.mark.asyncio
    async def test_delete_job_not_found(self, mock_db_session):
        """Test job deletion when job doesn't exist."""
        with patch("src.api.routers.jobs.JobCRUD.delete_job", return_value=False):
            with pytest.raises(HTTPException) as exc_info:
                await delete_job("nonexistent-job-id", mock_db_session)

            assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
            assert "not found" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_delete_job_database_error(self, mock_db_session):
        """Test job deletion with database error."""
        with patch("src.api.routers.jobs.JobCRUD.delete_job") as mock_delete:
            mock_delete.side_effect = SQLAlchemyError("Database error")

            with pytest.raises(HTTPException) as exc_info:
                await delete_job("test-job-id", mock_db_session)

            assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
            assert "Database operation failed" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_start_job_success(self, mock_db_session, sample_job):
        """Test successful job start."""
        sample_job.status = JobStatus.PENDING.value
        # Create a copy of the job with updated status
        updated_job = ScrapingJob(
            id=sample_job.id,
            source_url=sample_job.source_url,  # Required field
            domain=sample_job.domain,
            slug=sample_job.slug,
            status=JobStatus.RUNNING.value,  # Updated status
            priority=sample_job.priority,
            created_at=sample_job.created_at,
            retry_count=sample_job.retry_count,
            max_retries=sample_job.max_retries,
            # timeout_seconds=30,  # Field not in sample_job
            output_directory=sample_job.output_directory,
            # skip_existing=False,  # Field not in sample_job
            success=sample_job.success,
            images_downloaded=sample_job.images_downloaded,
        )

        with patch("src.api.routers.jobs.JobCRUD.get_job", return_value=sample_job):
            with patch(
                "src.api.routers.jobs.JobCRUD.update_job_status", return_value=updated_job
            ) as mock_update:
                result = await start_job("test-job-id", mock_db_session)

                assert isinstance(result, JobResponse)
                assert result.status == JobStatus.RUNNING.value

                mock_update.assert_called_once_with(
                    mock_db_session, "test-job-id", JobStatus.RUNNING
                )

    @pytest.mark.asyncio
    async def test_start_job_not_found(self, mock_db_session):
        """Test starting non-existent job."""
        with patch("src.api.routers.jobs.JobCRUD.get_job", return_value=None):
            with pytest.raises(HTTPException) as exc_info:
                await start_job("nonexistent-job-id", mock_db_session)

            assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
            assert "not found" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_start_job_invalid_status(self, mock_db_session, sample_job):
        """Test starting job with invalid status."""
        sample_job.status = JobStatus.RUNNING.value  # Already running

        with patch("src.api.routers.jobs.JobCRUD.get_job", return_value=sample_job):
            with pytest.raises(HTTPException) as exc_info:
                await start_job("test-job-id", mock_db_session)

            assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
            assert "cannot be started" in str(exc_info.value.detail)
            assert "running" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_start_job_database_error(self, mock_db_session, sample_job):
        """Test starting job with database error."""
        with patch("src.api.routers.jobs.JobCRUD.get_job", return_value=sample_job):
            with patch("src.api.routers.jobs.JobCRUD.update_job_status") as mock_update:
                mock_update.side_effect = SQLAlchemyError("Database error")

                with pytest.raises(HTTPException) as exc_info:
                    await start_job("test-job-id", mock_db_session)

                assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
                assert "Database operation failed" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_cancel_job_success(self, mock_db_session, sample_job):
        """Test successful job cancellation."""
        sample_job.status = JobStatus.PENDING.value
        # Create a copy of the job with updated status
        updated_job = ScrapingJob(
            id=sample_job.id,
            source_url=sample_job.source_url,  # Required field
            domain=sample_job.domain,
            slug=sample_job.slug,
            status=JobStatus.CANCELLED.value,  # Updated status
            priority=sample_job.priority,
            created_at=sample_job.created_at,
            retry_count=sample_job.retry_count,
            max_retries=sample_job.max_retries,
            # timeout_seconds=30,  # Field not in sample_job
            output_directory=sample_job.output_directory,
            # skip_existing=False,  # Field not in sample_job
            success=sample_job.success,
            images_downloaded=sample_job.images_downloaded,
        )

        with patch("src.api.routers.jobs.JobCRUD.get_job", return_value=sample_job):
            with patch(
                "src.api.routers.jobs.JobCRUD.update_job_status", return_value=updated_job
            ) as mock_update:
                result = await cancel_job("test-job-id", mock_db_session)

                assert isinstance(result, JobResponse)
                assert result.status == JobStatus.CANCELLED.value

                mock_update.assert_called_once_with(
                    mock_db_session, "test-job-id", JobStatus.CANCELLED
                )

    @pytest.mark.asyncio
    async def test_cancel_job_not_found(self, mock_db_session):
        """Test cancelling non-existent job."""
        with patch("src.api.routers.jobs.JobCRUD.get_job", return_value=None):
            with pytest.raises(HTTPException) as exc_info:
                await cancel_job("nonexistent-job-id", mock_db_session)

            assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_cancel_job_invalid_status_completed(self, mock_db_session, sample_job):
        """Test cancelling completed job."""
        sample_job.status = JobStatus.COMPLETED.value

        with patch("src.api.routers.jobs.JobCRUD.get_job", return_value=sample_job):
            with pytest.raises(HTTPException) as exc_info:
                await cancel_job("test-job-id", mock_db_session)

            assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
            assert "cannot be cancelled" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_cancel_job_invalid_status_failed(self, mock_db_session, sample_job):
        """Test cancelling failed job."""
        sample_job.status = JobStatus.FAILED.value

        with patch("src.api.routers.jobs.JobCRUD.get_job", return_value=sample_job):
            with pytest.raises(HTTPException) as exc_info:
                await cancel_job("test-job-id", mock_db_session)

            assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
            assert "cannot be cancelled" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_cancel_job_invalid_status_cancelled(self, mock_db_session, sample_job):
        """Test cancelling already cancelled job."""
        sample_job.status = JobStatus.CANCELLED.value

        with patch("src.api.routers.jobs.JobCRUD.get_job", return_value=sample_job):
            with pytest.raises(HTTPException) as exc_info:
                await cancel_job("test-job-id", mock_db_session)

            assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
            assert "cannot be cancelled" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_retry_job_success(self, mock_db_session, sample_job):
        """Test successful job retry."""
        # Setup job that can be retried
        sample_job.status = JobStatus.FAILED.value
        sample_job.retry_count = 1
        sample_job.max_retries = 3
        # can_retry is computed from status and retry counts

        with patch("src.api.routers.jobs.JobCRUD.get_job", return_value=sample_job):
            mock_db_session.flush = AsyncMock()
            mock_db_session.refresh = AsyncMock()

            result = await retry_job("test-job-id", mock_db_session)

            assert isinstance(result, JobResponse)
            assert sample_job.status == JobStatus.PENDING.value
            assert sample_job.retry_count == 2
            assert sample_job.error_message is None
            assert sample_job.error_type is None
            assert sample_job.started_at is None
            assert sample_job.completed_at is None

    @pytest.mark.asyncio
    async def test_retry_job_not_found(self, mock_db_session):
        """Test retrying non-existent job."""
        with patch("src.api.routers.jobs.JobCRUD.get_job", return_value=None):
            with pytest.raises(HTTPException) as exc_info:
                await retry_job("nonexistent-job-id", mock_db_session)

            assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_retry_job_cannot_retry(self, mock_db_session, sample_job):
        """Test retrying job that cannot be retried."""
        # Set up job that cannot be retried (retry_count >= max_retries)
        sample_job.retry_count = 3
        sample_job.max_retries = 3
        sample_job.status = JobStatus.FAILED.value

        with patch("src.api.routers.jobs.JobCRUD.get_job", return_value=sample_job):
            with pytest.raises(HTTPException) as exc_info:
                await retry_job("test-job-id", mock_db_session)

            assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
            assert "cannot be retried" in str(exc_info.value.detail)
            assert "retries: 3/3" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_retry_job_database_error(self, mock_db_session, sample_job):
        """Test retrying job with database error."""
        # Set up job that can be retried
        sample_job.status = JobStatus.FAILED.value
        sample_job.retry_count = 1
        sample_job.max_retries = 3

        with patch("src.api.routers.jobs.JobCRUD.get_job", return_value=sample_job):
            mock_db_session.flush.side_effect = SQLAlchemyError("Database error")

            with pytest.raises(HTTPException) as exc_info:
                await retry_job("test-job-id", mock_db_session)

            assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
            assert "Database operation failed" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_list_jobs_skip_calculation(self, mock_db_session):
        """Test skip calculation for different pages."""
        with patch("src.api.routers.jobs.JobCRUD.get_jobs", return_value=([], 0)) as mock_get_jobs:
            # Test page 3 with page_size 20
            await list_jobs(mock_db_session, page=3, page_size=20, status_filter=None, domain=None)

            # skip should be (3-1) * 20 = 40
            mock_get_jobs.assert_called_once_with(
                mock_db_session, skip=40, limit=20, status=None, domain=None
            )

    @pytest.mark.asyncio
    async def test_start_job_status_validation_scenarios(self, mock_db_session):
        """Test start job status validation for different statuses."""
        invalid_statuses = [
            JobStatus.RUNNING.value,
            JobStatus.COMPLETED.value,
            JobStatus.FAILED.value,
            JobStatus.CANCELLED.value,
        ]

        for invalid_status in invalid_statuses:
            job = ScrapingJob(
                id="test-job-status-validation",  # String UUID instead of integer
                source_url="https://test.com",  # Required field
                domain="test.com",
                slug="test",
                status=invalid_status,  # Already using .value
            )

            with patch("src.api.routers.jobs.JobCRUD.get_job", return_value=job):
                with pytest.raises(HTTPException) as exc_info:
                    await start_job("test-job-id", mock_db_session)

                assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
                assert invalid_status in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_cancel_job_valid_statuses(self, mock_db_session):
        """Test that jobs in valid statuses can be cancelled."""
        from datetime import datetime

        valid_statuses = [JobStatus.PENDING.value, JobStatus.RUNNING.value]

        for valid_status in valid_statuses:
            job = ScrapingJob(
                id="test-job-valid-status",  # String UUID instead of integer
                source_url="https://test.com",  # Required field
                domain="test.com",
                slug="test",
                status=valid_status,  # Already using .value
                priority=JobPriority.NORMAL.value,  # Use string value
                created_at=datetime.now(UTC),
                retry_count=0,
                max_retries=3,
                # timeout_seconds=30,  # Field not in model
                output_directory="converted_content/test",
                # skip_existing=False,  # Field not in model
                success=False,
                images_downloaded=0,
            )

            with patch("src.api.routers.jobs.JobCRUD.get_job", return_value=job):
                with patch("src.api.routers.jobs.JobCRUD.update_job_status", return_value=job):
                    result = await cancel_job("test-job-id", mock_db_session)

                    assert isinstance(result, JobResponse)

    @pytest.mark.asyncio
    async def test_job_response_validation(self, mock_db_session, sample_job):
        """Test that JobResponse validation works correctly."""
        with patch("src.api.routers.jobs.JobCRUD.get_job", return_value=sample_job):
            result = await get_job("test-job-id", mock_db_session)

            # Verify all required fields are present
            assert hasattr(result, "id")
            assert hasattr(result, "url")
            assert hasattr(result, "domain")
            assert hasattr(result, "status")
            assert hasattr(result, "priority")
            assert hasattr(result, "created_at")

    @pytest.mark.asyncio
    async def test_job_list_response_validation(self, mock_db_session):
        """Test that JobListResponse validation works correctly."""
        from datetime import datetime

        jobs = [
            ScrapingJob(
                id="test-job-1",
                source_url="https://test.com",  # Required field
                domain="test.com",
                slug="test",
                status=JobStatus.PENDING.value,
                priority=JobPriority.NORMAL.value,
                created_at=datetime.now(UTC),
                retry_count=0,
                max_retries=3,
                # timeout_seconds=30,  # Field not in model
                output_directory="converted_content/test",
                # skip_existing=False,  # Field not in model
                success=False,
                images_downloaded=0,
            )
        ]

        with patch("src.api.routers.jobs.JobCRUD.get_jobs", return_value=(jobs, 1)):
            result = await list_jobs(mock_db_session, page=1, page_size=50)

            # Verify pagination fields
            assert isinstance(result.jobs, list)
            assert isinstance(result.total, int)
            assert isinstance(result.page, int)
            assert isinstance(result.page_size, int)
            assert isinstance(result.total_pages, int)
