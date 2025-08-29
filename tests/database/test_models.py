"""Tests for database models and schema validation."""

from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database.models import (
    Base,
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
    """Test database model definitions and relationships."""

    @pytest.fixture
    def temp_db_engine(self):
        """Create temporary PostgreSQL test database for testing."""
        import os

        postgres_url = os.getenv(
            "TEST_DATABASE_URL",
            "postgresql+psycopg://test_user:test_password@localhost:5432/test_db",
        )
        engine = create_engine(postgres_url, echo=False)
        Base.metadata.create_all(engine)
        return engine

    @pytest.fixture
    def db_session(self, temp_db_engine):
        """Create database session for testing."""
        SessionLocal = sessionmaker(bind=temp_db_engine)
        session = SessionLocal()
        try:
            yield session
        finally:
            session.close()

    def test_scraping_job_model_creation(self, db_session):
        """Test ScrapingJob model creation with required fields."""
        job = ScrapingJob(
            url="https://example.com/test-post",
            domain="example.com",
            slug="test-post",
            output_directory="/tmp/output",
        )

        db_session.add(job)
        db_session.commit()

        # Verify job was created with correct defaults
        assert job.id is not None
        assert job.status == JobStatus.PENDING
        assert job.priority == JobPriority.NORMAL
        assert job.retry_count == 0
        assert job.success is False
        assert job.images_downloaded == 0
        assert job.created_at is not None
        assert isinstance(job.created_at, datetime)

    def test_scraping_job_properties(self, db_session):
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

    def test_scraping_job_can_retry_property(self, db_session):
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

    def test_batch_model_creation(self, db_session):
        """Test Batch model creation and defaults."""
        batch = Batch(
            name="Test Batch",
            description="A test batch for validation",
            output_base_directory="/tmp/batch_output",
        )

        db_session.add(batch)
        db_session.commit()

        assert batch.id is not None
        assert batch.status == JobStatus.PENDING
        assert batch.max_concurrent == 3
        assert batch.continue_on_error is True
        assert batch.total_jobs == 0
        assert batch.completed_jobs == 0
        assert batch.failed_jobs == 0
        assert batch.skipped_jobs == 0
        assert batch.created_at is not None

    def test_batch_success_rate_property(self, db_session):
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

    def test_job_batch_relationship(self, db_session):
        """Test relationship between jobs and batches."""
        # Create batch
        batch = Batch(name="Test Batch", output_base_directory="/tmp/output")
        db_session.add(batch)
        db_session.flush()

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

        db_session.add_all([job1, job2])
        db_session.commit()

        # Test relationships
        db_session.refresh(batch)
        assert len(batch.jobs) == 2
        assert job1.batch == batch
        assert job2.batch == batch

    def test_content_result_model(self, db_session):
        """Test ContentResult model creation and relationships."""
        # Create job first
        job = ScrapingJob(
            url="https://example.com/test",
            domain="example.com",
            output_directory="/tmp/output",
        )
        db_session.add(job)
        db_session.flush()

        # Create content result
        content = ContentResult(
            job_id=job.id,
            title="Test Article",
            converted_html="<p>Test content</p>",
            meta_description="Test description",
            word_count=100,
            image_count=5,
        )
        db_session.add(content)
        db_session.commit()

        # Verify creation and relationships
        assert content.id is not None
        assert content.job == job
        assert content.created_at is not None
        assert content.updated_at is not None

        # Test job relationship
        db_session.refresh(job)
        assert len(job.content_results) == 1
        assert job.content_results[0] == content

    def test_job_log_model(self, db_session):
        """Test JobLog model creation and relationships."""
        # Create job first
        job = ScrapingJob(
            url="https://example.com/test",
            domain="example.com",
            output_directory="/tmp/output",
        )
        db_session.add(job)
        db_session.flush()

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

        db_session.add_all([log1, log2])
        db_session.commit()

        # Verify creation and relationships
        assert log1.id is not None
        assert log2.id is not None
        assert log1.job == job
        assert log2.job == job

        # Test job relationship
        db_session.refresh(job)
        assert len(job.job_logs) == 2

    def test_system_metrics_model(self, db_session):
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

        db_session.add_all(metrics)
        db_session.commit()

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

    def test_cascade_deletion(self, db_session):
        """Test cascade deletion of related records."""
        # Create batch with jobs
        batch = Batch(name="Test Batch", output_base_directory="/tmp/output")
        db_session.add(batch)
        db_session.flush()

        job = ScrapingJob(
            url="https://example.com/test",
            domain="example.com",
            output_directory="/tmp/output",
            batch_id=batch.id,
        )
        db_session.add(job)
        db_session.flush()

        # Add content result and log
        content = ContentResult(job_id=job.id, title="Test")
        log_entry = JobLog(job_id=job.id, level="INFO", message="Test log")
        db_session.add_all([content, log_entry])
        db_session.commit()

        # Delete batch - should cascade to jobs and their related data
        db_session.delete(batch)
        db_session.commit()

        # Verify cascade deletion
        assert db_session.get(ScrapingJob, job.id) is None
        assert db_session.get(ContentResult, content.id) is None
        assert db_session.get(JobLog, log_entry.id) is None


class TestDatabaseUtilities:
    """Test database utility functions."""

    def test_get_database_url_default(self):
        """Test database URL generation with default configuration."""
        url = get_database_url()
        assert url.startswith("postgresql+psycopg://")
        assert "scraper_user:scraper_password@localhost:5432/scraper_db" in url

    def test_get_database_url_environment_override(self, monkeypatch):
        """Test database URL generation with environment variable overrides."""
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

        # Verify engine configuration
        assert engine.url.drivername == "postgresql+psycopg"
        assert "scraper_db" in str(engine.url.database)

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

    @pytest.fixture
    def temp_db_engine(self):
        """Create temporary PostgreSQL test database for testing."""
        import os

        postgres_url = os.getenv(
            "TEST_DATABASE_URL",
            "postgresql+psycopg://test_user:test_password@localhost:5432/test_db",
        )
        engine = create_engine(postgres_url, echo=False)
        Base.metadata.create_all(engine)
        return engine

    @pytest.fixture
    def db_session(self, temp_db_engine):
        """Create database session for testing."""
        SessionLocal = sessionmaker(bind=temp_db_engine)
        session = SessionLocal()
        try:
            yield session
        finally:
            session.close()

    def test_required_fields_validation(self, db_session):
        """Test that required fields are enforced."""
        # ScrapingJob missing required url
        with pytest.raises(Exception):  # SQLAlchemy will raise IntegrityError or similar
            job = ScrapingJob(domain="example.com", output_directory="/tmp/output")
            db_session.add(job)
            db_session.commit()

    def test_string_length_limits(self, db_session):
        """Test string field length constraints."""
        # Test very long URL (should work up to 2048 chars)
        long_url = "https://example.com/" + "a" * 2000
        job = ScrapingJob(
            url=long_url,
            domain="example.com",
            output_directory="/tmp/output",
        )
        db_session.add(job)
        db_session.commit()

        assert job.id is not None
        assert job.url == long_url

    def test_datetime_defaults(self, db_session):
        """Test that datetime fields have proper defaults."""
        job = ScrapingJob(
            url="https://example.com/test",
            domain="example.com",
            output_directory="/tmp/output",
        )
        db_session.add(job)
        db_session.commit()

        # created_at should be set automatically
        assert job.created_at is not None
        assert isinstance(job.created_at, datetime)

        # Other datetime fields should be None initially
        assert job.started_at is None
        assert job.completed_at is None
        assert job.next_retry_at is None

    def test_json_field_storage(self, db_session):
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
        db_session.add(job)
        db_session.commit()

        # Retrieve and verify JSON data
        db_session.refresh(job)
        assert job.converter_config == test_config
        assert job.converter_config["max_concurrent_downloads"] == 10
        assert job.converter_config["custom_settings"]["nested"]["value"] is True

    def test_foreign_key_constraints(self, db_session):
        """Test foreign key relationships and constraints."""
        # Create job without batch (should work)
        job1 = ScrapingJob(
            url="https://example.com/test1",
            domain="example.com",
            output_directory="/tmp/output",
        )
        db_session.add(job1)
        db_session.commit()
        assert job1.batch_id is None

        # Create batch and job with relationship
        batch = Batch(name="Test Batch", output_base_directory="/tmp/batch")
        db_session.add(batch)
        db_session.flush()

        job2 = ScrapingJob(
            url="https://example.com/test2",
            domain="example.com",
            output_directory="/tmp/output",
            batch_id=batch.id,
        )
        db_session.add(job2)
        db_session.commit()

        assert job2.batch_id == batch.id
        assert job2.batch == batch
