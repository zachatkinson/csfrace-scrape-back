"""Common utilities for API endpoints."""

from __future__ import annotations

from functools import wraps
from typing import TYPE_CHECKING, Any, TypeVar

import asyncio
from fastapi import HTTPException, status
from pydantic import BaseModel, ValidationError
from sqlalchemy.exc import SQLAlchemyError

if TYPE_CHECKING:
    from collections.abc import Callable

T = TypeVar("T", bound=BaseModel)


def handle_database_error(operation: str):
    """Create a standardized API error for database errors.

    Args:
        operation: The operation that failed (e.g., 'create job', 'retrieve batches')

    Returns:
        Function that raises standardized API error for database errors
    """

    def error_handler(e: SQLAlchemyError):
        return HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to {operation}: {str(e)}",
        )

    return error_handler


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


# Deprecated error utilities - Use APIErrorFactory directly instead
# These are kept for backward compatibility but should be migrated
def unauthorized_error(detail: str):
    """Create standardized 401 Unauthorized response. DEPRECATED: Use APIErrorFactory.unauthorized instead."""
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def bad_request_error(detail: str):
    """Create standardized 400 Bad Request response. DEPRECATED: Use APIErrorFactory.bad_request instead."""
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


def internal_server_error(detail: str):
    """Create standardized 500 Internal Server Error response. DEPRECATED: Use APIErrorFactory.internal_server_error instead."""
    return HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=detail)


def validation_error(detail: str):
    """Create standardized 422 Unprocessable Entity response for validation errors. DEPRECATED: Use APIErrorFactory.validation_error instead."""
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=detail)


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


# HTTPException re-raise pattern (DRY principle)
def handle_api_exceptions(error_message: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator to handle HTTPException re-raising pattern consistently.

    This eliminates the common DRY violation of:
        except HTTPException:
            raise  # Re-raise HTTP exceptions
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error: {e}") from e

    Args:
        error_message: Custom error message for unexpected exceptions

    Usage:
        @handle_api_exceptions("Failed to process request")
        def my_endpoint():
            # Your endpoint logic here
            pass
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return await func(*args, **kwargs)
            except HTTPException:
                raise  # Re-raise HTTP exceptions as-is
            except Exception as e:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"{error_message}: {str(e)}",
                ) from e

        @wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return func(*args, **kwargs)
            except HTTPException:
                raise  # Re-raise HTTP exceptions as-is
            except Exception as e:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"{error_message}: {str(e)}",
                ) from e

        # Return appropriate wrapper based on function type
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


# Service error handling decorator (DRY principle)
def handle_service_errors(operation: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator to handle common service errors with standardized HTTP responses.

    This eliminates repetitive try/catch blocks across API endpoints and provides
    consistent error messaging following REST API best practices.

    Args:
        operation: Description of the operation for error messages (e.g., "create batch")

    Usage:
        @handle_service_errors("create jobs")
        async def create_jobs_endpoint(jobs_data: JobsCreateRequest, service: JobService):
            return await service.create_jobs(jobs_data)
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return await func(*args, **kwargs)
            except ValidationError as e:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Validation error in {operation}: {str(e)}",
                ) from e
            except SQLAlchemyError as e:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to {operation}: {str(e)}",
                ) from e
            except ValueError as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid data for {operation}: {str(e)}",
                ) from e

        @wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return func(*args, **kwargs)
            except ValidationError as e:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Validation error in {operation}: {str(e)}",
                ) from e
            except SQLAlchemyError as e:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to {operation}: {str(e)}",
                ) from e
            except ValueError as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid data for {operation}: {str(e)}",
                ) from e

        # Return appropriate wrapper based on function type
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator
