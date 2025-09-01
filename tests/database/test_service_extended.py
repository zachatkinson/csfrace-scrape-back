"""Extended tests for database service layer to improve coverage.

This module provides additional comprehensive tests for untested code paths
and edge cases in the database service module.
"""

import os
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, Mock, patch

import pytest
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from src.core.exceptions import DatabaseError
from src.database.models import (
    Batch,
    ContentResult,
    JobLog,
    JobPriority,
    JobStatus,
    ScrapingJob,
)
from src.database.service import DatabaseService


@pytest.mark.database
class TestDatabaseServiceExtended:
    """Extended test coverage for database service operations."""

    @pytest.fixture
    def temp_db_service(self, postgres_container):
        """Create temporary database service for testing with PostgreSQL."""
        # Set environment variables for PostgreSQL connection
        os.environ["DATABASE_HOST"] = postgres_container.get_container_host_ip()
        os.environ["DATABASE_PORT"] = str(postgres_container.get_exposed_port(5432))
        os.environ["DATABASE_NAME"] = postgres_container.dbname
        os.environ["DATABASE_USER"] = postgres_container.username
        os.environ["DATABASE_PASSWORD"] = postgres_container.password

        try:
            # Create database service using PostgreSQL
            service = DatabaseService(echo=False)
            service.initialize_database()

            # Clean up database state before each test
            with service.get_session() as session:
                session.query(ContentResult).delete()
                session.query(JobLog).delete()
                session.query(ScrapingJob).delete()
                session.query(Batch).delete()
                session.commit()

            yield service
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

    def test_create_job_with_invalid_priority_string(self, temp_db_service):
        """Test job creation with invalid priority string defaults to NORMAL."""
        job = temp_db_service.create_job(
            url="https://example.com/test",
            output_directory="/tmp/output",
            priority="invalid_priority",  # Invalid priority
        )

        assert job.priority == JobPriority.NORMAL

    def test_create_job_with_priority_enum(self, temp_db_service):
        """Test job creation with JobPriority enum directly."""
        job = temp_db_service.create_job(
            url="https://example.com/test",
            output_directory="/tmp/output",
            priority=JobPriority.URGENT,  # Pass enum directly
        )

        assert job.priority == JobPriority.URGENT

    def test_create_job_url_parsing_edge_cases(self, temp_db_service):
        """Test URL parsing for various edge cases."""
        # URL with query parameters
        job1 = temp_db_service.create_job(
            url="https://example.com/path?query=param",
            output_directory="/tmp/output",
        )
        assert job1.domain == "example.com"
        assert job1.slug == "path"

        # URL with fragment
        job2 = temp_db_service.create_job(
            url="https://example.com/article#section",
            output_directory="/tmp/output",
        )
        assert job2.slug == "article"

        # URL with multiple path segments
        job3 = temp_db_service.create_job(
            url="https://example.com/blog/2024/01/post",
            output_directory="/tmp/output",
        )
        assert job3.slug == "post"

        # URL with no path after domain
        job4 = temp_db_service.create_job(
            url="https://example.com",
            output_directory="/tmp/output",
        )
        assert job4.slug == "homepage"

        # URL with trailing slash
        job5 = temp_db_service.create_job(
            url="https://example.com/page/",
            output_directory="/tmp/output",
        )
        assert job5.slug == "page"

    def test_create_job_with_custom_slug_kwarg(self, temp_db_service):
        """Test job creation with custom_slug in kwargs."""
        job = temp_db_service.create_job(
            url="https://example.com/test",
            output_directory="/tmp/output",
            custom_slug="my-custom-slug",
        )
        # When custom_slug is provided in kwargs, auto-extraction is skipped, slug remains None
        # This tests the condition: if not slug and not kwargs.get("custom_slug")
        assert job.slug is None  # Slug extraction skipped due to custom_slug in kwargs

    def test_create_job_database_error(self, temp_db_service):
        """Test job creation with database error."""
        with patch.object(temp_db_service, "get_session") as mock_session:
            mock_session.side_effect = SQLAlchemyError("Database error")

            with pytest.raises(DatabaseError, match="Job creation failed"):
                temp_db_service.create_job(
                    url="https://example.com/test",
                    output_directory="/tmp/output",
                )

    def test_get_job_database_error(self, temp_db_service):
        """Test job retrieval with database error."""
        with patch.object(temp_db_service, "get_session") as mock_session:
            mock_session.side_effect = SQLAlchemyError("Database error")

            with pytest.raises(DatabaseError, match="Job retrieval failed"):
                temp_db_service.get_job(1)

    def test_update_job_status_to_cancelled(self, temp_db_service):
        """Test updating job status to cancelled."""
        job = temp_db_service.create_job(
            url="https://example.com/test",
            output_directory="/tmp/output",
        )

        success = temp_db_service.update_job_status(job.id, JobStatus.CANCELLED)
        assert success is True

        updated_job = temp_db_service.get_job(job.id)
        assert updated_job.status == JobStatus.CANCELLED
        assert updated_job.completed_at is not None

    def test_update_job_status_database_error(self, temp_db_service):
        """Test job status update with database error."""
        with patch.object(temp_db_service, "get_session") as mock_session:
            mock_session.side_effect = SQLAlchemyError("Database error")

            with pytest.raises(DatabaseError, match="Job status update failed"):
                temp_db_service.update_job_status(1, JobStatus.COMPLETED)

    def test_get_pending_jobs_database_error(self, temp_db_service):
        """Test pending jobs retrieval with database error."""
        with patch.object(temp_db_service, "get_session") as mock_session:
            mock_session.side_effect = SQLAlchemyError("Database error")

            with pytest.raises(DatabaseError, match="Pending jobs retrieval failed"):
                temp_db_service.get_pending_jobs()

    def test_get_pending_jobs_priority_ordering_edge_case(self, temp_db_service):
        """Test pending jobs with same priority ordered by creation time."""
        # Create jobs with same priority but different creation times
        job1 = temp_db_service.create_job(
            url="https://example.com/first",
            output_directory="/tmp/output1",
            priority="normal",
        )

        # Simulate time passing
        import time

        time.sleep(0.01)

        job2 = temp_db_service.create_job(
            url="https://example.com/second",
            output_directory="/tmp/output2",
            priority="normal",
        )

        pending_jobs = temp_db_service.get_pending_jobs()
        assert len(pending_jobs) == 2
        # First created job should come first when priorities are equal
        assert pending_jobs[0].id == job1.id
        assert pending_jobs[1].id == job2.id

    def test_get_jobs_by_status_with_pagination(self, temp_db_service):
        """Test job retrieval by status with offset pagination."""
        # Create multiple jobs
        for i in range(10):
            job = temp_db_service.create_job(
                url=f"https://example.com/test{i}",
                output_directory=f"/tmp/output{i}",
            )
            temp_db_service.update_job_status(job.id, JobStatus.COMPLETED)

        # Get first page
        first_page = temp_db_service.get_jobs_by_status(JobStatus.COMPLETED, limit=5, offset=0)
        assert len(first_page) == 5

        # Get second page
        second_page = temp_db_service.get_jobs_by_status(JobStatus.COMPLETED, limit=5, offset=5)
        assert len(second_page) == 5

        # Verify no overlap
        first_page_ids = {job.id for job in first_page}
        second_page_ids = {job.id for job in second_page}
        assert first_page_ids.isdisjoint(second_page_ids)

    def test_get_jobs_by_status_database_error(self, temp_db_service):
        """Test jobs by status retrieval with database error."""
        with patch.object(temp_db_service, "get_session") as mock_session:
            mock_session.side_effect = SQLAlchemyError("Database error")

            with pytest.raises(DatabaseError, match="Jobs retrieval failed"):
                temp_db_service.get_jobs_by_status(JobStatus.COMPLETED)

    def test_get_retry_jobs_database_error(self, temp_db_service):
        """Test retry jobs retrieval with database error."""
        with patch.object(temp_db_service, "get_session") as mock_session:
            mock_session.side_effect = SQLAlchemyError("Database error")

            with pytest.raises(DatabaseError, match="Retry jobs retrieval failed"):
                temp_db_service.get_retry_jobs()

    def test_get_retry_jobs_null_next_retry_at(self, temp_db_service):
        """Test retry jobs with null next_retry_at (should be eligible)."""
        job = temp_db_service.create_job(
            url="https://example.com/test",
            output_directory="/tmp/output",
            max_retries=3,
        )

        temp_db_service.update_job_status(job.id, JobStatus.FAILED)

        # Ensure next_retry_at is None
        with temp_db_service.get_session() as session:
            session.query(ScrapingJob).filter(ScrapingJob.id == job.id).update(
                {"retry_count": 1, "next_retry_at": None}
            )

        retry_jobs = temp_db_service.get_retry_jobs()
        assert len(retry_jobs) == 1
        assert retry_jobs[0].id == job.id

    def test_create_batch_database_error(self, temp_db_service):
        """Test batch creation with database error."""
        with patch.object(temp_db_service, "get_session") as mock_session:
            mock_session.side_effect = SQLAlchemyError("Database error")

            with pytest.raises(DatabaseError, match="Batch creation failed"):
                temp_db_service.create_batch(name="Test Batch")

    def test_get_batch_database_error(self, temp_db_service):
        """Test batch retrieval with database error."""
        with patch.object(temp_db_service, "get_session") as mock_session:
            mock_session.side_effect = SQLAlchemyError("Database error")

            with pytest.raises(DatabaseError, match="Batch retrieval failed"):
                temp_db_service.get_batch(1)

    def test_update_batch_progress_nonexistent_batch(self, temp_db_service):
        """Test updating progress for non-existent batch."""
        success = temp_db_service.update_batch_progress(99999)
        assert success is False

    def test_update_batch_progress_database_error(self, temp_db_service):
        """Test batch progress update with database error."""
        with patch.object(temp_db_service, "get_session") as mock_session:
            mock_session.side_effect = SQLAlchemyError("Database error")

            with pytest.raises(DatabaseError, match="Batch progress update failed"):
                temp_db_service.update_batch_progress(1)

    def test_update_batch_progress_with_all_job_states(self, temp_db_service):
        """Test batch progress update with various job states."""
        batch = temp_db_service.create_batch(name="Test Batch")

        # Create jobs in different states
        jobs = []
        for i in range(10):
            job = temp_db_service.create_job(
                url=f"https://example.com/test{i}",
                output_directory=f"/tmp/output{i}",
                batch_id=batch.id,
            )
            jobs.append(job)

        # Set various states
        temp_db_service.update_job_status(jobs[0].id, JobStatus.COMPLETED)
        temp_db_service.update_job_status(jobs[1].id, JobStatus.COMPLETED)
        temp_db_service.update_job_status(jobs[2].id, JobStatus.COMPLETED)
        temp_db_service.update_job_status(jobs[3].id, JobStatus.FAILED)
        temp_db_service.update_job_status(jobs[4].id, JobStatus.FAILED)
        temp_db_service.update_job_status(jobs[5].id, JobStatus.SKIPPED)
        temp_db_service.update_job_status(jobs[6].id, JobStatus.RUNNING)
        temp_db_service.update_job_status(jobs[7].id, JobStatus.CANCELLED)
        # jobs[8] and jobs[9] remain PENDING

        # Update batch progress
        success = temp_db_service.update_batch_progress(batch.id)
        assert success is True

        # Verify counts
        updated_batch = temp_db_service.get_batch(batch.id)
        assert updated_batch.total_jobs == 10
        assert updated_batch.completed_jobs == 3
        assert updated_batch.failed_jobs == 2
        assert updated_batch.skipped_jobs == 1
        # RUNNING, CANCELLED, and PENDING are not counted in these specific fields

    def test_save_content_result_minimal(self, temp_db_service):
        """Test saving content result with minimal data."""
        job = temp_db_service.create_job(
            url="https://example.com/test",
            output_directory="/tmp/output",
        )

        # Save with minimal data
        content_result = temp_db_service.save_content_result(job_id=job.id)

        assert content_result.id is not None
        assert content_result.job_id == job.id
        assert content_result.converted_html is None
        assert content_result.title is None

    def test_save_content_result_database_error(self, temp_db_service):
        """Test content result save with database error."""
        with patch.object(temp_db_service, "get_session") as mock_session:
            mock_session.side_effect = SQLAlchemyError("Database error")

            with pytest.raises(DatabaseError, match="Content result save failed"):
                temp_db_service.save_content_result(job_id=1)

    def test_save_content_result_with_empty_metadata(self, temp_db_service):
        """Test saving content result with empty metadata dictionary."""
        job = temp_db_service.create_job(
            url="https://example.com/test",
            output_directory="/tmp/output",
        )

        content_result = temp_db_service.save_content_result(
            job_id=job.id,
            html_content="<p>Content</p>",
            metadata={},  # Empty metadata
            file_paths={},  # Empty file paths
        )

        assert content_result.id is not None
        assert content_result.title is None
        assert content_result.html_file_path is None

    def test_add_job_log_with_null_context(self, temp_db_service):
        """Test adding job log with null context data."""
        job = temp_db_service.create_job(
            url="https://example.com/test",
            output_directory="/tmp/output",
        )

        log_entry = temp_db_service.add_job_log(
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

    def test_add_job_log_exception_handling(self, temp_db_service):
        """Test job log addition with various exceptions."""
        # Test with general exception (not just database error)
        with patch.object(temp_db_service, "get_session") as mock_session:
            mock_session.side_effect = Exception("Unexpected error")

            # Should not raise, returns None
            log_entry = temp_db_service.add_job_log(
                job_id=1,
                level="ERROR",
                message="Test",
            )
            assert log_entry is None

    def test_get_job_statistics_with_null_values(self, temp_db_service):
        """Test statistics calculation with jobs having null metrics."""
        # Create jobs without duration or content metrics
        job1 = temp_db_service.create_job(
            url="https://example.com/test1",
            output_directory="/tmp/output1",
        )
        job2 = temp_db_service.create_job(
            url="https://example.com/test2",
            output_directory="/tmp/output2",
        )

        # Complete without duration
        temp_db_service.update_job_status(job1.id, JobStatus.COMPLETED)
        temp_db_service.update_job_status(job2.id, JobStatus.FAILED)

        stats = temp_db_service.get_job_statistics(days=7)

        assert stats["total_jobs"] == 2
        assert stats["avg_duration_seconds"] == 0.0  # Null average becomes 0
        assert stats["total_content_size_bytes"] == 0
        assert stats["total_images_downloaded"] == 0

    def test_get_job_statistics_database_error(self, temp_db_service):
        """Test statistics retrieval with database error."""
        with patch.object(temp_db_service, "get_session") as mock_session:
            mock_session.side_effect = SQLAlchemyError("Database error")

            with pytest.raises(DatabaseError, match="Statistics retrieval failed"):
                temp_db_service.get_job_statistics()

    def test_get_job_statistics_with_mixed_data(self, temp_db_service):
        """Test statistics with mix of complete and incomplete data."""
        # Create jobs with varying data completeness
        job1 = temp_db_service.create_job(
            url="https://example.com/test1",
            output_directory="/tmp/output1",
        )
        job2 = temp_db_service.create_job(
            url="https://example.com/test2",
            output_directory="/tmp/output2",
        )
        job3 = temp_db_service.create_job(
            url="https://example.com/test3",
            output_directory="/tmp/output3",
        )

        # Update with different combinations of data
        temp_db_service.update_job_status(job1.id, JobStatus.COMPLETED, duration=5.0)
        temp_db_service.update_job_status(job2.id, JobStatus.COMPLETED, duration=10.0)
        # job3 remains pending

        # Add content metrics to only some jobs
        with temp_db_service.get_session() as session:
            session.query(ScrapingJob).filter(ScrapingJob.id == job1.id).update(
                {"content_size_bytes": 2048, "images_downloaded": 10}
            )
            # job2 has no content metrics

        stats = temp_db_service.get_job_statistics(days=7)

        assert stats["total_jobs"] == 3
        assert stats["completed_jobs"] == 2
        assert stats["pending_jobs"] == 1
        assert stats["success_rate_percent"] == round(2 / 3 * 100, 2)
        assert stats["avg_duration_seconds"] == 7.5  # Average of 5.0 and 10.0
        assert stats["total_content_size_bytes"] == 2048
        assert stats["total_images_downloaded"] == 10

    def test_cleanup_old_jobs_database_error(self, temp_db_service):
        """Test job cleanup with database error."""
        with patch.object(temp_db_service, "get_session") as mock_session:
            mock_session.side_effect = SQLAlchemyError("Database error")

            with pytest.raises(DatabaseError, match="Job cleanup failed"):
                temp_db_service.cleanup_old_jobs()

    def test_cleanup_old_jobs_mixed_statuses(self, temp_db_service):
        """Test cleanup with various job statuses."""
        now = datetime.now(UTC)
        old_date = now - timedelta(days=35)

        # Create old jobs with different statuses
        old_completed = temp_db_service.create_job(
            url="https://example.com/old-completed",
            output_directory="/tmp/output",
        )
        temp_db_service.update_job_status(old_completed.id, JobStatus.COMPLETED)

        old_failed = temp_db_service.create_job(
            url="https://example.com/old-failed",
            output_directory="/tmp/output",
        )
        temp_db_service.update_job_status(old_failed.id, JobStatus.FAILED)

        old_pending = temp_db_service.create_job(
            url="https://example.com/old-pending",
            output_directory="/tmp/output",
        )
        # Leave as PENDING

        # Set old dates
        with temp_db_service.get_session() as session:
            session.query(ScrapingJob).filter(
                ScrapingJob.id.in_([old_completed.id, old_failed.id])
            ).update({"completed_at": old_date})
            session.query(ScrapingJob).filter(ScrapingJob.id == old_pending.id).update(
                {"created_at": old_date}
            )

        # Cleanup
        deleted_count = temp_db_service.cleanup_old_jobs(days=30)

        # Should only affect completed and failed jobs with old completed_at
        assert deleted_count == 2

        # Verify statuses
        assert temp_db_service.get_job(old_completed.id).status == JobStatus.CANCELLED
        assert temp_db_service.get_job(old_failed.id).status == JobStatus.CANCELLED
        assert temp_db_service.get_job(old_pending.id).status == JobStatus.PENDING  # Unchanged

    def test_cleanup_old_jobs_no_old_jobs(self, temp_db_service):
        """Test cleanup when no old jobs exist."""
        # Create only recent jobs
        job = temp_db_service.create_job(
            url="https://example.com/recent",
            output_directory="/tmp/output",
        )
        temp_db_service.update_job_status(job.id, JobStatus.COMPLETED)

        deleted_count = temp_db_service.cleanup_old_jobs(days=30)
        assert deleted_count == 0

        # Job should remain unchanged
        assert temp_db_service.get_job(job.id).status == JobStatus.COMPLETED

    def test_session_context_manager_with_commit_error(self, temp_db_service):
        """Test session context manager when commit fails."""
        # Mock the SessionLocal constructor to return our mock session
        with patch.object(temp_db_service, "SessionLocal") as mock_session_factory:
            mock_session = MagicMock()
            mock_session.commit.side_effect = SQLAlchemyError("Commit failed")
            mock_session_factory.return_value = mock_session

            with pytest.raises(SQLAlchemyError):
                with temp_db_service.get_session():
                    pass  # Should fail during commit

            # Verify rollback and close were called
            mock_session.rollback.assert_called_once()
            mock_session.close.assert_called_once()

    def test_initialize_database_idempotent(self, temp_db_service):
        """Test that initialize_database is idempotent."""
        # Should not raise on multiple calls
        temp_db_service.initialize_database()
        temp_db_service.initialize_database()
        temp_db_service.initialize_database()

        # Verify tables still exist
        from sqlalchemy import inspect

        inspector = inspect(temp_db_service.engine)
        table_names = inspector.get_table_names()
        assert "scraping_jobs" in table_names

    def test_create_job_integrity_error(self, temp_db_service):
        """Test job creation with integrity constraint violation."""
        with patch.object(temp_db_service, "get_session") as mock_get_session:
            mock_session = MagicMock()
            mock_get_session.return_value.__enter__ = Mock(return_value=mock_session)
            mock_get_session.return_value.__exit__ = Mock(return_value=None)

            # Mock IntegrityError during flush
            mock_session.flush.side_effect = IntegrityError("UNIQUE constraint failed", None, None)

            with pytest.raises(DatabaseError, match="Job creation failed"):
                temp_db_service.create_job(
                    url="https://example.com/test",
                    output_directory="/tmp/output",
                )
