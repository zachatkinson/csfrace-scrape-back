"""Tests for tracing utilities following DRY/SOLID principles."""

from unittest.mock import Mock, patch

import asyncio
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


class TestTraceDecorator:
    """Test trace decorator functionality following SOLID principles."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_tracer = Mock()
        self.tracer_patcher = patch("src.utils.tracing_utils.distributed_tracer", self.mock_tracer)
        self.tracer_patcher.start()

    def teardown_method(self):
        """Clean up test fixtures."""
        self.tracer_patcher.stop()

    def test_trace_decorator_sync_function_default_name(self):
        """Test trace decorator with sync function using default operation name."""

        @trace()
        def sample_function(arg1, arg2):
            return f"{arg1}_{arg2}"

        # Configure mock - trace_function returns a decorator, which returns a wrapped function
        mock_decorated_func = Mock(return_value="test_result")
        mock_decorator = Mock(return_value=mock_decorated_func)
        self.mock_tracer.trace_function.return_value = mock_decorator

        # Call decorated function
        result = sample_function("hello", "world")

        # Verify tracer was called with expected parameters
        expected_span_name = f"{sample_function.__module__}.{sample_function.__name__}"
        self.mock_tracer.trace_function.assert_called_once_with(expected_span_name, None)
        # Verify decorator was called with the original function
        mock_decorator.assert_called_once()
        # Verify the decorated function was called with args
        mock_decorated_func.assert_called_once_with("hello", "world")
        assert result == "test_result"

    def test_trace_decorator_sync_function_custom_name(self):
        """Test trace decorator with custom operation name."""

        @trace(operation_name="custom_operation")
        def sample_function():
            return "result"

        # Configure mock - trace_function returns a decorator, which returns a wrapped function
        mock_decorated_func = Mock(return_value="custom_result")
        mock_decorator = Mock(return_value=mock_decorated_func)
        self.mock_tracer.trace_function.return_value = mock_decorator

        # Call decorated function
        result = sample_function()

        # Verify custom operation name was used
        self.mock_tracer.trace_function.assert_called_once_with("custom_operation", None)
        # Verify decorator was called with the original function
        mock_decorator.assert_called_once()
        # Verify the decorated function was called
        mock_decorated_func.assert_called_once_with()
        assert result == "custom_result"

    def test_trace_decorator_sync_function_with_attributes(self):
        """Test trace decorator with custom attributes."""
        custom_attributes = {"component": "test", "version": "1.0"}

        @trace(attributes=custom_attributes)
        def sample_function():
            return "result"

        # Configure mock - trace_function returns a decorator, which returns a wrapped function
        mock_decorated_func = Mock(return_value="attr_result")
        mock_decorator = Mock(return_value=mock_decorated_func)
        self.mock_tracer.trace_function.return_value = mock_decorator

        # Call decorated function
        result = sample_function()

        # Verify attributes were passed
        expected_span_name = f"{sample_function.__module__}.{sample_function.__name__}"
        self.mock_tracer.trace_function.assert_called_once_with(
            expected_span_name, custom_attributes
        )
        # Verify decorator was called with the original function
        mock_decorator.assert_called_once()
        # Verify the decorated function was called
        mock_decorated_func.assert_called_once_with()
        assert result == "attr_result"

    @pytest.mark.asyncio
    async def test_trace_decorator_async_function_default_name(self):
        """Test trace decorator with async function using default operation name."""

        @trace()
        async def async_sample_function(arg1, arg2):
            return f"async_{arg1}_{arg2}"

        # Configure mock context manager
        mock_context = Mock()
        mock_context.__aenter__ = Mock(return_value=asyncio.Future())
        mock_context.__aenter__.return_value.set_result(None)
        mock_context.__aexit__ = Mock(return_value=asyncio.Future())
        mock_context.__aexit__.return_value.set_result(None)
        self.mock_tracer.trace_operation.return_value = mock_context

        # Call decorated function
        result = await async_sample_function("hello", "world")

        # Verify tracer was called with expected parameters
        expected_span_name = f"{async_sample_function.__module__}.{async_sample_function.__name__}"
        expected_attributes = {
            "function.name": "async_sample_function",
            "function.module": async_sample_function.__module__,
        }
        self.mock_tracer.trace_operation.assert_called_once_with(
            expected_span_name, expected_attributes
        )
        assert result == "async_hello_world"

    @pytest.mark.asyncio
    async def test_trace_decorator_async_function_custom_name_and_attributes(self):
        """Test trace decorator with async function, custom name and attributes."""
        custom_attributes = {"service": "scraper", "version": "2.0"}

        @trace(operation_name="async_custom_operation", attributes=custom_attributes)
        async def async_custom_function():
            return "async_custom_result"

        # Configure mock context manager
        mock_context = Mock()
        mock_context.__aenter__ = Mock(return_value=asyncio.Future())
        mock_context.__aenter__.return_value.set_result(None)
        mock_context.__aexit__ = Mock(return_value=asyncio.Future())
        mock_context.__aexit__.return_value.set_result(None)
        self.mock_tracer.trace_operation.return_value = mock_context

        # Call decorated function
        result = await async_custom_function()

        # Verify custom operation name and merged attributes
        expected_attributes = {
            "function.name": "async_custom_function",
            "function.module": async_custom_function.__module__,
            "service": "scraper",
            "version": "2.0",
        }
        self.mock_tracer.trace_operation.assert_called_once_with(
            "async_custom_operation", expected_attributes
        )
        assert result == "async_custom_result"

    def test_trace_decorator_preserves_function_metadata(self):
        """Test that trace decorator preserves original function metadata."""

        @trace()
        def original_function():
            """Original function docstring."""
            return "original"

        # Verify function metadata is preserved
        assert original_function.__name__ == "original_function"
        assert original_function.__doc__ == "Original function docstring."

    @pytest.mark.asyncio
    async def test_trace_decorator_async_preserves_metadata(self):
        """Test that trace decorator preserves async function metadata."""

        @trace()
        async def async_original_function():
            """Async original function docstring."""
            return "async_original"

        # Verify function metadata is preserved
        assert async_original_function.__name__ == "async_original_function"
        assert async_original_function.__doc__ == "Async original function docstring."

    def test_trace_decorator_with_exception_sync(self):
        """Test trace decorator behavior when sync function raises exception."""

        @trace()
        def failing_function():
            raise ValueError("Test exception")

        # Configure mock to raise exception - trace_function returns a decorator, which returns a wrapped function
        mock_decorated_func = Mock(side_effect=ValueError("Test exception"))
        mock_decorator = Mock(return_value=mock_decorated_func)
        self.mock_tracer.trace_function.return_value = mock_decorator

        # Verify exception is propagated
        with pytest.raises(ValueError, match="Test exception"):
            failing_function()

        # Verify tracer was still called
        self.mock_tracer.trace_function.assert_called_once()

    @pytest.mark.asyncio
    async def test_trace_decorator_with_exception_async(self):
        """Test trace decorator behavior when async function raises exception."""

        @trace()
        async def async_failing_function():
            raise ValueError("Async test exception")

        # Configure mock context manager that allows exception propagation
        mock_context = Mock()
        mock_context.__aenter__ = Mock(return_value=asyncio.Future())
        mock_context.__aenter__.return_value.set_result(None)
        mock_context.__aexit__ = Mock(return_value=asyncio.Future())
        mock_context.__aexit__.return_value.set_result(None)
        self.mock_tracer.trace_operation.return_value = mock_context

        # Verify exception is propagated
        with pytest.raises(ValueError, match="Async test exception"):
            await async_failing_function()

        # Verify tracer was called
        self.mock_tracer.trace_operation.assert_called_once()


class TestTraceUtilityFunctions:
    """Test trace utility functions following DRY principles."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_tracer = Mock()
        self.tracer_patcher = patch("src.utils.tracing_utils.distributed_tracer", self.mock_tracer)
        self.tracer_patcher.start()

    def teardown_method(self):
        """Clean up test fixtures."""
        self.tracer_patcher.stop()

    def test_add_trace_event_with_name_only(self):
        """Test adding trace event with name only."""
        add_trace_event("test_event")

        self.mock_tracer.add_event.assert_called_once_with("test_event", None)

    def test_add_trace_event_with_attributes(self):
        """Test adding trace event with name and attributes."""
        event_attributes = {"key1": "value1", "key2": 42}
        add_trace_event("complex_event", event_attributes)

        self.mock_tracer.add_event.assert_called_once_with("complex_event", event_attributes)

    def test_add_trace_event_empty_attributes(self):
        """Test adding trace event with empty attributes."""
        add_trace_event("empty_attr_event", {})

        self.mock_tracer.add_event.assert_called_once_with("empty_attr_event", {})

    def test_set_trace_attribute_string_value(self):
        """Test setting trace attribute with string value."""
        set_trace_attribute("user.name", "john_doe")

        self.mock_tracer.set_attribute.assert_called_once_with("user.name", "john_doe")

    def test_set_trace_attribute_numeric_value(self):
        """Test setting trace attribute with numeric value."""
        set_trace_attribute("request.size", 1024)

        self.mock_tracer.set_attribute.assert_called_once_with("request.size", 1024)

    def test_set_trace_attribute_boolean_value(self):
        """Test setting trace attribute with boolean value."""
        set_trace_attribute("cache.hit", True)

        self.mock_tracer.set_attribute.assert_called_once_with("cache.hit", True)

    def test_set_trace_attribute_none_value(self):
        """Test setting trace attribute with None value."""
        set_trace_attribute("optional.field", None)

        self.mock_tracer.set_attribute.assert_called_once_with("optional.field", None)

    def test_get_current_trace_context(self):
        """Test getting current trace context."""
        # Configure mock return values
        self.mock_tracer.get_current_trace_id.return_value = "trace_123"
        self.mock_tracer.get_current_span_id.return_value = "span_456"

        context = get_current_trace_context()

        # Verify correct context is returned
        expected_context = {
            "trace_id": "trace_123",
            "span_id": "span_456",
        }
        assert context == expected_context

        # Verify tracer methods were called
        self.mock_tracer.get_current_trace_id.assert_called_once()
        self.mock_tracer.get_current_span_id.assert_called_once()

    def test_get_current_trace_context_none_values(self):
        """Test getting current trace context when values are None."""
        # Configure mock to return None values
        self.mock_tracer.get_current_trace_id.return_value = None
        self.mock_tracer.get_current_span_id.return_value = None

        context = get_current_trace_context()

        # Verify None values are returned
        expected_context = {
            "trace_id": None,
            "span_id": None,
        }
        assert context == expected_context


class TestSpecializedTraceDecorators:
    """Test specialized trace decorators following SOLID principles."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_tracer = Mock()
        self.tracer_patcher = patch("src.utils.tracing_utils.distributed_tracer", self.mock_tracer)
        self.tracer_patcher.start()

    def teardown_method(self):
        """Clean up test fixtures."""
        self.tracer_patcher.stop()

    def test_trace_database_operation_decorator(self):
        """Test database operation tracing decorator."""

        @trace_database_operation("users", "select")
        def get_user_by_id(user_id):
            return f"User {user_id}"

        # Configure mock - trace_function returns a decorator, which returns a wrapped function
        mock_decorated_func = Mock(return_value="User 123")
        mock_decorator = Mock(return_value=mock_decorated_func)
        self.mock_tracer.trace_function.return_value = mock_decorator

        # Call decorated function
        result = get_user_by_id(123)

        # Verify database-specific tracing attributes
        expected_attributes = {
            "db.table": "users",
            "db.operation": "select",
            "component": "database",
        }
        self.mock_tracer.trace_function.assert_called_once_with("db.select", expected_attributes)
        assert result == "User 123"

    def test_trace_database_operation_insert(self):
        """Test database insert operation tracing."""

        @trace_database_operation("products", "insert")
        def create_product(product_data):
            return f"Created product {product_data['name']}"

        # Configure mock - trace_function returns a decorator, which returns a wrapped function
        mock_decorated_func = Mock(return_value="Created product Widget")
        mock_decorator = Mock(return_value=mock_decorated_func)
        self.mock_tracer.trace_function.return_value = mock_decorator

        # Call decorated function
        result = create_product({"name": "Widget"})

        # Verify insert operation tracing
        expected_attributes = {
            "db.table": "products",
            "db.operation": "insert",
            "component": "database",
        }
        self.mock_tracer.trace_function.assert_called_once_with("db.insert", expected_attributes)
        assert result == "Created product Widget"

    def test_trace_cache_operation_decorator(self):
        """Test cache operation tracing decorator."""

        @trace_cache_operation("redis", "get")
        def get_cached_value(key):
            return f"Value for {key}"

        # Configure mock - trace_function returns a decorator, which returns a wrapped function
        mock_decorated_func = Mock(return_value="Value for test_key")
        mock_decorator = Mock(return_value=mock_decorated_func)
        self.mock_tracer.trace_function.return_value = mock_decorator

        # Call decorated function
        result = get_cached_value("test_key")

        # Verify cache-specific tracing attributes
        expected_attributes = {
            "cache.type": "redis",
            "cache.operation": "get",
            "component": "cache",
        }
        self.mock_tracer.trace_function.assert_called_once_with("cache.get", expected_attributes)
        assert result == "Value for test_key"

    def test_trace_cache_operation_set(self):
        """Test cache set operation tracing."""

        @trace_cache_operation("memory", "set")
        def set_cached_value(key, value):
            return f"Set {key} = {value}"

        # Configure mock - trace_function returns a decorator, which returns a wrapped function
        mock_decorated_func = Mock(return_value="Set config = active")
        mock_decorator = Mock(return_value=mock_decorated_func)
        self.mock_tracer.trace_function.return_value = mock_decorator

        # Call decorated function
        result = set_cached_value("config", "active")

        # Verify set operation tracing
        expected_attributes = {
            "cache.type": "memory",
            "cache.operation": "set",
            "component": "cache",
        }
        self.mock_tracer.trace_function.assert_called_once_with("cache.set", expected_attributes)
        assert result == "Set config = active"

    def test_trace_http_request_decorator(self):
        """Test HTTP request tracing decorator."""

        @trace_http_request("GET", "https://api.example.com/users")
        def fetch_users():
            return {"users": []}

        # Configure mock - trace_function returns a decorator, which returns a wrapped function
        mock_decorated_func = Mock(return_value={"users": []})
        mock_decorator = Mock(return_value=mock_decorated_func)
        self.mock_tracer.trace_function.return_value = mock_decorator

        # Call decorated function
        result = fetch_users()

        # Verify HTTP-specific tracing attributes
        expected_attributes = {
            "http.method": "GET",
            "http.url": "https://api.example.com/users",
            "component": "http_client",
        }
        self.mock_tracer.trace_function.assert_called_once_with("http.get", expected_attributes)
        assert result == {"users": []}

    def test_trace_http_request_post(self):
        """Test HTTP POST request tracing."""

        @trace_http_request("POST", "https://api.example.com/users")
        def create_user(user_data):
            return {"id": 123, "name": user_data["name"]}

        # Configure mock - trace_function returns a decorator, which returns a wrapped function
        mock_decorated_func = Mock(return_value={"id": 123, "name": "John"})
        mock_decorator = Mock(return_value=mock_decorated_func)
        self.mock_tracer.trace_function.return_value = mock_decorator

        # Call decorated function
        result = create_user({"name": "John"})

        # Verify POST operation tracing
        expected_attributes = {
            "http.method": "POST",
            "http.url": "https://api.example.com/users",
            "component": "http_client",
        }
        self.mock_tracer.trace_function.assert_called_once_with("http.post", expected_attributes)
        assert result == {"id": 123, "name": "John"}

    def test_trace_database_operation_different_tables(self):
        """Test database operation tracing with different tables."""
        operations = [
            ("users", "select"),
            ("orders", "update"),
            ("products", "delete"),
            ("sessions", "insert"),
        ]

        for table, operation in operations:

            def make_db_operation(table_name, op_type):
                @trace_database_operation(table_name, op_type)
                def traced_db_operation():
                    return f"{op_type} on {table_name}"

                return traced_db_operation

            db_operation = make_db_operation(table, operation)

            # Configure mock - trace_function returns a decorator, which returns a wrapped function
            mock_decorated_func = Mock(return_value=f"{operation} on {table}")
            mock_decorator = Mock(return_value=mock_decorated_func)
            self.mock_tracer.trace_function.return_value = mock_decorator

            # Call decorated function
            result = db_operation()

            # Verify operation-specific tracing
            expected_attributes = {
                "db.table": table,
                "db.operation": operation,
                "component": "database",
            }
            expected_operation_name = f"db.{operation}"

            # Find the most recent call for this operation
            call_args = self.mock_tracer.trace_function.call_args
            assert call_args[0][0] == expected_operation_name
            assert call_args[0][1] == expected_attributes
            assert result == f"{operation} on {table}"

            # Reset mock for next iteration
            self.mock_tracer.reset_mock()

    def test_trace_cache_operation_different_types(self):
        """Test cache operation tracing with different cache types."""
        cache_configs = [
            ("redis", "get"),
            ("memory", "set"),
            ("file", "delete"),
            ("distributed", "invalidate"),
        ]

        for cache_type, operation in cache_configs:

            def make_cache_operation(cache_name, op_type):
                @trace_cache_operation(cache_name, op_type)
                def traced_cache_operation():
                    return f"{op_type} from {cache_name}"

                return traced_cache_operation

            cache_operation = make_cache_operation(cache_type, operation)

            # Configure mock - trace_function returns a decorator, which returns a wrapped function
            mock_decorated_func = Mock(return_value=f"{operation} from {cache_type}")
            mock_decorator = Mock(return_value=mock_decorated_func)
            self.mock_tracer.trace_function.return_value = mock_decorator

            # Call decorated function
            result = cache_operation()

            # Verify cache-specific tracing
            expected_attributes = {
                "cache.type": cache_type,
                "cache.operation": operation,
                "component": "cache",
            }
            expected_operation_name = f"cache.{operation}"

            call_args = self.mock_tracer.trace_function.call_args
            assert call_args[0][0] == expected_operation_name
            assert call_args[0][1] == expected_attributes
            assert result == f"{operation} from {cache_type}"

            # Reset mock for next iteration
            self.mock_tracer.reset_mock()


class TestTraceDecoratorEdgeCases:
    """Test edge cases and error conditions following modern testing practices."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_tracer = Mock()
        self.tracer_patcher = patch("src.utils.tracing_utils.distributed_tracer", self.mock_tracer)
        self.tracer_patcher.start()

    def teardown_method(self):
        """Clean up test fixtures."""
        self.tracer_patcher.stop()

    def test_trace_decorator_empty_attributes(self):
        """Test trace decorator with empty attributes dictionary."""

        @trace(attributes={})
        def function_with_empty_attrs():
            return "result"

        # Configure mock - trace_function returns a decorator, which returns a wrapped function
        mock_decorated_func = Mock(return_value="result")
        mock_decorator = Mock(return_value=mock_decorated_func)
        self.mock_tracer.trace_function.return_value = mock_decorator

        # Call decorated function
        result = function_with_empty_attrs()

        # Verify empty attributes are passed
        expected_span_name = (
            f"{function_with_empty_attrs.__module__}.{function_with_empty_attrs.__name__}"
        )
        self.mock_tracer.trace_function.assert_called_once_with(expected_span_name, {})
        assert result == "result"

    def test_trace_decorator_none_operation_name(self):
        """Test trace decorator with explicit None operation name."""

        @trace(operation_name=None)
        def function_with_none_name():
            return "none_result"

        # Configure mock - trace_function returns a decorator, which returns a wrapped function
        mock_decorated_func = Mock(return_value="none_result")
        mock_decorator = Mock(return_value=mock_decorated_func)
        self.mock_tracer.trace_function.return_value = mock_decorator

        # Call decorated function
        result = function_with_none_name()

        # Verify default name is used when None is provided
        expected_span_name = (
            f"{function_with_none_name.__module__}.{function_with_none_name.__name__}"
        )
        self.mock_tracer.trace_function.assert_called_once_with(expected_span_name, None)
        assert result == "none_result"

    def test_trace_decorator_complex_attributes(self):
        """Test trace decorator with complex attribute values."""
        complex_attributes = {
            "nested_dict": {"key": "value", "number": 42},
            "list_value": [1, 2, 3],
            "boolean_value": True,
            "none_value": None,
            "float_value": 3.14,
        }

        @trace(attributes=complex_attributes)
        def function_with_complex_attrs():
            return "complex_result"

        # Configure mock - trace_function returns a decorator, which returns a wrapped function
        mock_decorated_func = Mock(return_value="complex_result")
        mock_decorator = Mock(return_value=mock_decorated_func)
        self.mock_tracer.trace_function.return_value = mock_decorator

        # Call decorated function
        result = function_with_complex_attrs()

        # Verify complex attributes are passed through
        expected_span_name = (
            f"{function_with_complex_attrs.__module__}.{function_with_complex_attrs.__name__}"
        )
        self.mock_tracer.trace_function.assert_called_once_with(
            expected_span_name, complex_attributes
        )
        assert result == "complex_result"

    @pytest.mark.asyncio
    async def test_trace_decorator_async_function_detection(self):
        """Test that trace decorator correctly detects async functions."""

        @trace()
        async def async_function():
            return "async_result"

        # Verify the decorated function is still a coroutine
        assert asyncio.iscoroutinefunction(async_function)

        # Configure mock context manager
        mock_context = Mock()
        mock_context.__aenter__ = Mock(return_value=asyncio.Future())
        mock_context.__aenter__.return_value.set_result(None)
        mock_context.__aexit__ = Mock(return_value=asyncio.Future())
        mock_context.__aexit__.return_value.set_result(None)
        self.mock_tracer.trace_operation.return_value = mock_context

        # Call decorated function
        result = await async_function()

        # Verify async tracing path was used
        self.mock_tracer.trace_operation.assert_called_once()
        assert result == "async_result"

    def test_trace_decorator_function_with_args_and_kwargs(self):
        """Test trace decorator with function that has various argument types."""

        @trace()
        def function_with_various_args(
            pos1, pos2, *args, keyword1=None, keyword2="default", **kwargs
        ):
            return f"pos1={pos1}, pos2={pos2}, args={args}, kw1={keyword1}, kw2={keyword2}, kwargs={kwargs}"

        # Configure mock - trace_function returns a decorator, which returns a wrapped function
        expected_result = (
            "pos1=a, pos2=b, args=(c, d), kw1=test, kw2=custom, kwargs={'extra': 'value'}"
        )
        mock_decorated_func = Mock(return_value=expected_result)
        mock_decorator = Mock(return_value=mock_decorated_func)
        self.mock_tracer.trace_function.return_value = mock_decorator

        # Call decorated function with various arguments
        result = function_with_various_args(
            "a", "b", "c", "d", keyword1="test", keyword2="custom", extra="value"
        )

        # Verify all arguments were passed through correctly
        mock_decorated_func.assert_called_once_with(
            "a", "b", "c", "d", keyword1="test", keyword2="custom", extra="value"
        )
        assert result == expected_result
