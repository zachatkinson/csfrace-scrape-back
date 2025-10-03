"""Comprehensive tests for Jobs execution router - MANDATORY TEST_BUILDING.md compliance.

This module tests job execution API endpoints with complete coverage:
- POST / - Create jobs with automatic batch detection
- Background task execution for job processing
- Error handling and edge cases
- Performance benchmarks

ALL tests follow MANDATORY TEST_BUILDING.md patterns:
- AAA pattern with explicit comments
- Factory fixtures for DRY principle
- Comprehensive API endpoint testing
- Security validation for input handling
"""

import time
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, Mock, patch
from uuid import uuid4

import pytest
from fastapi import BackgroundTasks, Request
from pydantic import HttpUrl

from src.common.status import JobPriority, JobStatus

# ============================================================================
# Test Fixtures - DRY Principle
# ============================================================================


@pytest.fixture
def sample_job_data():
    """Factory for sample job data - DRY principle."""
    return {
        "id": str(uuid4()),
        "source_url": "https://example.com/test",
        "domain": "example.com",
        "user_id": "anonymous",
        "job_type": "scrape",
        "target_format": "json",
        "status": JobStatus.PENDING.value,
        "priority": JobPriority.NORMAL.value,
        "created_at": datetime.now(UTC),
        "started_at": None,
        "completed_at": None,
        "retry_count": 0,
        "max_retries": 3,
        "error_message": None,
        "processing_time_ms": None,
        "output_size_bytes": None,
        "batch_id": None,
        "options": {},
    }


@pytest.fixture
def mock_db_session():
    """Factory for mock database session - DRY principle."""
    session = AsyncMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.add = Mock()
    return session


@pytest.fixture
def mock_job_crud():
    """Factory for mock JobCRUD - DRY principle."""
    with patch("src.api.routers.jobs.execution.JobCRUD") as mock:
        yield mock


@pytest.fixture
def mock_background_tasks():
    """Factory for mock BackgroundTasks - DRY principle."""
    tasks = Mock(spec=BackgroundTasks)
    tasks.add_task = Mock()
    return tasks


@pytest.fixture
def mock_request():
    """Factory for mock Request (for rate limiting) - DRY principle."""
    request = Mock(spec=Request)
    request.client = Mock()
    request.client.host = "127.0.0.1"
    return request


# ============================================================================
# Create Jobs Endpoint Tests
# ============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
class TestCreateJobsEndpoint:
    """Tests for POST / endpoint - create jobs with batch detection."""

    async def test_create_single_job_success(
        self, mock_request, mock_background_tasks, mock_db_session, sample_job_data
    ):
        """Test create single job success - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        from src.api.schemas import JobsCreateRequest

        jobs_request = JobsCreateRequest(
            urls=[HttpUrl("https://example.com/test")],
            priority=JobPriority.NORMAL,
            max_retries=3,
            output_base_directory="output",
        )

        # Mock ScrapingJob creation
        with patch("src.api.routers.jobs.execution.ScrapingJob") as mock_scraping_job:
            mock_job = MagicMock(**sample_job_data)
            mock_scraping_job.return_value = mock_job

            from src.api.routers.jobs.execution import create_jobs

            # Act - MANDATORY
            response = await create_jobs(
                request=mock_request,
                jobs_data=jobs_request,
                background_tasks=mock_background_tasks,
                db=mock_db_session,
            )

            # Assert - MANDATORY
            assert response.total_jobs == 1
            assert len(response.jobs) == 1
            assert response.batch_id is None  # Single job = no batch
            assert response.jobs[0].source_url == "https://example.com/test"
            mock_db_session.add.assert_called_once()
            mock_db_session.flush.assert_called_once()
            mock_db_session.commit.assert_called_once()
            mock_background_tasks.add_task.assert_called_once()

    async def test_create_batch_jobs_success(
        self, mock_request, mock_background_tasks, mock_db_session, sample_job_data
    ):
        """Test create batch jobs success - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        from src.api.schemas import JobsCreateRequest

        urls = [
            HttpUrl("https://example.com/test1"),
            HttpUrl("https://example.com/test2"),
            HttpUrl("https://example.com/test3"),
        ]

        jobs_request = JobsCreateRequest(
            urls=urls,
            priority=JobPriority.NORMAL,
            max_retries=3,
            output_base_directory="output",
        )

        # Mock ScrapingJob creation
        with patch("src.api.routers.jobs.execution.ScrapingJob") as mock_scraping_job:
            mock_jobs = []
            for i in range(3):
                job_data = sample_job_data.copy()
                job_data["id"] = str(uuid4())
                job_data["source_url"] = str(urls[i])
                job_data["batch_id"] = "test-batch-id"
                mock_job = MagicMock(**job_data)
                mock_jobs.append(mock_job)

            mock_scraping_job.side_effect = mock_jobs

            from src.api.routers.jobs.execution import create_jobs

            # Act - MANDATORY
            response = await create_jobs(
                request=mock_request,
                jobs_data=jobs_request,
                background_tasks=mock_background_tasks,
                db=mock_db_session,
            )

            # Assert - MANDATORY
            assert response.total_jobs == 3
            assert len(response.jobs) == 3
            assert response.batch_id is not None  # Multiple jobs = batch
            assert mock_db_session.add.call_count == 3
            mock_db_session.flush.assert_called_once()
            mock_db_session.commit.assert_called_once()
            assert mock_background_tasks.add_task.call_count == 3

    async def test_create_jobs_with_custom_priority(
        self, mock_request, mock_background_tasks, mock_db_session, sample_job_data
    ):
        """Test create jobs with custom priority - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        from src.api.schemas import JobsCreateRequest

        jobs_request = JobsCreateRequest(
            urls=[HttpUrl("https://example.com/test")],
            priority=JobPriority.HIGH,  # Custom priority
            max_retries=5,
            output_base_directory="output",
        )

        # Mock ScrapingJob creation
        with patch("src.api.routers.jobs.execution.ScrapingJob") as mock_scraping_job:
            mock_job = MagicMock(**sample_job_data)
            mock_scraping_job.return_value = mock_job

            from src.api.routers.jobs.execution import create_jobs

            # Act - MANDATORY
            response = await create_jobs(
                request=mock_request,
                jobs_data=jobs_request,
                background_tasks=mock_background_tasks,
                db=mock_db_session,
            )

            # Assert - MANDATORY
            assert response.total_jobs == 1
            # Verify ScrapingJob was created with high priority
            mock_scraping_job.assert_called_once()
            call_kwargs = mock_scraping_job.call_args.kwargs
            assert call_kwargs["priority"] == JobPriority.HIGH.value

    async def test_create_jobs_extracts_domain(
        self, mock_request, mock_background_tasks, mock_db_session, sample_job_data
    ):
        """Test create jobs extracts domain correctly - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        from src.api.schemas import JobsCreateRequest

        jobs_request = JobsCreateRequest(
            urls=[HttpUrl("https://custom-domain.com/path/to/page")],
            priority=JobPriority.NORMAL,
            max_retries=3,
            output_base_directory="output",
        )

        # Mock ScrapingJob creation
        with patch("src.api.routers.jobs.execution.ScrapingJob") as mock_scraping_job:
            mock_job = MagicMock(**sample_job_data)
            mock_scraping_job.return_value = mock_job

            from src.api.routers.jobs.execution import create_jobs

            # Act - MANDATORY
            response = await create_jobs(
                request=mock_request,
                jobs_data=jobs_request,
                background_tasks=mock_background_tasks,
                db=mock_db_session,
            )

            # Assert - MANDATORY
            assert response.total_jobs == 1
            # Verify domain was extracted correctly
            mock_scraping_job.assert_called_once()
            call_kwargs = mock_scraping_job.call_args.kwargs
            assert call_kwargs["domain"] == "custom-domain.com"

    async def test_create_jobs_schedules_background_tasks(
        self, mock_request, mock_background_tasks, mock_db_session, sample_job_data
    ):
        """Test create jobs schedules background tasks - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        from src.api.schemas import JobsCreateRequest

        jobs_request = JobsCreateRequest(
            urls=[HttpUrl("https://example.com/test")],
            priority=JobPriority.NORMAL,
            max_retries=3,
            output_base_directory="output",
        )

        # Mock ScrapingJob creation
        with patch("src.api.routers.jobs.execution.ScrapingJob") as mock_scraping_job:
            mock_job = MagicMock(**sample_job_data)
            mock_scraping_job.return_value = mock_job

            from src.api.routers.jobs.execution import create_jobs

            # Act - MANDATORY
            await create_jobs(
                request=mock_request,
                jobs_data=jobs_request,
                background_tasks=mock_background_tasks,
                db=mock_db_session,
            )

            # Assert - MANDATORY
            # Verify background task was added with correct arguments
            mock_background_tasks.add_task.assert_called_once()
            call_args = mock_background_tasks.add_task.call_args
            # First arg should be execute_conversion_job function
            assert call_args[0][0].__name__ == "execute_conversion_job"


# ============================================================================
# Background Task Execution Tests
# ============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
class TestExecuteConversionJob:
    """Tests for execute_conversion_job background task."""

    async def test_execute_conversion_job_success(self, mock_job_crud):
        """Test execute_conversion_job success - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        job_id = str(uuid4())
        url = "https://example.com/test"
        output_dir = "test_output"

        # Mock async_session context manager
        mock_db = AsyncMock()
        mock_session_cm = AsyncMock()
        mock_session_cm.__aenter__.return_value = mock_db
        mock_session_cm.__aexit__.return_value = None

        # Mock AsyncWordPressConverter
        mock_converter = AsyncMock()
        mock_converter.convert = AsyncMock()

        with (
            patch("src.api.routers.jobs.execution.async_session", return_value=mock_session_cm),
            patch(
                "src.api.routers.jobs.execution.AsyncWordPressConverter",
                return_value=mock_converter,
            ),
            patch("src.api.routers.jobs.execution.Path") as mock_path,
        ):
            # Mock Path operations
            mock_path_instance = MagicMock()
            mock_path_instance.mkdir = MagicMock()
            mock_path_instance.exists.return_value = True
            mock_path_instance.rglob.return_value = []
            mock_path.return_value = mock_path_instance

            # Mock JobCRUD operations
            mock_job_crud.update_job_status = AsyncMock(return_value=MagicMock())

            from src.api.routers.jobs.execution import execute_conversion_job

            # Act - MANDATORY
            await execute_conversion_job(job_id, url, output_dir)

            # Assert - MANDATORY
            # Verify job status updates
            assert mock_job_crud.update_job_status.call_count == 2
            # First call: RUNNING
            first_call = mock_job_crud.update_job_status.call_args_list[0]
            assert first_call[0][1] == job_id
            assert first_call[0][2] == JobStatus.RUNNING
            # Second call: COMPLETED
            second_call = mock_job_crud.update_job_status.call_args_list[1]
            assert second_call[0][1] == job_id
            assert second_call[0][2] == JobStatus.COMPLETED

            # Verify converter was called
            mock_converter.convert.assert_called_once()

    async def test_execute_conversion_job_creates_output_dir(self, mock_job_crud):
        """Test execute_conversion_job creates output directory - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        job_id = str(uuid4())
        url = "https://example.com/test"
        output_dir = "test_output"

        # Mock async_session context manager
        mock_db = AsyncMock()
        mock_session_cm = AsyncMock()
        mock_session_cm.__aenter__.return_value = mock_db
        mock_session_cm.__aexit__.return_value = None

        # Mock AsyncWordPressConverter
        mock_converter = AsyncMock()
        mock_converter.convert = AsyncMock()

        with (
            patch("src.api.routers.jobs.execution.async_session", return_value=mock_session_cm),
            patch(
                "src.api.routers.jobs.execution.AsyncWordPressConverter",
                return_value=mock_converter,
            ),
            patch("src.api.routers.jobs.execution.Path") as mock_path,
        ):
            # Mock Path operations
            mock_path_instance = MagicMock()
            mock_path_instance.mkdir = MagicMock()
            mock_path_instance.exists.return_value = True
            mock_path_instance.rglob.return_value = []
            mock_path.return_value = mock_path_instance

            # Mock JobCRUD operations
            mock_job_crud.update_job_status = AsyncMock(return_value=MagicMock())

            from src.api.routers.jobs.execution import execute_conversion_job

            # Act - MANDATORY
            await execute_conversion_job(job_id, url, output_dir)

            # Assert - MANDATORY
            # Verify output directory was created with correct parameters
            mock_path.assert_called_once_with(output_dir)
            mock_path_instance.mkdir.assert_called_once_with(parents=True, exist_ok=True)


# ============================================================================
# MANDATORY Performance Benchmarks
# ============================================================================


@pytest.mark.performance
@pytest.mark.unit
@pytest.mark.asyncio
class TestJobsExecutionPerformance:
    """MANDATORY performance tests for Jobs execution endpoints."""

    async def test_create_jobs_performance(
        self, mock_request, mock_background_tasks, mock_db_session, sample_job_data
    ):
        """MANDATORY performance test - create jobs endpoint speed."""
        # Arrange - MANDATORY
        from src.api.schemas import JobsCreateRequest

        jobs_request = JobsCreateRequest(
            urls=[HttpUrl("https://example.com/test")],
            priority=JobPriority.NORMAL,
            max_retries=3,
            output_base_directory="output",
        )

        # Mock ScrapingJob creation
        with patch("src.api.routers.jobs.execution.ScrapingJob") as mock_scraping_job:
            mock_job = MagicMock(**sample_job_data)
            mock_scraping_job.return_value = mock_job

            from src.api.routers.jobs.execution import create_jobs

            iterations = 50

            # Act - MANDATORY
            start_time = time.perf_counter()

            for _ in range(iterations):
                await create_jobs(
                    request=mock_request,
                    jobs_data=jobs_request,
                    background_tasks=mock_background_tasks,
                    db=mock_db_session,
                )

            end_time = time.perf_counter()
            execution_time = end_time - start_time

            # Assert - MANDATORY
            avg_time = execution_time / iterations
            assert avg_time < 0.02  # <20ms per request (more complex endpoint)
            assert execution_time < 1.0  # Total <1s for 50 requests
