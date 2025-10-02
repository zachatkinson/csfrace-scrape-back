"""Comprehensive tests for distributed tracing utilities - MANDATORY TEST_BUILDING.md compliance.

This module tests distributed tracing utilities with complete coverage:
- trace() decorator for sync and async functions
- add_trace_event() for event recording
- set_trace_attribute() for attribute setting
- get_current_trace_context() for context retrieval
- Convenience decorators (trace_database_operation, trace_cache_operation, trace_http_request)
- Edge cases and error handling
- Performance benchmarks

ALL tests follow MANDATORY TEST_BUILDING.md patterns:
- AAA pattern with explicit comments
- Factory fixtures for DRY principle
- Comprehensive tracing scenario testing
- Performance benchmarks with specific thresholds
"""

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.utils.tracing_utils import (
    add_trace_event,
    get_current_trace_context,
    set_trace_attribute,
    trace,
    trace_cache_operation,
    trace_database_operation,
    trace_http_request,
)

# ============================================================================
# Test Fixtures - DRY Principle
# ============================================================================


@pytest.fixture
def mock_distributed_tracer():
    """Factory for mock distributed tracer - DRY principle."""
    return MagicMock()


@pytest.fixture
def sample_trace_attributes() -> dict[str, str]:
    """Factory for sample trace attributes - DRY principle."""
    return {"user_id": "123", "request_id": "abc-def", "action": "test_action"}


# ============================================================================
# trace() Decorator Tests
# ============================================================================


@pytest.mark.unit
class TestTraceDecorator:
    """Tests for trace decorator function."""

    @patch("src.utils.tracing_utils.distributed_tracer")
    def test_trace_decorator_with_sync_function(self, mock_tracer):
        """Test trace decorator with sync function - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        mock_tracer.trace_function.return_value = lambda func: func

        @trace("test_operation")
        def sync_function(x: int, y: int) -> int:
            return x + y

        # Act - MANDATORY
        result = sync_function(2, 3)

        # Assert - MANDATORY
        assert result == 5
        mock_tracer.trace_function.assert_called_once()

    @pytest.mark.asyncio
    @patch("src.utils.tracing_utils.distributed_tracer")
    async def test_trace_decorator_with_async_function(self, mock_tracer):
        """Test trace decorator with async function - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        mock_context = MagicMock()
        mock_context.__aenter__ = AsyncMock(return_value=mock_context)
        mock_context.__aexit__ = AsyncMock(return_value=None)
        mock_tracer.trace_operation.return_value = mock_context

        @trace("test_async_operation")
        async def async_function(x: int, y: int) -> int:
            return x + y

        # Act - MANDATORY
        result = await async_function(2, 3)

        # Assert - MANDATORY
        assert result == 5
        mock_tracer.trace_operation.assert_called_once()

    @patch("src.utils.tracing_utils.distributed_tracer")
    def test_trace_decorator_with_default_operation_name(self, mock_tracer):
        """Test trace decorator uses function name as default - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        mock_tracer.trace_function.return_value = lambda func: func

        @trace()
        def my_custom_function() -> str:
            return "result"

        # Act - MANDATORY
        result = my_custom_function()

        # Assert - MANDATORY
        assert result == "result"
        mock_tracer.trace_function.assert_called_once()

    @patch("src.utils.tracing_utils.distributed_tracer")
    def test_trace_decorator_with_custom_attributes(self, mock_tracer):
        """Test trace decorator with custom attributes - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        custom_attrs = {"component": "parser", "version": "1.0"}
        mock_tracer.trace_function.return_value = lambda func: func

        @trace(attributes=custom_attrs)
        def traced_function() -> str:
            return "traced"

        # Act - MANDATORY
        result = traced_function()

        # Assert - MANDATORY
        assert result == "traced"
        mock_tracer.trace_function.assert_called_once()

    @pytest.mark.asyncio
    @patch("src.utils.tracing_utils.distributed_tracer")
    async def test_trace_decorator_async_with_attributes(self, mock_tracer):
        """Test trace decorator async function with attributes - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        mock_context = MagicMock()
        mock_context.__aenter__ = AsyncMock(return_value=mock_context)
        mock_context.__aexit__ = AsyncMock(return_value=None)
        mock_tracer.trace_operation.return_value = mock_context

        custom_attrs = {"service": "scraper"}

        @trace("scrape_page", attributes=custom_attrs)
        async def scrape_async(url: str) -> dict:
            return {"url": url, "status": "success"}

        # Act - MANDATORY
        result = await scrape_async("https://example.com")

        # Assert - MANDATORY
        assert result["url"] == "https://example.com"
        assert result["status"] == "success"
        mock_tracer.trace_operation.assert_called_once()

    @patch("src.utils.tracing_utils.distributed_tracer")
    def test_trace_decorator_preserves_function_metadata(self, mock_tracer):
        """Test trace decorator preserves function metadata - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        mock_tracer.trace_function.return_value = lambda func: func

        @trace("test_metadata")
        def documented_function() -> str:
            """This function has documentation."""
            return "result"

        # Act - MANDATORY
        func_name = documented_function.__name__
        func_doc = documented_function.__doc__

        # Assert - MANDATORY
        assert func_name == "documented_function"
        assert "This function has documentation" in func_doc


# ============================================================================
# add_trace_event Tests
# ============================================================================


@pytest.mark.unit
class TestAddTraceEvent:
    """Tests for add_trace_event function."""

    @patch("src.utils.tracing_utils.distributed_tracer")
    def test_add_trace_event_with_name_only(self, mock_tracer):
        """Test add_trace_event with event name only - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        event_name = "cache_miss"

        # Act - MANDATORY
        add_trace_event(event_name)

        # Assert - MANDATORY
        mock_tracer.add_event.assert_called_once_with(event_name, None)

    @patch("src.utils.tracing_utils.distributed_tracer")
    def test_add_trace_event_with_attributes(self, mock_tracer):
        """Test add_trace_event with attributes - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        event_name = "validation_passed"
        attributes = {"user_id": "123", "action": "login"}

        # Act - MANDATORY
        add_trace_event(event_name, attributes)

        # Assert - MANDATORY
        mock_tracer.add_event.assert_called_once_with(event_name, attributes)

    @patch("src.utils.tracing_utils.distributed_tracer")
    def test_add_trace_event_with_empty_attributes(self, mock_tracer):
        """Test add_trace_event with empty attributes - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        event_name = "request_started"
        attributes = {}

        # Act - MANDATORY
        add_trace_event(event_name, attributes)

        # Assert - MANDATORY
        mock_tracer.add_event.assert_called_once_with(event_name, attributes)


# ============================================================================
# set_trace_attribute Tests
# ============================================================================


@pytest.mark.unit
class TestSetTraceAttribute:
    """Tests for set_trace_attribute function."""

    @patch("src.utils.tracing_utils.distributed_tracer")
    def test_set_trace_attribute_string_value(self, mock_tracer):
        """Test set_trace_attribute with string value - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        key = "user.id"
        value = "user-123"

        # Act - MANDATORY
        set_trace_attribute(key, value)

        # Assert - MANDATORY
        mock_tracer.set_attribute.assert_called_once_with(key, value)

    @patch("src.utils.tracing_utils.distributed_tracer")
    def test_set_trace_attribute_integer_value(self, mock_tracer):
        """Test set_trace_attribute with integer value - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        key = "database.query_count"
        value = 42

        # Act - MANDATORY
        set_trace_attribute(key, value)

        # Assert - MANDATORY
        mock_tracer.set_attribute.assert_called_once_with(key, value)

    @patch("src.utils.tracing_utils.distributed_tracer")
    def test_set_trace_attribute_boolean_value(self, mock_tracer):
        """Test set_trace_attribute with boolean value - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        key = "cache.hit"
        value = True

        # Act - MANDATORY
        set_trace_attribute(key, value)

        # Assert - MANDATORY
        mock_tracer.set_attribute.assert_called_once_with(key, value)

    @patch("src.utils.tracing_utils.distributed_tracer")
    def test_set_trace_attribute_float_value(self, mock_tracer):
        """Test set_trace_attribute with float value - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        key = "response.time_ms"
        value = 123.45

        # Act - MANDATORY
        set_trace_attribute(key, value)

        # Assert - MANDATORY
        mock_tracer.set_attribute.assert_called_once_with(key, value)


# ============================================================================
# get_current_trace_context Tests
# ============================================================================


@pytest.mark.unit
class TestGetCurrentTraceContext:
    """Tests for get_current_trace_context function."""

    @patch("src.utils.tracing_utils.distributed_tracer")
    def test_get_current_trace_context_with_active_trace(self, mock_tracer):
        """Test get_current_trace_context with active trace - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        mock_tracer.get_current_trace_id.return_value = "trace-123"
        mock_tracer.get_current_span_id.return_value = "span-456"

        # Act - MANDATORY
        context = get_current_trace_context()

        # Assert - MANDATORY
        assert context["trace_id"] == "trace-123"
        assert context["span_id"] == "span-456"
        mock_tracer.get_current_trace_id.assert_called_once()
        mock_tracer.get_current_span_id.assert_called_once()

    @patch("src.utils.tracing_utils.distributed_tracer")
    def test_get_current_trace_context_without_active_trace(self, mock_tracer):
        """Test get_current_trace_context without active trace - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        mock_tracer.get_current_trace_id.return_value = None
        mock_tracer.get_current_span_id.return_value = None

        # Act - MANDATORY
        context = get_current_trace_context()

        # Assert - MANDATORY
        assert context["trace_id"] is None
        assert context["span_id"] is None

    @patch("src.utils.tracing_utils.distributed_tracer")
    def test_get_current_trace_context_returns_dict(self, mock_tracer):
        """Test get_current_trace_context returns dict - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        mock_tracer.get_current_trace_id.return_value = "trace-abc"
        mock_tracer.get_current_span_id.return_value = "span-xyz"

        # Act - MANDATORY
        context = get_current_trace_context()

        # Assert - MANDATORY
        assert isinstance(context, dict)
        assert "trace_id" in context
        assert "span_id" in context


# ============================================================================
# Convenience Decorator Tests
# ============================================================================


@pytest.mark.unit
class TestConvenienceDecorators:
    """Tests for convenience decorator functions."""

    @patch("src.utils.tracing_utils.distributed_tracer")
    def test_trace_database_operation_decorator(self, mock_tracer):
        """Test trace_database_operation decorator - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        mock_tracer.trace_function.return_value = lambda func: func

        @trace_database_operation("users", "select")
        def query_users() -> list:
            return [{"id": 1, "name": "User 1"}]

        # Act - MANDATORY
        result = query_users()

        # Assert - MANDATORY
        assert len(result) == 1
        assert result[0]["id"] == 1
        mock_tracer.trace_function.assert_called_once()

    @patch("src.utils.tracing_utils.distributed_tracer")
    def test_trace_cache_operation_decorator(self, mock_tracer):
        """Test trace_cache_operation decorator - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        mock_tracer.trace_function.return_value = lambda func: func

        @trace_cache_operation("redis", "get")
        def get_from_cache(key: str) -> str | None:
            return "cached_value"

        # Act - MANDATORY
        result = get_from_cache("test_key")

        # Assert - MANDATORY
        assert result == "cached_value"
        mock_tracer.trace_function.assert_called_once()

    @patch("src.utils.tracing_utils.distributed_tracer")
    def test_trace_http_request_decorator(self, mock_tracer):
        """Test trace_http_request decorator - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        mock_tracer.trace_function.return_value = lambda func: func

        @trace_http_request("GET", "https://api.example.com")
        def make_request() -> dict:
            return {"status": 200, "data": "success"}

        # Act - MANDATORY
        result = make_request()

        # Assert - MANDATORY
        assert result["status"] == 200
        assert result["data"] == "success"
        mock_tracer.trace_function.assert_called_once()


# ============================================================================
# MANDATORY Performance Benchmarks
# ============================================================================


@pytest.mark.performance
@pytest.mark.unit
class TestTracingUtilsPerformance:
    """MANDATORY performance tests for tracing utilities."""

    @patch("src.utils.tracing_utils.distributed_tracer")
    def test_trace_decorator_overhead_sync(self, mock_tracer):
        """MANDATORY performance test - sync trace decorator overhead."""
        # Arrange - MANDATORY
        mock_tracer.trace_function.return_value = lambda func: func

        @trace("performance_test")
        def fast_function(x: int) -> int:
            return x * 2

        iterations = 10000

        # Act - MANDATORY
        start_time = time.perf_counter()

        for i in range(iterations):
            fast_function(i)

        end_time = time.perf_counter()
        execution_time = end_time - start_time

        # Assert - MANDATORY
        avg_time = execution_time / iterations
        assert avg_time < 0.0001  # <0.1ms per decorated call
        assert execution_time < 1.0  # Total <1s for 10000 calls

    @patch("src.utils.tracing_utils.distributed_tracer")
    def test_add_trace_event_performance(self, mock_tracer):
        """MANDATORY performance test - add_trace_event speed."""
        # Arrange - MANDATORY
        iterations = 10000

        # Act - MANDATORY
        start_time = time.perf_counter()

        for i in range(iterations):
            add_trace_event("performance_event", {"iteration": i})

        end_time = time.perf_counter()
        execution_time = end_time - start_time

        # Assert - MANDATORY
        avg_time = execution_time / iterations
        assert avg_time < 0.0001  # <0.1ms per event
        assert execution_time < 1.0  # Total <1s for 10000 events

    @patch("src.utils.tracing_utils.distributed_tracer")
    def test_set_trace_attribute_performance(self, mock_tracer):
        """MANDATORY performance test - set_trace_attribute speed."""
        # Arrange - MANDATORY
        iterations = 10000

        # Act - MANDATORY
        start_time = time.perf_counter()

        for i in range(iterations):
            set_trace_attribute(f"attribute_{i % 100}", i)

        end_time = time.perf_counter()
        execution_time = end_time - start_time

        # Assert - MANDATORY
        avg_time = execution_time / iterations
        assert avg_time < 0.0001  # <0.1ms per attribute set
        assert execution_time < 1.0  # Total <1s for 10000 sets
