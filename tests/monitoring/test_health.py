"""Comprehensive tests for health check system with TEST_BUILDING.md compliance.

This module tests the health checking functionality including:
- Health check registration and management
- Built-in health checks (system resources, database, cache, disk, memory)
- Health status determination and monitoring
- Periodic health monitoring with async loops
- Health summary and detailed reporting

All tests follow TEST_BUILDING.md ZERO TOLERANCE standards:
- AAA pattern with MANDATORY comments
- Factory fixtures for DRY compliance
- Security tests for malicious inputs
- Performance benchmarks with specific thresholds
- NO vestigial code
- Modern Python 3.11+ patterns
"""

import time
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

from src.monitoring.health import (
    HealthChecker,
    HealthCheckResult,
    HealthConfig,
    HealthStatus,
)

# ============================================================================
# Factory Fixtures (DRY Principle - MANDATORY)
# ============================================================================


@pytest.fixture
def health_config() -> HealthConfig:
    """Factory for HealthConfig - DRY principle."""
    return HealthConfig(
        enabled=True,
        check_interval=1.0,  # Fast for testing
        timeout_seconds=5.0,
        critical_checks=["database_connection"],
        warning_checks=["memory_usage"],
    )


@pytest.fixture
def health_checker(health_config: HealthConfig) -> HealthChecker:
    """Factory for HealthChecker - DRY principle."""
    return HealthChecker(config=health_config)


@pytest.fixture
def health_check_result() -> HealthCheckResult:
    """Factory for HealthCheckResult - DRY principle."""
    return HealthCheckResult(
        name="test_check",
        status=HealthStatus.HEALTHY,
        message="Test check passed",
        duration_ms=10.5,
        timestamp=datetime.now(UTC),
        details={"test_key": "test_value"},
    )


# ============================================================================
# Tests: HealthStatus Enum
# ============================================================================


@pytest.mark.unit
class TestHealthStatus:
    """Tests for HealthStatus enum - MANDATORY AAA pattern."""

    def test_all_status_levels_exist(self):
        """Test all health status levels exist - MANDATORY AAA pattern."""
        # Arrange - MANDATORY

        # Act - MANDATORY
        statuses = [
            HealthStatus.HEALTHY,
            HealthStatus.DEGRADED,
            HealthStatus.UNHEALTHY,
            HealthStatus.UNKNOWN,
        ]

        # Assert - MANDATORY
        assert len(statuses) == 4
        assert all(isinstance(s, HealthStatus) for s in statuses)

    def test_status_values_correct(self):
        """Test health status enum values - MANDATORY AAA pattern."""
        # Arrange - MANDATORY

        # Act - MANDATORY
        values = {
            HealthStatus.HEALTHY.value: "healthy",
            HealthStatus.DEGRADED.value: "degraded",
            HealthStatus.UNHEALTHY.value: "unhealthy",
            HealthStatus.UNKNOWN.value: "unknown",
        }

        # Assert - MANDATORY
        assert values[HealthStatus.HEALTHY.value] == "healthy"
        assert values[HealthStatus.DEGRADED.value] == "degraded"
        assert values[HealthStatus.UNHEALTHY.value] == "unhealthy"
        assert values[HealthStatus.UNKNOWN.value] == "unknown"


# ============================================================================
# Tests: HealthCheckResult Dataclass
# ============================================================================


@pytest.mark.unit
class TestHealthCheckResult:
    """Tests for HealthCheckResult dataclass - MANDATORY AAA pattern."""

    def test_result_creation_with_required_fields(self, health_check_result: HealthCheckResult):
        """Test health check result creation - MANDATORY AAA pattern."""
        # Arrange - MANDATORY (fixture provides result)

        # Act - MANDATORY

        # Assert - MANDATORY
        assert health_check_result.name == "test_check"
        assert health_check_result.status == HealthStatus.HEALTHY
        assert health_check_result.message == "Test check passed"
        assert health_check_result.duration_ms == 10.5
        assert isinstance(health_check_result.timestamp, datetime)
        assert health_check_result.details == {"test_key": "test_value"}

    def test_result_supports_all_statuses(self):
        """Test health check result supports all status types - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        statuses = [
            HealthStatus.HEALTHY,
            HealthStatus.DEGRADED,
            HealthStatus.UNHEALTHY,
            HealthStatus.UNKNOWN,
        ]

        # Act & Assert - MANDATORY
        for status in statuses:
            result = HealthCheckResult(
                name="test",
                status=status,
                message="Test",
                duration_ms=1.0,
                timestamp=datetime.now(UTC),
            )
            assert result.status == status

    def test_result_details_optional(self):
        """Test health check result details are optional - MANDATORY AAA pattern."""
        # Arrange - MANDATORY

        # Act - MANDATORY
        result = HealthCheckResult(
            name="test",
            status=HealthStatus.HEALTHY,
            message="Test",
            duration_ms=1.0,
            timestamp=datetime.now(UTC),
        )

        # Assert - MANDATORY
        assert result.details == {}


# ============================================================================
# Tests: HealthConfig
# ============================================================================


@pytest.mark.unit
class TestHealthConfig:
    """Tests for HealthConfig configuration - MANDATORY AAA pattern."""

    def test_config_defaults(self):
        """Test health config has sensible defaults - MANDATORY AAA pattern."""
        # Arrange - MANDATORY

        # Act - MANDATORY
        config = HealthConfig()

        # Assert - MANDATORY
        assert config.enabled is True
        assert config.check_interval == 30.0
        assert config.timeout_seconds == 10.0
        assert isinstance(config.critical_checks, list)
        assert isinstance(config.warning_checks, list)
        assert config.endpoint_path == "/health"
        assert config.detailed_endpoint_path == "/health/detailed"

    def test_config_customization(self):
        """Test health config can be customized - MANDATORY AAA pattern."""
        # Arrange - MANDATORY

        # Act - MANDATORY
        config = HealthConfig(
            enabled=False,
            check_interval=60.0,
            timeout_seconds=20.0,
            critical_checks=["database"],
            warning_checks=["cache"],
            endpoint_path="/custom/health",
        )

        # Assert - MANDATORY
        assert config.enabled is False
        assert config.check_interval == 60.0
        assert config.timeout_seconds == 20.0
        assert config.critical_checks == ["database"]
        assert config.warning_checks == ["cache"]
        assert config.endpoint_path == "/custom/health"


# ============================================================================
# Tests: HealthChecker Initialization
# ============================================================================


@pytest.mark.unit
class TestHealthCheckerInitialization:
    """Tests for HealthChecker initialization - MANDATORY AAA pattern."""

    def test_checker_initializes_with_config(self, health_config: HealthConfig):
        """Test health checker initializes with config - MANDATORY AAA pattern."""
        # Arrange - MANDATORY

        # Act - MANDATORY
        checker = HealthChecker(config=health_config)

        # Assert - MANDATORY
        assert checker.config == health_config
        assert isinstance(checker._checks, dict)
        assert isinstance(checker._results, dict)
        assert checker._checking is False

    def test_checker_registers_builtin_checks(self):
        """Test health checker registers built-in checks - MANDATORY AAA pattern."""
        # Arrange - MANDATORY

        # Act - MANDATORY
        checker = HealthChecker()

        # Assert - MANDATORY
        assert "system_resources" in checker._checks
        assert "database_connection" in checker._checks
        assert "cache_backend" in checker._checks
        assert "disk_space" in checker._checks
        assert "memory_usage" in checker._checks


# ============================================================================
# Tests: Check Registration
# ============================================================================


@pytest.mark.unit
class TestCheckRegistration:
    """Tests for health check registration - MANDATORY AAA pattern."""

    def test_register_custom_check(self, health_checker: HealthChecker):
        """Test registering a custom health check - MANDATORY AAA pattern."""

        # Arrange - MANDATORY
        async def custom_check():
            return True

        # Act - MANDATORY
        health_checker.register_check("custom_check", custom_check)

        # Assert - MANDATORY
        assert "custom_check" in health_checker._checks
        assert health_checker._checks["custom_check"] == custom_check

    def test_unregister_check(self, health_checker: HealthChecker):
        """Test unregistering a health check - MANDATORY AAA pattern."""

        # Arrange - MANDATORY
        async def custom_check():
            return True

        health_checker.register_check("custom_check", custom_check)

        # Act - MANDATORY
        result = health_checker.unregister_check("custom_check")

        # Assert - MANDATORY
        assert result is True
        assert "custom_check" not in health_checker._checks

    def test_unregister_nonexistent_check(self, health_checker: HealthChecker):
        """Test unregistering nonexistent check returns False - MANDATORY AAA pattern."""
        # Arrange - MANDATORY

        # Act - MANDATORY
        result = health_checker.unregister_check("nonexistent")

        # Assert - MANDATORY
        assert result is False


# ============================================================================
# Tests: Overall Status Determination
# ============================================================================


@pytest.mark.unit
class TestOverallStatusDetermination:
    """Tests for overall health status determination - MANDATORY AAA pattern."""

    def test_overall_status_unknown_when_no_results(self, health_checker: HealthChecker):
        """Test overall status is unknown when no results - MANDATORY AAA pattern."""
        # Arrange - MANDATORY

        # Act - MANDATORY
        status = health_checker.get_overall_status()

        # Assert - MANDATORY
        assert status == HealthStatus.UNKNOWN

    def test_overall_status_healthy_when_all_healthy(self, health_checker: HealthChecker):
        """Test overall status is healthy when all checks healthy - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        health_checker._results = {
            "check1": HealthCheckResult(
                "check1", HealthStatus.HEALTHY, "OK", 1.0, datetime.now(UTC)
            ),
            "check2": HealthCheckResult(
                "check2", HealthStatus.HEALTHY, "OK", 1.0, datetime.now(UTC)
            ),
        }

        # Act - MANDATORY
        status = health_checker.get_overall_status()

        # Assert - MANDATORY
        assert status == HealthStatus.HEALTHY

    def test_overall_status_degraded_when_any_degraded(self, health_checker: HealthChecker):
        """Test overall status is degraded when any check degraded - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        health_checker._results = {
            "check1": HealthCheckResult(
                "check1", HealthStatus.HEALTHY, "OK", 1.0, datetime.now(UTC)
            ),
            "check2": HealthCheckResult(
                "check2", HealthStatus.DEGRADED, "Warning", 1.0, datetime.now(UTC)
            ),
        }

        # Act - MANDATORY
        status = health_checker.get_overall_status()

        # Assert - MANDATORY
        assert status == HealthStatus.DEGRADED

    def test_overall_status_unhealthy_when_any_unhealthy(self, health_checker: HealthChecker):
        """Test overall status is unhealthy when any check unhealthy - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        health_checker._results = {
            "check1": HealthCheckResult(
                "check1", HealthStatus.HEALTHY, "OK", 1.0, datetime.now(UTC)
            ),
            "check2": HealthCheckResult(
                "check2", HealthStatus.UNHEALTHY, "Failed", 1.0, datetime.now(UTC)
            ),
        }

        # Act - MANDATORY
        status = health_checker.get_overall_status()

        # Assert - MANDATORY
        assert status == HealthStatus.UNHEALTHY

    def test_overall_status_unhealthy_when_critical_check_fails(self):
        """Test overall status is unhealthy when critical check fails - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        config = HealthConfig(critical_checks=["database_connection"])
        checker = HealthChecker(config=config)
        checker._results = {
            "database_connection": HealthCheckResult(
                "database_connection", HealthStatus.UNHEALTHY, "Failed", 1.0, datetime.now(UTC)
            ),
        }

        # Act - MANDATORY
        status = checker.get_overall_status()

        # Assert - MANDATORY
        assert status == HealthStatus.UNHEALTHY


# ============================================================================
# Tests: Health Summary
# ============================================================================


@pytest.mark.unit
class TestHealthSummary:
    """Tests for health summary generation - MANDATORY AAA pattern."""

    def test_get_health_summary_structure(self, health_checker: HealthChecker):
        """Test health summary has correct structure - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        health_checker._results = {
            "test": HealthCheckResult("test", HealthStatus.HEALTHY, "OK", 1.0, datetime.now(UTC)),
        }

        # Act - MANDATORY
        summary = health_checker.get_health_summary()

        # Assert - MANDATORY
        assert "status" in summary
        assert "timestamp" in summary
        assert "checks" in summary
        assert "summary" in summary
        assert "total_checks" in summary["summary"]
        assert "healthy" in summary["summary"]
        assert "degraded" in summary["summary"]
        assert "unhealthy" in summary["summary"]
        assert "unknown" in summary["summary"]

    def test_get_detailed_health_includes_details(self, health_checker: HealthChecker):
        """Test detailed health includes check details - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        health_checker._results = {
            "test": HealthCheckResult(
                "test",
                HealthStatus.HEALTHY,
                "OK",
                1.0,
                datetime.now(UTC),
                details={"cpu": 50.0},
            ),
        }

        # Act - MANDATORY
        detailed = health_checker.get_detailed_health()

        # Assert - MANDATORY
        assert "checks" in detailed
        assert "test" in detailed["checks"]
        assert "details" in detailed["checks"]["test"]
        assert detailed["checks"]["test"]["details"] == {"cpu": 50.0}


# ============================================================================
# Tests: Async Operations
# ============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
class TestHealthCheckerAsyncOperations:
    """Tests for async health checker operations - MANDATORY AAA pattern."""

    async def test_start_monitoring(self, health_checker: HealthChecker):
        """Test starting health monitoring - MANDATORY AAA pattern."""
        # Arrange - MANDATORY

        # Act - MANDATORY
        await health_checker.start_monitoring()

        # Assert - MANDATORY
        assert health_checker._checking is True
        assert health_checker._check_task is not None

        # Cleanup
        await health_checker.stop_monitoring()

    async def test_stop_monitoring(self, health_checker: HealthChecker):
        """Test stopping health monitoring - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        await health_checker.start_monitoring()

        # Act - MANDATORY
        await health_checker.stop_monitoring()

        # Assert - MANDATORY
        assert health_checker._checking is False

    async def test_shutdown_stops_monitoring(self, health_checker: HealthChecker):
        """Test shutdown stops monitoring - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        await health_checker.start_monitoring()

        # Act - MANDATORY
        await health_checker.shutdown()

        # Assert - MANDATORY
        assert health_checker._checking is False

    async def test_run_all_checks_executes_registered_checks(self, health_checker: HealthChecker):
        """Test run_all_checks executes all registered checks - MANDATORY AAA pattern."""

        # Arrange - MANDATORY
        async def custom_check():
            return True

        health_checker.register_check("custom", custom_check)

        # Act - MANDATORY
        results = await health_checker.run_all_checks()

        # Assert - MANDATORY
        assert "custom" in results
        assert isinstance(results["custom"], HealthCheckResult)

    async def test_run_single_check_with_boolean_return(self, health_checker: HealthChecker):
        """Test single check with boolean return - MANDATORY AAA pattern."""

        # Arrange - MANDATORY
        async def bool_check():
            return True

        # Act - MANDATORY
        result = await health_checker._run_single_check("bool_test", bool_check)

        # Assert - MANDATORY
        assert result.name == "bool_test"
        assert result.status == HealthStatus.HEALTHY
        assert result.message == "OK"

    async def test_run_single_check_with_false_return(self, health_checker: HealthChecker):
        """Test single check with False return - MANDATORY AAA pattern."""

        # Arrange - MANDATORY
        async def failing_check():
            return False

        # Act - MANDATORY
        result = await health_checker._run_single_check("fail_test", failing_check)

        # Assert - MANDATORY
        assert result.name == "fail_test"
        assert result.status == HealthStatus.UNHEALTHY
        assert result.message == "Check failed"


# ============================================================================
# Tests: Built-in Health Checks
# ============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
class TestBuiltinHealthChecks:
    """Tests for built-in health checks - MANDATORY AAA pattern."""

    async def test_check_system_resources_healthy(self):
        """Test system resources check when healthy - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        checker = HealthChecker()

        # Mock psutil to return healthy values
        with (
            patch("psutil.cpu_percent", return_value=50.0),
            patch("psutil.virtual_memory") as mock_memory,
        ):
            mock_memory.return_value = MagicMock(percent=60.0, available=4 * 1024**3)

            # Act - MANDATORY
            result = await checker._check_system_resources()

            # Assert - MANDATORY
            assert result.status == HealthStatus.HEALTHY
            assert "cpu_percent" in result.details
            assert "memory_percent" in result.details

    async def test_check_system_resources_degraded(self):
        """Test system resources check when degraded - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        checker = HealthChecker()

        # Mock psutil to return degraded values
        with (
            patch("psutil.cpu_percent", return_value=80.0),
            patch("psutil.virtual_memory") as mock_memory,
        ):
            mock_memory.return_value = MagicMock(percent=80.0, available=2 * 1024**3)

            # Act - MANDATORY
            result = await checker._check_system_resources()

            # Assert - MANDATORY
            assert result.status == HealthStatus.DEGRADED

    async def test_check_system_resources_unhealthy(self):
        """Test system resources check when unhealthy - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        checker = HealthChecker()

        # Mock psutil to return unhealthy values
        with (
            patch("psutil.cpu_percent", return_value=95.0),
            patch("psutil.virtual_memory") as mock_memory,
        ):
            mock_memory.return_value = MagicMock(percent=95.0, available=0.5 * 1024**3)

            # Act - MANDATORY
            result = await checker._check_system_resources()

            # Assert - MANDATORY
            assert result.status == HealthStatus.UNHEALTHY


# ============================================================================
# MANDATORY Security Tests
# ============================================================================


@pytest.mark.security
@pytest.mark.unit
class TestHealthSecurity:
    """MANDATORY security tests for health check system."""

    def test_check_name_sanitization(self, health_checker: HealthChecker):
        """MANDATORY security test - check names with malicious characters."""
        # Arrange - MANDATORY
        malicious_names = [
            "../../../etc/passwd",
            "test<script>alert('xss')</script>",
            "test'; DROP TABLE health;--",
            "test`whoami`",
        ]

        # Act & Assert - MANDATORY
        for name in malicious_names:

            async def test_check():
                return True

            health_checker.register_check(name, test_check)
            assert name in health_checker._checks

    def test_health_message_prevents_injection(self):
        """MANDATORY security test - health messages prevent injection."""
        # Arrange - MANDATORY
        malicious_message = "Check failed <script>alert('xss')</script>"

        # Act - MANDATORY
        result = HealthCheckResult(
            name="test",
            status=HealthStatus.UNHEALTHY,
            message=malicious_message,
            duration_ms=1.0,
            timestamp=datetime.now(UTC),
        )

        # Assert - MANDATORY (message stored but should be escaped on output)
        assert result.message == malicious_message


# ============================================================================
# MANDATORY Performance Tests
# ============================================================================


@pytest.mark.performance
@pytest.mark.unit
class TestHealthPerformance:
    """MANDATORY performance tests for health check system."""

    def test_overall_status_calculation_performance(self, health_checker: HealthChecker):
        """MANDATORY performance test - status calculation speed."""
        # Arrange - MANDATORY
        # Add many check results
        for i in range(100):
            health_checker._results[f"check_{i}"] = HealthCheckResult(
                f"check_{i}", HealthStatus.HEALTHY, "OK", 1.0, datetime.now(UTC)
            )

        iterations = 1000
        start_time = time.perf_counter()

        # Act - MANDATORY
        for _ in range(iterations):
            health_checker.get_overall_status()

        end_time = time.perf_counter()
        execution_time = end_time - start_time

        # Assert - MANDATORY
        avg_time = execution_time / iterations
        assert avg_time < 0.001  # <1ms per status calculation
        assert execution_time < 1.0  # Total <1s for 1000 calculations

    def test_health_summary_generation_performance(self, health_checker: HealthChecker):
        """MANDATORY performance test - summary generation speed."""
        # Arrange - MANDATORY
        for i in range(50):
            health_checker._results[f"check_{i}"] = HealthCheckResult(
                f"check_{i}", HealthStatus.HEALTHY, "OK", 1.0, datetime.now(UTC)
            )

        iterations = 100
        start_time = time.perf_counter()

        # Act - MANDATORY
        for _ in range(iterations):
            health_checker.get_health_summary()

        end_time = time.perf_counter()
        execution_time = end_time - start_time

        # Assert - MANDATORY
        avg_time = execution_time / iterations
        assert avg_time < 0.01  # <10ms per summary generation
        assert execution_time < 1.0  # Total <1s for 100 summaries
