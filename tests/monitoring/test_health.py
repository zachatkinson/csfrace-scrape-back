"""Tests for health check system."""

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.monitoring.health import (
    HealthChecker,
    HealthCheckResult,
    HealthConfig,
    HealthStatus,
)


class TestHealthStatus:
    """Test health status enumeration."""

    def test_status_values(self):
        """Test all status values."""
        assert HealthStatus.HEALTHY.value == "healthy"
        assert HealthStatus.DEGRADED.value == "degraded"
        assert HealthStatus.UNHEALTHY.value == "unhealthy"
        assert HealthStatus.UNKNOWN.value == "unknown"


class TestHealthCheckResult:
    """Test health check result data structure."""

    def test_result_creation(self):
        """Test creating health check result."""
        timestamp = datetime.now(timezone.utc)
        result = HealthCheckResult(
            name="test_check",
            status=HealthStatus.HEALTHY,
            message="All good",
            duration_ms=50.0,
            timestamp=timestamp,
            details={"cpu": 25.0},
        )

        assert result.name == "test_check"
        assert result.status == HealthStatus.HEALTHY
        assert result.message == "All good"
        assert result.duration_ms == 50.0
        assert result.timestamp == timestamp
        assert result.details == {"cpu": 25.0}


class TestHealthConfig:
    """Test health configuration."""

    def test_default_config(self):
        """Test default configuration values."""
        config = HealthConfig()

        assert config.enabled is True
        assert config.check_interval == 30.0
        assert config.timeout_seconds == 10.0
        assert config.critical_checks == []
        assert config.warning_checks == []
        assert config.endpoint_path == "/health"
        assert config.detailed_endpoint_path == "/health/detailed"

    def test_custom_config(self):
        """Test custom configuration."""
        config = HealthConfig(
            enabled=False,
            check_interval=60.0,
            timeout_seconds=5.0,
            critical_checks=["database"],
            warning_checks=["cache"],
        )

        assert config.enabled is False
        assert config.check_interval == 60.0
        assert config.timeout_seconds == 5.0
        assert config.critical_checks == ["database"]
        assert config.warning_checks == ["cache"]


class TestHealthChecker:
    """Test health checker functionality."""

    @pytest.fixture
    def health_checker(self):
        """Create health checker for testing."""
        config = HealthConfig(
            enabled=True,
            check_interval=0.1,  # Fast for testing
            timeout_seconds=1.0,
        )
        return HealthChecker(config)

    def test_initialization(self, health_checker):
        """Test health checker initialization."""
        assert health_checker.config.enabled is True
        assert len(health_checker._checks) > 0  # Built-in checks
        assert health_checker._results == {}
        assert health_checker._checking is False

    def test_register_check(self, health_checker):
        """Test registering custom health check."""

        async def custom_check():
            return True

        health_checker.register_check("custom_test", custom_check)
        assert "custom_test" in health_checker._checks
        assert health_checker._checks["custom_test"] == custom_check

    def test_unregister_check(self, health_checker):
        """Test unregistering health check."""

        async def custom_check():
            return True

        health_checker.register_check("custom_test", custom_check)
        assert "custom_test" in health_checker._checks

        success = health_checker.unregister_check("custom_test")
        assert success is True
        assert "custom_test" not in health_checker._checks

    def test_unregister_nonexistent_check(self, health_checker):
        """Test unregistering non-existent check."""
        success = health_checker.unregister_check("nonexistent")
        assert success is False

    @pytest.mark.asyncio
    async def test_start_stop_monitoring(self, health_checker):
        """Test starting and stopping health monitoring."""
        assert not health_checker._checking

        await health_checker.start_monitoring()
        assert health_checker._checking is True
        assert health_checker._check_task is not None

        await asyncio.sleep(0.2)  # Let it run briefly

        await health_checker.stop_monitoring()
        assert health_checker._checking is False

    @pytest.mark.asyncio
    async def test_monitoring_disabled(self):
        """Test that monitoring doesn't start when disabled."""
        config = HealthConfig(enabled=False)
        health_checker = HealthChecker(config)

        await health_checker.start_monitoring()
        assert not health_checker._checking

    @pytest.mark.asyncio
    async def test_run_all_checks(self, health_checker):
        """Test running all health checks."""

        # Add a simple test check
        async def test_check():
            return HealthCheckResult(
                name="test",
                status=HealthStatus.HEALTHY,
                message="Test OK",
                duration_ms=10.0,
                timestamp=datetime.now(timezone.utc),
            )

        health_checker.register_check("test", test_check)

        results = await health_checker.run_all_checks()

        assert "test" in results
        assert results["test"].status == HealthStatus.HEALTHY
        assert results["test"].message == "Test OK"

    @pytest.mark.asyncio
    async def test_run_check_with_boolean_return(self, health_checker):
        """Test running check that returns boolean."""

        async def bool_check():
            return True

        health_checker.register_check("bool_test", bool_check)

        results = await health_checker.run_all_checks()

        assert "bool_test" in results
        assert results["bool_test"].status == HealthStatus.HEALTHY
        assert results["bool_test"].message == "OK"

    @pytest.mark.asyncio
    async def test_run_check_with_string_return(self, health_checker):
        """Test running check that returns string."""

        async def string_check():
            return "Custom status message"

        health_checker.register_check("string_test", string_check)

        results = await health_checker.run_all_checks()

        assert "string_test" in results
        assert results["string_test"].status == HealthStatus.HEALTHY
        assert results["string_test"].message == "Custom status message"

    @pytest.mark.asyncio
    async def test_check_timeout(self, health_checker):
        """Test check timeout handling."""

        async def slow_check():
            await asyncio.sleep(2.0)  # Longer than timeout
            return True

        health_checker.register_check("slow_test", slow_check)

        results = await health_checker.run_all_checks()

        assert "slow_test" in results
        assert results["slow_test"].status == HealthStatus.UNHEALTHY
        assert "timed out" in results["slow_test"].message

    @pytest.mark.asyncio
    async def test_check_exception(self, health_checker):
        """Test check exception handling."""

        async def failing_check():
            raise Exception("Test failure")

        health_checker.register_check("failing_test", failing_check)

        results = await health_checker.run_all_checks()

        assert "failing_test" in results
        assert results["failing_test"].status == HealthStatus.UNHEALTHY
        assert "Check failed: Test failure" in results["failing_test"].message

    @pytest.mark.asyncio
    async def test_system_resources_check(self, health_checker):
        """Test built-in system resources check."""
        with patch("psutil.cpu_percent", return_value=50.0):
            with patch("psutil.virtual_memory") as mock_memory:
                mock_memory.return_value.percent = 60.0
                mock_memory.return_value.available = 4 * 1024**3

                result = await health_checker._check_system_resources()

                assert result.name == "system_resources"
                assert result.status == HealthStatus.HEALTHY
                assert "50.0%" in result.message
                assert "60.0%" in result.message

    @pytest.mark.asyncio
    async def test_system_resources_check_high_usage(self, health_checker):
        """Test system resources check with high usage."""
        with patch("psutil.cpu_percent", return_value=95.0):
            with patch("psutil.virtual_memory") as mock_memory:
                mock_memory.return_value.percent = 95.0
                mock_memory.return_value.available = 0.5 * 1024**3

                result = await health_checker._check_system_resources()

                assert result.status == HealthStatus.UNHEALTHY
                assert "High resource usage" in result.message

    @pytest.mark.asyncio
    async def test_system_resources_check_no_psutil(self, health_checker):
        """Test system resources check without psutil."""
        with patch("psutil.cpu_percent", side_effect=ImportError()):
            result = await health_checker._check_system_resources()

            assert result.status == HealthStatus.UNKNOWN
            assert "psutil not available" in result.message

    @pytest.mark.asyncio
    async def test_database_check_success(self, health_checker):
        """Test database connection check success."""
        with patch("src.database.service.DatabaseService") as mock_db_service:
            mock_session = MagicMock()
            mock_session.execute.return_value.fetchone.return_value = [1]
            mock_db_service.return_value.get_session.return_value.__enter__ = MagicMock(
                return_value=mock_session
            )
            mock_db_service.return_value.get_session.return_value.__exit__ = MagicMock(
                return_value=None
            )

            result = await health_checker._check_database()

            assert result.status == HealthStatus.HEALTHY
            assert "connection successful" in result.message

    @pytest.mark.asyncio
    async def test_database_check_failure(self, health_checker):
        """Test database connection check failure."""
        with patch("src.database.service.DatabaseService") as mock_db_service:
            mock_db_service.return_value.get_session.side_effect = Exception("Connection failed")

            result = await health_checker._check_database()

            assert result.status == HealthStatus.UNHEALTHY
            assert "Connection failed" in result.message

    @pytest.mark.asyncio
    async def test_cache_check_success(self, health_checker):
        """Test cache backend check success."""
        with patch("src.caching.manager.cache_manager") as mock_cache:
            with patch("time.time", return_value=123456789):
                mock_entry = MagicMock()
                mock_entry.value = "test_123456789"
                mock_cache.initialize = AsyncMock()
                mock_cache.backend.set = AsyncMock(return_value=True)
                mock_cache.backend.get = AsyncMock(return_value=mock_entry)
                mock_cache.backend.delete = AsyncMock(return_value=True)
                mock_cache.config.backend.value = "file"

                result = await health_checker._check_cache()

                assert result.status == HealthStatus.HEALTHY
                assert "operational" in result.message

    @pytest.mark.asyncio
    async def test_cache_check_failure(self, health_checker):
        """Test cache backend check failure."""
        with patch("src.caching.manager.cache_manager") as mock_cache:
            mock_cache.initialize = AsyncMock(side_effect=Exception("Cache error"))

            result = await health_checker._check_cache()

            assert result.status == HealthStatus.UNHEALTHY
            assert "Cache error" in result.message

    @pytest.mark.asyncio
    async def test_disk_space_check_healthy(self, health_checker):
        """Test disk space check with healthy space."""
        with patch("psutil.disk_usage") as mock_disk:
            mock_disk.return_value.total = 100 * 1024**3  # 100GB
            mock_disk.return_value.free = 50 * 1024**3  # 50GB free (50%)

            result = await health_checker._check_disk_space()

            assert result.status == HealthStatus.HEALTHY
            assert "50.0%" in result.message

    @pytest.mark.asyncio
    async def test_disk_space_check_low(self, health_checker):
        """Test disk space check with low space."""
        with patch("psutil.disk_usage") as mock_disk:
            mock_disk.return_value.total = 100 * 1024**3  # 100GB
            mock_disk.return_value.free = 3 * 1024**3  # 3GB free (3%)

            result = await health_checker._check_disk_space()

            assert result.status == HealthStatus.UNHEALTHY
            assert "Critical" in result.message

    @pytest.mark.asyncio
    async def test_memory_usage_check_healthy(self, health_checker):
        """Test memory usage check with healthy usage."""
        with patch("psutil.virtual_memory") as mock_memory:
            mock_memory.return_value.percent = 60.0
            mock_memory.return_value.available = 4 * 1024**3
            mock_memory.return_value.total = 8 * 1024**3

            result = await health_checker._check_memory_usage()

            assert result.status == HealthStatus.HEALTHY
            assert "60.0%" in result.message

    @pytest.mark.asyncio
    async def test_memory_usage_check_critical(self, health_checker):
        """Test memory usage check with critical usage."""
        with patch("psutil.virtual_memory") as mock_memory:
            mock_memory.return_value.percent = 97.0
            mock_memory.return_value.available = 0.2 * 1024**3
            mock_memory.return_value.total = 8 * 1024**3

            result = await health_checker._check_memory_usage()

            assert result.status == HealthStatus.UNHEALTHY
            assert "Critical" in result.message

    def test_get_overall_status_healthy(self, health_checker):
        """Test overall status when all checks healthy."""
        health_checker._results = {
            "check1": HealthCheckResult(
                "check1", HealthStatus.HEALTHY, "OK", 10, datetime.now(timezone.utc)
            ),
            "check2": HealthCheckResult(
                "check2", HealthStatus.HEALTHY, "OK", 15, datetime.now(timezone.utc)
            ),
        }

        status = health_checker.get_overall_status()
        assert status == HealthStatus.HEALTHY

    def test_get_overall_status_degraded(self, health_checker):
        """Test overall status when some checks degraded."""
        health_checker._results = {
            "check1": HealthCheckResult(
                "check1", HealthStatus.HEALTHY, "OK", 10, datetime.now(timezone.utc)
            ),
            "check2": HealthCheckResult(
                "check2", HealthStatus.DEGRADED, "Warning", 15, datetime.now(timezone.utc)
            ),
        }

        status = health_checker.get_overall_status()
        assert status == HealthStatus.DEGRADED

    def test_get_overall_status_unhealthy(self, health_checker):
        """Test overall status when some checks unhealthy."""
        health_checker._results = {
            "check1": HealthCheckResult(
                "check1", HealthStatus.HEALTHY, "OK", 10, datetime.now(timezone.utc)
            ),
            "check2": HealthCheckResult(
                "check2", HealthStatus.UNHEALTHY, "Failed", 15, datetime.now(timezone.utc)
            ),
        }

        status = health_checker.get_overall_status()
        assert status == HealthStatus.UNHEALTHY

    def test_get_overall_status_critical_unhealthy(self, health_checker):
        """Test overall status when critical checks unhealthy."""
        health_checker.config.critical_checks = ["critical_check"]
        health_checker._results = {
            "critical_check": HealthCheckResult(
                "critical_check",
                HealthStatus.UNHEALTHY,
                "Critical fail",
                10,
                datetime.now(timezone.utc),
            ),
            "normal_check": HealthCheckResult(
                "normal_check", HealthStatus.HEALTHY, "OK", 15, datetime.now(timezone.utc)
            ),
        }

        status = health_checker.get_overall_status()
        assert status == HealthStatus.UNHEALTHY

    def test_get_overall_status_unknown(self, health_checker):
        """Test overall status when no results."""
        health_checker._results = {}

        status = health_checker.get_overall_status()
        assert status == HealthStatus.UNKNOWN

    def test_get_health_summary(self, health_checker):
        """Test getting health summary."""
        timestamp = datetime.now(timezone.utc)
        health_checker._results = {
            "check1": HealthCheckResult("check1", HealthStatus.HEALTHY, "OK", 10, timestamp),
            "check2": HealthCheckResult("check2", HealthStatus.DEGRADED, "Warning", 15, timestamp),
        }

        summary = health_checker.get_health_summary()

        assert summary["status"] == "degraded"
        assert "timestamp" in summary
        assert len(summary["checks"]) == 2
        assert summary["checks"]["check1"]["status"] == "healthy"
        assert summary["checks"]["check2"]["status"] == "degraded"
        assert summary["summary"]["total_checks"] == 2
        assert summary["summary"]["healthy"] == 1
        assert summary["summary"]["degraded"] == 1

    def test_get_detailed_health(self, health_checker):
        """Test getting detailed health information."""
        timestamp = datetime.now(timezone.utc)
        health_checker._results = {
            "check1": HealthCheckResult(
                "check1", HealthStatus.HEALTHY, "OK", 10, timestamp, {"detail": "value"}
            )
        }

        detailed = health_checker.get_detailed_health()

        assert "checks" in detailed
        assert "check1" in detailed["checks"]
        assert detailed["checks"]["check1"]["details"] == {"detail": "value"}

    @pytest.mark.asyncio
    async def test_shutdown(self, health_checker):
        """Test health checker shutdown."""
        await health_checker.start_monitoring()
        assert health_checker._checking is True

        await health_checker.shutdown()
        assert health_checker._checking is False

    @pytest.mark.asyncio
    async def test_monitoring_loop_error_handling(self, health_checker):
        """Test monitoring loop handles errors gracefully."""
        with patch.object(health_checker, "run_all_checks", side_effect=Exception("Check error")):
            await health_checker.start_monitoring()

            # Let it run briefly to hit the error
            await asyncio.sleep(0.2)

            # Should still be checking despite errors
            assert health_checker._checking is True

            await health_checker.stop_monitoring()

    @pytest.mark.asyncio
    async def test_multiple_start_stop_cycles(self, health_checker):
        """Test multiple start/stop cycles work correctly."""
        # First cycle
        await health_checker.start_monitoring()
        assert health_checker._checking is True
        await health_checker.stop_monitoring()
        assert health_checker._checking is False

        # Second cycle
        await health_checker.start_monitoring()
        assert health_checker._checking is True
        await health_checker.stop_monitoring()
        assert health_checker._checking is False
