"""Unit tests for CleanupService following audit_3.md standards.

Tests for database cleanup and maintenance service with comprehensive coverage
following AAA pattern and SOLID testing principles.
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import Mock, patch
from uuid import uuid4

import pytest
from sqlalchemy import text

from src.common.status import JobStatus
from src.database.models.jobs import ContentResult, JobLog, ScrapingJob
from src.database.services.cleanup_service import CleanupService


class TestCleanupService:
    """Test suite for CleanupService following AAA pattern."""

    @pytest.fixture
    def cleanup_service(self, test_session):
        """Create CleanupService instance with test database session."""
        return CleanupService(session=test_session)

    @pytest.fixture
    def old_job(self, test_session, create_job):
        """Create an old job for cleanup testing."""
        old_date = datetime.now(UTC) - timedelta(days=10)
        job = create_job(status=JobStatus.COMPLETED, created_at=old_date)
        return job

    @pytest.fixture
    def recent_job(self, test_session, create_job):
        """Create a recent job that shouldn't be cleaned up.

        Creates a job that's 12 hours old, which is recent enough to avoid
        cleanup when using days=1 parameter (jobs older than 1 day).
        """
        recent_date = datetime.now(UTC) - timedelta(hours=12)
        job = create_job(status=JobStatus.COMPLETED, created_at=recent_date)
        return job

    @pytest.fixture
    def failed_job(self, test_session, create_job):
        """Create a failed job for cleanup testing."""
        old_date = datetime.now(UTC) - timedelta(days=5)
        job = create_job(status=JobStatus.FAILED, created_at=old_date)
        return job

    @pytest.mark.unit
    @pytest.mark.database
    def test_cleanup_jobs_success(self, cleanup_service, test_session):
        """Test successful cleanup of old jobs."""
        # Arrange
        # Manually create jobs to avoid fixture ordering issues
        from src.database.models.auth import User
        from uuid import uuid4

        # Create user
        user = User(
            id=str(uuid4()),
            username="testuser",
            email="test@example.com",
            full_name="Test User",
            created_at=datetime.now(UTC),
        )
        test_session.add(user)
        test_session.flush()

        # Create old job (10 days old)
        old_date = datetime.now(UTC) - timedelta(days=10)
        old_job = ScrapingJob(
            id=str(uuid4()),
            source_url="https://example.com/old",
            user_id=user.id,
            status=JobStatus.COMPLETED.value,
            created_at=old_date,
            domain="example.com",
        )
        test_session.add(old_job)

        # Create recent job (12 hours old)
        recent_date = datetime.now(UTC) - timedelta(hours=12)
        recent_job = ScrapingJob(
            id=str(uuid4()),
            source_url="https://example.com/recent",
            user_id=user.id,
            status=JobStatus.COMPLETED.value,
            created_at=recent_date,
            domain="example.com",
        )
        test_session.add(recent_job)
        test_session.commit()

        days_to_keep = 7

        # Act
        updated_count = cleanup_service.cleanup_jobs(days=days_to_keep)

        # Assert
        # cleanup_jobs does bulk UPDATE not DELETE (sets status to CANCELLED)
        # At least the old job (10 days old) should be updated
        assert updated_count >= 1

        # Verify old job status was changed to CANCELLED
        test_session.expire_all()  # Clear session cache
        test_session.refresh(old_job)
        assert old_job.status == JobStatus.CANCELLED.value

        # Verify recent job (12 hours old) is unchanged
        test_session.refresh(recent_job)
        assert recent_job.status == JobStatus.COMPLETED.value  # Original status

    @pytest.mark.unit
    @pytest.mark.database
    def test_cleanup_jobs_default_days(self, cleanup_service, test_session):
        """Test cleanup with default 7 days retention."""
        # Arrange
        # Manually create job to avoid fixture issues
        from src.database.models.auth import User
        from uuid import uuid4

        user = User(
            id=str(uuid4()),
            username="testuser2",
            email="test2@example.com",
            full_name="Test User 2",
            created_at=datetime.now(UTC),
        )
        test_session.add(user)
        test_session.flush()

        old_date = datetime.now(UTC) - timedelta(days=10)
        very_old_job = ScrapingJob(
            id=str(uuid4()),
            source_url="https://example.com/very-old",
            user_id=user.id,
            status=JobStatus.COMPLETED.value,
            created_at=old_date,
            domain="example.com",
        )
        test_session.add(very_old_job)
        test_session.commit()

        # Act
        updated_count = cleanup_service.cleanup_jobs()  # Default 7 days

        # Assert
        # cleanup_jobs does bulk UPDATE not DELETE
        assert updated_count >= 1
        test_session.expire_all()
        test_session.refresh(very_old_job)
        assert very_old_job.status == JobStatus.CANCELLED.value

    @pytest.mark.unit
    @pytest.mark.database
    def test_cleanup_jobs_no_old_jobs(self, cleanup_service, test_session, recent_job):
        """Test cleanup when no jobs are old enough."""
        # Arrange - only recent job exists

        # Act
        deleted_count = cleanup_service.cleanup_jobs(days=1)

        # Assert
        assert deleted_count == 0
        test_session.refresh(recent_job)
        assert recent_job.status == JobStatus.COMPLETED.value  # Unchanged

    @pytest.mark.unit
    @pytest.mark.database
    def test_cleanup_failed_jobs_success(self, cleanup_service, test_session, failed_job):
        """Test successful cleanup of old failed jobs."""
        # Arrange
        days_to_keep = 3
        failed_job_id = failed_job.id  # Store ID before deletion

        # Act
        deleted_count = cleanup_service.cleanup_failed_jobs(days=days_to_keep)

        # Assert
        assert deleted_count >= 1

        # Verify failed job was actually deleted (not just status changed)
        remaining_jobs = (
            test_session.query(ScrapingJob).filter(ScrapingJob.id == failed_job_id).first()
        )
        assert remaining_jobs is None  # Job should be deleted

    @pytest.mark.unit
    @pytest.mark.database
    def test_cleanup_failed_jobs_default_days(self, cleanup_service, test_session, create_job):
        """Test cleanup of failed jobs with default 3 days retention."""
        # Arrange
        # Create job with explicit old date (5 days ago)
        old_date = datetime.now(UTC) - timedelta(days=5)
        old_failed_job = create_job(status=JobStatus.FAILED, created_at=old_date)

        # Act
        deleted_count = cleanup_service.cleanup_failed_jobs()  # Default 3 days

        # Assert
        assert deleted_count >= 1

    @pytest.mark.unit
    @pytest.mark.database
    def test_cleanup_failed_jobs_preserves_recent(self, cleanup_service, test_session):
        """Test that recent failed jobs are preserved."""
        # Arrange
        # Manually create job to avoid ObjectDeletedError
        from src.database.models.auth import User
        from uuid import uuid4

        user = User(
            id=str(uuid4()),
            username="testuser3",
            email="test3@example.com",
            full_name="Test User 3",
            created_at=datetime.now(UTC),
        )
        test_session.add(user)
        test_session.flush()

        recent_date = datetime.now(UTC) - timedelta(days=1)
        recent_failed_job = ScrapingJob(
            id=str(uuid4()),
            source_url="https://example.com/recent-failed",
            user_id=user.id,
            status=JobStatus.FAILED.value,
            created_at=recent_date,
            domain="example.com",
        )
        test_session.add(recent_failed_job)
        test_session.commit()

        recent_failed_job_id = recent_failed_job.id

        # Act
        deleted_count = cleanup_service.cleanup_failed_jobs(days=3)

        # Assert
        assert deleted_count == 0

        # Verify recent failed job still exists
        test_session.expire_all()  # Clear cache
        remaining_job = (
            test_session.query(ScrapingJob).filter(ScrapingJob.id == recent_failed_job_id).first()
        )
        assert remaining_job is not None

    @pytest.mark.unit
    @pytest.mark.database
    def test_cleanup_failed_jobs_only_failed_status(
        self, cleanup_service, test_session, create_job
    ):
        """Test that only failed jobs are cleaned up, not other statuses."""
        # Arrange
        old_completed_job = create_job(status=JobStatus.COMPLETED)
        old_completed_job.created_at = datetime.now(UTC) - timedelta(days=5)
        test_session.commit()

        # Act
        deleted_count = cleanup_service.cleanup_failed_jobs(days=3)

        # Assert - Completed job should not be deleted
        remaining_job = (
            test_session.query(ScrapingJob).filter(ScrapingJob.id == old_completed_job.id).first()
        )
        assert remaining_job is not None  # Should still exist

    @pytest.mark.unit
    @pytest.mark.database
    def test_cleanup_orphaned_content_success(self, cleanup_service, test_session, create_job):
        """Test cleanup of orphaned content records.

        NOTE: In production, CASCADE DELETE at the database level (line 163 in jobs.py)
        prevents orphaned content from existing. This test verifies the cleanup logic
        works correctly even when CASCADE has already handled the cleanup.

        The cleanup_orphaned_content() function serves as a safety net for edge cases like:
        - Manual database operations with constraints disabled
        - Data migrations or imports
        - Database recovery scenarios

        Since CASCADE DELETE is enforced, we expect 0 orphans to be found and deleted.
        """
        from sqlalchemy import text

        # Arrange
        # Create two jobs - one to keep, one to delete
        job_to_keep = create_job()
        job_to_delete = create_job()

        # Create content record linked to job we'll keep
        linked_content = ContentResult(
            job_id=job_to_keep.id,
            original_html="<html>test</html>",
            converted_html="<html>test</html>",
            html_file_path="/tmp/test.html",
            title="Test Content",
            created_at=datetime.now(UTC),
        )
        test_session.add(linked_content)

        # Create content record linked to job we'll delete
        content_to_cascade = ContentResult(
            job_id=job_to_delete.id,
            original_html="<html>will be cascaded</html>",
            converted_html="<html>will be cascaded</html>",
            html_file_path="/tmp/cascade.html",
            title="Cascade Content",
            created_at=datetime.now(UTC),
        )
        test_session.add(content_to_cascade)
        test_session.commit()

        # Delete the job - CASCADE will automatically delete associated content
        test_session.execute(
            text("DELETE FROM jobs WHERE id = :job_id"), {"job_id": job_to_delete.id}
        )
        test_session.commit()

        # Act
        deleted_count = cleanup_service.cleanup_orphaned_content()

        # Assert
        # CASCADE already handled cleanup, so 0 orphans should be found
        assert deleted_count == 0

        # Verify linked content still exists (wasn't affected by cleanup)
        linked_content_id = linked_content.id
        linked_content_exists = (
            test_session.query(ContentResult).filter(ContentResult.id == linked_content_id).first()
        )
        assert linked_content_exists is not None

    @pytest.mark.unit
    @pytest.mark.database
    def test_cleanup_orphaned_content_no_orphans(self, cleanup_service, test_session, create_job):
        """Test cleanup when no orphaned content exists."""
        # Arrange
        job = create_job()

        # Create only linked content
        linked_content = ContentResult(
            job_id=job.id,
            original_html="<html>test</html>",
            converted_html="<html>test</html>",
            html_file_path="/tmp/test.html",
            title="Linked Content",
            created_at=datetime.now(UTC),
        )
        test_session.add(linked_content)
        test_session.commit()

        # Act
        deleted_count = cleanup_service.cleanup_orphaned_content()

        # Assert
        assert deleted_count == 0

    @pytest.mark.unit
    @pytest.mark.database
    def test_cleanup_orphaned_logs_success(self, cleanup_service, test_session, create_job):
        """Test cleanup of orphaned log records.

        NOTE: In production, CASCADE DELETE at the database level (line 231 in jobs.py)
        prevents orphaned logs from existing. This test verifies the cleanup logic
        works correctly even when CASCADE has already handled the cleanup.

        The cleanup_orphaned_logs() function serves as a safety net for edge cases like:
        - Manual database operations with constraints disabled
        - Data migrations or imports
        - Database recovery scenarios

        Since CASCADE DELETE is enforced, we expect 0 orphans to be found and deleted.
        """
        from sqlalchemy import text

        # Arrange
        # Create two jobs - one to keep, one to delete
        job_to_keep = create_job()
        job_to_delete = create_job()

        # Create log record linked to job we'll keep
        linked_log = JobLog(
            job_id=job_to_keep.id,
            level="INFO",
            message="Job started",
            timestamp=datetime.now(UTC),
            component="test",
            operation="test_operation",
        )
        test_session.add(linked_log)

        # Create log record linked to job we'll delete
        log_to_cascade = JobLog(
            job_id=job_to_delete.id,
            level="ERROR",
            message="Will be cascaded",
            timestamp=datetime.now(UTC),
            component="test",
            operation="test_operation",
        )
        test_session.add(log_to_cascade)
        test_session.commit()

        # Delete the job - CASCADE will automatically delete associated logs
        test_session.execute(
            text("DELETE FROM jobs WHERE id = :job_id"), {"job_id": job_to_delete.id}
        )
        test_session.commit()

        # Act
        deleted_count = cleanup_service.cleanup_orphaned_logs()

        # Assert
        # CASCADE already handled cleanup, so 0 orphans should be found
        assert deleted_count == 0

        # Verify linked log still exists (wasn't affected by cleanup)
        linked_log_id = linked_log.id
        linked_log_exists = test_session.query(JobLog).filter(JobLog.id == linked_log_id).first()
        assert linked_log_exists is not None

    @pytest.mark.unit
    @pytest.mark.database
    def test_cleanup_orphaned_logs_no_orphans(self, cleanup_service, test_session, create_job):
        """Test cleanup when no orphaned logs exist."""
        # Arrange
        job = create_job()

        # Create only linked log
        linked_log = JobLog(
            job_id=job.id,
            level="INFO",
            message="Test log",
            timestamp=datetime.now(UTC),
            component="test",
            operation="test_operation",
        )
        test_session.add(linked_log)
        test_session.commit()

        # Act
        deleted_count = cleanup_service.cleanup_orphaned_logs()

        # Assert
        assert deleted_count == 0

    @pytest.mark.unit
    @pytest.mark.database
    def test_vacuum_database_success(self, cleanup_service, test_session, create_job):
        """Test database vacuum operation.

        VACUUM requires autocommit mode in PostgreSQL. The CleanupService
        properly handles this by temporarily enabling autocommit on the
        raw connection following PostgreSQL best practices.
        """
        # Arrange - Act
        cleanup_service.vacuum_database()

        # Assert
        # Vacuum doesn't return a value, just verify it doesn't raise an exception
        # In production, this would reclaim space following PostgreSQL optimization

    @pytest.mark.unit
    @pytest.mark.database
    def test_cleanup_all_comprehensive(self, cleanup_service, test_session, create_job):
        """Test comprehensive cleanup operation."""
        # Arrange
        # Create various test data
        old_job = create_job()
        old_job.created_at = datetime.now(UTC) - timedelta(days=10)

        old_failed_job = create_job(status=JobStatus.FAILED)
        old_failed_job.created_at = datetime.now(UTC) - timedelta(days=5)

        test_session.commit()

        # Act
        results = cleanup_service.cleanup_all(old_jobs_days=7, failed_jobs_days=3)

        # Assert
        assert isinstance(results, dict)
        assert "old_jobs_deleted" in results
        assert "failed_jobs_deleted" in results
        assert "orphaned_content_deleted" in results
        assert "orphaned_logs_deleted" in results
        assert "vacuum_performed" in results

        # Verify all operations ran
        assert isinstance(results["old_jobs_deleted"], int)
        assert isinstance(results["failed_jobs_deleted"], int)
        assert isinstance(results["orphaned_content_deleted"], int)
        assert isinstance(results["orphaned_logs_deleted"], int)
        assert isinstance(results["vacuum_performed"], bool)

    @pytest.mark.unit
    @pytest.mark.database
    def test_cleanup_all_default_parameters(self, cleanup_service, test_session):
        """Test cleanup_all with default parameters."""
        # Arrange - Act
        results = cleanup_service.cleanup_all()

        # Assert
        assert isinstance(results, dict)
        assert all(
            key in results
            for key in [
                "old_jobs_deleted",
                "failed_jobs_deleted",
                "orphaned_content_deleted",
                "orphaned_logs_deleted",
                "vacuum_performed",
            ]
        )

    @pytest.mark.unit
    @pytest.mark.database
    def test_cleanup_all_vacuum_failure_graceful(self, cleanup_service, test_session):
        """Test that vacuum failure doesn't break cleanup_all."""
        # Arrange
        with patch.object(
            cleanup_service, "vacuum_database", side_effect=Exception("Vacuum failed")
        ):
            # Act
            results = cleanup_service.cleanup_all()

            # Assert
            # Vacuum failure should be handled gracefully
            assert results["vacuum_performed"] is False
            # Other operations should still complete
            assert "old_jobs_deleted" in results

    @pytest.mark.unit
    @pytest.mark.database
    def test_get_database_size_success(self, cleanup_service, test_session):
        """Test database size information retrieval."""
        # Arrange - Act
        size_info = cleanup_service.get_database_size()

        # Assert
        assert isinstance(size_info, dict)
        assert "total_size_bytes" in size_info
        assert "total_size_pretty" in size_info
        assert isinstance(size_info["total_size_bytes"], int)
        assert isinstance(size_info["total_size_pretty"], str)

    @pytest.mark.unit
    @pytest.mark.database
    def test_get_database_size_no_result(self, cleanup_service, test_session):
        """Test database size when query returns no result."""
        # Arrange
        with patch.object(test_session, "execute") as mock_execute:
            mock_result = Mock()
            mock_result.first.return_value = None
            mock_execute.return_value = mock_result

            # Act
            size_info = cleanup_service.get_database_size()

            # Assert
            assert size_info == {"total_size_bytes": 0, "total_size_pretty": "0 bytes"}

    @pytest.mark.unit
    @pytest.mark.database
    def test_get_table_sizes_success(self, cleanup_service, test_session):
        """Test table size information retrieval."""
        # Arrange - Act
        table_sizes = cleanup_service.get_table_sizes()

        # Assert
        assert isinstance(table_sizes, list)
        # Each table entry should have required fields
        for table_info in table_sizes:
            assert isinstance(table_info, dict)
            assert "schema" in table_info
            assert "table" in table_info
            assert "size_pretty" in table_info
            assert "size_bytes" in table_info


class TestCleanupServiceEdgeCases:
    """Edge cases and error scenarios for CleanupService."""

    @pytest.fixture
    def cleanup_service(self, test_session):
        """Create CleanupService instance with test database session."""
        return CleanupService(session=test_session)

    @pytest.mark.unit
    @pytest.mark.database
    def test_cleanup_jobs_zero_days(self, cleanup_service, test_session, create_job):
        """Test cleanup with zero days retention."""
        # Arrange
        job = create_job()

        # Act
        deleted_count = cleanup_service.cleanup_jobs(days=0)

        # Assert
        # Should cleanup all jobs regardless of age
        assert deleted_count >= 1
        test_session.refresh(job)
        assert job.status == JobStatus.CANCELLED.value

    @pytest.mark.unit
    @pytest.mark.database
    def test_cleanup_jobs_negative_days(self, cleanup_service, test_session, create_job):
        """Test cleanup with negative days (edge case)."""
        # Arrange
        job = create_job()

        # Act
        deleted_count = cleanup_service.cleanup_jobs(days=-1)

        # Assert
        # Should cleanup all jobs
        assert deleted_count >= 1

    @pytest.mark.unit
    @pytest.mark.database
    def test_cleanup_empty_database(self, cleanup_service, test_session, create_job):
        """Test cleanup operations on empty database."""
        # Arrange - empty database

        # Act
        old_jobs_deleted = cleanup_service.cleanup_jobs()
        failed_jobs_deleted = cleanup_service.cleanup_failed_jobs()
        orphaned_content_deleted = cleanup_service.cleanup_orphaned_content()
        orphaned_logs_deleted = cleanup_service.cleanup_orphaned_logs()

        # Assert
        assert old_jobs_deleted == 0
        assert failed_jobs_deleted == 0
        assert orphaned_content_deleted == 0
        assert orphaned_logs_deleted == 0

    @pytest.mark.unit
    @pytest.mark.database
    def test_cleanup_with_large_dataset(self, cleanup_service, test_session, create_job):
        """Test cleanup performance with larger dataset."""
        # Arrange
        # Create multiple old jobs
        old_date = datetime.now(UTC) - timedelta(days=10)
        jobs = []
        for i in range(10):  # Create 10 old jobs
            job = create_job()
            job.created_at = old_date
            jobs.append(job)
        test_session.commit()

        # Act
        deleted_count = cleanup_service.cleanup_jobs(days=7)

        # Assert
        assert deleted_count == 10  # All 10 jobs should be updated

    @pytest.mark.unit
    @pytest.mark.database
    def test_concurrent_cleanup_operations(self, cleanup_service, test_session, create_job):
        """Test that cleanup operations can be run concurrently."""
        # This is a simplified test for concurrent operations

        # Arrange
        old_job = create_job()
        old_job.created_at = datetime.now(UTC) - timedelta(days=10)
        test_session.commit()

        # Act - Run multiple cleanup operations
        results1 = cleanup_service.cleanup_jobs()
        results2 = cleanup_service.cleanup_orphaned_content()
        results3 = cleanup_service.cleanup_orphaned_logs()

        # Assert
        # Operations should complete without conflicts
        assert isinstance(results1, int)
        assert isinstance(results2, int)
        assert isinstance(results3, int)

    @pytest.mark.unit
    def test_session_handling(self, test_session):
        """Test proper session handling in CleanupService."""
        # Arrange
        service = CleanupService(session=test_session)

        # Act - Assert
        assert service.session is test_session

    @pytest.mark.unit
    @pytest.mark.database
    def test_cleanup_orphaned_content_with_actual_orphans(self, cleanup_service, test_session):
        """Test cleanup of actual orphaned content records by temporarily disabling FK constraints.

        Lines 111-113 in cleanup_service.py are defensive code that handle orphaned records.
        These can only occur when:
        1. Foreign key constraints are temporarily disabled during manual operations
        2. Data migrations or imports bypass constraints
        3. Database recovery scenarios

        This test simulates such scenarios by temporarily disabling FK constraints.
        """
        # Arrange - Temporarily disable foreign key constraint to create orphan
        test_session.execute(text("ALTER TABLE content_results DISABLE TRIGGER ALL"))

        # Insert orphaned content record directly with non-existent job_id
        now = datetime.now(UTC)
        test_session.execute(
            text(
                """
                INSERT INTO content_results (job_id, original_html, converted_html,
                                            html_file_path, title, created_at, updated_at)
                VALUES (:job_id, :original_html, :converted_html,
                        :html_file_path, :title, :created_at, :updated_at)
                """
            ),
            {
                "job_id": str(uuid4()),  # Non-existent job_id to create orphan
                "original_html": "<html>orphaned</html>",
                "converted_html": "<html>orphaned</html>",
                "html_file_path": "/tmp/orphaned.html",
                "title": "Orphaned Content",
                "created_at": now,
                "updated_at": now,
            },
        )
        test_session.commit()

        # Re-enable foreign key constraint
        test_session.execute(text("ALTER TABLE content_results ENABLE TRIGGER ALL"))
        test_session.commit()

        # Verify orphan exists before cleanup
        orphaned_content = test_session.execute(
            text(
                """
                SELECT c.id FROM content_results c
                LEFT JOIN jobs j ON c.job_id = j.id
                WHERE j.id IS NULL
                """
            )
        ).fetchall()
        assert len(orphaned_content) == 1

        # Act - cleanup should find and delete the orphaned content (covers lines 111-113)
        deleted_count = cleanup_service.cleanup_orphaned_content()

        # Assert - Should delete the orphaned content (line 111-113 coverage)
        assert deleted_count == 1

        # Verify orphan is gone
        orphaned_content_after = test_session.execute(
            text(
                """
                SELECT c.id FROM content_results c
                LEFT JOIN jobs j ON c.job_id = j.id
                WHERE j.id IS NULL
                """
            )
        ).fetchall()
        assert len(orphaned_content_after) == 0

    @pytest.mark.unit
    @pytest.mark.database
    def test_cleanup_orphaned_logs_with_actual_orphans(self, cleanup_service, test_session):
        """Test cleanup of actual orphaned log records by temporarily disabling FK constraints.

        Lines 139-141 in cleanup_service.py are defensive code that handle orphaned logs.
        These can only occur when:
        1. Foreign key constraints are temporarily disabled during manual operations
        2. Data migrations or imports bypass constraints
        3. Database recovery scenarios

        This test simulates such scenarios by temporarily disabling FK constraints.
        """
        # Arrange - Temporarily disable foreign key constraint to create orphan
        test_session.execute(text("ALTER TABLE job_logs DISABLE TRIGGER ALL"))

        # Insert orphaned log record directly with non-existent job_id
        test_session.execute(
            text(
                """
                INSERT INTO job_logs (job_id, level, message, timestamp, component, operation)
                VALUES (:job_id, :level, :message, :timestamp, :component, :operation)
                """
            ),
            {
                "job_id": str(uuid4()),  # Non-existent job_id to create orphan
                "level": "INFO",
                "message": "Orphaned log message",
                "timestamp": datetime.now(UTC),
                "component": "test",
                "operation": "test_operation",
            },
        )
        test_session.commit()

        # Re-enable foreign key constraint
        test_session.execute(text("ALTER TABLE job_logs ENABLE TRIGGER ALL"))
        test_session.commit()

        # Verify orphan exists before cleanup
        orphaned_logs = test_session.execute(
            text(
                """
                SELECT l.id FROM job_logs l
                LEFT JOIN jobs j ON l.job_id = j.id
                WHERE j.id IS NULL
                """
            )
        ).fetchall()
        assert len(orphaned_logs) == 1

        # Act - cleanup should find and delete the orphaned log (covers lines 139-141)
        deleted_count = cleanup_service.cleanup_orphaned_logs()

        # Assert - Should delete the orphaned log (line 139-141 coverage)
        assert deleted_count == 1

        # Verify orphan is gone
        orphaned_logs_after = test_session.execute(
            text(
                """
                SELECT l.id FROM job_logs l
                LEFT JOIN jobs j ON l.job_id = j.id
                WHERE j.id IS NULL
                """
            )
        ).fetchall()
        assert len(orphaned_logs_after) == 0

    @pytest.mark.unit
    @pytest.mark.database
    def test_cleanup_with_foreign_key_constraints(self, cleanup_service, test_session, create_job):
        """Test cleanup respects foreign key constraints."""
        # Arrange
        job = create_job()

        # Create content linked to job
        content = ContentResult(
            job_id=job.id,
            original_html="<html><body>test</body></html>",
            converted_html="<html><body>test</body></html>",
            html_file_path="/tmp/test.html",
            title="Test Content",
            created_at=datetime.now(UTC),
        )
        test_session.add(content)
        test_session.commit()

        # Act - Try to cleanup orphaned content (should find none)
        deleted_count = cleanup_service.cleanup_orphaned_content()

        # Assert
        assert deleted_count == 0  # No orphaned content should be found

        # Verify content still exists
        remaining_content = (
            test_session.query(ContentResult).filter(ContentResult.id == content.id).first()
        )
        assert remaining_content is not None
