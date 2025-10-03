"""Comprehensive test suite for LoggingService following TEST_BUILDING.md standards.

This module tests all logging-related database operations:
- Adding job log entries with metadata
- Retrieving logs by job ID and level
- Getting recent logs across all jobs
- Filtering error-level logs
- Counting logs by level
- Validation and error handling
- Edge cases with context data
"""

import pytest

from src.core.exceptions import ValidationError
from src.database.models.auth import (
    User,  # noqa: F401 - Import at module level for test_database_engine
)
from src.database.services.job_service import JobService
from src.database.services.logging_service import JobLogRequest, LoggingService
from tests.conftest import JobFactory


class TestLoggingServiceAddLog:
    """Test adding job log entries."""

    @pytest.mark.database
    def test_add_job_log_basic(self, test_session):
        """Test adding basic job log entry."""
        # Arrange
        job_service = JobService(test_session)
        logging_service = LoggingService(test_session)

        job = job_service.create_job(JobFactory.create_job_request(session=test_session))
        test_session.commit()

        request = JobLogRequest(job_id=job.id, level="INFO", message="Test log message")

        # Act
        log_entry = logging_service.add_job_log(request)
        test_session.commit()

        # Assert
        assert log_entry is not None
        assert log_entry.job_id == job.id
        assert log_entry.level == "INFO"
        assert log_entry.message == "Test log message"
        assert log_entry.timestamp is not None
        assert log_entry.component is None
        assert log_entry.operation is None

    @pytest.mark.database
    def test_add_job_log_with_all_fields(self, test_session):
        """Test adding log entry with all optional fields."""
        # Arrange
        job_service = JobService(test_session)
        logging_service = LoggingService(test_session)

        job = job_service.create_job(JobFactory.create_job_request(session=test_session))
        test_session.commit()

        context_data = {"url": "https://example.com", "retry_count": 2, "duration_ms": 1500}

        request = JobLogRequest(
            job_id=job.id,
            level="ERROR",
            message="Failed to fetch page",
            component="scraper",
            operation="fetch_page",
            context_data=context_data,
        )

        # Act
        log_entry = logging_service.add_job_log(request)
        test_session.commit()

        # Assert
        assert log_entry.component == "scraper"
        assert log_entry.operation == "fetch_page"
        assert log_entry.context_data == context_data

    @pytest.mark.database
    def test_add_job_log_level_normalization(self, test_session):
        """Test log level is normalized to uppercase."""
        # Arrange
        job_service = JobService(test_session)
        logging_service = LoggingService(test_session)

        job = job_service.create_job(JobFactory.create_job_request(session=test_session))
        test_session.commit()

        request = JobLogRequest(job_id=job.id, level="debug", message="Debug message")

        # Act
        log_entry = logging_service.add_job_log(request)
        test_session.commit()

        # Assert
        assert log_entry.level == "DEBUG"

    @pytest.mark.database
    def test_add_job_log_all_levels(self, test_session):
        """Test adding logs with all valid levels."""
        # Arrange
        job_service = JobService(test_session)
        logging_service = LoggingService(test_session)

        job = job_service.create_job(JobFactory.create_job_request(session=test_session))
        test_session.commit()

        levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]

        # Act & Assert
        for level in levels:
            request = JobLogRequest(job_id=job.id, level=level, message=f"{level} message")
            log_entry = logging_service.add_job_log(request)
            test_session.commit()
            assert log_entry.level == level

    @pytest.mark.database
    def test_add_job_log_message_trimmed(self, test_session):
        """Test log message is trimmed of whitespace."""
        # Arrange
        job_service = JobService(test_session)
        logging_service = LoggingService(test_session)

        job = job_service.create_job(JobFactory.create_job_request(session=test_session))
        test_session.commit()

        request = JobLogRequest(job_id=job.id, level="INFO", message="  Test message  ")

        # Act
        log_entry = logging_service.add_job_log(request)
        test_session.commit()

        # Assert
        assert log_entry.message == "Test message"

    @pytest.mark.database
    def test_add_job_log_multiple_entries(self, test_session):
        """Test adding multiple log entries for same job."""
        # Arrange
        job_service = JobService(test_session)
        logging_service = LoggingService(test_session)

        job = job_service.create_job(JobFactory.create_job_request(session=test_session))
        test_session.commit()

        # Act
        for i in range(5):
            request = JobLogRequest(job_id=job.id, level="INFO", message=f"Message {i}")
            logging_service.add_job_log(request)

        test_session.commit()

        # Assert
        logs = logging_service.get_job_logs(job.id)
        assert len(logs) == 5


class TestLoggingServiceValidation:
    """Test validation and error handling."""

    @pytest.mark.database
    def test_add_job_log_empty_job_id_raises_error(self, test_session):
        """Test that empty job_id raises ValidationError."""
        # Arrange
        logging_service = LoggingService(test_session)

        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            JobLogRequest(job_id="", level="INFO", message="Test message")

        assert exc_info.value.details.get("field") == "job_id"

    @pytest.mark.database
    def test_add_job_log_empty_message_raises_error(self, test_session):
        """Test that empty message raises ValidationError."""
        # Arrange
        job_service = JobService(test_session)
        job = job_service.create_job(JobFactory.create_job_request(session=test_session))
        test_session.commit()

        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            JobLogRequest(job_id=job.id, level="INFO", message="")

        assert exc_info.value.details.get("field") == "message"

    @pytest.mark.database
    def test_add_job_log_whitespace_message_raises_error(self, test_session):
        """Test that whitespace-only message raises ValidationError."""
        # Arrange
        job_service = JobService(test_session)
        job = job_service.create_job(JobFactory.create_job_request(session=test_session))
        test_session.commit()

        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            JobLogRequest(job_id=job.id, level="INFO", message="   ")

        assert exc_info.value.details.get("field") == "message"

    @pytest.mark.database
    def test_add_job_log_invalid_level_raises_error(self, test_session):
        """Test that invalid log level raises ValidationError."""
        # Arrange
        job_service = JobService(test_session)
        job = job_service.create_job(JobFactory.create_job_request(session=test_session))
        test_session.commit()

        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            JobLogRequest(job_id=job.id, level="INVALID", message="Test message")

        assert exc_info.value.details.get("field") == "level"


class TestLoggingServiceGetLogs:
    """Test retrieving job logs."""

    @pytest.mark.database
    def test_get_job_logs_basic(self, test_session):
        """Test retrieving logs for a specific job."""
        # Arrange
        job_service = JobService(test_session)
        logging_service = LoggingService(test_session)

        job = job_service.create_job(JobFactory.create_job_request(session=test_session))
        test_session.commit()

        # Add logs
        for i in range(3):
            request = JobLogRequest(job_id=job.id, level="INFO", message=f"Message {i}")
            logging_service.add_job_log(request)

        test_session.commit()

        # Act
        logs = logging_service.get_job_logs(job.id)

        # Assert
        assert len(logs) == 3

    @pytest.mark.database
    def test_get_job_logs_no_logs(self, test_session):
        """Test retrieving logs for job with no logs."""
        # Arrange
        job_service = JobService(test_session)
        logging_service = LoggingService(test_session)

        job = job_service.create_job(JobFactory.create_job_request(session=test_session))
        test_session.commit()

        # Act
        logs = logging_service.get_job_logs(job.id)

        # Assert
        assert len(logs) == 0

    @pytest.mark.database
    def test_get_job_logs_with_level_filter(self, test_session):
        """Test retrieving logs filtered by level."""
        # Arrange
        job_service = JobService(test_session)
        logging_service = LoggingService(test_session)

        job = job_service.create_job(JobFactory.create_job_request(session=test_session))
        test_session.commit()

        # Add logs with different levels
        logging_service.add_job_log(JobLogRequest(job_id=job.id, level="INFO", message="Info 1"))
        logging_service.add_job_log(JobLogRequest(job_id=job.id, level="ERROR", message="Error 1"))
        logging_service.add_job_log(JobLogRequest(job_id=job.id, level="INFO", message="Info 2"))
        logging_service.add_job_log(JobLogRequest(job_id=job.id, level="ERROR", message="Error 2"))
        test_session.commit()

        # Act
        error_logs = logging_service.get_job_logs(job.id, level="ERROR")

        # Assert
        assert len(error_logs) == 2
        assert all(log.level == "ERROR" for log in error_logs)

    @pytest.mark.database
    def test_get_job_logs_ordered_newest_first(self, test_session):
        """Test logs are ordered by timestamp (newest first)."""
        # Arrange
        job_service = JobService(test_session)
        logging_service = LoggingService(test_session)

        job = job_service.create_job(JobFactory.create_job_request(session=test_session))
        test_session.commit()

        # Add logs
        logging_service.add_job_log(JobLogRequest(job_id=job.id, level="INFO", message="First"))
        logging_service.add_job_log(JobLogRequest(job_id=job.id, level="INFO", message="Second"))
        logging_service.add_job_log(JobLogRequest(job_id=job.id, level="INFO", message="Third"))
        test_session.commit()

        # Act
        logs = logging_service.get_job_logs(job.id)

        # Assert
        assert logs[0].message == "Third"
        assert logs[1].message == "Second"
        assert logs[2].message == "First"

    @pytest.mark.database
    def test_get_job_logs_respects_limit(self, test_session):
        """Test limit parameter restricts number of logs returned."""
        # Arrange
        job_service = JobService(test_session)
        logging_service = LoggingService(test_session)

        job = job_service.create_job(JobFactory.create_job_request(session=test_session))
        test_session.commit()

        # Add many logs
        for i in range(20):
            request = JobLogRequest(job_id=job.id, level="INFO", message=f"Message {i}")
            logging_service.add_job_log(request)

        test_session.commit()

        # Act
        logs = logging_service.get_job_logs(job.id, limit=5)

        # Assert
        assert len(logs) == 5

    @pytest.mark.database
    def test_get_job_logs_case_insensitive_level(self, test_session):
        """Test level filter is case-insensitive."""
        # Arrange
        job_service = JobService(test_session)
        logging_service = LoggingService(test_session)

        job = job_service.create_job(JobFactory.create_job_request(session=test_session))
        test_session.commit()

        logging_service.add_job_log(JobLogRequest(job_id=job.id, level="ERROR", message="Error"))
        test_session.commit()

        # Act
        logs = logging_service.get_job_logs(job.id, level="error")

        # Assert
        assert len(logs) == 1


class TestLoggingServiceRecentLogs:
    """Test getting recent logs across all jobs."""

    @pytest.mark.database
    def test_get_recent_logs_basic(self, test_session):
        """Test getting recent logs across all jobs."""
        # Arrange
        job_service = JobService(test_session)
        logging_service = LoggingService(test_session)

        # Create multiple jobs with logs
        for _ in range(3):
            job = job_service.create_job(JobFactory.create_job_request(session=test_session))
            logging_service.add_job_log(JobLogRequest(job_id=job.id, level="INFO", message="Log"))

        test_session.commit()

        # Act
        logs = logging_service.get_recent_logs(limit=100)

        # Assert
        assert len(logs) == 3

    @pytest.mark.database
    def test_get_recent_logs_respects_limit(self, test_session):
        """Test recent logs respects limit parameter."""
        # Arrange
        job_service = JobService(test_session)
        logging_service = LoggingService(test_session)

        job = job_service.create_job(JobFactory.create_job_request(session=test_session))

        for i in range(10):
            logging_service.add_job_log(
                JobLogRequest(job_id=job.id, level="INFO", message=f"Message {i}")
            )

        test_session.commit()

        # Act
        logs = logging_service.get_recent_logs(limit=5)

        # Assert
        assert len(logs) == 5

    @pytest.mark.database
    def test_get_recent_logs_no_logs(self, test_session):
        """Test getting recent logs when no logs exist."""
        # Arrange
        logging_service = LoggingService(test_session)

        # Act
        logs = logging_service.get_recent_logs()

        # Assert
        assert len(logs) == 0


class TestLoggingServiceErrorLogs:
    """Test getting error-level logs."""

    @pytest.mark.database
    def test_get_error_logs_basic(self, test_session):
        """Test getting error-level logs."""
        # Arrange
        job_service = JobService(test_session)
        logging_service = LoggingService(test_session)

        job = job_service.create_job(JobFactory.create_job_request(session=test_session))

        # Add logs with different levels
        logging_service.add_job_log(JobLogRequest(job_id=job.id, level="INFO", message="Info"))
        logging_service.add_job_log(JobLogRequest(job_id=job.id, level="ERROR", message="Error"))
        logging_service.add_job_log(
            JobLogRequest(job_id=job.id, level="CRITICAL", message="Critical")
        )
        logging_service.add_job_log(
            JobLogRequest(job_id=job.id, level="WARNING", message="Warning")
        )

        test_session.commit()

        # Act
        error_logs = logging_service.get_error_logs()

        # Assert
        assert len(error_logs) == 2  # ERROR and CRITICAL
        assert all(log.level in ["ERROR", "CRITICAL"] for log in error_logs)

    @pytest.mark.database
    def test_get_error_logs_no_errors(self, test_session):
        """Test getting error logs when no errors exist."""
        # Arrange
        job_service = JobService(test_session)
        logging_service = LoggingService(test_session)

        job = job_service.create_job(JobFactory.create_job_request(session=test_session))
        logging_service.add_job_log(JobLogRequest(job_id=job.id, level="INFO", message="Info"))
        test_session.commit()

        # Act
        error_logs = logging_service.get_error_logs()

        # Assert
        assert len(error_logs) == 0

    @pytest.mark.database
    def test_get_error_logs_respects_limit(self, test_session):
        """Test error logs respects limit parameter."""
        # Arrange
        job_service = JobService(test_session)
        logging_service = LoggingService(test_session)

        job = job_service.create_job(JobFactory.create_job_request(session=test_session))

        for i in range(10):
            logging_service.add_job_log(
                JobLogRequest(job_id=job.id, level="ERROR", message=f"Error {i}")
            )

        test_session.commit()

        # Act
        error_logs = logging_service.get_error_logs(limit=3)

        # Assert
        assert len(error_logs) == 3


class TestLoggingServiceCountLogs:
    """Test counting logs by level."""

    @pytest.mark.database
    def test_count_logs_by_level_basic(self, test_session):
        """Test counting logs by level for all jobs."""
        # Arrange
        job_service = JobService(test_session)
        logging_service = LoggingService(test_session)

        job = job_service.create_job(JobFactory.create_job_request(session=test_session))

        # Add logs with different levels
        logging_service.add_job_log(JobLogRequest(job_id=job.id, level="INFO", message="Info 1"))
        logging_service.add_job_log(JobLogRequest(job_id=job.id, level="INFO", message="Info 2"))
        logging_service.add_job_log(JobLogRequest(job_id=job.id, level="ERROR", message="Error 1"))
        logging_service.add_job_log(
            JobLogRequest(job_id=job.id, level="WARNING", message="Warning")
        )

        test_session.commit()

        # Act
        counts = logging_service.count_logs_by_level()

        # Assert
        assert counts["INFO"] == 2
        assert counts["ERROR"] == 1
        assert counts["WARNING"] == 1

    @pytest.mark.database
    def test_count_logs_by_level_with_job_filter(self, test_session):
        """Test counting logs by level for specific job."""
        # Arrange
        job_service = JobService(test_session)
        logging_service = LoggingService(test_session)

        job1 = job_service.create_job(JobFactory.create_job_request(session=test_session))
        job2 = job_service.create_job(JobFactory.create_job_request(session=test_session))

        # Add logs to different jobs
        logging_service.add_job_log(
            JobLogRequest(job_id=job1.id, level="INFO", message="Job1 Info")
        )
        logging_service.add_job_log(
            JobLogRequest(job_id=job1.id, level="ERROR", message="Job1 Error")
        )
        logging_service.add_job_log(
            JobLogRequest(job_id=job2.id, level="INFO", message="Job2 Info")
        )

        test_session.commit()

        # Act
        counts = logging_service.count_logs_by_level(job_id=job1.id)

        # Assert
        assert counts["INFO"] == 1
        assert counts["ERROR"] == 1
        assert len(counts) == 2  # Only job1 levels

    @pytest.mark.database
    def test_count_logs_by_level_no_logs(self, test_session):
        """Test counting logs when no logs exist."""
        # Arrange
        logging_service = LoggingService(test_session)

        # Act
        counts = logging_service.count_logs_by_level()

        # Assert
        assert counts == {}


class TestLoggingServiceEdgeCases:
    """Test edge cases and special scenarios."""

    @pytest.mark.database
    def test_add_job_log_null_context_data(self, test_session):
        """Test adding log with None context_data."""
        # Arrange
        job_service = JobService(test_session)
        logging_service = LoggingService(test_session)

        job = job_service.create_job(JobFactory.create_job_request(session=test_session))
        test_session.commit()

        request = JobLogRequest(job_id=job.id, level="INFO", message="Test", context_data=None)

        # Act
        log_entry = logging_service.add_job_log(request)
        test_session.commit()

        # Assert
        assert log_entry.context_data is None

    @pytest.mark.database
    def test_add_job_log_empty_context_data(self, test_session):
        """Test adding log with empty context_data dict."""
        # Arrange
        job_service = JobService(test_session)
        logging_service = LoggingService(test_session)

        job = job_service.create_job(JobFactory.create_job_request(session=test_session))
        test_session.commit()

        request = JobLogRequest(job_id=job.id, level="INFO", message="Test", context_data={})

        # Act
        log_entry = logging_service.add_job_log(request)
        test_session.commit()

        # Assert
        assert log_entry.context_data == {}

    @pytest.mark.database
    def test_add_job_log_complex_context_data(self, test_session):
        """Test adding log with complex nested context_data."""
        # Arrange
        job_service = JobService(test_session)
        logging_service = LoggingService(test_session)

        job = job_service.create_job(JobFactory.create_job_request(session=test_session))
        test_session.commit()

        complex_context = {
            "nested": {"key1": "value1", "key2": 123},
            "list": [1, 2, 3],
            "mixed": {"list": [{"a": 1}]},
        }

        request = JobLogRequest(
            job_id=job.id, level="INFO", message="Test", context_data=complex_context
        )

        # Act
        log_entry = logging_service.add_job_log(request)
        test_session.commit()

        # Assert
        assert log_entry.context_data == complex_context

    @pytest.mark.database
    def test_add_job_log_very_long_message(self, test_session):
        """Test adding log with very long message."""
        # Arrange
        job_service = JobService(test_session)
        logging_service = LoggingService(test_session)

        job = job_service.create_job(JobFactory.create_job_request(session=test_session))
        test_session.commit()

        long_message = "A" * 10000  # Very long message

        request = JobLogRequest(job_id=job.id, level="INFO", message=long_message)

        # Act
        log_entry = logging_service.add_job_log(request)
        test_session.commit()

        # Assert
        assert log_entry.message == long_message
        assert len(log_entry.message) == 10000

    @pytest.mark.database
    def test_add_job_log_unicode_characters(self, test_session):
        """Test adding log with unicode characters."""
        # Arrange
        job_service = JobService(test_session)
        logging_service = LoggingService(test_session)

        job = job_service.create_job(JobFactory.create_job_request(session=test_session))
        test_session.commit()

        unicode_message = "Test 测试 🚀 Тест"

        request = JobLogRequest(job_id=job.id, level="INFO", message=unicode_message)

        # Act
        log_entry = logging_service.add_job_log(request)
        test_session.commit()

        # Assert
        assert log_entry.message == unicode_message
