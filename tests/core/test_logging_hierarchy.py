"""Comprehensive tests for src/core/logging_hierarchy.py.

Test coverage: 192 statements, 71% → 85%+
Following TEST_BUILDING.md MANDATORY standards with ZERO TOLERANCE.
"""

from unittest.mock import MagicMock, Mock

import pytest

from src.core.logging_hierarchy import (
    APILoggingMixin,
    AuthLoggingMixin,
    CacheLoggingMixin,
    DatabaseLoggingMixin,
    JobLoggingMixin,
    LoggerHierarchy,
    LogLevel,
    MonitoringLoggingMixin,
    ScrapingLoggingMixin,
    ServiceLogger,
    ServiceLoggingMixin,
    ServiceType,
    get_api_logger,
    get_auth_logger,
    get_cache_logger,
    get_core_logger,
    get_database_logger,
    get_general_logger,
    get_job_logger,
    get_monitoring_logger,
    get_scraping_logger,
)

# =============================================================================
# FIXTURES - Factory Pattern for DRY Principle
# =============================================================================


@pytest.fixture
def reset_logger_hierarchy():
    """Reset LoggerHierarchy state between tests - DRY principle."""
    LoggerHierarchy._loggers = {}
    LoggerHierarchy._configured = False
    yield
    LoggerHierarchy._loggers = {}
    LoggerHierarchy._configured = False


@pytest.fixture
def mock_logger(mocker):
    """Factory for mock logger - DRY principle."""
    mock = MagicMock()
    mocker.patch("src.utils.logging.get_logger", return_value=mock)
    mocker.patch("src.utils.logging.configure_logging")
    return mock


# =============================================================================
# TEST LogLevel Enum
# =============================================================================


@pytest.mark.unit
class TestLogLevel:
    """Test LogLevel enum."""

    def test_log_level_values(self):
        """Test LogLevel has correct numeric values."""
        # Assert
        assert LogLevel.DEBUG.value == 10
        assert LogLevel.INFO.value == 20
        assert LogLevel.WARNING.value == 30
        assert LogLevel.ERROR.value == 40
        assert LogLevel.CRITICAL.value == 50

    def test_log_level_ordering(self):
        """Test LogLevel ordering."""
        # Assert
        assert LogLevel.DEBUG.value < LogLevel.INFO.value
        assert LogLevel.INFO.value < LogLevel.WARNING.value
        assert LogLevel.WARNING.value < LogLevel.ERROR.value
        assert LogLevel.ERROR.value < LogLevel.CRITICAL.value


# =============================================================================
# TEST ServiceType Enum
# =============================================================================


@pytest.mark.unit
class TestServiceType:
    """Test ServiceType enum."""

    def test_service_type_values(self):
        """Test ServiceType has correct string values."""
        # Assert
        assert ServiceType.DATABASE.value == "database"
        assert ServiceType.AUTH.value == "auth"
        assert ServiceType.CACHE.value == "cache"
        assert ServiceType.MONITORING.value == "monitoring"
        assert ServiceType.API.value == "api"
        assert ServiceType.JOB.value == "job"
        assert ServiceType.SCRAPING.value == "scraping"
        assert ServiceType.GENERAL.value == "general"


# =============================================================================
# TEST ServiceLogger - Core Logging Class
# =============================================================================


@pytest.mark.unit
class TestServiceLogger:
    """Test ServiceLogger functionality."""

    def test_service_logger_init(self, mock_logger):
        """Test ServiceLogger initialization."""
        # Arrange & Act
        logger = ServiceLogger("test.module", ServiceType.DATABASE)

        # Assert
        assert logger.name == "test.module"
        assert logger.service_type == ServiceType.DATABASE
        assert logger._logger is not None

    def test_service_logger_creates_with_context(self, mock_logger):
        """Test ServiceLogger creates logger with service context."""
        # Arrange & Act
        logger = ServiceLogger("test.module", ServiceType.AUTH)

        # Assert
        mock_logger.bind.assert_called_once()
        call_kwargs = mock_logger.bind.call_args.kwargs
        assert call_kwargs["component"] == "auth"
        assert call_kwargs["layer"] == "security"
        assert call_kwargs["sensitive"] is True
        assert call_kwargs["service_type"] == "auth"
        assert call_kwargs["logger_name"] == "test.module"

    def test_service_logger_get_default_level_database(self, mock_logger):
        """Test get_default_level for database service."""
        # Arrange
        logger = ServiceLogger("test.module", ServiceType.DATABASE)

        # Act
        level = logger.get_default_level()

        # Assert
        assert level == LogLevel.INFO

    def test_service_logger_get_default_level_auth(self, mock_logger):
        """Test get_default_level for auth service (WARNING)."""
        # Arrange
        logger = ServiceLogger("test.module", ServiceType.AUTH)

        # Act
        level = logger.get_default_level()

        # Assert
        assert level == LogLevel.WARNING

    def test_service_logger_get_default_level_monitoring(self, mock_logger):
        """Test get_default_level for monitoring service (DEBUG)."""
        # Arrange
        logger = ServiceLogger("test.module", ServiceType.MONITORING)

        # Act
        level = logger.get_default_level()

        # Assert
        assert level == LogLevel.DEBUG

    def test_service_logger_debug(self, mock_logger):
        """Test debug logging method."""
        # Arrange
        logger = ServiceLogger("test.module", ServiceType.GENERAL)
        bound_logger = mock_logger.bind.return_value

        # Act
        logger.debug("Test debug message", key="value")

        # Assert
        bound_logger.debug.assert_called_once_with("Test debug message", key="value")

    def test_service_logger_info(self, mock_logger):
        """Test info logging method."""
        # Arrange
        logger = ServiceLogger("test.module", ServiceType.GENERAL)
        bound_logger = mock_logger.bind.return_value

        # Act
        logger.info("Test info message", key="value")

        # Assert
        bound_logger.info.assert_called_once_with("Test info message", key="value")

    def test_service_logger_warning(self, mock_logger):
        """Test warning logging method."""
        # Arrange
        logger = ServiceLogger("test.module", ServiceType.GENERAL)
        bound_logger = mock_logger.bind.return_value

        # Act
        logger.warning("Test warning message", key="value")

        # Assert
        bound_logger.warning.assert_called_once_with("Test warning message", key="value")

    def test_service_logger_error(self, mock_logger):
        """Test error logging method."""
        # Arrange
        logger = ServiceLogger("test.module", ServiceType.GENERAL)
        bound_logger = mock_logger.bind.return_value

        # Act
        logger.error("Test error message", key="value")

        # Assert
        bound_logger.error.assert_called_once_with("Test error message", key="value")

    def test_service_logger_critical(self, mock_logger):
        """Test critical logging method."""
        # Arrange
        logger = ServiceLogger("test.module", ServiceType.GENERAL)
        bound_logger = mock_logger.bind.return_value

        # Act
        logger.critical("Test critical message", key="value")

        # Assert
        bound_logger.critical.assert_called_once_with("Test critical message", key="value")

    def test_service_logger_bind(self, mock_logger):
        """Test bind method."""
        # Arrange
        logger = ServiceLogger("test.module", ServiceType.GENERAL)
        bound_logger = mock_logger.bind.return_value

        # Act
        result = logger.bind(request_id="123")

        # Assert
        bound_logger.bind.assert_called_once_with(request_id="123")

    def test_service_logger_exception(self, mock_logger):
        """Test exception logging method."""
        # Arrange
        logger = ServiceLogger("test.module", ServiceType.GENERAL)
        bound_logger = mock_logger.bind.return_value

        # Act
        logger.exception("Test exception message", key="value")

        # Assert
        bound_logger.exception.assert_called_once_with("Test exception message", key="value")

    def test_service_logger_with_context(self, mock_logger):
        """Test with_context method."""
        # Arrange
        logger = ServiceLogger("test.module", ServiceType.GENERAL)
        bound_logger = mock_logger.bind.return_value

        # Act
        result = logger.with_context(user_id="user-123")

        # Assert
        bound_logger.bind.assert_called_once_with(user_id="user-123")


# =============================================================================
# TEST LoggerHierarchy - Central Registry
# =============================================================================


@pytest.mark.unit
class TestLoggerHierarchy:
    """Test LoggerHierarchy functionality."""

    def test_logger_hierarchy_configure(self, reset_logger_hierarchy, mocker):
        """Test LoggerHierarchy configuration."""
        # Arrange
        mock_configure = mocker.patch("src.utils.logging.configure_logging")

        # Act
        LoggerHierarchy.configure(LogLevel.DEBUG)

        # Assert
        mock_configure.assert_called_once_with("DEBUG")
        assert LoggerHierarchy._configured is True

    def test_logger_hierarchy_configure_idempotent(self, reset_logger_hierarchy, mocker):
        """Test configure is idempotent (doesn't reconfigure)."""
        # Arrange
        mock_configure = mocker.patch("src.utils.logging.configure_logging")
        LoggerHierarchy.configure()

        # Act - configure again
        LoggerHierarchy.configure()

        # Assert - only called once
        assert mock_configure.call_count == 1

    def test_logger_hierarchy_get_service_logger_creates_new(
        self, reset_logger_hierarchy, mock_logger
    ):
        """Test get_service_logger creates new logger."""
        # Act
        logger = LoggerHierarchy.get_service_logger("test.module", ServiceType.DATABASE)

        # Assert
        assert isinstance(logger, ServiceLogger)
        assert logger.name == "test.module"
        assert logger.service_type == ServiceType.DATABASE
        assert "database:test.module" in LoggerHierarchy._loggers

    def test_logger_hierarchy_get_service_logger_returns_cached(
        self, reset_logger_hierarchy, mock_logger
    ):
        """Test get_service_logger returns cached logger."""
        # Arrange
        logger1 = LoggerHierarchy.get_service_logger("test.module", ServiceType.DATABASE)

        # Act
        logger2 = LoggerHierarchy.get_service_logger("test.module", ServiceType.DATABASE)

        # Assert
        assert logger1 is logger2

    def test_logger_hierarchy_get_database_logger(self, reset_logger_hierarchy, mock_logger):
        """Test get_database_logger convenience method."""
        # Act
        logger = LoggerHierarchy.get_database_logger("test.module")

        # Assert
        assert logger.service_type == ServiceType.DATABASE

    def test_logger_hierarchy_get_auth_logger(self, reset_logger_hierarchy, mock_logger):
        """Test get_auth_logger convenience method."""
        # Act
        logger = LoggerHierarchy.get_auth_logger("test.module")

        # Assert
        assert logger.service_type == ServiceType.AUTH

    def test_logger_hierarchy_get_cache_logger(self, reset_logger_hierarchy, mock_logger):
        """Test get_cache_logger convenience method."""
        # Act
        logger = LoggerHierarchy.get_cache_logger("test.module")

        # Assert
        assert logger.service_type == ServiceType.CACHE

    def test_logger_hierarchy_get_monitoring_logger(self, reset_logger_hierarchy, mock_logger):
        """Test get_monitoring_logger convenience method."""
        # Act
        logger = LoggerHierarchy.get_monitoring_logger("test.module")

        # Assert
        assert logger.service_type == ServiceType.MONITORING

    def test_logger_hierarchy_get_api_logger(self, reset_logger_hierarchy, mock_logger):
        """Test get_api_logger convenience method."""
        # Act
        logger = LoggerHierarchy.get_api_logger("test.module")

        # Assert
        assert logger.service_type == ServiceType.API

    def test_logger_hierarchy_get_job_logger(self, reset_logger_hierarchy, mock_logger):
        """Test get_job_logger convenience method."""
        # Act
        logger = LoggerHierarchy.get_job_logger("test.module")

        # Assert
        assert logger.service_type == ServiceType.JOB

    def test_logger_hierarchy_get_scraping_logger(self, reset_logger_hierarchy, mock_logger):
        """Test get_scraping_logger convenience method."""
        # Act
        logger = LoggerHierarchy.get_scraping_logger("test.module")

        # Assert
        assert logger.service_type == ServiceType.SCRAPING

    def test_logger_hierarchy_get_general_logger(self, reset_logger_hierarchy, mock_logger):
        """Test get_general_logger convenience method."""
        # Act
        logger = LoggerHierarchy.get_general_logger("test.module")

        # Assert
        assert logger.service_type == ServiceType.GENERAL


# =============================================================================
# TEST Convenience Functions
# =============================================================================


@pytest.mark.unit
class TestConvenienceFunctions:
    """Test module-level convenience functions."""

    def test_get_database_logger_with_name(self, reset_logger_hierarchy, mock_logger):
        """Test get_database_logger with explicit name."""
        # Act
        logger = get_database_logger("test.module")

        # Assert
        assert isinstance(logger, ServiceLogger)
        assert logger.service_type == ServiceType.DATABASE
        assert logger.name == "test.module"

    def test_get_database_logger_auto_detect(self, reset_logger_hierarchy, mock_logger):
        """Test get_database_logger with name auto-detection."""
        # Act
        logger = get_database_logger()

        # Assert
        assert isinstance(logger, ServiceLogger)
        assert logger.service_type == ServiceType.DATABASE

    def test_get_auth_logger_with_name(self, reset_logger_hierarchy, mock_logger):
        """Test get_auth_logger with explicit name."""
        # Act
        logger = get_auth_logger("test.module")

        # Assert
        assert logger.service_type == ServiceType.AUTH

    def test_get_cache_logger_with_name(self, reset_logger_hierarchy, mock_logger):
        """Test get_cache_logger with explicit name."""
        # Act
        logger = get_cache_logger("test.module")

        # Assert
        assert logger.service_type == ServiceType.CACHE

    def test_get_monitoring_logger_with_name(self, reset_logger_hierarchy, mock_logger):
        """Test get_monitoring_logger with explicit name."""
        # Act
        logger = get_monitoring_logger("test.module")

        # Assert
        assert logger.service_type == ServiceType.MONITORING

    def test_get_api_logger_with_name(self, reset_logger_hierarchy, mock_logger):
        """Test get_api_logger with explicit name."""
        # Act
        logger = get_api_logger("test.module")

        # Assert
        assert logger.service_type == ServiceType.API

    def test_get_job_logger_with_name(self, reset_logger_hierarchy, mock_logger):
        """Test get_job_logger with explicit name."""
        # Act
        logger = get_job_logger("test.module")

        # Assert
        assert logger.service_type == ServiceType.JOB

    def test_get_scraping_logger_with_name(self, reset_logger_hierarchy, mock_logger):
        """Test get_scraping_logger with explicit name."""
        # Act
        logger = get_scraping_logger("test.module")

        # Assert
        assert logger.service_type == ServiceType.SCRAPING

    def test_get_general_logger_with_name(self, reset_logger_hierarchy, mock_logger):
        """Test get_general_logger with explicit name."""
        # Act
        logger = get_general_logger("test.module")

        # Assert
        assert logger.service_type == ServiceType.GENERAL

    def test_get_core_logger_with_name(self, reset_logger_hierarchy, mock_logger):
        """Test get_core_logger with explicit name."""
        # Act
        logger = get_core_logger("test.module")

        # Assert
        assert logger.service_type == ServiceType.GENERAL

    def test_get_database_logger_no_frame(self, reset_logger_hierarchy, mock_logger, mocker):
        """Test get_database_logger when currentframe returns None."""
        # Arrange
        mocker.patch("inspect.currentframe", return_value=None)

        # Act
        logger = get_database_logger()

        # Assert
        assert logger.name == "unknown"

    def test_get_auth_logger_no_back_frame(self, reset_logger_hierarchy, mock_logger, mocker):
        """Test get_auth_logger when f_back is None."""
        # Arrange
        mock_frame = Mock()
        mock_frame.f_back = None
        mocker.patch("inspect.currentframe", return_value=mock_frame)

        # Act
        logger = get_auth_logger()

        # Assert
        assert logger.name == "unknown"

    def test_get_cache_logger_no_frame(self, reset_logger_hierarchy, mock_logger, mocker):
        """Test get_cache_logger when currentframe returns None."""
        # Arrange
        mocker.patch("inspect.currentframe", return_value=None)

        # Act
        logger = get_cache_logger()

        # Assert
        assert logger.name == "unknown"

    def test_get_monitoring_logger_no_frame(self, reset_logger_hierarchy, mock_logger, mocker):
        """Test get_monitoring_logger when currentframe returns None."""
        # Arrange
        mocker.patch("inspect.currentframe", return_value=None)

        # Act
        logger = get_monitoring_logger()

        # Assert
        assert logger.name == "unknown"

    def test_get_api_logger_no_frame(self, reset_logger_hierarchy, mock_logger, mocker):
        """Test get_api_logger when currentframe returns None."""
        # Arrange
        mocker.patch("inspect.currentframe", return_value=None)

        # Act
        logger = get_api_logger()

        # Assert
        assert logger.name == "unknown"

    def test_get_job_logger_no_frame(self, reset_logger_hierarchy, mock_logger, mocker):
        """Test get_job_logger when currentframe returns None."""
        # Arrange
        mocker.patch("inspect.currentframe", return_value=None)

        # Act
        logger = get_job_logger()

        # Assert
        assert logger.name == "unknown"

    def test_get_scraping_logger_no_frame(self, reset_logger_hierarchy, mock_logger, mocker):
        """Test get_scraping_logger when currentframe returns None."""
        # Arrange
        mocker.patch("inspect.currentframe", return_value=None)

        # Act
        logger = get_scraping_logger()

        # Assert
        assert logger.name == "unknown"

    def test_get_general_logger_no_frame(self, reset_logger_hierarchy, mock_logger, mocker):
        """Test get_general_logger when currentframe returns None."""
        # Arrange
        mocker.patch("inspect.currentframe", return_value=None)

        # Act
        logger = get_general_logger()

        # Assert
        assert logger.name == "unknown"

    def test_get_core_logger_no_frame(self, reset_logger_hierarchy, mock_logger, mocker):
        """Test get_core_logger when currentframe returns None."""
        # Arrange
        mocker.patch("inspect.currentframe", return_value=None)

        # Act
        logger = get_core_logger()

        # Assert
        assert logger.name == "unknown"

    def test_get_auth_logger_no_name_in_globals(self, reset_logger_hierarchy, mock_logger, mocker):
        """Test get_auth_logger when __name__ not in f_globals."""
        # Arrange
        mock_frame = Mock()
        mock_frame.f_back = Mock()
        mock_frame.f_back.f_globals = {}  # No __name__ key
        mocker.patch("inspect.currentframe", return_value=mock_frame)

        # Act
        logger = get_auth_logger()

        # Assert
        assert logger.name == "unknown"

    def test_get_cache_logger_no_name_in_globals(self, reset_logger_hierarchy, mock_logger, mocker):
        """Test get_cache_logger when __name__ not in f_globals."""
        # Arrange
        mock_frame = Mock()
        mock_frame.f_back = Mock()
        mock_frame.f_back.f_globals = {}
        mocker.patch("inspect.currentframe", return_value=mock_frame)

        # Act
        logger = get_cache_logger()

        # Assert
        assert logger.name == "unknown"

    def test_get_monitoring_logger_no_name_in_globals(
        self, reset_logger_hierarchy, mock_logger, mocker
    ):
        """Test get_monitoring_logger when __name__ not in f_globals."""
        # Arrange
        mock_frame = Mock()
        mock_frame.f_back = Mock()
        mock_frame.f_back.f_globals = {}
        mocker.patch("inspect.currentframe", return_value=mock_frame)

        # Act
        logger = get_monitoring_logger()

        # Assert
        assert logger.name == "unknown"

    def test_get_api_logger_no_name_in_globals(self, reset_logger_hierarchy, mock_logger, mocker):
        """Test get_api_logger when __name__ not in f_globals."""
        # Arrange
        mock_frame = Mock()
        mock_frame.f_back = Mock()
        mock_frame.f_back.f_globals = {}
        mocker.patch("inspect.currentframe", return_value=mock_frame)

        # Act
        logger = get_api_logger()

        # Assert
        assert logger.name == "unknown"

    def test_get_job_logger_no_name_in_globals(self, reset_logger_hierarchy, mock_logger, mocker):
        """Test get_job_logger when __name__ not in f_globals."""
        # Arrange
        mock_frame = Mock()
        mock_frame.f_back = Mock()
        mock_frame.f_back.f_globals = {}
        mocker.patch("inspect.currentframe", return_value=mock_frame)

        # Act
        logger = get_job_logger()

        # Assert
        assert logger.name == "unknown"

    def test_get_scraping_logger_no_name_in_globals(
        self, reset_logger_hierarchy, mock_logger, mocker
    ):
        """Test get_scraping_logger when __name__ not in f_globals."""
        # Arrange
        mock_frame = Mock()
        mock_frame.f_back = Mock()
        mock_frame.f_back.f_globals = {}
        mocker.patch("inspect.currentframe", return_value=mock_frame)

        # Act
        logger = get_scraping_logger()

        # Assert
        assert logger.name == "unknown"

    def test_get_general_logger_no_name_in_globals(
        self, reset_logger_hierarchy, mock_logger, mocker
    ):
        """Test get_general_logger when __name__ not in f_globals."""
        # Arrange
        mock_frame = Mock()
        mock_frame.f_back = Mock()
        mock_frame.f_back.f_globals = {}
        mocker.patch("inspect.currentframe", return_value=mock_frame)

        # Act
        logger = get_general_logger()

        # Assert
        assert logger.name == "unknown"

    def test_get_core_logger_no_name_in_globals(self, reset_logger_hierarchy, mock_logger, mocker):
        """Test get_core_logger when __name__ not in f_globals."""
        # Arrange
        mock_frame = Mock()
        mock_frame.f_back = Mock()
        mock_frame.f_back.f_globals = {}
        mocker.patch("inspect.currentframe", return_value=mock_frame)

        # Act
        logger = get_core_logger()

        # Assert
        assert logger.name == "unknown"


# =============================================================================
# TEST ServiceLoggingMixin - Base Mixin
# =============================================================================


@pytest.mark.unit
class TestServiceLoggingMixin:
    """Test ServiceLoggingMixin functionality."""

    def test_service_logging_mixin_logger_property(self, reset_logger_hierarchy, mock_logger):
        """Test ServiceLoggingMixin logger property."""

        # Arrange
        class TestClass(ServiceLoggingMixin):
            pass

        instance = TestClass()

        # Act
        logger = instance.logger

        # Assert
        assert isinstance(logger, ServiceLogger)
        assert logger.service_type == ServiceType.GENERAL

    def test_service_logging_mixin_log_with_context(self, reset_logger_hierarchy, mock_logger):
        """Test ServiceLoggingMixin log_with_context method."""

        # Arrange
        class TestClass(ServiceLoggingMixin):
            pass

        instance = TestClass()
        bound_logger = mock_logger.bind.return_value

        # Act
        result = instance.log_with_context(request_id="123")

        # Assert
        bound_logger.bind.assert_called_once()
        call_kwargs = bound_logger.bind.call_args.kwargs
        assert "class_name" in call_kwargs
        assert call_kwargs["request_id"] == "123"


# =============================================================================
# TEST Specialized Mixins
# =============================================================================


@pytest.mark.unit
class TestDatabaseLoggingMixin:
    """Test DatabaseLoggingMixin."""

    def test_database_logging_mixin_service_type(self, reset_logger_hierarchy, mock_logger):
        """Test DatabaseLoggingMixin has correct service type."""

        # Arrange
        class TestClass(DatabaseLoggingMixin):
            pass

        instance = TestClass()

        # Act
        logger = instance.logger

        # Assert
        assert logger.service_type == ServiceType.DATABASE


@pytest.mark.unit
class TestAuthLoggingMixin:
    """Test AuthLoggingMixin."""

    def test_auth_logging_mixin_service_type(self, reset_logger_hierarchy, mock_logger):
        """Test AuthLoggingMixin has correct service type."""

        # Arrange
        class TestClass(AuthLoggingMixin):
            pass

        instance = TestClass()

        # Act
        logger = instance.logger

        # Assert
        assert logger.service_type == ServiceType.AUTH


@pytest.mark.unit
class TestCacheLoggingMixin:
    """Test CacheLoggingMixin."""

    def test_cache_logging_mixin_service_type(self, reset_logger_hierarchy, mock_logger):
        """Test CacheLoggingMixin has correct service type."""

        # Arrange
        class TestClass(CacheLoggingMixin):
            pass

        instance = TestClass()

        # Act
        logger = instance.logger

        # Assert
        assert logger.service_type == ServiceType.CACHE


@pytest.mark.unit
class TestMonitoringLoggingMixin:
    """Test MonitoringLoggingMixin."""

    def test_monitoring_logging_mixin_service_type(self, reset_logger_hierarchy, mock_logger):
        """Test MonitoringLoggingMixin has correct service type."""

        # Arrange
        class TestClass(MonitoringLoggingMixin):
            pass

        instance = TestClass()

        # Act
        logger = instance.logger

        # Assert
        assert logger.service_type == ServiceType.MONITORING


@pytest.mark.unit
class TestAPILoggingMixin:
    """Test APILoggingMixin."""

    def test_api_logging_mixin_service_type(self, reset_logger_hierarchy, mock_logger):
        """Test APILoggingMixin has correct service type."""

        # Arrange
        class TestClass(APILoggingMixin):
            pass

        instance = TestClass()

        # Act
        logger = instance.logger

        # Assert
        assert logger.service_type == ServiceType.API


@pytest.mark.unit
class TestJobLoggingMixin:
    """Test JobLoggingMixin."""

    def test_job_logging_mixin_service_type(self, reset_logger_hierarchy, mock_logger):
        """Test JobLoggingMixin has correct service type."""

        # Arrange
        class TestClass(JobLoggingMixin):
            pass

        instance = TestClass()

        # Act
        logger = instance.logger

        # Assert
        assert logger.service_type == ServiceType.JOB


@pytest.mark.unit
class TestScrapingLoggingMixin:
    """Test ScrapingLoggingMixin."""

    def test_scraping_logging_mixin_service_type(self, reset_logger_hierarchy, mock_logger):
        """Test ScrapingLoggingMixin has correct service type."""

        # Arrange
        class TestClass(ScrapingLoggingMixin):
            pass

        instance = TestClass()

        # Act
        logger = instance.logger

        # Assert
        assert logger.service_type == ServiceType.SCRAPING
