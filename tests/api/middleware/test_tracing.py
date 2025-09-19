"""Comprehensive tests for tracing middleware using DRY/SOLID principles."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI, Request
from starlette.responses import PlainTextResponse

from src.api.middleware.tracing import CorrelationMiddleware, EnhancedTracingMiddleware


class TestEnhancedTracingMiddlewareInitialization:
    """Test Enhanced Tracing Middleware initialization following SOLID principles."""

    def test_initialization_with_default_correlation_header(self):
        """Test middleware initialization with default correlation header."""
        app = FastAPI()
        middleware = EnhancedTracingMiddleware(app)

        assert middleware.correlation_header == "X-Correlation-ID"
        assert middleware.app == app

    def test_initialization_with_custom_correlation_header(self):
        """Test middleware initialization with custom correlation header."""
        app = FastAPI()
        custom_header = "X-Custom-Correlation"
        middleware = EnhancedTracingMiddleware(app, correlation_header=custom_header)

        assert middleware.correlation_header == custom_header
        assert middleware.app == app


class TestEnhancedTracingMiddlewareBasicFlow:
    """Test Enhanced Tracing Middleware basic request flow."""

    @pytest.fixture
    def mock_app(self):
        """Create mock FastAPI app for testing."""
        app = FastAPI()

        @app.get("/test")
        async def test_endpoint():
            return {"message": "test"}

        return app

    @pytest.fixture
    def mock_performance_monitor(self):
        """Mock performance monitor for testing."""
        with patch("src.api.middleware.tracing.performance_monitor") as mock:
            mock.start_trace.return_value = "test_trace_id"
            mock.finish_trace.return_value = None
            yield mock

    @pytest.fixture
    def mock_distributed_tracer(self):
        """Mock distributed tracer for testing."""
        with patch("src.api.middleware.tracing.distributed_tracer") as mock:
            mock.trace_operation.return_value.__aenter__ = AsyncMock(return_value=mock)
            mock.trace_operation.return_value.__aexit__ = AsyncMock(return_value=None)
            mock.get_current_trace_id.return_value = "otel_trace_id"
            mock.set_attribute.return_value = None
            mock.record_exception.return_value = None
            yield mock

    @pytest.mark.asyncio
    async def test_successful_request_processing(
        self, mock_app, mock_performance_monitor, mock_distributed_tracer
    ):
        """Test successful request processing with tracing."""
        middleware = EnhancedTracingMiddleware(mock_app)

        # Create mock request
        request = MagicMock(spec=Request)
        request.method = "GET"
        request.url.path = "/test"
        request.url = MagicMock()
        request.url.scheme = "http"
        request.url.hostname = "localhost"
        request.headers = {"User-Agent": "test-agent"}
        request.client = MagicMock()
        request.client.host = "127.0.0.1"

        # Create mock response
        expected_response = PlainTextResponse("OK")

        # Mock call_next
        call_next = AsyncMock(return_value=expected_response)

        # Execute middleware
        response = await middleware.dispatch(request, call_next)

        # Verify call_next was called
        call_next.assert_called_once_with(request)

        # Verify performance monitoring was started and finished
        mock_performance_monitor.start_trace.assert_called_once()
        mock_performance_monitor.finish_trace.assert_called_once()

        # Verify response headers contain correlation ID
        assert middleware.correlation_header in response.headers

        # Verify trace ID header is set
        assert "X-Trace-ID" in response.headers
        assert response.headers["X-Trace-ID"] == "otel_trace_id"

    @pytest.mark.asyncio
    async def test_request_with_existing_correlation_id(
        self, mock_app, mock_performance_monitor, mock_distributed_tracer
    ):
        """Test request processing with existing correlation ID."""
        middleware = EnhancedTracingMiddleware(mock_app)
        existing_correlation_id = "existing-12345"

        # Create mock request with existing correlation ID
        request = MagicMock(spec=Request)
        request.method = "POST"
        request.url.path = "/api/test"
        request.url = MagicMock()
        request.url.scheme = "https"
        request.url.hostname = "api.example.com"
        request.headers = {
            "X-Correlation-ID": existing_correlation_id,
            "User-Agent": "test-client/1.0",
        }
        request.client = MagicMock()
        request.client.host = "192.168.1.1"

        expected_response = PlainTextResponse("Created")
        call_next = AsyncMock(return_value=expected_response)

        response = await middleware.dispatch(request, call_next)

        # Verify existing correlation ID is preserved
        assert response.headers[middleware.correlation_header] == existing_correlation_id

        # Verify trace metadata includes correlation ID
        mock_performance_monitor.start_trace.assert_called_once()
        call_args = mock_performance_monitor.start_trace.call_args
        metadata = call_args.kwargs["metadata"]
        assert metadata["correlation_id"] == existing_correlation_id

    @pytest.mark.asyncio
    async def test_request_without_client_info(
        self, mock_app, mock_performance_monitor, mock_distributed_tracer
    ):
        """Test request processing when client info is unavailable."""
        middleware = EnhancedTracingMiddleware(mock_app)

        request = MagicMock(spec=Request)
        request.method = "GET"
        request.url.path = "/health"
        request.url = MagicMock()
        request.url.scheme = "http"
        request.url.hostname = None  # No hostname
        request.headers = {}  # No headers
        request.client = None  # No client info

        expected_response = PlainTextResponse("OK")
        call_next = AsyncMock(return_value=expected_response)

        response = await middleware.dispatch(request, call_next)

        # Should handle missing client info gracefully
        call_args = mock_performance_monitor.start_trace.call_args
        metadata = call_args.kwargs["metadata"]
        assert metadata["client_ip"] == "unknown"
        assert metadata["user_agent"] is None


class TestEnhancedTracingMiddlewareErrorHandling:
    """Test Enhanced Tracing Middleware error handling scenarios."""

    @pytest.fixture
    def mock_app(self):
        """Create mock FastAPI app that raises exceptions."""
        app = FastAPI()

        @app.get("/error")
        async def error_endpoint():
            raise ValueError("Test error")

        return app

    @pytest.fixture
    def mock_performance_monitor(self):
        """Mock performance monitor for error testing."""
        with patch("src.api.middleware.tracing.performance_monitor") as mock:
            mock.start_trace.return_value = "error_trace_id"
            mock.finish_trace.return_value = None
            yield mock

    @pytest.fixture
    def mock_distributed_tracer(self):
        """Mock distributed tracer for error testing."""
        with patch("src.api.middleware.tracing.distributed_tracer") as mock:
            span_mock = MagicMock()
            mock.trace_operation.return_value.__aenter__ = AsyncMock(return_value=span_mock)
            mock.trace_operation.return_value.__aexit__ = AsyncMock(return_value=None)
            mock.record_exception.return_value = None
            yield mock

    @pytest.mark.asyncio
    async def test_exception_handling_and_tracing(
        self, mock_app, mock_performance_monitor, mock_distributed_tracer
    ):
        """Test exception handling with proper trace recording."""
        middleware = EnhancedTracingMiddleware(mock_app)

        request = MagicMock(spec=Request)
        request.method = "GET"
        request.url.path = "/error"
        request.url = MagicMock()
        request.url.scheme = "http"
        request.url.hostname = "localhost"
        request.headers = {}
        request.client = MagicMock()
        request.client.host = "127.0.0.1"

        # Mock call_next to raise exception
        test_error = ValueError("Simulated error")
        call_next = AsyncMock(side_effect=test_error)

        # Should re-raise the exception
        with pytest.raises(ValueError, match="Simulated error"):
            await middleware.dispatch(request, call_next)

        # Verify error was recorded in performance monitor
        mock_performance_monitor.finish_trace.assert_called_once_with(
            "error_trace_id", status="error", error="Simulated error"
        )

        # Verify exception was recorded in distributed tracer
        mock_distributed_tracer.record_exception.assert_called_once_with(test_error)

    @pytest.mark.asyncio
    async def test_span_error_attributes_set(
        self, mock_app, mock_performance_monitor, mock_distributed_tracer
    ):
        """Test that span error attributes are properly set."""
        middleware = EnhancedTracingMiddleware(mock_app)

        request = MagicMock(spec=Request)
        request.method = "POST"
        request.url.path = "/api/fail"
        request.url = MagicMock()
        request.url.scheme = "https"
        request.url.hostname = "api.example.com"
        request.headers = {}
        request.client = MagicMock()
        request.client.host = "10.0.0.1"

        # Mock span from distributed tracer
        span_mock = MagicMock()
        mock_distributed_tracer.trace_operation.return_value.__aenter__ = AsyncMock(
            return_value=span_mock
        )

        test_error = RuntimeError("Runtime failure")
        call_next = AsyncMock(side_effect=test_error)

        with pytest.raises(RuntimeError):
            await middleware.dispatch(request, call_next)

        # Verify span error attributes
        span_mock.set_attribute.assert_any_call("error", True)
        span_mock.set_attribute.assert_any_call("error.message", "Runtime failure")
        span_mock.set_attribute.assert_any_call("error.type", "RuntimeError")

    @pytest.mark.asyncio
    async def test_no_trace_id_scenario(
        self, mock_app, mock_performance_monitor, mock_distributed_tracer
    ):
        """Test scenario where custom trace ID is None."""
        middleware = EnhancedTracingMiddleware(mock_app)

        # Mock performance monitor to return None trace ID
        mock_performance_monitor.start_trace.return_value = None

        request = MagicMock(spec=Request)
        request.method = "GET"
        request.url.path = "/test"
        request.url = MagicMock()
        request.url.scheme = "http"
        request.url.hostname = "localhost"
        request.headers = {}
        request.client = MagicMock()
        request.client.host = "127.0.0.1"

        expected_response = PlainTextResponse("OK")
        call_next = AsyncMock(return_value=expected_response)

        response = await middleware.dispatch(request, call_next)

        # Should not call finish_trace when trace_id is None
        mock_performance_monitor.finish_trace.assert_not_called()

        # But response should still be processed
        assert response == expected_response


class TestCorrelationMiddlewareInitialization:
    """Test Correlation Middleware initialization following SOLID principles."""

    def test_initialization_with_default_header(self):
        """Test correlation middleware initialization with default header."""
        app = FastAPI()
        middleware = CorrelationMiddleware(app)

        assert middleware.correlation_header == "X-Correlation-ID"
        assert middleware.app == app

    def test_initialization_with_custom_header(self):
        """Test correlation middleware initialization with custom header."""
        app = FastAPI()
        custom_header = "X-Request-ID"
        middleware = CorrelationMiddleware(app, correlation_header=custom_header)

        assert middleware.correlation_header == custom_header
        assert middleware.app == app


class TestCorrelationMiddlewareBasicFlow:
    """Test Correlation Middleware basic request flow."""

    @pytest.fixture
    def mock_app(self):
        """Create mock FastAPI app for correlation testing."""
        app = FastAPI()

        @app.get("/test")
        async def test_endpoint():
            return {"message": "test"}

        return app

    @pytest.fixture
    def mock_distributed_tracer(self):
        """Mock distributed tracer for correlation testing."""
        with patch("src.api.middleware.tracing.distributed_tracer") as mock:
            mock.set_attribute.return_value = None
            yield mock

    @pytest.mark.asyncio
    async def test_correlation_id_generation(self, mock_app, mock_distributed_tracer):
        """Test correlation ID generation for requests without existing ID."""
        middleware = CorrelationMiddleware(mock_app)

        request = MagicMock(spec=Request)
        request.headers = {}  # No existing correlation ID

        expected_response = PlainTextResponse("OK")
        call_next = AsyncMock(return_value=expected_response)

        with patch("uuid.uuid4") as mock_uuid:
            mock_uuid.return_value = "generated-uuid-123"

            response = await middleware.dispatch(request, call_next)

        # Should generate and set correlation ID
        assert response.headers["X-Correlation-ID"] == "generated-uuid-123"

        # Should set attribute in distributed tracer
        mock_distributed_tracer.set_attribute.assert_called_once_with(
            "correlation.id", "generated-uuid-123"
        )

    @pytest.mark.asyncio
    async def test_correlation_id_preservation(self, mock_app, mock_distributed_tracer):
        """Test correlation ID preservation from existing request header."""
        middleware = CorrelationMiddleware(mock_app)
        existing_id = "existing-correlation-456"

        request = MagicMock(spec=Request)
        request.headers = {"X-Correlation-ID": existing_id}

        expected_response = PlainTextResponse("OK")
        call_next = AsyncMock(return_value=expected_response)

        response = await middleware.dispatch(request, call_next)

        # Should preserve existing correlation ID
        assert response.headers["X-Correlation-ID"] == existing_id

        # Should set attribute in distributed tracer
        mock_distributed_tracer.set_attribute.assert_called_once_with("correlation.id", existing_id)

    @pytest.mark.asyncio
    async def test_custom_correlation_header(self, mock_app, mock_distributed_tracer):
        """Test correlation middleware with custom header name."""
        custom_header = "X-Request-Tracking-ID"
        middleware = CorrelationMiddleware(mock_app, correlation_header=custom_header)

        request = MagicMock(spec=Request)
        request.headers = {custom_header: "custom-tracking-789"}

        expected_response = PlainTextResponse("OK")
        call_next = AsyncMock(return_value=expected_response)

        response = await middleware.dispatch(request, call_next)

        # Should use custom header name
        assert response.headers[custom_header] == "custom-tracking-789"

        # Should set attribute in distributed tracer
        mock_distributed_tracer.set_attribute.assert_called_once_with(
            "correlation.id", "custom-tracking-789"
        )


class TestMiddlewareIntegration:
    """Test middleware integration scenarios and edge cases."""

    @pytest.fixture
    def app_with_middleware(self):
        """Create FastAPI app with both middleware components."""
        app = FastAPI()

        @app.get("/api/users")
        async def get_users():
            return {"users": []}

        @app.post("/api/users")
        async def create_user():
            return {"id": 1, "name": "Test User"}

        return app

    def test_middleware_compatibility(self, app_with_middleware):
        """Test that both middleware classes can be used together."""
        # Should be able to instantiate both without conflicts
        enhanced_middleware = EnhancedTracingMiddleware(app_with_middleware)
        correlation_middleware = CorrelationMiddleware(app_with_middleware)

        assert enhanced_middleware.correlation_header == correlation_middleware.correlation_header
        assert enhanced_middleware.app == correlation_middleware.app == app_with_middleware

    @pytest.mark.asyncio
    async def test_correlation_id_consistency(self, app_with_middleware):
        """Test correlation ID consistency between different middleware."""
        enhanced_middleware = EnhancedTracingMiddleware(app_with_middleware)
        correlation_middleware = CorrelationMiddleware(app_with_middleware)

        # Use same correlation ID across both middleware
        test_correlation_id = "consistent-id-abc"

        request = MagicMock(spec=Request)
        request.method = "GET"
        request.url.path = "/api/users"
        request.url = MagicMock()
        request.url.scheme = "http"
        request.url.hostname = "localhost"
        request.headers = {"X-Correlation-ID": test_correlation_id}
        request.client = MagicMock()
        request.client.host = "127.0.0.1"

        expected_response = PlainTextResponse('{"users": []}')
        call_next = AsyncMock(return_value=expected_response)

        with (
            patch("src.api.middleware.tracing.performance_monitor"),
            patch("src.api.middleware.tracing.distributed_tracer") as mock_tracer,
        ):
            # Configure mock span properly to avoid AsyncMock warnings
            span_mock = MagicMock()
            span_mock.set_attribute = MagicMock()  # Ensure set_attribute is sync
            mock_tracer.trace_operation.return_value.__aenter__ = AsyncMock(return_value=span_mock)
            mock_tracer.trace_operation.return_value.__aexit__ = AsyncMock(return_value=None)
            mock_tracer.get_current_trace_id.return_value = "trace123"
            mock_tracer.set_attribute.return_value = None

            # Both middleware should handle the same correlation ID
            enhanced_response = await enhanced_middleware.dispatch(request, call_next)
            correlation_response = await correlation_middleware.dispatch(request, call_next)

            assert enhanced_response.headers["X-Correlation-ID"] == test_correlation_id
            assert correlation_response.headers["X-Correlation-ID"] == test_correlation_id

    @pytest.mark.asyncio
    async def test_response_body_size_calculation(self, app_with_middleware):
        """Test response body size calculation in enhanced tracing."""
        middleware = EnhancedTracingMiddleware(app_with_middleware)

        request = MagicMock(spec=Request)
        request.method = "GET"
        request.url.path = "/api/test"
        request.url = MagicMock()
        request.url.scheme = "http"
        request.url.hostname = "localhost"
        request.headers = {}
        request.client = MagicMock()
        request.client.host = "127.0.0.1"

        # Mock response with body attribute
        response_with_body = MagicMock()
        response_with_body.status_code = 200
        response_with_body.body = b'{"test": "data"}'
        response_with_body.headers = {}

        call_next = AsyncMock(return_value=response_with_body)

        with (
            patch("src.api.middleware.tracing.performance_monitor"),
            patch("src.api.middleware.tracing.distributed_tracer") as mock_tracer,
        ):
            span_mock = MagicMock()
            mock_tracer.trace_operation.return_value.__aenter__ = AsyncMock(return_value=span_mock)
            mock_tracer.get_current_trace_id.return_value = "trace123"

            await middleware.dispatch(request, call_next)

            # Should set response size attribute
            span_mock.set_attribute.assert_any_call("response.size", len(b'{"test": "data"}'))

    @pytest.mark.asyncio
    async def test_response_without_body_attribute(self, app_with_middleware):
        """Test response handling when body attribute is missing."""
        middleware = EnhancedTracingMiddleware(app_with_middleware)

        request = MagicMock(spec=Request)
        request.method = "GET"
        request.url.path = "/api/test"
        request.url = MagicMock()
        request.url.scheme = "http"
        request.url.hostname = "localhost"
        request.headers = {}
        request.client = MagicMock()
        request.client.host = "127.0.0.1"

        # Mock response without body attribute
        response_without_body = MagicMock()
        response_without_body.status_code = 204
        response_without_body.headers = {}
        del response_without_body.body  # Remove body attribute

        call_next = AsyncMock(return_value=response_without_body)

        with (
            patch("src.api.middleware.tracing.performance_monitor"),
            patch("src.api.middleware.tracing.distributed_tracer") as mock_tracer,
        ):
            span_mock = MagicMock()
            mock_tracer.trace_operation.return_value.__aenter__ = AsyncMock(return_value=span_mock)
            mock_tracer.get_current_trace_id.return_value = "trace456"

            await middleware.dispatch(request, call_next)

            # Should set response size to 0 when no body attribute
            span_mock.set_attribute.assert_any_call("response.size", 0)


class TestMiddlewareErrorEdgeCases:
    """Test middleware error handling edge cases and boundary conditions."""

    @pytest.fixture
    def mock_app(self):
        """Create mock app for edge case testing."""
        return FastAPI()

    @pytest.mark.asyncio
    async def test_none_span_handling(self, mock_app):
        """Test handling when OpenTelemetry span is None."""
        middleware = EnhancedTracingMiddleware(mock_app)

        request = MagicMock(spec=Request)
        request.method = "GET"
        request.url.path = "/test"
        request.url = MagicMock()
        request.url.scheme = "http"
        request.url.hostname = "localhost"
        request.headers = {}
        request.client = MagicMock()
        request.client.host = "127.0.0.1"

        expected_response = PlainTextResponse("OK")
        call_next = AsyncMock(return_value=expected_response)

        with (
            patch("src.api.middleware.tracing.performance_monitor"),
            patch("src.api.middleware.tracing.distributed_tracer") as mock_tracer,
        ):
            # Return None span
            mock_tracer.trace_operation.return_value.__aenter__ = AsyncMock(return_value=None)
            mock_tracer.get_current_trace_id.return_value = None

            response = await middleware.dispatch(request, call_next)

            # Should handle None span gracefully
            assert response == expected_response

    @pytest.mark.asyncio
    async def test_none_span_error_handling(self, mock_app):
        """Test error handling when OpenTelemetry span is None."""
        middleware = EnhancedTracingMiddleware(mock_app)

        request = MagicMock(spec=Request)
        request.method = "GET"
        request.url.path = "/error"
        request.url = MagicMock()
        request.url.scheme = "http"
        request.url.hostname = "localhost"
        request.headers = {}
        request.client = MagicMock()
        request.client.host = "127.0.0.1"

        test_error = RuntimeError("Test error")
        call_next = AsyncMock(side_effect=test_error)

        with (
            patch("src.api.middleware.tracing.performance_monitor"),
            patch("src.api.middleware.tracing.distributed_tracer") as mock_tracer,
        ):
            # Return None span
            mock_tracer.trace_operation.return_value.__aenter__ = AsyncMock(return_value=None)

            with pytest.raises(RuntimeError):
                await middleware.dispatch(request, call_next)

            # Should record exception even with None span
            mock_tracer.record_exception.assert_called_once_with(test_error)

    @pytest.mark.asyncio
    async def test_uuid_generation_edge_cases(self, mock_app):
        """Test UUID generation edge cases."""
        middleware = CorrelationMiddleware(mock_app)

        with (
            patch("src.api.middleware.tracing.distributed_tracer"),
            patch("uuid.uuid4") as mock_uuid,
        ):
            # Test multiple UUID generations separately
            mock_uuid.return_value = "uuid-1"
            request1 = MagicMock(spec=Request)
            request1.headers = {}
            call_next1 = AsyncMock(return_value=PlainTextResponse("OK"))
            response1 = await middleware.dispatch(request1, call_next1)

            mock_uuid.return_value = "uuid-2"
            request2 = MagicMock(spec=Request)
            request2.headers = {}
            call_next2 = AsyncMock(return_value=PlainTextResponse("OK"))
            response2 = await middleware.dispatch(request2, call_next2)

            mock_uuid.return_value = "uuid-3"
            request3 = MagicMock(spec=Request)
            request3.headers = {}
            call_next3 = AsyncMock(return_value=PlainTextResponse("OK"))
            response3 = await middleware.dispatch(request3, call_next3)

            # Each request should get unique correlation ID
            assert response1.headers["X-Correlation-ID"] == "uuid-1"
            assert response2.headers["X-Correlation-ID"] == "uuid-2"
            assert response3.headers["X-Correlation-ID"] == "uuid-3"

            assert mock_uuid.call_count == 3
