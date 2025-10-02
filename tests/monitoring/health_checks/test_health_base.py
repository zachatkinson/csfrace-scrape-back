"""Comprehensive tests for base health check components - MANDATORY TEST_BUILDING.md compliance.

This module tests base health check functionality with complete coverage:
- HealthStatus enum values
- HealthCheckResult creation and validation
- HealthCheckResult dictionary conversion
- HealthCheck base class initialization
- HealthCheck execute() with timeout and error handling
- FunctionHealthCheck with different function types
- Edge cases and error handling
- Performance benchmarks

ALL tests follow MANDATORY TEST_BUILDING.md patterns:
- AAA pattern with explicit comments
- Factory fixtures for DRY principle
- Comprehensive health check scenario testing
- Performance benchmarks with specific thresholds
"""

import time
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import asyncio
import pytest

from src.monitoring.health_checks.base import (
    FunctionHealthCheck,
    HealthCheck,
    HealthCheckResult,
    HealthStatus,
)

# ============================================================================
# Test Fixtures - DRY Principle
# ============================================================================


@pytest.fixture
def sample_health_result() -> HealthCheckResult:
    """Factory for sample health check result - DRY principle."""
    return HealthCheckResult(
        name="test_check",
        status=HealthStatus.HEALTHY,
        message="Test successful",
        duration_ms=10.5,
        details={"key": "value"},
        tags=["test", "sample"],
    )


@pytest.fixture
def mock_check_function():
    """Factory for mock check function - DRY principle."""
    return MagicMock(return_value=True)


@pytest.fixture
def mock_async_check_function():
    """Factory for mock async check function - DRY principle."""
    return AsyncMock(return_value=True)


# ============================================================================
# HealthStatus Tests
# ============================================================================


@pytest.mark.unit
class TestHealthStatus:
    """Tests for HealthStatus enum."""

    def test_health_status_healthy_value(self):
        """Test HealthStatus.HEALTHY has correct value - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        expected_value = "healthy"

        # Act - MANDATORY
        actual_value = HealthStatus.HEALTHY.value

        # Assert - MANDATORY
        assert actual_value == expected_value

    def test_health_status_degraded_value(self):
        """Test HealthStatus.DEGRADED has correct value - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        expected_value = "degraded"

        # Act - MANDATORY
        actual_value = HealthStatus.DEGRADED.value

        # Assert - MANDATORY
        assert actual_value == expected_value

    def test_health_status_unhealthy_value(self):
        """Test HealthStatus.UNHEALTHY has correct value - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        expected_value = "unhealthy"

        # Act - MANDATORY
        actual_value = HealthStatus.UNHEALTHY.value

        # Assert - MANDATORY
        assert actual_value == expected_value

    def test_health_status_unknown_value(self):
        """Test HealthStatus.UNKNOWN has correct value - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        expected_value = "unknown"

        # Act - MANDATORY
        actual_value = HealthStatus.UNKNOWN.value

        # Assert - MANDATORY
        assert actual_value == expected_value


# ============================================================================
# HealthCheckResult Tests
# ============================================================================


@pytest.mark.unit
class TestHealthCheckResult:
    """Tests for HealthCheckResult dataclass."""

    def test_health_check_result_creation(self):
        """Test HealthCheckResult creation with required fields - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        name = "test_check"
        status = HealthStatus.HEALTHY
        message = "All good"
        duration_ms = 15.5

        # Act - MANDATORY
        result = HealthCheckResult(
            name=name, status=status, message=message, duration_ms=duration_ms
        )

        # Assert - MANDATORY
        assert result.name == name
        assert result.status == status
        assert result.message == message
        assert result.duration_ms == duration_ms
        assert isinstance(result.timestamp, datetime)
        assert result.details == {}
        assert result.tags == []

    def test_health_check_result_with_optional_fields(self):
        """Test HealthCheckResult with all optional fields - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        name = "test_check"
        status = HealthStatus.HEALTHY
        message = "Test message"
        duration_ms = 10.0
        details = {"key1": "value1", "key2": "value2"}
        tags = ["tag1", "tag2"]
        timestamp = datetime.now(UTC)

        # Act - MANDATORY
        result = HealthCheckResult(
            name=name,
            status=status,
            message=message,
            duration_ms=duration_ms,
            details=details,
            tags=tags,
            timestamp=timestamp,
        )

        # Assert - MANDATORY
        assert result.name == name
        assert result.status == status
        assert result.message == message
        assert result.duration_ms == duration_ms
        assert result.details == details
        assert result.tags == tags
        assert result.timestamp == timestamp

    def test_is_healthy_returns_true_for_healthy_status(self):
        """Test is_healthy() returns True for HEALTHY status - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        result = HealthCheckResult(
            name="test", status=HealthStatus.HEALTHY, message="OK", duration_ms=10.0
        )

        # Act - MANDATORY
        is_healthy = result.is_healthy()

        # Assert - MANDATORY
        assert is_healthy is True

    def test_is_healthy_returns_false_for_unhealthy_status(self):
        """Test is_healthy() returns False for UNHEALTHY status - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        result = HealthCheckResult(
            name="test", status=HealthStatus.UNHEALTHY, message="Failed", duration_ms=10.0
        )

        # Act - MANDATORY
        is_healthy = result.is_healthy()

        # Assert - MANDATORY
        assert is_healthy is False

    def test_is_healthy_returns_false_for_degraded_status(self):
        """Test is_healthy() returns False for DEGRADED status - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        result = HealthCheckResult(
            name="test", status=HealthStatus.DEGRADED, message="Slow", duration_ms=10.0
        )

        # Act - MANDATORY
        is_healthy = result.is_healthy()

        # Assert - MANDATORY
        assert is_healthy is False

    def test_to_dict_conversion(self, sample_health_result):
        """Test to_dict() converts result to dictionary - MANDATORY AAA pattern."""
        # Arrange - MANDATORY (using fixture)

        # Act - MANDATORY
        result_dict = sample_health_result.to_dict()

        # Assert - MANDATORY
        assert isinstance(result_dict, dict)
        assert result_dict["name"] == "test_check"
        assert result_dict["status"] == "healthy"
        assert result_dict["message"] == "Test successful"
        assert result_dict["duration_ms"] == 10.5
        assert result_dict["details"] == {"key": "value"}
        assert result_dict["tags"] == ["test", "sample"]
        assert "timestamp" in result_dict
        assert isinstance(result_dict["timestamp"], str)


# ============================================================================
# HealthCheck Base Class Tests
# ============================================================================


@pytest.mark.unit
class TestHealthCheckBase:
    """Tests for HealthCheck abstract base class."""

    def test_health_check_initialization_with_defaults(self):
        """Test HealthCheck initialization with default values - MANDATORY AAA pattern."""

        # Arrange - MANDATORY
        class TestHealthCheck(HealthCheck):
            async def check(self) -> HealthCheckResult:
                return HealthCheckResult(
                    name=self.name,
                    status=HealthStatus.HEALTHY,
                    message="OK",
                    duration_ms=0.0,
                )

        # Act - MANDATORY
        health_check = TestHealthCheck(name="test_check")

        # Assert - MANDATORY
        assert health_check.name == "test_check"
        assert health_check.timeout_seconds == 30.0
        assert health_check.tags == []
        assert health_check.enabled is True

    def test_health_check_initialization_with_custom_values(self):
        """Test HealthCheck initialization with custom values - MANDATORY AAA pattern."""

        # Arrange - MANDATORY
        class TestHealthCheck(HealthCheck):
            async def check(self) -> HealthCheckResult:
                return HealthCheckResult(
                    name=self.name,
                    status=HealthStatus.HEALTHY,
                    message="OK",
                    duration_ms=0.0,
                )

        # Act - MANDATORY
        health_check = TestHealthCheck(
            name="custom_check",
            timeout_seconds=10.0,
            tags=["critical", "database"],
            enabled=False,
        )

        # Assert - MANDATORY
        assert health_check.name == "custom_check"
        assert health_check.timeout_seconds == 10.0
        assert health_check.tags == ["critical", "database"]
        assert health_check.enabled is False

    @pytest.mark.asyncio
    async def test_execute_when_disabled_returns_unknown(self):
        """Test execute() returns UNKNOWN when check is disabled - MANDATORY AAA pattern."""

        # Arrange - MANDATORY
        class TestHealthCheck(HealthCheck):
            async def check(self) -> HealthCheckResult:
                return HealthCheckResult(
                    name=self.name,
                    status=HealthStatus.HEALTHY,
                    message="OK",
                    duration_ms=0.0,
                )

        health_check = TestHealthCheck(name="test_check", enabled=False)

        # Act - MANDATORY
        result = await health_check.execute()

        # Assert - MANDATORY
        assert result.name == "test_check"
        assert result.status == HealthStatus.UNKNOWN
        assert result.message == "Health check disabled"
        assert result.duration_ms == 0.0

    @pytest.mark.asyncio
    async def test_execute_successful_check(self):
        """Test execute() with successful check - MANDATORY AAA pattern."""

        # Arrange - MANDATORY
        class TestHealthCheck(HealthCheck):
            async def check(self) -> HealthCheckResult:
                return HealthCheckResult(
                    name="internal_check",
                    status=HealthStatus.HEALTHY,
                    message="Test passed",
                    duration_ms=5.0,
                )

        health_check = TestHealthCheck(name="test_check", tags=["test"])

        # Act - MANDATORY
        result = await health_check.execute()

        # Assert - MANDATORY
        assert result.name == "test_check"  # Name overridden by execute()
        assert result.status == HealthStatus.HEALTHY
        assert result.message == "Test passed"
        assert result.tags == ["test"]  # Tags added by execute()
        assert result.duration_ms > 0

    @pytest.mark.asyncio
    async def test_execute_timeout_handling(self):
        """Test execute() handles timeout correctly - MANDATORY AAA pattern."""

        # Arrange - MANDATORY
        class SlowHealthCheck(HealthCheck):
            async def check(self) -> HealthCheckResult:
                await asyncio.sleep(2.0)  # Sleep longer than timeout
                return HealthCheckResult(
                    name=self.name,
                    status=HealthStatus.HEALTHY,
                    message="Should not reach here",
                    duration_ms=0.0,
                )

        health_check = SlowHealthCheck(name="slow_check", timeout_seconds=0.1)

        # Act - MANDATORY
        result = await health_check.execute()

        # Assert - MANDATORY
        assert result.name == "slow_check"
        assert result.status == HealthStatus.UNHEALTHY
        assert "timed out" in result.message.lower()
        assert result.duration_ms > 0


# ============================================================================
# FunctionHealthCheck Tests
# ============================================================================


@pytest.mark.unit
class TestFunctionHealthCheck:
    """Tests for FunctionHealthCheck wrapper."""

    @pytest.mark.asyncio
    async def test_function_health_check_with_bool_return(self, mock_check_function):
        """Test FunctionHealthCheck with bool return value - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        mock_check_function.return_value = True
        health_check = FunctionHealthCheck(name="bool_check", check_func=mock_check_function)

        # Act - MANDATORY
        result = await health_check.check()

        # Assert - MANDATORY
        assert result.name == "bool_check"
        assert result.status == HealthStatus.HEALTHY
        assert result.message == "OK"
        mock_check_function.assert_called_once()

    @pytest.mark.asyncio
    async def test_function_health_check_with_false_bool_return(self, mock_check_function):
        """Test FunctionHealthCheck with False bool return - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        mock_check_function.return_value = False
        health_check = FunctionHealthCheck(name="bool_check", check_func=mock_check_function)

        # Act - MANDATORY
        result = await health_check.check()

        # Assert - MANDATORY
        assert result.name == "bool_check"
        assert result.status == HealthStatus.UNHEALTHY
        assert result.message == "Check failed"

    @pytest.mark.asyncio
    async def test_function_health_check_with_string_return(self, mock_check_function):
        """Test FunctionHealthCheck with string return value - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        mock_check_function.return_value = "Everything is working"
        health_check = FunctionHealthCheck(name="string_check", check_func=mock_check_function)

        # Act - MANDATORY
        result = await health_check.check()

        # Assert - MANDATORY
        assert result.name == "string_check"
        assert result.status == HealthStatus.HEALTHY
        assert result.message == "Everything is working"

    @pytest.mark.asyncio
    async def test_function_health_check_with_health_check_result_return(self, mock_check_function):
        """Test FunctionHealthCheck with HealthCheckResult return - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        expected_result = HealthCheckResult(
            name="custom_result",
            status=HealthStatus.DEGRADED,
            message="Partially working",
            duration_ms=25.0,
            details={"warning": "slow"},
        )
        mock_check_function.return_value = expected_result
        health_check = FunctionHealthCheck(name="result_check", check_func=mock_check_function)

        # Act - MANDATORY
        result = await health_check.check()

        # Assert - MANDATORY
        assert result == expected_result

    @pytest.mark.asyncio
    async def test_function_health_check_with_async_function(self, mock_async_check_function):
        """Test FunctionHealthCheck with async function - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        mock_async_check_function.return_value = True
        health_check = FunctionHealthCheck(name="async_check", check_func=mock_async_check_function)

        # Act - MANDATORY
        result = await health_check.check()

        # Assert - MANDATORY
        assert result.status == HealthStatus.HEALTHY
        mock_async_check_function.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_function_health_check_with_custom_timeout(self, mock_check_function):
        """Test FunctionHealthCheck with custom timeout - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        mock_check_function.return_value = True
        health_check = FunctionHealthCheck(
            name="timeout_check", check_func=mock_check_function, timeout_seconds=5.0
        )

        # Act - MANDATORY
        result = await health_check.execute()

        # Assert - MANDATORY
        assert result.status == HealthStatus.HEALTHY
        assert health_check.timeout_seconds == 5.0


# ============================================================================
# MANDATORY Performance Benchmarks
# ============================================================================


@pytest.mark.performance
@pytest.mark.unit
class TestHealthCheckPerformance:
    """MANDATORY performance tests for health check operations."""

    @pytest.mark.asyncio
    async def test_health_check_result_creation_performance(self):
        """MANDATORY performance test - HealthCheckResult creation speed."""
        # Arrange - MANDATORY
        iterations = 10000

        # Act - MANDATORY
        start_time = time.perf_counter()

        for i in range(iterations):
            HealthCheckResult(
                name=f"check_{i}",
                status=HealthStatus.HEALTHY,
                message="OK",
                duration_ms=10.0,
                details={"iteration": i},
                tags=["test"],
            )

        end_time = time.perf_counter()
        execution_time = end_time - start_time

        # Assert - MANDATORY
        avg_time = execution_time / iterations
        assert avg_time < 0.0001  # <0.1ms per creation
        assert execution_time < 1.0  # Total <1s for 10000 creations

    @pytest.mark.asyncio
    async def test_health_check_execute_performance(self):
        """MANDATORY performance test - health check execution speed."""

        # Arrange - MANDATORY
        class FastHealthCheck(HealthCheck):
            async def check(self) -> HealthCheckResult:
                return HealthCheckResult(
                    name=self.name,
                    status=HealthStatus.HEALTHY,
                    message="Fast check",
                    duration_ms=0.0,
                )

        health_check = FastHealthCheck(name="fast_check")
        iterations = 1000

        # Act - MANDATORY
        start_time = time.perf_counter()

        for _ in range(iterations):
            await health_check.execute()

        end_time = time.perf_counter()
        execution_time = end_time - start_time

        # Assert - MANDATORY
        avg_time = execution_time / iterations
        assert avg_time < 0.01  # <10ms per execution
        assert execution_time < 5.0  # Total <5s for 1000 executions
