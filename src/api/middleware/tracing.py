"""Tracing middleware that integrates custom performance monitoring with OpenTelemetry."""

import uuid
from collections.abc import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from ...monitoring import distributed_tracer, performance_monitor


class EnhancedTracingMiddleware(BaseHTTPMiddleware):  # pylint: disable=too-few-public-methods
    """Enhanced tracing middleware combining custom and OpenTelemetry tracing."""

    def __init__(self, app, correlation_header: str = "X-Correlation-ID"):
        """Initialize enhanced tracing middleware.

        Args:
            app: FastAPI application
            correlation_header: Header name for correlation IDs
        """
        super().__init__(app)
        self.correlation_header = correlation_header

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request with enhanced tracing.

        Args:
            request: Incoming HTTP request
            call_next: Next middleware/handler

        Returns:
            HTTP response
        """
        # Generate or extract correlation ID
        correlation_id = request.headers.get(self.correlation_header) or str(uuid.uuid4())

        # Extract request information
        method = request.method
        path = request.url.path
        endpoint = f"{method} {path}"

        # Start custom performance trace
        trace_metadata = {
            "correlation_id": correlation_id,
            "method": method,
            "path": path,
            "user_agent": request.headers.get("User-Agent"),
            "client_ip": getattr(request.client, "host", "unknown")
            if request.client
            else "unknown",
        }

        custom_trace_id = performance_monitor.start_trace(
            operation=endpoint, metadata=trace_metadata
        )

        # Create OpenTelemetry span attributes
        otel_attributes = {
            "http.method": method,
            "http.url": str(request.url),
            "http.scheme": request.url.scheme,
            "http.host": request.url.hostname or "unknown",
            "http.user_agent": request.headers.get("User-Agent", ""),
            "correlation_id": correlation_id,
        }

        # Start OpenTelemetry distributed trace
        async with distributed_tracer.trace_operation(
            operation_name=endpoint, attributes=otel_attributes
        ) as span:
            try:
                # Add correlation ID to response headers
                response = await call_next(request)
                response.headers[self.correlation_header] = correlation_id

                # Add trace ID to response headers if available
                trace_id = distributed_tracer.get_current_trace_id()
                if trace_id:
                    response.headers["X-Trace-ID"] = trace_id

                # Record successful completion
                if custom_trace_id:
                    performance_monitor.finish_trace(custom_trace_id, status="success")

                if span:
                    span.set_attribute("http.status_code", response.status_code)
                    span.set_attribute(
                        "response.size", len(response.body) if hasattr(response, "body") else 0
                    )

                return response

            except Exception as e:
                # Record error in custom trace
                if custom_trace_id:
                    performance_monitor.finish_trace(custom_trace_id, status="error", error=str(e))

                # Record error in OpenTelemetry span
                if span:
                    span.set_attribute("error", True)
                    span.set_attribute("error.message", str(e))
                    span.set_attribute("error.type", type(e).__name__)

                distributed_tracer.record_exception(e)

                raise


class CorrelationMiddleware(BaseHTTPMiddleware):  # pylint: disable=too-few-public-methods
    """Lightweight correlation ID middleware for requests without full tracing."""

    def __init__(self, app, correlation_header: str = "X-Correlation-ID"):
        """Initialize correlation middleware.

        Args:
            app: FastAPI application
            correlation_header: Header name for correlation IDs
        """
        super().__init__(app)
        self.correlation_header = correlation_header

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Add correlation ID to request/response.

        Args:
            request: Incoming HTTP request
            call_next: Next middleware/handler

        Returns:
            HTTP response with correlation ID
        """
        # Generate or extract correlation ID
        correlation_id = request.headers.get(self.correlation_header) or str(uuid.uuid4())

        # Add to OpenTelemetry context if available
        distributed_tracer.set_attribute("correlation.id", correlation_id)

        # Process request
        response = await call_next(request)

        # Add correlation ID to response
        response.headers[self.correlation_header] = correlation_id

        return response
