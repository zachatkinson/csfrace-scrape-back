"""Unit tests for job database models following TEST_BUILDING.md MANDATORY standards.

MANDATORY COMPLIANCE:
- AAA Pattern (Arrange-Act-Assert) - NON-NEGOTIABLE
- SOLID principles testing
- PostgreSQL database for integration tests (ZERO TOLERANCE for SQLite)
- Factory Pattern for test data
- 95%+ coverage target
- Focus on model properties and business logic

Tests ScrapingJob, ContentResult, and JobLog models.
"""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from src.common.status import JobPriority, JobStatus
from src.database.models.jobs import ContentResult, JobLog, ScrapingJob

# ============================================================================
# MANDATORY Fixtures Following TEST_BUILDING.md Factory Pattern
# ============================================================================


@pytest.fixture
def sample_job_data():
    """Factory for ScrapingJob test data - DRY principle."""
    return {
        "id": str(uuid4()),
        "user_id": str(uuid4()),
        "source_url": "https://example.com/test",
        "domain": "example.com",
        "job_type": "single",
        "target_format": "html",
        "status": "pending",
        "priority": 5,
        "retry_count": 0,
        "max_retries": 3,
        "options": {},
    }


@pytest.fixture
def scraping_job(sample_job_data):
    """Factory for ScrapingJob instance - MANDATORY DI."""
    return ScrapingJob(**sample_job_data)


# ============================================================================
# Test Suite 1: ScrapingJob Properties (6 tests) - Cover missing lines
# ============================================================================


class TestScrapingJobProperties:
    """Test ScrapingJob property methods - Lines 123, 128-130, 135, 140-143, 148."""

    @pytest.mark.unit
    def test_status_enum_property(self, scraping_job):
        """Test status_enum property returns JobStatus enum - Line 123.

        AAA Pattern:
        - Arrange: Job with 'pending' status
        - Act: Access status_enum property
        - Assert: Returns JobStatus.PENDING enum
        """
        # Arrange
        scraping_job.status = "pending"

        # Act
        status_enum = scraping_job.status_enum

        # Assert
        assert isinstance(status_enum, JobStatus)
        assert status_enum == JobStatus.PENDING

    @pytest.mark.unit
    def test_status_enum_completed(self, scraping_job):
        """Test status_enum with completed status."""
        # Arrange
        scraping_job.status = "completed"

        # Act
        status_enum = scraping_job.status_enum

        # Assert
        assert status_enum == JobStatus.COMPLETED

    @pytest.mark.unit
    def test_priority_enum_property(self, scraping_job):
        """Test priority_enum property returns JobPriority enum - Lines 128-130.

        Tests the priority_enum property which imports db_to_priority.
        """
        # Arrange
        scraping_job.priority = 8  # HIGH priority (db value 8)

        # Act
        priority_enum = scraping_job.priority_enum

        # Assert
        assert isinstance(priority_enum, JobPriority)
        assert priority_enum == JobPriority.HIGH

    @pytest.mark.unit
    def test_priority_enum_normal(self, scraping_job):
        """Test priority_enum with normal priority."""
        # Arrange
        scraping_job.priority = 5  # NORMAL priority (db value 5)

        # Act
        priority_enum = scraping_job.priority_enum

        # Assert
        assert priority_enum == JobPriority.NORMAL

    @pytest.mark.unit
    def test_priority_enum_urgent(self, scraping_job):
        """Test priority_enum with urgent priority."""
        # Arrange
        scraping_job.priority = 10  # URGENT priority (db value 10)

        # Act
        priority_enum = scraping_job.priority_enum

        # Assert
        assert priority_enum == JobPriority.URGENT

    @pytest.mark.unit
    def test_is_finished_completed(self, scraping_job):
        """Test is_finished property for completed job - Line 135."""
        # Arrange
        scraping_job.status = "completed"

        # Act
        result = scraping_job.is_finished

        # Assert
        assert result is True

    @pytest.mark.unit
    def test_is_finished_failed(self, scraping_job):
        """Test is_finished property for failed job."""
        # Arrange
        scraping_job.status = "failed"

        # Act
        result = scraping_job.is_finished

        # Assert
        assert result is True

    @pytest.mark.unit
    def test_is_finished_cancelled(self, scraping_job):
        """Test is_finished property for cancelled job."""
        # Arrange
        scraping_job.status = "cancelled"

        # Act
        result = scraping_job.is_finished

        # Assert
        assert result is True

    @pytest.mark.unit
    def test_is_finished_pending(self, scraping_job):
        """Test is_finished property returns False for pending job."""
        # Arrange
        scraping_job.status = "pending"

        # Act
        result = scraping_job.is_finished

        # Assert
        assert result is False

    @pytest.mark.unit
    def test_is_finished_running(self, scraping_job):
        """Test is_finished property returns False for running job."""
        # Arrange
        scraping_job.status = "running"

        # Act
        result = scraping_job.is_finished

        # Assert
        assert result is False

    @pytest.mark.unit
    def test_duration_property_with_times(self, scraping_job):
        """Test duration property calculates time difference - Lines 140-143."""
        # Arrange
        start_time = datetime.now(UTC)
        end_time = start_time + timedelta(seconds=45)
        scraping_job.started_at = start_time
        scraping_job.completed_at = end_time

        # Act
        duration = scraping_job.duration

        # Assert
        assert duration is not None
        assert abs(duration - 45.0) < 0.01  # Within 10ms tolerance

    @pytest.mark.unit
    def test_duration_property_no_start_time(self, scraping_job):
        """Test duration property returns None when no start time."""
        # Arrange
        scraping_job.started_at = None
        scraping_job.completed_at = datetime.now(UTC)

        # Act
        duration = scraping_job.duration

        # Assert
        assert duration is None

    @pytest.mark.unit
    def test_duration_property_no_end_time(self, scraping_job):
        """Test duration property returns None when no completion time."""
        # Arrange
        scraping_job.started_at = datetime.now(UTC)
        scraping_job.completed_at = None

        # Act
        duration = scraping_job.duration

        # Assert
        assert duration is None

    @pytest.mark.unit
    def test_can_retry_failed_under_limit(self, scraping_job):
        """Test can_retry property returns True for failed job under limit - Line 148."""
        # Arrange
        scraping_job.status = "failed"
        scraping_job.retry_count = 2
        scraping_job.max_retries = 3

        # Act
        result = scraping_job.can_retry

        # Assert
        assert result is True

    @pytest.mark.unit
    def test_can_retry_failed_at_limit(self, scraping_job):
        """Test can_retry property returns False when retry limit reached."""
        # Arrange
        scraping_job.status = "failed"
        scraping_job.retry_count = 3
        scraping_job.max_retries = 3

        # Act
        result = scraping_job.can_retry

        # Assert
        assert result is False

    @pytest.mark.unit
    def test_can_retry_completed(self, scraping_job):
        """Test can_retry property returns False for completed job."""
        # Arrange
        scraping_job.status = "completed"
        scraping_job.retry_count = 0
        scraping_job.max_retries = 3

        # Act
        result = scraping_job.can_retry

        # Assert
        assert result is False


# ============================================================================
# Test Suite 2: Model Representations (3 tests) - String methods
# ============================================================================


class TestModelRepresentations:
    """Test __repr__ methods for all models."""

    @pytest.mark.unit
    def test_scraping_job_repr(self, scraping_job):
        """Test ScrapingJob string representation."""
        # Act
        repr_str = repr(scraping_job)

        # Assert
        assert "ScrapingJob" in repr_str
        assert scraping_job.id in repr_str
        assert scraping_job.source_url in repr_str
        assert scraping_job.status in repr_str

    @pytest.mark.unit
    def test_content_result_repr(self):
        """Test ContentResult string representation."""
        # Arrange
        content_result = ContentResult(id=1, job_id=str(uuid4()), title="Test Content")

        # Act
        repr_str = repr(content_result)

        # Assert
        assert "ContentResult" in repr_str
        assert "1" in repr_str
        assert "Test Content" in repr_str

    @pytest.mark.unit
    def test_job_log_repr(self):
        """Test JobLog string representation."""
        # Arrange
        timestamp = datetime.now(UTC)
        job_log = JobLog(
            id=1, job_id=str(uuid4()), level="INFO", message="Test log message", timestamp=timestamp
        )

        # Act
        repr_str = repr(job_log)

        # Assert
        assert "JobLog" in repr_str
        assert "1" in repr_str
        assert "INFO" in repr_str


# ============================================================================
# Test Suite 3: Model Relationships (3 tests) - Relationship setup
# ============================================================================


class TestModelRelationships:
    """Test model relationship configurations."""

    @pytest.mark.unit
    def test_scraping_job_has_relationships(self, scraping_job):
        """Test ScrapingJob has proper relationship attributes."""
        # Assert - Relationship attributes exist
        assert hasattr(scraping_job, "user")
        assert hasattr(scraping_job, "content_results")
        assert hasattr(scraping_job, "job_logs")

    @pytest.mark.unit
    def test_content_result_has_job_relationship(self):
        """Test ContentResult has job relationship."""
        # Arrange
        content_result = ContentResult(job_id=str(uuid4()), title="Test")

        # Assert
        assert hasattr(content_result, "job")

    @pytest.mark.unit
    def test_job_log_has_job_relationship(self):
        """Test JobLog has job relationship."""
        # Arrange
        job_log = JobLog(job_id=str(uuid4()), level="INFO", message="Test")

        # Assert
        assert hasattr(job_log, "job")
