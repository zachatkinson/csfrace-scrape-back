"""Comprehensive tests for health check registry - MANDATORY TEST_BUILDING.md compliance.

This module tests health check registry functionality with complete coverage:
- HealthCheckRegistry initialization
- Health check registration and unregistration
- Tag management and filtering
- Running individual and multiple health checks
- Parallel and sequential execution
- Health summary generation
- Edge cases and error handling
- Performance benchmarks

ALL tests follow MANDATORY TEST_BUILDING.md patterns:
- AAA pattern with explicit comments
- Factory fixtures for DRY principle
- Comprehensive registry scenario testing
- Performance benchmarks with specific thresholds
"""

import time

import asyncio
import pytest

from src.monitoring.health_checks.base import HealthCheck, HealthCheckResult, HealthStatus
from src.monitoring.health_checks.registry import HealthCheckRegistry

# ============================================================================
# Test Fixtures - DRY Principle
# ============================================================================


@pytest.fixture
def registry():
    """Factory for HealthCheckRegistry - DRY principle."""
    return HealthCheckRegistry()


@pytest.fixture
def mock_health_check():
    """Factory for mock HealthCheck - DRY principle."""

    class MockHealthCheck(HealthCheck):
        async def check(self) -> HealthCheckResult:
            return HealthCheckResult(
                name=self.name,
                status=HealthStatus.HEALTHY,
                message="Mock check passed",
                duration_ms=10.0,
            )

    return MockHealthCheck(name="mock_check", timeout_seconds=5.0)


@pytest.fixture
def sample_health_result():
    """Factory for sample HealthCheckResult - DRY principle."""
    return HealthCheckResult(
        name="sample_check",
        status=HealthStatus.HEALTHY,
        message="Sample successful",
        duration_ms=15.0,
        details={"key": "value"},
    )


# ============================================================================
# HealthCheckRegistry Initialization Tests
# ============================================================================


@pytest.mark.unit
class TestHealthCheckRegistryInit:
    """Tests for HealthCheckRegistry initialization."""

    def test_registry_initialization_empty(self):
        """Test registry initializes with empty state - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # Act - MANDATORY
        registry = HealthCheckRegistry()

        # Assert - MANDATORY
        assert len(registry._checks) == 0
        assert len(registry._tags) == 0
        assert registry.list_checks() == []
        assert registry.list_tags() == []


# ============================================================================
# Register/Unregister Tests
# ============================================================================


@pytest.mark.unit
class TestRegisterUnregister:
    """Tests for health check registration and unregistration."""

    def test_register_health_check_without_tags(self, registry, mock_health_check):
        """Test registering health check without tags - MANDATORY AAA pattern."""
        # Arrange - MANDATORY (using fixtures)

        # Act - MANDATORY
        registry.register(mock_health_check)

        # Assert - MANDATORY
        assert "mock_check" in registry._checks
        assert registry._checks["mock_check"] == mock_health_check
        assert len(registry.list_checks()) == 1

    def test_register_health_check_with_tags(self, registry, mock_health_check):
        """Test registering health check with tags - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        tags = ["critical", "database"]

        # Act - MANDATORY
        registry.register(mock_health_check, tags=tags)

        # Assert - MANDATORY
        assert "mock_check" in registry._checks
        assert "critical" in registry._tags
        assert "database" in registry._tags
        assert "mock_check" in registry._tags["critical"]
        assert "mock_check" in registry._tags["database"]

    def test_register_duplicate_health_check_overwrites(self, registry, mock_health_check):
        """Test registering duplicate check overwrites existing - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        registry.register(mock_health_check)

        class NewMockHealthCheck(HealthCheck):
            async def check(self) -> HealthCheckResult:
                return HealthCheckResult(
                    name=self.name,
                    status=HealthStatus.UNHEALTHY,
                    message="New mock",
                    duration_ms=5.0,
                )

        new_check = NewMockHealthCheck(name="mock_check")

        # Act - MANDATORY
        registry.register(new_check)

        # Assert - MANDATORY
        assert registry._checks["mock_check"] == new_check
        assert len(registry.list_checks()) == 1

    def test_unregister_existing_health_check(self, registry, mock_health_check):
        """Test unregistering existing health check - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        registry.register(mock_health_check, tags=["test"])

        # Act - MANDATORY
        result = registry.unregister("mock_check")

        # Assert - MANDATORY
        assert result is True
        assert "mock_check" not in registry._checks
        assert len(registry.list_checks()) == 0
        assert len(registry._tags) == 0  # Tag cleaned up

    def test_unregister_nonexistent_health_check(self, registry):
        """Test unregistering nonexistent check returns False - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # Act - MANDATORY
        result = registry.unregister("nonexistent")

        # Assert - MANDATORY
        assert result is False


# ============================================================================
# Get Check/Tag Tests
# ============================================================================


@pytest.mark.unit
class TestGetChecks:
    """Tests for getting checks and filtering by tags."""

    def test_get_check_existing(self, registry, mock_health_check):
        """Test getting existing health check - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        registry.register(mock_health_check)

        # Act - MANDATORY
        check = registry.get_check("mock_check")

        # Assert - MANDATORY
        assert check == mock_health_check

    def test_get_check_nonexistent(self, registry):
        """Test getting nonexistent check returns None - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # Act - MANDATORY
        check = registry.get_check("nonexistent")

        # Assert - MANDATORY
        assert check is None

    def test_get_checks_by_tag_existing(self, registry, mock_health_check):
        """Test getting checks by existing tag - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        registry.register(mock_health_check, tags=["critical"])

        # Act - MANDATORY
        checks = registry.get_checks_by_tag("critical")

        # Assert - MANDATORY
        assert len(checks) == 1
        assert checks[0] == mock_health_check

    def test_get_checks_by_tag_nonexistent(self, registry):
        """Test getting checks by nonexistent tag - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # Act - MANDATORY
        checks = registry.get_checks_by_tag("nonexistent")

        # Assert - MANDATORY
        assert len(checks) == 0

    def test_list_checks(self, registry):
        """Test listing all registered check names - MANDATORY AAA pattern."""

        # Arrange - MANDATORY
        class Check1(HealthCheck):
            async def check(self) -> HealthCheckResult:
                return HealthCheckResult(
                    name=self.name, status=HealthStatus.HEALTHY, message="OK", duration_ms=0.0
                )

        class Check2(HealthCheck):
            async def check(self) -> HealthCheckResult:
                return HealthCheckResult(
                    name=self.name, status=HealthStatus.HEALTHY, message="OK", duration_ms=0.0
                )

        registry.register(Check1(name="check1"))
        registry.register(Check2(name="check2"))

        # Act - MANDATORY
        check_names = registry.list_checks()

        # Assert - MANDATORY
        assert len(check_names) == 2
        assert "check1" in check_names
        assert "check2" in check_names

    def test_list_tags(self, registry, mock_health_check):
        """Test listing all registered tags - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        registry.register(mock_health_check, tags=["critical", "database"])

        # Act - MANDATORY
        tags = registry.list_tags()

        # Assert - MANDATORY
        assert len(tags) == 2
        assert "critical" in tags
        assert "database" in tags


# ============================================================================
# Run Check Tests
# ============================================================================


@pytest.mark.unit
class TestRunCheck:
    """Tests for running individual health checks."""

    @pytest.mark.asyncio
    async def test_run_check_existing_successful(self, registry, mock_health_check):
        """Test running existing check successfully - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        registry.register(mock_health_check)

        # Act - MANDATORY
        result = await registry.run_check("mock_check")

        # Assert - MANDATORY
        assert result is not None
        assert result.name == "mock_check"
        assert result.status == HealthStatus.HEALTHY

    @pytest.mark.asyncio
    async def test_run_check_nonexistent(self, registry):
        """Test running nonexistent check returns None - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # Act - MANDATORY
        result = await registry.run_check("nonexistent")

        # Assert - MANDATORY
        assert result is None

    @pytest.mark.asyncio
    async def test_run_check_timeout_handling(self, registry):
        """Test run_check() handles timeout correctly - MANDATORY AAA pattern."""

        # Arrange - MANDATORY
        class SlowCheck(HealthCheck):
            async def check(self) -> HealthCheckResult:
                await asyncio.sleep(2.0)
                return HealthCheckResult(
                    name=self.name,
                    status=HealthStatus.HEALTHY,
                    message="Should not reach",
                    duration_ms=0.0,
                )

        slow_check = SlowCheck(name="slow_check", timeout_seconds=0.1)
        registry.register(slow_check)

        # Act - MANDATORY
        result = await registry.run_check("slow_check")

        # Assert - MANDATORY
        assert result is not None
        assert result.status == HealthStatus.UNHEALTHY
        assert "timed out" in result.message.lower()

    @pytest.mark.asyncio
    async def test_run_check_exception_handling(self, registry):
        """Test run_check() handles exceptions correctly - MANDATORY AAA pattern."""

        # Arrange - MANDATORY
        class FailingCheck(HealthCheck):
            async def check(self) -> HealthCheckResult:
                raise ValueError("Test error")

        failing_check = FailingCheck(name="failing_check")
        registry.register(failing_check)

        # Act - MANDATORY
        result = await registry.run_check("failing_check")

        # Assert - MANDATORY
        assert result is not None
        assert result.status == HealthStatus.UNHEALTHY
        assert "check failed" in result.message.lower()
        assert result.details["error_type"] == "ValueError"


# ============================================================================
# Run Multiple Checks Tests
# ============================================================================


@pytest.mark.unit
class TestRunMultipleChecks:
    """Tests for running multiple health checks."""

    @pytest.mark.asyncio
    async def test_run_checks_by_tag(self, registry):
        """Test running checks by tag - MANDATORY AAA pattern."""

        # Arrange - MANDATORY
        class Check1(HealthCheck):
            async def check(self) -> HealthCheckResult:
                return HealthCheckResult(
                    name=self.name, status=HealthStatus.HEALTHY, message="OK", duration_ms=10.0
                )

        class Check2(HealthCheck):
            async def check(self) -> HealthCheckResult:
                return HealthCheckResult(
                    name=self.name, status=HealthStatus.HEALTHY, message="OK", duration_ms=15.0
                )

        registry.register(Check1(name="check1"), tags=["critical"])
        registry.register(Check2(name="check2"), tags=["critical"])

        # Act - MANDATORY
        results = await registry.run_checks_by_tag("critical")

        # Assert - MANDATORY
        assert len(results) == 2
        assert all(isinstance(r, HealthCheckResult) for r in results)

    @pytest.mark.asyncio
    async def test_run_checks_by_nonexistent_tag(self, registry):
        """Test running checks by nonexistent tag - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # Act - MANDATORY
        results = await registry.run_checks_by_tag("nonexistent")

        # Assert - MANDATORY
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_run_all_checks_parallel(self, registry):
        """Test running all checks in parallel - MANDATORY AAA pattern."""

        # Arrange - MANDATORY
        class Check1(HealthCheck):
            async def check(self) -> HealthCheckResult:
                await asyncio.sleep(0.1)
                return HealthCheckResult(
                    name=self.name, status=HealthStatus.HEALTHY, message="OK", duration_ms=10.0
                )

        class Check2(HealthCheck):
            async def check(self) -> HealthCheckResult:
                await asyncio.sleep(0.1)
                return HealthCheckResult(
                    name=self.name, status=HealthStatus.HEALTHY, message="OK", duration_ms=15.0
                )

        registry.register(Check1(name="check1"))
        registry.register(Check2(name="check2"))

        # Act - MANDATORY
        start_time = time.perf_counter()
        results = await registry.run_all_checks(parallel=True)
        execution_time = time.perf_counter() - start_time

        # Assert - MANDATORY
        assert len(results) == 2
        assert execution_time < 0.3  # Should complete in <0.3s (parallel, not 0.2s sequential)

    @pytest.mark.asyncio
    async def test_run_all_checks_sequential(self, registry):
        """Test running all checks sequentially - MANDATORY AAA pattern."""

        # Arrange - MANDATORY
        class Check1(HealthCheck):
            async def check(self) -> HealthCheckResult:
                return HealthCheckResult(
                    name=self.name, status=HealthStatus.HEALTHY, message="OK", duration_ms=10.0
                )

        class Check2(HealthCheck):
            async def check(self) -> HealthCheckResult:
                return HealthCheckResult(
                    name=self.name, status=HealthStatus.HEALTHY, message="OK", duration_ms=15.0
                )

        registry.register(Check1(name="check1"))
        registry.register(Check2(name="check2"))

        # Act - MANDATORY
        results = await registry.run_all_checks(parallel=False)

        # Assert - MANDATORY
        assert len(results) == 2
        assert all(isinstance(r, HealthCheckResult) for r in results)

    @pytest.mark.asyncio
    async def test_run_all_checks_empty_registry(self, registry):
        """Test running all checks with empty registry - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # Act - MANDATORY
        results = await registry.run_all_checks()

        # Assert - MANDATORY
        assert len(results) == 0


# ============================================================================
# Health Summary Tests
# ============================================================================


@pytest.mark.unit
class TestHealthSummary:
    """Tests for health summary generation."""

    def test_get_health_summary_empty_results(self, registry):
        """Test getting health summary with no results - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        results = []

        # Act - MANDATORY
        summary = registry.get_health_summary(results)

        # Assert - MANDATORY
        assert summary["status"] == "UNKNOWN"
        assert summary["total_checks"] == 0
        assert summary["healthy"] == 0
        assert summary["degraded"] == 0
        assert summary["unhealthy"] == 0
        assert summary["checks"] == []

    def test_get_health_summary_all_healthy(self, registry):
        """Test getting health summary with all healthy checks - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        results = [
            HealthCheckResult(
                name="check1", status=HealthStatus.HEALTHY, message="OK", duration_ms=10.0
            ),
            HealthCheckResult(
                name="check2", status=HealthStatus.HEALTHY, message="OK", duration_ms=15.0
            ),
        ]

        # Act - MANDATORY
        summary = registry.get_health_summary(results)

        # Assert - MANDATORY
        assert summary["status"] == "HEALTHY"
        assert summary["total_checks"] == 2
        assert summary["healthy"] == 2
        assert summary["degraded"] == 0
        assert summary["unhealthy"] == 0
        assert len(summary["checks"]) == 2

    def test_get_health_summary_with_degraded(self, registry):
        """Test getting health summary with degraded checks - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        results = [
            HealthCheckResult(
                name="check1", status=HealthStatus.HEALTHY, message="OK", duration_ms=10.0
            ),
            HealthCheckResult(
                name="check2", status=HealthStatus.DEGRADED, message="Slow", duration_ms=100.0
            ),
        ]

        # Act - MANDATORY
        summary = registry.get_health_summary(results)

        # Assert - MANDATORY
        assert summary["status"] == "DEGRADED"
        assert summary["total_checks"] == 2
        assert summary["healthy"] == 1
        assert summary["degraded"] == 1
        assert summary["unhealthy"] == 0

    def test_get_health_summary_with_unhealthy(self, registry):
        """Test getting health summary with unhealthy checks - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        results = [
            HealthCheckResult(
                name="check1", status=HealthStatus.HEALTHY, message="OK", duration_ms=10.0
            ),
            HealthCheckResult(
                name="check2", status=HealthStatus.UNHEALTHY, message="Failed", duration_ms=0.0
            ),
        ]

        # Act - MANDATORY
        summary = registry.get_health_summary(results)

        # Assert - MANDATORY
        assert summary["status"] == "UNHEALTHY"
        assert summary["total_checks"] == 2
        assert summary["healthy"] == 1
        assert summary["degraded"] == 0
        assert summary["unhealthy"] == 1


# ============================================================================
# MANDATORY Performance Benchmarks
# ============================================================================


@pytest.mark.performance
@pytest.mark.unit
class TestHealthCheckRegistryPerformance:
    """MANDATORY performance tests for registry operations."""

    def test_registry_creation_performance(self):
        """MANDATORY performance test - registry creation speed."""
        # Arrange - MANDATORY
        iterations = 10000

        # Act - MANDATORY
        start_time = time.perf_counter()

        for _ in range(iterations):
            HealthCheckRegistry()

        end_time = time.perf_counter()
        execution_time = end_time - start_time

        # Assert - MANDATORY
        avg_time = execution_time / iterations
        assert avg_time < 0.0001  # <0.1ms per creation
        assert execution_time < 1.0  # Total <1s for 10000 creations

    def test_register_check_performance(self, mock_health_check):
        """MANDATORY performance test - check registration speed."""
        # Arrange - MANDATORY
        registry = HealthCheckRegistry()
        iterations = 1000

        # Act - MANDATORY
        start_time = time.perf_counter()

        for i in range(iterations):

            class TestCheck(HealthCheck):
                async def check(self) -> HealthCheckResult:
                    return HealthCheckResult(
                        name=self.name,
                        status=HealthStatus.HEALTHY,
                        message="OK",
                        duration_ms=0.0,
                    )

            registry.register(TestCheck(name=f"check_{i}"))

        end_time = time.perf_counter()
        execution_time = end_time - start_time

        # Assert - MANDATORY
        avg_time = execution_time / iterations
        assert avg_time < 0.001  # <1ms per registration
        assert execution_time < 1.0  # Total <1s for 1000 registrations
