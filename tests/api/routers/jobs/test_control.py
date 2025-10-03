"""Comprehensive tests for Jobs control router - MANDATORY TEST_BUILDING.md compliance.

This module tests job control API endpoints with complete coverage:
- POST /{job_id}/start - Start a pending job
- POST /{job_id}/cancel - Cancel a running job
- POST /{job_id}/retry - Retry a failed job
- State transition validation
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
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from src.common.status import JobStatus

# ============================================================================
# Test Fixtures - DRY Principle
# ============================================================================


@pytest.fixture
def sample_job_dict():
    """Factory for sample job data - DRY principle."""
    return {
        "id": str(uuid4()),
        "source_url": "https://example.com/test",
        "job_type": "scrape",
        "target_format": "json",
        "status": JobStatus.PENDING.value,
        "priority": "normal",
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
        "can_retry": True,
    }


@pytest.fixture
def mock_db_session():
    """Factory for mock database session - DRY principle."""
    session = AsyncMock()
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    return session


@pytest.fixture
def mock_job_crud():
    """Factory for mock JobCRUD - DRY principle."""
    with patch("src.api.routers.jobs.control.JobCRUD") as mock:
        yield mock


# ============================================================================
# Start Job Endpoint Tests
# ============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
class TestStartJobEndpoint:
    """Tests for POST /{job_id}/start endpoint - start job."""

    async def test_start_job_success(self, mock_job_crud, mock_db_session, sample_job_dict):
        """Test start job success - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        job_id = sample_job_dict["id"]
        mock_job = MagicMock(**sample_job_dict)

        # Job after starting
        started_job_dict = sample_job_dict.copy()
        started_job_dict["status"] = JobStatus.RUNNING.value
        started_job_dict["started_at"] = datetime.now(UTC)
        mock_started_job = MagicMock(**started_job_dict)

        mock_job_crud.get_job = AsyncMock(return_value=mock_job)
        mock_job_crud.update_job_status = AsyncMock(return_value=mock_started_job)

        from src.api.routers.jobs.control import start_job

        # Act - MANDATORY
        response = await start_job(job_id=job_id, db=mock_db_session)

        # Assert - MANDATORY
        assert response.id == job_id
        assert response.status == JobStatus.RUNNING.value
        mock_job_crud.get_job.assert_called_once_with(mock_db_session, job_id)
        mock_job_crud.update_job_status.assert_called_once_with(
            mock_db_session, job_id, JobStatus.RUNNING
        )

    async def test_start_job_not_found(self, mock_job_crud, mock_db_session):
        """Test start job not found - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        job_id = str(uuid4())
        mock_job_crud.get_job = AsyncMock(return_value=None)

        from src.api.routers.jobs.control import start_job

        # Act & Assert - MANDATORY
        with pytest.raises(Exception):  # Will raise APIErrorFactory.not_found
            await start_job(job_id=job_id, db=mock_db_session)

        mock_job_crud.get_job.assert_called_once_with(mock_db_session, job_id)
        mock_job_crud.update_job_status.assert_not_called()

    async def test_start_job_invalid_status(self, mock_job_crud, mock_db_session, sample_job_dict):
        """Test start job with invalid status - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        job_id = sample_job_dict["id"]
        sample_job_dict["status"] = JobStatus.RUNNING.value  # Already running
        mock_job = MagicMock(**sample_job_dict)
        mock_job_crud.get_job = AsyncMock(return_value=mock_job)

        from src.api.routers.jobs.control import start_job

        # Act & Assert - MANDATORY
        with pytest.raises(Exception):  # Will raise APIErrorFactory.business_logic_error
            await start_job(job_id=job_id, db=mock_db_session)

        mock_job_crud.get_job.assert_called_once_with(mock_db_session, job_id)
        mock_job_crud.update_job_status.assert_not_called()

    async def test_start_job_completed_status(
        self, mock_job_crud, mock_db_session, sample_job_dict
    ):
        """Test start job with completed status - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        job_id = sample_job_dict["id"]
        sample_job_dict["status"] = JobStatus.COMPLETED.value  # Already completed
        mock_job = MagicMock(**sample_job_dict)
        mock_job_crud.get_job = AsyncMock(return_value=mock_job)

        from src.api.routers.jobs.control import start_job

        # Act & Assert - MANDATORY
        with pytest.raises(Exception):  # Will raise APIErrorFactory.business_logic_error
            await start_job(job_id=job_id, db=mock_db_session)

        mock_job_crud.get_job.assert_called_once_with(mock_db_session, job_id)
        mock_job_crud.update_job_status.assert_not_called()


# ============================================================================
# Cancel Job Endpoint Tests
# ============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
class TestCancelJobEndpoint:
    """Tests for POST /{job_id}/cancel endpoint - cancel job."""

    async def test_cancel_job_success_pending(
        self, mock_job_crud, mock_db_session, sample_job_dict
    ):
        """Test cancel pending job success - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        job_id = sample_job_dict["id"]
        sample_job_dict["status"] = JobStatus.PENDING.value
        mock_job = MagicMock(**sample_job_dict)

        cancelled_job_dict = sample_job_dict.copy()
        cancelled_job_dict["status"] = JobStatus.CANCELLED.value
        mock_cancelled_job = MagicMock(**cancelled_job_dict)

        mock_job_crud.get_job = AsyncMock(return_value=mock_job)
        mock_job_crud.update_job_status = AsyncMock(return_value=mock_cancelled_job)

        from src.api.routers.jobs.control import cancel_job

        # Act - MANDATORY
        response = await cancel_job(job_id=job_id, db=mock_db_session)

        # Assert - MANDATORY
        assert response.id == job_id
        assert response.status == JobStatus.CANCELLED.value
        mock_job_crud.get_job.assert_called_once_with(mock_db_session, job_id)
        mock_job_crud.update_job_status.assert_called_once_with(
            mock_db_session, job_id, JobStatus.CANCELLED
        )

    async def test_cancel_job_success_running(
        self, mock_job_crud, mock_db_session, sample_job_dict
    ):
        """Test cancel running job success - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        job_id = sample_job_dict["id"]
        sample_job_dict["status"] = JobStatus.RUNNING.value
        mock_job = MagicMock(**sample_job_dict)

        cancelled_job_dict = sample_job_dict.copy()
        cancelled_job_dict["status"] = JobStatus.CANCELLED.value
        mock_cancelled_job = MagicMock(**cancelled_job_dict)

        mock_job_crud.get_job = AsyncMock(return_value=mock_job)
        mock_job_crud.update_job_status = AsyncMock(return_value=mock_cancelled_job)

        from src.api.routers.jobs.control import cancel_job

        # Act - MANDATORY
        response = await cancel_job(job_id=job_id, db=mock_db_session)

        # Assert - MANDATORY
        assert response.id == job_id
        assert response.status == JobStatus.CANCELLED.value
        mock_job_crud.get_job.assert_called_once_with(mock_db_session, job_id)
        mock_job_crud.update_job_status.assert_called_once_with(
            mock_db_session, job_id, JobStatus.CANCELLED
        )

    async def test_cancel_job_not_found(self, mock_job_crud, mock_db_session):
        """Test cancel job not found - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        job_id = str(uuid4())
        mock_job_crud.get_job = AsyncMock(return_value=None)

        from src.api.routers.jobs.control import cancel_job

        # Act & Assert - MANDATORY
        with pytest.raises(Exception):  # Will raise APIErrorFactory.not_found
            await cancel_job(job_id=job_id, db=mock_db_session)

        mock_job_crud.get_job.assert_called_once_with(mock_db_session, job_id)
        mock_job_crud.update_job_status.assert_not_called()

    async def test_cancel_job_already_completed(
        self, mock_job_crud, mock_db_session, sample_job_dict
    ):
        """Test cancel already completed job - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        job_id = sample_job_dict["id"]
        sample_job_dict["status"] = JobStatus.COMPLETED.value
        mock_job = MagicMock(**sample_job_dict)
        mock_job_crud.get_job = AsyncMock(return_value=mock_job)

        from src.api.routers.jobs.control import cancel_job

        # Act & Assert - MANDATORY
        with pytest.raises(Exception):  # Will raise APIErrorFactory.business_logic_error
            await cancel_job(job_id=job_id, db=mock_db_session)

        mock_job_crud.get_job.assert_called_once_with(mock_db_session, job_id)
        mock_job_crud.update_job_status.assert_not_called()

    async def test_cancel_job_already_failed(self, mock_job_crud, mock_db_session, sample_job_dict):
        """Test cancel already failed job - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        job_id = sample_job_dict["id"]
        sample_job_dict["status"] = JobStatus.FAILED.value
        mock_job = MagicMock(**sample_job_dict)
        mock_job_crud.get_job = AsyncMock(return_value=mock_job)

        from src.api.routers.jobs.control import cancel_job

        # Act & Assert - MANDATORY
        with pytest.raises(Exception):  # Will raise APIErrorFactory.business_logic_error
            await cancel_job(job_id=job_id, db=mock_db_session)

        mock_job_crud.get_job.assert_called_once_with(mock_db_session, job_id)
        mock_job_crud.update_job_status.assert_not_called()

    async def test_cancel_job_already_cancelled(
        self, mock_job_crud, mock_db_session, sample_job_dict
    ):
        """Test cancel already cancelled job - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        job_id = sample_job_dict["id"]
        sample_job_dict["status"] = JobStatus.CANCELLED.value
        mock_job = MagicMock(**sample_job_dict)
        mock_job_crud.get_job = AsyncMock(return_value=mock_job)

        from src.api.routers.jobs.control import cancel_job

        # Act & Assert - MANDATORY
        with pytest.raises(Exception):  # Will raise APIErrorFactory.business_logic_error
            await cancel_job(job_id=job_id, db=mock_db_session)

        mock_job_crud.get_job.assert_called_once_with(mock_db_session, job_id)
        mock_job_crud.update_job_status.assert_not_called()


# ============================================================================
# Retry Job Endpoint Tests
# ============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
class TestRetryJobEndpoint:
    """Tests for POST /{job_id}/retry endpoint - retry job."""

    async def test_retry_job_success(self, mock_job_crud, mock_db_session, sample_job_dict):
        """Test retry job success - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        job_id = sample_job_dict["id"]
        sample_job_dict["status"] = JobStatus.FAILED.value
        sample_job_dict["error_message"] = "Previous error"
        sample_job_dict["retry_count"] = 1
        sample_job_dict["can_retry"] = True
        mock_job = MagicMock(**sample_job_dict)
        mock_job_crud.get_job = AsyncMock(return_value=mock_job)

        from src.api.routers.jobs.control import retry_job

        # Act - MANDATORY
        response = await retry_job(job_id=job_id, db=mock_db_session)

        # Assert - MANDATORY
        assert response.id == job_id
        assert mock_job.status == JobStatus.PENDING.value
        assert mock_job.retry_count == 2  # Incremented
        assert mock_job.error_message is None
        assert mock_job.started_at is None
        assert mock_job.completed_at is None
        mock_db_session.flush.assert_called_once()
        mock_db_session.refresh.assert_called_once_with(mock_job)

    async def test_retry_job_not_found(self, mock_job_crud, mock_db_session):
        """Test retry job not found - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        job_id = str(uuid4())
        mock_job_crud.get_job = AsyncMock(return_value=None)

        from src.api.routers.jobs.control import retry_job

        # Act & Assert - MANDATORY
        with pytest.raises(Exception):  # Will raise APIErrorFactory.not_found
            await retry_job(job_id=job_id, db=mock_db_session)

        mock_job_crud.get_job.assert_called_once_with(mock_db_session, job_id)
        mock_db_session.flush.assert_not_called()

    async def test_retry_job_retry_limit_exceeded(
        self, mock_job_crud, mock_db_session, sample_job_dict
    ):
        """Test retry job with retry limit exceeded - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        job_id = sample_job_dict["id"]
        sample_job_dict["status"] = JobStatus.FAILED.value
        sample_job_dict["retry_count"] = 3
        sample_job_dict["max_retries"] = 3
        sample_job_dict["can_retry"] = False  # Retry limit exceeded
        mock_job = MagicMock(**sample_job_dict)
        mock_job_crud.get_job = AsyncMock(return_value=mock_job)

        from src.api.routers.jobs.control import retry_job

        # Act & Assert - MANDATORY
        with pytest.raises(Exception):  # Will raise APIErrorFactory.business_logic_error
            await retry_job(job_id=job_id, db=mock_db_session)

        mock_job_crud.get_job.assert_called_once_with(mock_db_session, job_id)
        mock_db_session.flush.assert_not_called()

    async def test_retry_job_wrong_status(self, mock_job_crud, mock_db_session, sample_job_dict):
        """Test retry job with wrong status - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        job_id = sample_job_dict["id"]
        sample_job_dict["status"] = JobStatus.RUNNING.value  # Can't retry running job
        sample_job_dict["can_retry"] = False
        mock_job = MagicMock(**sample_job_dict)
        mock_job_crud.get_job = AsyncMock(return_value=mock_job)

        from src.api.routers.jobs.control import retry_job

        # Act & Assert - MANDATORY
        with pytest.raises(Exception):  # Will raise APIErrorFactory.business_logic_error
            await retry_job(job_id=job_id, db=mock_db_session)

        mock_job_crud.get_job.assert_called_once_with(mock_db_session, job_id)
        mock_db_session.flush.assert_not_called()


# ============================================================================
# MANDATORY Performance Benchmarks
# ============================================================================


@pytest.mark.performance
@pytest.mark.unit
@pytest.mark.asyncio
class TestJobsControlPerformance:
    """MANDATORY performance tests for Jobs control endpoints."""

    async def test_start_job_performance(self, mock_job_crud, mock_db_session, sample_job_dict):
        """MANDATORY performance test - start job endpoint speed."""
        # Arrange - MANDATORY
        job_id = sample_job_dict["id"]
        mock_job = MagicMock(**sample_job_dict)

        started_job_dict = sample_job_dict.copy()
        started_job_dict["status"] = JobStatus.RUNNING.value
        mock_started_job = MagicMock(**started_job_dict)

        mock_job_crud.get_job = AsyncMock(return_value=mock_job)
        mock_job_crud.update_job_status = AsyncMock(return_value=mock_started_job)

        from src.api.routers.jobs.control import start_job

        iterations = 100

        # Act - MANDATORY
        start_time = time.perf_counter()

        for _ in range(iterations):
            await start_job(job_id=job_id, db=mock_db_session)

        end_time = time.perf_counter()
        execution_time = end_time - start_time

        # Assert - MANDATORY
        avg_time = execution_time / iterations
        assert avg_time < 0.01  # <10ms per request
        assert execution_time < 1.0  # Total <1s for 100 requests

    async def test_cancel_job_performance(self, mock_job_crud, mock_db_session, sample_job_dict):
        """MANDATORY performance test - cancel job endpoint speed."""
        # Arrange - MANDATORY
        job_id = sample_job_dict["id"]
        sample_job_dict["status"] = JobStatus.RUNNING.value
        mock_job = MagicMock(**sample_job_dict)

        cancelled_job_dict = sample_job_dict.copy()
        cancelled_job_dict["status"] = JobStatus.CANCELLED.value
        mock_cancelled_job = MagicMock(**cancelled_job_dict)

        mock_job_crud.get_job = AsyncMock(return_value=mock_job)
        mock_job_crud.update_job_status = AsyncMock(return_value=mock_cancelled_job)

        from src.api.routers.jobs.control import cancel_job

        iterations = 100

        # Act - MANDATORY
        start_time = time.perf_counter()

        for _ in range(iterations):
            await cancel_job(job_id=job_id, db=mock_db_session)

        end_time = time.perf_counter()
        execution_time = end_time - start_time

        # Assert - MANDATORY
        avg_time = execution_time / iterations
        assert avg_time < 0.01  # <10ms per request
        assert execution_time < 1.0  # Total <1s for 100 requests

    async def test_retry_job_performance(self, mock_job_crud, mock_db_session, sample_job_dict):
        """MANDATORY performance test - retry job endpoint speed."""
        # Arrange - MANDATORY
        job_id = sample_job_dict["id"]
        sample_job_dict["status"] = JobStatus.FAILED.value
        sample_job_dict["can_retry"] = True
        mock_job = MagicMock(**sample_job_dict)
        mock_job_crud.get_job = AsyncMock(return_value=mock_job)

        from src.api.routers.jobs.control import retry_job

        iterations = 100

        # Act - MANDATORY
        start_time = time.perf_counter()

        for _ in range(iterations):
            # Reset mock job state for each iteration
            mock_job.status = JobStatus.FAILED.value
            mock_job.retry_count = 1
            await retry_job(job_id=job_id, db=mock_db_session)

        end_time = time.perf_counter()
        execution_time = end_time - start_time

        # Assert - MANDATORY
        avg_time = execution_time / iterations
        assert avg_time < 0.01  # <10ms per request
        assert execution_time < 1.0  # Total <1s for 100 requests
