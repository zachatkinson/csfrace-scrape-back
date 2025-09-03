"""Comprehensive tests for database service layer functionality with PostgreSQL containers.

This module consolidates all database service tests following DRY and SOLID principles.
Tests are organized into logical groups for better maintainability and coverage.
"""

import os
import threading
import time
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, Mock, patch

import pytest
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from src.core.exceptions import DatabaseError
from src.database.models import (
    JobPriority,
    JobStatus,
    ScrapingJob,
)
from src.database.service import DatabaseService


@pytest.mark.integration
class TestDatabaseServiceCore:
    """Core database service operations and initialization."""

    def test_database_service_initialization(self, postgres_container):
        """Test DatabaseService initialization with PostgreSQL."""
        # Set environment variables for PostgreSQL connection
        os.environ["DATABASE_HOST"] = postgres_container.get_container_host_ip()
        os.environ["DATABASE_PORT"] = str(postgres_container.get_exposed_port(5432))
        os.environ["DATABASE_NAME"] = postgres_container.dbname
        os.environ["DATABASE_USER"] = postgres_container.username
        os.environ["DATABASE_PASSWORD"] = postgres_container.password

        try:
            service = DatabaseService(echo=True)
            assert service.engine is not None
            assert service.SessionLocal is not None
            # Verify PostgreSQL connection
            assert "postgresql" in str(service.engine.url)
        finally:
            # Clean up environment variables
            for key in [
                "DATABASE_HOST",
                "DATABASE_PORT",
                "DATABASE_NAME",
                "DATABASE_USER",
                "DATABASE_PASSWORD",
            ]:
                os.environ.pop(key, None)

    def test_initialize_database(self, testcontainers_db_service):
        """Test database table creation."""
        # Should not raise any exceptions
        testcontainers_db_service.initialize_database()

        # Verify tables were created by checking engine with inspector
        from sqlalchemy import inspect

        inspector = inspect(testcontainers_db_service.engine)
        table_names = inspector.get_table_names()
        expected_tables = {
            "scraping_jobs",
            "batches",
            "content_results",
            "job_logs",
            "system_metrics",
        }
        assert expected_tables.issubset(set(table_names))

    def test_initialize_database_idempotent(self, testcontainers_db_service):
        """Test that initialize_database is idempotent."""
        # Should not raise on multiple calls
        testcontainers_db_service.initialize_database()
        testcontainers_db_service.initialize_database()
        testcontainers_db_service.initialize_database()

        # Verify tables still exist
        from sqlalchemy import inspect

        inspector = inspect(testcontainers_db_service.engine)
        table_names = inspector.get_table_names()
        assert "scraping_jobs" in table_names


@pytest.mark.unit
class TestDatabaseServiceSessions:
    """Database session management and transaction tests using mocks."""

    def test_session_context_manager_success(self, mocker):
        """Test database session context manager with successful transaction."""
        from tests.utils import MockSessionFactory

        # Create mock service with DRY factory pattern
        service, mock_session = MockSessionFactory.create_mock_service(mocker)

        # Test successful context manager execution
        with service.get_session() as session:
            session.add("test_item")
            # Should commit automatically

        # Verify session operations called correctly
        service.SessionLocal.assert_called_once()  # Session factory called
        mock_session.add.assert_called_once_with("test_item")
        mock_session.commit.assert_called_once()
        mock_session.close.assert_called_once()

    def test_session_context_manager_rollback(self, mocker):
        """Test database session context manager with exception rollback."""
        from tests.utils import MockSessionFactory

        # Create mock service with DRY factory pattern
        service, mock_session = MockSessionFactory.create_mock_service(mocker)

        # Test exception handling in context manager
        test_exception = ValueError("Test exception")
        try:
            with service.get_session() as session:
                session.add("test_item")
                raise test_exception
        except ValueError:
            pass  # Expected

        # Verify session operations and exception handling
        service.SessionLocal.assert_called_once()  # Session factory called
        mock_session.add.assert_called_once_with("test_item")
        mock_session.rollback.assert_called_once()  # Should rollback on exception
        mock_session.close.assert_called_once()
        # Commit should not be called due to exception
        mock_session.commit.assert_not_called()

    def test_session_context_manager_with_commit_error(self, mocker):
        """Test session context manager when commit fails."""
        from tests.utils import MockSessionFactory

        # Create mock service with commit error using DRY factory pattern
        service, mock_session = MockSessionFactory.create_mock_service(
            mocker, commit_side_effect=SQLAlchemyError("Commit failed")
        )

        # Test commit error handling
        with pytest.raises(SQLAlchemyError):
            with service.get_session():
                pass  # Should fail during commit

        # Verify error handling sequence
        service.SessionLocal.assert_called_once()  # Session factory called
        mock_session.commit.assert_called_once()  # Commit attempted
        mock_session.rollback.assert_called_once()  # Rollback on error
        mock_session.close.assert_called_once()  # Always closed


@pytest.mark.integration
class TestDatabaseServiceJobOperations:
    """Job creation, retrieval, and status management tests."""

    def test_create_job_basic(self, testcontainers_db_service):
        """Test basic job creation with auto-extracted domain and slug."""
        job = testcontainers_db_service.create_job(
            url="https://example.com/blog/test-post",
            output_directory="/tmp/output",
        )

        assert job.id is not None
        assert job.url == "https://example.com/blog/test-post"
        assert job.domain == "example.com"
        assert job.slug == "test-post"
        assert job.output_directory == "/tmp/output"
        assert job.status == JobStatus.PENDING

    def test_create_job_with_custom_fields(self, testcontainers_db_service):
        """Test job creation with custom domain, slug, and additional fields."""
        job = testcontainers_db_service.create_job(
            url="https://example.com/blog/post",
            output_directory="/tmp/output",
            domain="custom.com",
            slug="custom-slug",
            priority="high",
            max_retries=5,
            timeout_seconds=60,
        )

        assert job.domain == "custom.com"
        assert job.slug == "custom-slug"
        assert job.priority.value == "high"
        assert job.max_retries == 5
        assert job.timeout_seconds == 60

    def test_create_job_with_batch(self, testcontainers_db_service):
        """Test job creation associated with a batch."""
        # Create batch first
        batch = testcontainers_db_service.create_batch(
            name="Test Batch",
            description="Test batch for job creation",
        )

        # Create job in batch
        job = testcontainers_db_service.create_job(
            url="https://example.com/test",
            output_directory="/tmp/output",
            batch_id=batch.id,
        )

        assert job.batch_id == batch.id

        # Verify batch relationship through fresh query to avoid DetachedInstanceError
        retrieved_job = testcontainers_db_service.get_job(job.id)
        assert retrieved_job is not None
        assert retrieved_job.batch_id == batch.id

    def test_create_job_url_parsing_edge_cases(self, testcontainers_db_service):
        """Test URL parsing for various edge cases."""
        # URL with query parameters
        job1 = testcontainers_db_service.create_job(
            url="https://example.com/path?query=param",
            output_directory="/tmp/output",
        )
        assert job1.domain == "example.com"
        assert job1.slug == "path"

        # URL with fragment
        job2 = testcontainers_db_service.create_job(
            url="https://example.com/article#section",
            output_directory="/tmp/output",
        )
        assert job2.slug == "article"

        # URL with multiple path segments
        job3 = testcontainers_db_service.create_job(
            url="https://example.com/blog/2024/01/post",
            output_directory="/tmp/output",
        )
        assert job3.slug == "post"

        # URL with no path after domain
        job4 = testcontainers_db_service.create_job(
            url="https://example.com",
            output_directory="/tmp/output",
        )
        assert job4.slug == "homepage"

        # URL with trailing slash
        job5 = testcontainers_db_service.create_job(
            url="https://example.com/page/",
            output_directory="/tmp/output",
        )
        assert job5.slug == "page"

    def test_create_job_homepage_slug_extraction(self, testcontainers_db_service):
        """Test slug extraction for homepage URLs."""
        job = testcontainers_db_service.create_job(
            url="https://example.com/",
            output_directory="/tmp/output",
        )
        assert job.slug == "homepage"

    def test_create_job_with_priority_string(self, testcontainers_db_service):
        """Test job creation with string priority."""
        job = testcontainers_db_service.create_job(
            url="https://example.com/test",
            output_directory="/tmp/output",
            priority="urgent",
        )
        assert job.priority == JobPriority.URGENT

    def test_create_job_with_invalid_priority_string(self, testcontainers_db_service):
        """Test job creation with invalid priority string defaults to NORMAL."""
        job = testcontainers_db_service.create_job(
            url="https://example.com/test",
            output_directory="/tmp/output",
            priority="invalid_priority",
        )
        assert job.priority == JobPriority.NORMAL

    def test_create_job_with_priority_enum(self, testcontainers_db_service):
        """Test job creation with JobPriority enum directly."""
        job = testcontainers_db_service.create_job(
            url="https://example.com/test",
            output_directory="/tmp/output",
            priority=JobPriority.URGENT,
        )
        assert job.priority == JobPriority.URGENT

    def test_create_job_with_custom_slug_kwarg(self, testcontainers_db_service):
        """Test job creation with custom_slug in kwargs."""
        job = testcontainers_db_service.create_job(
            url="https://example.com/test",
            output_directory="/tmp/output",
            custom_slug="my-custom-slug",
        )
        # When custom_slug is provided in kwargs, auto-extraction is skipped
        assert job.slug is None

    def test_get_job(self, testcontainers_db_service):
        """Test job retrieval by ID."""
        # Create job
        created_job = testcontainers_db_service.create_job(
            url="https://example.com/test",
            output_directory="/tmp/output",
        )

        # Retrieve job
        retrieved_job = testcontainers_db_service.get_job(created_job.id)
        assert retrieved_job is not None
        assert retrieved_job.id == created_job.id
        assert retrieved_job.url == created_job.url

    def test_get_job_nonexistent(self, testcontainers_db_service):
        """Test retrieval of non-existent job."""
        job = testcontainers_db_service.get_job(99999)
        assert job is None


@pytest.mark.integration
class TestDatabaseServiceJobStatusUpdates:
    """Job status update operations."""

    def test_update_job_status_to_running(self, testcontainers_db_service):
        """Test updating job status to running (sets started_at)."""
        job = testcontainers_db_service.create_job(
            url="https://example.com/test",
            output_directory="/tmp/output",
        )

        success = testcontainers_db_service.update_job_status(job.id, JobStatus.RUNNING)
        assert success is True

        # Verify update
        updated_job = testcontainers_db_service.get_job(job.id)
        assert updated_job.status == JobStatus.RUNNING
        assert updated_job.started_at is not None

    def test_update_job_status_to_completed(self, testcontainers_db_service):
        """Test updating job status to completed with duration."""
        job = testcontainers_db_service.create_job(
            url="https://example.com/test",
            output_directory="/tmp/output",
        )

        success = testcontainers_db_service.update_job_status(
            job.id, JobStatus.COMPLETED, duration=5.5
        )
        assert success is True

        # Verify update
        updated_job = testcontainers_db_service.get_job(job.id)
        assert updated_job.status == JobStatus.COMPLETED
        assert updated_job.completed_at is not None
        assert updated_job.duration_seconds == 5.5

    def test_update_job_status_to_failed_with_error(self, testcontainers_db_service):
        """Test updating job status to failed with error message."""
        job = testcontainers_db_service.create_job(
            url="https://example.com/test",
            output_directory="/tmp/output",
        )

        error_msg = "Connection timeout"
        success = testcontainers_db_service.update_job_status(
            job.id,
            JobStatus.FAILED,
            error_message=error_msg,
        )
        assert success is True

        # Verify update
        updated_job = testcontainers_db_service.get_job(job.id)
        assert updated_job.status == JobStatus.FAILED
        assert updated_job.error_message == error_msg
        assert updated_job.completed_at is not None

    def test_update_job_status_to_cancelled(self, testcontainers_db_service):
        """Test updating job status to cancelled."""
        job = testcontainers_db_service.create_job(
            url="https://example.com/test-cancel",
            output_directory="/tmp/output",
        )

        # Verify job exists before updating
        retrieved_job = testcontainers_db_service.get_job(job.id)
        assert retrieved_job is not None
        assert retrieved_job.status == JobStatus.PENDING

        # Update status
        success = testcontainers_db_service.update_job_status(job.id, JobStatus.CANCELLED)
        assert success is True

        # Verify the update
        updated_job = testcontainers_db_service.get_job(job.id)
        assert updated_job is not None
        assert updated_job.status == JobStatus.CANCELLED
        assert updated_job.completed_at is not None

    def test_update_job_status_nonexistent(self, testcontainers_db_service):
        """Test updating status of non-existent job."""
        success = testcontainers_db_service.update_job_status(99999, JobStatus.COMPLETED)
        assert success is False


@pytest.mark.integration
class TestDatabaseServiceJobRetrieval:
    """Job retrieval and filtering operations."""

    def test_get_pending_jobs(self, testcontainers_db_service, test_isolation_id):
        """Test retrieval of pending jobs with priority ordering using isolation IDs."""
        from tests.utils import DataMatcher, JobFactory

        # Create test jobs using DRY factory pattern with isolation
        job_factory = JobFactory(test_isolation_id)
        job_specs = job_factory.create_priority_test_jobs()

        # Create jobs in database following SOLID principles
        created_jobs = {}
        for spec in job_specs:
            job = testcontainers_db_service.create_job(
                url=spec.unique_url,
                output_directory=spec.output_directory,
                priority=spec.priority,
            )
            created_jobs[spec.priority] = job

        # Mark one as running to exclude it from pending results
        testcontainers_db_service.update_job_status(
            created_jobs[JobPriority.LOW].id, JobStatus.RUNNING
        )

        # Get pending jobs and filter using utility class
        # Use a larger limit to account for concurrent tests
        pending_jobs = testcontainers_db_service.get_pending_jobs(limit=1000)
        test_jobs = DataMatcher.filter_jobs_by_test_id(pending_jobs, test_isolation_id)

        # Assert using DRY helper with detailed error messages
        DataMatcher.assert_job_count(test_jobs, 3, "Priority ordering test (excluding running job)")

        # Check order: URGENT -> HIGH -> NORMAL (LOW should be excluded as RUNNING)
        assert test_jobs[0].id == created_jobs[JobPriority.URGENT].id
        assert test_jobs[1].id == created_jobs[JobPriority.HIGH].id
        assert test_jobs[2].id == created_jobs[JobPriority.NORMAL].id

    def test_get_pending_jobs_with_limit(self, testcontainers_db_service, test_isolation_id):
        """Test pending jobs retrieval with limit."""
        from tests.utils import DataMatcher

        # Create multiple jobs with isolation
        for i in range(5):
            testcontainers_db_service.create_job(
                url=f"https://example.com/test{i}-{test_isolation_id}",
                output_directory=f"/tmp/output{i}",
            )

        # Get with limit and filter by isolation
        pending_jobs = testcontainers_db_service.get_pending_jobs(limit=10)
        test_jobs = DataMatcher.filter_jobs_by_test_id(pending_jobs, test_isolation_id)

        # Should return our 5 test jobs
        DataMatcher.assert_job_count(test_jobs, 5, "Limit test with isolation")

        # Test limit functionality by getting limited results
        limited_jobs = testcontainers_db_service.get_pending_jobs(limit=3)
        limited_test_jobs = DataMatcher.filter_jobs_by_test_id(limited_jobs, test_isolation_id)
        assert len(limited_test_jobs) <= 3

    def test_get_pending_jobs_priority_ordering_with_test_isolation(
        self, testcontainers_db_service, test_isolation_id
    ):
        """Test pending jobs with priority ordering using test isolation."""
        from tests.utils import DataMatcher, JobFactory

        # Create test data using DRY factory pattern
        job_factory = JobFactory(test_isolation_id)
        job_specs = job_factory.create_priority_test_jobs()

        # Create jobs in database following SOLID principles
        created_jobs = {}
        for spec in job_specs:
            job = testcontainers_db_service.create_job(
                url=spec.unique_url,
                output_directory=spec.output_directory,
                priority=spec.priority,
            )
            created_jobs[spec.priority] = job

        # Get pending jobs and filter using utility class
        # Use a larger limit to account for concurrent tests
        pending_jobs = testcontainers_db_service.get_pending_jobs(limit=1000)
        test_jobs = DataMatcher.filter_jobs_by_test_id(pending_jobs, test_isolation_id)

        # Assert using DRY helper with detailed error messages
        DataMatcher.assert_job_count(test_jobs, 4, "Priority ordering test")

        # Check order: URGENT -> HIGH -> NORMAL -> LOW
        assert test_jobs[0].id == created_jobs[JobPriority.URGENT].id
        assert test_jobs[1].id == created_jobs[JobPriority.HIGH].id
        assert test_jobs[2].id == created_jobs[JobPriority.NORMAL].id
        assert test_jobs[3].id == created_jobs[JobPriority.LOW].id

    def test_get_pending_jobs_excludes_non_pending_with_test_isolation(
        self, testcontainers_db_service, test_isolation_id
    ):
        """Test that non-pending jobs are excluded using test isolation."""
        from tests.utils import DataMatcher, JobFactory

        # Create test jobs using DRY factory pattern
        job_factory = JobFactory(test_isolation_id)
        job_specs = job_factory.create_status_test_jobs()

        # Create jobs with different statuses following SOLID principles
        pending_job = testcontainers_db_service.create_job(
            url=job_specs["pending"].unique_url,
            output_directory=job_specs["pending"].output_directory,
        )
        running_job = testcontainers_db_service.create_job(
            url=job_specs["running"].unique_url,
            output_directory=job_specs["running"].output_directory,
        )
        testcontainers_db_service.update_job_status(running_job.id, JobStatus.RUNNING)

        completed_job = testcontainers_db_service.create_job(
            url=job_specs["completed"].unique_url,
            output_directory=job_specs["completed"].output_directory,
        )
        testcontainers_db_service.update_job_status(completed_job.id, JobStatus.COMPLETED)

        # Get pending jobs and filter using utility class
        pending_jobs = testcontainers_db_service.get_pending_jobs()
        test_pending_jobs = DataMatcher.filter_jobs_by_test_id(pending_jobs, test_isolation_id)

        # Assert using DRY helper with detailed error messages
        DataMatcher.assert_job_count(test_pending_jobs, 1, "Status exclusion test")
        assert test_pending_jobs[0].id == pending_job.id

    def test_get_pending_jobs_priority_ordering_edge_case(
        self, testcontainers_db_service, mock_time_sleep, test_isolation_id
    ):
        """Test pending jobs with same priority ordered by creation time."""
        from tests.utils import DataMatcher

        # Create jobs with same priority but different creation times with isolation
        job1 = testcontainers_db_service.create_job(
            url=f"https://example.com/first-{test_isolation_id}",
            output_directory="/tmp/output1",
            priority="normal",
        )

        # Simulate time passing - mocked by mock_time_sleep fixture
        time.sleep(0.01)  # Instant return with mock_time_sleep

        job2 = testcontainers_db_service.create_job(
            url=f"https://example.com/second-{test_isolation_id}",
            output_directory="/tmp/output2",
            priority="normal",
        )

        # Get pending jobs and filter by isolation
        # Use a larger limit to account for concurrent tests
        pending_jobs = testcontainers_db_service.get_pending_jobs(limit=1000)
        test_jobs = DataMatcher.filter_jobs_by_test_id(pending_jobs, test_isolation_id)

        DataMatcher.assert_job_count(test_jobs, 2, "Priority edge case test")
        # First created job should come first when priorities are equal
        assert test_jobs[0].id == job1.id
        assert test_jobs[1].id == job2.id

    def test_get_jobs_by_status(self, testcontainers_db_service):
        """Test job retrieval by status with pagination."""
        # Create jobs with different statuses
        job1 = testcontainers_db_service.create_job(
            url="https://example.com/test1",
            output_directory="/tmp/output1",
        )
        job2 = testcontainers_db_service.create_job(
            url="https://example.com/test2",
            output_directory="/tmp/output2",
        )
        job3 = testcontainers_db_service.create_job(
            url="https://example.com/test3",
            output_directory="/tmp/output3",
        )

        # Update some statuses
        testcontainers_db_service.update_job_status(job1.id, JobStatus.COMPLETED)
        testcontainers_db_service.update_job_status(job2.id, JobStatus.COMPLETED)

        # Get completed jobs
        completed_jobs = testcontainers_db_service.get_jobs_by_status(JobStatus.COMPLETED)
        assert len(completed_jobs) == 2

        # Get pending jobs
        pending_jobs = testcontainers_db_service.get_jobs_by_status(JobStatus.PENDING)
        assert len(pending_jobs) == 1
        assert pending_jobs[0].id == job3.id

    def test_get_jobs_by_status_with_pagination(self, testcontainers_db_service, test_isolation_id):
        """Test job retrieval by status with offset pagination."""
        # Create multiple jobs with unique identifiers for test isolation
        created_job_ids = []
        for i in range(7):  # Create 7 jobs for meaningful pagination test
            job = testcontainers_db_service.create_job(
                url=f"https://example.com/pagination-test-{test_isolation_id}-{i}",
                output_directory=f"/tmp/output{i}",
            )
            testcontainers_db_service.update_job_status(job.id, JobStatus.COMPLETED)
            created_job_ids.append(job.id)

        # Test basic pagination functionality with limit and offset
        # Test 1: Get first 3 jobs
        first_page = testcontainers_db_service.get_jobs_by_status(
            JobStatus.COMPLETED, limit=3, offset=0
        )
        assert len(first_page) >= 3, "Should return at least 3 completed jobs"
        assert len(first_page) <= 3, "Should not return more than 3 jobs when limit=3"

        # Test 2: Get next 3 jobs (offset=3)
        second_page = testcontainers_db_service.get_jobs_by_status(
            JobStatus.COMPLETED, limit=3, offset=3
        )
        assert len(second_page) >= 3, "Should return at least 3 jobs from offset=3"
        assert len(second_page) <= 3, "Should not return more than 3 jobs when limit=3"

        # Test 3: Verify pagination returns different jobs (no overlap in IDs)
        first_page_ids = {job.id for job in first_page}
        second_page_ids = {job.id for job in second_page}
        assert first_page_ids.isdisjoint(second_page_ids), "Pagination should return different jobs"

        # Test 4: Verify our created jobs exist in database
        all_completed = testcontainers_db_service.get_jobs_by_status(JobStatus.COMPLETED)
        test_jobs = [job for job in all_completed if job.id in created_job_ids]
        assert len(test_jobs) == 7, f"Expected 7 test jobs, got {len(test_jobs)}"


@pytest.mark.integration
class TestDatabaseServiceRetryOperations:
    """Job retry and recovery operations."""

    def test_get_retry_jobs(self, testcontainers_db_service):
        """Test retrieval of jobs eligible for retry."""
        # Create failed jobs
        job1 = testcontainers_db_service.create_job(
            url="https://example.com/test1",
            output_directory="/tmp/output1",
            max_retries=3,
        )
        job2 = testcontainers_db_service.create_job(
            url="https://example.com/test2",
            output_directory="/tmp/output2",
            max_retries=3,
        )

        # Make them failed with different retry counts
        testcontainers_db_service.update_job_status(job1.id, JobStatus.FAILED)
        testcontainers_db_service.update_job_status(job2.id, JobStatus.FAILED)

        # Update retry counts directly
        with testcontainers_db_service.get_session() as session:
            session.query(ScrapingJob).filter(ScrapingJob.id == job1.id).update({"retry_count": 1})
            session.query(ScrapingJob).filter(ScrapingJob.id == job2.id).update(
                {
                    "retry_count": 3  # At limit, should not be eligible
                }
            )

        # Get retry jobs
        retry_jobs = testcontainers_db_service.get_retry_jobs()
        assert len(retry_jobs) == 1
        assert retry_jobs[0].id == job1.id

    def test_get_retry_jobs_with_future_retry_time(self, testcontainers_db_service):
        """Test retry jobs filtering by next_retry_at time."""
        job = testcontainers_db_service.create_job(
            url="https://example.com/test",
            output_directory="/tmp/output",
        )

        testcontainers_db_service.update_job_status(job.id, JobStatus.FAILED)

        # Set future retry time
        future_time = datetime.now(UTC) + timedelta(hours=1)
        with testcontainers_db_service.get_session() as session:
            session.query(ScrapingJob).filter(ScrapingJob.id == job.id).update(
                {"next_retry_at": future_time}
            )

        # Should not be eligible yet
        retry_jobs = testcontainers_db_service.get_retry_jobs()
        assert len(retry_jobs) == 0

        # Set past retry time
        past_time = datetime.now(UTC) - timedelta(minutes=1)
        with testcontainers_db_service.get_session() as session:
            session.query(ScrapingJob).filter(ScrapingJob.id == job.id).update(
                {"next_retry_at": past_time}
            )

        # Should be eligible now
        retry_jobs = testcontainers_db_service.get_retry_jobs()
        assert len(retry_jobs) == 1

    def test_get_retry_jobs_null_next_retry_at(self, testcontainers_db_service):
        """Test retry jobs with null next_retry_at (should be eligible)."""
        job = testcontainers_db_service.create_job(
            url="https://example.com/test",
            output_directory="/tmp/output",
            max_retries=3,
        )

        testcontainers_db_service.update_job_status(job.id, JobStatus.FAILED)

        # Ensure next_retry_at is None
        with testcontainers_db_service.get_session() as session:
            session.query(ScrapingJob).filter(ScrapingJob.id == job.id).update(
                {"retry_count": 1, "next_retry_at": None}
            )

        retry_jobs = testcontainers_db_service.get_retry_jobs()
        assert len(retry_jobs) == 1
        assert retry_jobs[0].id == job.id

    def test_get_retry_jobs_with_limit(self, testcontainers_db_service, test_isolation_id):
        """Test retrieving retry jobs with limit."""
        # Create multiple failed jobs with unique identifiers for test isolation
        created_job_ids = []
        for i in range(5):
            job = testcontainers_db_service.create_job(
                url=f"https://example.com/retry-test-{test_isolation_id}-{i}",
                output_directory="/tmp/test",
            )
            created_job_ids.append(job.id)
            with testcontainers_db_service.get_session() as session:
                db_job = session.get(ScrapingJob, job.id)
                db_job.status = JobStatus.FAILED
                db_job.retry_count = 1
                db_job.max_retries = 3
                session.commit()

        # Get retry jobs and filter to our test jobs
        retry_jobs = testcontainers_db_service.get_retry_jobs(
            max_jobs=10
        )  # Get more to ensure we get ours
        test_retry_jobs = [job for job in retry_jobs if job.id in created_job_ids]

        # Verify we have exactly our 5 test jobs available for retry
        assert len(test_retry_jobs) == 5, f"Expected 5 test retry jobs, got {len(test_retry_jobs)}"

        # Test the limit functionality with our known jobs
        limited_retry_jobs = testcontainers_db_service.get_retry_jobs(max_jobs=3)
        assert len(limited_retry_jobs) <= 3, "Should not return more than 3 jobs when max_jobs=3"
        assert len(limited_retry_jobs) >= 1, "Should return at least 1 retry job"


@pytest.mark.integration
class TestDatabaseServiceBatchOperations:
    """Batch creation and management operations."""

    def test_create_batch(self, testcontainers_db_service):
        """Test batch creation with configuration."""
        batch = testcontainers_db_service.create_batch(
            name="Test Batch",
            description="A comprehensive test batch",
            output_base_directory="/tmp/batch_output",
            max_concurrent=5,
            continue_on_error=False,
        )

        assert batch.id is not None
        assert batch.name == "Test Batch"
        assert batch.description == "A comprehensive test batch"
        assert batch.output_base_directory == "/tmp/batch_output"
        assert batch.status == JobStatus.PENDING
        assert batch.max_concurrent == 5
        assert batch.continue_on_error is False

    def test_get_batch(self, testcontainers_db_service):
        """Test batch retrieval by ID."""
        created_batch = testcontainers_db_service.create_batch(name="Test Batch")

        retrieved_batch = testcontainers_db_service.get_batch(created_batch.id)
        assert retrieved_batch is not None
        assert retrieved_batch.id == created_batch.id
        assert retrieved_batch.name == created_batch.name

    def test_get_batch_nonexistent(self, testcontainers_db_service):
        """Test retrieval of non-existent batch."""
        batch = testcontainers_db_service.get_batch(99999)
        assert batch is None

    def test_update_batch_progress(self, testcontainers_db_service):
        """Test batch progress counter updates based on job statuses."""
        # Create batch with jobs
        batch = testcontainers_db_service.create_batch(name="Progress Test Batch")

        jobs = []
        for i in range(5):
            job = testcontainers_db_service.create_job(
                url=f"https://example.com/test{i}",
                output_directory=f"/tmp/output{i}",
                batch_id=batch.id,
            )
            jobs.append(job)

        # Update job statuses
        testcontainers_db_service.update_job_status(jobs[0].id, JobStatus.COMPLETED)
        testcontainers_db_service.update_job_status(jobs[1].id, JobStatus.COMPLETED)
        testcontainers_db_service.update_job_status(jobs[2].id, JobStatus.FAILED)
        testcontainers_db_service.update_job_status(jobs[3].id, JobStatus.SKIPPED)
        # jobs[4] remains PENDING

        # Update batch progress
        success = testcontainers_db_service.update_batch_progress(batch.id)
        assert success is True

        # Verify progress counters
        updated_batch = testcontainers_db_service.get_batch(batch.id)
        assert updated_batch.total_jobs == 5
        assert updated_batch.completed_jobs == 2
        assert updated_batch.failed_jobs == 1
        assert updated_batch.skipped_jobs == 1

    def test_update_batch_progress_nonexistent_batch(self, testcontainers_db_service):
        """Test updating progress for non-existent batch."""
        success = testcontainers_db_service.update_batch_progress(99999)
        assert success is False

    def test_update_batch_progress_with_all_job_states(
        self, testcontainers_db_service, test_isolation_id
    ):
        """Test batch progress update with various job states."""
        batch = testcontainers_db_service.create_batch(name=f"Test Batch {test_isolation_id}")

        # Create jobs in different states with unique identifiers
        jobs = []
        for i in range(10):
            job = testcontainers_db_service.create_job(
                url=f"https://example.com/batch-progress-test-{test_isolation_id}-{i}",
                output_directory=f"/tmp/output{i}",
                batch_id=batch.id,
            )
            jobs.append(job)

        # Set various states
        testcontainers_db_service.update_job_status(jobs[0].id, JobStatus.COMPLETED)
        testcontainers_db_service.update_job_status(jobs[1].id, JobStatus.COMPLETED)
        testcontainers_db_service.update_job_status(jobs[2].id, JobStatus.COMPLETED)
        testcontainers_db_service.update_job_status(jobs[3].id, JobStatus.FAILED)
        testcontainers_db_service.update_job_status(jobs[4].id, JobStatus.FAILED)
        testcontainers_db_service.update_job_status(jobs[5].id, JobStatus.SKIPPED)
        testcontainers_db_service.update_job_status(jobs[6].id, JobStatus.RUNNING)
        testcontainers_db_service.update_job_status(jobs[7].id, JobStatus.CANCELLED)
        # jobs[8] and jobs[9] remain PENDING

        # Update batch progress
        success = testcontainers_db_service.update_batch_progress(batch.id)
        assert success is True

        # Verify counts
        updated_batch = testcontainers_db_service.get_batch(batch.id)
        assert updated_batch.total_jobs == 10
        assert updated_batch.completed_jobs == 3
        assert updated_batch.failed_jobs == 2
        assert updated_batch.skipped_jobs == 1
        # RUNNING, CANCELLED, and PENDING are not counted in these specific fields


@pytest.mark.integration
class TestDatabaseServiceContentOperations:
    """Content result and logging operations."""

    def test_save_content_result(self, testcontainers_db_service):
        """Test saving converted content results."""
        job = testcontainers_db_service.create_job(
            url="https://example.com/test",
            output_directory="/tmp/output",
        )

        metadata = {
            "title": "Test Article",
            "meta_description": "Test description",
            "author": "Test Author",
            "tags": ["test", "example"],
            "categories": ["blog"],
            "custom_field": "custom_value",
        }

        file_paths = {
            "html": "/tmp/output/content.html",
            "metadata": "/tmp/output/metadata.txt",
            "images": "/tmp/output/images",
        }

        content_result = testcontainers_db_service.save_content_result(
            job_id=job.id,
            html_content="<p>Converted content</p>",
            metadata=metadata,
            file_paths=file_paths,
            word_count=100,
            image_count=5,
        )

        assert content_result.id is not None
        assert content_result.job_id == job.id
        assert content_result.converted_html == "<p>Converted content</p>"
        assert content_result.title == "Test Article"
        assert content_result.meta_description == "Test description"
        assert content_result.author == "Test Author"
        assert content_result.tags == ["test", "example"]
        assert content_result.categories == ["blog"]
        assert content_result.html_file_path == "/tmp/output/content.html"
        assert content_result.word_count == 100
        assert content_result.extra_metadata["custom_field"] == "custom_value"

    def test_save_content_result_minimal(self, testcontainers_db_service):
        """Test saving content result with minimal data."""
        job = testcontainers_db_service.create_job(
            url="https://example.com/test",
            output_directory="/tmp/output",
        )

        # Save with minimal data
        content_result = testcontainers_db_service.save_content_result(job_id=job.id)

        assert content_result.id is not None
        assert content_result.job_id == job.id
        assert content_result.converted_html is None
        assert content_result.title is None

    def test_save_content_result_with_empty_metadata(
        self, testcontainers_db_service, test_isolation_id
    ):
        """Test saving content result with empty metadata dictionary."""
        job = testcontainers_db_service.create_job(
            url=f"https://example.com/empty-metadata-test-{test_isolation_id}",
            output_directory="/tmp/output",
        )

        # Add small delay to reduce concurrent insertion pressure
        import time

        time.sleep(0.01)

        content_result = testcontainers_db_service.save_content_result(
            job_id=job.id,
            html_content="<p>Content</p>",
            metadata={},  # Empty metadata
            file_paths={},  # Empty file paths
        )

        assert content_result.id is not None
        assert content_result.title is None
        assert content_result.html_file_path is None

    def test_add_job_log(self, testcontainers_db_service):
        """Test adding structured log entries for jobs."""
        job = testcontainers_db_service.create_job(
            url="https://example.com/test",
            output_directory="/tmp/output",
        )

        log_entry = testcontainers_db_service.add_job_log(
            job_id=job.id,
            level="INFO",
            message="Processing started successfully",
            component="html_processor",
            operation="process",
            context_data={"step": "initialization", "config": {"timeout": 30}},
        )

        assert log_entry is not None
        assert log_entry.id is not None
        assert log_entry.job_id == job.id
        assert log_entry.level == "INFO"
        assert log_entry.message == "Processing started successfully"
        assert log_entry.component == "html_processor"
        assert log_entry.operation == "process"
        assert log_entry.context_data["step"] == "initialization"
        assert log_entry.timestamp is not None

    def test_add_job_log_with_null_context(self, testcontainers_db_service):
        """Test adding job log with null context data."""
        job = testcontainers_db_service.create_job(
            url="https://example.com/test",
            output_directory="/tmp/output",
        )

        log_entry = testcontainers_db_service.add_job_log(
            job_id=job.id,
            level="debug",  # Test lowercase conversion
            message="Test message",
            component=None,
            operation=None,
            context_data=None,
        )

        assert log_entry is not None
        assert log_entry.level == "DEBUG"  # Should be uppercase
        assert log_entry.component is None
        assert log_entry.operation is None
        assert log_entry.context_data is None

    def test_add_job_log_error_handling(self, testcontainers_db_service):
        """Test job log creation with database errors."""
        # Create job
        job = testcontainers_db_service.create_job(
            url="https://example.com/test",
            output_directory="/tmp/output",
        )

        # Mock database error
        with patch.object(testcontainers_db_service, "get_session") as mock_session:
            mock_session.side_effect = Exception("Database error")

            # Should not raise, returns None on error
            log_entry = testcontainers_db_service.add_job_log(
                job_id=job.id,
                level="ERROR",
                message="Test error log",
            )
            assert log_entry is None


@pytest.mark.integration
class TestDatabaseServiceStatisticsAndAnalytics:
    """Statistics calculation and analytics operations."""

    def test_get_job_statistics(self, testcontainers_db_service):
        """Test job statistics calculation for time period."""
        # Create jobs with different statuses and timing
        now = datetime.now(UTC)

        # Recent jobs (within 7 days)
        job1 = testcontainers_db_service.create_job(
            url="https://example.com/test1",
            output_directory="/tmp/output1",
        )
        job2 = testcontainers_db_service.create_job(
            url="https://example.com/test2",
            output_directory="/tmp/output2",
        )

        # Update statuses and add metrics
        testcontainers_db_service.update_job_status(job1.id, JobStatus.COMPLETED, duration=2.5)
        testcontainers_db_service.update_job_status(job2.id, JobStatus.FAILED)

        # Add content metrics
        with testcontainers_db_service.get_session() as session:
            session.query(ScrapingJob).filter(ScrapingJob.id == job1.id).update(
                {
                    "content_size_bytes": 1024,
                    "images_downloaded": 5,
                }
            )

        # Get statistics
        stats = testcontainers_db_service.get_job_statistics(days=7)

        assert stats["period_days"] == 7
        assert stats["total_jobs"] == 2
        assert stats["completed_jobs"] == 1
        assert stats["failed_jobs"] == 1
        assert stats["pending_jobs"] == 0
        assert stats["success_rate_percent"] == 50.0
        assert stats["avg_duration_seconds"] == 2.5
        assert stats["total_content_size_bytes"] == 1024
        assert stats["total_images_downloaded"] == 5

    def test_get_job_statistics_empty(self, testcontainers_db_service):
        """Test job statistics with no jobs in time period."""
        stats = testcontainers_db_service.get_job_statistics(days=1)

        assert stats["total_jobs"] == 0
        assert stats["success_rate_percent"] == 0.0
        assert stats["avg_duration_seconds"] == 0.0

    def test_get_job_statistics_with_null_values(
        self, testcontainers_db_service, test_isolation_id
    ):
        """Test statistics calculation with jobs having null metrics."""
        # Record initial count to filter out other test jobs
        initial_stats = testcontainers_db_service.get_job_statistics(days=7)
        initial_count = initial_stats["total_jobs"]

        # Create jobs without duration or content metrics with unique identifiers
        job1 = testcontainers_db_service.create_job(
            url=f"https://example.com/null-stats-test-{test_isolation_id}-1",
            output_directory="/tmp/output1",
        )
        job2 = testcontainers_db_service.create_job(
            url=f"https://example.com/null-stats-test-{test_isolation_id}-2",
            output_directory="/tmp/output2",
        )

        # Complete without duration
        testcontainers_db_service.update_job_status(job1.id, JobStatus.COMPLETED)
        testcontainers_db_service.update_job_status(job2.id, JobStatus.FAILED)

        stats = testcontainers_db_service.get_job_statistics(days=7)

        # Verify we added exactly 2 jobs (account for concurrent test jobs)
        assert stats["total_jobs"] == initial_count + 2, (
            f"Expected {initial_count + 2} total jobs, got {stats['total_jobs']}"
        )
        assert stats["avg_duration_seconds"] == 0.0  # Null average becomes 0
        assert stats["total_content_size_bytes"] == 0
        assert stats["total_images_downloaded"] == 0

    def test_get_job_statistics_with_mixed_data(self, testcontainers_db_service):
        """Test statistics with mix of complete and incomplete data."""
        # Create jobs with varying data completeness
        job1 = testcontainers_db_service.create_job(
            url="https://example.com/test1",
            output_directory="/tmp/output1",
        )
        job2 = testcontainers_db_service.create_job(
            url="https://example.com/test2",
            output_directory="/tmp/output2",
        )
        job3 = testcontainers_db_service.create_job(
            url="https://example.com/test3",
            output_directory="/tmp/output3",
        )

        # Update with different combinations of data
        testcontainers_db_service.update_job_status(job1.id, JobStatus.COMPLETED, duration=5.0)
        testcontainers_db_service.update_job_status(job2.id, JobStatus.COMPLETED, duration=10.0)
        # job3 remains pending

        # Add content metrics to only some jobs
        with testcontainers_db_service.get_session() as session:
            session.query(ScrapingJob).filter(ScrapingJob.id == job1.id).update(
                {"content_size_bytes": 2048, "images_downloaded": 10}
            )
            # job2 has no content metrics

        stats = testcontainers_db_service.get_job_statistics(days=7)

        assert stats["total_jobs"] == 3
        assert stats["completed_jobs"] == 2
        assert stats["pending_jobs"] == 1
        assert stats["success_rate_percent"] == round(2 / 3 * 100, 2)
        assert stats["avg_duration_seconds"] == 7.5  # Average of 5.0 and 10.0
        assert stats["total_content_size_bytes"] == 2048
        assert stats["total_images_downloaded"] == 10


@pytest.mark.integration
class TestDatabaseServiceCleanupOperations:
    """Database cleanup and maintenance operations."""

    def test_cleanup_old_jobs(self, testcontainers_db_service):
        """Test cleanup of old completed jobs."""
        # Create old completed job
        old_job = testcontainers_db_service.create_job(
            url="https://example.com/old",
            output_directory="/tmp/output",
        )
        testcontainers_db_service.update_job_status(old_job.id, JobStatus.COMPLETED)

        # Create recent job
        recent_job = testcontainers_db_service.create_job(
            url="https://example.com/recent",
            output_directory="/tmp/output",
        )
        testcontainers_db_service.update_job_status(recent_job.id, JobStatus.COMPLETED)

        # Manually set old completion date
        old_date = datetime.now(UTC) - timedelta(days=35)
        with testcontainers_db_service.get_session() as session:
            session.query(ScrapingJob).filter(ScrapingJob.id == old_job.id).update(
                {"completed_at": old_date}
            )

        # Cleanup jobs older than 30 days
        deleted_count = testcontainers_db_service.cleanup_old_jobs(days=30)
        assert deleted_count == 1

        # Verify old job was marked as cancelled (soft delete)
        updated_old_job = testcontainers_db_service.get_job(old_job.id)
        assert updated_old_job.status == JobStatus.CANCELLED

        # Recent job should remain completed
        updated_recent_job = testcontainers_db_service.get_job(recent_job.id)
        assert updated_recent_job.status == JobStatus.COMPLETED

    def test_cleanup_old_jobs_mixed_statuses(self, testcontainers_db_service):
        """Test cleanup with various job statuses."""
        now = datetime.now(UTC)
        old_date = now - timedelta(days=35)

        # Create old jobs with different statuses
        old_completed = testcontainers_db_service.create_job(
            url="https://example.com/old-completed",
            output_directory="/tmp/output",
        )
        testcontainers_db_service.update_job_status(old_completed.id, JobStatus.COMPLETED)

        old_failed = testcontainers_db_service.create_job(
            url="https://example.com/old-failed",
            output_directory="/tmp/output",
        )
        testcontainers_db_service.update_job_status(old_failed.id, JobStatus.FAILED)

        old_pending = testcontainers_db_service.create_job(
            url="https://example.com/old-pending",
            output_directory="/tmp/output",
        )
        # Leave as PENDING

        # Set old dates
        with testcontainers_db_service.get_session() as session:
            session.query(ScrapingJob).filter(
                ScrapingJob.id.in_([old_completed.id, old_failed.id])
            ).update({"completed_at": old_date})
            session.query(ScrapingJob).filter(ScrapingJob.id == old_pending.id).update(
                {"created_at": old_date}
            )

        # Cleanup
        deleted_count = testcontainers_db_service.cleanup_old_jobs(days=30)

        # Should only affect completed and failed jobs with old completed_at
        assert deleted_count == 2

        # Verify statuses
        assert testcontainers_db_service.get_job(old_completed.id).status == JobStatus.CANCELLED
        assert testcontainers_db_service.get_job(old_failed.id).status == JobStatus.CANCELLED
        assert (
            testcontainers_db_service.get_job(old_pending.id).status == JobStatus.PENDING
        )  # Unchanged

    def test_cleanup_old_jobs_no_old_jobs(self, testcontainers_db_service):
        """Test cleanup when no old jobs exist."""
        # Create only recent jobs
        job = testcontainers_db_service.create_job(
            url="https://example.com/recent",
            output_directory="/tmp/output",
        )
        testcontainers_db_service.update_job_status(job.id, JobStatus.COMPLETED)

        deleted_count = testcontainers_db_service.cleanup_old_jobs(days=30)
        assert deleted_count == 0

        # Job should remain unchanged
        assert testcontainers_db_service.get_job(job.id).status == JobStatus.COMPLETED


@pytest.mark.unit
class TestDatabaseServiceErrorHandling:
    """Database service error handling and transaction management."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock database session."""
        session = MagicMock(spec=Session)
        session.__enter__ = MagicMock(return_value=session)
        session.__exit__ = MagicMock(return_value=None)
        session.commit = MagicMock()
        session.rollback = MagicMock()
        session.close = MagicMock()
        session.flush = MagicMock()
        session.add = MagicMock()
        return session

    @pytest.fixture
    def mock_service(self, mock_session):
        """Create a database service with mocked dependencies."""
        with patch("src.database.service.create_database_engine") as mock_engine:
            with patch("src.database.service.sessionmaker") as mock_sessionmaker:
                mock_sessionmaker.return_value = MagicMock(return_value=mock_session)
                service = DatabaseService(echo=False)
                service.SessionLocal = MagicMock(return_value=mock_session)
                return service

    def test_database_error_handling_in_operations(self, testcontainers_db_service):
        """Test proper exception handling and DatabaseError wrapping."""
        # Mock session to raise SQLAlchemy error
        with patch.object(testcontainers_db_service, "get_session") as mock_session:
            from sqlalchemy.exc import SQLAlchemyError

            mock_session.side_effect = SQLAlchemyError("Database connection failed")

            # Should wrap in DatabaseError
            with pytest.raises(DatabaseError, match="Job creation failed"):
                testcontainers_db_service.create_job(
                    url="https://example.com/test",
                    output_directory="/tmp/output",
                )

    def test_integrity_error_handling(self, testcontainers_db_service):
        """Test handling of database integrity constraint violations."""
        with patch.object(testcontainers_db_service, "get_session") as mock_get_session:
            mock_session = MagicMock()
            mock_get_session.return_value.__enter__ = Mock(return_value=mock_session)
            mock_get_session.return_value.__exit__ = Mock(return_value=None)

            # Mock IntegrityError during flush
            mock_session.flush.side_effect = IntegrityError("UNIQUE constraint failed", None, None)

            with pytest.raises(DatabaseError, match="Job creation failed"):
                testcontainers_db_service.create_job(
                    url="https://example.com/test",
                    output_directory="/tmp/output",
                )

    def test_database_initialization_error(self):
        """Test database initialization error handling."""
        with patch("src.database.service.Base") as mock_base:
            from sqlalchemy.exc import SQLAlchemyError

            # Mock Base.metadata.create_all to fail
            mock_base.metadata.create_all.side_effect = SQLAlchemyError("Cannot create tables")

            service = DatabaseService()

            with pytest.raises(DatabaseError, match="Database initialization failed"):
                service.initialize_database()

    def test_get_job_database_error(self, testcontainers_db_service):
        """Test job retrieval with database error."""
        with patch.object(testcontainers_db_service, "get_session") as mock_session:
            mock_session.side_effect = SQLAlchemyError("Database error")

            with pytest.raises(DatabaseError, match="Job retrieval failed"):
                testcontainers_db_service.get_job(1)

    def test_update_job_status_database_error(self, testcontainers_db_service):
        """Test job status update with database error."""
        with patch.object(testcontainers_db_service, "get_session") as mock_session:
            mock_session.side_effect = SQLAlchemyError("Database error")

            with pytest.raises(DatabaseError, match="Job status update failed"):
                testcontainers_db_service.update_job_status(1, JobStatus.COMPLETED)

    def test_get_pending_jobs_database_error(self, testcontainers_db_service):
        """Test pending jobs retrieval with database error."""
        with patch.object(testcontainers_db_service, "get_session") as mock_session:
            mock_session.side_effect = SQLAlchemyError("Database error")

            with pytest.raises(DatabaseError, match="Pending jobs retrieval failed"):
                testcontainers_db_service.get_pending_jobs()

    def test_get_jobs_by_status_database_error(self, testcontainers_db_service):
        """Test jobs by status retrieval with database error."""
        with patch.object(testcontainers_db_service, "get_session") as mock_session:
            mock_session.side_effect = SQLAlchemyError("Database error")

            with pytest.raises(DatabaseError, match="Jobs retrieval failed"):
                testcontainers_db_service.get_jobs_by_status(JobStatus.COMPLETED)

    def test_get_retry_jobs_database_error(self, testcontainers_db_service):
        """Test retry jobs retrieval with database error."""
        with patch.object(testcontainers_db_service, "get_session") as mock_session:
            mock_session.side_effect = SQLAlchemyError("Database error")

            with pytest.raises(DatabaseError, match="Retry jobs retrieval failed"):
                testcontainers_db_service.get_retry_jobs()

    def test_create_batch_database_error(self, testcontainers_db_service):
        """Test batch creation with database error."""
        with patch.object(testcontainers_db_service, "get_session") as mock_session:
            mock_session.side_effect = SQLAlchemyError("Database error")

            with pytest.raises(DatabaseError, match="Batch creation failed"):
                testcontainers_db_service.create_batch(name="Test Batch")

    def test_get_batch_database_error(self, testcontainers_db_service):
        """Test batch retrieval with database error."""
        with patch.object(testcontainers_db_service, "get_session") as mock_session:
            mock_session.side_effect = SQLAlchemyError("Database error")

            with pytest.raises(DatabaseError, match="Batch retrieval failed"):
                testcontainers_db_service.get_batch(1)

    def test_update_batch_progress_database_error(self, testcontainers_db_service):
        """Test batch progress update with database error."""
        with patch.object(testcontainers_db_service, "get_session") as mock_session:
            mock_session.side_effect = SQLAlchemyError("Database error")

            with pytest.raises(DatabaseError, match="Batch progress update failed"):
                testcontainers_db_service.update_batch_progress(1)

    def test_save_content_result_database_error(self, testcontainers_db_service):
        """Test content result save with database error."""
        with patch.object(testcontainers_db_service, "get_session") as mock_session:
            mock_session.side_effect = SQLAlchemyError("Database error")

            with pytest.raises(DatabaseError, match="Content result save failed"):
                testcontainers_db_service.save_content_result(job_id=1)

    def test_add_job_log_exception_handling(self, testcontainers_db_service):
        """Test job log addition with various exceptions."""
        # Test with general exception (not just database error)
        with patch.object(testcontainers_db_service, "get_session") as mock_session:
            mock_session.side_effect = Exception("Unexpected error")

            # Should not raise, returns None
            log_entry = testcontainers_db_service.add_job_log(
                job_id=1,
                level="ERROR",
                message="Test",
            )
            assert log_entry is None

    def test_get_job_statistics_database_error(self, testcontainers_db_service):
        """Test statistics retrieval with database error."""
        with patch.object(testcontainers_db_service, "get_session") as mock_session:
            mock_session.side_effect = SQLAlchemyError("Database error")

            with pytest.raises(DatabaseError, match="Statistics retrieval failed"):
                testcontainers_db_service.get_job_statistics()

    def test_cleanup_old_jobs_database_error(self, testcontainers_db_service):
        """Test job cleanup with database error."""
        with patch.object(testcontainers_db_service, "get_session") as mock_session:
            mock_session.side_effect = SQLAlchemyError("Database error")

            with pytest.raises(DatabaseError, match="Job cleanup failed"):
                testcontainers_db_service.cleanup_old_jobs()


@pytest.mark.integration
class TestDatabaseServiceConcurrency:
    """Concurrency and thread safety tests."""

    def test_concurrent_access_handling(self, testcontainers_db_service, mock_time_sleep):
        """Test handling of concurrent database access."""
        # PostgreSQL supports concurrent access - this test should pass

        # Initialize database first
        testcontainers_db_service.initialize_database()

        results = []
        errors = []
        lock = threading.Lock()

        def create_job_worker(worker_id):
            try:
                # Add small delay to increase chance of concurrent access
                time.sleep(0.01)  # Mocked by mock_time_sleep fixture
                job = testcontainers_db_service.create_job(
                    url=f"https://example.com/test{worker_id}",
                    output_directory=f"/tmp/output{worker_id}",
                )
                with lock:
                    results.append(job.id)
            except Exception as e:
                with lock:
                    errors.append(e)

        # Create multiple threads to test concurrent access
        threads = []
        for i in range(10):
            thread = threading.Thread(target=create_job_worker, args=(i,))
            threads.append(thread)

        # Start all threads
        for thread in threads:
            thread.start()

        # Wait for completion
        for thread in threads:
            thread.join()

        # For real databases (PostgreSQL, MySQL), expect successful concurrent operations
        assert len(errors) == 0, f"Concurrent access should work for real databases: {errors}"
        assert len(results) == 10
        assert len(set(results)) == 10  # All unique IDs
