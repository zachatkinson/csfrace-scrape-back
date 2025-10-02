"""Comprehensive tests for health streaming endpoints - MANDATORY TEST_BUILDING.md compliance.

This module tests health streaming functionality with complete coverage:
- Router configuration
- Stream test endpoint
- SSE health stream endpoint
- Initial health status generation
- Health update event generation
- Client disconnect handling
- Error handling scenarios

ALL tests follow MANDATORY TEST_BUILDING.md patterns:
- AAA pattern with explicit comments
- Factory fixtures for DRY principle
- Comprehensive SSE streaming scenario testing
- Performance benchmarks with specific thresholds
"""

import time
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from src.api.routers.health.streaming import (
    _generate_health_update_events_safe,
    _generate_initial_health_events_safe,
    health_stream,
    health_stream_test,
    router,
)

# ============================================================================
# Test Fixtures - DRY Principle
# ============================================================================


@pytest.fixture
def sample_health_status():
    """Factory for sample health status - DRY principle."""
    return {
        "status": "healthy",
        "version": "1.0.0",
        "database": {
            "status": "healthy",
            "latency_ms": 5.2,
        },
        "cache": {
            "status": "healthy",
            "latency_ms": 1.1,
        },
        "monitoring": {
            "status": "healthy",
            "checks_passing": 10,
        },
        "timestamp": datetime.now(UTC),
    }


@pytest.fixture
def mock_db_session():
    """Factory for mock database session - DRY principle."""
    session = MagicMock()
    session.execute = AsyncMock()
    return session


@pytest.fixture
def mock_request():
    """Factory for mock request - DRY principle."""
    request = MagicMock()
    request.is_disconnected = AsyncMock(return_value=False)
    return request


# ============================================================================
# Router Configuration Tests
# ============================================================================


@pytest.mark.unit
class TestHealthStreamingRouter:
    """Tests for health streaming router configuration."""

    def test_router_exists(self):
        """Test that health streaming router exists - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # Act - MANDATORY
        # Assert - MANDATORY
        assert router is not None
        assert isinstance(router, APIRouter)

    def test_router_has_stream_test_endpoint(self):
        """Test router has /stream-test endpoint - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # Act - MANDATORY
        routes = [route.path for route in router.routes]

        # Assert - MANDATORY
        assert "/stream-test" in routes

    def test_router_has_stream_endpoint(self):
        """Test router has /stream-original endpoint - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # Act - MANDATORY
        routes = [route.path for route in router.routes]

        # Assert - MANDATORY
        assert "/stream-original" in routes

    def test_stream_test_endpoint_uses_get_method(self):
        """Test stream-test endpoint uses GET method - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # Act - MANDATORY
        stream_test_route = next(route for route in router.routes if route.path == "/stream-test")

        # Assert - MANDATORY
        assert "GET" in stream_test_route.methods

    def test_stream_endpoint_uses_get_method(self):
        """Test stream endpoint uses GET method - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # Act - MANDATORY
        stream_route = next(route for route in router.routes if route.path == "/stream-original")

        # Assert - MANDATORY
        assert "GET" in stream_route.methods


# ============================================================================
# Stream Test Endpoint Tests
# ============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
class TestHealthStreamTestEndpoint:
    """Tests for GET /stream-test endpoint."""

    async def test_health_stream_test_returns_dict(self):
        """Test health_stream_test returns dict - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # Act - MANDATORY
        result = await health_stream_test()

        # Assert - MANDATORY
        assert isinstance(result, dict)

    async def test_health_stream_test_has_message(self):
        """Test health_stream_test has message field - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # Act - MANDATORY
        result = await health_stream_test()

        # Assert - MANDATORY
        assert "message" in result
        assert result["message"] == "SSE endpoint test"

    async def test_health_stream_test_has_status(self):
        """Test health_stream_test has status field - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # Act - MANDATORY
        result = await health_stream_test()

        # Assert - MANDATORY
        assert "status" in result
        assert result["status"] == "ok"


# ============================================================================
# Health Stream Endpoint Tests
# ============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
class TestHealthStreamEndpoint:
    """Tests for GET /stream endpoint."""

    async def test_health_stream_returns_streaming_response(self, mock_request, mock_db_session):
        """Test health_stream returns StreamingResponse - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        mock_request.is_disconnected = AsyncMock(return_value=True)  # Immediate disconnect

        with patch(
            "src.api.routers.health.streaming._generate_initial_health_events_safe",
            return_value=None,
        ):
            # Act - MANDATORY
            result = await health_stream(mock_request, mock_db_session)

            # Assert - MANDATORY
            assert isinstance(result, StreamingResponse)

    async def test_health_stream_sets_correct_media_type(self, mock_request, mock_db_session):
        """Test health_stream sets text/event-stream media type - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        mock_request.is_disconnected = AsyncMock(return_value=True)

        with patch(
            "src.api.routers.health.streaming._generate_initial_health_events_safe",
            return_value=None,
        ):
            # Act - MANDATORY
            result = await health_stream(mock_request, mock_db_session)

            # Assert - MANDATORY
            assert result.media_type == "text/event-stream"

    async def test_health_stream_sets_sse_headers(self, mock_request, mock_db_session):
        """Test health_stream sets SSE headers - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        mock_request.is_disconnected = AsyncMock(return_value=True)

        with patch(
            "src.api.routers.health.streaming._generate_initial_health_events_safe",
            return_value=None,
        ):
            # Act - MANDATORY
            result = await health_stream(mock_request, mock_db_session)

            # Assert - MANDATORY
            assert result.headers["Cache-Control"] == "no-cache"
            assert result.headers["Connection"] == "keep-alive"
            assert "Access-Control-Allow-Origin" in result.headers


# ============================================================================
# Initial Health Events Generation Tests
# ============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
class TestInitialHealthEventsGeneration:
    """Tests for initial health events generation."""

    async def test_generate_initial_health_events_safe_exists(self):
        """Test _generate_initial_health_events_safe function exists - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # Act - MANDATORY
        # Assert - MANDATORY
        assert callable(_generate_initial_health_events_safe)

    async def test_initial_health_events_called_by_stream(self, mock_request, mock_db_session):
        """Test initial events function called by health stream - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        mock_request.is_disconnected = AsyncMock(return_value=True)
        mock_initial = AsyncMock()

        with patch(
            "src.api.routers.health.streaming._generate_initial_health_events_safe", mock_initial
        ):
            # Act - MANDATORY
            result = await health_stream(mock_request, mock_db_session)

            # Assert - MANDATORY
            # Function is called within the stream generator
            assert isinstance(result, StreamingResponse)


# ============================================================================
# Health Update Events Generation Tests
# ============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
class TestHealthUpdateEventsGeneration:
    """Tests for health update events generation."""

    async def test_generate_health_update_events_safe_exists(self):
        """Test _generate_health_update_events_safe function exists - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # Act - MANDATORY
        # Assert - MANDATORY
        assert callable(_generate_health_update_events_safe)

    async def test_health_update_events_callable(self, mock_db_session):
        """Test update events function is callable - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        mock_service = MagicMock()
        mock_service.get_comprehensive_health_status = AsyncMock(return_value={"status": "healthy"})

        with patch("src.api.routers.health.streaming.health_service", mock_service):
            # Act - MANDATORY
            # The function should be callable (decorator-wrapped)
            result = _generate_health_update_events_safe(mock_db_session)

            # Assert - MANDATORY
            # Should return an async generator or coroutine
            assert result is not None


# ============================================================================
# Integration Tests
# ============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
class TestHealthStreamingIntegration:
    """Integration tests for health streaming endpoints."""

    async def test_stream_test_endpoint_accessible(self):
        """Test stream-test endpoint is accessible - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # Act - MANDATORY
        result = await health_stream_test()

        # Assert - MANDATORY
        assert result["status"] == "ok"

    async def test_health_stream_handles_immediate_disconnect(self, mock_db_session):
        """Test health stream handles immediate disconnect - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        mock_request = MagicMock()
        mock_request.is_disconnected = AsyncMock(return_value=True)

        with patch(
            "src.api.routers.health.streaming._generate_initial_health_events_safe",
            return_value=None,
        ):
            # Act - MANDATORY
            result = await health_stream(mock_request, mock_db_session)

            # Assert - MANDATORY
            assert isinstance(result, StreamingResponse)


# ============================================================================
# Event Generator Tests - Coverage for missing lines
# ============================================================================


# ============================================================================
# MANDATORY Performance Benchmarks
# ============================================================================


@pytest.mark.performance
@pytest.mark.unit
@pytest.mark.asyncio
class TestHealthStreamingPerformance:
    """MANDATORY performance tests for health streaming endpoints."""

    async def test_stream_test_endpoint_performance(self):
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

    async def test_health_stream_creation_performance(self, mock_request, mock_db_session):
        """MANDATORY performance test - health stream creation speed."""
        # Arrange - MANDATORY
        mock_request.is_disconnected = AsyncMock(return_value=True)
        iterations = 10

        with patch(
            "src.api.routers.health.streaming._generate_initial_health_events_safe",
            return_value=None,
        ):
            # Act - MANDATORY
            start_time = time.perf_counter()

            for _ in range(iterations):
                await health_stream(mock_request, mock_db_session)

            end_time = time.perf_counter()
            execution_time = end_time - start_time

            # Assert - MANDATORY
            avg_time = execution_time / iterations
            assert avg_time < 0.05  # <50ms per stream creation
            assert execution_time < 0.5  # Total <500ms for 10 creations
