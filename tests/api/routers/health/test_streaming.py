"""Comprehensive tests for health streaming endpoints - MANDATORY TEST_BUILDING.md compliance.

This module tests health streaming functionality with complete coverage:
- Router configuration
- Stream test endpoint

Note: The actual SSE health streaming endpoint is tested in test_health_stream.py
as it lives in health_stream.py, not streaming.py.

ALL tests follow MANDATORY TEST_BUILDING.md patterns:
- AAA pattern with explicit comments
- Factory fixtures for DRY principle
- Performance benchmarks with specific thresholds
"""

import time

import pytest
from fastapi import APIRouter
from fastapi.routing import APIRoute

from src.api.routers.health.streaming import (
    health_stream_test,
    router,
)

# ============================================================================
# Router Configuration Tests
# ============================================================================


@pytest.mark.unit
class TestHealthStreamingRouter:
    """Tests for health streaming router configuration."""

    def test_router_exists(self) -> None:
        """Test that health streaming router exists - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # Act - MANDATORY
        # Assert - MANDATORY
        assert router is not None
        assert isinstance(router, APIRouter)

    def test_router_has_stream_test_endpoint(self) -> None:
        """Test router has /stream-test endpoint - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # Act - MANDATORY
        routes = [route.path for route in router.routes if isinstance(route, APIRoute)]

        # Assert - MANDATORY
        assert "/stream-test" in routes

    def test_stream_test_endpoint_uses_get_method(self) -> None:
        """Test stream-test endpoint uses GET method - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # Act - MANDATORY
        stream_test_route = next(
            (
                route
                for route in router.routes
                if isinstance(route, APIRoute) and route.path == "/stream-test"
            ),
            None,
        )

        # Assert - MANDATORY
        assert stream_test_route is not None
        assert "GET" in stream_test_route.methods


# ============================================================================
# Stream Test Endpoint Tests
# ============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
class TestHealthStreamTestEndpoint:
    """Tests for GET /stream-test endpoint."""

    async def test_health_stream_test_returns_dict(self) -> None:
        """Test health_stream_test returns dict - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # Act - MANDATORY
        result = await health_stream_test()

        # Assert - MANDATORY
        assert isinstance(result, dict)

    async def test_health_stream_test_has_message(self) -> None:
        """Test health_stream_test has message field - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # Act - MANDATORY
        result = await health_stream_test()

        # Assert - MANDATORY
        assert "message" in result
        assert result["message"] == "SSE endpoint test"

    async def test_health_stream_test_has_status(self) -> None:
        """Test health_stream_test has status field - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # Act - MANDATORY
        result = await health_stream_test()

        # Assert - MANDATORY
        assert "status" in result
        assert result["status"] == "ok"


# ============================================================================
# MANDATORY Performance Benchmarks
# ============================================================================


@pytest.mark.performance
@pytest.mark.unit
@pytest.mark.asyncio
class TestHealthStreamingPerformance:
    """MANDATORY performance tests for health streaming endpoints."""

    async def test_stream_test_endpoint_performance(self) -> None:
        """MANDATORY performance test - stream test endpoint speed."""
        # Arrange - MANDATORY
        iterations = 100

        # Act - MANDATORY
        start_time = time.perf_counter()

        for _ in range(iterations):
            await health_stream_test()

        end_time = time.perf_counter()
        execution_time = end_time - start_time

        # Assert - MANDATORY
        avg_time = execution_time / iterations
        assert avg_time < 0.005  # <5ms per call
        assert execution_time < 0.5  # Total <500ms for 100 calls
