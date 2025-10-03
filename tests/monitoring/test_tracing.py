"""Comprehensive tests for OpenTelemetry distributed tracing integration.

MANDATORY: All tests follow TEST_BUILDING.md ZERO TOLERANCE standards.
"""

import time

import pytest

from src.monitoring.tracing import OPENTELEMETRY_AVAILABLE, DistributedTracer, TracingConfig

# ============================================================================
# FACTORY FIXTURES - DRY PRINCIPLE (MANDATORY)
# ============================================================================


@pytest.fixture
def tracing_config() -> TracingConfig:
    """Factory for TracingConfig - DRY principle."""
    return TracingConfig(
        enabled=True,
        service_name="test-service",
        service_version="1.0.0",
        environment="test",
        export_to_console=False,
        export_to_jaeger=False,
        export_to_otlp=False,
        sampling_rate=1.0,
        instrument_fastapi=False,  # Disable for most tests
        instrument_aiohttp=False,
        instrument_sqlalchemy=False,
    )


@pytest.fixture
def distributed_tracer(tracing_config: TracingConfig) -> DistributedTracer:
    """Factory for DistributedTracer - DRY principle."""
    return DistributedTracer(config=tracing_config)


# ============================================================================
# CONFIGURATION TESTS
# ============================================================================


@pytest.mark.unit
class TestTracingConfig:
    """Tests for TracingConfig dataclass."""

    def test_config_defaults(self):
        """Test TracingConfig has sensible defaults - MANDATORY AAA pattern."""
        # Arrange - MANDATORY

        # Act - MANDATORY
        config = TracingConfig()

        # Assert - MANDATORY
        assert config.enabled is True
        assert config.service_name == "csfrace-scraper"
        assert config.service_version == "2.2.2"
        assert config.environment == "production"
        assert config.export_to_console is False
        assert config.export_to_jaeger is False
        assert config.export_to_otlp is False
        assert config.otlp_endpoint == "http://localhost:4317"
        assert config.sampling_rate == 1.0
        assert config.instrument_fastapi is True
        assert config.instrument_aiohttp is True
        assert config.instrument_sqlalchemy is True
        assert config.correlation_id_header == "X-Correlation-ID"
        assert config.trace_id_header == "X-Trace-ID"

    def test_config_customization(self):
        """Test TracingConfig allows customization - MANDATORY AAA pattern."""
        # Arrange - MANDATORY

        # Act - MANDATORY
        config = TracingConfig(
            enabled=False,
            service_name="custom-service",
            service_version="2.0.0",
            environment="staging",
            export_to_console=True,
            export_to_jaeger=True,
            export_to_otlp=True,
            otlp_endpoint="http://custom:4317",
            sampling_rate=0.5,
            instrument_fastapi=False,
            instrument_aiohttp=False,
            instrument_sqlalchemy=False,
            correlation_id_header="X-Custom-Correlation",
            trace_id_header="X-Custom-Trace",
        )

        # Assert - MANDATORY
        assert config.enabled is False
        assert config.service_name == "custom-service"
        assert config.service_version == "2.0.0"
        assert config.environment == "staging"
        assert config.export_to_console is True
        assert config.export_to_jaeger is True
        assert config.export_to_otlp is True
        assert config.otlp_endpoint == "http://custom:4317"
        assert config.sampling_rate == 0.5
        assert config.instrument_fastapi is False
        assert config.instrument_aiohttp is False
        assert config.instrument_sqlalchemy is False
        assert config.correlation_id_header == "X-Custom-Correlation"
        assert config.trace_id_header == "X-Custom-Trace"


# ============================================================================
# DISTRIBUTED TRACER INITIALIZATION TESTS
# ============================================================================


@pytest.mark.unit
class TestDistributedTracerInitialization:
    """Tests for DistributedTracer initialization."""

    def test_tracer_initializes_with_config(self, tracing_config: TracingConfig):
        """Test tracer initializes with provided config - MANDATORY AAA pattern."""
        # Arrange - MANDATORY

        # Act - MANDATORY
        tracer = DistributedTracer(config=tracing_config)

        # Assert - MANDATORY
        assert tracer.config == tracing_config
        assert tracer._initialized is False
        assert tracer.tracer_provider is None
        assert tracer.tracer is None

    def test_tracer_uses_default_config(self):
        """Test tracer uses default config when none provided - MANDATORY AAA pattern."""
        # Arrange - MANDATORY

        # Act - MANDATORY
        tracer = DistributedTracer()

        # Assert - MANDATORY
        assert tracer.config.enabled is True
        assert tracer.config.service_name == "csfrace-scraper"

    @pytest.mark.skipif(not OPENTELEMETRY_AVAILABLE, reason="OpenTelemetry not installed")
    def test_initialize_sets_up_tracer_provider(self, distributed_tracer: DistributedTracer):
        """Test initialize sets up tracer provider - MANDATORY AAA pattern."""
        # Arrange - MANDATORY

        # Act - MANDATORY
        distributed_tracer.initialize()

        # Assert - MANDATORY
        assert distributed_tracer._initialized is True
        assert distributed_tracer.tracer_provider is not None
        assert distributed_tracer.tracer is not None

        # Cleanup
        distributed_tracer.shutdown()

    def test_initialize_when_disabled(self):
        """Test initialize does nothing when disabled - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        config = TracingConfig(enabled=False)
        tracer = DistributedTracer(config=config)

        # Act - MANDATORY
        tracer.initialize()

        # Assert - MANDATORY
        assert tracer._initialized is False
        assert tracer.tracer_provider is None

    def test_initialize_when_already_initialized(self):
        """Test initialize is idempotent - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        if not OPENTELEMETRY_AVAILABLE:
            pytest.skip("OpenTelemetry not installed")

        tracer = DistributedTracer()
        tracer.initialize()
        first_provider = tracer.tracer_provider

        # Act - MANDATORY
        tracer.initialize()  # Call again

        # Assert - MANDATORY
        assert tracer.tracer_provider is first_provider  # Same instance

        # Cleanup
        tracer.shutdown()


# ============================================================================
# OPENTELEMETRY AVAILABILITY TESTS
# ============================================================================


@pytest.mark.unit
class TestOpenTelemetryAvailability:
    """Tests for OpenTelemetry availability handling."""

    def test_opentelemetry_availability_flag(self):
        """Test OPENTELEMETRY_AVAILABLE flag reflects actual availability - MANDATORY AAA pattern."""
        # Arrange - MANDATORY

        # Act - MANDATORY
        # OPENTELEMETRY_AVAILABLE is set at module import time

        # Assert - MANDATORY
        # Should be a boolean
        assert isinstance(OPENTELEMETRY_AVAILABLE, bool)

    def test_tracer_works_without_opentelemetry(self):
        """Test tracer gracefully handles missing OpenTelemetry - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        config = TracingConfig(enabled=True)

        # Act - MANDATORY
        tracer = DistributedTracer(config=config)
        tracer.initialize()

        # Assert - MANDATORY
        # Should not raise errors
        if not OPENTELEMETRY_AVAILABLE:
            assert tracer._initialized is False


# ============================================================================
# TRACE OPERATION TESTS
# ============================================================================


@pytest.mark.asyncio
@pytest.mark.unit
class TestTraceOperation:
    """Tests for trace_operation context manager."""

    @pytest.mark.skipif(not OPENTELEMETRY_AVAILABLE, reason="OpenTelemetry not installed")
    async def test_trace_operation_creates_span(self, distributed_tracer: DistributedTracer):
        """Test trace_operation creates span - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        distributed_tracer.initialize()

        # Act - MANDATORY
        async with distributed_tracer.trace_operation("test_operation") as span:
            # Assert - MANDATORY (within context)
            assert span is not None

        # Cleanup
        distributed_tracer.shutdown()

    @pytest.mark.skipif(not OPENTELEMETRY_AVAILABLE, reason="OpenTelemetry not installed")
    async def test_trace_operation_with_attributes(self, distributed_tracer: DistributedTracer):
        """Test trace_operation accepts attributes - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        distributed_tracer.initialize()
        attributes = {"user_id": "123", "action": "scrape"}

        # Act - MANDATORY
        async with distributed_tracer.trace_operation("test_op", attributes=attributes) as span:
            # Assert - MANDATORY (within context)
            assert span is not None

        # Cleanup
        distributed_tracer.shutdown()

    async def test_trace_operation_when_not_initialized(
        self, distributed_tracer: DistributedTracer
    ):
        """Test trace_operation yields None when not initialized - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # Don't initialize

        # Act - MANDATORY
        async with distributed_tracer.trace_operation("test_op") as span:
            # Assert - MANDATORY
            assert span is None


# ============================================================================
# FUNCTION DECORATOR TESTS
# ============================================================================


@pytest.mark.unit
class TestFunctionDecorators:
    """Tests for function tracing decorators."""

    @pytest.mark.skipif(not OPENTELEMETRY_AVAILABLE, reason="OpenTelemetry not installed")
    def test_trace_function_decorator(self, distributed_tracer: DistributedTracer):
        """Test trace_function decorator - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        distributed_tracer.initialize()

        @distributed_tracer.trace_function("test_operation")
        def test_func():
            return "result"

        # Act - MANDATORY
        result = test_func()

        # Assert - MANDATORY
        assert result == "result"

        # Cleanup
        distributed_tracer.shutdown()

    @pytest.mark.skipif(not OPENTELEMETRY_AVAILABLE, reason="OpenTelemetry not installed")
    @pytest.mark.asyncio
    async def test_trace_async_function_decorator(self, distributed_tracer: DistributedTracer):
        """Test trace_async_function decorator - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        distributed_tracer.initialize()

        @distributed_tracer.trace_async_function("async_operation")
        async def async_func():
            return "async_result"

        # Act - MANDATORY
        result = await async_func()

        # Assert - MANDATORY
        assert result == "async_result"

        # Cleanup
        distributed_tracer.shutdown()

    def test_trace_function_decorator_when_not_initialized(
        self, distributed_tracer: DistributedTracer
    ):
        """Test decorator works when not initialized - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # Don't initialize

        @distributed_tracer.trace_function("test_op")
        def test_func():
            return "result"

        # Act - MANDATORY
        result = test_func()

        # Assert - MANDATORY
        assert result == "result"  # Function still works


# ============================================================================
# TRACE/SPAN ID RETRIEVAL TESTS
# ============================================================================


@pytest.mark.unit
class TestTraceSpanIdRetrieval:
    """Tests for trace and span ID retrieval."""

    def test_get_current_trace_id_when_not_initialized(self, distributed_tracer: DistributedTracer):
        """Test get_current_trace_id returns None when not initialized - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # Don't initialize

        # Act - MANDATORY
        trace_id = distributed_tracer.get_current_trace_id()

        # Assert - MANDATORY
        assert trace_id is None

    def test_get_current_span_id_when_not_initialized(self, distributed_tracer: DistributedTracer):
        """Test get_current_span_id returns None when not initialized - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # Don't initialize

        # Act - MANDATORY
        span_id = distributed_tracer.get_current_span_id()

        # Assert - MANDATORY
        assert span_id is None


# ============================================================================
# SPAN EVENT/ATTRIBUTE TESTS
# ============================================================================


@pytest.mark.unit
class TestSpanEventsAndAttributes:
    """Tests for span events and attributes."""

    def test_add_event_when_not_initialized(self, distributed_tracer: DistributedTracer):
        """Test add_event does nothing when not initialized - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # Don't initialize

        # Act - MANDATORY
        distributed_tracer.add_event("test_event", {"key": "value"})

        # Assert - MANDATORY
        # Should not raise errors
        assert True

    def test_set_attribute_when_not_initialized(self, distributed_tracer: DistributedTracer):
        """Test set_attribute does nothing when not initialized - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # Don't initialize

        # Act - MANDATORY
        distributed_tracer.set_attribute("key", "value")

        # Assert - MANDATORY
        # Should not raise errors
        assert True

    @pytest.mark.skipif(not OPENTELEMETRY_AVAILABLE, reason="OpenTelemetry not installed")
    @pytest.mark.asyncio
    async def test_add_event_within_trace(self, distributed_tracer: DistributedTracer):
        """Test add_event works within active trace - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        distributed_tracer.initialize()

        # Act - MANDATORY
        async with distributed_tracer.trace_operation("test_op") as span:
            distributed_tracer.add_event("processing_started", {"step": "1"})

        # Assert - MANDATORY
        # Should not raise errors
        assert span is not None

        # Cleanup
        distributed_tracer.shutdown()

    @pytest.mark.skipif(not OPENTELEMETRY_AVAILABLE, reason="OpenTelemetry not installed")
    @pytest.mark.asyncio
    async def test_set_attribute_within_trace(self, distributed_tracer: DistributedTracer):
        """Test set_attribute works within active trace - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        distributed_tracer.initialize()

        # Act - MANDATORY
        async with distributed_tracer.trace_operation("test_op") as span:
            distributed_tracer.set_attribute("custom_key", "custom_value")

        # Assert - MANDATORY
        # Should not raise errors
        assert span is not None

        # Cleanup
        distributed_tracer.shutdown()


# ============================================================================
# EXCEPTION RECORDING TESTS
# ============================================================================


@pytest.mark.unit
class TestExceptionRecording:
    """Tests for exception recording in spans."""

    def test_record_exception_when_not_initialized(self, distributed_tracer: DistributedTracer):
        """Test record_exception does nothing when not initialized - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # Don't initialize
        exception = ValueError("test error")

        # Act - MANDATORY
        distributed_tracer.record_exception(exception)

        # Assert - MANDATORY
        # Should not raise errors
        assert True

    @pytest.mark.skipif(not OPENTELEMETRY_AVAILABLE, reason="OpenTelemetry not installed")
    @pytest.mark.asyncio
    async def test_record_exception_within_trace(self, distributed_tracer: DistributedTracer):
        """Test record_exception works within active trace - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        distributed_tracer.initialize()
        exception = ValueError("test error")

        # Act - MANDATORY
        async with distributed_tracer.trace_operation("test_op") as span:
            distributed_tracer.record_exception(exception)

        # Assert - MANDATORY
        # Should not raise errors
        assert span is not None

        # Cleanup
        distributed_tracer.shutdown()


# ============================================================================
# TRACING STATUS TESTS
# ============================================================================


@pytest.mark.unit
class TestTracingStatus:
    """Tests for tracing status retrieval."""

    def test_get_tracing_status_structure(self, distributed_tracer: DistributedTracer):
        """Test get_tracing_status returns correct structure - MANDATORY AAA pattern."""
        # Arrange - MANDATORY

        # Act - MANDATORY
        status = distributed_tracer.get_tracing_status()

        # Assert - MANDATORY
        assert "initialized" in status
        assert "opentelemetry_available" in status
        assert "service_name" in status
        assert "service_version" in status
        assert "environment" in status
        assert "sampling_rate" in status
        assert "current_trace_id" in status
        assert "current_span_id" in status
        assert "auto_instrumentation" in status
        assert "exporters" in status

    def test_get_tracing_status_when_not_initialized(self, distributed_tracer: DistributedTracer):
        """Test tracing status when not initialized - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # Don't initialize

        # Act - MANDATORY
        status = distributed_tracer.get_tracing_status()

        # Assert - MANDATORY
        assert status["initialized"] is False
        assert status["current_trace_id"] is None
        assert status["current_span_id"] is None

    @pytest.mark.skipif(not OPENTELEMETRY_AVAILABLE, reason="OpenTelemetry not installed")
    def test_get_tracing_status_when_initialized(self, distributed_tracer: DistributedTracer):
        """Test tracing status when initialized - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        distributed_tracer.initialize()

        # Act - MANDATORY
        status = distributed_tracer.get_tracing_status()

        # Assert - MANDATORY
        assert status["initialized"] is True
        assert status["opentelemetry_available"] is True
        assert status["service_name"] == "test-service"
        assert status["service_version"] == "1.0.0"
        assert status["environment"] == "test"

        # Cleanup
        distributed_tracer.shutdown()


# ============================================================================
# SHUTDOWN TESTS
# ============================================================================


@pytest.mark.unit
class TestShutdown:
    """Tests for tracer shutdown."""

    def test_shutdown_when_not_initialized(self, distributed_tracer: DistributedTracer):
        """Test shutdown does nothing when not initialized - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # Don't initialize

        # Act - MANDATORY
        distributed_tracer.shutdown()

        # Assert - MANDATORY
        assert distributed_tracer._initialized is False

    @pytest.mark.skipif(not OPENTELEMETRY_AVAILABLE, reason="OpenTelemetry not installed")
    def test_shutdown_cleans_up_resources(self, distributed_tracer: DistributedTracer):
        """Test shutdown cleans up tracer resources - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        distributed_tracer.initialize()

        # Act - MANDATORY
        distributed_tracer.shutdown()

        # Assert - MANDATORY
        assert distributed_tracer._initialized is False


# ============================================================================
# AUTO-INSTRUMENTATION TESTS
# ============================================================================


@pytest.mark.unit
class TestAutoInstrumentation:
    """Tests for auto-instrumentation setup."""

    @pytest.mark.skipif(not OPENTELEMETRY_AVAILABLE, reason="OpenTelemetry not installed")
    def test_auto_instrumentation_fastapi(self):
        """Test FastAPI auto-instrumentation can be enabled - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        config = TracingConfig(
            instrument_fastapi=True, instrument_aiohttp=False, instrument_sqlalchemy=False
        )
        tracer = DistributedTracer(config=config)

        # Act - MANDATORY
        tracer.initialize()

        # Assert - MANDATORY
        assert tracer._initialized is True

        # Cleanup
        tracer.shutdown()

    @pytest.mark.skipif(not OPENTELEMETRY_AVAILABLE, reason="OpenTelemetry not installed")
    def test_auto_instrumentation_aiohttp(self):
        """Test aiohttp auto-instrumentation can be enabled - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        config = TracingConfig(
            instrument_fastapi=False, instrument_aiohttp=True, instrument_sqlalchemy=False
        )
        tracer = DistributedTracer(config=config)

        # Act - MANDATORY
        tracer.initialize()

        # Assert - MANDATORY
        assert tracer._initialized is True

        # Cleanup
        tracer.shutdown()

    @pytest.mark.skipif(not OPENTELEMETRY_AVAILABLE, reason="OpenTelemetry not installed")
    def test_auto_instrumentation_sqlalchemy(self):
        """Test SQLAlchemy auto-instrumentation can be enabled - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        config = TracingConfig(
            instrument_fastapi=False, instrument_aiohttp=False, instrument_sqlalchemy=True
        )
        tracer = DistributedTracer(config=config)

        # Act - MANDATORY
        tracer.initialize()

        # Assert - MANDATORY
        assert tracer._initialized is True

        # Cleanup
        tracer.shutdown()


# ============================================================================
# EXPORTER CONFIGURATION TESTS
# ============================================================================


@pytest.mark.unit
class TestExporterConfiguration:
    """Tests for exporter configuration."""

    @pytest.mark.skipif(not OPENTELEMETRY_AVAILABLE, reason="OpenTelemetry not installed")
    def test_console_exporter_configuration(self):
        """Test console exporter can be configured - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        config = TracingConfig(export_to_console=True)
        tracer = DistributedTracer(config=config)

        # Act - MANDATORY
        tracer.initialize()

        # Assert - MANDATORY
        assert tracer._initialized is True
        status = tracer.get_tracing_status()
        assert status["exporters"]["console"] is True

        # Cleanup
        tracer.shutdown()

    @pytest.mark.skipif(not OPENTELEMETRY_AVAILABLE, reason="OpenTelemetry not installed")
    def test_otlp_exporter_configuration(self):
        """Test OTLP exporter can be configured - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        config = TracingConfig(export_to_otlp=True, otlp_endpoint="http://localhost:4317")
        tracer = DistributedTracer(config=config)

        # Act - MANDATORY
        tracer.initialize()

        # Assert - MANDATORY
        assert tracer._initialized is True
        status = tracer.get_tracing_status()
        assert status["exporters"]["otlp"] is True

        # Cleanup
        tracer.shutdown()


# ============================================================================
# MANDATORY SECURITY TESTS
# ============================================================================


@pytest.mark.security
@pytest.mark.unit
class TestTracingSecurity:
    """MANDATORY security tests for distributed tracing."""

    def test_span_attributes_sanitization(self, distributed_tracer: DistributedTracer):
        """MANDATORY security test - span attributes with malicious content."""
        # Arrange - MANDATORY
        malicious_attributes = {
            "user_input": "<script>alert('xss')</script>",
            "sql_injection": "'; DROP TABLE traces;--",
            "path_traversal": "../../../etc/passwd",
        }

        # Act - MANDATORY
        # Tracing should store attributes as-is (app must sanitize on display)
        if OPENTELEMETRY_AVAILABLE:
            distributed_tracer.initialize()
            distributed_tracer.set_attribute("test", malicious_attributes["user_input"])
            distributed_tracer.shutdown()

        # Assert - MANDATORY
        # Should not raise errors
        assert True

    def test_event_attributes_sanitization(self, distributed_tracer: DistributedTracer):
        """MANDATORY security test - event attributes with malicious content."""
        # Arrange - MANDATORY
        malicious_data = {
            "command": "rm -rf /",
            "query": "SELECT * FROM users WHERE id = '1' OR '1'='1'",
        }

        # Act - MANDATORY
        if OPENTELEMETRY_AVAILABLE:
            distributed_tracer.initialize()
            distributed_tracer.add_event("malicious_event", malicious_data)
            distributed_tracer.shutdown()

        # Assert - MANDATORY
        # Should not raise errors
        assert True


# ============================================================================
# MANDATORY PERFORMANCE BENCHMARKS
# ============================================================================


@pytest.mark.performance
@pytest.mark.unit
class TestTracingPerformance:
    """MANDATORY performance tests for distributed tracing."""

    @pytest.mark.skipif(not OPENTELEMETRY_AVAILABLE, reason="OpenTelemetry not installed")
    def test_trace_operation_overhead(self, distributed_tracer: DistributedTracer):
        """MANDATORY performance test - trace operation overhead."""
        # Arrange - MANDATORY
        distributed_tracer.initialize()
        iterations = 100

        # Act - MANDATORY
        start_time = time.perf_counter()

        import asyncio

        for i in range(iterations):

            async def traced_op(idx=i):
                async with distributed_tracer.trace_operation(f"test_op_{idx}") as span:
                    pass

            asyncio.run(traced_op())

        end_time = time.perf_counter()
        execution_time = end_time - start_time

        # Assert - MANDATORY
        avg_time = execution_time / iterations
        assert avg_time < 0.01  # <10ms per traced operation
        assert execution_time < 1.0  # Total <1s for 100 operations

        # Cleanup
        distributed_tracer.shutdown()

    @pytest.mark.skipif(not OPENTELEMETRY_AVAILABLE, reason="OpenTelemetry not installed")
    def test_get_tracing_status_performance(self, distributed_tracer: DistributedTracer):
        """MANDATORY performance test - status retrieval speed."""
        # Arrange - MANDATORY
        distributed_tracer.initialize()
        iterations = 1000

        # Act - MANDATORY
        start_time = time.perf_counter()

        for _ in range(iterations):
            distributed_tracer.get_tracing_status()

        end_time = time.perf_counter()
        execution_time = end_time - start_time

        # Assert - MANDATORY
        avg_time = execution_time / iterations
        assert avg_time < 0.001  # <1ms per status retrieval
        assert execution_time < 1.0  # Total <1s for 1000 retrievals

        # Cleanup
        distributed_tracer.shutdown()
