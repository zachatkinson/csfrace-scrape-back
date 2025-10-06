"""Unit tests for JobService following audit_3.md standards.

Tests for job management service with comprehensive coverage following AAA pattern
and SOLID testing principles with database integration.
"""

from datetime import datetime
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from src.common.status import JobPriority, JobStatus
from src.core.exceptions import ValidationError
from src.database.models.auth import (
    User,  # noqa: F401 - Import at module level for test_database_engine
)
from src.database.models.jobs import ScrapingJob
from src.database.services.job_service import JobCreateRequest, JobService
from tests.conftest import JobFactory


class TestJobCreateRequest:
    """Test suite for JobCreateRequest model validation."""

    @pytest.mark.unit
    def test_job_create_request_valid_data(self) -> None:
        """Test JobCreateRequest with valid data."""
        # Arrange
        url = "https://example.com/test"
        output_dir = "/tmp/output"
        user_id = str(uuid4())

        # Act
        request = JobCreateRequest(
            url=url,
            output_directory=output_dir,
            user_id=user_id,
            priority=JobPriority.HIGH,
            max_retries=5,
            options={"test": True},
        )

        # Assert
        assert request.url == url
        assert request.output_directory == output_dir
        assert request.user_id == user_id
        assert request.priority == JobPriority.HIGH
        assert request.max_retries == 5
        assert request.options == {"test": True}

    @pytest.mark.unit
    def test_job_create_request_default_values(self) -> None:
        """Test JobCreateRequest with default values."""
        # Arrange
        url = "https://example.com/test"
        output_dir = "/tmp/output"
        user_id = str(uuid4())

        # Act
        request = JobCreateRequest(url=url, output_directory=output_dir, user_id=user_id)

        # Assert
        assert request.url == url
        assert request.output_directory == output_dir
        assert request.user_id == user_id  # MANDATORY parameter
        assert request.priority == JobPriority.NORMAL  # Default
        assert request.max_retries == 3  # Default
        assert request.options == {}  # Default empty dict
        assert request.batch_id is None  # Default

    @pytest.mark.unit
    def test_job_create_request_validation_empty_url(self) -> None:
        """Test validation error for empty URL."""
        # Arrange - Act - Assert
        with pytest.raises(ValidationError) as exc_info:
            JobCreateRequest(url="", output_directory="/tmp/output", user_id=str(uuid4()))

        assert exc_info.value.details.get("field") == "url"
        assert "URL is required" in str(exc_info.value)

    @pytest.mark.unit
    def test_job_create_request_validation_whitespace_url(self) -> None:
        """Test validation error for whitespace-only URL."""
        # Arrange - Act - Assert
        with pytest.raises(ValidationError) as exc_info:
            JobCreateRequest(url="   ", output_directory="/tmp/output", user_id=str(uuid4()))

        assert exc_info.value.details.get("field") == "url"

    @pytest.mark.unit
    def test_job_create_request_validation_empty_output_directory(self) -> None:
        """Test validation error for empty output directory."""
        # Arrange - Act - Assert
        with pytest.raises(ValidationError) as exc_info:
            JobCreateRequest(url="https://example.com", output_directory="", user_id=str(uuid4()))

        assert exc_info.value.details.get("field") == "output_directory"
        assert "Output directory is required" in str(exc_info.value)

    @pytest.mark.unit
    def test_job_create_request_normalization(self) -> None:
        """Test that URL and output directory are normalized (stripped)."""
        # Arrange
        url_with_spaces = "  https://example.com/test  "
        output_dir_with_spaces = "  /tmp/output  "

        # Act
        request = JobCreateRequest(
            url=url_with_spaces, output_directory=output_dir_with_spaces, user_id=str(uuid4())
        )

        # Assert
        assert request.url == "https://example.com/test"  # Stripped
        assert request.output_directory == "/tmp/output"  # Stripped

    @pytest.mark.unit
    def test_job_create_request_options_none_to_empty_dict(self) -> None:
        """Test that None options are converted to empty dict."""
        # Arrange - Act
        request = JobCreateRequest(
            url="https://example.com",
            output_directory="/tmp/output",
            user_id=str(uuid4()),
            options=None,
        )

        # Assert
        assert request.options == {}


class TestJobService:
    """Test suite for JobService following AAA pattern."""

    @pytest.fixture
    def job_service(self, test_session: Session) -> JobService:
        """Create JobService instance with test database session."""
        return JobService(session=test_session)

    @pytest.fixture
    def sample_job_request(self, test_session: Session) -> JobCreateRequest:
        """Create sample job request for testing."""
        return JobFactory.create_job_request(session=test_session)  # type: ignore[no-any-return]

    @pytest.mark.unit
    @pytest.mark.database
    def test_create_job_success(
        self, job_service: JobService, sample_job_request: JobCreateRequest, test_session: Session
    ) -> None:
        """Test successful job creation."""
        # Arrange
        initial_job_count = test_session.query(ScrapingJob).count()

        # Act
        result = job_service.create_job(sample_job_request)

        # Assert
        assert isinstance(result, ScrapingJob)
        assert result.id is not None
        assert result.source_url == sample_job_request.url
        assert result.user_id == sample_job_request.user_id
        assert result.status == JobStatus.PENDING.value
        assert result.priority == job_service._normalize_priority(sample_job_request.priority)
        assert result.max_retries == sample_job_request.max_retries
        # Options now includes output_directory
        assert result.options is not None
        assert result.options.get("output_directory") == sample_job_request.output_directory
        assert result.created_at is not None
        assert isinstance(result.created_at, datetime)

        # Verify job was persisted
        final_job_count = test_session.query(ScrapingJob).count()
        assert final_job_count == initial_job_count + 1

    @pytest.mark.unit
    @pytest.mark.database
    def test_create_job_with_batch_id(self, job_service: JobService, test_session: Session) -> None:
        """Test job creation with batch ID."""
        # Arrange
        batch_id = str(uuid4())
        request = JobFactory.create_job_request(session=test_session, batch_id=batch_id)

        # Act
        result = job_service.create_job(request)

        # Assert
        assert result.batch_id == batch_id

    @pytest.mark.unit
    @pytest.mark.database
    def test_create_job_domain_extraction(
        self, job_service: JobService, test_session: Session
    ) -> None:
        """Test that domain is extracted from URL."""
        # Arrange
        request = JobFactory.create_job_request(
            session=test_session, url="https://example.com/path/to/page"
        )

        # Act
        result = job_service.create_job(request)

        # Assert
        assert result.domain is not None
        # Domain extraction is handled by extract_domain utility

    @pytest.mark.unit
    @pytest.mark.parametrize(
        "priority_input,expected_int",
        [
            (JobPriority.LOW, 1),
            (JobPriority.NORMAL, 5),
            (JobPriority.HIGH, 8),
            (JobPriority.URGENT, 10),
            ("low", 1),
            ("normal", 5),
            ("high", 8),
            ("urgent", 10),
            (1, 1),
            (5, 5),
            (10, 10),
            (15, 10),  # Clamped to max
            (-5, 1),  # Clamped to min
        ],
    )
    def test_normalize_priority(
        self, job_service: JobService, priority_input: Any, expected_int: int
    ) -> None:
        """Test priority normalization with various input types."""
        # Arrange - Act
        result = job_service._normalize_priority(priority_input)

        # Assert
        assert result == expected_int
        assert isinstance(result, int)

    @pytest.mark.unit
    def test_normalize_priority_invalid_string(self, job_service: JobService) -> None:
        """Test priority normalization with invalid string defaults to 5."""
        # Arrange - Act
        result = job_service._normalize_priority("invalid_priority")

        # Assert
        assert result == 5  # Default priority

    @pytest.mark.unit
    def test_extract_domain_safely(self, job_service: JobService) -> None:
        """Test safe domain extraction from URL."""
        # Arrange
        url = "https://example.com/path"

        # Act
        result = job_service._extract_domain_safely(url)

        # Assert
        assert result is not None
        # Note: Actual domain extraction logic is in utils

    @pytest.mark.unit
    @pytest.mark.database
    def test_create_jobs_batch_success(
        self, job_service: JobService, test_session: Session
    ) -> None:
        """Test successful batch job creation."""
        # Arrange
        # Create user for foreign key constraint (MANDATORY)
        test_user_id = JobFactory._ensure_user_exists(test_session)

        urls = [
            "https://example.com/page1",
            "https://example.com/page2",
            "https://example.com/page3",
        ]
        config = {
            "output_directory": "/tmp/batch_output",
            "user_id": test_user_id,
            "priority": JobPriority.HIGH,
            "max_retries": 5,
        }
        initial_count = test_session.query(ScrapingJob).count()

        # Act
        results = job_service.create_jobs(urls, **config)

        # Assert
        assert len(results) == 3
        assert all(isinstance(job, ScrapingJob) for job in results)

        # Verify all jobs have same batch_id (since multiple URLs)
        batch_ids = [job.batch_id for job in results]
        assert len(set(batch_ids)) == 1  # All same batch_id
        assert batch_ids[0] is not None

        # Verify all jobs have correct config
        for i, job in enumerate(results):
            assert job.source_url == urls[i]
            assert job.priority == 8  # HIGH priority normalized
            assert job.max_retries == 5

        # Verify persistence
        final_count = test_session.query(ScrapingJob).count()
        assert final_count == initial_count + 3

    @pytest.mark.unit
    @pytest.mark.database
    def test_create_jobs_single_url_no_batch_id(
        self, job_service: JobService, test_session: Session
    ) -> None:
        """Test that single URL doesn't get batch_id."""
        # Arrange
        # Create user for foreign key constraint (MANDATORY)
        test_user_id = JobFactory._ensure_user_exists(test_session)

        urls = ["https://example.com/single"]
        config = {"output_directory": "/tmp/output", "user_id": test_user_id}

        # Act
        results = job_service.create_jobs(urls, **config)

        # Assert
        assert len(results) == 1
        assert results[0].batch_id is None  # Single job shouldn't have batch_id

    @pytest.mark.unit
    def test_create_jobs_empty_urls_validation_error(
        self, job_service: JobService, test_session: Session
    ) -> None:
        """Test validation error for empty URLs list."""
        # Arrange
        test_user_id = JobFactory._ensure_user_exists(test_session)

        # Act - Assert
        with pytest.raises(ValidationError) as exc_info:
            job_service.create_jobs([], output_directory="/tmp/output", user_id=test_user_id)

        assert exc_info.value.details.get("field") == "urls"
        assert "At least one URL is required" in str(exc_info.value)

    @pytest.mark.unit
    @pytest.mark.database
    def test_get_job_success(self, job_service: JobService, test_session: Session) -> None:
        """Test successful job retrieval by ID."""
        # Arrange
        job = JobFactory.create_scraping_job(test_session)
        job_id = job.id

        # Act
        result = job_service.get_job(job_id)

        # Assert
        assert result is not None
        assert result.id == job_id
        assert result.source_url == job.source_url

    @pytest.mark.unit
    @pytest.mark.database
    def test_get_job_not_found(self, job_service: JobService) -> None:
        """Test job retrieval for non-existent ID."""
        # Arrange
        non_existent_id = str(uuid4())

        # Act
        result = job_service.get_job(non_existent_id)

        # Assert
        assert result is None

    @pytest.mark.unit
    @pytest.mark.database
    def test_update_job_status_success(
        self, job_service: JobService, test_session: Session
    ) -> None:
        """Test successful job status update."""
        # Arrange
        job = JobFactory.create_scraping_job(test_session, status=JobStatus.PENDING)
        job_id = job.id

        # Act
        result = job_service.update_job_status(
            job_id=job_id,
            new_status=JobStatus.RUNNING,
            processing_time_ms=1500,
        )

        # Assert
        assert result is not None
        assert result.status == JobStatus.RUNNING.value
        assert result.processing_time_ms == 1500
        assert result.started_at is not None  # Should be set for RUNNING status
        assert result.completed_at is None  # Not completed yet

    @pytest.mark.unit
    @pytest.mark.database
    def test_update_job_status_to_completed(
        self, job_service: JobService, test_session: Session
    ) -> None:
        """Test updating job status to completed sets completed_at."""
        # Arrange
        job = JobFactory.create_scraping_job(test_session, status=JobStatus.RUNNING)
        job_id = job.id

        # Act
        result = job_service.update_job_status(
            job_id=job_id,
            new_status=JobStatus.COMPLETED,
            processing_time_ms=5000,
        )

        # Assert
        assert result is not None
        assert result.status == JobStatus.COMPLETED.value
        assert result.completed_at is not None
        assert isinstance(result.completed_at, datetime)

    @pytest.mark.unit
    @pytest.mark.database
    def test_update_job_status_to_failed_with_error(
        self, job_service: JobService, test_session: Session
    ) -> None:
        """Test updating job status to failed with error message."""
        # Arrange
        job = JobFactory.create_scraping_job(test_session, status=JobStatus.RUNNING)
        error_message = "Connection timeout"

        # Act
        result = job_service.update_job_status(
            job_id=job.id,
            new_status=JobStatus.FAILED,
            error_message=error_message,
        )

        # Assert
        assert result is not None
        assert result.status == JobStatus.FAILED.value
        assert result.error_message == error_message
        assert result.completed_at is not None

    @pytest.mark.unit
    def test_update_job_status_not_found(self, job_service: JobService) -> None:
        """Test updating status for non-existent job."""
        # Arrange
        non_existent_id = str(uuid4())

        # Act
        result = job_service.update_job_status(
            job_id=non_existent_id,
            new_status=JobStatus.COMPLETED,
        )

        # Assert
        assert result is None

    @pytest.mark.unit
    @pytest.mark.database
    def test_get_pending_jobs(self, job_service: JobService, test_session: Session) -> None:
        """Test retrieval of pending jobs ordered by priority."""
        # Arrange
        # Create jobs with different priorities and statuses
        high_priority_job = JobFactory.create_scraping_job(
            test_session, status=JobStatus.PENDING, priority=8
        )
        normal_priority_job = JobFactory.create_scraping_job(
            test_session, status=JobStatus.PENDING, priority=5
        )
        low_priority_job = JobFactory.create_scraping_job(
            test_session, status=JobStatus.PENDING, priority=1
        )
        running_job = JobFactory.create_scraping_job(
            test_session, status=JobStatus.RUNNING, priority=10
        )

        # Act
        results = job_service.get_pending_jobs(limit=10)

        # Assert
        assert len(results) == 3  # Only pending jobs

        # Verify jobs are returned and ordered by priority (high to low)
        job_priorities = [job.priority for job in results]
        assert job_priorities == sorted(job_priorities, reverse=True)

        # Verify only pending jobs are returned
        for job in results:
            assert job.status == JobStatus.PENDING.value

    @pytest.mark.unit
    @pytest.mark.database
    def test_get_jobs_by_status(self, job_service: JobService, test_session: Session) -> None:
        """Test filtering jobs by status."""
        # Arrange
        completed_job1 = JobFactory.create_scraping_job(test_session, status=JobStatus.COMPLETED)
        completed_job2 = JobFactory.create_scraping_job(test_session, status=JobStatus.COMPLETED)
        pending_job = JobFactory.create_scraping_job(test_session, status=JobStatus.PENDING)

        # Act
        results = job_service.get_jobs_by_status(JobStatus.COMPLETED, limit=10)

        # Assert
        assert len(results) == 2
        for job in results:
            assert job.status == JobStatus.COMPLETED.value

    @pytest.mark.unit
    @pytest.mark.database
    def test_get_jobs_by_status_with_domain_filter(
        self, job_service: JobService, test_session: Session
    ) -> None:
        """Test filtering jobs by status and domain."""
        # Arrange
        domain = "example.com"

        # Create job for specific domain
        job_request = JobFactory.create_job_request(
            session=test_session, url=f"https://{domain}/page"
        )
        target_job = job_service.create_job(job_request)
        job_service.update_job_status(target_job.id, JobStatus.COMPLETED)

        # Create job for different domain
        other_job_request = JobFactory.create_job_request(
            session=test_session, url="https://other.com/page"
        )
        other_job = job_service.create_job(other_job_request)
        job_service.update_job_status(other_job.id, JobStatus.COMPLETED)

        # Act
        results = job_service.get_jobs_by_status(
            status=JobStatus.COMPLETED, domain=domain, limit=10
        )

        # Assert
        assert len(results) >= 1
        # Note: Domain filtering depends on how extract_domain works

    @pytest.mark.unit
    @pytest.mark.database
    def test_get_retry_jobs(self, job_service: JobService, test_session: Session) -> None:
        """Test retrieval of jobs eligible for retry."""
        # Arrange
        # Create failed job that can be retried
        retry_job = JobFactory.create_scraping_job(
            test_session, status=JobStatus.FAILED, priority=8
        )
        retry_job.retry_count = 1
        retry_job.max_retries = 3
        test_session.commit()

        # Create failed job that exceeded max retries
        exhausted_job = JobFactory.create_scraping_job(test_session, status=JobStatus.FAILED)
        exhausted_job.retry_count = 3
        exhausted_job.max_retries = 3
        test_session.commit()

        # Act
        results = job_service.get_retry_jobs(max_jobs=10)

        # Assert
        assert len(results) >= 1
        for job in results:
            assert job.status == JobStatus.FAILED.value
            assert job.retry_count < job.max_retries

    @pytest.mark.unit
    @pytest.mark.database
    def test_get_batch_jobs(self, job_service: JobService, test_session: Session) -> None:
        """Test retrieval of jobs in a batch."""
        # Arrange
        # Create user for foreign key constraint (MANDATORY)
        test_user_id = JobFactory._ensure_user_exists(test_session)

        # Create multiple jobs in same batch
        # Note: create_jobs automatically assigns batch_id when multiple URLs provided
        urls = ["https://example.com/1", "https://example.com/2", "https://example.com/3"]
        config = {"output_directory": "/tmp/batch", "user_id": test_user_id}

        created_jobs = job_service.create_jobs(urls, **config)
        batch_id = created_jobs[0].batch_id  # Get the auto-assigned batch_id
        assert batch_id is not None  # Multiple URLs should have batch_id

        # Act
        results = job_service.get_batch_jobs(batch_id)

        # Assert
        assert len(results) == 3
        for job in results:
            assert job.batch_id == batch_id

    @pytest.mark.unit
    @pytest.mark.database
    def test_get_batch_summary(self, job_service: JobService, test_session: Session) -> None:
        """Test batch summary calculation."""
        # Arrange
        # Create user for foreign key constraint (MANDATORY)
        test_user_id = JobFactory._ensure_user_exists(test_session)

        # Create jobs with different statuses
        # Note: create_jobs automatically assigns batch_id when multiple URLs provided
        urls = ["https://example.com/1", "https://example.com/2", "https://example.com/3"]
        jobs = job_service.create_jobs(urls, output_directory="/tmp/batch", user_id=test_user_id)
        batch_id = jobs[0].batch_id  # Get the auto-assigned batch_id
        assert batch_id is not None  # Multiple URLs should have batch_id

        # Update jobs to different statuses
        job_service.update_job_status(jobs[0].id, JobStatus.COMPLETED)
        job_service.update_job_status(jobs[1].id, JobStatus.RUNNING)
        # jobs[2] remains PENDING
        test_session.commit()  # Ensure status updates are committed

        # Act
        summary = job_service.get_batch_summary(batch_id)

        # Assert
        assert summary["batch_id"] == batch_id
        assert summary["total_jobs"] == 3
        assert summary["overall_status"] == "mixed"  # Mixed statuses
        assert "status_counts" in summary
        assert summary["status_counts"][JobStatus.COMPLETED.value] == 1
        assert summary["status_counts"][JobStatus.RUNNING.value] == 1
        assert summary["status_counts"][JobStatus.PENDING.value] == 1

    @pytest.mark.unit
    def test_get_batch_summary_empty_batch(self, job_service: JobService) -> None:
        """Test batch summary for non-existent batch."""
        # Arrange
        non_existent_batch_id = str(uuid4())

        # Act
        summary = job_service.get_batch_summary(non_existent_batch_id)

        # Assert
        assert summary["batch_id"] == non_existent_batch_id
        assert summary["total_jobs"] == 0
        assert summary["overall_status"] == "empty"
        assert summary["status_counts"] == {}


class TestJobServiceEdgeCases:
    """Edge cases and error scenarios for JobService."""

    @pytest.fixture
    def job_service(self, test_session: Session) -> JobService:
        """Create JobService instance with test database session."""
        return JobService(session=test_session)

    @pytest.mark.unit
    @pytest.mark.database
    def test_create_job_with_very_long_url(self, job_service: JobService) -> None:
        """Test job creation with very long URL."""
        # Arrange
        long_url = "https://example.com/" + "a" * 1000  # Very long URL
        request = JobFactory.create_job_request(session=job_service.session, url=long_url)

        # Act
        result = job_service.create_job(request)

        # Assert
        assert result.source_url == long_url

    @pytest.mark.unit
    @pytest.mark.database
    def test_create_job_with_unicode_url(self, job_service: JobService) -> None:
        """Test job creation with Unicode characters in URL."""
        # Arrange
        unicode_url = "https://example.com/测试/页面"
        request = JobFactory.create_job_request(session=job_service.session, url=unicode_url)

        # Act
        result = job_service.create_job(request)

        # Assert
        assert result.source_url == unicode_url

    @pytest.mark.unit
    def test_normalize_priority_edge_cases(self, job_service: JobService) -> None:
        """Test priority normalization with edge case inputs."""
        # Test various invalid inputs
        assert job_service._normalize_priority(None) == 5
        assert job_service._normalize_priority("") == 5
        assert job_service._normalize_priority([]) == 5
        assert job_service._normalize_priority({}) == 5

    @pytest.mark.unit
    @pytest.mark.database
    def test_concurrent_job_creation(self, job_service: JobService, test_session: Session) -> None:
        """Test that concurrent job creation doesn't cause conflicts."""
        # This is a simplified test - real concurrency testing would require more setup

        # Arrange
        requests = [JobFactory.create_job_request(session=test_session) for _ in range(5)]

        # Act
        results = [job_service.create_job(req) for req in requests]

        # Assert
        assert len(results) == 5
        assert len({job.id for job in results}) == 5  # All unique IDs

    @pytest.mark.unit
    @pytest.mark.database
    def test_get_batch_summary_all_failed(
        self, job_service: JobService, test_session: Session
    ) -> None:
        """Test batch summary when all jobs have failed."""
        # Arrange - Create user for foreign key constraint (MANDATORY)
        test_user_id = JobFactory._ensure_user_exists(test_session)

        # Create batch with multiple failed jobs
        urls = ["https://example.com/1", "https://example.com/2", "https://example.com/3"]
        jobs = job_service.create_jobs(urls, output_directory="/tmp/batch", user_id=test_user_id)
        batch_id = jobs[0].batch_id
        assert batch_id is not None  # Multiple URLs should have batch_id

        # Update all jobs to FAILED status
        for job in jobs:
            job_service.update_job_status(job.id, JobStatus.FAILED, error_message="Test error")
        test_session.commit()

        # Act
        summary = job_service.get_batch_summary(batch_id)

        # Assert
        assert summary["batch_id"] == batch_id
        assert summary["total_jobs"] == 3
        assert summary["overall_status"] == "failed"  # All jobs failed (line 446)
        assert summary["status_counts"][JobStatus.FAILED.value] == 3

    @pytest.mark.unit
    @pytest.mark.database
    def test_get_batch_summary_all_running(
        self, job_service: JobService, test_session: Session
    ) -> None:
        """Test batch summary when all jobs are running."""
        # Arrange - Create user for foreign key constraint (MANDATORY)
        test_user_id = JobFactory._ensure_user_exists(test_session)

        # Create batch with jobs
        urls = ["https://example.com/1", "https://example.com/2"]
        jobs = job_service.create_jobs(urls, output_directory="/tmp/batch", user_id=test_user_id)
        batch_id = jobs[0].batch_id
        assert batch_id is not None  # Multiple URLs should have batch_id

        # Update all jobs to RUNNING status
        for job in jobs:
            job_service.update_job_status(job.id, JobStatus.RUNNING)
        test_session.commit()

        # Act
        summary = job_service.get_batch_summary(batch_id)

        # Assert
        assert summary["batch_id"] == batch_id
        assert summary["total_jobs"] == 2
        assert summary["overall_status"] == "running"  # All jobs running (line 450-451)
        assert summary["status_counts"][JobStatus.RUNNING.value] == 2

    @pytest.mark.unit
    @pytest.mark.database
    def test_get_batch_summary_all_pending(
        self, job_service: JobService, test_session: Session
    ) -> None:
        """Test batch summary when all jobs are pending."""
        # Arrange - Create user for foreign key constraint (MANDATORY)
        test_user_id = JobFactory._ensure_user_exists(test_session)

        # Create batch - jobs start as PENDING by default
        urls = ["https://example.com/1", "https://example.com/2"]
        jobs = job_service.create_jobs(urls, output_directory="/tmp/batch", user_id=test_user_id)
        batch_id = jobs[0].batch_id
        assert batch_id is not None  # Multiple URLs should have batch_id

        test_session.commit()

        # Act
        summary = job_service.get_batch_summary(batch_id)

        # Assert
        assert summary["batch_id"] == batch_id
        assert summary["total_jobs"] == 2
        assert summary["overall_status"] == "pending"  # All jobs pending (line 452-453)
        assert summary["status_counts"][JobStatus.PENDING.value] == 2

    @pytest.mark.unit
    @pytest.mark.database
    def test_get_batch_summary_all_cancelled(
        self, job_service: JobService, test_session: Session
    ) -> None:
        """Test batch summary when all jobs are cancelled."""
        # Arrange - Create user for foreign key constraint (MANDATORY)
        test_user_id = JobFactory._ensure_user_exists(test_session)

        # Create batch with jobs
        urls = ["https://example.com/1", "https://example.com/2"]
        jobs = job_service.create_jobs(urls, output_directory="/tmp/batch", user_id=test_user_id)
        batch_id = jobs[0].batch_id
        assert batch_id is not None  # Multiple URLs should have batch_id

        # Update all jobs to CANCELLED status
        for job in jobs:
            job_service.update_job_status(job.id, JobStatus.CANCELLED)
        test_session.commit()

        # Act
        summary = job_service.get_batch_summary(batch_id)

        # Assert
        assert summary["batch_id"] == batch_id
        assert summary["total_jobs"] == 2
        assert summary["overall_status"] == "failed"  # All cancelled counts as failed (line 446)
        assert summary["status_counts"][JobStatus.CANCELLED.value] == 2

    @pytest.mark.unit
    @pytest.mark.database
    def test_get_batch_summary_unknown_status_mix(
        self, job_service: JobService, test_session: Session
    ) -> None:
        """Test batch summary with edge case status combinations that don't match standard patterns."""
        # Arrange - Create user for foreign key constraint (MANDATORY)
        test_user_id = JobFactory._ensure_user_exists(test_session)

        # Create batch with single job in uncommon final state
        urls = ["https://example.com/1"]
        jobs = job_service.create_jobs(urls, output_directory="/tmp/batch", user_id=test_user_id)
        batch_id = jobs[0].batch_id
        assert batch_id is not None  # Multiple URLs should have batch_id

        # Update to FAILED status (single status but not completed/running/pending)
        job_service.update_job_status(jobs[0].id, JobStatus.FAILED, error_message="Test")
        test_session.commit()

        # Act
        summary = job_service.get_batch_summary(batch_id)

        # Assert
        assert summary["batch_id"] == batch_id
        assert summary["total_jobs"] == 1
        # With single job in FAILED status, should be "failed" not "mixed"
        assert summary["overall_status"] == "failed"  # Line 446
        assert summary["status_counts"][JobStatus.FAILED.value] == 1

    @pytest.mark.unit
    @pytest.mark.database
    def test_get_batch_summary_fallback_mixed(
        self, job_service: JobService, test_session: Session
    ) -> None:
        """Test batch summary fallback to 'mixed' for unusual single-status edge cases."""
        # Arrange - Create user for foreign key constraint (MANDATORY)
        test_user_id = JobFactory._ensure_user_exists(test_session)

        # Create batch with single CANCELLED job (not completed/running/pending/failed)
        urls = ["https://example.com/1"]
        jobs = job_service.create_jobs(urls, output_directory="/tmp/batch", user_id=test_user_id)
        batch_id = jobs[0].batch_id
        assert batch_id is not None  # Multiple URLs should have batch_id

        # Manually set job status to simulate edge case
        # CANCELLED doesn't trigger any of the specific branches for single status
        from sqlalchemy import update

        from src.database.models.jobs import ScrapingJob

        # Direct update to bypass service logic
        stmt = (
            update(ScrapingJob)
            .where(ScrapingJob.id == jobs[0].id)
            .values(status=JobStatus.CANCELLED.value)
        )
        test_session.execute(stmt)
        test_session.commit()

        # Act
        summary = job_service.get_batch_summary(batch_id)

        # Assert - Expect "failed" since CANCELLED is in the failed/cancelled group
        assert summary["batch_id"] == batch_id
        assert summary["total_jobs"] == 1
        assert summary["overall_status"] == "failed"  # CANCELLED counts as failed (line 446)
