"""Tests for central observability manager."""
# pylint: disable=protected-access,too-many-public-methods

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from src.monitoring.alerts import AlertConfig
from src.monitoring.health import HealthConfig
from src.monitoring.metrics import MetricsConfig
from src.monitoring.observability import (
    ObservabilityConfig,
    ObservabilityManager,
    observability_manager,
)
from src.monitoring.performance import PerformanceConfig


class TestObservabilityConfig:
    """Test observability configuration."""

    def test_default_config(self):
        """Test default configuration values."""
        config = ObservabilityConfig()

        assert config.enabled is True
        assert config.metrics_config is None
        assert config.health_config is None
        assert config.alerts_config is None
        assert config.performance_config is None
        assert config.startup_health_check is True
        assert config.graceful_shutdown_timeout == 30.0
        assert config.enable_correlation_ids is True
        assert config.correlation_header_name == "X-Correlation-ID"

    def test_custom_config(self):
        """Test custom configuration with component configs."""
        metrics_config = MetricsConfig(enabled=False)
        health_config = HealthConfig(enabled=False)
        alerts_config = AlertConfig(enabled=False)
        performance_config = PerformanceConfig(enabled=False)

        config = ObservabilityConfig(
            enabled=False,
            metrics_config=metrics_config,
            health_config=health_config,
            alerts_config=alerts_config,
            performance_config=performance_config,
            startup_health_check=False,
            graceful_shutdown_timeout=60.0,
            enable_correlation_ids=False,
            correlation_header_name="X-Request-ID",
        )

        assert config.enabled is False
        assert config.metrics_config == metrics_config
        assert config.health_config == health_config
        assert config.alerts_config == alerts_config
        assert config.performance_config == performance_config
        assert config.startup_health_check is False
        assert config.graceful_shutdown_timeout == 60.0
        assert config.enable_correlation_ids is False
        assert config.correlation_header_name == "X-Request-ID"


class TestObservabilityManager:
    """Test observability manager functionality."""

    @pytest.fixture
    def config(self):
        """Create test configuration."""
        return ObservabilityConfig(
            enabled=True,
            startup_health_check=False,  # Disable for testing
            graceful_shutdown_timeout=5.0,  # Shorter for testing
        )

    @pytest.fixture
    def manager(self, config):
        """Create observability manager for testing."""
        return ObservabilityManager(config)

    @pytest.fixture
    def disabled_manager(self):
        """Create disabled observability manager."""
        config = ObservabilityConfig(enabled=False)
        return ObservabilityManager(config)

    def test_initialization_default_config(self):
        """Test initialization with default configuration."""
        manager = ObservabilityManager()

        assert manager.config.enabled is True
        assert manager._initialized is False
        assert manager.metrics_collector is not None
        assert manager.health_checker is not None
        assert manager.alert_manager is not None
        assert manager.performance_monitor is not None

    def test_initialization_custom_config(self, config, manager):
        """Test initialization with custom configuration."""
        assert manager.config == config
        assert manager._initialized is False

    def test_initialization_with_component_configs(self):
        """Test initialization with individual component configs."""
        metrics_config = MetricsConfig(collection_interval=60.0)
        health_config = HealthConfig(check_interval=120.0)
        alerts_config = AlertConfig(evaluation_interval=90.0)
        performance_config = PerformanceConfig(max_trace_history=2000)

        config = ObservabilityConfig(
            metrics_config=metrics_config,
            health_config=health_config,
            alerts_config=alerts_config,
            performance_config=performance_config,
        )

        manager = ObservabilityManager(config)

        assert manager.metrics_collector.config == metrics_config
        assert manager.health_checker.config == health_config
        assert manager.alert_manager.config == alerts_config
        assert manager.performance_monitor.config == performance_config

    @pytest.mark.asyncio
    async def test_initialize_all_components(self, manager):
        """Test initializing all components."""
        with patch.object(manager.metrics_collector, "start_collection") as mock_metrics:
            with patch.object(manager.health_checker, "start_monitoring") as mock_health:
                with patch.object(manager.alert_manager, "start_evaluation") as mock_alerts:
                    await manager.initialize()

                    assert manager._initialized is True
                    mock_metrics.assert_called_once()
                    mock_health.assert_called_once()
                    mock_alerts.assert_called_once()

    @pytest.mark.asyncio
    async def test_initialize_disabled(self, disabled_manager):
        """Test initialization when disabled."""
        await disabled_manager.initialize()
        assert disabled_manager._initialized is False

    @pytest.mark.asyncio
    async def test_initialize_already_initialized(self, manager):
        """Test initialization when already initialized."""
        manager._initialized = True

        with patch.object(manager.metrics_collector, "start_collection") as mock_metrics:
            await manager.initialize()
            mock_metrics.assert_not_called()

    @pytest.mark.asyncio
    async def test_initialize_with_startup_health_check(self):
        """Test initialization with startup health check."""
        config = ObservabilityConfig(startup_health_check=True)
        manager = ObservabilityManager(config)

        with patch.object(manager, "_run_startup_health_check") as mock_health_check:
            with patch.object(manager.metrics_collector, "start_collection"):
                with patch.object(manager.health_checker, "start_monitoring"):
                    with patch.object(manager.alert_manager, "start_evaluation"):
                        await manager.initialize()
                        mock_health_check.assert_called_once()

    @pytest.mark.asyncio
    async def test_initialize_failure_cleanup(self, manager):
        """Test initialization failure triggers cleanup."""
        with patch.object(
            manager.metrics_collector, "start_collection", side_effect=Exception("Init failed")
        ):
            with patch.object(manager, "shutdown") as mock_shutdown:
                with pytest.raises(Exception, match="Init failed"):
                    await manager.initialize()
                mock_shutdown.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_startup_health_check_healthy(self, manager):
        """Test startup health check with healthy status."""
        mock_results = {
            "system": MagicMock(status=MagicMock(value="healthy")),
            "database": MagicMock(status=MagicMock(value="healthy")),
        }

        with patch.object(manager.health_checker, "run_all_checks", return_value=mock_results):
            with patch.object(
                manager.health_checker,
                "get_overall_status",
                return_value=MagicMock(value="healthy"),
            ):
                # Should not raise exception
                await manager._run_startup_health_check()

    @pytest.mark.asyncio
    async def test_run_startup_health_check_degraded(self, manager):
        """Test startup health check with degraded status."""
        mock_results = {
            "system": MagicMock(status=MagicMock(value="healthy")),
            "database": MagicMock(status=MagicMock(value="degraded")),
        }

        with patch.object(manager.health_checker, "run_all_checks", return_value=mock_results):
            with patch.object(
                manager.health_checker,
                "get_overall_status",
                return_value=MagicMock(value="degraded"),
            ):
                # Should not raise exception but log warning
                await manager._run_startup_health_check()

    @pytest.mark.asyncio
    async def test_run_startup_health_check_unhealthy(self, manager):
        """Test startup health check with unhealthy status."""
        mock_results = {
            "system": MagicMock(status=MagicMock(value="unhealthy"), message="System overloaded"),
            "database": MagicMock(status=MagicMock(value="unknown"), message="Connection failed"),
        }

        with patch.object(manager.health_checker, "run_all_checks", return_value=mock_results):
            with patch.object(
                manager.health_checker,
                "get_overall_status",
                return_value=MagicMock(value="unhealthy"),
            ):
                # Should not raise exception but log errors
                await manager._run_startup_health_check()

    @pytest.mark.asyncio
    async def test_run_startup_health_check_exception(self, manager):
        """Test startup health check with exception."""
        with patch.object(
            manager.health_checker, "run_all_checks", side_effect=Exception("Health check failed")
        ):
            # Should not raise exception but log error
            await manager._run_startup_health_check()

    @pytest.mark.asyncio
    async def test_shutdown_all_components(self, manager):
        """Test shutting down all components."""
        manager._initialized = True

        with patch.object(manager.alert_manager, "shutdown") as mock_alerts:
            with patch.object(manager.health_checker, "shutdown") as mock_health:
                with patch.object(manager.metrics_collector, "shutdown") as mock_metrics:
                    with patch.object(manager.performance_monitor, "shutdown") as mock_perf:
                        await manager.shutdown()

                        assert manager._initialized is False
                        mock_alerts.assert_called_once()
                        mock_health.assert_called_once()
                        mock_metrics.assert_called_once()
                        mock_perf.assert_called_once()

    @pytest.mark.asyncio
    async def test_shutdown_not_initialized(self, manager):
        """Test shutdown when not initialized."""
        assert manager._initialized is False

        with patch.object(manager.metrics_collector, "shutdown") as mock_metrics:
            await manager.shutdown()
            mock_metrics.assert_not_called()

    @pytest.mark.asyncio
    async def test_shutdown_with_timeout(self, manager):
        """Test shutdown with timeout."""
        manager._initialized = True
        manager.config.graceful_shutdown_timeout = 0.1

        # Mock slow shutdown
        async def slow_shutdown():
            await asyncio.sleep(1.0)

        with patch.object(manager.metrics_collector, "shutdown", side_effect=slow_shutdown):
            # Should complete with timeout warning
            await manager.shutdown()
            assert manager._initialized is False

    @pytest.mark.asyncio
    async def test_shutdown_with_exception(self, manager):
        """Test shutdown with component exception."""
        manager._initialized = True

        with patch.object(
            manager.metrics_collector, "shutdown", side_effect=Exception("Shutdown failed")
        ):
            # Should complete despite exception
            await manager.shutdown()
            assert manager._initialized is False

    def test_get_system_overview_not_initialized(self, manager):
        """Test getting system overview when not initialized."""
        overview = manager.get_system_overview()

        assert "timestamp" in overview
        assert overview["system_status"] == "unknown"
        assert overview["observability_status"]["initialized"] is False

    def test_get_system_overview_initialized(self, manager):
        """Test getting system overview when initialized."""
        manager._initialized = True

        mock_health_summary = {"status": "healthy", "checks": {"system": "healthy"}}

        mock_metrics_snapshot = {
            "timestamp": "2024-01-01T00:00:00Z",
            "system_metrics": {"cpu": 50.0},
        }

        mock_alert_summary = {"total_rules": 5, "active_alerts": 1}

        mock_perf_summary = {"total_traces": 100, "avg_duration": 0.5}

        with patch.object(
            manager.health_checker, "get_health_summary", return_value=mock_health_summary
        ):
            with patch.object(
                manager.metrics_collector,
                "get_metrics_snapshot",
                return_value=mock_metrics_snapshot,
            ):
                with patch.object(
                    manager.alert_manager, "get_alert_summary", return_value=mock_alert_summary
                ):
                    with patch.object(
                        manager.performance_monitor,
                        "get_performance_summary",
                        return_value=mock_perf_summary,
                    ):
                        overview = manager.get_system_overview()

        assert overview["system_status"] == "healthy"
        assert overview["health"] == mock_health_summary
        assert overview["metrics"] == mock_metrics_snapshot
        assert overview["alerts"] == mock_alert_summary
        assert overview["performance"] == mock_perf_summary

    def test_get_system_overview_with_exception(self, manager):
        """Test getting system overview with exception."""
        manager._initialized = True

        with patch.object(
            manager.health_checker,
            "get_health_summary",
            side_effect=Exception("Health summary failed"),
        ):
            overview = manager.get_system_overview()
            assert "error" in overview

    def test_get_component_status(self, manager):
        """Test getting component status."""
        status = manager.get_component_status()

        assert "metrics_collector" in status
        assert "health_checker" in status
        assert "alert_manager" in status
        assert "performance_monitor" in status

        # Check metrics collector status
        metrics_status = status["metrics_collector"]
        assert "enabled" in metrics_status
        assert "collecting" in metrics_status
        assert "prometheus_available" in metrics_status
        assert "active_traces" in metrics_status

    def test_get_component_status_detailed(self, manager):
        """Test getting detailed component status."""
        # Set up some mock data
        manager.metrics_collector._collecting = True
        manager.health_checker._checking = True
        manager.alert_manager._evaluating = True

        status = manager.get_component_status()

        assert status["metrics_collector"]["collecting"] is True
        assert status["health_checker"]["monitoring"] is True
        assert status["alert_manager"]["evaluating"] is True

    @pytest.mark.asyncio
    async def test_run_diagnostic_healthy_system(self, manager):
        """Test running diagnostic on healthy system."""
        manager._initialized = True
        manager.metrics_collector._collecting = True
        manager.metrics_collector.config.enabled = True

        mock_health_results = {
            "system": MagicMock(status=MagicMock(value="healthy")),
            "database": MagicMock(status=MagicMock(value="healthy")),
        }

        with patch.object(
            manager.health_checker, "run_all_checks", return_value=mock_health_results
        ):
            with patch.object(
                manager.health_checker,
                "get_overall_status",
                return_value=MagicMock(value="healthy"),
            ):
                diagnostic = await manager.run_diagnostic()

        assert diagnostic["overall_status"] == "healthy"
        assert len(diagnostic["issues"]) == 0
        assert diagnostic["components"]["metrics_collector"]["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_run_diagnostic_degraded_system(self, manager):
        """Test running diagnostic on degraded system."""
        manager._initialized = True
        manager.metrics_collector._collecting = False  # Problem
        manager.alert_manager._evaluating = False  # Another problem

        # Mock health checker to return healthy status so degraded issues are visible
        mock_health_results = {
            "system": MagicMock(status=MagicMock(value="healthy")),
            "database": MagicMock(status=MagicMock(value="healthy")),
        }

        with patch.object(
            manager.health_checker, "run_all_checks", return_value=mock_health_results
        ):
            with patch.object(
                manager.health_checker,
                "get_overall_status",
                return_value=MagicMock(value="healthy"),
            ):
                diagnostic = await manager.run_diagnostic()

        assert diagnostic["overall_status"] == "degraded"
        assert len(diagnostic["issues"]) > 0
        assert "Metrics collection not running" in diagnostic["issues"]
        assert "Alert evaluation not running" in diagnostic["issues"]

    @pytest.mark.asyncio
    async def test_run_diagnostic_with_unhealthy_checks(self, manager):
        """Test diagnostic with unhealthy health checks."""
        manager._initialized = True

        mock_health_results = {
            "system": MagicMock(status=MagicMock(value="unhealthy")),
            "database": MagicMock(status=MagicMock(value="unknown")),
        }

        with patch.object(
            manager.health_checker, "run_all_checks", return_value=mock_health_results
        ):
            with patch.object(
                manager.health_checker,
                "get_overall_status",
                return_value=MagicMock(value="unhealthy"),
            ):
                diagnostic = await manager.run_diagnostic()

        assert diagnostic["overall_status"] == "unhealthy"
        assert any("Health check failed: system" in issue for issue in diagnostic["issues"])
        assert any("Health check failed: database" in issue for issue in diagnostic["issues"])

    @pytest.mark.asyncio
    async def test_run_diagnostic_with_active_alerts(self, manager):
        """Test diagnostic with active alerts."""
        manager._initialized = True
        manager.alert_manager._evaluating = True
        manager.alert_manager.active_alerts = {"alert1": MagicMock(), "alert2": MagicMock()}

        diagnostic = await manager.run_diagnostic()

        assert diagnostic["components"]["alert_manager"]["status"] == "warning"
        assert any("2 active alerts" in issue for issue in diagnostic["issues"])

    @pytest.mark.asyncio
    async def test_run_diagnostic_with_slow_requests(self, manager):
        """Test diagnostic with many slow requests."""
        manager._initialized = True
        manager.performance_monitor.slow_requests = [MagicMock() for _ in range(15)]

        diagnostic = await manager.run_diagnostic()

        assert diagnostic["components"]["performance_monitor"]["status"] == "warning"
        assert any("High number of slow requests" in issue for issue in diagnostic["issues"])

    @pytest.mark.asyncio
    async def test_run_diagnostic_with_exception(self, manager):
        """Test diagnostic with exception."""
        with patch.object(
            manager.health_checker, "run_all_checks", side_effect=Exception("Diagnostic failed")
        ):
            diagnostic = await manager.run_diagnostic()

            assert diagnostic["overall_status"] == "error"
            assert "error" in diagnostic

    def test_export_metrics_enabled(self, manager):
        """Test exporting metrics when enabled."""
        mock_data = b"# Prometheus metrics\ntest_metric 1.0\n"

        with patch.object(
            manager.metrics_collector, "export_prometheus_metrics", return_value=mock_data
        ):
            result = manager.export_metrics()
            assert result == mock_data

    def test_export_metrics_disabled(self, manager):
        """Test exporting metrics when disabled."""
        manager.metrics_collector.config.enabled = False

        result = manager.export_metrics()
        assert b"Metrics collection disabled" in result

    @pytest.mark.asyncio
    async def test_context_manager(self, manager):
        """Test observability manager as async context manager."""
        async with manager as obs:
            assert obs == manager
            assert manager._initialized is True

        # After exiting context, should be shutdown
        assert manager._initialized is False

    @pytest.mark.asyncio
    async def test_context_manager_with_exception(self, manager):
        """Test context manager handles exceptions."""
        try:
            async with manager:
                assert manager._initialized is True
                raise ValueError("Test exception")
        except ValueError:
            pass

        # Should still be shutdown after exception
        assert manager._initialized is False

    def test_global_observability_manager(self):
        """Test global observability manager instance."""
        assert observability_manager is not None
        assert isinstance(observability_manager, ObservabilityManager)

    @pytest.mark.asyncio
    async def test_multiple_initialize_calls(self, manager):
        """Test multiple initialize calls are safe."""
        await manager.initialize()
        assert manager._initialized is True

        # Second call should be no-op
        await manager.initialize()
        assert manager._initialized is True

    @pytest.mark.asyncio
    async def test_multiple_shutdown_calls(self, manager):
        """Test multiple shutdown calls are safe."""
        manager._initialized = True

        await manager.shutdown()
        assert manager._initialized is False

        # Second call should be no-op
        await manager.shutdown()
        assert manager._initialized is False

    @pytest.mark.asyncio
    async def test_shutdown_event_handling(self, manager):
        """Test shutdown event is set properly."""
        # Initialize manager so shutdown doesn't early return
        manager._initialized = True

        assert not manager._shutdown_event.is_set()

        # Start shutdown as a task but don't complete it yet
        shutdown_task = asyncio.create_task(manager.shutdown())

        # Give it a moment to start and set the event
        await asyncio.sleep(0.01)

        # Event should be set during shutdown
        assert manager._shutdown_event.is_set()

        # Now complete the shutdown
        await shutdown_task
