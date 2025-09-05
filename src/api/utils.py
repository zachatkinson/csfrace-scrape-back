"""Common utilities for API endpoints."""

from functools import wraps
from collections.abc import Callable
from typing import Any, TypeVar

from fastapi import HTTPException, status
from pydantic import BaseModel, ValidationError
from sqlalchemy.exc import SQLAlchemyError

T = TypeVar('T', bound=BaseModel)


def handle_database_error(operation: str) -> HTTPException:
    """Create a standardized HTTPException for database errors.

    Args:
        operation: The operation that failed (e.g., 'create job', 'retrieve batches')

    Returns:
        Standardized HTTPException for database errors
    """
    def error_handler(e: SQLAlchemyError) -> HTTPException:
        return HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to {operation}: {str(e)}",
        )
    return error_handler


def create_paginated_response(items: list, total: int, page: int, page_size: int) -> dict:
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
    items_key: str,
    items: list[Any],
    total: int,
    page: int,
    page_size: int
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


def rate_limited_endpoint(rate_limit: str):  # pylint: disable=unused-argument  # noqa: ARG001
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
    def decorator(func: Callable) -> Callable:
        # This decorator is primarily for documentation and doesn't modify behavior
        # SlowAPI handles the actual rate limiting via @limiter.limit() decorator
        return func
    return decorator


# Authentication error utilities (DRY principle)
def unauthorized_error(detail: str) -> HTTPException:
    """Create standardized 401 Unauthorized response."""
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def bad_request_error(detail: str) -> HTTPException:
    """Create standardized 400 Bad Request response."""
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=detail,
    )


def internal_server_error(detail: str) -> HTTPException:
    """Create standardized 500 Internal Server Error response."""
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=detail,
    )


# Assignment-from-none wrapper (DRY principle)
def maybe_none[T](func: Callable[..., T | None], *args, **kwargs) -> T | None:
    """Wrapper for functions that may return None - eliminates pylint warnings.
    
    This utility centralizes the pylint disable logic for functions that legitimately
    return None, making the intent explicit and reducing comment repetition.
    
    Usage:
        user = maybe_none(auth_service.authenticate_user, username, password)
        provider = maybe_none(service.get_provider, name)
    """
    return func(*args, **kwargs)  # pylint: disable=assignment-from-none


# Service error handling decorator (DRY principle)
def handle_service_errors(operation: str):
    """Decorator to handle common service errors with standardized HTTP responses.
    
    This eliminates repetitive try/catch blocks across API endpoints and provides
    consistent error messaging following REST API best practices.
    
    Args:
        operation: Description of the operation for error messages (e.g., "create batch")
        
    Usage:
        @handle_service_errors("create batch")
        async def create_batch_endpoint(batch_data: BatchCreate, service: BatchService):
            return await service.create_batch(batch_data)
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except ValidationError as e:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Validation error in {operation}: {str(e)}"
                ) from e
            except SQLAlchemyError as e:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to {operation}: {str(e)}"
                ) from e
            except ValueError as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid data for {operation}: {str(e)}"
                ) from e
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except ValidationError as e:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Validation error in {operation}: {str(e)}"
                ) from e
            except SQLAlchemyError as e:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to {operation}: {str(e)}"
                ) from e
            except ValueError as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid data for {operation}: {str(e)}"
                ) from e
        
        # Return appropriate wrapper based on function type
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    
    return decorator
