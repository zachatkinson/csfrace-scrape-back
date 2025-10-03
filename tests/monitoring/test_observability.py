"""Comprehensive tests for central observability manager - MANDATORY TEST_BUILDING.md compliance.

This module tests the ObservabilityManager with complete coverage:
- ObservabilityConfig initialization and validation
- ObservabilityManager initialization with custom configs
- Component initialization (metrics, health, alerts, performance, tracing)
- Startup health check execution
- Graceful shutdown of all components
- Error handling and recovery
- Performance benchmarks

ALL tests follow MANDATORY TEST_BUILDING.md patterns:
- AAA pattern with explicit comments
- Factory fixtures for DRY principle
- Comprehensive observability scenario testing
- Performance benchmarks with specific thresholds
"""

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.monitoring.observability import (
    ObservabilityConfig,
    ObservabilityManager,
    _initialize_tracer_safe,
    _start_alert_manager_safe,
    _start_health_checker_safe,
    _start_metrics_collector_safe,
)

# ============================================================================
# Test Fixtures - DRY Principle
# ============================================================================


@pytest.fixture
def mock_metrics_collector():
    """Factory for mock metrics collector - DRY principle."""
    collector = MagicMock()
    collector.config = MagicMock(enabled=True)
    collector.start_collection = AsyncMock()
    collector.stop_collection = AsyncMock()
    return collector


@pytest.fixture
def mock_health_checker():
    """Factory for mock health checker - DRY principle."""
    checker = MagicMock()
    checker.config = MagicMock(enabled=True)
    checker.start_monitoring = AsyncMock()
    checker.stop_monitoring = AsyncMock()
    checker.run_all_checks = AsyncMock(return_value={})
    checker.get_overall_status = MagicMock()
    return checker


@pytest.fixture
def mock_alert_manager():
    """Factory for mock alert manager - DRY principle."""
    manager = MagicMock()
    manager.config = MagicMock(enabled=True)
    manager.start_evaluation = AsyncMock()
    manager.stop_evaluation = AsyncMock()
    return manager


@pytest.fixture
def mock_performance_monitor():
    """Factory for mock performance monitor - DRY principle."""
    monitor = MagicMock()
    monitor.config = MagicMock(enabled=True)
    return monitor


@pytest.fixture
def mock_distributed_tracer():
    """Factory for mock distributed tracer - DRY principle."""
    tracer = MagicMock()
    tracer.config = MagicMock(enabled=True)
    tracer.initialize = MagicMock()
    return tracer


@pytest.fixture
def observability_config():
    """Factory for observability configuration - DRY principle."""
    return ObservabilityConfig(
        enabled=True,
        startup_health_check=True,
        graceful_shutdown_timeout=30.0,
        enable_correlation_ids=True,
        correlation_header_name="X-Correlation-ID",
    )


# ============================================================================
# ObservabilityConfig Tests
# ============================================================================


@pytest.mark.unit
class TestObservabilityConfig:
    """Tests for ObservabilityConfig dataclass."""

    def test_observability_config_default_values(self):
        """Test ObservabilityConfig default values - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # No explicit arrangement needed

        # Act - MANDATORY
        config = ObservabilityConfig()

        # Assert - MANDATORY
        assert config.enabled is True
        assert config.startup_health_check is True
        assert config.graceful_shutdown_timeout == 30.0
        assert config.enable_correlation_ids is True
        assert config.correlation_header_name == "X-Correlation-ID"

    def test_observability_config_custom_values(self):
        """Test ObservabilityConfig with custom values - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        custom_timeout = 60.0
        custom_header = "X-Custom-Correlation"

        # Act - MANDATORY
        config = ObservabilityConfig(
            enabled=False,
            startup_health_check=False,
            graceful_shutdown_timeout=custom_timeout,
            correlation_header_name=custom_header,
        )

        # Assert - MANDATORY
        assert config.enabled is False
        assert config.startup_health_check is False
        assert config.graceful_shutdown_timeout == 60.0
        assert config.correlation_header_name == custom_header

    def test_observability_config_with_component_configs(self):
        """Test ObservabilityConfig with component configs - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        metrics_config = MagicMock()
        health_config = MagicMock()

        # Act - MANDATORY
        config = ObservabilityConfig(metrics_config=metrics_config, health_config=health_config)

        # Assert - MANDATORY
        assert config.metrics_config is metrics_config
        assert config.health_config is health_config


# ============================================================================
# ObservabilityManager Initialization Tests
# ============================================================================


@pytest.mark.unit
class TestObservabilityManagerInit:
    """Tests for ObservabilityManager initialization."""

    @patch("src.monitoring.observability.metrics_collector")
    @patch("src.monitoring.observability.health_checker")
    @patch("src.monitoring.observability.alert_manager")
    @patch("src.monitoring.observability.performance_monitor")
    @patch("src.monitoring.observability.distributed_tracer")
    def test_observability_manager_init_default_config(
        self,
        mock_tracer,
        mock_perf,
        mock_alerts,
        mock_health,
        mock_metrics,
    ):
        """Test ObservabilityManager init with default config - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # Mocks already arranged

        # Act - MANDATORY
        manager = ObservabilityManager()

        # Assert - MANDATORY
        assert manager.config.enabled is True
        assert manager._initialized is False
        assert manager.metrics_collector is mock_metrics
        assert manager.health_checker is mock_health
        assert manager.alert_manager is mock_alerts

    @patch("src.monitoring.observability.metrics_collector")
    @patch("src.monitoring.observability.health_checker")
    @patch("src.monitoring.observability.alert_manager")
    @patch("src.monitoring.observability.performance_monitor")
    @patch("src.monitoring.observability.distributed_tracer")
    def test_observability_manager_init_custom_config(
        self,
        mock_tracer,
        mock_perf,
        mock_alerts,
        mock_health,
        mock_metrics,
        observability_config,
    ):
        """Test ObservabilityManager init with custom config - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # Config from fixture

        # Act - MANDATORY
        manager = ObservabilityManager(observability_config)

        # Assert - MANDATORY
        assert manager.config is observability_config
        assert manager.config.enabled is True
        assert manager.config.startup_health_check is True


# ============================================================================
# ObservabilityManager Initialize Tests
# ============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
class TestObservabilityManagerInitialize:
    """Tests for ObservabilityManager.initialize() method."""

    @patch("src.monitoring.observability.metrics_collector")
    @patch("src.monitoring.observability.health_checker")
    @patch("src.monitoring.observability.alert_manager")
    @patch("src.monitoring.observability.performance_monitor")
    @patch("src.monitoring.observability.distributed_tracer")
    async def test_initialize_all_components_enabled(
        self,
        mock_tracer,
        mock_perf,
        mock_alerts,
        mock_health,
        mock_metrics,
    ):
        """Test initialize with all components enabled - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        mock_metrics.config = MagicMock(enabled=True)
        mock_health.config = MagicMock(enabled=True)
        mock_alerts.config = MagicMock(enabled=True)
        mock_tracer.config = MagicMock(enabled=True)

        mock_metrics.start_collection = AsyncMock()
        mock_health.start_monitoring = AsyncMock()
        mock_health.run_all_checks = AsyncMock(return_value={})
        mock_health.get_overall_status = MagicMock()
        mock_health.get_overall_status.return_value = MagicMock(value="healthy")
        mock_alerts.start_evaluation = AsyncMock()
        mock_tracer.initialize = MagicMock()

        manager = ObservabilityManager()

        # Act - MANDATORY
        await manager.initialize()

        # Assert - MANDATORY
        assert manager._initialized is True
        mock_metrics.start_collection.assert_called_once()
        mock_health.start_monitoring.assert_called_once()
        mock_alerts.start_evaluation.assert_called_once()
        mock_tracer.initialize.assert_called_once()

    @patch("src.monitoring.observability.metrics_collector")
    @patch("src.monitoring.observability.health_checker")
    @patch("src.monitoring.observability.alert_manager")
    @patch("src.monitoring.observability.performance_monitor")
    @patch("src.monitoring.observability.distributed_tracer")
    async def test_initialize_with_disabled_observability(
        self,
        mock_tracer,
        mock_perf,
        mock_alerts,
        mock_health,
        mock_metrics,
    ):
        """Test initialize with disabled observability - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        disabled_config = ObservabilityConfig(enabled=False)
        manager = ObservabilityManager(disabled_config)

        # Act - MANDATORY
        await manager.initialize()

        # Assert - MANDATORY
        assert manager._initialized is False

    @patch("src.monitoring.observability.metrics_collector")
    @patch("src.monitoring.observability.health_checker")
    @patch("src.monitoring.observability.alert_manager")
    @patch("src.monitoring.observability.performance_monitor")
    @patch("src.monitoring.observability.distributed_tracer")
    async def test_initialize_idempotent(
        self,
        mock_tracer,
        mock_perf,
        mock_alerts,
        mock_health,
        mock_metrics,
    ):
        """Test initialize is idempotent - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        mock_metrics.config = MagicMock(enabled=True)
        mock_health.config = MagicMock(enabled=True)
        mock_alerts.config = MagicMock(enabled=True)
        mock_tracer.config = MagicMock(enabled=True)

        mock_metrics.start_collection = AsyncMock()
        mock_health.start_monitoring = AsyncMock()
        mock_health.run_all_checks = AsyncMock(return_value={})
        mock_health.get_overall_status = MagicMock()
        mock_health.get_overall_status.return_value = MagicMock(value="healthy")
        mock_alerts.start_evaluation = AsyncMock()
        mock_tracer.initialize = MagicMock()

        manager = ObservabilityManager()

        # Act - MANDATORY
        await manager.initialize()
        await manager.initialize()  # Second call

        # Assert - MANDATORY
        assert manager._initialized is True
        # Should only be called once despite two initialize() calls
        assert mock_metrics.start_collection.call_count == 1


# ============================================================================
# Startup Health Check Tests
# ============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
class TestStartupHealthCheck:
    """Tests for startup health check functionality."""

    @patch("src.monitoring.observability.metrics_collector")
    @patch("src.monitoring.observability.health_checker")
    @patch("src.monitoring.observability.alert_manager")
    @patch("src.monitoring.observability.performance_monitor")
    @patch("src.monitoring.observability.distributed_tracer")
    async def test_startup_health_check_healthy_status(
        self,
        mock_tracer,
        mock_perf,
        mock_alerts,
        mock_health,
        mock_metrics,
    ):
        """Test startup health check with healthy status - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        mock_metrics.config = MagicMock(enabled=True)
        mock_health.config = MagicMock(enabled=True)
        mock_alerts.config = MagicMock(enabled=True)
        mock_tracer.config = MagicMock(enabled=True)

        mock_metrics.start_collection = AsyncMock()
        mock_health.start_monitoring = AsyncMock()
        mock_health.run_all_checks = AsyncMock(return_value={"check1": MagicMock()})
        mock_health.get_overall_status = MagicMock()
        mock_health.get_overall_status.return_value = MagicMock(value="healthy")
        mock_alerts.start_evaluation = AsyncMock()
        mock_tracer.initialize = MagicMock()

        manager = ObservabilityManager()

        # Act - MANDATORY
        await manager.initialize()

        # Assert - MANDATORY
        mock_health.run_all_checks.assert_called_once()
        mock_health.get_overall_status.assert_called_once()


# ============================================================================
# Shutdown Tests
# ============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
class TestObservabilityManagerShutdown:
    """Tests for ObservabilityManager.shutdown() method."""

    @patch("src.monitoring.observability.metrics_collector")
    @patch("src.monitoring.observability.health_checker")
    @patch("src.monitoring.observability.alert_manager")
    @patch("src.monitoring.observability.performance_monitor")
    @patch("src.monitoring.observability.distributed_tracer")
    async def test_shutdown_all_components(
        self,
        mock_tracer,
        mock_perf,
        mock_alerts,
        mock_health,
        mock_metrics,
    ):
        """Test shutdown stops all components - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        mock_metrics.config = MagicMock(enabled=True)
        mock_health.config = MagicMock(enabled=True)
        mock_alerts.config = MagicMock(enabled=True)
        mock_tracer.config = MagicMock(enabled=True)

        mock_metrics.start_collection = AsyncMock()
        mock_metrics.stop_collection = AsyncMock()
        mock_health.start_monitoring = AsyncMock()
        mock_health.stop_monitoring = AsyncMock()
        mock_health.run_all_checks = AsyncMock(return_value={})
        mock_health.get_overall_status = MagicMock()
        mock_health.get_overall_status.return_value = MagicMock(value="healthy")
        mock_alerts.start_evaluation = AsyncMock()
        mock_alerts.stop_evaluation = AsyncMock()
        mock_tracer.initialize = MagicMock()

        manager = ObservabilityManager()
        await manager.initialize()

        # Act - MANDATORY
        await manager.shutdown()

        # Assert - MANDATORY
        assert manager._initialized is False
        mock_metrics.stop_collection.assert_called_once()
        mock_health.stop_monitoring.assert_called_once()
        mock_alerts.stop_evaluation.assert_called_once()

    @patch("src.monitoring.observability.metrics_collector")
    @patch("src.monitoring.observability.health_checker")
    @patch("src.monitoring.observability.alert_manager")
    @patch("src.monitoring.observability.performance_monitor")
    @patch("src.monitoring.observability.distributed_tracer")
    async def test_shutdown_handles_component_errors(
        self,
        mock_tracer,
        mock_perf,
        mock_alerts,
        mock_health,
        mock_metrics,
    ):
        """Test shutdown handles component errors gracefully - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        mock_metrics.config = MagicMock(enabled=True)
        mock_health.config = MagicMock(enabled=True)
        mock_alerts.config = MagicMock(enabled=True)
        mock_tracer.config = MagicMock(enabled=True)

        mock_metrics.start_collection = AsyncMock()
        mock_metrics.stop_collection = AsyncMock(side_effect=Exception("Metrics error"))
        mock_health.start_monitoring = AsyncMock()
        mock_health.stop_monitoring = AsyncMock(side_effect=Exception("Health error"))
        mock_health.run_all_checks = AsyncMock(return_value={})
        mock_health.get_overall_status = MagicMock()
        mock_health.get_overall_status.return_value = MagicMock(value="healthy")
        mock_alerts.start_evaluation = AsyncMock()
        mock_alerts.stop_evaluation = AsyncMock(side_effect=Exception("Alerts error"))
        mock_tracer.initialize = MagicMock()

        manager = ObservabilityManager()
        await manager.initialize()

        # Act - MANDATORY
        # Should not raise despite component errors
        await manager.shutdown()

        # Assert - MANDATORY
        assert manager._initialized is False


# ============================================================================
# Safe Helper Function Tests
# ============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
class TestSafeHelperFunctions:
    """Tests for safe helper functions."""

    async def test_start_metrics_collector_safe(self, mock_metrics_collector):
        """Test _start_metrics_collector_safe - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # Mock from fixture

        # Act - MANDATORY
        await _start_metrics_collector_safe(mock_metrics_collector)

        # Assert - MANDATORY
        mock_metrics_collector.start_collection.assert_called_once()

    async def test_start_health_checker_safe(self, mock_health_checker):
        """Test _start_health_checker_safe - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # Mock from fixture

        # Act - MANDATORY
        await _start_health_checker_safe(mock_health_checker)

        # Assert - MANDATORY
        mock_health_checker.start_monitoring.assert_called_once()

    async def test_start_alert_manager_safe(self, mock_alert_manager):
        """Test _start_alert_manager_safe - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # Mock from fixture

        # Act - MANDATORY
        await _start_alert_manager_safe(mock_alert_manager)

        # Assert - MANDATORY
        mock_alert_manager.start_evaluation.assert_called_once()

    async def test_initialize_tracer_safe(self, mock_distributed_tracer):
        """Test _initialize_tracer_safe - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # Mock from fixture

        # Act - MANDATORY
        await _initialize_tracer_safe(mock_distributed_tracer)

        # Assert - MANDATORY
        mock_distributed_tracer.initialize.assert_called_once()


# ============================================================================
# MANDATORY Performance Benchmarks
# ============================================================================


@pytest.mark.performance
@pytest.mark.unit
@pytest.mark.asyncio
class TestObservabilityManagerPerformance:
    """MANDATORY performance tests for ObservabilityManager."""

    @patch("src.monitoring.observability.metrics_collector")
    @patch("src.monitoring.observability.health_checker")
    @patch("src.monitoring.observability.alert_manager")
    @patch("src.monitoring.observability.performance_monitor")
    @patch("src.monitoring.observability.distributed_tracer")
    async def test_initialization_performance(
        self,
        mock_tracer,
        mock_perf,
        mock_alerts,
        mock_health,
        mock_metrics,
    ):
        """MANDATORY performance test - manager initialization speed."""
        # Arrange - MANDATORY
        mock_metrics.config = MagicMock(enabled=True)
        mock_health.config = MagicMock(enabled=True)
        mock_alerts.config = MagicMock(enabled=True)
        mock_tracer.config = MagicMock(enabled=True)

        mock_metrics.start_collection = AsyncMock()
        mock_health.start_monitoring = AsyncMock()
        mock_health.run_all_checks = AsyncMock(return_value={})
        mock_health.get_overall_status = MagicMock()
        mock_health.get_overall_status.return_value = MagicMock(value="healthy")
        mock_alerts.start_evaluation = AsyncMock()
        mock_tracer.initialize = MagicMock()

        manager = ObservabilityManager()

        # Act - MANDATORY
        start_time = time.perf_counter()
        await manager.initialize()
        end_time = time.perf_counter()
        execution_time = end_time - start_time

        # Assert - MANDATORY
        assert execution_time < 1.0  # <1s initialization
        assert manager._initialized is True

    @patch("src.monitoring.observability.metrics_collector")
    @patch("src.monitoring.observability.health_checker")
    @patch("src.monitoring.observability.alert_manager")
    @patch("src.monitoring.observability.performance_monitor")
    @patch("src.monitoring.observability.distributed_tracer")
    async def test_shutdown_performance(
        self,
        mock_tracer,
        mock_perf,
        mock_alerts,
        mock_health,
        mock_metrics,
    ):
        """MANDATORY performance test - graceful shutdown speed."""
        # Arrange - MANDATORY
        mock_metrics.config = MagicMock(enabled=True)
        mock_health.config = MagicMock(enabled=True)
        mock_alerts.config = MagicMock(enabled=True)
        mock_tracer.config = MagicMock(enabled=True)

        mock_metrics.start_collection = AsyncMock()
        mock_metrics.stop_collection = AsyncMock()
        mock_health.start_monitoring = AsyncMock()
        mock_health.stop_monitoring = AsyncMock()
        mock_health.run_all_checks = AsyncMock(return_value={})
        mock_health.get_overall_status = MagicMock()
        mock_health.get_overall_status.return_value = MagicMock(value="healthy")
        mock_alerts.start_evaluation = AsyncMock()
        mock_alerts.stop_evaluation = AsyncMock()
        mock_tracer.initialize = MagicMock()

        manager = ObservabilityManager()
        await manager.initialize()

        # Act - MANDATORY
        start_time = time.perf_counter()
        await manager.shutdown()
        end_time = time.perf_counter()
        execution_time = end_time - start_time

        # Assert - MANDATORY
        assert execution_time < 5.0  # <5s shutdown
        assert manager._initialized is False
