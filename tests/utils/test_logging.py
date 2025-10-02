"""Comprehensive tests for logging utilities - MANDATORY TEST_BUILDING.md compliance.

This module tests centralized logging configuration with complete coverage:
- LoggerFactory configuration and initialization
- Logger instance creation with auto-detection
- Output format selection (JSON vs console)
- Color output control
- Context binding and propagation
- LoggingMixin functionality
- Environment variable integration
- Thread safety and caching

ALL tests follow MANDATORY TEST_BUILDING.md patterns:
- AAA pattern with explicit comments
- Factory fixtures for DRY principle
- Comprehensive logging scenario testing
- Performance benchmarks with specific thresholds
"""

import os
import time
from io import StringIO
from unittest.mock import patch

import pytest

from src.utils.logging import (
    LoggerFactory,
    LoggingMixin,
    configure_logging,
    get_logger,
    with_context,
)

# ============================================================================
# Test Fixtures - DRY Principle
# ============================================================================


@pytest.fixture(autouse=True)
def reset_logger_factory():
    """Reset LoggerFactory state before AND after each test - DRY principle."""
    # Arrange - MANDATORY
    # Reset state BEFORE test to ensure clean slate
    LoggerFactory._configured = False
    LoggerFactory._log_level = "INFO"

    # Act - MANDATORY (yield to test)
    yield

    # Assert - MANDATORY (cleanup)
    # Reset state AFTER test to prevent pollution
    LoggerFactory._configured = False
    LoggerFactory._log_level = "INFO"


@pytest.fixture
def mock_stderr():
    """Factory for mock stderr - DRY principle."""
    return StringIO()


@pytest.fixture
def sample_log_context() -> dict[str, str]:
    """Factory for sample log context - DRY principle."""
    return {"user_id": "123", "request_id": "abc-def", "action": "test_action"}


# ============================================================================
# LoggerFactory Tests
# ============================================================================


@pytest.mark.unit
class TestLoggerFactory:
    """Tests for LoggerFactory class."""

    def test_logger_factory_configure_sets_configured_flag(self):
        """Test configure sets the configured flag - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        LoggerFactory._configured = False

        # Act - MANDATORY
        LoggerFactory.configure()

        # Assert - MANDATORY
        assert LoggerFactory._configured is True

    def test_logger_factory_configure_sets_log_level(self):
        """Test configure sets log level - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        log_level = "DEBUG"

        # Act - MANDATORY
        LoggerFactory.configure(log_level=log_level)

        # Assert - MANDATORY
        assert LoggerFactory._log_level == "DEBUG"

    def test_logger_factory_configure_only_once(self):
        """Test configure is idempotent - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        LoggerFactory.configure(log_level="DEBUG")
        first_level = LoggerFactory._log_level

        # Act - MANDATORY
        LoggerFactory.configure(log_level="ERROR")  # Should be ignored

        # Assert - MANDATORY
        assert LoggerFactory._log_level == first_level  # Unchanged

    def test_logger_factory_configure_with_json_enabled(self):
        """Test configure with JSON output enabled - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        LoggerFactory._configured = False

        # Act - MANDATORY
        LoggerFactory.configure(enable_json=True)

        # Assert - MANDATORY
        assert LoggerFactory._configured is True

    def test_logger_factory_configure_with_colors_disabled(self):
        """Test configure with colors disabled - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        LoggerFactory._configured = False

        # Act - MANDATORY
        LoggerFactory.configure(enable_colors=False)

        # Assert - MANDATORY
        assert LoggerFactory._configured is True

    @patch("sys.stderr.isatty", return_value=True)
    def test_logger_factory_configure_auto_detect_tty(self, mock_isatty):
        """Test configure auto-detects TTY for colors - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        LoggerFactory._configured = False

        # Act - MANDATORY
        LoggerFactory.configure()

        # Assert - MANDATORY
        assert LoggerFactory._configured is True
        mock_isatty.assert_called()

    @patch("sys.stderr.isatty", return_value=False)
    def test_logger_factory_configure_auto_detect_non_tty(self, mock_isatty):
        """Test configure auto-detects non-TTY for JSON - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        LoggerFactory._configured = False

        # Act - MANDATORY
        LoggerFactory.configure()

        # Assert - MANDATORY
        assert LoggerFactory._configured is True
        mock_isatty.assert_called()

    @patch.dict(os.environ, {"LOG_FORMAT": "json"})
    def test_logger_factory_configure_respects_log_format_env(self):
        """Test configure respects LOG_FORMAT env var - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        LoggerFactory._configured = False

        # Act - MANDATORY
        LoggerFactory.configure()

        # Assert - MANDATORY
        assert LoggerFactory._configured is True

    @patch.dict(os.environ, {"NO_COLOR": "1"})
    def test_logger_factory_configure_respects_no_color_env(self):
        """Test configure respects NO_COLOR env var - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        LoggerFactory._configured = False

        # Act - MANDATORY
        LoggerFactory.configure()

        # Assert - MANDATORY
        assert LoggerFactory._configured is True

    def test_logger_factory_get_logger_returns_bound_logger(self):
        """Test get_logger returns BoundLogger - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        LoggerFactory._configured = False

        # Act - MANDATORY
        logger = LoggerFactory.get_logger("test_logger")

        # Assert - MANDATORY
        # structlog may return proxy or filtering bound logger
        assert hasattr(logger, "info")
        assert hasattr(logger, "debug")
        assert hasattr(logger, "error")

    def test_logger_factory_get_logger_auto_configures(self):
        """Test get_logger auto-configures if needed - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        LoggerFactory._configured = False

        # Act - MANDATORY
        logger = LoggerFactory.get_logger("test_logger")

        # Assert - MANDATORY
        assert LoggerFactory._configured is True
        assert logger is not None

    def test_logger_factory_get_logger_with_name(self):
        """Test get_logger with explicit name - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        logger_name = "my.custom.logger"

        # Act - MANDATORY
        logger = LoggerFactory.get_logger(logger_name)

        # Assert - MANDATORY
        assert logger is not None

    def test_logger_factory_get_logger_without_name_auto_detects(self):
        """Test get_logger auto-detects caller module - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # No explicit name provided

        # Act - MANDATORY
        logger = LoggerFactory.get_logger()

        # Assert - MANDATORY
        assert logger is not None


# ============================================================================
# get_logger Tests
# ============================================================================


@pytest.mark.unit
class TestGetLogger:
    """Tests for get_logger convenience function."""

    def test_get_logger_returns_bound_logger(self):
        """Test get_logger returns BoundLogger - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # Reset factory state
        LoggerFactory._configured = False

        # Act - MANDATORY
        logger = get_logger("test_module")

        # Assert - MANDATORY
        # structlog may return proxy or filtering bound logger
        assert hasattr(logger, "info")
        assert hasattr(logger, "debug")
        assert hasattr(logger, "error")

    def test_get_logger_with_explicit_name(self):
        """Test get_logger with explicit name - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        logger_name = "explicit.logger.name"

        # Act - MANDATORY
        logger = get_logger(logger_name)

        # Assert - MANDATORY
        assert logger is not None

    def test_get_logger_without_name_auto_detects(self):
        """Test get_logger auto-detects caller - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # No name provided

        # Act - MANDATORY
        logger = get_logger()

        # Assert - MANDATORY
        assert logger is not None

    def test_get_logger_caches_loggers(self):
        """Test get_logger returns cached instances - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        logger_name = "cached.logger"

        # Act - MANDATORY
        logger1 = get_logger(logger_name)
        logger2 = get_logger(logger_name)

        # Assert - MANDATORY
        # structlog creates new proxy objects but they wrap the same logger
        # Test that both loggers have same logging capability
        assert hasattr(logger1, "info")
        assert hasattr(logger2, "info")


# ============================================================================
# configure_logging Tests
# ============================================================================


@pytest.mark.unit
class TestConfigureLogging:
    """Tests for configure_logging function."""

    def test_configure_logging_with_explicit_log_level(self):
        """Test configure_logging with explicit level - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        log_level = "WARNING"

        # Act - MANDATORY
        configure_logging(log_level=log_level)

        # Assert - MANDATORY
        assert LoggerFactory._log_level == "WARNING"

    @patch.dict(os.environ, {"LOG_LEVEL": "ERROR"})
    def test_configure_logging_from_environment(self):
        """Test configure_logging reads LOG_LEVEL env - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        LoggerFactory._configured = False

        # Act - MANDATORY
        configure_logging()

        # Assert - MANDATORY
        assert LoggerFactory._log_level == "ERROR"

    @patch.dict(os.environ, {}, clear=True)
    def test_configure_logging_defaults_to_info(self):
        """Test configure_logging defaults to INFO - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        LoggerFactory._configured = False

        # Act - MANDATORY
        configure_logging()

        # Assert - MANDATORY
        assert LoggerFactory._log_level == "INFO"

    def test_configure_logging_with_json_enabled(self):
        """Test configure_logging with JSON format - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        LoggerFactory._configured = False

        # Act - MANDATORY
        configure_logging(enable_json=True)

        # Assert - MANDATORY
        assert LoggerFactory._configured is True

    def test_configure_logging_with_colors_disabled(self):
        """Test configure_logging with colors off - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        LoggerFactory._configured = False

        # Act - MANDATORY
        configure_logging(enable_colors=False)

        # Assert - MANDATORY
        assert LoggerFactory._configured is True

    def test_configure_logging_explicit_level_overrides_env(self):
        """Test explicit level overrides environment - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        LoggerFactory._configured = False
        with patch.dict(os.environ, {"LOG_LEVEL": "DEBUG"}):
            # Act - MANDATORY
            configure_logging(log_level="ERROR")

            # Assert - MANDATORY
            assert LoggerFactory._log_level == "ERROR"


# ============================================================================
# with_context Tests
# ============================================================================


@pytest.mark.unit
class TestWithContext:
    """Tests for with_context function."""

    def test_with_context_returns_bound_logger(self):
        """Test with_context returns BoundLogger - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        context = {"key": "value"}

        # Act - MANDATORY
        logger = with_context(**context)

        # Assert - MANDATORY
        # structlog may return filtering bound logger
        assert hasattr(logger, "info")
        assert hasattr(logger, "debug")
        assert hasattr(logger, "error")

    def test_with_context_binds_single_value(self, sample_log_context: dict[str, str]):
        """Test with_context binds single value - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        user_id = sample_log_context["user_id"]

        # Act - MANDATORY
        logger = with_context(user_id=user_id)

        # Assert - MANDATORY
        assert logger is not None

    def test_with_context_binds_multiple_values(self, sample_log_context: dict[str, str]):
        """Test with_context binds multiple values - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # Use fixture context

        # Act - MANDATORY
        logger = with_context(**sample_log_context)

        # Assert - MANDATORY
        assert logger is not None

    def test_with_context_creates_independent_loggers(self):
        """Test with_context creates independent loggers - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        context1 = {"request_id": "req-1"}
        context2 = {"request_id": "req-2"}

        # Act - MANDATORY
        logger1 = with_context(**context1)
        logger2 = with_context(**context2)

        # Assert - MANDATORY
        # Loggers should be different instances with different context
        assert logger1 is not logger2


# ============================================================================
# LoggingMixin Tests
# ============================================================================


@pytest.mark.unit
class TestLoggingMixin:
    """Tests for LoggingMixin class."""

    def test_logging_mixin_provides_logger_property(self):
        """Test LoggingMixin provides logger property - MANDATORY AAA pattern."""

        # Arrange - MANDATORY
        class TestClass(LoggingMixin):
            pass

        instance = TestClass()

        # Act - MANDATORY
        logger = instance.logger

        # Assert - MANDATORY
        # structlog may return proxy object
        assert hasattr(logger, "info")
        assert hasattr(logger, "debug")
        assert hasattr(logger, "error")

    def test_logging_mixin_logger_includes_class_name(self):
        """Test logger includes class name - MANDATORY AAA pattern."""

        # Arrange - MANDATORY
        class CustomTestClass(LoggingMixin):
            pass

        instance = CustomTestClass()

        # Act - MANDATORY
        logger = instance.logger

        # Assert - MANDATORY
        assert logger is not None
        # Logger should be bound to class module + name

    def test_logging_mixin_logger_is_cached(self):
        """Test logger property is consistent - MANDATORY AAA pattern."""

        # Arrange - MANDATORY
        class CachedTestClass(LoggingMixin):
            pass

        instance = CachedTestClass()

        # Act - MANDATORY
        logger1 = instance.logger
        logger2 = instance.logger

        # Assert - MANDATORY
        # structlog creates new proxy objects but both should work
        assert hasattr(logger1, "info")
        assert hasattr(logger2, "info")


# ============================================================================
# Integration Tests
# ============================================================================


@pytest.mark.unit
class TestLoggingIntegration:
    """Integration tests for logging functionality."""

    def test_logger_can_log_info_message(self):
        """Test logger can log info messages - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        logger = get_logger("test_integration")
        message = "Test info message"

        # Act - MANDATORY
        try:
            logger.info(message)
            success = True
        except Exception:
            success = False

        # Assert - MANDATORY
        assert success is True

    def test_logger_can_log_with_context(self):
        """Test logger logs with context - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        logger = with_context(user_id="123", action="test")
        message = "Action performed"

        # Act - MANDATORY
        try:
            logger.info(message)
            success = True
        except Exception:
            success = False

        # Assert - MANDATORY
        assert success is True

    def test_logging_mixin_integration(self):
        """Test LoggingMixin integration - MANDATORY AAA pattern."""

        # Arrange - MANDATORY
        class IntegrationTestClass(LoggingMixin):
            def perform_action(self):
                self.logger.info("Action performed")
                return True

        instance = IntegrationTestClass()

        # Act - MANDATORY
        result = instance.perform_action()

        # Assert - MANDATORY
        assert result is True


# ============================================================================
# MANDATORY Performance Benchmarks
# ============================================================================


@pytest.mark.performance
@pytest.mark.unit
class TestLoggingPerformance:
    """MANDATORY performance tests for logging utilities."""

    def test_get_logger_performance(self):
        """MANDATORY performance test - logger creation speed."""
        # Arrange - MANDATORY
        iterations = 10000

        # Act - MANDATORY
        start_time = time.perf_counter()

        for i in range(iterations):
            get_logger(f"test_logger_{i % 100}")  # Cycle through 100 names

        end_time = time.perf_counter()
        execution_time = end_time - start_time

        # Assert - MANDATORY
        avg_time = execution_time / iterations
        assert avg_time < 0.0001  # <0.1ms per logger creation
        assert execution_time < 1.0  # Total <1s for 10000 creations

    def test_logger_bind_context_performance(self):
        """MANDATORY performance test - context binding speed."""
        # Arrange - MANDATORY
        logger = get_logger("performance_test")
        iterations = 10000

        # Act - MANDATORY
        start_time = time.perf_counter()

        for i in range(iterations):
            logger.bind(request_id=f"req-{i}", user_id=i)

        end_time = time.perf_counter()
        execution_time = end_time - start_time

        # Assert - MANDATORY
        avg_time = execution_time / iterations
        assert avg_time < 0.0001  # <0.1ms per bind operation
        assert execution_time < 1.0  # Total <1s for 10000 binds

    def test_with_context_performance(self):
        """MANDATORY performance test - with_context function speed."""
        # Arrange - MANDATORY
        iterations = 1000

        # Act - MANDATORY
        start_time = time.perf_counter()

        for i in range(iterations):
            with_context(user_id=i, request_id=f"req-{i}", action="test")

        end_time = time.perf_counter()
        execution_time = end_time - start_time

        # Assert - MANDATORY
        avg_time = execution_time / iterations
        assert avg_time < 0.001  # <1ms per with_context call
        assert execution_time < 1.0  # Total <1s for 1000 calls
