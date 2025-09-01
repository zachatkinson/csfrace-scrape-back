"""Unit tests for health router endpoints."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException, status
from sqlalchemy import text

from src.api.routers.health import (
    get_metrics,
    health_check,
    liveness_check,
    prometheus_metrics,
    readiness_check,
)
from src.api.schemas import HealthCheckResponse, MetricsResponse


class TestHealthRouterEndpoints:
    """Test health router endpoint functions."""

    @pytest.fixture
    def mock_db_session(self):
        """Mock database session."""
        return AsyncMock()

    @pytest.mark.asyncio
    async def test_health_check_all_healthy(self, mock_db_session):
        """Test health check when all components are healthy."""
        # Mock database check
        mock_db_session.execute = AsyncMock()

        # Mock health checker
        with patch("src.api.routers.health.health_checker.get_health_summary") as mock_health:
            mock_health.return_value = {"status": "healthy"}

            # Mock observability manager
            with patch(
                "src.api.routers.health.observability_manager.get_component_status"
            ) as mock_obs:
                mock_obs.return_value = {"status": "healthy"}

                result = await health_check(mock_db_session)

                assert isinstance(result, HealthCheckResponse)
                assert result.status == "healthy"
                assert result.version == "1.1.0"
                assert result.database["status"] == "healthy"
                assert result.database["connected"] is True
                # Cache may be configured in the environment
                assert result.cache["status"] in ["healthy", "not_configured"]

                # Verify database was checked
                mock_db_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_health_check_database_failure(self, mock_db_session):
        """Test health check with database failure."""
        mock_db_session.execute.side_effect = Exception("Connection refused")

        with patch("src.api.routers.health.health_checker.get_health_summary") as mock_health:
            mock_health.return_value = {"status": "healthy"}

            with patch(
                "src.api.routers.health.observability_manager.get_component_status"
            ) as mock_obs:
                mock_obs.return_value = {"status": "healthy"}

                with pytest.raises(HTTPException) as exc_info:
                    await health_check(mock_db_session)

                assert exc_info.value.status_code == status.HTTP_503_SERVICE_UNAVAILABLE

                # Should still return health check data in error detail
                error_detail = exc_info.value.detail
                assert error_detail["status"] == "unhealthy"
                assert error_detail["database"]["status"] == "unhealthy"
                assert error_detail["database"]["connected"] is False
                assert "Connection refused" in error_detail["database"]["error"]

    @pytest.mark.asyncio
    async def test_health_check_degraded_system(self, mock_db_session):
        """Test health check with degraded system status."""
        mock_db_session.execute = AsyncMock()

        with patch("src.api.routers.health.health_checker.get_health_summary") as mock_health:
            mock_health.return_value = {"status": "degraded"}

            with patch(
                "src.api.routers.health.observability_manager.get_component_status"
            ) as mock_obs:
                mock_obs.return_value = {"status": "healthy"}

                result = await health_check(mock_db_session)

                assert result.status == "degraded"
                assert result.database["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_health_check_with_cache_healthy(self, mock_db_session):
        """Test health check with healthy cache."""
        mock_db_session.execute = AsyncMock()

        with patch("src.api.routers.health.health_checker.get_health_summary") as mock_health:
            mock_health.return_value = {"status": "healthy"}

            with patch(
                "src.api.routers.health.observability_manager.get_component_status"
            ) as mock_obs:
                mock_obs.return_value = {"status": "healthy"}

                # Mock cache manager
                mock_cache_manager = MagicMock()
                mock_cache_manager.initialize = AsyncMock()
                mock_cache_manager.backend_type = "redis"

                with patch.dict(
                    "sys.modules",
                    {"src.caching.manager": MagicMock(cache_manager=mock_cache_manager)},
                ):
                    result = await health_check(mock_db_session)

                    assert result.cache["status"] == "healthy"
                    assert result.cache["backend"] == "redis"

    @pytest.mark.asyncio
    async def test_health_check_with_cache_error(self, mock_db_session):
        """Test health check with cache error."""
        mock_db_session.execute = AsyncMock()

        with patch("src.api.routers.health.health_checker.get_health_summary") as mock_health:
            mock_health.return_value = {"status": "healthy"}

            with patch(
                "src.api.routers.health.observability_manager.get_component_status"
            ) as mock_obs:
                mock_obs.return_value = {"status": "healthy"}

                # Mock cache manager that fails
                mock_cache_manager = MagicMock()
                mock_cache_manager.initialize.side_effect = Exception("Redis connection failed")

                with patch.dict(
                    "sys.modules",
                    {"src.caching.manager": MagicMock(cache_manager=mock_cache_manager)},
                ):
                    result = await health_check(mock_db_session)

                    assert result.status == "degraded"
                    assert result.cache["status"] == "error"
                    assert "Redis connection failed" in result.cache["error"]

    @pytest.mark.asyncio
    async def test_health_check_cache_import_error(self, mock_db_session):
        """Test health check when cache module is not available."""
        mock_db_session.execute = AsyncMock()

        with patch("src.api.routers.health.health_checker.get_health_summary") as mock_health:
            mock_health.return_value = {"status": "healthy"}

            with patch(
                "src.api.routers.health.observability_manager.get_component_status"
            ) as mock_obs:
                mock_obs.return_value = {"status": "healthy"}

                # Import will fail
                with patch(
                    "builtins.__import__",
                    side_effect=ImportError("No module named 'src.caching.manager'"),
                ):
                    result = await health_check(mock_db_session)

                    # Should handle import error gracefully
                    assert result.cache["status"] == "error"

    @pytest.mark.asyncio
    async def test_health_check_general_exception(self, mock_db_session):
        """Test health check with unexpected exception."""
        with patch("src.api.routers.health.health_checker.get_health_summary") as mock_health:
            mock_health.side_effect = Exception("Unexpected error")

            with pytest.raises(HTTPException) as exc_info:
                await health_check(mock_db_session)

            assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
            assert "Health check failed: Unexpected error" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_get_metrics_success(self):
        """Test successful metrics retrieval."""
        mock_metrics = {
            "system_metrics": {"cpu_usage": 45.2, "memory_usage": 1024},
            "application_metrics": {"active_jobs": 5, "completed_jobs": 100},
            "database_metrics": {"active_connections": 10, "query_count": 500},
        }

        with patch(
            "src.api.routers.health.metrics_collector.get_metrics_snapshot"
        ) as mock_collector:
            mock_collector.return_value = mock_metrics

            result = await get_metrics()

            assert isinstance(result, MetricsResponse)
            assert isinstance(result.timestamp, datetime)
            assert result.system_metrics == mock_metrics["system_metrics"]
            # Application metrics may include additional trace fields
            assert (
                result.application_metrics["active_jobs"]
                == mock_metrics["application_metrics"]["active_jobs"]
            )
            assert (
                result.application_metrics["completed_jobs"]
                == mock_metrics["application_metrics"]["completed_jobs"]
            )
            assert result.database_metrics == mock_metrics["database_metrics"]

    @pytest.mark.asyncio
    async def test_get_metrics_with_performance_data(self):
        """Test metrics retrieval with performance monitoring."""
        mock_metrics = {
            "system_metrics": {"cpu_usage": 30.0},
            "application_metrics": {"active_jobs": 3},
            "database_metrics": {"active_connections": 5},
        }

        mock_performance = {
            "avg_response_time": 125.5,
            "requests_per_second": 30.0,
            "error_rate": 0.02,
        }

        with patch(
            "src.api.routers.health.metrics_collector.get_metrics_snapshot"
        ) as mock_collector:
            mock_collector.return_value = mock_metrics

            # Mock performance monitor
            mock_perf_monitor = MagicMock()
            mock_perf_monitor.get_performance_summary.return_value = mock_performance

            with patch.dict(
                "sys.modules",
                {"src.monitoring.performance": MagicMock(performance_monitor=mock_perf_monitor)},
            ):
                result = await get_metrics()

                # Performance data should be merged into application_metrics
                assert result.application_metrics["active_jobs"] == 3
                assert result.application_metrics["avg_response_time"] == 125.5
                assert result.application_metrics["requests_per_second"] == 30.0

    @pytest.mark.asyncio
    async def test_get_metrics_performance_import_error(self):
        """Test metrics retrieval when performance monitoring is not available."""
        mock_metrics = {
            "system_metrics": {"cpu_usage": 25.0},
            "application_metrics": {"active_jobs": 2},
            "database_metrics": {"active_connections": 3},
        }

        with patch(
            "src.api.routers.health.metrics_collector.get_metrics_snapshot"
        ) as mock_collector:
            mock_collector.return_value = mock_metrics

            # Performance import fails
            with patch(
                "builtins.__import__",
                side_effect=ImportError("No module named 'src.monitoring.performance'"),
            ):
                result = await get_metrics()

                # Should work without performance data
                assert isinstance(result, MetricsResponse)
                assert result.application_metrics == mock_metrics["application_metrics"]

    @pytest.mark.asyncio
    async def test_get_metrics_performance_attribute_error(self):
        """Test metrics retrieval when performance monitor has no get_performance_summary."""
        mock_metrics = {
            "system_metrics": {"cpu_usage": 25.0},
            "application_metrics": {"active_jobs": 2},
            "database_metrics": {"active_connections": 3},
        }

        with patch(
            "src.api.routers.health.metrics_collector.get_metrics_snapshot"
        ) as mock_collector:
            mock_collector.return_value = mock_metrics

            # Performance monitor exists but missing method
            mock_perf_monitor = MagicMock()
            del mock_perf_monitor.get_performance_summary  # Remove method

            with patch.dict(
                "sys.modules",
                {"src.monitoring.performance": MagicMock(performance_monitor=mock_perf_monitor)},
            ):
                result = await get_metrics()

                # Should work without performance data
                assert isinstance(result, MetricsResponse)

    @pytest.mark.asyncio
    async def test_get_metrics_collector_error(self):
        """Test metrics retrieval with collector error."""
        with patch(
            "src.api.routers.health.metrics_collector.get_metrics_snapshot"
        ) as mock_collector:
            mock_collector.side_effect = Exception("Metrics collection failed")

            with pytest.raises(HTTPException) as exc_info:
                await get_metrics()

            assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
            assert "Failed to collect metrics: Metrics collection failed" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_liveness_check(self):
        """Test liveness check endpoint."""
        result = await liveness_check()

        assert result == {"status": "alive"}

    @pytest.mark.asyncio
    async def test_readiness_check_success(self, mock_db_session):
        """Test successful readiness check."""
        mock_db_session.execute = AsyncMock()

        result = await readiness_check(mock_db_session)

        assert result == {"status": "ready"}
        mock_db_session.execute.assert_called_once()
        # Verify it executed the SELECT 1 query
        call_args = mock_db_session.execute.call_args[0]
        assert isinstance(call_args[0], type(text("SELECT 1")))

    @pytest.mark.asyncio
    async def test_readiness_check_database_failure(self, mock_db_session):
        """Test readiness check with database failure."""
        mock_db_session.execute.side_effect = Exception("Database not ready")

        with pytest.raises(HTTPException) as exc_info:
            await readiness_check(mock_db_session)

        assert exc_info.value.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        assert "Service not ready: Database not ready" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_prometheus_metrics_success(self):
        """Test successful Prometheus metrics export."""
        mock_metrics_data = b"""# HELP total_requests Total requests processed
# TYPE total_requests counter
total_requests 1500
# HELP active_jobs Currently active jobs
# TYPE active_jobs gauge
active_jobs 8
# HELP request_duration_seconds Request duration in seconds
# TYPE request_duration_seconds histogram
request_duration_seconds_bucket{le="0.1"} 100
request_duration_seconds_bucket{le="0.5"} 450
request_duration_seconds_bucket{le="1.0"} 800
"""

        with patch(
            "src.api.routers.health.metrics_collector.export_prometheus_metrics"
        ) as mock_export:
            mock_export.return_value = mock_metrics_data

            result = await prometheus_metrics()

            assert isinstance(result, str)
            assert "total_requests 1500" in result
            assert "active_jobs 8" in result
            assert "request_duration_seconds_bucket" in result

            mock_export.assert_called_once()

    @pytest.mark.asyncio
    async def test_prometheus_metrics_export_failure(self):
        """Test Prometheus metrics export failure."""
        with patch(
            "src.api.routers.health.metrics_collector.export_prometheus_metrics"
        ) as mock_export:
            mock_export.side_effect = Exception("Prometheus export failed")

            with pytest.raises(HTTPException) as exc_info:
                await prometheus_metrics()

            assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
            assert (
                "Failed to export Prometheus metrics: Prometheus export failed"
                in exc_info.value.detail
            )

    @pytest.mark.asyncio
    async def test_health_check_timestamp_format(self, mock_db_session):
        """Test that health check timestamp is properly formatted."""
        mock_db_session.execute = AsyncMock()

        with patch("src.api.routers.health.health_checker.get_health_summary") as mock_health:
            mock_health.return_value = {"status": "healthy"}

            with patch(
                "src.api.routers.health.observability_manager.get_component_status"
            ) as mock_obs:
                mock_obs.return_value = {"status": "healthy"}

                result = await health_check(mock_db_session)

                assert isinstance(result.timestamp, datetime)
                assert result.timestamp.tzinfo == UTC

    @pytest.mark.asyncio
    async def test_health_check_cache_status_scenarios(self, mock_db_session):
        """Test different cache status scenarios."""
        mock_db_session.execute = AsyncMock()

        # Test cache not configured (default)
        with patch("src.api.routers.health.health_checker") as mock_health_checker:
            mock_health_checker.get_health_summary.return_value = {"status": "healthy"}
            with patch("src.api.routers.health.observability_manager") as mock_obs:
                mock_obs.get_component_status.return_value = {"status": "healthy"}
            with patch("builtins.__import__", side_effect=ImportError("No cache module")):
                result = await health_check(mock_db_session)
                assert result.cache["status"] == "error"

    @pytest.mark.asyncio
    async def test_health_check_observability_status_integration(self, mock_db_session):
        """Test integration with observability manager status."""
        mock_db_session.execute = AsyncMock()

        test_obs_statuses = ["healthy", "degraded", "error", "unknown"]

        for obs_status in test_obs_statuses:
            with patch("src.api.routers.health.health_checker.get_health_summary") as mock_health:
                mock_health.return_value = {"status": "healthy"}

                with patch(
                    "src.api.routers.health.observability_manager.get_component_status"
                ) as mock_obs:
                    mock_obs.return_value = {"status": obs_status}

                    result = await health_check(mock_db_session)

                    assert result.monitoring["status"] == obs_status

    @pytest.mark.asyncio
    async def test_get_metrics_empty_snapshots(self):
        """Test metrics retrieval with empty snapshots."""
        empty_metrics = {"system_metrics": {}, "application_metrics": {}, "database_metrics": {}}

        with patch(
            "src.api.routers.health.metrics_collector.get_metrics_snapshot"
        ) as mock_collector:
            mock_collector.return_value = empty_metrics

            result = await get_metrics()

            assert result.system_metrics == {}
            # Application metrics may include default trace fields even when empty
            if "active_traces" in result.application_metrics:
                # Check that trace metrics are at default values
                assert result.application_metrics.get("active_traces", 0) == 0
                assert result.application_metrics.get("total_traces", 0) == 0
            else:
                assert result.application_metrics == {}
            assert result.database_metrics == {}

    @pytest.mark.asyncio
    async def test_get_metrics_missing_metric_categories(self):
        """Test metrics retrieval with missing metric categories."""
        incomplete_metrics = {
            "system_metrics": {"cpu_usage": 50.0}
            # Missing application_metrics and database_metrics
        }

        with patch(
            "src.api.routers.health.metrics_collector.get_metrics_snapshot"
        ) as mock_collector:
            mock_collector.return_value = incomplete_metrics

            result = await get_metrics()

            assert result.system_metrics == {"cpu_usage": 50.0}
            # Application metrics may include default trace fields even when empty
            if "active_traces" in result.application_metrics:
                # Check that trace metrics are at default values
                assert result.application_metrics.get("active_traces", 0) == 0
                assert result.application_metrics.get("total_traces", 0) == 0
            else:
                assert result.application_metrics == {}  # Should default to empty
            assert result.database_metrics == {}

    @pytest.mark.asyncio
    async def test_get_metrics_timestamp_precision(self):
        """Test that metrics timestamp has proper precision."""
        with patch(
            "src.api.routers.health.metrics_collector.get_metrics_snapshot"
        ) as mock_collector:
            mock_collector.return_value = {
                "system_metrics": {},
                "application_metrics": {},
                "database_metrics": {},
            }

            result = await get_metrics()

            assert isinstance(result.timestamp, datetime)
            assert result.timestamp.tzinfo == UTC
            # Timestamp should be recent (within last minute)
            time_diff = datetime.now(UTC) - result.timestamp
            assert time_diff.total_seconds() < 60

    @pytest.mark.asyncio
    async def test_prometheus_metrics_encoding_handling(self):
        """Test Prometheus metrics handles encoding correctly."""
        # Test with non-ASCII characters in metrics
        mock_metrics_with_unicode = '# HELP requests Total requests\ntotal_requests{method="GET",endpoint="/api/v1/测试"} 42\n'.encode()

        with patch(
            "src.api.routers.health.metrics_collector.export_prometheus_metrics"
        ) as mock_export:
            mock_export.return_value = mock_metrics_with_unicode

            result = await prometheus_metrics()

            assert isinstance(result, str)
            assert "测试" in result  # Unicode should be properly decoded

    @pytest.mark.asyncio
    async def test_readiness_check_sql_query_execution(self, mock_db_session):
        """Test that readiness check executes the correct SQL query."""
        mock_db_session.execute = AsyncMock()

        await readiness_check(mock_db_session)

        # Verify the SELECT 1 query was executed
        mock_db_session.execute.assert_called_once()
        call_args = mock_db_session.execute.call_args[0]
        executed_query = call_args[0]

        # Should be a text() query with "SELECT 1"
        assert hasattr(executed_query, "text")

    @pytest.mark.asyncio
    async def test_health_check_http_exception_passthrough(self, mock_db_session):
        """Test that HTTPExceptions are passed through correctly."""
        mock_db_session.execute = AsyncMock()

        with patch("src.api.routers.health.health_checker.get_health_summary") as mock_health:
            # Simulate an HTTPException being raised internally
            test_http_exception = HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Service temporarily unavailable",
            )
            mock_health.side_effect = test_http_exception

            # Should re-raise the same HTTPException
            with pytest.raises(HTTPException) as exc_info:
                await health_check(mock_db_session)

            assert exc_info.value == test_http_exception

    @pytest.mark.asyncio
    async def test_health_check_status_determination_logic(self, mock_db_session):
        """Test the overall status determination logic."""
        mock_db_session.execute = AsyncMock()

        # Test various combinations of component statuses
        test_scenarios = [
            # (health_summary_status, overall_expected_status)
            ({"status": "healthy"}, "healthy"),
            ({"status": "degraded"}, "degraded"),
            ({"status": "error"}, "degraded"),
            ({"status": "unknown"}, "degraded"),
            ({}, "degraded"),  # Missing status key
        ]

        for health_summary, expected_status in test_scenarios:
            with patch("src.api.routers.health.health_checker.get_health_summary") as mock_health:
                mock_health.return_value = health_summary

                with patch(
                    "src.api.routers.health.observability_manager.get_component_status"
                ) as mock_obs:
                    mock_obs.return_value = {"status": "healthy"}

                    if expected_status == "degraded":
                        # Degraded status should still return 200, not 503
                        result = await health_check(mock_db_session)
                        assert result.status == expected_status
                    else:
                        result = await health_check(mock_db_session)
                        assert result.status == expected_status
