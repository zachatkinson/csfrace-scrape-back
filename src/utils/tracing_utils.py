"""Utility functions and decorators for distributed tracing."""

from functools import wraps
from typing import Any, Callable, TypeVar

from ..monitoring import distributed_tracer

F = TypeVar('F', bound=Callable[..., Any])


def trace(operation_name: str | None = None, attributes: dict[str, Any] | None = None) -> Callable[[F], F]:
    """Decorator to add distributed tracing to any function.

    Args:
        operation_name: Name for the trace operation (defaults to function name)
        attributes: Additional attributes to attach to the span

    Returns:
        Decorated function with tracing

    Usage:
        @trace("scrape_wordpress_page")
        async def scrape_page(url: str) -> dict:
            return await fetch_content(url)

        @trace(attributes={"component": "auth"})
        def validate_token(token: str) -> bool:
            return jwt.decode(token)
    """
    def decorator(func: F) -> F:
        if hasattr(func, '__code__') and func.__code__.co_flags & 0x80:  # Check if coroutine
            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                span_name = operation_name or f"{func.__module__}.{func.__name__}"
                span_attributes = {
                    "function.name": func.__name__,
                    "function.module": func.__module__,
                    **(attributes or {})
                }
                
                async with distributed_tracer.trace_operation(span_name, span_attributes):
                    return await func(*args, **kwargs)
            
            return async_wrapper
        else:
            @wraps(func) 
            def sync_wrapper(*args, **kwargs):
                span_name = operation_name or f"{func.__module__}.{func.__name__}"
                return distributed_tracer.trace_function(span_name, attributes)(func)(*args, **kwargs)
            
            return sync_wrapper

    return decorator


def add_trace_event(name: str, attributes: dict[str, Any] | None = None) -> None:
    """Add an event to the current trace span.

    Args:
        name: Event name
        attributes: Event attributes

    Usage:
        add_trace_event("cache_miss", {"cache_type": "redis", "key": cache_key})
        add_trace_event("validation_passed", {"user_id": user.id})
    """
    distributed_tracer.add_event(name, attributes)


def set_trace_attribute(key: str, value: Any) -> None:
    """Set an attribute on the current trace span.

    Args:
        key: Attribute key
        value: Attribute value

    Usage:
        set_trace_attribute("user.id", current_user.id)
        set_trace_attribute("database.query_count", query_count)
    """
    distributed_tracer.set_attribute(key, value)


def get_current_trace_context() -> dict[str, str | None]:
    """Get current trace context information.

    Returns:
        Dictionary with current trace and span IDs

    Usage:
        context = get_current_trace_context()
        logger.info("Processing request", **context)
    """
    return {
        "trace_id": distributed_tracer.get_current_trace_id(),
        "span_id": distributed_tracer.get_current_span_id(),
    }


class TraceContextManager:
    """Context manager for manual span management.
    
    Usage:
        async with TraceContextManager("database_operation", {"table": "users"}) as span:
            result = await db.query("SELECT * FROM users")
            span.set_attribute("result_count", len(result))
    """
    
    def __init__(self, operation_name: str, attributes: dict[str, Any] | None = None):
        """Initialize trace context manager.
        
        Args:
            operation_name: Name of the operation
            attributes: Initial span attributes
        """
        self.operation_name = operation_name
        self.attributes = attributes or {}
        self._span_context = None

    async def __aenter__(self):
        """Enter async context and start span."""
        self._span_context = distributed_tracer.trace_operation(
            self.operation_name, 
            self.attributes
        )
        return await self._span_context.__aenter__()

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit async context and end span."""
        if self._span_context:
            return await self._span_context.__aexit__(exc_type, exc_val, exc_tb)


# Convenience functions for common tracing scenarios
def trace_database_operation(table: str, operation: str):
    """Decorator for database operations.
    
    Args:
        table: Database table name
        operation: Operation type (select, insert, update, delete)
    """
    return trace(
        operation_name=f"db.{operation}",
        attributes={
            "db.table": table,
            "db.operation": operation,
            "component": "database"
        }
    )


def trace_cache_operation(cache_type: str, operation: str):
    """Decorator for cache operations.
    
    Args:
        cache_type: Cache type (redis, memory, file)
        operation: Operation type (get, set, delete)
    """
    return trace(
        operation_name=f"cache.{operation}",
        attributes={
            "cache.type": cache_type,
            "cache.operation": operation,
            "component": "cache"
        }
    )


def trace_http_request(method: str, url: str):
    """Decorator for HTTP requests.
    
    Args:
        method: HTTP method
        url: Target URL
    """
    return trace(
        operation_name=f"http.{method.lower()}",
        attributes={
            "http.method": method,
            "http.url": url,
            "component": "http_client"
        }
    )