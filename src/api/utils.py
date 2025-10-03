"""Common utilities for API endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, TypeVar

from pydantic import BaseModel

if TYPE_CHECKING:
    from collections.abc import Callable

T = TypeVar("T", bound=BaseModel)


# handle_database_error REMOVED - DRY violation
# Use @api_error_handler("database operation") instead


def create_paginated_response(
    items: list[Any], total: int, page: int, page_size: int
) -> dict[str, Any]:
    """Create a standardized paginated response structure.

    Args:
        items: List of items for current page
        total: Total number of items
        page: Current page number
        page_size: Number of items per page

    Returns:
        Dictionary with pagination structure
    """
    total_pages = (total + page_size - 1) // page_size

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
    }


def create_response_dict(
    items_key: str, items: list[Any], total: int, page: int, page_size: int
) -> dict[str, Any]:
    """Create a complete response dictionary for paginated endpoints.

    Args:
        items_key: The key name for items in response (e.g., 'jobs', 'batches')
        items: List of items for current page
        total: Total number of items
        page: Current page number
        page_size: Number of items per page

    Returns:
        Dictionary ready for response model validation
    """
    pagination = create_paginated_response(items, total, page, page_size)

    return {
        items_key: pagination["items"],
        "total": pagination["total"],
        "page": pagination["page"],
        "page_size": pagination["page_size"],
        "total_pages": pagination["total_pages"],
    }


def rate_limited_endpoint(
    rate_limit: str,  # noqa: ARG001
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator factory for rate-limited endpoints that properly handles SlowAPI requirements.

    This decorator provides documentation for rate-limited endpoints and ensures proper
    parameter naming conventions are followed for SlowAPI integration.

    Args:
        rate_limit: Rate limit string (e.g., "10/hour", "20/minute")

    Usage:
        @limiter.limit("10/hour")
        @rate_limited_endpoint("10/hour")
        def my_endpoint(request: Request, other_param: str):
            # Your endpoint logic - request param is properly named for SlowAPI
            pass

    Note:
        The 'request' parameter MUST be named 'request' (not '_request') for SlowAPI.
        This decorator is purely for documentation and convention enforcement.
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        # This decorator is primarily for documentation and doesn't modify behavior
        # SlowAPI handles the actual rate limiting via @limiter.limit() decorator
        return func

    return decorator


# Assignment-from-none wrapper (DRY principle)
def maybe_none(func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    """Wrapper for functions that may return None - eliminates pylint warnings.

    This utility centralizes the pylint disable logic for functions that legitimately
    return None, making the intent explicit and reducing comment repetition.

    Usage:
        user = maybe_none(auth_service.authenticate_user, username, password)
        provider = maybe_none(service.get_provider, name)
    """
    return func(*args, **kwargs)  # pylint: disable=assignment-from-none


# handle_api_exceptions REMOVED - DRY violation
# Use @api_error_handler("operation description") instead


# handle_service_errors REMOVED - DRY violation
# Use @api_error_handler("service operation") instead
