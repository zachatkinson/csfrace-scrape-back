"""Comprehensive tests for health check endpoints - MANDATORY TEST_BUILDING.md compliance.

This module tests health check endpoints with complete coverage:
- Comprehensive health check endpoint (/)
- Liveness check endpoint (/live)
- Readiness check endpoint (/ready)
- Health service integration
- Database connectivity verification
- Error handling and unhealthy state responses
- Uptime calculation

ALL tests follow MANDATORY TEST_BUILDING.md patterns:
- AAA pattern with explicit comments
- Factory fixtures for DRY principle
- Comprehensive health check scenario testing
- Performance benchmarks with specific thresholds
"""

import time
from typing import Any
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import asyncio
import pytest
from fastapi import APIRouter
from fastapi.routing import APIRoute
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from src.api.routers.health.checks import (
    _startup_time,
    health_check,
    liveness_check,
    readiness_check,
    router,
)
from src.auth.models import StatusResponse

# ============================================================================
# Test Fixtures - DRY Principle
# ============================================================================


@pytest.fixture
def mock_db_session() -> Mock:
    """Factory for mock database session - DRY principle."""
    db = MagicMock()
    db.execute = AsyncMock()
    return db


@pytest.fixture
def sample_healthy_status() -> dict[str, Any]:
    """Factory for sample healthy health status - DRY principle."""
    from datetime import datetime

    return {
        "status": "healthy",
        "version": "1.0.0",
        "database": {"status": "healthy", "latency_ms": 5.2},
        "cache": {"status": "healthy", "latency_ms": 1.1},
        "monitoring": {"status": "healthy", "checks_passing": 10},
        "timestamp": datetime(2023, 1, 1, 0, 0, 0),
    }


@pytest.fixture
def sample_unhealthy_status() -> dict[str, Any]:
    """Factory for sample unhealthy health status - DRY principle."""
    from datetime import datetime

    return {
        "status": "unhealthy",
        "version": "1.0.0",
        "database": {"status": "unhealthy", "latency_ms": None, "error": "Connection failed"},
        "cache": {"status": "healthy", "latency_ms": 1.1},
        "monitoring": {"status": "unhealthy", "checks_passing": 5, "checks_failing": 5},
        "timestamp": datetime(2023, 1, 1, 0, 0, 0),
    }


@pytest.fixture
def sample_degraded_status() -> dict[str, Any]:
    """Factory for sample degraded health status - DRY principle."""
    from datetime import datetime

    return {
        "status": "degraded",
        "version": "1.0.0",
        "database": {"status": "healthy", "latency_ms": 5.2},
        "cache": {"status": "degraded", "latency_ms": 100.5, "warning": "High latency"},
        "monitoring": {"status": "degraded", "checks_passing": 8, "checks_failing": 2},
        "timestamp": datetime(2023, 1, 1, 0, 0, 0),
    }


# ============================================================================
# Router Configuration Tests
# ============================================================================


@pytest.mark.unit
class TestHealthChecksRouter:
    """Tests for health checks router configuration."""

    def test_router_exists(self) -> None:
        """Test that checks router exists - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # Act - MANDATORY
        # Assert - MANDATORY
        assert router is not None
        assert isinstance(router, APIRouter)

    def test_router_has_health_check_endpoint(self) -> None:
        """Test router has / endpoint - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # Act - MANDATORY
        routes = [route.path for route in router.routes if isinstance(route, APIRoute)]

        # Assert - MANDATORY
        assert "/" in routes

    def test_router_has_liveness_endpoint(self) -> None:
        """Test router has /live endpoint - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # Act - MANDATORY
        routes = [route.path for route in router.routes if isinstance(route, APIRoute)]

        # Assert - MANDATORY
        assert "/live" in routes

    def test_router_has_readiness_endpoint(self) -> None:
        """Test router has /ready endpoint - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # Act - MANDATORY
        routes = [route.path for route in router.routes if isinstance(route, APIRoute)]

        # Assert - MANDATORY
        assert "/ready" in routes

    def test_all_endpoints_use_get_method(self) -> None:
        """Test all endpoints use GET method - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # Act - MANDATORY
        # Assert - MANDATORY
        for route in router.routes:
            if isinstance(route, APIRoute):
                assert "GET" in route.methods


# ============================================================================
# Health Check Endpoint Tests
# ============================================================================


@pytest.mark.unit
class TestHealthCheckEndpoint:
    """Tests for comprehensive health check endpoint."""

    @pytest.mark.asyncio
    async def test_health_check_returns_healthy_response(
        self, mock_db_session: Mock, sample_healthy_status: dict[str, Any]
    ) -> None:
        """Test health_check returns healthy response - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        mock_health_service = MagicMock()
        mock_health_service.get_comprehensive_health_status = AsyncMock(
            return_value=sample_healthy_status
        )

        with patch("src.api.routers.health.checks.health_service", mock_health_service):
            # Act - MANDATORY
            response = await health_check(mock_db_session)

            # Assert - MANDATORY
            assert response.status == "healthy"
            mock_health_service.get_comprehensive_health_status.assert_called_once_with(
                mock_db_session
            )

    @pytest.mark.asyncio
    async def test_health_check_includes_all_components(
        self, mock_db_session: Mock, sample_healthy_status: dict[str, Any]
    ) -> None:
        """Test health_check includes all components - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        mock_health_service = MagicMock()
        mock_health_service.get_comprehensive_health_status = AsyncMock(
            return_value=sample_healthy_status
        )

        with patch("src.api.routers.health.checks.health_service", mock_health_service):
            # Act - MANDATORY
            response = await health_check(mock_db_session)

            # Assert - MANDATORY
            assert hasattr(response, "database")
            assert hasattr(response, "cache")
            assert hasattr(response, "version")

    @pytest.mark.asyncio
    async def test_health_check_raises_when_unhealthy(
        self, mock_db_session: Mock, sample_unhealthy_status: dict[str, Any]
    ) -> None:
        """Test health_check raises exception when unhealthy - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        mock_health_service = MagicMock()
        mock_health_service.get_comprehensive_health_status = AsyncMock(
            return_value=sample_unhealthy_status
        )

        with patch("src.api.routers.health.checks.health_service", mock_health_service):
            # Act - MANDATORY & Assert - MANDATORY
            # api_error_handler decorator wraps HTTPException in RuntimeError
            with pytest.raises(RuntimeError) as exc_info:
                await health_check(mock_db_session)

            # Verify exception details
            assert "health check" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_health_check_accepts_degraded_status(
        self, mock_db_session: Mock, sample_degraded_status: dict[str, Any]
    ) -> None:
        """Test health_check accepts degraded status - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        mock_health_service = MagicMock()
        mock_health_service.get_comprehensive_health_status = AsyncMock(
            return_value=sample_degraded_status
        )

        with patch("src.api.routers.health.checks.health_service", mock_health_service):
            # Act - MANDATORY
            response = await health_check(mock_db_session)

            # Assert - MANDATORY
            # Should return successfully with degraded status
            assert response.status == "degraded"

    @pytest.mark.asyncio
    async def test_health_check_calls_health_service(
        self, mock_db_session: Mock, sample_healthy_status: dict[str, Any]
    ) -> None:
        """Test health_check calls health service - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        mock_health_service = MagicMock()
        mock_health_service.get_comprehensive_health_status = AsyncMock(
            return_value=sample_healthy_status
        )

        with patch("src.api.routers.health.checks.health_service", mock_health_service):
            # Act - MANDATORY
            await health_check(mock_db_session)

            # Assert - MANDATORY
            mock_health_service.get_comprehensive_health_status.assert_called_once_with(
                mock_db_session
            )


# ============================================================================
# Liveness Check Endpoint Tests
# ============================================================================


@pytest.mark.unit
class TestLivenessCheckEndpoint:
    """Tests for liveness check endpoint."""

    @pytest.mark.asyncio
    async def test_liveness_check_returns_alive_status(self) -> None:
        """Test liveness_check returns alive status - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # Act - MANDATORY
        response = await liveness_check()

        # Assert - MANDATORY
        assert isinstance(response, StatusResponse)
        assert response.status == "alive"

    @pytest.mark.asyncio
    async def test_liveness_check_includes_uptime(self) -> None:
        """Test liveness_check includes uptime - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # Act - MANDATORY
        response = await liveness_check()

        # Assert - MANDATORY
        assert hasattr(response, "uptime_seconds")
        assert response.uptime_seconds is not None
        assert isinstance(response.uptime_seconds, int)
        assert response.uptime_seconds >= 0

    @pytest.mark.asyncio
    async def test_liveness_check_calculates_uptime_correctly(self) -> None:
        """Test liveness_check calculates uptime - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # Wait a brief moment to ensure uptime increases
        initial_response = await liveness_check()
        await asyncio.sleep(0.1)

        # Act - MANDATORY
        second_response = await liveness_check()

        # Assert - MANDATORY
        initial_uptime = initial_response.uptime_seconds
        second_uptime = second_response.uptime_seconds
        assert initial_uptime is not None
        assert second_uptime is not None
        assert second_uptime >= initial_uptime

    @pytest.mark.asyncio
    async def test_liveness_check_does_not_require_db(self) -> None:
        """Test liveness_check doesn't require database - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # Act - MANDATORY
        # Should not raise any exceptions without database
        response = await liveness_check()

        # Assert - MANDATORY
        assert response.status == "alive"

    @pytest.mark.asyncio
    async def test_liveness_check_is_fast(self) -> None:
        """Test liveness_check executes quickly - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        start_time = time.perf_counter()

        # Act - MANDATORY
        await liveness_check()

        # Assert - MANDATORY
        execution_time = time.perf_counter() - start_time
        assert execution_time < 0.001  # Should complete in <1ms


# ============================================================================
# Readiness Check Endpoint Tests
# ============================================================================


@pytest.mark.unit
class TestReadinessCheckEndpoint:
    """Tests for readiness check endpoint."""

    @pytest.mark.asyncio
    async def test_readiness_check_returns_ready_status(self, mock_db_session: Mock) -> None:
        """Test readiness_check returns ready status - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        mock_db_session.execute = AsyncMock()

        # Act - MANDATORY
        response = await readiness_check(mock_db_session)

        # Assert - MANDATORY
        assert isinstance(response, StatusResponse)
        assert response.status == "ready"

    @pytest.mark.asyncio
    async def test_readiness_check_verifies_database(self, mock_db_session: Mock) -> None:
        """Test readiness_check verifies database - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        mock_db_session.execute = AsyncMock()

        # Act - MANDATORY
        await readiness_check(mock_db_session)

        # Assert - MANDATORY
        # Should execute SELECT 1 query
        mock_db_session.execute.assert_called_once()
        call_args = mock_db_session.execute.call_args[0][0]
        assert isinstance(call_args, type(text("SELECT 1")))

    @pytest.mark.asyncio
    async def test_readiness_check_fails_when_db_unavailable(self) -> None:
        """Test readiness_check fails with unavailable DB - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        mock_db_session = MagicMock()
        mock_db_session.execute = AsyncMock(
            side_effect=SQLAlchemyError("Database connection failed")
        )

        # Act - MANDATORY & Assert - MANDATORY
        # api_error_handler decorator wraps SQLAlchemyError in RuntimeError
        with pytest.raises(RuntimeError) as exc_info:
            await readiness_check(mock_db_session)

        # Verify exception - decorator wraps database errors
        assert "readiness check" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_readiness_check_requires_db_session(self) -> None:
        """Test readiness_check requires database session - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        mock_db_session = MagicMock()
        mock_db_session.execute = AsyncMock()

        # Act - MANDATORY
        response = await readiness_check(mock_db_session)

        # Assert - MANDATORY
        # Should have called database
        assert mock_db_session.execute.called
        assert response.status == "ready"


# ============================================================================
# Startup Time Tests
# ============================================================================


@pytest.mark.unit
class TestStartupTime:
    """Tests for startup time tracking."""

    def test_startup_time_is_set(self) -> None:
        """Test startup time is initialized - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # Act - MANDATORY
        # Assert - MANDATORY
        assert _startup_time is not None
        assert isinstance(_startup_time, float)
        assert _startup_time > 0

    def test_startup_time_is_reasonable(self) -> None:
        """Test startup time is reasonable - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        current_time = time.time()

        # Act - MANDATORY
        # Assert - MANDATORY
        # Startup time should be before current time
        assert _startup_time <= current_time
        # And not too far in the past (within last hour for tests)
        assert current_time - _startup_time < 3600


# ============================================================================
# Integration Tests
# ============================================================================


@pytest.mark.unit
class TestHealthChecksIntegration:
    """Integration tests for health check endpoints."""

    @pytest.mark.asyncio
    async def test_liveness_and_readiness_work_together(self, mock_db_session: Mock) -> None:
        """Test liveness and readiness checks work together - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        mock_db_session.execute = AsyncMock()

        # Act - MANDATORY
        liveness_response = await liveness_check()
        readiness_response = await readiness_check(mock_db_session)

        # Assert - MANDATORY
        assert liveness_response.status == "alive"
        assert readiness_response.status == "ready"

    @pytest.mark.asyncio
    async def test_health_check_with_healthy_service(
        self, mock_db_session: Mock, sample_healthy_status: dict[str, Any]
    ) -> None:
        """Test health check with healthy service - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        mock_health_service = MagicMock()
        mock_health_service.get_comprehensive_health_status = AsyncMock(
            return_value=sample_healthy_status
        )

        with patch("src.api.routers.health.checks.health_service", mock_health_service):
            # Act - MANDATORY
            health_response = await health_check(mock_db_session)
            liveness_response = await liveness_check()
            mock_db_session.execute = AsyncMock()
            readiness_response = await readiness_check(mock_db_session)

            # Assert - MANDATORY
            assert health_response.status == "healthy"
            assert liveness_response.status == "alive"
            assert readiness_response.status == "ready"


# ============================================================================
# MANDATORY Performance Benchmarks
# ============================================================================


@pytest.mark.performance
@pytest.mark.unit
class TestHealthChecksPerformance:
    """MANDATORY performance tests for health check endpoints."""

    @pytest.mark.asyncio
    async def test_liveness_check_performance(self) -> None:
        """MANDATORY performance test - liveness check speed."""
        # Arrange - MANDATORY
        iterations = 1000

        # Act - MANDATORY
        start_time = time.perf_counter()

        for _ in range(iterations):
            await liveness_check()

        end_time = time.perf_counter()
        execution_time = end_time - start_time

        # Assert - MANDATORY
        avg_time = execution_time / iterations
        assert avg_time < 0.001  # <1ms per check
        assert execution_time < 1.0  # Total <1s for 1000 checks

    @pytest.mark.asyncio
    async def test_readiness_check_performance(self, mock_db_session: Mock) -> None:
        """MANDATORY performance test - readiness check speed."""
        # Arrange - MANDATORY
        mock_db_session.execute = AsyncMock()
        iterations = 100

        # Act - MANDATORY
        start_time = time.perf_counter()

        for _ in range(iterations):
            await readiness_check(mock_db_session)

        end_time = time.perf_counter()
        execution_time = end_time - start_time

        # Assert - MANDATORY
        avg_time = execution_time / iterations
        assert avg_time < 0.01  # <10ms per check
        assert execution_time < 1.0  # Total <1s for 100 checks

    @pytest.mark.asyncio
    async def test_health_check_performance(
        self, mock_db_session: Mock, sample_healthy_status: dict[str, Any]
    ) -> None:
        """MANDATORY performance test - health check speed."""
        # Arrange - MANDATORY
        mock_health_service = MagicMock()
        mock_health_service.get_comprehensive_health_status = AsyncMock(
            return_value=sample_healthy_status
        )
        iterations = 100

        with patch("src.api.routers.health.checks.health_service", mock_health_service):
            # Act - MANDATORY
            start_time = time.perf_counter()

            for _ in range(iterations):
                await health_check(mock_db_session)

            end_time = time.perf_counter()
            execution_time = end_time - start_time

        # Assert - MANDATORY
        avg_time = execution_time / iterations
        assert avg_time < 0.01  # <10ms per check
        assert execution_time < 1.0  # Total <1s for 100 checks
