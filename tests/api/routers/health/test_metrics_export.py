"""Comprehensive tests for metrics export endpoints - MANDATORY TEST_BUILDING.md compliance.

This module tests metrics export functionality with complete coverage:
- Metrics collection endpoint
- Prometheus metrics export endpoint
- Cache status retrieval with error handling
- Performance summary collection
- Error handling scenarios
- Integration with monitoring components

ALL tests follow MANDATORY TEST_BUILDING.md patterns:
- AAA pattern with explicit comments
- Factory fixtures for DRY principle
- Comprehensive error scenario testing
- Performance benchmarks with specific thresholds
"""

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import APIRouter

from src.api.routers.health.metrics_export import (
    _get_cache_backend_type_safe,
    _get_cache_status,
    _get_cache_status_safe,
    _get_performance_summary,
    get_metrics,
    prometheus_metrics,
    router,
)

# ============================================================================
# Test Fixtures - DRY Principle
# ============================================================================


@pytest.fixture
def sample_metrics_snapshot():
    """Factory for sample metrics snapshot - DRY principle."""
    return {
        "system_metrics": {
            "cpu_percent": 45.2,
            "memory_percent": 62.8,
            "disk_usage": 78.5,
        },
        "application_metrics": {
            "requests_total": 1234,
            "requests_success": 1200,
            "requests_failed": 34,
        },
        "database_metrics": {
            "connections": 10,
            "queries_total": 5678,
            "latency_ms": 12.5,
        },
    }


@pytest.fixture
def sample_performance_summary():
    """Factory for sample performance summary - DRY principle."""
    return {
        "avg_response_time": 125.5,
        "p95_response_time": 250.0,
        "p99_response_time": 500.0,
        "throughput": 100.0,
    }


@pytest.fixture
def sample_cache_status():
    """Factory for sample cache status - DRY principle."""
    return {
        "status": "healthy",
        "backend": "redis",
    }


@pytest.fixture
def sample_prometheus_data():
    """Factory for sample Prometheus metrics - DRY principle."""
    return b"""# HELP http_requests_total Total HTTP requests
# TYPE http_requests_total counter
http_requests_total{method="GET",status="200"} 1234
http_requests_total{method="POST",status="201"} 567
"""


# ============================================================================
# Router Configuration Tests
# ============================================================================


@pytest.mark.unit
class TestMetricsExportRouter:
    """Tests for metrics export router configuration."""

    def test_router_exists(self):
        """Test that metrics export router exists - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # Act - MANDATORY
        # Assert - MANDATORY
        assert router is not None
        assert isinstance(router, APIRouter)

    def test_router_has_metrics_endpoint(self):
        """Test router has /metrics endpoint - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # Act - MANDATORY
        routes = [route.path for route in router.routes]

        # Assert - MANDATORY
        assert "/metrics" in routes

    def test_router_has_prometheus_endpoint(self):
        """Test router has /prometheus endpoint - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # Act - MANDATORY
        routes = [route.path for route in router.routes]

        # Assert - MANDATORY
        assert "/prometheus" in routes

    def test_metrics_endpoint_uses_get_method(self):
        """Test metrics endpoint uses GET method - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # Act - MANDATORY
        metrics_route = next(route for route in router.routes if route.path == "/metrics")

        # Assert - MANDATORY
        assert "GET" in metrics_route.methods

    def test_prometheus_endpoint_uses_get_method(self):
        """Test prometheus endpoint uses GET method - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # Act - MANDATORY
        prometheus_route = next(route for route in router.routes if route.path == "/prometheus")

        # Assert - MANDATORY
        assert "GET" in prometheus_route.methods


# ============================================================================
# Get Metrics Endpoint Tests
# ============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
class TestGetMetricsEndpoint:
    """Tests for GET /metrics endpoint."""

    async def test_get_metrics_returns_metrics_response(
        self, sample_metrics_snapshot, sample_performance_summary, sample_cache_status
    ):
        """Test get_metrics returns MetricsResponse - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        mock_collector = MagicMock()
        mock_collector.get_metrics_snapshot.return_value = sample_metrics_snapshot

        with patch("src.api.routers.health.metrics_export.metrics_collector", mock_collector):
            with patch(
                "src.api.routers.health.metrics_export._get_performance_summary",
                return_value=sample_performance_summary,
            ):
                with patch(
                    "src.api.routers.health.metrics_export._get_cache_status",
                    return_value=AsyncMock(return_value=sample_cache_status)(),
                ):
                    # Act - MANDATORY
                    result = await get_metrics()

                    # Assert - MANDATORY
                    assert result is not None
                    assert hasattr(result, "timestamp")
                    assert hasattr(result, "system_metrics")
                    assert hasattr(result, "application_metrics")
                    assert hasattr(result, "database_metrics")

    async def test_get_metrics_calls_metrics_collector(self, sample_metrics_snapshot):
        """Test get_metrics calls metrics_collector - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        mock_collector = MagicMock()
        mock_collector.get_metrics_snapshot.return_value = sample_metrics_snapshot

        with patch("src.api.routers.health.metrics_export.metrics_collector", mock_collector):
            with patch(
                "src.api.routers.health.metrics_export._get_performance_summary", return_value={}
            ):
                with patch(
                    "src.api.routers.health.metrics_export._get_cache_status",
                    return_value=AsyncMock(return_value={})(),
                ):
                    # Act - MANDATORY
                    await get_metrics()

                    # Assert - MANDATORY
                    mock_collector.get_metrics_snapshot.assert_called_once()

    async def test_get_metrics_includes_system_metrics(self, sample_metrics_snapshot):
        """Test get_metrics includes system metrics - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        mock_collector = MagicMock()
        mock_collector.get_metrics_snapshot.return_value = sample_metrics_snapshot

        with patch("src.api.routers.health.metrics_export.metrics_collector", mock_collector):
            with patch(
                "src.api.routers.health.metrics_export._get_performance_summary", return_value={}
            ):
                with patch(
                    "src.api.routers.health.metrics_export._get_cache_status",
                    return_value=AsyncMock(return_value={})(),
                ):
                    # Act - MANDATORY
                    result = await get_metrics()

                    # Assert - MANDATORY
                    assert result.system_metrics == sample_metrics_snapshot["system_metrics"]

    async def test_get_metrics_includes_application_metrics(self, sample_metrics_snapshot):
        """Test get_metrics includes application metrics - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        mock_collector = MagicMock()
        mock_collector.get_metrics_snapshot.return_value = sample_metrics_snapshot

        with patch("src.api.routers.health.metrics_export.metrics_collector", mock_collector):
            with patch(
                "src.api.routers.health.metrics_export._get_performance_summary", return_value={}
            ):
                with patch(
                    "src.api.routers.health.metrics_export._get_cache_status",
                    return_value=AsyncMock(return_value={})(),
                ):
                    # Act - MANDATORY
                    result = await get_metrics()

                    # Assert - MANDATORY
                    assert "requests_total" in result.application_metrics

    async def test_get_metrics_includes_database_metrics(self, sample_metrics_snapshot):
        """Test get_metrics includes database metrics - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        mock_collector = MagicMock()
        mock_collector.get_metrics_snapshot.return_value = sample_metrics_snapshot

        with patch("src.api.routers.health.metrics_export.metrics_collector", mock_collector):
            with patch(
                "src.api.routers.health.metrics_export._get_performance_summary", return_value={}
            ):
                with patch(
                    "src.api.routers.health.metrics_export._get_cache_status",
                    return_value=AsyncMock(return_value={})(),
                ):
                    # Act - MANDATORY
                    result = await get_metrics()

                    # Assert - MANDATORY
                    assert result.database_metrics == sample_metrics_snapshot["database_metrics"]

    async def test_get_metrics_merges_performance_summary(
        self, sample_metrics_snapshot, sample_performance_summary
    ):
        """Test get_metrics merges performance summary - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        mock_collector = MagicMock()
        mock_collector.get_metrics_snapshot.return_value = sample_metrics_snapshot

        with patch("src.api.routers.health.metrics_export.metrics_collector", mock_collector):
            with patch(
                "src.api.routers.health.metrics_export._get_performance_summary",
                return_value=sample_performance_summary,
            ):
                with patch(
                    "src.api.routers.health.metrics_export._get_cache_status",
                    return_value=AsyncMock(return_value={})(),
                ):
                    # Act - MANDATORY
                    result = await get_metrics()

                    # Assert - MANDATORY
                    assert "avg_response_time" in result.application_metrics
                    assert result.application_metrics["avg_response_time"] == 125.5


# ============================================================================
# Prometheus Metrics Endpoint Tests
# ============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
class TestPrometheusMetricsEndpoint:
    """Tests for GET /prometheus endpoint."""

    async def test_prometheus_metrics_returns_string(self, sample_prometheus_data):
        """Test prometheus_metrics returns string - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        mock_collector = MagicMock()
        mock_collector.export_prometheus_metrics.return_value = sample_prometheus_data

        with patch("src.api.routers.health.metrics_export.metrics_collector", mock_collector):
            # Act - MANDATORY
            result = await prometheus_metrics()

            # Assert - MANDATORY
            assert isinstance(result, str)

    async def test_prometheus_metrics_calls_exporter(self, sample_prometheus_data):
        """Test prometheus_metrics calls exporter - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        mock_collector = MagicMock()
        mock_collector.export_prometheus_metrics.return_value = sample_prometheus_data

        with patch("src.api.routers.health.metrics_export.metrics_collector", mock_collector):
            # Act - MANDATORY
            await prometheus_metrics()

            # Assert - MANDATORY
            mock_collector.export_prometheus_metrics.assert_called_once()

    async def test_prometheus_metrics_decodes_utf8(self, sample_prometheus_data):
        """Test prometheus_metrics decodes UTF-8 - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        mock_collector = MagicMock()
        mock_collector.export_prometheus_metrics.return_value = sample_prometheus_data

        with patch("src.api.routers.health.metrics_export.metrics_collector", mock_collector):
            # Act - MANDATORY
            result = await prometheus_metrics()

            # Assert - MANDATORY
            assert "http_requests_total" in result
            assert result == sample_prometheus_data.decode("utf-8")


# ============================================================================
# Cache Status Helper Tests
# ============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
class TestCacheStatusHelpers:
    """Tests for cache status helper functions."""

    async def test_get_cache_status_returns_dict(self):
        """Test _get_cache_status returns dict - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        mock_manager = MagicMock()
        mock_manager.initialize = AsyncMock()
        mock_safe = AsyncMock(return_value={"status": "healthy"})

        with patch("src.api.routers.health.metrics_export.cache_manager", mock_manager):
            with patch("src.api.routers.health.metrics_export._get_cache_status_safe", mock_safe):
                # Act - MANDATORY
                result = await _get_cache_status()

                # Assert - MANDATORY
                assert isinstance(result, dict)

    async def test_get_cache_status_when_manager_is_none(self):
        """Test _get_cache_status when manager is None - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        with patch("src.api.routers.health.metrics_export.cache_manager", None):
            # Act - MANDATORY
            result = await _get_cache_status()

            # Assert - MANDATORY
            assert result == {"status": "not_configured"}

    async def test_get_cache_status_safe_initializes_manager(self):
        """Test _get_cache_status_safe initializes manager - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        mock_manager = MagicMock()
        mock_manager.initialize = AsyncMock()
        mock_manager.backend_type = "redis"

        with patch("src.api.routers.health.metrics_export.cache_manager", mock_manager):
            with patch(
                "src.api.routers.health.metrics_export._get_cache_backend_type_safe",
                return_value=AsyncMock(return_value="redis")(),
            ):
                # Act - MANDATORY
                await _get_cache_status_safe()

                # Assert - MANDATORY
                mock_manager.initialize.assert_called_once()

    async def test_get_cache_status_safe_returns_backend_type(self):
        """Test _get_cache_status_safe returns backend type - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        mock_manager = MagicMock()
        mock_manager.initialize = AsyncMock()
        mock_manager.backend_type = "redis"
        mock_backend_safe = AsyncMock(return_value="redis")

        with patch("src.api.routers.health.metrics_export.cache_manager", mock_manager):
            with patch(
                "src.api.routers.health.metrics_export._get_cache_backend_type_safe",
                mock_backend_safe,
            ):
                # Act - MANDATORY
                result = await _get_cache_status_safe()

                # Assert - MANDATORY
                assert result["backend"] == "redis"
                assert result["status"] == "healthy"

    async def test_get_cache_backend_type_safe_calls_manager(self):
        """Test _get_cache_backend_type_safe calls manager - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        mock_manager = MagicMock()
        mock_manager.get_detailed_backend_type = AsyncMock(return_value="redis:cluster")

        with patch("src.api.routers.health.metrics_export.cache_manager", mock_manager):
            # Act - MANDATORY
            result = await _get_cache_backend_type_safe()

            # Assert - MANDATORY
            mock_manager.get_detailed_backend_type.assert_called_once()
            assert result == "redis:cluster"


# ============================================================================
# Performance Summary Helper Tests
# ============================================================================


@pytest.mark.unit
class TestPerformanceSummaryHelpers:
    """Tests for performance summary helper functions."""

    def test_get_performance_summary_returns_dict(self, sample_performance_summary):
        """Test _get_performance_summary returns dict - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        mock_monitor = MagicMock()
        mock_safe = MagicMock(return_value=sample_performance_summary)

        with patch("src.api.routers.health.metrics_export.performance_monitor", mock_monitor):
            with patch(
                "src.api.routers.health.metrics_export._get_performance_data_safe", mock_safe
            ):
                # Act - MANDATORY
                result = _get_performance_summary()

                # Assert - MANDATORY
                assert isinstance(result, dict)

    def test_get_performance_summary_when_monitor_is_none(self):
        """Test _get_performance_summary when monitor is None - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        with patch("src.api.routers.health.metrics_export.performance_monitor", None):
            # Act - MANDATORY
            result = _get_performance_summary()

            # Assert - MANDATORY
            assert result == {}

    def test_get_performance_summary_with_mock_safe_func(self, sample_performance_summary):
        """Test _get_performance_summary with mocked safe function - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        mock_monitor = MagicMock()
        mock_safe = MagicMock(return_value=sample_performance_summary)

        with patch("src.api.routers.health.metrics_export.performance_monitor", mock_monitor):
            with patch(
                "src.api.routers.health.metrics_export._get_performance_data_safe", mock_safe
            ):
                # Act - MANDATORY
                result = _get_performance_summary()

                # Assert - MANDATORY
                # Verify safe function was called
                mock_safe.assert_called_once()
                assert result == sample_performance_summary


# ============================================================================
# Error Handling Tests
# ============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
class TestMetricsExportErrorHandling:
    """Tests for error handling in metrics export endpoints."""

    async def test_get_cache_status_handles_safe_error(self):
        """Test _get_cache_status handles error from safe function - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        mock_manager = MagicMock()
        mock_safe = AsyncMock(return_value=None)

        with patch("src.api.routers.health.metrics_export.cache_manager", mock_manager):
            with patch("src.api.routers.health.metrics_export._get_cache_status_safe", mock_safe):
                # Act - MANDATORY
                result = await _get_cache_status()

                # Assert - MANDATORY
                assert result["status"] == "error"
                assert "Cache status check failed" in result["error"]

    def test_get_performance_summary_handles_safe_error(self):
        """Test _get_performance_summary handles error from safe function - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        mock_monitor = MagicMock()
        mock_safe = MagicMock(return_value=None)

        with patch("src.api.routers.health.metrics_export.performance_monitor", mock_monitor):
            with patch(
                "src.api.routers.health.metrics_export._get_performance_data_safe", mock_safe
            ):
                # Act - MANDATORY
                result = _get_performance_summary()

                # Assert - MANDATORY
                assert result == {}


# ============================================================================
# Integration Tests
# ============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
class TestMetricsExportIntegration:
    """Integration tests for metrics export endpoints."""

    async def test_get_metrics_combines_all_sources(
        self, sample_metrics_snapshot, sample_performance_summary, sample_cache_status
    ):
        """Test get_metrics combines all metric sources - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        mock_collector = MagicMock()
        mock_collector.get_metrics_snapshot.return_value = sample_metrics_snapshot

        with patch("src.api.routers.health.metrics_export.metrics_collector", mock_collector):
            with patch(
                "src.api.routers.health.metrics_export._get_performance_summary",
                return_value=sample_performance_summary,
            ):
                with patch(
                    "src.api.routers.health.metrics_export._get_cache_status",
                    return_value=AsyncMock(return_value=sample_cache_status)(),
                ):
                    # Act - MANDATORY
                    result = await get_metrics()

                    # Assert - MANDATORY
                    # Should have system metrics
                    assert "cpu_percent" in result.system_metrics
                    # Should have application metrics
                    assert "requests_total" in result.application_metrics
                    # Should have performance metrics
                    assert "avg_response_time" in result.application_metrics
                    # Should have cache status
                    assert "cache" in result.application_metrics
                    # Should have database metrics
                    assert "connections" in result.database_metrics


# ============================================================================
# MANDATORY Performance Benchmarks
# ============================================================================


@pytest.mark.performance
@pytest.mark.unit
@pytest.mark.asyncio
class TestMetricsExportPerformance:
    """MANDATORY performance tests for metrics export endpoints."""

    async def test_get_metrics_performance(self, sample_metrics_snapshot):
        """MANDATORY performance test - get_metrics speed."""
        # Arrange - MANDATORY
        mock_collector = MagicMock()
        mock_collector.get_metrics_snapshot.return_value = sample_metrics_snapshot
        iterations = 100

        with patch("src.api.routers.health.metrics_export.metrics_collector", mock_collector):
            with patch(
                "src.api.routers.health.metrics_export._get_performance_summary", return_value={}
            ):
                with patch(
                    "src.api.routers.health.metrics_export._get_cache_status",
                    return_value=AsyncMock(return_value={})(),
                ):
                    # Act - MANDATORY
                    start_time = time.perf_counter()

                    for _ in range(iterations):
                        await get_metrics()

                    end_time = time.perf_counter()
                    execution_time = end_time - start_time

                    # Assert - MANDATORY
                    avg_time = execution_time / iterations
                    assert avg_time < 0.01  # <10ms per call
                    assert execution_time < 1.0  # Total <1s for 100 calls

    async def test_prometheus_metrics_performance(self, sample_prometheus_data):
        """MANDATORY performance test - prometheus_metrics speed."""
        # Arrange - MANDATORY
        mock_collector = MagicMock()
        mock_collector.export_prometheus_metrics.return_value = sample_prometheus_data
        iterations = 100

        with patch("src.api.routers.health.metrics_export.metrics_collector", mock_collector):
            # Act - MANDATORY
            start_time = time.perf_counter()

            for _ in range(iterations):
                await prometheus_metrics()

            end_time = time.perf_counter()
            execution_time = end_time - start_time

            # Assert - MANDATORY
            avg_time = execution_time / iterations
            assert avg_time < 0.005  # <5ms per call
            assert execution_time < 0.5  # Total <500ms for 100 calls

    async def test_cache_status_check_performance(self):
        """MANDATORY performance test - cache status check speed."""
        # Arrange - MANDATORY
        mock_manager = MagicMock()
        mock_manager.initialize = AsyncMock()
        mock_manager.backend_type = "redis"
        iterations = 100

        with patch("src.api.routers.health.metrics_export.cache_manager", mock_manager):
            with patch(
                "src.api.routers.health.metrics_export._get_cache_backend_type_safe",
                return_value=AsyncMock(return_value="redis")(),
            ):
                # Act - MANDATORY
                start_time = time.perf_counter()

                for _ in range(iterations):
                    await _get_cache_status_safe()

                end_time = time.perf_counter()
                execution_time = end_time - start_time

                # Assert - MANDATORY
                avg_time = execution_time / iterations
                assert avg_time < 0.01  # <10ms per check
                assert execution_time < 1.0  # Total <1s for 100 checks
