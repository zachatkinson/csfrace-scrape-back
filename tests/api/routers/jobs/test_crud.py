"""Comprehensive tests for Jobs CRUD router - MANDATORY TEST_BUILDING.md compliance.

This module tests job CRUD API endpoints with complete coverage:
- GET / - List jobs with pagination and filters
- GET /{job_id} - Get single job
- PUT /{job_id} - Update job
- DELETE /{job_id} - Delete job
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
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from src.common.status import JobStatus

# ============================================================================
# Test Fixtures - DRY Principle
# ============================================================================


@pytest.fixture
def sample_job_dict() -> dict[str, Any]:
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
    }


@pytest.fixture
def sample_job_list(sample_job_dict: dict[str, Any]) -> list[dict[str, Any]]:
    """Factory for list of sample jobs - DRY principle."""
    jobs: list[dict[str, Any]] = []
    for i in range(5):
        job = sample_job_dict.copy()
        job["id"] = str(uuid4())
        job["source_url"] = f"https://example.com/test{i}"
        jobs.append(job)
    return jobs


@pytest.fixture
def mock_db_session() -> AsyncMock:
    """Factory for mock database session - DRY principle."""
    return AsyncMock()


@pytest.fixture
def mock_job_crud() -> Any:
    """Factory for mock JobCRUD - DRY principle."""
    with patch("src.api.routers.jobs.crud.JobCRUD") as mock:
        yield mock


# ============================================================================
# List Jobs Endpoint Tests
# ============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
class TestListJobsEndpoint:
    """Tests for GET / endpoint - list jobs with pagination."""

    async def test_list_jobs_default_pagination(
        self, mock_job_crud: Any, mock_db_session: AsyncMock, sample_job_list: list[dict[str, Any]]
    ) -> None:
        """Test list jobs with default pagination - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        mock_job_crud.get_jobs = AsyncMock(return_value=(sample_job_list, len(sample_job_list)))

        from src.api.routers.jobs.crud import list_jobs

        # Act - MANDATORY
        response = await list_jobs(
            db=mock_db_session,
            page=1,
            page_size=50,
            status_filter=None,
            domain=None,
        )

        # Assert - MANDATORY
        assert response.jobs is not None
        assert len(response.jobs) == len(sample_job_list)
        assert response.total == len(sample_job_list)
        assert response.page == 1
        assert response.page_size == 50
        mock_job_crud.get_jobs.assert_called_once_with(
            mock_db_session, skip=0, limit=50, status=None, domain=None
        )

    async def test_list_jobs_custom_pagination(
        self, mock_job_crud: Any, mock_db_session: AsyncMock, sample_job_list: list[dict[str, Any]]
    ) -> None:
        """Test list jobs with custom pagination - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        page = 2
        page_size = 2
        mock_job_crud.get_jobs = AsyncMock(return_value=(sample_job_list[:2], len(sample_job_list)))

        from src.api.routers.jobs.crud import list_jobs

        # Act - MANDATORY
        response = await list_jobs(
            db=mock_db_session,
            page=page,
            page_size=page_size,
            status_filter=None,
            domain=None,
        )

        # Assert - MANDATORY
        assert response.page == page
        assert response.page_size == page_size
        assert response.total == len(sample_job_list)
        # skip = (page - 1) * page_size = (2-1) * 2 = 2
        mock_job_crud.get_jobs.assert_called_once_with(
            mock_db_session, skip=2, limit=2, status=None, domain=None
        )

    async def test_list_jobs_with_status_filter(
        self, mock_job_crud: Any, mock_db_session: AsyncMock, sample_job_list: list[dict[str, Any]]
    ) -> None:
        """Test list jobs with status filter - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        status_filter = JobStatus.COMPLETED
        filtered_jobs = [j for j in sample_job_list if j["status"] == status_filter.value]
        mock_job_crud.get_jobs = AsyncMock(return_value=(filtered_jobs, len(filtered_jobs)))

        from src.api.routers.jobs.crud import list_jobs

        # Act - MANDATORY
        response = await list_jobs(
            db=mock_db_session,
            page=1,
            page_size=50,
            status_filter=status_filter,
            domain=None,
        )

        # Assert - MANDATORY
        mock_job_crud.get_jobs.assert_called_once_with(
            mock_db_session, skip=0, limit=50, status=status_filter, domain=None
        )

    async def test_list_jobs_with_domain_filter(
        self, mock_job_crud: Any, mock_db_session: AsyncMock, sample_job_list: list[dict[str, Any]]
    ) -> None:
        """Test list jobs with domain filter - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        domain = "example.com"
        mock_job_crud.get_jobs = AsyncMock(return_value=(sample_job_list, len(sample_job_list)))

        from src.api.routers.jobs.crud import list_jobs

        # Act - MANDATORY
        response = await list_jobs(
            db=mock_db_session,
            page=1,
            page_size=50,
            status_filter=None,
            domain=domain,
        )

        # Assert - MANDATORY
        mock_job_crud.get_jobs.assert_called_once_with(
            mock_db_session, skip=0, limit=50, status=None, domain=domain
        )

    async def test_list_jobs_empty_result(
        self, mock_job_crud: Any, mock_db_session: AsyncMock
    ) -> None:
        """Test list jobs with no results - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        mock_job_crud.get_jobs = AsyncMock(return_value=([], 0))

        from src.api.routers.jobs.crud import list_jobs

        # Act - MANDATORY
        response = await list_jobs(
            db=mock_db_session,
            page=1,
            page_size=50,
            status_filter=None,
            domain=None,
        )

        # Assert - MANDATORY
        assert len(response.jobs) == 0
        assert response.total == 0


# ============================================================================
# Get Job Endpoint Tests
# ============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
class TestGetJobEndpoint:
    """Tests for GET /{job_id} endpoint - get single job."""

    async def test_get_job_success(
        self, mock_job_crud: Any, mock_db_session: AsyncMock, sample_job_dict: dict[str, Any]
    ) -> None:
        """Test get job success - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        job_id = sample_job_dict["id"]
        mock_job = MagicMock(**sample_job_dict)
        mock_job_crud.get_job = AsyncMock(return_value=mock_job)

        from src.api.routers.jobs.crud import get_job

        # Act - MANDATORY
        response = await get_job(job_id=job_id, db=mock_db_session)

        # Assert - MANDATORY
        assert response.id == job_id
        assert response.source_url == sample_job_dict["source_url"]
        mock_job_crud.get_job.assert_called_once_with(mock_db_session, job_id)

    async def test_get_job_not_found(self, mock_job_crud: Any, mock_db_session: AsyncMock) -> None:
        """Test get job not found - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        job_id = str(uuid4())
        mock_job_crud.get_job = AsyncMock(return_value=None)

        from src.api.routers.jobs.crud import get_job

        # Act & Assert - MANDATORY
        with pytest.raises(Exception):  # Will raise APIErrorFactory.not_found
            await get_job(job_id=job_id, db=mock_db_session)

        mock_job_crud.get_job.assert_called_once_with(mock_db_session, job_id)


# ============================================================================
# Update Job Endpoint Tests
# ============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
class TestUpdateJobEndpoint:
    """Tests for PUT /{job_id} endpoint - update job."""

    async def test_update_job_success(
        self, mock_job_crud: Any, mock_db_session: AsyncMock, sample_job_dict: dict[str, Any]
    ) -> None:
        """Test update job success - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        job_id = sample_job_dict["id"]
        updated_job_dict = sample_job_dict.copy()
        updated_job_dict["status"] = JobStatus.RUNNING.value
        mock_job = MagicMock(**updated_job_dict)
        mock_job_crud.update_job = AsyncMock(return_value=mock_job)

        from src.api.routers.jobs.crud import update_job
        from src.api.schemas import JobUpdate

        job_update = JobUpdate(status=JobStatus.RUNNING.value)

        # Act - MANDATORY
        response = await update_job(job_id=job_id, job_data=job_update, db=mock_db_session)

        # Assert - MANDATORY
        assert response.id == job_id
        assert response.status == JobStatus.RUNNING.value
        mock_job_crud.update_job.assert_called_once_with(mock_db_session, job_id, job_update)

    async def test_update_job_not_found(
        self, mock_job_crud: Any, mock_db_session: AsyncMock
    ) -> None:
        """Test update job not found - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        job_id = str(uuid4())
        mock_job_crud.update_job = AsyncMock(return_value=None)

        from src.api.routers.jobs.crud import update_job
        from src.api.schemas import JobUpdate

        job_update = JobUpdate(status=JobStatus.COMPLETED.value)

        # Act & Assert - MANDATORY
        with pytest.raises(Exception):  # Will raise APIErrorFactory.not_found
            await update_job(job_id=job_id, job_data=job_update, db=mock_db_session)

        mock_job_crud.update_job.assert_called_once_with(mock_db_session, job_id, job_update)


# ============================================================================
# Delete Job Endpoint Tests
# ============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
class TestDeleteJobEndpoint:
    """Tests for DELETE /{job_id} endpoint - delete job."""

    async def test_delete_job_success(self, mock_job_crud: Any, mock_db_session: AsyncMock) -> None:
        """Test delete job success - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        job_id = str(uuid4())
        mock_job_crud.delete_job = AsyncMock(return_value=True)

        from src.api.routers.jobs.crud import delete_job

        # Act - MANDATORY
        await delete_job(job_id=job_id, db=mock_db_session)

        # Assert - MANDATORY
        mock_job_crud.delete_job.assert_called_once_with(mock_db_session, job_id)

    async def test_delete_job_not_found(
        self, mock_job_crud: Any, mock_db_session: AsyncMock
    ) -> None:
        """Test delete job not found - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        job_id = str(uuid4())
        mock_job_crud.delete_job = AsyncMock(return_value=False)

        from src.api.routers.jobs.crud import delete_job

        # Act & Assert - MANDATORY
        with pytest.raises(Exception):  # Will raise APIErrorFactory.not_found
            await delete_job(job_id=job_id, db=mock_db_session)

        mock_job_crud.delete_job.assert_called_once_with(mock_db_session, job_id)


# ============================================================================
# MANDATORY Performance Benchmarks
# ============================================================================


@pytest.mark.performance
@pytest.mark.unit
@pytest.mark.asyncio
class TestJobsCRUDPerformance:
    """MANDATORY performance tests for Jobs CRUD endpoints."""

    async def test_list_jobs_performance(
        self, mock_job_crud: Any, mock_db_session: AsyncMock, sample_job_list: list[dict[str, Any]]
    ) -> None:
        """MANDATORY performance test - list jobs endpoint speed."""
        # Arrange - MANDATORY
        mock_job_crud.get_jobs = AsyncMock(return_value=(sample_job_list, len(sample_job_list)))

        from src.api.routers.jobs.crud import list_jobs

        iterations = 100

        # Act - MANDATORY
        start_time = time.perf_counter()

        for _ in range(iterations):
            await list_jobs(
                db=mock_db_session,
                page=1,
                page_size=50,
                status_filter=None,
                domain=None,
            )

        end_time = time.perf_counter()
        execution_time = end_time - start_time

        # Assert - MANDATORY
        avg_time = execution_time / iterations
        assert avg_time < 0.01  # <10ms per request
        assert execution_time < 1.0  # Total <1s for 100 requests

    async def test_get_job_performance(
        self, mock_job_crud: Any, mock_db_session: AsyncMock, sample_job_dict: dict[str, Any]
    ) -> None:
        """MANDATORY performance test - get job endpoint speed."""
        # Arrange - MANDATORY
        job_id = sample_job_dict["id"]
        mock_job = MagicMock(**sample_job_dict)
        mock_job_crud.get_job = AsyncMock(return_value=mock_job)

        from src.api.routers.jobs.crud import get_job

        iterations = 100

        # Act - MANDATORY
        start_time = time.perf_counter()

        for _ in range(iterations):
            await get_job(job_id=job_id, db=mock_db_session)

        end_time = time.perf_counter()
        execution_time = end_time - start_time

        # Assert - MANDATORY
        avg_time = execution_time / iterations
        assert avg_time < 0.01  # <10ms per request
        assert execution_time < 1.0  # Total <1s for 100 requests
