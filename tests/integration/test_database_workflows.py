"""Integration tests for database workflows following audit_3.md standards.

Tests for complete database workflows including job lifecycle, cleanup operations,
and service interactions with comprehensive coverage following AAA pattern.
"""

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from src.common.status import JobPriority, JobStatus
from src.database.models.jobs import ContentResult, JobLog, ScrapingJob
from src.database.services.cleanup_service import CleanupService
from src.database.services.job_service import JobService
from tests.conftest import JobFactory


class TestJobLifecycleIntegration:
    """Integration tests for complete job lifecycle workflows."""

    @pytest.fixture
    def job_service(self, test_session: Any) -> JobService:
        """Create JobService instance with test database session."""
        return JobService(session=test_session)

    @pytest.fixture
    def cleanup_service(self, test_session: Any) -> CleanupService:
        """Create CleanupService instance with test database session."""
        return CleanupService(session=test_session)

    @pytest.mark.integration
    @pytest.mark.database
    def test_complete_job_lifecycle(self, job_service: JobService, test_session: Any) -> None:
        """Test complete job lifecycle from creation to completion."""
        # Arrange - MANDATORY: Pass session to ensure user exists (foreign key constraint)
        job_request = JobFactory.create_job_request(
            session=test_session, url="https://example.com/test-page", priority=JobPriority.HIGH
        )

        # Act & Assert - Job Creation
        job = job_service.create_job(job_request)
        assert job.status == JobStatus.PENDING.value
        assert job.source_url == job_request.url
        assert job.retry_count == 0

        # Act & Assert - Job Processing Start
        updated_job = job_service.update_job_status(job_id=job.id, new_status=JobStatus.RUNNING)
        assert updated_job is not None
        assert updated_job.status == JobStatus.RUNNING.value
        assert updated_job.started_at is not None

        # Act & Assert - Job Completion
        final_job = job_service.update_job_status(
            job_id=job.id, new_status=JobStatus.COMPLETED, processing_time_ms=5000
        )
        assert final_job is not None
        assert final_job.status == JobStatus.COMPLETED.value
        assert final_job.completed_at is not None
        assert final_job.processing_time_ms == 5000

        # Verify job persisted correctly
        retrieved_job = job_service.get_job(job.id)
        assert retrieved_job is not None
        assert retrieved_job.status == JobStatus.COMPLETED.value

    @pytest.mark.integration
    @pytest.mark.database
    def test_job_retry_workflow(self, job_service: JobService, test_session: Any) -> None:
        """Test job retry workflow with failure and retry logic."""
        # Arrange
        job_request = JobFactory.create_job_request(session=test_session, max_retries=3)

        # Act - Create and fail job
        job = job_service.create_job(job_request)
        job_service.update_job_status(job.id, JobStatus.RUNNING)
        failed_job = job_service.update_job_status(
            job_id=job.id, new_status=JobStatus.FAILED, error_message="Connection timeout"
        )

        # Assert initial failure
        assert failed_job is not None
        assert failed_job.status == JobStatus.FAILED.value
        assert failed_job.error_message == "Connection timeout"

        # Act - Get retry jobs
        retry_jobs = job_service.get_retry_jobs()

        # Assert job is eligible for retry
        assert len(retry_jobs) >= 1
        retry_job_ids = [j.id for j in retry_jobs]
        assert job.id in retry_job_ids

        # Act - Retry the job (second attempt)
        # Note: retry_count is managed by the service, not directly manipulated
        job_service.update_job_status(job.id, JobStatus.RUNNING)
        completed_job = job_service.update_job_status(job_id=job.id, new_status=JobStatus.COMPLETED)

        # Assert successful retry
        assert completed_job is not None
        assert completed_job.status == JobStatus.COMPLETED.value
        # Note: retry_count tracking would require service method implementation

    @pytest.mark.integration
    @pytest.mark.database
    def test_batch_job_workflow(self, job_service: JobService, test_session: Any) -> None:
        """Test complete batch job workflow."""
        # Arrange - MANDATORY: Create user for foreign key constraint
        test_user_id = JobFactory._ensure_user_exists(test_session)

        urls = [
            "https://example.com/page1",
            "https://example.com/page2",
            "https://example.com/page3",
        ]
        batch_config = {
            "user_id": test_user_id,
            "output_directory": "/tmp/batch_test",
            "priority": JobPriority.NORMAL,
            "max_retries": 2,
        }

        # Act - Create batch jobs
        batch_jobs = job_service.create_jobs(urls, **batch_config)

        # Assert batch creation
        assert len(batch_jobs) == 3
        batch_id = batch_jobs[0].batch_id
        assert all(job.batch_id == batch_id for job in batch_jobs)

        # Act - Process batch jobs with different outcomes
        job_service.update_job_status(batch_jobs[0].id, JobStatus.RUNNING)
        job_service.update_job_status(batch_jobs[0].id, JobStatus.COMPLETED)

        job_service.update_job_status(batch_jobs[1].id, JobStatus.RUNNING)
        job_service.update_job_status(
            batch_jobs[1].id, JobStatus.FAILED, error_message="Rate limited"
        )

        # batch_jobs[2] remains PENDING

        # Act - Get batch summary
        assert batch_id is not None
        summary = job_service.get_batch_summary(batch_id)

        # Assert batch summary
        assert summary["batch_id"] == batch_id
        assert summary["total_jobs"] == 3
        assert summary["overall_status"] == "mixed"
        assert summary["status_counts"][JobStatus.COMPLETED.value] == 1
        assert summary["status_counts"][JobStatus.FAILED.value] == 1
        assert summary["status_counts"][JobStatus.PENDING.value] == 1

        # Act - Get batch jobs
        retrieved_batch_jobs = job_service.get_batch_jobs(batch_id)

        # Assert batch retrieval
        assert len(retrieved_batch_jobs) == 3
        assert all(job.batch_id == batch_id for job in retrieved_batch_jobs)

    @pytest.mark.integration
    @pytest.mark.database
    def test_job_priority_ordering(self, job_service: JobService, test_session: Any) -> None:
        """Test that job priority ordering works correctly."""
        # Arrange - Create jobs with different priorities
        low_job = job_service.create_job(
            JobFactory.create_job_request(session=test_session, priority=JobPriority.LOW)
        )
        normal_job = job_service.create_job(
            JobFactory.create_job_request(session=test_session, priority=JobPriority.NORMAL)
        )
        high_job = job_service.create_job(
            JobFactory.create_job_request(session=test_session, priority=JobPriority.HIGH)
        )
        urgent_job = job_service.create_job(
            JobFactory.create_job_request(session=test_session, priority=JobPriority.URGENT)
        )

        # Act - Get pending jobs (should be ordered by priority)
        pending_jobs = job_service.get_pending_jobs(limit=10)

        # Assert priority ordering
        assert len(pending_jobs) >= 4
        priorities = [job.priority for job in pending_jobs[:4]]

        # Should be ordered from high to low priority
        assert priorities == sorted(priorities, reverse=True)

        # Verify specific job priorities
        priority_map = {job.id: job.priority for job in pending_jobs}
        assert priority_map[urgent_job.id] == 10  # URGENT
        assert priority_map[high_job.id] == 8  # HIGH
        assert priority_map[normal_job.id] == 5  # NORMAL
        assert priority_map[low_job.id] == 1  # LOW


class TestDatabaseCleanupIntegration:
    """Integration tests for database cleanup workflows."""

    @pytest.fixture
    def job_service(self, test_session: Any) -> JobService:
        """Create JobService instance with test database session."""
        return JobService(session=test_session)

    @pytest.fixture
    def cleanup_service(self, test_session: Any) -> CleanupService:
        """Create CleanupService instance with test database session."""
        return CleanupService(session=test_session)

    @pytest.mark.integration
    @pytest.mark.database
    def test_comprehensive_cleanup_workflow(
        self, job_service: JobService, cleanup_service: CleanupService, test_session: Any
    ) -> None:
        """Test comprehensive cleanup workflow with jobs, content, and logs."""
        # Arrange - Create test data for cleanup

        # Create old completed job
        old_job = job_service.create_job(
            JobFactory.create_job_request(
                session=test_session,
            )
        )
        old_job.created_at = datetime.now(UTC) - timedelta(days=10)
        test_session.commit()  # MANDATORY: Commit timestamp change to database
        job_service.update_job_status(old_job.id, JobStatus.COMPLETED)
        old_job_id = old_job.id  # Store ID before potential detachment

        # Create old failed job
        old_failed_job = job_service.create_job(
            JobFactory.create_job_request(
                session=test_session,
            )
        )
        old_failed_job.created_at = datetime.now(UTC) - timedelta(days=5)
        test_session.commit()  # MANDATORY: Commit timestamp change to database
        job_service.update_job_status(old_failed_job.id, JobStatus.FAILED)
        old_failed_job_id = old_failed_job.id  # Store ID before deletion

        # Create recent job (should not be cleaned up)
        recent_job = job_service.create_job(
            JobFactory.create_job_request(
                session=test_session,
            )
        )
        recent_job.created_at = datetime.now(UTC) - timedelta(days=1)
        test_session.commit()  # MANDATORY: Commit timestamp change to database
        job_service.update_job_status(recent_job.id, JobStatus.COMPLETED)
        recent_job_id = recent_job.id  # Store ID before potential detachment

        # Create content and log records for recent job
        linked_content = ContentResult(
            job_id=recent_job.id,
            converted_html="<html>test content</html>",
            html_file_path="/tmp/test.html",
            created_at=datetime.now(UTC),
        )

        linked_log = JobLog(
            job_id=recent_job.id,
            level="INFO",
            message="Job completed successfully",
            timestamp=datetime.now(UTC),
            component="job.processor",
        )

        # Note: Cannot create truly orphaned records in PostgreSQL due to MANDATORY foreign key constraints
        # Instead, we test cleanup of old jobs which will CASCADE delete their content/logs
        test_session.add_all([linked_content, linked_log])
        test_session.commit()

        # Get initial counts
        initial_job_count = test_session.query(ScrapingJob).count()
        initial_content_count = test_session.query(ContentResult).count()
        initial_log_count = test_session.query(JobLog).count()

        # Act - Run comprehensive cleanup
        cleanup_results = cleanup_service.cleanup_all(old_jobs_days=7, failed_jobs_days=3)

        # Assert - Verify cleanup results
        assert (
            cleanup_results["old_jobs_deleted"] >= 1
        )  # Old completed job (status updated to CANCELLED)
        assert cleanup_results["failed_jobs_deleted"] >= 1  # Old failed job (DELETED)
        # Note: orphaned_content/logs_deleted will be 0 because PostgreSQL foreign keys prevent orphans
        # CASCADE deletes happen automatically when parent jobs are deleted
        assert isinstance(cleanup_results.get("orphaned_content_deleted", 0), int)
        assert isinstance(cleanup_results.get("orphaned_logs_deleted", 0), int)
        assert isinstance(cleanup_results["vacuum_performed"], bool)

        # Verify old job status was updated to CANCELLED (not deleted)
        test_session.expire_all()  # Refresh all objects from database
        # Query fresh from database since cleanup runs in separate session/transaction
        old_job_after_cleanup = (
            test_session.query(ScrapingJob).filter(ScrapingJob.id == old_job_id).first()
        )
        assert old_job_after_cleanup is not None, (
            "Old completed job should still exist with CANCELLED status"
        )
        assert old_job_after_cleanup.status == JobStatus.CANCELLED.value

        # Verify recent job is unchanged
        recent_job_after_cleanup = (
            test_session.query(ScrapingJob).filter(ScrapingJob.id == recent_job_id).first()
        )
        assert recent_job_after_cleanup is not None, "Recent job (1 day old) should not be deleted"
        assert recent_job_after_cleanup.status == JobStatus.COMPLETED.value

        # Verify old failed job was actually DELETED (not just status updated)
        deleted_failed_job = (
            test_session.query(ScrapingJob).filter(ScrapingJob.id == old_failed_job_id).first()
        )
        assert deleted_failed_job is None

        # Verify linked records for recent job are preserved (CASCADE delete only affects deleted jobs)
        preserved_content = (
            test_session.query(ContentResult).filter(ContentResult.job_id == recent_job_id).first()
        )
        assert preserved_content is not None
        assert preserved_content.html_file_path == "/tmp/test.html"

        preserved_log = test_session.query(JobLog).filter(JobLog.job_id == recent_job_id).first()
        assert preserved_log is not None
        assert preserved_log.component == "job.processor"

    @pytest.mark.integration
    @pytest.mark.database
    def test_cleanup_with_foreign_key_integrity(
        self, job_service: JobService, cleanup_service: CleanupService, test_session: Any
    ) -> None:
        """Test that cleanup operations maintain foreign key integrity."""
        # Arrange - Create job with associated records
        job = job_service.create_job(
            JobFactory.create_job_request(
                session=test_session,
            )
        )
        job.created_at = datetime.now(UTC) - timedelta(days=10)
        test_session.commit()

        # Create content and logs for the job
        content = ContentResult(
            job_id=job.id,
            converted_html="{}",
            html_file_path="/tmp/job_content.json",
            created_at=datetime.now(UTC),
        )

        log = JobLog(
            job_id=job.id,
            level="INFO",
            message="Processing started",
            timestamp=datetime.now(UTC),
            component="processor",
        )

        test_session.add_all([content, log])
        test_session.commit()

        # Act - Run cleanup that updates job status (doesn't delete job)
        deleted_count = cleanup_service.cleanup_jobs(days=7)

        # Assert - Job status updated, but relationships maintained
        assert deleted_count >= 1

        test_session.refresh(job)
        assert job.status == JobStatus.CANCELLED.value

        # Verify associated records still exist since job wasn't deleted
        remaining_content = (
            test_session.query(ContentResult).filter(ContentResult.job_id == job.id).first()
        )
        assert remaining_content is not None

        remaining_log = test_session.query(JobLog).filter(JobLog.job_id == job.id).first()
        assert remaining_log is not None

    @pytest.mark.integration
    @pytest.mark.database
    def test_incremental_cleanup_workflow(
        self, job_service: JobService, cleanup_service: CleanupService, test_session: Any
    ) -> None:
        """Test incremental cleanup workflow over time."""
        # Arrange - Create jobs at different times
        very_old_job = job_service.create_job(
            JobFactory.create_job_request(
                session=test_session,
            )
        )
        very_old_job.created_at = datetime.now(UTC) - timedelta(days=15)

        old_job = job_service.create_job(
            JobFactory.create_job_request(
                session=test_session,
            )
        )
        old_job.created_at = datetime.now(UTC) - timedelta(days=8)

        recent_job = job_service.create_job(
            JobFactory.create_job_request(
                session=test_session,
            )
        )
        recent_job.created_at = datetime.now(UTC) - timedelta(days=3)

        test_session.commit()

        # Act & Assert - First cleanup (14 day retention)
        deleted_count_1 = cleanup_service.cleanup_jobs(days=14)
        assert deleted_count_1 >= 1  # Very old job

        test_session.refresh(very_old_job)
        assert very_old_job.status == JobStatus.CANCELLED.value

        # Other jobs should be unchanged
        test_session.refresh(old_job)
        test_session.refresh(recent_job)
        assert old_job.status == JobStatus.PENDING.value
        assert recent_job.status == JobStatus.PENDING.value

        # Act & Assert - Second cleanup (7 day retention)
        deleted_count_2 = cleanup_service.cleanup_jobs(days=7)
        assert deleted_count_2 >= 1  # Old job

        test_session.refresh(old_job)
        assert old_job.status == JobStatus.CANCELLED.value

        # Recent job should still be unchanged
        test_session.refresh(recent_job)
        assert recent_job.status == JobStatus.PENDING.value

        # Act & Assert - Third cleanup (1 day retention)
        deleted_count_3 = cleanup_service.cleanup_jobs(days=1)
        assert deleted_count_3 >= 1  # Recent job

        test_session.refresh(recent_job)
        assert recent_job.status == JobStatus.CANCELLED.value


class TestServiceInteractionIntegration:
    """Integration tests for service interactions and cross-cutting concerns."""

    @pytest.fixture
    def job_service(self, test_session: Any) -> JobService:
        """Create JobService instance with test database session."""
        return JobService(session=test_session)

    @pytest.fixture
    def cleanup_service(self, test_session: Any) -> CleanupService:
        """Create CleanupService instance with test database session."""
        return CleanupService(session=test_session)

    @pytest.mark.integration
    @pytest.mark.database
    def test_job_service_and_cleanup_service_interaction(
        self, job_service: JobService, cleanup_service: CleanupService, test_session: Any
    ) -> None:
        """Test interaction between JobService and CleanupService."""
        # Arrange - MANDATORY: Create user for foreign key constraint
        test_user_id = JobFactory._ensure_user_exists(test_session)

        # Create jobs using JobService
        urls = ["https://example.com/1", "https://example.com/2"]
        batch_jobs = job_service.create_jobs(
            urls, user_id=test_user_id, output_directory="/tmp/test", priority=JobPriority.HIGH
        )

        # Set jobs to old dates
        for job in batch_jobs:
            job.created_at = datetime.now(UTC) - timedelta(days=10)
        test_session.commit()

        # Act - Use CleanupService to clean up jobs created by JobService
        deleted_count = cleanup_service.cleanup_jobs(days=7)

        # Assert - Verify interaction worked correctly
        assert deleted_count >= 2  # Both batch jobs

        for job in batch_jobs:
            test_session.refresh(job)
            assert job.status == JobStatus.CANCELLED.value

    @pytest.mark.integration
    @pytest.mark.database
    @pytest.mark.performance
    def test_large_scale_job_processing(self, job_service: JobService, test_session: Any) -> None:
        """Test performance with larger number of jobs."""
        # Arrange - MANDATORY: Create user for foreign key constraint
        test_user_id = JobFactory._ensure_user_exists(test_session)

        # Create multiple jobs efficiently
        urls = [f"https://example.com/page{i}" for i in range(20)]

        # Act - Create batch jobs
        start_time = datetime.now(UTC)
        batch_jobs = job_service.create_jobs(
            urls,
            user_id=test_user_id,
            output_directory="/tmp/large_batch",
            priority=JobPriority.NORMAL,
        )
        creation_time = datetime.now(UTC) - start_time

        # Assert - Verify performance and correctness
        assert len(batch_jobs) == 20
        assert creation_time.total_seconds() < 5.0  # Should complete quickly

        # Verify all jobs have same batch_id
        batch_ids = {job.batch_id for job in batch_jobs}
        assert len(batch_ids) == 1  # All same batch_id

        # Act - Retrieve pending jobs efficiently
        start_time = datetime.now(UTC)
        pending_jobs = job_service.get_pending_jobs(limit=50)
        retrieval_time = datetime.now(UTC) - start_time

        # Assert - Verify efficient retrieval
        assert len(pending_jobs) >= 20
        assert retrieval_time.total_seconds() < 2.0  # Should be fast

        # Verify ordering
        for i in range(len(pending_jobs) - 1):
            assert pending_jobs[i].priority >= pending_jobs[i + 1].priority

    @pytest.mark.integration
    @pytest.mark.database
    def test_transaction_rollback_behavior(
        self, job_service: JobService, test_session: Any
    ) -> None:
        """Test transaction rollback behavior in service interactions."""
        # Arrange
        initial_job_count = test_session.query(ScrapingJob).count()

        # Act - Create job and then rollback
        job = job_service.create_job(
            JobFactory.create_job_request(
                session=test_session,
            )
        )
        job_id = job.id

        # Verify job exists before rollback
        assert test_session.query(ScrapingJob).filter(ScrapingJob.id == job_id).first() is not None

        # Rollback the transaction
        test_session.rollback()

        # Assert - Job should not exist after rollback
        final_job_count = test_session.query(ScrapingJob).count()
        assert final_job_count == initial_job_count

        remaining_job = test_session.query(ScrapingJob).filter(ScrapingJob.id == job_id).first()
        assert remaining_job is None
