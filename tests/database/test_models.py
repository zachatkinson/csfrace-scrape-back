"""Tests for database models and schema validation."""

from datetime import datetime

import pytest

from src.database.models import (
    Batch,
    ContentResult,
    JobLog,
    JobPriority,
    JobStatus,
    ScrapingJob,
    SystemMetrics,
    create_database_engine,
    get_database_url,
)


class TestDatabaseModels:
    """Test database model definitions and relationships using Testcontainers.

    Following 2025 best practices:
    - Use real PostgreSQL instead of mocks for higher confidence
    - Testcontainers provide automatic container lifecycle management
    - No more skipping tests when database unavailable
    """

    def test_scraping_job_model_creation(self, testcontainers_db_service):
        """Test ScrapingJob model creation with required fields."""
        job = ScrapingJob(
            url="https://example.com/test-post",
            domain="example.com",
            slug="test-post",
            output_directory="/tmp/output",
        )

        with testcontainers_db_service.get_session() as session:
            session.add(job)
            session.commit()

        # Verify job was created with correct defaults
        assert job.id is not None
        assert job.status == JobStatus.PENDING
        assert job.priority == JobPriority.NORMAL
        assert job.retry_count == 0
        assert job.success is False
        assert job.images_downloaded == 0
        assert job.created_at is not None
        assert isinstance(job.created_at, datetime)

    def test_scraping_job_properties(self, testcontainers_db_service):
        """Test ScrapingJob computed properties."""
        job = ScrapingJob(
            url="https://example.com/test",
            domain="example.com",
            output_directory="/tmp/output",
        )

        # Test duration calculation
        assert job.duration is None  # No start/end time

        job.start_time = 100.0
        job.end_time = 105.5
        assert job.duration == 5.5

        # Test is_finished property
        assert not job.is_finished  # PENDING status

        job.status = JobStatus.COMPLETED
        assert job.is_finished

        job.status = JobStatus.FAILED
        assert job.is_finished

        job.status = JobStatus.RUNNING
        assert not job.is_finished

    def test_scraping_job_can_retry_property(self, testcontainers_db_service):
        """Test ScrapingJob can_retry property logic."""
        job = ScrapingJob(
            url="https://example.com/test",
            domain="example.com",
            output_directory="/tmp/output",
            max_retries=3,
        )

        # Cannot retry when not failed
        assert not job.can_retry

        # Can retry when failed and under limit
        job.status = JobStatus.FAILED
        job.retry_count = 1
        assert job.can_retry

        # Cannot retry when retry limit reached
        job.retry_count = 3
        assert not job.can_retry

    def test_batch_model_creation(self, testcontainers_db_service):
        """Test Batch model creation and defaults."""
        batch = Batch(
            name="Test Batch",
            description="A test batch for validation",
            output_base_directory="/tmp/batch_output",
        )

        with testcontainers_db_service.get_session() as session:
            session.add(batch)
            session.commit()

        assert batch.id is not None
        assert batch.status == JobStatus.PENDING
        assert batch.max_concurrent == 5
        assert batch.continue_on_error is True
        assert batch.total_jobs == 0
        assert batch.completed_jobs == 0
        assert batch.failed_jobs == 0
        assert batch.skipped_jobs == 0
        assert batch.created_at is not None

    def test_batch_success_rate_property(self, testcontainers_db_service):
        """Test Batch success_rate property calculation."""
        batch = Batch(name="Test Batch", output_base_directory="/tmp/output")

        # Empty batch has 0% success rate
        assert batch.success_rate == 0.0

        # Batch with completed jobs
        batch.total_jobs = 10
        batch.completed_jobs = 8
        assert batch.success_rate == 0.8

        # All completed
        batch.completed_jobs = 10
        assert batch.success_rate == 1.0

    def test_job_batch_relationship(self, testcontainers_db_service):
        """Test relationship between jobs and batches."""
        with testcontainers_db_service.get_session() as session:
            # Create batch
            batch = Batch(name="Test Batch", output_base_directory="/tmp/output")
            session.add(batch)
            session.flush()

            # Create jobs in batch
            job1 = ScrapingJob(
                url="https://example.com/post1",
                domain="example.com",
                output_directory="/tmp/output/post1",
                batch_id=batch.id,
            )
            job2 = ScrapingJob(
                url="https://example.com/post2",
                domain="example.com",
                output_directory="/tmp/output/post2",
                batch_id=batch.id,
            )

            session.add_all([job1, job2])
            session.commit()

            # Test relationships
            session.refresh(batch)
            assert len(batch.jobs) == 2
            assert job1.batch == batch
            assert job2.batch == batch

    def test_content_result_model(self, testcontainers_db_service):
        """Test ContentResult model creation and relationships."""
        with testcontainers_db_service.get_session() as session:
            # Create job first
            job = ScrapingJob(
                url="https://example.com/test",
                domain="example.com",
                output_directory="/tmp/output",
            )
            session.add(job)
            session.flush()

            # Create content result
            content = ContentResult(
                job_id=job.id,
                title="Test Article",
                converted_html="<p>Test content</p>",
                meta_description="Test description",
                word_count=100,
                image_count=5,
            )
            session.add(content)
            session.commit()

            # Verify creation and relationships
            assert content.id is not None
            assert content.job == job
            assert content.created_at is not None
            assert content.updated_at is not None

            # Test job relationship
            session.refresh(job)
            assert len(job.content_results) == 1
            assert job.content_results[0] == content

    def test_job_log_model(self, testcontainers_db_service):
        """Test JobLog model creation and relationships."""
        with testcontainers_db_service.get_session() as session:
            # Create job first
            job = ScrapingJob(
                url="https://example.com/test",
                domain="example.com",
                output_directory="/tmp/output",
            )
            session.add(job)
            session.flush()

            # Create log entries
            log1 = JobLog(
                job_id=job.id,
                level="INFO",
                message="Starting job processing",
                component="processor",
                operation="start",
                context_data={"step": "initialization"},
            )
            log2 = JobLog(
                job_id=job.id,
                level="ERROR",
                message="Processing failed",
                component="html_processor",
                exception_type="ProcessingError",
            )

            session.add_all([log1, log2])
            session.commit()

            # Verify creation and relationships
            assert log1.id is not None
            assert log2.id is not None
            assert log1.job == job
            assert log2.job == job

            # Test job relationship
            session.refresh(job)
            assert len(job.job_logs) == 2

    def test_system_metrics_model(self, testcontainers_db_service):
        """Test SystemMetrics model creation and data types."""
        metrics = [
            SystemMetrics(
                metric_type="performance",
                metric_name="avg_processing_time",
                numeric_value=2.5,
                component="html_processor",
                environment="test",
            ),
            SystemMetrics(
                metric_type="status",
                metric_name="system_health",
                string_value="healthy",
                component="system",
                environment="production",
            ),
            SystemMetrics(
                metric_type="detailed",
                metric_name="job_statistics",
                json_value={"completed": 100, "failed": 5, "success_rate": 0.95},
                tags={"version": "1.0.0", "region": "us-east-1"},
            ),
        ]

        with testcontainers_db_service.get_session() as session:
            session.add_all(metrics)
            session.commit()

            # Verify all metrics were created
            for metric in metrics:
                assert metric.id is not None
                assert metric.timestamp is not None
                assert isinstance(metric.timestamp, datetime)

    def test_enum_values(self):
        """Test enum value definitions."""
        # JobStatus enum
        assert JobStatus.PENDING.value == "pending"
        assert JobStatus.RUNNING.value == "running"
        assert JobStatus.COMPLETED.value == "completed"
        assert JobStatus.FAILED.value == "failed"
        assert JobStatus.SKIPPED.value == "skipped"
        assert JobStatus.CANCELLED.value == "cancelled"

        # JobPriority enum
        assert JobPriority.LOW.value == "low"
        assert JobPriority.NORMAL.value == "normal"
        assert JobPriority.HIGH.value == "high"
        assert JobPriority.URGENT.value == "urgent"

    def test_cascade_deletion(self, testcontainers_db_service):
        """Test cascade deletion of related records."""
        # Store IDs for verification
        batch_id = None
        job_id = None
        content_id = None
        log_entry_id = None

        # Create and delete data in separate session
        with testcontainers_db_service.get_session() as session:
            # Create batch with jobs
            batch = Batch(name="Test Batch", output_base_directory="/tmp/output")
            session.add(batch)
            session.flush()

            job = ScrapingJob(
                url="https://example.com/test",
                domain="example.com",
                output_directory="/tmp/output",
                batch_id=batch.id,
            )
            session.add(job)
            session.flush()

            # Add content result and log
            content = ContentResult(job_id=job.id, title="Test")
            log_entry = JobLog(job_id=job.id, level="INFO", message="Test log")
            session.add_all([content, log_entry])
            session.commit()

            # Store IDs before deletion
            batch_id = batch.id
            job_id = job.id
            content_id = content.id
            log_entry_id = log_entry.id

            # Delete batch - should cascade to jobs and their related data
            session.delete(batch)
            session.commit()

        # Verify cascade deletion using fresh session
        with testcontainers_db_service.get_session() as verification_session:
            assert verification_session.get(Batch, batch_id) is None
            assert verification_session.get(ScrapingJob, job_id) is None
            assert verification_session.get(ContentResult, content_id) is None
            assert verification_session.get(JobLog, log_entry_id) is None


class TestDatabaseUtilities:
    """Test database utility functions."""

    def test_get_database_url_default(self):
        """Test database URL generation with environment configuration (CLAUDE.md compliance)."""
        url = get_database_url()
        assert url.startswith("postgresql+psycopg://")
        # Should use environment variables, not hardcoded defaults
        assert "localhost" in url
        assert "5432" in url
        assert len(url) > 30  # Basic sanity check for valid URL format

    def test_get_database_url_environment_override(self, monkeypatch):
        """Test database URL generation with environment variable overrides."""
        # Clear DATABASE_URL so individual components are used instead
        monkeypatch.delenv("DATABASE_URL", raising=False)
        monkeypatch.setenv("DATABASE_HOST", "testhost")
        monkeypatch.setenv("DATABASE_PORT", "5433")
        monkeypatch.setenv("DATABASE_NAME", "testdb")
        monkeypatch.setenv("DATABASE_USER", "testuser")
        monkeypatch.setenv("DATABASE_PASSWORD", "testpass")

        url = get_database_url()
        expected = "postgresql+psycopg://testuser:testpass@testhost:5433/testdb"
        assert url == expected

    def test_create_database_engine(self):
        """Test database engine creation with proper configuration."""
        engine = create_database_engine(echo=False)

        # Verify engine configuration (CLAUDE.md compliance - use environment values)
        assert engine.url.drivername == "postgresql+psycopg"
        # Database name comes from environment variables, not hardcoded values
        assert engine.url.database is not None
        assert len(str(engine.url.database)) > 0

        # Test that engine can be created without errors
        assert engine is not None
        assert engine.echo is False

    def test_database_engine_with_echo(self):
        """Test database engine creation with SQL echo enabled."""
        engine = create_database_engine(echo=True)
        assert engine.echo is True

    def test_database_connection_string_format(self):
        """Test that database URL follows PostgreSQL connection string format."""
        url = get_database_url()

        # Should follow postgresql+psycopg://user:password@host:port/database format
        parts = url.split("://")
        assert parts[0] == "postgresql+psycopg"

        connection_part = parts[1]
        assert "@" in connection_part  # Should have user@host format
        assert ":" in connection_part  # Should have port specification


class TestModelConstraintsAndValidation:
    """Test model constraints and data validation."""

    def test_required_fields_validation(self, testcontainers_db_service):
        """Test that required fields are enforced."""
        # ScrapingJob missing required url
        with pytest.raises(Exception):  # SQLAlchemy will raise IntegrityError or similar
            with testcontainers_db_service.get_session() as session:
                job = ScrapingJob(domain="example.com", output_directory="/tmp/output")
                session.add(job)
                session.commit()

    def test_string_length_limits(self, testcontainers_db_service):
        """Test string field length constraints."""
        # Test very long URL (should work up to 2048 chars)
        long_url = "https://example.com/" + "a" * 2000
        job = ScrapingJob(
            url=long_url,
            domain="example.com",
            output_directory="/tmp/output",
        )
        with testcontainers_db_service.get_session() as session:
            session.add(job)
            session.commit()

            assert job.id is not None
            assert job.url == long_url

    def test_datetime_defaults(self, testcontainers_db_service):
        """Test that datetime fields have proper defaults."""
        job = ScrapingJob(
            url="https://example.com/test",
            domain="example.com",
            output_directory="/tmp/output",
        )
        with testcontainers_db_service.get_session() as session:
            session.add(job)
            session.commit()

            # created_at should be set automatically
            assert job.created_at is not None
            assert isinstance(job.created_at, datetime)

            # Other datetime fields should be None initially
            assert job.started_at is None
            assert job.completed_at is None
            assert job.next_retry_at is None

    def test_json_field_storage(self, testcontainers_db_service):
        """Test JSON field storage and retrieval."""
        test_config = {
            "max_concurrent_downloads": 10,
            "timeout": 30,
            "custom_settings": {
                "nested": {"value": True},
                "list": [1, 2, 3],
            },
        }

        job = ScrapingJob(
            url="https://example.com/test",
            domain="example.com",
            output_directory="/tmp/output",
            converter_config=test_config,
        )
        with testcontainers_db_service.get_session() as session:
            session.add(job)
            session.commit()

            # Retrieve and verify JSON data
            session.refresh(job)
            assert job.converter_config == test_config
            assert job.converter_config["max_concurrent_downloads"] == 10
            assert job.converter_config["custom_settings"]["nested"]["value"] is True

    def test_foreign_key_constraints(self, testcontainers_db_service):
        """Test foreign key relationships and constraints."""
        with testcontainers_db_service.get_session() as session:
            # Create job without batch (should work)
            job1 = ScrapingJob(
                url="https://example.com/test1",
                domain="example.com",
                output_directory="/tmp/output",
            )
            session.add(job1)
            session.commit()
            assert job1.batch_id is None

            # Create batch and job with relationship
            batch = Batch(name="Test Batch", output_base_directory="/tmp/batch")
            session.add(batch)
            session.flush()

            job2 = ScrapingJob(
                url="https://example.com/test2",
                domain="example.com",
                output_directory="/tmp/output",
                batch_id=batch.id,
            )
            session.add(job2)
            session.commit()

            assert job2.batch_id == batch.id
            assert job2.batch == batch
