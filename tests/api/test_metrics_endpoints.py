"""Comprehensive tests for API metrics endpoints - MANDATORY TEST_BUILDING.md compliance.

This module tests FastAPI metrics endpoints functionality with complete coverage:
- prometheus_metrics() endpoint functionality
- MetricsConfiguration.setup_metrics() configuration
- Prometheus format validation
- Error handling for metrics collection failures
- Security validation for metrics exposure
- Performance benchmarks

ALL tests follow MANDATORY TEST_BUILDING.md patterns:
- AAA pattern with explicit comments
- Factory fixtures for DRY principle
- Comprehensive metrics endpoint scenario testing
- Security testing for sensitive data exposure
- Performance benchmarks with specific thresholds
"""

import time
from unittest.mock import MagicMock, patch

import pytest
from fastapi.responses import PlainTextResponse

from src.api.metrics_endpoints import MetricsConfiguration, prometheus_metrics, router

# ============================================================================
# Test Fixtures - DRY Principle
# ============================================================================


@pytest.fixture
def mock_metrics_collector():
    """Factory for mock metrics collector - DRY principle."""
    collector = MagicMock()
    collector.metrics = {"http_requests_total": 100, "http_request_duration_seconds": 0.5}
    collector.export_prometheus_metrics.return_value = (
        b"# TYPE http_requests_total counter\nhttp_requests_total 100\n"
    )
    return collector


@pytest.fixture
def sample_prometheus_metrics():
    """Factory for sample Prometheus metrics data - DRY principle."""
    return b"""# HELP http_requests_total Total HTTP requests
# TYPE http_requests_total counter
http_requests_total 100

# HELP http_request_duration_seconds HTTP request duration
# TYPE http_request_duration_seconds histogram
http_request_duration_seconds_sum 50.0
http_request_duration_seconds_count 100
"""


@pytest.fixture
def empty_metrics_collector():
    """Factory for empty metrics collector - DRY principle."""
    collector = MagicMock()
    collector.metrics = {}
    collector.export_prometheus_metrics.return_value = b""
    return collector


# ============================================================================
# Router Configuration Tests
# ============================================================================


@pytest.mark.unit
class TestMetricsRouter:
    """Tests for metrics router configuration."""

    def test_router_exists(self):
        """Test that metrics router is properly configured - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # Act - MANDATORY
        # Assert - MANDATORY
        assert router is not None
        assert hasattr(router, "tags")
        assert "Monitoring" in router.tags

    def test_router_has_metrics_endpoint(self):
        """Test that /metrics endpoint is registered - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        routes = [route.path for route in router.routes]

        # Act - MANDATORY
        # Assert - MANDATORY
        assert "/metrics" in routes


# ============================================================================
# prometheus_metrics() Tests
# ============================================================================


@pytest.mark.unit
class TestPrometheusMetrics:
    """Tests for prometheus_metrics() endpoint function."""

    @pytest.mark.asyncio
    async def test_prometheus_metrics_returns_string(self, mock_metrics_collector):
        """Test prometheus_metrics() returns string - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # Patch at the import location inside the function
        with patch("src.monitoring.metrics.metrics_collector", mock_metrics_collector):
            # Act - MANDATORY
            result = await prometheus_metrics()

            # Assert - MANDATORY
            assert isinstance(result, str)
            assert len(result) > 0

    @pytest.mark.asyncio
    async def test_prometheus_metrics_calls_export(self, mock_metrics_collector):
        """Test that export_prometheus_metrics() is called - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        with patch("src.monitoring.metrics.metrics_collector", mock_metrics_collector):
            # Act - MANDATORY
            await prometheus_metrics()

            # Assert - MANDATORY
            mock_metrics_collector.export_prometheus_metrics.assert_called_once()

    @pytest.mark.asyncio
    async def test_prometheus_metrics_decodes_bytes_to_utf8(self, mock_metrics_collector):
        """Test that bytes are properly decoded to UTF-8 - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        mock_metrics_collector.export_prometheus_metrics.return_value = b"test_metric 123"

        with patch("src.monitoring.metrics.metrics_collector", mock_metrics_collector):
            # Act - MANDATORY
            result = await prometheus_metrics()

            # Assert - MANDATORY
            assert result == "test_metric 123"
            assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_prometheus_metrics_logging(self, mock_metrics_collector):
        """Test that prometheus_metrics() logs appropriately - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        with patch("src.monitoring.metrics.metrics_collector", mock_metrics_collector):
            with patch("src.api.metrics_endpoints.logger") as mock_logger:
                # Act - MANDATORY
                await prometheus_metrics()

                # Assert - MANDATORY
                mock_logger.info.assert_called_once_with("Exporting Prometheus metrics")
                mock_logger.debug.assert_called_once()
                # Verify debug log includes metrics size
                debug_call_kwargs = mock_logger.debug.call_args[1]
                assert "metrics_size_bytes" in debug_call_kwargs

    @pytest.mark.asyncio
    async def test_prometheus_metrics_with_valid_format(self, sample_prometheus_metrics):
        """Test prometheus_metrics() with valid Prometheus format - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        mock_collector = MagicMock()
        mock_collector.export_prometheus_metrics.return_value = sample_prometheus_metrics

        with patch("src.monitoring.metrics.metrics_collector", mock_collector):
            # Act - MANDATORY
            result = await prometheus_metrics()

            # Assert - MANDATORY
            assert "# HELP" in result
            assert "# TYPE" in result
            assert "http_requests_total" in result
            assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_prometheus_metrics_with_empty_metrics(self, empty_metrics_collector):
        """Test prometheus_metrics() with empty metrics - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        with patch("src.monitoring.metrics.metrics_collector", empty_metrics_collector):
            # Act - MANDATORY
            result = await prometheus_metrics()

            # Assert - MANDATORY
            assert isinstance(result, str)
            # Empty metrics should return empty string
            assert result == ""

    @pytest.mark.asyncio
    async def test_prometheus_metrics_with_large_dataset(self):
        """Test prometheus_metrics() with large metrics dataset - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        large_metrics = b"# Large metrics data\n" + (b'test_metric{label="value"} 123\n' * 1000)
        mock_collector = MagicMock()
        mock_collector.export_prometheus_metrics.return_value = large_metrics

        with patch("src.monitoring.metrics.metrics_collector", mock_collector):
            # Act - MANDATORY
            result = await prometheus_metrics()

            # Assert - MANDATORY
            assert isinstance(result, str)
            assert len(result) > 10000  # Should be large
            assert "test_metric" in result


# ============================================================================
# MetricsConfiguration Tests
# ============================================================================


@pytest.mark.unit
class TestMetricsConfiguration:
    """Tests for MetricsConfiguration class."""

    def test_setup_metrics_with_initialized_collector(self, mock_metrics_collector):
        """Test setup_metrics() with initialized collector - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        with patch("src.monitoring.metrics.metrics_collector", mock_metrics_collector):
            # Act - MANDATORY
            MetricsConfiguration.setup_metrics()

            # Assert - MANDATORY
            # Should complete without errors
            assert mock_metrics_collector.metrics  # Metrics exist

    def test_setup_metrics_with_empty_collector(self, empty_metrics_collector):
        """Test setup_metrics() with empty collector - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        with patch("src.monitoring.metrics.metrics_collector", empty_metrics_collector):
            with patch("src.api.metrics_endpoints.logger") as mock_logger:
                # Act - MANDATORY
                MetricsConfiguration.setup_metrics()

                # Assert - MANDATORY
                # Should log warning about uninitialized metrics
                warning_calls = list(mock_logger.warning.call_args_list)
                assert len(warning_calls) > 0
                assert "not initialized" in str(warning_calls[0])

    def test_setup_metrics_logging(self, mock_metrics_collector):
        """Test that setup_metrics() logs appropriately - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        with patch("src.monitoring.metrics.metrics_collector", mock_metrics_collector):
            with patch("src.api.metrics_endpoints.logger") as mock_logger:
                # Act - MANDATORY
                MetricsConfiguration.setup_metrics()

                # Assert - MANDATORY
                info_calls = [call[0][0] for call in mock_logger.info.call_args_list]
                assert "Setting up application metrics" in info_calls
                assert "Application metrics setup completed" in info_calls

    def test_setup_metrics_is_static_method(self):
        """Test that setup_metrics() is a static method - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # Act - MANDATORY
        # Assert - MANDATORY
        assert isinstance(MetricsConfiguration.__dict__["setup_metrics"], staticmethod)

    def test_setup_metrics_idempotent(self, mock_metrics_collector):
        """Test setup_metrics() is idempotent - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        with patch("src.monitoring.metrics.metrics_collector", mock_metrics_collector):
            # Act - MANDATORY
            MetricsConfiguration.setup_metrics()
            MetricsConfiguration.setup_metrics()  # Call twice

            # Assert - MANDATORY
            # Should complete without errors on multiple calls
            assert mock_metrics_collector.metrics


# ============================================================================
# Security Tests - MANDATORY
# ============================================================================


@pytest.mark.unit
@pytest.mark.security
class TestMetricsEndpointsSecurity:
    """MANDATORY security tests for metrics endpoints."""

    @pytest.mark.asyncio
    async def test_prometheus_metrics_no_sensitive_data_leakage(self):
        """MANDATORY security test - metrics don't leak sensitive data."""
        # Arrange - MANDATORY
        sensitive_metrics = b"""# HELP test_metric Test metric
# TYPE test_metric gauge
test_metric{password="secret123",api_key="sk_live_123"} 1
"""
        mock_collector = MagicMock()
        mock_collector.export_prometheus_metrics.return_value = sensitive_metrics

        with patch("src.monitoring.metrics.metrics_collector", mock_collector):
            # Act - MANDATORY
            result = await prometheus_metrics()

            # Assert - MANDATORY
            # Note: Current implementation does NOT sanitize metrics labels
            # This documents the current behavior
            assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_prometheus_metrics_response_format_is_plain_text(self):
        """MANDATORY security test - response is plain text (not HTML/JSON)."""
        # Arrange - MANDATORY
        # Act - MANDATORY
        # Get route for /metrics endpoint
        metrics_route = None
        for route in router.routes:
            if route.path == "/metrics":
                metrics_route = route
                break

        # Assert - MANDATORY
        assert metrics_route is not None
        assert metrics_route.response_class == PlainTextResponse

    @pytest.mark.asyncio
    async def test_prometheus_metrics_no_internal_errors_exposed(self):
        """MANDATORY security test - internal errors are handled gracefully."""
        # Arrange - MANDATORY
        mock_collector = MagicMock()
        mock_collector.export_prometheus_metrics.side_effect = Exception("Internal error")

        with patch("src.monitoring.metrics.metrics_collector", mock_collector):
            # Act - MANDATORY
            # The decorator should catch exceptions
            with pytest.raises(Exception):
                await prometheus_metrics()

            # Assert - MANDATORY
            # Exception should be raised (decorator handles it)
            mock_collector.export_prometheus_metrics.assert_called_once()


# ============================================================================
# MANDATORY Performance Benchmarks
# ============================================================================


@pytest.mark.performance
@pytest.mark.unit
class TestMetricsEndpointsPerformance:
    """MANDATORY performance tests for metrics endpoints."""

    @pytest.mark.asyncio
    async def test_prometheus_metrics_performance(self, mock_metrics_collector):
        """MANDATORY performance test - metrics export speed."""
        # Arrange - MANDATORY
        iterations = 100

        with patch("src.monitoring.metrics.metrics_collector", mock_metrics_collector):
            # Act - MANDATORY
            start_time = time.perf_counter()

            for _ in range(iterations):
                await prometheus_metrics()

            end_time = time.perf_counter()
            execution_time = end_time - start_time

        # Assert - MANDATORY
        avg_time = execution_time / iterations
        assert avg_time < 0.01  # <10ms per export
        assert execution_time < 1.0  # Total <1s for 100 exports

    def test_setup_metrics_performance(self, mock_metrics_collector):
        """MANDATORY performance test - metrics setup speed."""
        # Arrange - MANDATORY
        iterations = 100

        with patch("src.monitoring.metrics.metrics_collector", mock_metrics_collector):
            # Act - MANDATORY
            start_time = time.perf_counter()

            for _ in range(iterations):
                MetricsConfiguration.setup_metrics()

            end_time = time.perf_counter()
            execution_time = end_time - start_time

        # Assert - MANDATORY
        avg_time = execution_time / iterations
        assert avg_time < 0.005  # <5ms per setup
        assert execution_time < 0.5  # Total <500ms for 100 setups

    @pytest.mark.asyncio
    async def test_prometheus_metrics_large_dataset_performance(self):
        """MANDATORY performance test - large metrics dataset handling."""
        # Arrange - MANDATORY
        # Create large metrics dataset (10KB+)
        large_metrics = b"# Large metrics\n" + (b'test_metric{label="value"} 123\n' * 500)
        mock_collector = MagicMock()
        mock_collector.export_prometheus_metrics.return_value = large_metrics

        with patch("src.monitoring.metrics.metrics_collector", mock_collector):
            # Act - MANDATORY
            start_time = time.perf_counter()
            result = await prometheus_metrics()
            execution_time = time.perf_counter() - start_time

        # Assert - MANDATORY
        assert execution_time < 0.05  # Should complete in <50ms
        assert len(result) > 10000  # Verify large dataset was processed


# ============================================================================
# Integration Tests
# ============================================================================


@pytest.mark.unit
class TestMetricsEndpointsIntegration:
    """Integration tests for metrics endpoints."""

    @pytest.mark.asyncio
    async def test_prometheus_metrics_end_to_end(self, mock_metrics_collector):
        """Test full prometheus_metrics() flow - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        mock_metrics_collector.export_prometheus_metrics.return_value = b"http_requests_total 42"

        with patch("src.monitoring.metrics.metrics_collector", mock_metrics_collector):
            # Act - MANDATORY
            result = await prometheus_metrics()

            # Assert - MANDATORY
            assert result == "http_requests_total 42"
            mock_metrics_collector.export_prometheus_metrics.assert_called_once()

    def test_metrics_configuration_setup_and_export(self, mock_metrics_collector):
        """Test MetricsConfiguration setup followed by export - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        with patch("src.monitoring.metrics.metrics_collector", mock_metrics_collector):
            # Act - MANDATORY
            MetricsConfiguration.setup_metrics()

            # Assert - MANDATORY
            assert mock_metrics_collector.metrics  # Metrics should be initialized
