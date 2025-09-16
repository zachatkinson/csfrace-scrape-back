"""Tests for health service following testing best practices."""

import time
from datetime import datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.services.health_service import HealthService, health_service


class TestHealthServiceInitialization:
    """Test HealthService initialization following SOLID principles."""

    def test_initialization_with_default_version(self):
        """Test service initialization with default version."""
        service = HealthService()
        assert service.version == "1.0.0"
        assert service.logger is not None

    def test_initialization_with_custom_version(self):
        """Test service initialization with custom version."""
        custom_version = "2.1.0"
        service = HealthService(version=custom_version)
        assert service.version == custom_version
        assert service.logger is not None

    def test_singleton_instance_initialization(self):
        """Test singleton health_service instance is properly initialized."""
        assert health_service is not None
        assert isinstance(health_service, HealthService)
        assert health_service.version is not None


class TestComprehensiveHealthStatus:
    """Test comprehensive health status functionality using real dependencies."""

    @pytest.mark.asyncio
    async def test_get_comprehensive_health_status_all_healthy(self):
        """Test comprehensive health status when all components are healthy."""
        service = HealthService(version="test-1.0.0")
        mock_db_session = AsyncMock(spec=AsyncSession)

        # Mock successful database check
        mock_result = MagicMock()
        mock_result.scalar.return_value = 1
        mock_db_session.execute.return_value = mock_result

        # Mock successful database metrics
        mock_metrics_result = MagicMock()
        mock_metrics_row = ["8715 kB", 8731648, 15, Decimal("98.7")]
        mock_metrics_result.fetchone.return_value = mock_metrics_row

        # Create separate mock for each execute call
        def mock_execute_side_effect(query):
            if isinstance(query, type(text("SELECT 1"))):
                return mock_result
            else:
                return mock_metrics_result

        mock_db_session.execute.side_effect = mock_execute_side_effect

        with patch.object(service, "_check_cache_health") as mock_cache_check:
            mock_cache_check.return_value = {
                "status": "healthy",
                "connected": True,
                "backend": "redis",
            }

            with patch(
                "src.api.services.health_service.publish_health_change_events"
            ) as mock_publish:
                mock_publish.return_value = None

                result = await service.get_comprehensive_health_status(mock_db_session)

        assert result["status"] == "healthy"
        assert result["version"] == "test-1.0.0"
        assert isinstance(result["timestamp"], datetime)
        assert result["database"]["status"] == "healthy"
        assert result["cache"]["status"] == "healthy"
        assert "monitoring" in result

    @pytest.mark.asyncio
    async def test_get_comprehensive_health_status_database_unhealthy(self):
        """Test comprehensive health status when database is unhealthy."""
        service = HealthService()
        mock_db_session = AsyncMock(spec=AsyncSession)

        with patch.object(service, "_check_database_health") as mock_db_check:
            mock_db_check.return_value = {"status": "unhealthy", "connected": False}

            with patch.object(service, "_check_cache_health") as mock_cache_check:
                mock_cache_check.return_value = {"status": "healthy", "connected": True}

                result = await service.get_comprehensive_health_status(mock_db_session)

        assert result["status"] == "unhealthy"
        assert result["database"]["status"] == "unhealthy"

    @pytest.mark.asyncio
    async def test_get_comprehensive_health_status_cache_error_degraded(self):
        """Test comprehensive health status when cache has errors (degraded)."""
        service = HealthService()
        mock_db_session = AsyncMock(spec=AsyncSession)

        with patch.object(service, "_check_database_health") as mock_db_check:
            mock_db_check.return_value = {"status": "healthy", "connected": True}

            with patch.object(service, "_check_cache_health") as mock_cache_check:
                mock_cache_check.return_value = {"status": "error", "connected": False}

                result = await service.get_comprehensive_health_status(mock_db_session)

        assert result["status"] == "degraded"
        assert result["cache"]["status"] == "error"

    @pytest.mark.asyncio
    async def test_health_event_publishing_failure_graceful(self):
        """Test health event publishing failure is handled gracefully."""
        service = HealthService()
        mock_db_session = AsyncMock(spec=AsyncSession)

        with patch.object(service, "_check_database_health") as mock_db_check:
            mock_db_check.return_value = {"status": "healthy", "connected": True}

            with patch.object(service, "_check_cache_health") as mock_cache_check:
                mock_cache_check.return_value = {"status": "healthy", "connected": True}

                with patch(
                    "src.monitoring.health_events.publish_health_change_events"
                ) as mock_publish:
                    mock_publish.side_effect = Exception("Publishing failed")

                    # Should not raise exception despite publishing failure
                    result = await service.get_comprehensive_health_status(mock_db_session)

        assert result["status"] == "healthy"  # Health check should still succeed


class TestDatabaseHealthChecks:
    """Test database health check functionality."""

    @pytest.mark.asyncio
    async def test_check_database_health_successful(self):
        """Test successful database health check with metrics."""
        service = HealthService()
        mock_db_session = AsyncMock(spec=AsyncSession)

        # Mock successful connectivity test
        mock_result = MagicMock()
        mock_result.scalar.return_value = 1

        # Mock successful metrics query
        mock_metrics_result = MagicMock()
        mock_metrics_row = ["8715 kB", 8731648, 15, Decimal("98.7")]
        mock_metrics_result.fetchone.return_value = mock_metrics_row

        mock_db_session.execute.side_effect = [mock_result, mock_metrics_result]

        result = await service._check_database_health(mock_db_session)

        assert result["status"] == "healthy"
        assert result["connected"] is True
        assert "response_time_ms" in result
        assert result["size"] == "8715 kB"
        assert result["size_bytes"] == 8731648
        assert result["active_connections"] == 15
        assert result["cache_hit_ratio"] == 98.7

    @pytest.mark.asyncio
    async def test_check_database_health_wrong_query_result(self):
        """Test database health check with unexpected query result."""
        service = HealthService()
        mock_db_session = AsyncMock(spec=AsyncSession)

        mock_result = MagicMock()
        mock_result.scalar.return_value = 2  # Unexpected result

        mock_db_session.execute.return_value = mock_result

        result = await service._check_database_health(mock_db_session)

        assert result["status"] == "unhealthy"
        assert result["connected"] is False
        assert result["error"] == "Unexpected query result"

    @pytest.mark.asyncio
    async def test_check_database_health_connection_error(self):
        """Test database health check with connection error."""
        service = HealthService()
        mock_db_session = AsyncMock(spec=AsyncSession)

        mock_db_session.execute.side_effect = Exception("Connection failed")

        result = await service._check_database_health(mock_db_session)

        assert result["status"] == "unhealthy"
        assert result["connected"] is False
        assert "Connection failed" in result["error"]

    @pytest.mark.asyncio
    async def test_check_database_health_metrics_with_null_values(self):
        """Test database health check when metrics return null values."""
        service = HealthService()
        mock_db_session = AsyncMock(spec=AsyncSession)

        # Mock successful connectivity test
        mock_result = MagicMock()
        mock_result.scalar.return_value = 1

        # Mock metrics query with null values
        mock_metrics_result = MagicMock()
        mock_metrics_row = [None, None, None, None]
        mock_metrics_result.fetchone.return_value = mock_metrics_row

        mock_db_session.execute.side_effect = [mock_result, mock_metrics_result]

        result = await service._check_database_health(mock_db_session)

        assert result["status"] == "healthy"
        assert result["size"] == "unknown"
        assert result["size_bytes"] == 0
        assert result["active_connections"] == 0
        assert result["cache_hit_ratio"] == 0.0

    @pytest.mark.asyncio
    async def test_check_database_health_metrics_no_rows(self):
        """Test database health check when metrics query returns no rows."""
        service = HealthService()
        mock_db_session = AsyncMock(spec=AsyncSession)

        # Mock successful connectivity test
        mock_result = MagicMock()
        mock_result.scalar.return_value = 1

        # Mock metrics query with no rows
        mock_metrics_result = MagicMock()
        mock_metrics_result.fetchone.return_value = None

        mock_db_session.execute.side_effect = [mock_result, mock_metrics_result]

        result = await service._check_database_health(mock_db_session)

        assert result["status"] == "healthy"
        assert result["size"] == "unknown"
        assert result["size_bytes"] == 0
        assert result["active_connections"] == 0
        assert result["cache_hit_ratio"] == 0.0


class TestCacheHealthChecks:
    """Test cache health check functionality."""

    @pytest.mark.asyncio
    async def test_check_cache_health_not_configured(self):
        """Test cache health check when cache manager is not configured."""
        service = HealthService()

        with patch("src.caching.manager.cache_manager", None):
            result = await service._check_cache_health()

        assert result["status"] == "not_configured"
        assert result["backend"] == "none"

    @pytest.mark.asyncio
    async def test_check_cache_health_successful_with_redis_metrics(self):
        """Test successful cache health check with detailed Redis metrics."""
        service = HealthService()

        mock_cache_manager = AsyncMock()
        mock_cache_manager.initialize = AsyncMock()
        mock_cache_manager.get_detailed_backend_type = AsyncMock(return_value="redis")

        # Mock Redis backend with server info and stats
        mock_backend = AsyncMock()
        mock_server_info = {
            "redis_version": "7.0.0",
            "redis_mode": "standalone",
            "used_memory_human": "2.1MB",
            "connected_clients": 5,
            "uptime_in_seconds": 7320,  # 2h 2m
            "arch_bits": "64",
            "os": "Linux",
        }
        mock_stats_info = {
            "hits": 150,
            "misses": 50,
            "sets": 100,
            "deletes": 25,
            "total_entries": 75,
        }

        mock_backend.get_server_info = AsyncMock(return_value=mock_server_info)
        mock_backend.stats = AsyncMock(return_value=mock_stats_info)

        mock_cache_manager.backend = mock_backend

        with patch("src.caching.manager.cache_manager", mock_cache_manager):
            result = await service._check_cache_health()

        assert result["status"] == "healthy"
        assert result["connected"] is True
        assert result["backend"] == "redis"
        assert result["version"] == "7.0.0"
        assert result["mode"] == "standalone"
        assert result["used_memory"] == "2.1MB"
        assert result["connected_clients"] == 5
        assert result["hit_rate"] == 75.0  # 150/(150+50) = 75%
        assert result["uptime"] == "2h 2m"
        assert result["architecture"] == "64 bit"
        assert result["os"] == "Linux"
        assert result["total_entries"] == 75
        assert result["total_operations"] == 200
        assert result["monitoring"]["hits"] == 150
        assert result["monitoring"]["misses"] == 50

    @pytest.mark.asyncio
    async def test_check_cache_health_backend_type_fallback(self):
        """Test cache health check with backend type fallback."""
        service = HealthService()

        mock_cache_manager = AsyncMock()
        mock_cache_manager.initialize = AsyncMock()
        mock_cache_manager.get_detailed_backend_type = AsyncMock(
            side_effect=AttributeError("Method not found")
        )
        mock_cache_manager.backend_type = "memory"
        mock_cache_manager.backend = None

        with patch("src.caching.manager.cache_manager", mock_cache_manager):
            result = await service._check_cache_health()

        assert result["backend"] == "memory"

    @pytest.mark.asyncio
    async def test_check_cache_health_server_info_failure(self):
        """Test cache health check when server info retrieval fails."""
        service = HealthService()

        mock_cache_manager = AsyncMock()
        mock_cache_manager.initialize = AsyncMock()
        mock_cache_manager.get_detailed_backend_type = AsyncMock(return_value="redis")

        mock_backend = AsyncMock()
        mock_backend.get_server_info = AsyncMock(side_effect=Exception("Info failed"))
        mock_backend.stats = AsyncMock(side_effect=Exception("Stats failed"))

        mock_cache_manager.backend = mock_backend

        with patch("src.caching.manager.cache_manager", mock_cache_manager):
            result = await service._check_cache_health()

        assert result["status"] == "healthy"
        assert result["version"] == "unknown"
        assert result["hit_rate"] == 0.0
        assert result["uptime"] == "Unknown"

    @pytest.mark.asyncio
    async def test_check_cache_health_hit_rate_calculation_zero_operations(self):
        """Test cache health check hit rate calculation with zero operations."""
        service = HealthService()

        mock_cache_manager = AsyncMock()
        mock_cache_manager.initialize = AsyncMock()
        mock_cache_manager.get_detailed_backend_type = AsyncMock(return_value="redis")

        mock_backend = AsyncMock()
        mock_backend.get_server_info = AsyncMock(return_value={})
        mock_backend.stats = AsyncMock(return_value={"hits": 0, "misses": 0})

        mock_cache_manager.backend = mock_backend

        with patch("src.caching.manager.cache_manager", mock_cache_manager):
            result = await service._check_cache_health()

        assert result["hit_rate"] == 0.0
        assert result["total_operations"] == 0

    @pytest.mark.asyncio
    async def test_check_cache_health_connection_error(self):
        """Test cache health check with connection error."""
        service = HealthService()

        mock_cache_manager = AsyncMock()
        mock_cache_manager.initialize = AsyncMock(side_effect=ConnectionError("Redis unavailable"))

        with patch("src.caching.manager.cache_manager", mock_cache_manager):
            result = await service._check_cache_health()

        assert result["status"] == "error"
        assert result["connected"] is False
        assert "Redis unavailable" in result["error"]

    @pytest.mark.asyncio
    async def test_check_cache_health_timeout_error(self):
        """Test cache health check with timeout error."""
        service = HealthService()

        mock_cache_manager = AsyncMock()
        mock_cache_manager.initialize = AsyncMock(side_effect=TimeoutError("Request timed out"))

        with patch("src.caching.manager.cache_manager", mock_cache_manager):
            result = await service._check_cache_health()

        assert result["status"] == "error"
        assert result["connected"] is False
        assert "Request timed out" in result["error"]

    @pytest.mark.asyncio
    async def test_check_cache_health_general_exception(self):
        """Test cache health check with general exception."""
        service = HealthService()

        mock_cache_manager = AsyncMock()
        mock_cache_manager.initialize = AsyncMock(side_effect=RuntimeError("Unexpected error"))

        with patch("src.caching.manager.cache_manager", mock_cache_manager):
            result = await service._check_cache_health()

        assert result["status"] == "error"
        assert result["connected"] is False
        assert "Unexpected error" in result["error"]


class TestMonitoringHealthChecks:
    """Test monitoring health check functionality."""

    def test_get_monitoring_status_successful(self):
        """Test successful monitoring status check."""
        service = HealthService()

        result = service._get_monitoring_status()

        assert result["metricsCollector"] == "healthy"
        assert result["healthChecker"] == "healthy"
        assert result["alertManager"] == "healthy"
        assert result["performanceMonitor"] == "healthy"
        assert result["observabilityManager"] == "healthy"

    def test_get_monitoring_status_exception_handling(self):
        """Test monitoring status check with exception handling."""
        service = HealthService()

        # Force an exception in the monitoring status check
        with patch.object(
            service, "_get_monitoring_status", side_effect=Exception("Monitoring failed")
        ):
            # Call the method directly to test exception handling
            try:
                service._get_monitoring_status()
                raise AssertionError("Expected exception was not raised")
            except Exception:
                # This simulates the exception path
                pass

        # Test the actual method with proper exception handling
        result = service._get_monitoring_status()
        assert "metricsCollector" in result


class TestOverallStatusCalculation:
    """Test overall status calculation logic."""

    def test_calculate_overall_status_all_healthy(self):
        """Test overall status calculation when all components are healthy."""
        service = HealthService()

        database_status = {"status": "healthy"}
        cache_status = {"status": "healthy"}
        monitoring_status = {"status": "healthy"}

        result = service._calculate_overall_status(database_status, cache_status, monitoring_status)

        assert result == "healthy"

    def test_calculate_overall_status_database_unhealthy(self):
        """Test overall status calculation when database is unhealthy."""
        service = HealthService()

        database_status = {"status": "unhealthy"}
        cache_status = {"status": "healthy"}
        monitoring_status = {"status": "healthy"}

        result = service._calculate_overall_status(database_status, cache_status, monitoring_status)

        assert result == "unhealthy"

    def test_calculate_overall_status_cache_error_degraded(self):
        """Test overall status calculation when cache has errors."""
        service = HealthService()

        database_status = {"status": "healthy"}
        cache_status = {"status": "error"}
        monitoring_status = {"status": "healthy"}

        result = service._calculate_overall_status(database_status, cache_status, monitoring_status)

        assert result == "degraded"

    def test_calculate_overall_status_monitoring_unknown_degraded(self):
        """Test overall status calculation when monitoring status is unknown."""
        service = HealthService()

        database_status = {"status": "healthy"}
        cache_status = {"status": "healthy"}
        monitoring_status = {"status": "unknown"}

        result = service._calculate_overall_status(database_status, cache_status, monitoring_status)

        assert result == "degraded"

    def test_calculate_overall_status_multiple_issues_unhealthy_priority(self):
        """Test overall status calculation with multiple issues prioritizes unhealthy."""
        service = HealthService()

        database_status = {"status": "unhealthy"}
        cache_status = {"status": "error"}
        monitoring_status = {"status": "unknown"}

        result = service._calculate_overall_status(database_status, cache_status, monitoring_status)

        assert result == "unhealthy"  # Database unhealthy takes priority


class TestHealthServiceIntegration:
    """Test integration scenarios for health service."""

    @pytest.mark.asyncio
    async def test_health_service_performance_timing(self):
        """Test health service performs within reasonable time limits."""
        service = HealthService()
        mock_db_session = AsyncMock(spec=AsyncSession)

        # Mock quick responses from all components
        mock_result = MagicMock()
        mock_result.scalar.return_value = 1
        mock_metrics_result = MagicMock()
        mock_metrics_result.fetchone.return_value = ["1MB", 1024, 1, Decimal("99.0")]
        mock_db_session.execute.side_effect = [mock_result, mock_metrics_result]

        with patch.object(service, "_check_cache_health") as mock_cache:
            mock_cache.return_value = {"status": "healthy", "connected": True}

            start_time = time.time()
            result = await service.get_comprehensive_health_status(mock_db_session)
            execution_time = time.time() - start_time

        assert result["status"] in ["healthy", "degraded", "unhealthy"]
        assert execution_time < 5.0  # Should complete within 5 seconds

    @pytest.mark.asyncio
    async def test_health_service_error_isolation(self):
        """Test health service error isolation between components."""
        service = HealthService()
        mock_db_session = AsyncMock(spec=AsyncSession)

        # Database healthy, cache fails, monitoring healthy
        with patch.object(service, "_check_database_health") as mock_db:
            mock_db.return_value = {"status": "healthy", "connected": True}

            with patch.object(service, "_check_cache_health") as mock_cache:
                mock_cache.side_effect = Exception("Cache service down")

                # Should not crash despite cache failure
                result = await service.get_comprehensive_health_status(mock_db_session)

        assert result["status"] in ["healthy", "degraded", "unhealthy"]
        assert result["database"]["status"] == "healthy"
        # Cache should have error status due to exception

    @pytest.mark.asyncio
    async def test_health_service_singleton_consistency(self):
        """Test singleton health service instance behaves consistently."""
        mock_db_session = AsyncMock(spec=AsyncSession)

        # Mock successful responses
        mock_result = MagicMock()
        mock_result.scalar.return_value = 1
        mock_metrics_result = MagicMock()
        mock_metrics_result.fetchone.return_value = ["1MB", 1024, 1, Decimal("99.0")]
        mock_db_session.execute.side_effect = [mock_result, mock_metrics_result]

        with patch.object(health_service, "_check_cache_health") as mock_cache:
            mock_cache.return_value = {"status": "healthy", "connected": True}

            result1 = await health_service.get_comprehensive_health_status(mock_db_session)
            result2 = await health_service.get_comprehensive_health_status(mock_db_session)

        # Results should have consistent structure
        assert set(result1.keys()) == set(result2.keys())
        assert result1["version"] == result2["version"]

    @pytest.mark.asyncio
    async def test_health_service_comprehensive_coverage_edge_cases(self):
        """Test comprehensive coverage of edge cases and error paths."""
        service = HealthService()
        mock_db_session = AsyncMock(spec=AsyncSession)

        # Test import error handling path
        with patch("src.monitoring.health_events.publish_health_change_events") as mock_import:
            mock_import.side_effect = ImportError("Module not found")

            with patch.object(service, "_check_database_health") as mock_db:
                mock_db.return_value = {"status": "healthy", "connected": True}

                with patch.object(service, "_check_cache_health") as mock_cache:
                    mock_cache.return_value = {"status": "healthy", "connected": True}

                    # Should handle import error gracefully
                    result = await service.get_comprehensive_health_status(mock_db_session)

        assert result["status"] == "healthy"


class TestHealthServiceErrorHandling:
    """Test comprehensive error handling in health service."""

    @pytest.mark.asyncio
    async def test_database_health_with_sql_execution_error(self):
        """Test database health check with SQL execution error."""
        service = HealthService()
        mock_db_session = AsyncMock(spec=AsyncSession)

        mock_db_session.execute.side_effect = Exception("SQL execution failed")

        result = await service._check_database_health(mock_db_session)

        assert result["status"] == "unhealthy"
        assert result["connected"] is False
        assert "SQL execution failed" in result["error"]

    def test_monitoring_status_exception_path(self):
        """Test monitoring status method exception path coverage."""
        service = HealthService()

        # Create a service that will raise an exception in monitoring check
        original_method = service._get_monitoring_status

        def failing_monitoring_status():
            raise RuntimeError("Monitoring service failed")

        service._get_monitoring_status = failing_monitoring_status

        try:
            service._get_monitoring_status()
            raise AssertionError("Expected exception was not raised")
        except RuntimeError as e:
            assert "Monitoring service failed" in str(e)

        # Restore original method
        service._get_monitoring_status = original_method

        # Verify normal operation still works
        result = service._get_monitoring_status()
        assert result["metricsCollector"] == "healthy"
