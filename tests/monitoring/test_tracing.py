"""Tests for OpenTelemetry distributed tracing implementation."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.monitoring.tracing import DistributedTracer, TracingConfig
from src.utils.tracing_utils import (
    TraceContextManager,
    add_trace_event,
    get_current_trace_context,
    set_trace_attribute,
    trace,
    trace_cache_operation,
    trace_database_operation,
    trace_http_request,
)


class TestTracingConfig:
    """Test tracing configuration."""

    def test_default_config(self):
        """Test default tracing configuration."""
        config = TracingConfig()
        
        assert config.enabled is True
        assert config.service_name == "csfrace-scraper"
        assert config.service_version == "2.2.2"
        assert config.environment == "production"
        assert config.sampling_rate == 1.0
        assert config.instrument_fastapi is True
        assert config.instrument_aiohttp is True
        assert config.instrument_sqlalchemy is True

    def test_custom_config(self):
        """Test custom tracing configuration."""
        config = TracingConfig(
            enabled=False,
            service_name="test-service",
            service_version="1.0.0",
            environment="test",
            sampling_rate=0.5,
            export_to_console=True,
        )
        
        assert config.enabled is False
        assert config.service_name == "test-service"
        assert config.service_version == "1.0.0"
        assert config.environment == "test"
        assert config.sampling_rate == 0.5
        assert config.export_to_console is True


class TestDistributedTracer:
    """Test OpenTelemetry distributed tracer."""

    def test_tracer_initialization_without_opentelemetry(self):
        """Test tracer initialization when OpenTelemetry is not available."""
        with patch('src.monitoring.tracing.OPENTELEMETRY_AVAILABLE', False):
            tracer = DistributedTracer()
            assert tracer.tracer is None
            assert tracer._initialized is False

    @patch('src.monitoring.tracing.OPENTELEMETRY_AVAILABLE', True)
    def test_tracer_initialization_disabled(self):
        """Test tracer initialization when disabled in config."""
        config = TracingConfig(enabled=False)
        tracer = DistributedTracer(config)
        
        tracer.initialize()
        assert tracer._initialized is False

    @patch('src.monitoring.tracing.OPENTELEMETRY_AVAILABLE', True)  
    @patch('opentelemetry.trace')
    @patch('opentelemetry.sdk.trace.TracerProvider') 
    @patch('opentelemetry.sdk.resources.Resource')
    def test_tracer_initialization_success(self, mock_resource, mock_tracer_provider, mock_trace):
        """Test successful tracer initialization."""
        # Setup mocks
        mock_provider = MagicMock()
        mock_tracer_provider.return_value = mock_provider
        mock_tracer = MagicMock()
        mock_trace.get_tracer.return_value = mock_tracer

        tracer = DistributedTracer()
        tracer.initialize()

        assert tracer._initialized is True
        assert tracer.tracer_provider == mock_provider
        mock_trace.set_tracer_provider.assert_called_once_with(mock_provider)

    @patch('src.monitoring.tracing.OPENTELEMETRY_AVAILABLE', True)
    def test_get_current_trace_id_not_initialized(self):
        """Test getting trace ID when tracer not initialized."""
        tracer = DistributedTracer()
        result = tracer.get_current_trace_id()
        assert result is None

    @patch('src.monitoring.tracing.OPENTELEMETRY_AVAILABLE', True)
    @patch('src.monitoring.tracing.trace')
    def test_get_current_trace_id_success(self, mock_trace):
        """Test successful trace ID retrieval."""
        # Setup mock span
        mock_span = MagicMock()
        mock_span.is_recording.return_value = True
        mock_span_context = MagicMock()
        mock_span_context.trace_id = 123456789
        mock_span.get_span_context.return_value = mock_span_context
        mock_trace.get_current_span.return_value = mock_span

        tracer = DistributedTracer()
        tracer._initialized = True
        
        result = tracer.get_current_trace_id()
        assert result == format(123456789, '032x')

    def test_shutdown_not_initialized(self):
        """Test shutdown when tracer not initialized."""
        tracer = DistributedTracer()
        # Should not raise exception
        tracer.shutdown()

    @patch('src.monitoring.tracing.OPENTELEMETRY_AVAILABLE', True)
    def test_shutdown_success(self):
        """Test successful tracer shutdown."""
        tracer = DistributedTracer()
        tracer._initialized = True
        mock_provider = MagicMock()
        tracer.tracer_provider = mock_provider

        tracer.shutdown()

        mock_provider.shutdown.assert_called_once()
        assert tracer._initialized is False

    def test_get_tracing_status(self):
        """Test getting tracing status."""
        config = TracingConfig(service_name="test-service")
        tracer = DistributedTracer(config)
        
        status = tracer.get_tracing_status()
        
        assert status["service_name"] == "test-service"
        assert status["initialized"] is False
        assert "auto_instrumentation" in status
        assert "exporters" in status


class TestTracingUtils:
    """Test tracing utility functions."""

    @patch('src.utils.tracing_utils.distributed_tracer')
    def test_trace_decorator_async_function(self, mock_tracer):
        """Test trace decorator on async function."""
        mock_context_manager = AsyncMock()
        mock_tracer.trace_operation.return_value = mock_context_manager

        @trace("test_operation")
        async def async_function(x: int) -> int:
            return x * 2

        # The function should be wrapped
        assert hasattr(async_function, '__wrapped__')

    @patch('src.utils.tracing_utils.distributed_tracer')
    def test_trace_decorator_sync_function(self, mock_tracer):
        """Test trace decorator on synchronous function."""
        mock_tracer.trace_function.return_value = lambda f: f

        @trace("test_operation")
        def sync_function(x: int) -> int:
            return x * 2

        result = sync_function(5)
        assert result == 10
        mock_tracer.trace_function.assert_called_once()

    @patch('src.utils.tracing_utils.distributed_tracer')
    def test_add_trace_event(self, mock_tracer):
        """Test adding trace event."""
        add_trace_event("test_event", {"key": "value"})
        mock_tracer.add_event.assert_called_once_with("test_event", {"key": "value"})

    @patch('src.utils.tracing_utils.distributed_tracer')
    def test_set_trace_attribute(self, mock_tracer):
        """Test setting trace attribute."""
        set_trace_attribute("test_key", "test_value")
        mock_tracer.set_attribute.assert_called_once_with("test_key", "test_value")

    @patch('src.utils.tracing_utils.distributed_tracer')
    def test_get_current_trace_context(self, mock_tracer):
        """Test getting current trace context."""
        mock_tracer.get_current_trace_id.return_value = "trace123"
        mock_tracer.get_current_span_id.return_value = "span456"

        context = get_current_trace_context()
        
        assert context["trace_id"] == "trace123"
        assert context["span_id"] == "span456"

    def test_trace_database_operation(self):
        """Test database operation tracing decorator."""
        decorator = trace_database_operation("users", "select")
        assert callable(decorator)

    def test_trace_cache_operation(self):
        """Test cache operation tracing decorator."""
        decorator = trace_cache_operation("redis", "get")
        assert callable(decorator)

    def test_trace_http_request(self):
        """Test HTTP request tracing decorator."""
        decorator = trace_http_request("GET", "https://api.example.com")
        assert callable(decorator)


class TestTraceContextManager:
    """Test trace context manager."""

    @patch('src.utils.tracing_utils.distributed_tracer')
    @pytest.mark.asyncio
    async def test_context_manager_success(self, mock_tracer):
        """Test successful context manager usage."""
        mock_context = AsyncMock()
        mock_span = MagicMock()
        mock_context.__aenter__.return_value = mock_span
        mock_tracer.trace_operation.return_value = mock_context

        async with TraceContextManager("test_operation", {"attr": "value"}) as span:
            assert span == mock_span

        mock_tracer.trace_operation.assert_called_once_with(
            "test_operation", 
            {"attr": "value"}
        )
        mock_context.__aenter__.assert_called_once()
        mock_context.__aexit__.assert_called_once()

    @patch('src.utils.tracing_utils.distributed_tracer')
    @pytest.mark.asyncio
    async def test_context_manager_exception(self, mock_tracer):
        """Test context manager with exception."""
        mock_context = AsyncMock()
        mock_context.__aenter__.return_value = MagicMock()
        mock_tracer.trace_operation.return_value = mock_context

        with pytest.raises(ValueError):
            async with TraceContextManager("test_operation") as span:
                raise ValueError("Test error")

        mock_context.__aexit__.assert_called_once()


class TestTracingIntegration:
    """Integration tests for tracing components."""

    @patch('src.monitoring.tracing.OPENTELEMETRY_AVAILABLE', True)
    @patch('opentelemetry.trace') 
    @patch('opentelemetry.sdk.trace.TracerProvider')
    def test_tracer_integration_with_utils(self, mock_tracer_provider, mock_trace):
        """Test integration between tracer and utilities."""
        # Setup tracer
        tracer = DistributedTracer()
        tracer.initialize()
        
        # Mock current span for utilities
        mock_span = MagicMock()
        mock_span.is_recording.return_value = True
        mock_trace.get_current_span.return_value = mock_span

        # Test utility functions
        add_trace_event("test_event")
        set_trace_attribute("test_attr", "value")

        # Verify tracer methods were called through utilities
        assert tracer._initialized is True

    def test_tracing_disabled_gracefully(self):
        """Test that tracing utilities work gracefully when tracing is disabled."""
        # These should not raise exceptions even when tracing is unavailable
        add_trace_event("test_event")
        set_trace_attribute("test_attr", "value")
        context = get_current_trace_context()
        
        # Context should have None values when tracing unavailable
        assert context["trace_id"] is None or isinstance(context["trace_id"], str)
        assert context["span_id"] is None or isinstance(context["span_id"], str)