"""Tests for database service layer functionality with PostgreSQL containers."""

import os
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from src.core.exceptions import DatabaseError
from src.database.models import (
    JobStatus,
    ScrapingJob,
)
from src.database.service import DatabaseService


@pytest.mark.database
class TestDatabaseService:
    """Test database service operations and transaction management."""

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

            # Clean up database state before each test for test isolation
            with service.get_session() as session:
                # Delete in proper order: child tables first, then parent tables
                # With CASCADE foreign keys, deleting parent should cascade to children
                from src.database.models import Batch, ContentResult, JobLog, ScrapingJob

                # Delete child records first (although CASCADE should handle this)
                session.query(ContentResult).delete()
                session.query(JobLog).delete()
                # Then delete parent records
                session.query(ScrapingJob).delete()
                session.query(Batch).delete()
                session.commit()

            yield service
        finally:
            # Clean up database state after each test for complete isolation
            try:
                with service.get_session() as session:
                    from src.database.models import Batch, ContentResult, JobLog, ScrapingJob

                    # Delete child records first
                    session.query(ContentResult).delete()
                    session.query(JobLog).delete()
                    # Then delete parent records
                    session.query(ScrapingJob).delete()
                    session.query(Batch).delete()
                    session.commit()
            except Exception as cleanup_error:
                # Don't fail tests due to cleanup issues
                print(f"Warning: Database cleanup error: {cleanup_error}")

            # Clean up environment variables
            for key in [
                "DATABASE_HOST",
                "DATABASE_PORT",
                "DATABASE_NAME",
                "DATABASE_USER",
                "DATABASE_PASSWORD",
            ]:
                os.environ.pop(key, None)

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

    def test_initialize_database(self, temp_db_service):
        """Test database table creation."""
        # Should not raise any exceptions
        temp_db_service.initialize_database()

        # Verify tables were created by checking engine with inspector
        from sqlalchemy import inspect

        inspector = inspect(temp_db_service.engine)
        table_names = inspector.get_table_names()
        expected_tables = {
            "scraping_jobs",
            "batches",
            "content_results",
            "job_logs",
            "system_metrics",
        }
        assert expected_tables.issubset(set(table_names))

    def test_session_context_manager_success(self, temp_db_service):
        """Test database session context manager with successful transaction."""
        with temp_db_service.get_session() as session:
            job = ScrapingJob(
                url="https://example.com/test",
                domain="example.com",
                output_directory="/tmp/output",
            )
            session.add(job)
            # Should commit automatically

        # Verify job was saved
        with temp_db_service.get_session() as session:
            saved_job = session.query(ScrapingJob).first()
            assert saved_job is not None
            assert saved_job.url == "https://example.com/test"

    def test_session_context_manager_rollback(self, temp_db_service):
        """Test database session context manager with exception rollback."""
        try:
            with temp_db_service.get_session() as session:
                job = ScrapingJob(
                    url="https://example.com/test",
                    domain="example.com",
                    output_directory="/tmp/output",
                )
                session.add(job)
                session.flush()  # Generate ID
                job_id = job.id

                # Force an exception
                raise ValueError("Test exception")
        except ValueError:
            pass  # Expected

        # Verify rollback occurred
        with temp_db_service.get_session() as session:
            saved_job = session.query(ScrapingJob).first()
            assert saved_job is None

    def test_create_job_basic(self, temp_db_service):
        """Test basic job creation with auto-extracted domain and slug."""
        job = temp_db_service.create_job(
            url="https://example.com/blog/test-post",
            output_directory="/tmp/output",
        )

        assert job.id is not None
        assert job.url == "https://example.com/blog/test-post"
        assert job.domain == "example.com"
        assert job.slug == "test-post"
        assert job.output_directory == "/tmp/output"
        assert job.status == JobStatus.PENDING

    def test_create_job_with_custom_fields(self, temp_db_service):
        """Test job creation with custom domain, slug, and additional fields."""
        job = temp_db_service.create_job(
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

    def test_create_job_with_batch(self, temp_db_service):
        """Test job creation associated with a batch."""
        # Create batch first
        batch = temp_db_service.create_batch(
            name="Test Batch",
            description="Test batch for job creation",
        )

        # Create job in batch
        job = temp_db_service.create_job(
            url="https://example.com/test",
            output_directory="/tmp/output",
            batch_id=batch.id,
        )

        assert job.batch_id == batch.id

        # Verify batch relationship through fresh query to avoid DetachedInstanceError
        retrieved_job = temp_db_service.get_job(job.id)
        assert retrieved_job is not None
        assert retrieved_job.batch_id == batch.id

    def test_create_job_homepage_slug_extraction(self, temp_db_service):
        """Test slug extraction for homepage URLs."""
        job = temp_db_service.create_job(
            url="https://example.com/",
            output_directory="/tmp/output",
        )

        assert job.slug == "homepage"

    def test_get_job(self, temp_db_service):
        """Test job retrieval by ID."""
        # Create job
        created_job = temp_db_service.create_job(
            url="https://example.com/test",
            output_directory="/tmp/output",
        )

        # Retrieve job
        retrieved_job = temp_db_service.get_job(created_job.id)
        assert retrieved_job is not None
        assert retrieved_job.id == created_job.id
        assert retrieved_job.url == created_job.url

    def test_get_job_nonexistent(self, temp_db_service):
        """Test retrieval of non-existent job."""
        job = temp_db_service.get_job(99999)
        assert job is None

    def test_update_job_status_to_running(self, temp_db_service):
        """Test updating job status to running (sets started_at)."""
        job = temp_db_service.create_job(
            url="https://example.com/test",
            output_directory="/tmp/output",
        )

        success = temp_db_service.update_job_status(job.id, JobStatus.RUNNING)
        assert success is True

        # Verify update
        updated_job = temp_db_service.get_job(job.id)
        assert updated_job.status == JobStatus.RUNNING
        assert updated_job.started_at is not None

    def test_update_job_status_to_completed(self, temp_db_service):
        """Test updating job status to completed with duration."""
        job = temp_db_service.create_job(
            url="https://example.com/test",
            output_directory="/tmp/output",
        )

        success = temp_db_service.update_job_status(job.id, JobStatus.COMPLETED, duration=5.5)
        assert success is True

        # Verify update
        updated_job = temp_db_service.get_job(job.id)
        assert updated_job.status == JobStatus.COMPLETED
        assert updated_job.completed_at is not None
        assert updated_job.duration_seconds == 5.5

    def test_update_job_status_to_failed_with_error(self, temp_db_service):
        """Test updating job status to failed with error message."""
        job = temp_db_service.create_job(
            url="https://example.com/test",
            output_directory="/tmp/output",
        )

        error_msg = "Connection timeout"
        success = temp_db_service.update_job_status(
            job.id,
            JobStatus.FAILED,
            error_message=error_msg,
        )
        assert success is True

        # Verify update
        updated_job = temp_db_service.get_job(job.id)
        assert updated_job.status == JobStatus.FAILED
        assert updated_job.error_message == error_msg
        assert updated_job.completed_at is not None

    def test_update_job_status_nonexistent(self, temp_db_service):
        """Test updating status of non-existent job."""
        success = temp_db_service.update_job_status(99999, JobStatus.COMPLETED)
        assert success is False

    def test_get_pending_jobs(self, temp_db_service):
        """Test retrieval of pending jobs with priority ordering."""
        # Create jobs with different priorities
        job_low = temp_db_service.create_job(
            url="https://example.com/low",
            output_directory="/tmp/output",
            priority="low",
        )
        job_high = temp_db_service.create_job(
            url="https://example.com/high",
            output_directory="/tmp/output",
            priority="high",
        )
        job_normal = temp_db_service.create_job(
            url="https://example.com/normal",
            output_directory="/tmp/output",
            priority="normal",
        )
        job_urgent = temp_db_service.create_job(
            url="https://example.com/urgent",
            output_directory="/tmp/output",
            priority="urgent",
        )

        # Mark one as running to exclude it
        temp_db_service.update_job_status(job_low.id, JobStatus.RUNNING)

        # Get pending jobs
        pending_jobs = temp_db_service.get_pending_jobs(limit=10)

        # Should exclude running job and order by priority
        assert len(pending_jobs) == 3
        assert pending_jobs[0].id == job_urgent.id  # urgent first
        assert pending_jobs[1].id == job_high.id  # high second
        assert pending_jobs[2].id == job_normal.id  # normal last

    def test_get_pending_jobs_with_limit(self, temp_db_service):
        """Test pending jobs retrieval with limit."""
        # Create multiple jobs
        for i in range(5):
            temp_db_service.create_job(
                url=f"https://example.com/test{i}",
                output_directory=f"/tmp/output{i}",
            )

        # Get with limit
        pending_jobs = temp_db_service.get_pending_jobs(limit=3)
        assert len(pending_jobs) == 3

    def test_get_jobs_by_status(self, temp_db_service):
        """Test job retrieval by status with pagination."""
        # Create jobs with different statuses
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

        # Update some statuses
        temp_db_service.update_job_status(job1.id, JobStatus.COMPLETED)
        temp_db_service.update_job_status(job2.id, JobStatus.COMPLETED)

        # Get completed jobs
        completed_jobs = temp_db_service.get_jobs_by_status(JobStatus.COMPLETED)
        assert len(completed_jobs) == 2

        # Get pending jobs
        pending_jobs = temp_db_service.get_jobs_by_status(JobStatus.PENDING)
        assert len(pending_jobs) == 1
        assert pending_jobs[0].id == job3.id

    def test_get_retry_jobs(self, temp_db_service):
        """Test retrieval of jobs eligible for retry."""
        # Create failed jobs
        job1 = temp_db_service.create_job(
            url="https://example.com/test1",
            output_directory="/tmp/output1",
            max_retries=3,
        )
        job2 = temp_db_service.create_job(
            url="https://example.com/test2",
            output_directory="/tmp/output2",
            max_retries=3,
        )

        # Make them failed with different retry counts
        temp_db_service.update_job_status(job1.id, JobStatus.FAILED)
        temp_db_service.update_job_status(job2.id, JobStatus.FAILED)

        # Update retry counts directly
        with temp_db_service.get_session() as session:
            session.query(ScrapingJob).filter(ScrapingJob.id == job1.id).update({"retry_count": 1})
            session.query(ScrapingJob).filter(ScrapingJob.id == job2.id).update(
                {
                    "retry_count": 3  # At limit, should not be eligible
                }
            )

        # Get retry jobs
        retry_jobs = temp_db_service.get_retry_jobs()
        assert len(retry_jobs) == 1
        assert retry_jobs[0].id == job1.id

    def test_get_retry_jobs_with_future_retry_time(self, temp_db_service):
        """Test retry jobs filtering by next_retry_at time."""
        job = temp_db_service.create_job(
            url="https://example.com/test",
            output_directory="/tmp/output",
        )

        temp_db_service.update_job_status(job.id, JobStatus.FAILED)

        # Set future retry time
        future_time = datetime.now(UTC) + timedelta(hours=1)
        with temp_db_service.get_session() as session:
            session.query(ScrapingJob).filter(ScrapingJob.id == job.id).update(
                {"next_retry_at": future_time}
            )

        # Should not be eligible yet
        retry_jobs = temp_db_service.get_retry_jobs()
        assert len(retry_jobs) == 0

        # Set past retry time
        past_time = datetime.now(UTC) - timedelta(minutes=1)
        with temp_db_service.get_session() as session:
            session.query(ScrapingJob).filter(ScrapingJob.id == job.id).update(
                {"next_retry_at": past_time}
            )

        # Should be eligible now
        retry_jobs = temp_db_service.get_retry_jobs()
        assert len(retry_jobs) == 1

    def test_create_batch(self, temp_db_service):
        """Test batch creation with configuration."""
        batch = temp_db_service.create_batch(
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

    def test_get_batch(self, temp_db_service):
        """Test batch retrieval by ID."""
        created_batch = temp_db_service.create_batch(name="Test Batch")

        retrieved_batch = temp_db_service.get_batch(created_batch.id)
        assert retrieved_batch is not None
        assert retrieved_batch.id == created_batch.id
        assert retrieved_batch.name == created_batch.name

    def test_get_batch_nonexistent(self, temp_db_service):
        """Test retrieval of non-existent batch."""
        batch = temp_db_service.get_batch(99999)
        assert batch is None

    def test_update_batch_progress(self, temp_db_service):
        """Test batch progress counter updates based on job statuses."""
        # Create batch with jobs
        batch = temp_db_service.create_batch(name="Progress Test Batch")

        jobs = []
        for i in range(5):
            job = temp_db_service.create_job(
                url=f"https://example.com/test{i}",
                output_directory=f"/tmp/output{i}",
                batch_id=batch.id,
            )
            jobs.append(job)

        # Update job statuses
        temp_db_service.update_job_status(jobs[0].id, JobStatus.COMPLETED)
        temp_db_service.update_job_status(jobs[1].id, JobStatus.COMPLETED)
        temp_db_service.update_job_status(jobs[2].id, JobStatus.FAILED)
        temp_db_service.update_job_status(jobs[3].id, JobStatus.SKIPPED)
        # jobs[4] remains PENDING

        # Update batch progress
        success = temp_db_service.update_batch_progress(batch.id)
        assert success is True

        # Verify progress counters
        updated_batch = temp_db_service.get_batch(batch.id)
        assert updated_batch.total_jobs == 5
        assert updated_batch.completed_jobs == 2
        assert updated_batch.failed_jobs == 1
        assert updated_batch.skipped_jobs == 1

    def test_save_content_result(self, temp_db_service):
        """Test saving converted content results."""
        job = temp_db_service.create_job(
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

        content_result = temp_db_service.save_content_result(
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

    def test_add_job_log(self, temp_db_service):
        """Test adding structured log entries for jobs."""
        job = temp_db_service.create_job(
            url="https://example.com/test",
            output_directory="/tmp/output",
        )

        log_entry = temp_db_service.add_job_log(
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

    def test_add_job_log_error_handling(self, temp_db_service):
        """Test job log creation with database errors."""
        # Create job
        job = temp_db_service.create_job(
            url="https://example.com/test",
            output_directory="/tmp/output",
        )

        # Mock database error
        with patch.object(temp_db_service, "get_session") as mock_session:
            mock_session.side_effect = Exception("Database error")

            # Should not raise, returns None on error
            log_entry = temp_db_service.add_job_log(
                job_id=job.id,
                level="ERROR",
                message="Test error log",
            )
            assert log_entry is None

    def test_get_job_statistics(self, temp_db_service):
        """Test job statistics calculation for time period."""
        # Create jobs with different statuses and timing
        now = datetime.now(UTC)

        # Recent jobs (within 7 days)
        job1 = temp_db_service.create_job(
            url="https://example.com/test1",
            output_directory="/tmp/output1",
        )
        job2 = temp_db_service.create_job(
            url="https://example.com/test2",
            output_directory="/tmp/output2",
        )

        # Update statuses and add metrics
        temp_db_service.update_job_status(job1.id, JobStatus.COMPLETED, duration=2.5)
        temp_db_service.update_job_status(job2.id, JobStatus.FAILED)

        # Add content metrics
        with temp_db_service.get_session() as session:
            session.query(ScrapingJob).filter(ScrapingJob.id == job1.id).update(
                {
                    "content_size_bytes": 1024,
                    "images_downloaded": 5,
                }
            )

        # Get statistics
        stats = temp_db_service.get_job_statistics(days=7)

        assert stats["period_days"] == 7
        assert stats["total_jobs"] == 2
        assert stats["completed_jobs"] == 1
        assert stats["failed_jobs"] == 1
        assert stats["pending_jobs"] == 0
        assert stats["success_rate_percent"] == 50.0
        assert stats["avg_duration_seconds"] == 2.5
        assert stats["total_content_size_bytes"] == 1024
        assert stats["total_images_downloaded"] == 5

    def test_get_job_statistics_empty(self, temp_db_service):
        """Test job statistics with no jobs in time period."""
        stats = temp_db_service.get_job_statistics(days=1)

        assert stats["total_jobs"] == 0
        assert stats["success_rate_percent"] == 0.0
        assert stats["avg_duration_seconds"] == 0.0

    def test_cleanup_old_jobs(self, temp_db_service):
        """Test cleanup of old completed jobs."""
        # Create old completed job
        old_job = temp_db_service.create_job(
            url="https://example.com/old",
            output_directory="/tmp/output",
        )
        temp_db_service.update_job_status(old_job.id, JobStatus.COMPLETED)

        # Create recent job
        recent_job = temp_db_service.create_job(
            url="https://example.com/recent",
            output_directory="/tmp/output",
        )
        temp_db_service.update_job_status(recent_job.id, JobStatus.COMPLETED)

        # Manually set old completion date
        old_date = datetime.now(UTC) - timedelta(days=35)
        with temp_db_service.get_session() as session:
            session.query(ScrapingJob).filter(ScrapingJob.id == old_job.id).update(
                {"completed_at": old_date}
            )

        # Cleanup jobs older than 30 days
        deleted_count = temp_db_service.cleanup_old_jobs(days=30)
        assert deleted_count == 1

        # Verify old job was marked as cancelled (soft delete)
        updated_old_job = temp_db_service.get_job(old_job.id)
        assert updated_old_job.status == JobStatus.CANCELLED

        # Recent job should remain completed
        updated_recent_job = temp_db_service.get_job(recent_job.id)
        assert updated_recent_job.status == JobStatus.COMPLETED


@pytest.mark.database
class TestDatabaseServiceErrorHandling:
    """Test database service error handling and transaction management."""

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

            # Clean up database state before each test for test isolation
            with service.get_session() as session:
                # Delete in proper order: child tables first, then parent tables
                # With CASCADE foreign keys, deleting parent should cascade to children
                from src.database.models import Batch, ContentResult, JobLog, ScrapingJob

                # Delete child records first (although CASCADE should handle this)
                session.query(ContentResult).delete()
                session.query(JobLog).delete()
                # Then delete parent records
                session.query(ScrapingJob).delete()
                session.query(Batch).delete()
                session.commit()

            yield service
        finally:
            # Clean up database state after each test for complete isolation
            try:
                with service.get_session() as session:
                    from src.database.models import Batch, ContentResult, JobLog, ScrapingJob

                    # Delete child records first
                    session.query(ContentResult).delete()
                    session.query(JobLog).delete()
                    # Then delete parent records
                    session.query(ScrapingJob).delete()
                    session.query(Batch).delete()
                    session.commit()
            except Exception as cleanup_error:
                # Don't fail tests due to cleanup issues
                print(f"Warning: Database cleanup error: {cleanup_error}")

            # Clean up environment variables
            for key in [
                "DATABASE_HOST",
                "DATABASE_PORT",
                "DATABASE_NAME",
                "DATABASE_USER",
                "DATABASE_PASSWORD",
            ]:
                os.environ.pop(key, None)

    def test_database_error_handling_in_operations(self, temp_db_service):
        """Test proper exception handling and DatabaseError wrapping."""
        # Mock session to raise SQLAlchemy error
        with patch.object(temp_db_service, "get_session") as mock_session:
            from sqlalchemy.exc import SQLAlchemyError

            mock_session.side_effect = SQLAlchemyError("Database connection failed")

            # Should wrap in DatabaseError
            with pytest.raises(DatabaseError, match="Job creation failed"):
                temp_db_service.create_job(
                    url="https://example.com/test",
                    output_directory="/tmp/output",
                )

    def test_integrity_error_handling(self, temp_db_service):
        """Test handling of database integrity constraint violations."""
        with patch.object(temp_db_service, "get_session") as mock_session:
            from sqlalchemy.exc import IntegrityError

            # Mock session context manager
            mock_ctx = MagicMock()
            mock_ctx.__enter__ = MagicMock(return_value=mock_session)
            mock_ctx.__exit__ = MagicMock(return_value=None)
            mock_session.return_value = mock_ctx

            # Mock integrity error during add/flush
            mock_session.add.side_effect = IntegrityError("UNIQUE constraint failed", None, None)

            with pytest.raises(DatabaseError, match="Job creation failed"):
                temp_db_service.create_job(
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

    def test_concurrent_access_handling(self, temp_db_service, mock_time_sleep):
        """Test handling of concurrent database access."""
        import threading
        import time

        # PostgreSQL supports concurrent access - this test should pass

        # Initialize database first
        temp_db_service.initialize_database()

        results = []
        errors = []
        lock = threading.Lock()

        def create_job_worker(worker_id):
            try:
                # Add small delay to increase chance of concurrent access
                time.sleep(0.01)  # Mocked by mock_time_sleep fixture
                job = temp_db_service.create_job(
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
