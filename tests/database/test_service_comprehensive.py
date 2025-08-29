"""Comprehensive tests for database service layer to improve coverage to 80%+."""

import os
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

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


@pytest.mark.database
class TestDatabaseServiceComprehensive:
    """Comprehensive test suite for database service operations."""

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

    @pytest.fixture
    def real_service(self, monkeypatch):
        """Create a real database service for integration tests."""
        # Check if we're in CI environment with PostgreSQL
        if (
            os.environ.get("DATABASE_HOST") == "localhost"
            and os.environ.get("DATABASE_USER") == "test_user"
        ):
            # In CI, skip tests that require real database as they're tested separately
            pytest.skip(
                "Skipping real database tests in CI - tested in dedicated integration tests"
            )

        # For local testing, use in-memory SQLite for fast tests
        monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")

        # Need to reload the models module to pick up the new DATABASE_URL
        import importlib

        import src.database.models

        importlib.reload(src.database.models)

        # Now create the service with the SQLite database
        from src.database.service import DatabaseService

        service = DatabaseService(echo=False)
        service.initialize_database()
        yield service

        # Clean up
        if hasattr(service, "engine"):
            service.engine.dispose()

    # Test initialization and database setup
    def test_database_service_initialization(self):
        """Test DatabaseService initialization."""
        with patch("src.database.service.create_database_engine") as mock_engine:
            with patch("src.database.service.sessionmaker") as mock_sessionmaker:
                service = DatabaseService(echo=True)
                assert service.engine is not None
                assert service.SessionLocal is not None
                mock_engine.assert_called_once()
                mock_sessionmaker.assert_called_once()

    def test_initialize_database_success(self, mock_service):
        """Test successful database initialization."""
        with patch("src.database.models.Base.metadata.create_all") as mock_create:
            mock_service.initialize_database()
            mock_create.assert_called_once()

    def test_initialize_database_failure(self, mock_service):
        """Test database initialization failure handling."""
        with patch(
            "src.database.models.Base.metadata.create_all",
            side_effect=SQLAlchemyError("Connection failed"),
        ):
            with pytest.raises(DatabaseError) as exc_info:
                mock_service.initialize_database()
            assert "Database initialization failed" in str(exc_info.value)

    # Test session management
    def test_get_session_success(self, mock_service, mock_session):
        """Test successful session context manager."""
        with mock_service.get_session() as session:
            assert session == mock_session
        mock_session.commit.assert_called_once()
        mock_session.close.assert_called_once()

    def test_get_session_with_exception(self, mock_service, mock_session):
        """Test session rollback on exception."""
        with pytest.raises(ValueError):
            with mock_service.get_session() as session:
                raise ValueError("Test error")
        mock_session.rollback.assert_called_once()
        mock_session.close.assert_called_once()

    # Test job creation with various scenarios
    def test_create_job_basic(self, real_service):
        """Test basic job creation."""
        job = real_service.create_job(url="https://example.com/test", output_directory="/tmp/test")
        assert job.id is not None
        assert job.url == "https://example.com/test"
        assert job.domain == "example.com"
        assert job.slug == "test"
        assert job.status == JobStatus.PENDING

    def test_create_job_with_custom_domain_and_slug(self, real_service):
        """Test job creation with custom domain and slug."""
        job = real_service.create_job(
            url="https://example.com/path/to/page",
            output_directory="/tmp/test",
            domain="custom.domain",
            slug="custom-slug",
        )
        assert job.domain == "custom.domain"
        assert job.slug == "custom-slug"

    def test_create_job_auto_extract_homepage_slug(self, real_service):
        """Test auto-extraction of homepage slug."""
        job = real_service.create_job(url="https://example.com/", output_directory="/tmp/test")
        assert job.slug == "homepage"

    def test_create_job_with_batch_id(self, real_service):
        """Test job creation with batch association."""
        batch = real_service.create_batch(name="Test Batch", description="Test batch description")
        job = real_service.create_job(
            url="https://example.com/test", output_directory="/tmp/test", batch_id=batch.id
        )
        assert job.batch_id == batch.id

    def test_create_job_with_priority_string(self, real_service):
        """Test job creation with string priority."""
        job = real_service.create_job(
            url="https://example.com/test", output_directory="/tmp/test", priority="urgent"
        )
        assert job.priority == JobPriority.URGENT

    def test_create_job_with_invalid_priority_string(self, real_service):
        """Test job creation with invalid priority defaults to NORMAL."""
        job = real_service.create_job(
            url="https://example.com/test",
            output_directory="/tmp/test",
            priority="invalid_priority",
        )
        assert job.priority == JobPriority.NORMAL

    def test_create_job_with_priority_enum(self, real_service):
        """Test job creation with JobPriority enum."""
        job = real_service.create_job(
            url="https://example.com/test", output_directory="/tmp/test", priority=JobPriority.HIGH
        )
        assert job.priority == JobPriority.HIGH

    def test_create_job_integrity_error(self, mock_service, mock_session):
        """Test job creation with integrity constraint violation."""
        mock_session.add.side_effect = IntegrityError("Duplicate", "params", "orig")
        with pytest.raises(DatabaseError) as exc_info:
            mock_service.create_job(url="https://example.com/test", output_directory="/tmp/test")
        assert "Job creation failed" in str(exc_info.value)

    def test_create_job_database_error(self, mock_service, mock_session):
        """Test job creation with general database error."""
        mock_session.add.side_effect = SQLAlchemyError("Database error")
        with pytest.raises(DatabaseError) as exc_info:
            mock_service.create_job(url="https://example.com/test", output_directory="/tmp/test")
        assert "Job creation failed" in str(exc_info.value)

    # Test job retrieval
    def test_get_job_exists(self, real_service):
        """Test retrieving an existing job."""
        created_job = real_service.create_job(
            url="https://example.com/test", output_directory="/tmp/test"
        )
        retrieved_job = real_service.get_job(created_job.id)
        assert retrieved_job is not None
        assert retrieved_job.id == created_job.id

    def test_get_job_not_exists(self, real_service):
        """Test retrieving a non-existent job."""
        job = real_service.get_job(99999)
        assert job is None

    def test_get_job_database_error(self, mock_service, mock_session):
        """Test job retrieval with database error."""
        mock_session.get.side_effect = SQLAlchemyError("Database error")
        with pytest.raises(DatabaseError) as exc_info:
            mock_service.get_job(1)
        assert "Job retrieval failed" in str(exc_info.value)

    # Test job status updates
    def test_update_job_status_to_running(self, real_service):
        """Test updating job status to RUNNING."""
        job = real_service.create_job(url="https://example.com/test", output_directory="/tmp/test")
        success = real_service.update_job_status(job.id, JobStatus.RUNNING)
        assert success is True

        updated_job = real_service.get_job(job.id)
        assert updated_job.status == JobStatus.RUNNING
        assert updated_job.started_at is not None

    def test_update_job_status_to_completed(self, real_service):
        """Test updating job status to COMPLETED with duration."""
        job = real_service.create_job(url="https://example.com/test", output_directory="/tmp/test")
        success = real_service.update_job_status(job.id, JobStatus.COMPLETED, duration=10.5)
        assert success is True

        updated_job = real_service.get_job(job.id)
        assert updated_job.status == JobStatus.COMPLETED
        assert updated_job.completed_at is not None
        assert updated_job.duration_seconds == 10.5

    def test_update_job_status_to_failed(self, real_service):
        """Test updating job status to FAILED with error message."""
        job = real_service.create_job(url="https://example.com/test", output_directory="/tmp/test")
        success = real_service.update_job_status(
            job.id, JobStatus.FAILED, error_message="Connection timeout", duration=5.0
        )
        assert success is True

        updated_job = real_service.get_job(job.id)
        assert updated_job.status == JobStatus.FAILED
        assert updated_job.error_message == "Connection timeout"
        assert updated_job.duration_seconds == 5.0

    def test_update_job_status_to_cancelled(self, real_service):
        """Test updating job status to CANCELLED."""
        job = real_service.create_job(url="https://example.com/test", output_directory="/tmp/test")
        success = real_service.update_job_status(job.id, JobStatus.CANCELLED)
        assert success is True

        updated_job = real_service.get_job(job.id)
        assert updated_job.status == JobStatus.CANCELLED
        assert updated_job.completed_at is not None

    def test_update_job_status_nonexistent_job(self, real_service):
        """Test updating status of non-existent job."""
        success = real_service.update_job_status(99999, JobStatus.RUNNING)
        assert success is False

    def test_update_job_status_database_error(self, mock_service, mock_session):
        """Test job status update with database error."""
        mock_session.execute.side_effect = SQLAlchemyError("Database error")
        with pytest.raises(DatabaseError) as exc_info:
            mock_service.update_job_status(1, JobStatus.COMPLETED)
        assert "Job status update failed" in str(exc_info.value)

    # Test pending job retrieval
    def test_get_pending_jobs_with_priority(self, real_service):
        """Test retrieving pending jobs ordered by priority."""
        # Create jobs with different priorities
        low_job = real_service.create_job(
            url="https://example.com/low", output_directory="/tmp/test", priority=JobPriority.LOW
        )
        normal_job = real_service.create_job(
            url="https://example.com/normal",
            output_directory="/tmp/test",
            priority=JobPriority.NORMAL,
        )
        urgent_job = real_service.create_job(
            url="https://example.com/urgent",
            output_directory="/tmp/test",
            priority=JobPriority.URGENT,
        )
        high_job = real_service.create_job(
            url="https://example.com/high", output_directory="/tmp/test", priority=JobPriority.HIGH
        )

        # Get pending jobs
        pending_jobs = real_service.get_pending_jobs(limit=10)

        # Check order: URGENT -> HIGH -> NORMAL -> LOW
        assert len(pending_jobs) == 4
        assert pending_jobs[0].id == urgent_job.id
        assert pending_jobs[1].id == high_job.id
        assert pending_jobs[2].id == normal_job.id
        assert pending_jobs[3].id == low_job.id

    def test_get_pending_jobs_with_limit(self, real_service):
        """Test retrieving pending jobs with limit."""
        # Create 5 jobs
        for i in range(5):
            real_service.create_job(
                url=f"https://example.com/test{i}", output_directory="/tmp/test"
            )

        # Get only 3 jobs
        pending_jobs = real_service.get_pending_jobs(limit=3)
        assert len(pending_jobs) == 3

    def test_get_pending_jobs_excludes_non_pending(self, real_service):
        """Test that non-pending jobs are excluded."""
        # Create jobs with different statuses
        pending_job = real_service.create_job(
            url="https://example.com/pending", output_directory="/tmp/test"
        )
        running_job = real_service.create_job(
            url="https://example.com/running", output_directory="/tmp/test"
        )
        real_service.update_job_status(running_job.id, JobStatus.RUNNING)

        completed_job = real_service.create_job(
            url="https://example.com/completed", output_directory="/tmp/test"
        )
        real_service.update_job_status(completed_job.id, JobStatus.COMPLETED)

        # Get pending jobs
        pending_jobs = real_service.get_pending_jobs()
        assert len(pending_jobs) == 1
        assert pending_jobs[0].id == pending_job.id

    def test_get_pending_jobs_database_error(self, mock_service, mock_session):
        """Test pending jobs retrieval with database error."""
        mock_session.execute.side_effect = SQLAlchemyError("Database error")
        with pytest.raises(DatabaseError) as exc_info:
            mock_service.get_pending_jobs()
        assert "Pending jobs retrieval failed" in str(exc_info.value)

    # Test jobs by status retrieval
    def test_get_jobs_by_status(self, real_service):
        """Test retrieving jobs by specific status."""
        # Create jobs with different statuses
        for i in range(3):
            job = real_service.create_job(
                url=f"https://example.com/completed{i}", output_directory="/tmp/test"
            )
            real_service.update_job_status(job.id, JobStatus.COMPLETED)

        for i in range(2):
            job = real_service.create_job(
                url=f"https://example.com/failed{i}", output_directory="/tmp/test"
            )
            real_service.update_job_status(job.id, JobStatus.FAILED)

        # Get completed jobs
        completed_jobs = real_service.get_jobs_by_status(JobStatus.COMPLETED)
        assert len(completed_jobs) == 3

        # Get failed jobs
        failed_jobs = real_service.get_jobs_by_status(JobStatus.FAILED)
        assert len(failed_jobs) == 2

    def test_get_jobs_by_status_with_pagination(self, real_service):
        """Test retrieving jobs by status with pagination."""
        # Create 5 completed jobs
        for i in range(5):
            job = real_service.create_job(
                url=f"https://example.com/test{i}", output_directory="/tmp/test"
            )
            real_service.update_job_status(job.id, JobStatus.COMPLETED)

        # Get first page
        page1 = real_service.get_jobs_by_status(JobStatus.COMPLETED, limit=2, offset=0)
        assert len(page1) == 2

        # Get second page
        page2 = real_service.get_jobs_by_status(JobStatus.COMPLETED, limit=2, offset=2)
        assert len(page2) == 2

        # Ensure different jobs
        page1_ids = [j.id for j in page1]
        page2_ids = [j.id for j in page2]
        assert set(page1_ids).isdisjoint(set(page2_ids))

    def test_get_jobs_by_status_database_error(self, mock_service, mock_session):
        """Test jobs by status retrieval with database error."""
        mock_session.execute.side_effect = SQLAlchemyError("Database error")
        with pytest.raises(DatabaseError) as exc_info:
            mock_service.get_jobs_by_status(JobStatus.COMPLETED)
        assert "Jobs retrieval failed" in str(exc_info.value)

    # Test retry job retrieval
    def test_get_retry_jobs_basic(self, real_service):
        """Test retrieving failed jobs eligible for retry."""
        # Create a failed job with retries remaining
        job = real_service.create_job(url="https://example.com/test", output_directory="/tmp/test")
        # Update job to have retry info
        with real_service.get_session() as session:
            db_job = session.get(ScrapingJob, job.id)
            db_job.status = JobStatus.FAILED
            db_job.retry_count = 1
            db_job.max_retries = 3
            db_job.next_retry_at = datetime.now(timezone.utc) - timedelta(minutes=1)
            session.commit()

        retry_jobs = real_service.get_retry_jobs()
        assert len(retry_jobs) == 1
        assert retry_jobs[0].id == job.id

    def test_get_retry_jobs_excludes_max_retries(self, real_service):
        """Test that jobs at max retries are excluded."""
        job = real_service.create_job(url="https://example.com/test", output_directory="/tmp/test")
        # Update job to have max retries reached
        with real_service.get_session() as session:
            db_job = session.get(ScrapingJob, job.id)
            db_job.status = JobStatus.FAILED
            db_job.retry_count = 3
            db_job.max_retries = 3
            session.commit()

        retry_jobs = real_service.get_retry_jobs()
        assert len(retry_jobs) == 0

    def test_get_retry_jobs_respects_next_retry_time(self, real_service):
        """Test that jobs with future retry time are excluded."""
        job = real_service.create_job(url="https://example.com/test", output_directory="/tmp/test")
        # Update job with future retry time
        with real_service.get_session() as session:
            db_job = session.get(ScrapingJob, job.id)
            db_job.status = JobStatus.FAILED
            db_job.retry_count = 1
            db_job.max_retries = 3
            db_job.next_retry_at = datetime.now(timezone.utc) + timedelta(hours=1)
            session.commit()

        retry_jobs = real_service.get_retry_jobs()
        assert len(retry_jobs) == 0

    def test_get_retry_jobs_with_limit(self, real_service):
        """Test retrieving retry jobs with limit."""
        # Create multiple failed jobs
        for i in range(5):
            job = real_service.create_job(
                url=f"https://example.com/test{i}", output_directory="/tmp/test"
            )
            with real_service.get_session() as session:
                db_job = session.get(ScrapingJob, job.id)
                db_job.status = JobStatus.FAILED
                db_job.retry_count = 1
                db_job.max_retries = 3
                session.commit()

        retry_jobs = real_service.get_retry_jobs(max_jobs=3)
        assert len(retry_jobs) == 3

    def test_get_retry_jobs_database_error(self, mock_service, mock_session):
        """Test retry jobs retrieval with database error."""
        mock_session.execute.side_effect = SQLAlchemyError("Database error")
        with pytest.raises(DatabaseError) as exc_info:
            mock_service.get_retry_jobs()
        assert "Retry jobs retrieval failed" in str(exc_info.value)

    # Test batch operations
    def test_create_batch_basic(self, real_service):
        """Test basic batch creation."""
        batch = real_service.create_batch(name="Test Batch", description="Test description")
        assert batch.id is not None
        assert batch.name == "Test Batch"
        assert batch.description == "Test description"
        assert batch.output_base_directory == "batch_output"

    def test_create_batch_with_custom_directory(self, real_service):
        """Test batch creation with custom output directory."""
        batch = real_service.create_batch(name="Test Batch", output_base_directory="/custom/path")
        assert batch.output_base_directory == "/custom/path"

    def test_create_batch_with_config(self, real_service):
        """Test batch creation with additional configuration."""
        batch = real_service.create_batch(name="Test Batch", max_concurrent=10, timeout=300)
        assert batch.batch_config.get("max_concurrent") == 10
        assert batch.batch_config.get("timeout") == 300

    def test_create_batch_database_error(self, mock_service, mock_session):
        """Test batch creation with database error."""
        mock_session.add.side_effect = SQLAlchemyError("Database error")
        with pytest.raises(DatabaseError) as exc_info:
            mock_service.create_batch(name="Test Batch")
        assert "Batch creation failed" in str(exc_info.value)

    def test_get_batch_exists(self, real_service):
        """Test retrieving an existing batch."""
        created_batch = real_service.create_batch(name="Test Batch")
        retrieved_batch = real_service.get_batch(created_batch.id)
        assert retrieved_batch is not None
        assert retrieved_batch.id == created_batch.id
        assert retrieved_batch.name == "Test Batch"

    def test_get_batch_not_exists(self, real_service):
        """Test retrieving a non-existent batch."""
        batch = real_service.get_batch(99999)
        assert batch is None

    def test_get_batch_database_error(self, mock_service, mock_session):
        """Test batch retrieval with database error."""
        mock_session.execute.side_effect = SQLAlchemyError("Database error")
        with pytest.raises(DatabaseError) as exc_info:
            mock_service.get_batch(1)
        assert "Batch retrieval failed" in str(exc_info.value)

    def test_update_batch_progress(self, real_service):
        """Test updating batch progress based on job statuses."""
        # Create batch and jobs
        batch = real_service.create_batch(name="Test Batch")

        # Create jobs with different statuses
        for i in range(3):
            job = real_service.create_job(
                url=f"https://example.com/completed{i}",
                output_directory="/tmp/test",
                batch_id=batch.id,
            )
            real_service.update_job_status(job.id, JobStatus.COMPLETED)

        for i in range(2):
            job = real_service.create_job(
                url=f"https://example.com/failed{i}",
                output_directory="/tmp/test",
                batch_id=batch.id,
            )
            real_service.update_job_status(job.id, JobStatus.FAILED)

        job = real_service.create_job(
            url="https://example.com/skipped", output_directory="/tmp/test", batch_id=batch.id
        )
        real_service.update_job_status(job.id, JobStatus.SKIPPED)

        # Update batch progress
        success = real_service.update_batch_progress(batch.id)
        assert success is True

        # Check updated batch
        updated_batch = real_service.get_batch(batch.id)
        assert updated_batch.total_jobs == 6
        assert updated_batch.completed_jobs == 3
        assert updated_batch.failed_jobs == 2
        assert updated_batch.skipped_jobs == 1

    def test_update_batch_progress_nonexistent(self, real_service):
        """Test updating progress for non-existent batch."""
        success = real_service.update_batch_progress(99999)
        assert success is False

    def test_update_batch_progress_database_error(self, mock_service, mock_session):
        """Test batch progress update with database error."""
        mock_session.execute.side_effect = SQLAlchemyError("Database error")
        with pytest.raises(DatabaseError) as exc_info:
            mock_service.update_batch_progress(1)
        assert "Batch progress update failed" in str(exc_info.value)

    # Test content result operations
    def test_save_content_result_basic(self, real_service):
        """Test saving basic content result."""
        job = real_service.create_job(url="https://example.com/test", output_directory="/tmp/test")

        content_result = real_service.save_content_result(
            job_id=job.id, html_content="<h1>Test Content</h1>"
        )

        assert content_result.id is not None
        assert content_result.job_id == job.id
        assert content_result.converted_html == "<h1>Test Content</h1>"

    def test_save_content_result_with_metadata(self, real_service):
        """Test saving content result with metadata."""
        job = real_service.create_job(url="https://example.com/test", output_directory="/tmp/test")

        metadata = {
            "title": "Test Page",
            "meta_description": "Test description",
            "author": "Test Author",
            "tags": ["tag1", "tag2"],
            "categories": ["category1"],
            "custom_field": "custom_value",
        }

        content_result = real_service.save_content_result(job_id=job.id, metadata=metadata)

        assert content_result.title == "Test Page"
        assert content_result.meta_description == "Test description"
        assert content_result.author == "Test Author"
        assert content_result.tags == ["tag1", "tag2"]
        assert content_result.categories == ["category1"]
        assert content_result.extra_metadata["custom_field"] == "custom_value"

    def test_save_content_result_with_file_paths(self, real_service):
        """Test saving content result with file paths."""
        job = real_service.create_job(url="https://example.com/test", output_directory="/tmp/test")

        file_paths = {
            "html": "/tmp/test/content.html",
            "metadata": "/tmp/test/metadata.json",
            "images": "/tmp/test/images/",
        }

        content_result = real_service.save_content_result(job_id=job.id, file_paths=file_paths)

        assert content_result.html_file_path == "/tmp/test/content.html"
        assert content_result.metadata_file_path == "/tmp/test/metadata.json"
        assert content_result.images_directory == "/tmp/test/images/"

    def test_save_content_result_database_error(self, mock_service, mock_session):
        """Test content result save with database error."""
        mock_session.add.side_effect = SQLAlchemyError("Database error")
        with pytest.raises(DatabaseError) as exc_info:
            mock_service.save_content_result(job_id=1, html_content="test")
        assert "Content result save failed" in str(exc_info.value)

    # Test job logging
    def test_add_job_log_basic(self, real_service):
        """Test adding basic job log entry."""
        job = real_service.create_job(url="https://example.com/test", output_directory="/tmp/test")

        log = real_service.add_job_log(job_id=job.id, level="INFO", message="Test log message")

        assert log is not None
        assert log.job_id == job.id
        assert log.level == "INFO"
        assert log.message == "Test log message"

    def test_add_job_log_with_context(self, real_service):
        """Test adding job log with component and context data."""
        job = real_service.create_job(url="https://example.com/test", output_directory="/tmp/test")

        context_data = {"key": "value", "count": 42}
        log = real_service.add_job_log(
            job_id=job.id,
            level="WARN",
            message="Warning message",
            component="Processor",
            operation="fetch",
            context_data=context_data,
        )

        assert log.component == "Processor"
        assert log.operation == "fetch"
        assert log.context_data == context_data

    def test_add_job_log_level_uppercase(self, real_service):
        """Test that log level is converted to uppercase."""
        job = real_service.create_job(url="https://example.com/test", output_directory="/tmp/test")

        log = real_service.add_job_log(job_id=job.id, level="error", message="Error message")

        assert log.level == "ERROR"

    def test_add_job_log_failure_returns_none(self, mock_service, mock_session):
        """Test that log failures don't raise exceptions."""
        mock_session.add.side_effect = Exception("Database error")
        log = mock_service.add_job_log(job_id=1, level="ERROR", message="Test message")
        assert log is None

    # Test statistics
    def test_get_job_statistics_basic(self, real_service):
        """Test getting job statistics."""
        # Create jobs with different statuses
        for i in range(5):
            job = real_service.create_job(
                url=f"https://example.com/completed{i}", output_directory="/tmp/test"
            )
            with real_service.get_session() as session:
                db_job = session.get(ScrapingJob, job.id)
                db_job.status = JobStatus.COMPLETED
                db_job.duration_seconds = 10.0
                db_job.content_size_bytes = 1000
                db_job.images_downloaded = 5
                session.commit()

        for i in range(3):
            job = real_service.create_job(
                url=f"https://example.com/failed{i}", output_directory="/tmp/test"
            )
            real_service.update_job_status(job.id, JobStatus.FAILED)

        stats = real_service.get_job_statistics(days=7)

        assert stats["total_jobs"] == 8
        assert stats["completed_jobs"] == 5
        assert stats["failed_jobs"] == 3
        assert stats["pending_jobs"] == 0
        assert stats["success_rate_percent"] == 62.5
        assert stats["avg_duration_seconds"] == 10.0
        assert stats["total_content_size_bytes"] == 5000
        assert stats["total_images_downloaded"] == 25

    def test_get_job_statistics_with_time_filter(self, real_service):
        """Test job statistics with time filtering."""
        # Create old job (should be excluded)
        old_job = real_service.create_job(
            url="https://example.com/old", output_directory="/tmp/test"
        )
        with real_service.get_session() as session:
            db_job = session.get(ScrapingJob, old_job.id)
            db_job.created_at = datetime.now(timezone.utc) - timedelta(days=10)
            session.commit()

        # Create recent job (should be included)
        recent_job = real_service.create_job(
            url="https://example.com/recent", output_directory="/tmp/test"
        )

        stats = real_service.get_job_statistics(days=7)
        assert stats["total_jobs"] == 1  # Only recent job

    def test_get_job_statistics_empty_database(self, real_service):
        """Test job statistics with no jobs."""
        stats = real_service.get_job_statistics(days=7)

        assert stats["total_jobs"] == 0
        assert stats["success_rate_percent"] == 0.0
        assert stats["avg_duration_seconds"] == 0.0

    def test_get_job_statistics_database_error(self, mock_service, mock_session):
        """Test job statistics with database error."""
        mock_session.execute.side_effect = SQLAlchemyError("Database error")
        with pytest.raises(DatabaseError) as exc_info:
            mock_service.get_job_statistics(days=7)
        assert "Statistics retrieval failed" in str(exc_info.value)

    # Test cleanup operations
    def test_cleanup_old_jobs(self, real_service):
        """Test cleaning up old completed jobs."""
        # Create old completed job
        old_job = real_service.create_job(
            url="https://example.com/old", output_directory="/tmp/test"
        )
        with real_service.get_session() as session:
            db_job = session.get(ScrapingJob, old_job.id)
            db_job.status = JobStatus.COMPLETED
            db_job.completed_at = datetime.now(timezone.utc) - timedelta(days=40)
            session.commit()

        # Create recent completed job
        recent_job = real_service.create_job(
            url="https://example.com/recent", output_directory="/tmp/test"
        )
        real_service.update_job_status(recent_job.id, JobStatus.COMPLETED)

        # Run cleanup
        deleted_count = real_service.cleanup_old_jobs(days=30)
        assert deleted_count == 1

        # Check old job is cancelled (soft delete)
        updated_old = real_service.get_job(old_job.id)
        assert updated_old.status == JobStatus.CANCELLED

        # Check recent job is unchanged
        updated_recent = real_service.get_job(recent_job.id)
        assert updated_recent.status == JobStatus.COMPLETED

    def test_cleanup_old_jobs_includes_failed(self, real_service):
        """Test that cleanup includes failed jobs."""
        old_job = real_service.create_job(
            url="https://example.com/old", output_directory="/tmp/test"
        )
        with real_service.get_session() as session:
            db_job = session.get(ScrapingJob, old_job.id)
            db_job.status = JobStatus.FAILED
            db_job.completed_at = datetime.now(timezone.utc) - timedelta(days=35)
            session.commit()

        deleted_count = real_service.cleanup_old_jobs(days=30)
        assert deleted_count == 1

        updated_job = real_service.get_job(old_job.id)
        assert updated_job.status == JobStatus.CANCELLED

    def test_cleanup_old_jobs_excludes_pending(self, real_service):
        """Test that cleanup excludes pending jobs."""
        # Create old pending job (shouldn't be cleaned up)
        old_job = real_service.create_job(
            url="https://example.com/old", output_directory="/tmp/test"
        )
        with real_service.get_session() as session:
            db_job = session.get(ScrapingJob, old_job.id)
            db_job.created_at = datetime.now(timezone.utc) - timedelta(days=40)
            session.commit()

        deleted_count = real_service.cleanup_old_jobs(days=30)
        assert deleted_count == 0

        # Job should still be pending
        updated_job = real_service.get_job(old_job.id)
        assert updated_job.status == JobStatus.PENDING

    def test_cleanup_old_jobs_database_error(self, mock_service, mock_session):
        """Test cleanup with database error."""
        mock_session.execute.side_effect = SQLAlchemyError("Database error")
        with pytest.raises(DatabaseError) as exc_info:
            mock_service.cleanup_old_jobs(days=30)
        assert "Job cleanup failed" in str(exc_info.value)
