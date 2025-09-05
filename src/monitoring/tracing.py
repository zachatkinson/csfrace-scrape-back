"""OpenTelemetry distributed tracing integration for enhanced observability.

This module provides OpenTelemetry-compliant distributed tracing that integrates
with the existing monitoring infrastructure while following industry standards.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

try:
    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.instrumentation.aiohttp_client import AioHttpClientInstrumentor
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
    from opentelemetry.propagate import set_global_textmap
    from opentelemetry.propagators.b3 import B3MultiFormat
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

    OPENTELEMETRY_AVAILABLE = True
except ImportError:
    OPENTELEMETRY_AVAILABLE = False
    logger.warning("OpenTelemetry not available - distributed tracing disabled")
    trace = None  # type: ignore[assignment]


@dataclass
class TracingConfig:
    """Configuration for OpenTelemetry distributed tracing."""

    enabled: bool = True
    service_name: str = "csfrace-scraper"
    service_version: str = "2.2.2"
    environment: str = "production"

    # Export configuration
    export_to_console: bool = False  # For debugging
    export_to_jaeger: bool = False
    export_to_otlp: bool = False
    otlp_endpoint: str = "http://localhost:4317"

    # Sampling configuration
    sampling_rate: float = 1.0  # 1.0 = trace all requests

    # Auto-instrumentation
    instrument_fastapi: bool = True
    instrument_aiohttp: bool = True
    instrument_sqlalchemy: bool = True

    # Custom settings
    correlation_id_header: str = "X-Correlation-ID"
    trace_id_header: str = "X-Trace-ID"


class DistributedTracer:
    """OpenTelemetry-based distributed tracing manager."""

    def __init__(self, config: TracingConfig | None = None):
        """Initialize distributed tracer.

        Args:
            config: Tracing configuration
        """
        self.config = config or TracingConfig()
        self.tracer_provider: TracerProvider | None = None
        self.tracer: Any = None
        self._initialized = False

        if not OPENTELEMETRY_AVAILABLE:
            logger.warning("OpenTelemetry not available - distributed tracing disabled")
            return

        logger.info(
            "Distributed tracer initialized",
            enabled=self.config.enabled,
            service=self.config.service_name,
        )

    def initialize(self) -> None:
        """Initialize OpenTelemetry tracing infrastructure."""
        if not self.config.enabled or not OPENTELEMETRY_AVAILABLE or self._initialized:
            return

        logger.info("Initializing OpenTelemetry distributed tracing")

        try:
            # Create resource with service information
            resource = Resource.create(
                {
                    "service.name": self.config.service_name,
                    "service.version": self.config.service_version,
                    "deployment.environment": self.config.environment,
                    "telemetry.sdk.language": "python",
                    "telemetry.sdk.name": "opentelemetry",
                }
            )

            # Create tracer provider
            self.tracer_provider = TracerProvider(resource=resource)

            # Configure exporters
            if self.config.export_to_console:
                console_processor = BatchSpanProcessor(ConsoleSpanExporter())
                self.tracer_provider.add_span_processor(console_processor)
                logger.debug("Console span exporter configured")

            if self.config.export_to_otlp:
                otlp_exporter = OTLPSpanExporter(endpoint=self.config.otlp_endpoint)
                otlp_processor = BatchSpanProcessor(otlp_exporter)
                self.tracer_provider.add_span_processor(otlp_processor)
                logger.debug("OTLP span exporter configured", endpoint=self.config.otlp_endpoint)

            # Set global tracer provider
            trace.set_tracer_provider(self.tracer_provider)

            # Configure propagation (B3 format for compatibility)
            set_global_textmap(B3MultiFormat())

            # Get tracer
            self.tracer = trace.get_tracer(__name__)

            # Auto-instrument frameworks
            self._setup_auto_instrumentation()

            self._initialized = True
            logger.info("OpenTelemetry distributed tracing initialized successfully")

        except Exception as e:
            logger.error("Failed to initialize distributed tracing", error=str(e))
            raise

    def _setup_auto_instrumentation(self) -> None:
        """Setup automatic instrumentation for common frameworks."""
        if not OPENTELEMETRY_AVAILABLE:
            return

        try:
            # FastAPI instrumentation
            if self.config.instrument_fastapi:
                FastAPIInstrumentor().instrument()
                logger.debug("FastAPI auto-instrumentation enabled")

            # aiohttp client instrumentation
            if self.config.instrument_aiohttp:
                AioHttpClientInstrumentor().instrument()
                logger.debug("aiohttp client auto-instrumentation enabled")

            # SQLAlchemy instrumentation
            if self.config.instrument_sqlalchemy:
                SQLAlchemyInstrumentor().instrument()
                logger.debug("SQLAlchemy auto-instrumentation enabled")

        except Exception as e:
            logger.error("Failed to setup auto-instrumentation", error=str(e))

    @asynccontextmanager
    async def trace_operation(
        self,
        operation_name: str,
        attributes: dict[str, Any] | None = None,
        parent_context: Any | None = None,
    ) -> AsyncGenerator[Any]:
        """Create a distributed trace span for an async operation.

        Args:
            operation_name: Name of the operation being traced
            attributes: Additional attributes to attach to the span
            parent_context: Parent trace context

        Yields:
            OpenTelemetry span object
        """
        if not self._initialized or not self.tracer:
            # Fallback to no-op context if tracing not available
            yield None
            return

        attributes = attributes or {}

        with self.tracer.start_as_current_span(
            operation_name,
            attributes=attributes,
            context=parent_context,
        ) as span:
            try:
                # Add custom attributes
                span.set_attribute("operation.type", "async")

                # Add correlation ID if available
                correlation_id = attributes.get("correlation_id")
                if correlation_id:
                    span.set_attribute("correlation.id", correlation_id)

                logger.debug(
                    "Started distributed trace span",
                    operation=operation_name,
                    span_id=span.get_span_context().span_id,
                    trace_id=span.get_span_context().trace_id,
                )

                yield span

            except Exception as e:
                span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
                span.set_attribute("error.message", str(e))
                span.set_attribute("error.type", type(e).__name__)

                logger.error(
                    "Distributed trace span failed",
                    operation=operation_name,
                    error=str(e),
                )
                raise

    def trace_function(self, operation_name: str, attributes: dict[str, Any] | None = None):
        """Decorator for tracing synchronous functions.

        Args:
            operation_name: Name of the operation being traced
            attributes: Additional attributes to attach to the span

        Returns:
            Decorated function
        """

        def decorator(func):
            def wrapper(*args, **kwargs):
                if not self._initialized or not self.tracer:
                    return func(*args, **kwargs)

                span_attributes = attributes or {}
                span_attributes.update(
                    {
                        "function.name": func.__name__,
                        "function.module": func.__module__,
                    }
                )

                with self.tracer.start_as_current_span(
                    operation_name or func.__name__,
                    attributes=span_attributes,
                ) as span:
                    try:
                        result = func(*args, **kwargs)
                        span.set_status(trace.Status(trace.StatusCode.OK))
                        return result
                    except Exception as e:
                        span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
                        span.set_attribute("error.message", str(e))
                        span.set_attribute("error.type", type(e).__name__)
                        raise

            return wrapper

        return decorator

    def trace_async_function(self, operation_name: str, attributes: dict[str, Any] | None = None):
        """Decorator for tracing asynchronous functions.

        Args:
            operation_name: Name of the operation being traced
            attributes: Additional attributes to attach to the span

        Returns:
            Decorated async function
        """

        def decorator(func):
            async def wrapper(*args, **kwargs):
                if not self._initialized:
                    return await func(*args, **kwargs)

                async with self.trace_operation(
                    operation_name or func.__name__,
                    {
                        **(attributes or {}),
                        "function.name": func.__name__,
                        "function.module": func.__module__,
                    },
                ):
                    return await func(*args, **kwargs)

            return wrapper

        return decorator

    def get_current_trace_id(self) -> str | None:
        """Get the current trace ID if available.

        Returns:
            Current trace ID or None
        """
        if not self._initialized or not OPENTELEMETRY_AVAILABLE:
            return None

        try:
            current_span = trace.get_current_span()
            if current_span and current_span.is_recording():
                return format(current_span.get_span_context().trace_id, "032x")
        except Exception as e:
            logger.debug("Failed to get current trace ID", error=str(e))

        return None

    def get_current_span_id(self) -> str | None:
        """Get the current span ID if available.

        Returns:
            Current span ID or None
        """
        if not self._initialized or not OPENTELEMETRY_AVAILABLE:
            return None

        try:
            current_span = trace.get_current_span()
            if current_span and current_span.is_recording():
                return format(current_span.get_span_context().span_id, "016x")
        except Exception as e:
            logger.debug("Failed to get current span ID", error=str(e))

        return None

    def add_event(self, name: str, attributes: dict[str, Any] | None = None) -> None:
        """Add an event to the current span.

        Args:
            name: Event name
            attributes: Event attributes
        """
        if not self._initialized or not OPENTELEMETRY_AVAILABLE:
            return

        try:
            current_span = trace.get_current_span()
            if current_span and current_span.is_recording():
                current_span.add_event(name, attributes or {})
        except Exception as e:
            logger.debug("Failed to add span event", event=name, error=str(e))

    def set_attribute(self, key: str, value: Any) -> None:
        """Set an attribute on the current span.

        Args:
            key: Attribute key
            value: Attribute value
        """
        if not self._initialized or not OPENTELEMETRY_AVAILABLE:
            return

        try:
            current_span = trace.get_current_span()
            if current_span and current_span.is_recording():
                current_span.set_attribute(key, value)
        except Exception as e:
            logger.debug("Failed to set span attribute", key=key, error=str(e))

    def record_exception(self, exception: Exception) -> None:
        """Record an exception in the current span.

        Args:
            exception: Exception to record
        """
        if not self._initialized or not OPENTELEMETRY_AVAILABLE:
            return

        try:
            current_span = trace.get_current_span()
            if current_span and current_span.is_recording():
                current_span.record_exception(exception)
                current_span.set_status(trace.Status(trace.StatusCode.ERROR, str(exception)))
        except Exception as e:
            logger.debug("Failed to record exception in span", error=str(e))

    def shutdown(self) -> None:
        """Shutdown the distributed tracer."""
        if not self._initialized:
            return

        logger.info("Shutting down distributed tracer")

        try:
            if self.tracer_provider:
                self.tracer_provider.shutdown()

            self._initialized = False
            logger.info("Distributed tracer shutdown complete")

        except Exception as e:
            logger.error("Error during distributed tracer shutdown", error=str(e))

    def get_tracing_status(self) -> dict[str, Any]:
        """Get current tracing status and statistics.

        Returns:
            Tracing status information
        """
        return {
            "initialized": self._initialized,
            "opentelemetry_available": OPENTELEMETRY_AVAILABLE,
            "service_name": self.config.service_name,
            "service_version": self.config.service_version,
            "environment": self.config.environment,
            "sampling_rate": self.config.sampling_rate,
            "current_trace_id": self.get_current_trace_id(),
            "current_span_id": self.get_current_span_id(),
            "auto_instrumentation": {
                "fastapi": self.config.instrument_fastapi,
                "aiohttp": self.config.instrument_aiohttp,
                "sqlalchemy": self.config.instrument_sqlalchemy,
            },
            "exporters": {
                "console": self.config.export_to_console,
                "otlp": self.config.export_to_otlp,
                "jaeger": self.config.export_to_jaeger,
            },
        }


# Global distributed tracer instance
distributed_tracer = DistributedTracer()
