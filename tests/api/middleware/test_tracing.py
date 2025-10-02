"""Comprehensive tests for tracing middleware - MANDATORY TEST_BUILDING.md compliance.

This module tests tracing middleware functionality with complete coverage:
- EnhancedTracingMiddleware correlation ID handling
- EnhancedTracingMiddleware performance tracing integration
- EnhancedTracingMiddleware OpenTelemetry integration
- CorrelationMiddleware lightweight correlation tracking
- Error handling and exception recording
- Header propagation
- Performance benchmarks

ALL tests follow MANDATORY TEST_BUILDING.md patterns:
- AAA pattern with explicit comments
- Factory fixtures for DRY principle
- Comprehensive middleware scenario testing
- Performance benchmarks with specific thresholds
"""

import time
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI, Request, Response

from src.api.middleware.tracing import CorrelationMiddleware, EnhancedTracingMiddleware

# ============================================================================
# Test Fixtures - DRY Principle
# ============================================================================


@pytest.fixture
def mock_performance_monitor():
    """Factory for mock performance monitor - DRY principle."""
    monitor = MagicMock()
    monitor.start_trace.return_value = "trace_id_12345"
    monitor.finish_trace.return_value = None
    return monitor


@pytest.fixture
def mock_distributed_tracer():
    """Factory for mock distributed tracer - DRY principle."""
    tracer = MagicMock()
    tracer.trace_operation.return_value.__aenter__ = AsyncMock(return_value=MagicMock())
    tracer.trace_operation.return_value.__aexit__ = AsyncMock(return_value=None)
    tracer.get_current_trace_id.return_value = "otel_trace_abc123"
    tracer.set_attribute.return_value = None
    tracer.record_exception.return_value = None
    return tracer


@pytest.fixture
def mock_request():
    """Factory for mock HTTP request - DRY principle."""
    request = MagicMock(spec=Request)
    request.method = "GET"
    request.url.path = "/api/test"
    request.url.scheme = "http"
    request.url.hostname = "localhost"
    request.url.__str__ = MagicMock(return_value="http://localhost/api/test")
    request.headers = {"User-Agent": "test-client/1.0"}
    request.client = MagicMock()
    request.client.host = "127.0.0.1"
    return request


@pytest.fixture
def mock_response():
    """Factory for mock HTTP response - DRY principle."""
    response = MagicMock(spec=Response)
    response.status_code = 200
    response.headers = {}
    response.body = b"test response body"
    return response


@pytest.fixture
def test_app():
    """Factory for test FastAPI application - DRY principle."""
    app = FastAPI()

    @app.get("/test")
    async def test_endpoint():
        return {"message": "test"}

    @app.get("/error")
    async def error_endpoint():
        raise ValueError("Test error")

    return app


# ============================================================================
# EnhancedTracingMiddleware Tests
# ============================================================================


@pytest.mark.unit
class TestEnhancedTracingMiddleware:
    """Tests for EnhancedTracingMiddleware class."""

    def test_initialization(self):
        """Test middleware initialization - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        app = FastAPI()

        # Act - MANDATORY
        middleware = EnhancedTracingMiddleware(app)

        # Assert - MANDATORY
        assert middleware.correlation_header == "X-Correlation-ID"
        assert middleware.app == app

    def test_initialization_custom_correlation_header(self):
        """Test middleware with custom correlation header - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        app = FastAPI()
        custom_header = "X-Custom-Correlation"

        # Act - MANDATORY
        middleware = EnhancedTracingMiddleware(app, correlation_header=custom_header)

        # Assert - MANDATORY
        assert middleware.correlation_header == custom_header

    @pytest.mark.asyncio
    async def test_dispatch_generates_correlation_id(
        self, mock_request, mock_response, mock_performance_monitor, mock_distributed_tracer
    ):
        """Test dispatch generates correlation ID - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        app = FastAPI()
        middleware = EnhancedTracingMiddleware(app)
        call_next = AsyncMock(return_value=mock_response)

        with (
            patch("src.api.middleware.tracing.performance_monitor", mock_performance_monitor),
            patch("src.api.middleware.tracing.distributed_tracer", mock_distributed_tracer),
        ):
            # Act - MANDATORY
            response = await middleware.dispatch(mock_request, call_next)

            # Assert - MANDATORY
            assert "X-Correlation-ID" in response.headers
            # Verify it's a valid UUID
            correlation_id = response.headers["X-Correlation-ID"]
            uuid.UUID(correlation_id)  # Should not raise

    @pytest.mark.asyncio
    async def test_dispatch_preserves_existing_correlation_id(
        self, mock_request, mock_response, mock_performance_monitor, mock_distributed_tracer
    ):
        """Test dispatch preserves existing correlation ID - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        existing_id = "existing-correlation-123"
        mock_request.headers["X-Correlation-ID"] = existing_id
        app = FastAPI()
        middleware = EnhancedTracingMiddleware(app)
        call_next = AsyncMock(return_value=mock_response)

        with (
            patch("src.api.middleware.tracing.performance_monitor", mock_performance_monitor),
            patch("src.api.middleware.tracing.distributed_tracer", mock_distributed_tracer),
        ):
            # Act - MANDATORY
            response = await middleware.dispatch(mock_request, call_next)

            # Assert - MANDATORY
            assert response.headers["X-Correlation-ID"] == existing_id

    @pytest.mark.asyncio
    async def test_dispatch_starts_performance_trace(
        self, mock_request, mock_response, mock_performance_monitor, mock_distributed_tracer
    ):
        """Test dispatch starts performance trace - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        app = FastAPI()
        middleware = EnhancedTracingMiddleware(app)
        call_next = AsyncMock(return_value=mock_response)

        with (
            patch("src.api.middleware.tracing.performance_monitor", mock_performance_monitor),
            patch("src.api.middleware.tracing.distributed_tracer", mock_distributed_tracer),
        ):
            # Act - MANDATORY
            await middleware.dispatch(mock_request, call_next)

            # Assert - MANDATORY
            mock_performance_monitor.start_trace.assert_called_once()
            call_args = mock_performance_monitor.start_trace.call_args
            assert call_args[1]["operation"] == "GET /api/test"
            assert "correlation_id" in call_args[1]["metadata"]

    @pytest.mark.asyncio
    async def test_dispatch_finishes_trace_on_success(
        self, mock_request, mock_response, mock_performance_monitor, mock_distributed_tracer
    ):
        """Test dispatch finishes trace on success - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        app = FastAPI()
        middleware = EnhancedTracingMiddleware(app)
        call_next = AsyncMock(return_value=mock_response)

        with (
            patch("src.api.middleware.tracing.performance_monitor", mock_performance_monitor),
            patch("src.api.middleware.tracing.distributed_tracer", mock_distributed_tracer),
        ):
            # Act - MANDATORY
            await middleware.dispatch(mock_request, call_next)

            # Assert - MANDATORY
            mock_performance_monitor.finish_trace.assert_called_once_with(
                "trace_id_12345", status="success"
            )

    @pytest.mark.asyncio
    async def test_dispatch_adds_trace_id_to_response(
        self, mock_request, mock_response, mock_performance_monitor, mock_distributed_tracer
    ):
        """Test dispatch adds OpenTelemetry trace ID - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        app = FastAPI()
        middleware = EnhancedTracingMiddleware(app)
        call_next = AsyncMock(return_value=mock_response)

        with (
            patch("src.api.middleware.tracing.performance_monitor", mock_performance_monitor),
            patch("src.api.middleware.tracing.distributed_tracer", mock_distributed_tracer),
        ):
            # Act - MANDATORY
            response = await middleware.dispatch(mock_request, call_next)

            # Assert - MANDATORY
            assert "X-Trace-ID" in response.headers
            assert response.headers["X-Trace-ID"] == "otel_trace_abc123"

    @pytest.mark.asyncio
    async def test_dispatch_handles_error(
        self, mock_request, mock_performance_monitor, mock_distributed_tracer
    ):
        """Test dispatch handles errors - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        app = FastAPI()
        middleware = EnhancedTracingMiddleware(app)
        test_error = ValueError("Test error")
        call_next = AsyncMock(side_effect=test_error)

        with (
            patch("src.api.middleware.tracing.performance_monitor", mock_performance_monitor),
            patch("src.api.middleware.tracing.distributed_tracer", mock_distributed_tracer),
        ):
            # Act - MANDATORY
            with pytest.raises(ValueError):
                await middleware.dispatch(mock_request, call_next)

            # Assert - MANDATORY
            mock_performance_monitor.finish_trace.assert_called_once()
            call_args = mock_performance_monitor.finish_trace.call_args[1]
            assert call_args["status"] == "error"
            assert "Test error" in call_args["error"]

    @pytest.mark.asyncio
    async def test_dispatch_records_exception_in_otel(
        self, mock_request, mock_performance_monitor, mock_distributed_tracer
    ):
        """Test dispatch records exception in OpenTelemetry - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        app = FastAPI()
        middleware = EnhancedTracingMiddleware(app)
        test_error = ValueError("Test error")
        call_next = AsyncMock(side_effect=test_error)

        with (
            patch("src.api.middleware.tracing.performance_monitor", mock_performance_monitor),
            patch("src.api.middleware.tracing.distributed_tracer", mock_distributed_tracer),
        ):
            # Act - MANDATORY
            with pytest.raises(ValueError):
                await middleware.dispatch(mock_request, call_next)

            # Assert - MANDATORY
            mock_distributed_tracer.record_exception.assert_called_once_with(test_error)

    @pytest.mark.asyncio
    async def test_dispatch_client_ip_extraction(
        self, mock_response, mock_performance_monitor, mock_distributed_tracer
    ):
        """Test client IP extraction - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        app = FastAPI()
        middleware = EnhancedTracingMiddleware(app)
        mock_request = MagicMock(spec=Request)
        mock_request.method = "POST"
        mock_request.url.path = "/api/endpoint"
        mock_request.url.scheme = "https"
        mock_request.url.hostname = "api.example.com"
        mock_request.url.__str__ = MagicMock(return_value="https://api.example.com/api/endpoint")
        mock_request.headers = {"User-Agent": "custom-agent"}
        mock_request.client = MagicMock()
        mock_request.client.host = "192.168.1.100"
        call_next = AsyncMock(return_value=mock_response)

        with (
            patch("src.api.middleware.tracing.performance_monitor", mock_performance_monitor),
            patch("src.api.middleware.tracing.distributed_tracer", mock_distributed_tracer),
        ):
            # Act - MANDATORY
            await middleware.dispatch(mock_request, call_next)

            # Assert - MANDATORY
            call_args = mock_performance_monitor.start_trace.call_args
            metadata = call_args[1]["metadata"]
            assert metadata["client_ip"] == "192.168.1.100"


# ============================================================================
# CorrelationMiddleware Tests
# ============================================================================


@pytest.mark.unit
class TestCorrelationMiddleware:
    """Tests for CorrelationMiddleware class."""

    def test_initialization(self):
        """Test middleware initialization - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        app = FastAPI()

        # Act - MANDATORY
        middleware = CorrelationMiddleware(app)

        # Assert - MANDATORY
        assert middleware.correlation_header == "X-Correlation-ID"
        assert middleware.app == app

    def test_initialization_custom_header(self):
        """Test middleware with custom header - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        app = FastAPI()
        custom_header = "X-Request-ID"

        # Act - MANDATORY
        middleware = CorrelationMiddleware(app, correlation_header=custom_header)

        # Assert - MANDATORY
        assert middleware.correlation_header == custom_header

    @pytest.mark.asyncio
    async def test_dispatch_generates_correlation_id(
        self, mock_request, mock_response, mock_distributed_tracer
    ):
        """Test dispatch generates correlation ID - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        app = FastAPI()
        middleware = CorrelationMiddleware(app)
        call_next = AsyncMock(return_value=mock_response)

        with patch("src.api.middleware.tracing.distributed_tracer", mock_distributed_tracer):
            # Act - MANDATORY
            response = await middleware.dispatch(mock_request, call_next)

            # Assert - MANDATORY
            assert "X-Correlation-ID" in response.headers
            # Verify it's a valid UUID
            correlation_id = response.headers["X-Correlation-ID"]
            uuid.UUID(correlation_id)  # Should not raise

    @pytest.mark.asyncio
    async def test_dispatch_preserves_existing_correlation_id(
        self, mock_request, mock_response, mock_distributed_tracer
    ):
        """Test dispatch preserves existing ID - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        existing_id = "preserved-correlation-456"
        mock_request.headers["X-Correlation-ID"] = existing_id
        app = FastAPI()
        middleware = CorrelationMiddleware(app)
        call_next = AsyncMock(return_value=mock_response)

        with patch("src.api.middleware.tracing.distributed_tracer", mock_distributed_tracer):
            # Act - MANDATORY
            response = await middleware.dispatch(mock_request, call_next)

            # Assert - MANDATORY
            assert response.headers["X-Correlation-ID"] == existing_id

    @pytest.mark.asyncio
    async def test_dispatch_sets_otel_attribute(
        self, mock_request, mock_response, mock_distributed_tracer
    ):
        """Test dispatch sets OpenTelemetry attribute - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        app = FastAPI()
        middleware = CorrelationMiddleware(app)
        call_next = AsyncMock(return_value=mock_response)

        with patch("src.api.middleware.tracing.distributed_tracer", mock_distributed_tracer):
            # Act - MANDATORY
            await middleware.dispatch(mock_request, call_next)

            # Assert - MANDATORY
            mock_distributed_tracer.set_attribute.assert_called_once()
            call_args = mock_distributed_tracer.set_attribute.call_args[0]
            assert call_args[0] == "correlation.id"


# ============================================================================
# MANDATORY Performance Benchmarks
# ============================================================================


@pytest.mark.performance
@pytest.mark.unit
class TestTracingMiddlewarePerformance:
    """MANDATORY performance tests for tracing middleware."""

    @pytest.mark.asyncio
    async def test_enhanced_tracing_middleware_performance(
        self, mock_request, mock_response, mock_performance_monitor, mock_distributed_tracer
    ):
        """MANDATORY performance test - enhanced middleware overhead."""
        # Arrange - MANDATORY
        app = FastAPI()
        middleware = EnhancedTracingMiddleware(app)
        call_next = AsyncMock(return_value=mock_response)
        iterations = 100

        with (
            patch("src.api.middleware.tracing.performance_monitor", mock_performance_monitor),
            patch("src.api.middleware.tracing.distributed_tracer", mock_distributed_tracer),
        ):
            # Act - MANDATORY
            start_time = time.perf_counter()

            for _ in range(iterations):
                await middleware.dispatch(mock_request, call_next)

            end_time = time.perf_counter()
            execution_time = end_time - start_time

        # Assert - MANDATORY
        avg_time = execution_time / iterations
        assert avg_time < 0.01  # <10ms per request overhead
        assert execution_time < 1.0  # Total <1s for 100 requests

    @pytest.mark.asyncio
    async def test_correlation_middleware_performance(
        self, mock_request, mock_response, mock_distributed_tracer
    ):
        """MANDATORY performance test - correlation middleware overhead."""
        # Arrange - MANDATORY
        app = FastAPI()
        middleware = CorrelationMiddleware(app)
        call_next = AsyncMock(return_value=mock_response)
        iterations = 100

        with patch("src.api.middleware.tracing.distributed_tracer", mock_distributed_tracer):
            # Act - MANDATORY
            start_time = time.perf_counter()

            for _ in range(iterations):
                await middleware.dispatch(mock_request, call_next)

            end_time = time.perf_counter()
            execution_time = end_time - start_time

        # Assert - MANDATORY
        avg_time = execution_time / iterations
        assert avg_time < 0.005  # <5ms per request overhead
        assert execution_time < 0.5  # Total <500ms for 100 requests
