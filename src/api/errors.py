"""Centralized API error handling and response factory.

Eliminates DRY violations in error response creation and ensures
consistent error handling patterns across all API endpoints.

Updated to use the unified exception hierarchy from core.exceptions.
"""

import traceback
from collections.abc import Callable
from typing import Any

from fastapi import HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from starlette.types import ASGIApp, Receive, Scope, Send

from src.core.logging_hierarchy import get_api_logger

from ..core.environment import EnvironmentLoader
from ..core.exceptions import (
    APIBusinessLogicError,
    APIDatabaseError,
    APIError,
    APINotFoundError,
    APIValidationError,
    AuthenticationError,
    AuthorizationError,
    BaseApplicationError,
    ExceptionMapper,
    RateLimitError,
    ServiceUnavailableError,
)

logger = get_api_logger()


class APIErrorFactory:
    """Factory for creating consistent API error responses.

    Eliminates DRY violations by centralizing all error response
    creation with consistent structure and logging.

    Updated to use unified exception hierarchy for better consistency.
    """

    # Enable debug mode for detailed error information
    _debug_mode = EnvironmentLoader.get_bool("API_DEBUG_ERRORS", False)

    @classmethod
    def not_found(cls, resource: str, identifier: Any) -> HTTPException:
        """Create a standardized 404 Not Found response.

        Args:
            resource: Type of resource (e.g., 'Batch', 'Job', 'User')
            identifier: Resource identifier that wasn't found

        Returns:
            HTTPException with consistent 404 structure
        """
        error = APINotFoundError(resource, identifier)
        error.log_error("warning")
        return HTTPException(status_code=error.status_code, detail=cls._create_error_detail(error))

    @classmethod
    def database_error(cls, operation: str, original_error: Exception) -> HTTPException:
        """Create a standardized database error response.

        Args:
            operation: Database operation that failed (e.g., 'create batch', 'update job')
            original_error: Original database exception

        Returns:
            HTTPException with consistent database error structure
        """
        error = APIDatabaseError(operation, original_error)
        error.log_error("error")
        return HTTPException(status_code=error.status_code, detail=cls._create_error_detail(error))

    @classmethod
    def validation_error(
        cls, message: str, field: str | None = None, details: dict[str, Any] | None = None
    ) -> HTTPException:
        """Create a standardized validation error response.

        Args:
            message: Validation error message
            field: Specific field that failed validation
            details: Additional validation details

        Returns:
            HTTPException with consistent validation error structure
        """
        error = APIValidationError(message, field, details=details)
        error.log_error("warning")
        return HTTPException(status_code=error.status_code, detail=cls._create_error_detail(error))

    @classmethod
    def business_logic_error(cls, message: str, error_code: str | None = None) -> HTTPException:
        """Create a standardized business logic error response.

        Args:
            message: Business logic error message
            error_code: Specific error code for client handling

        Returns:
            HTTPException with consistent business logic error structure
        """
        error = APIBusinessLogicError(message, error_code or "API_BUSINESS_LOGIC_ERROR")
        error.log_error("warning")
        return HTTPException(status_code=error.status_code, detail=cls._create_error_detail(error))

    @classmethod
    def internal_server_error(
        cls, message: str = "Internal server error", original_error: Exception | None = None
    ) -> HTTPException:
        """Create a standardized internal server error response.

        Args:
            message: Error message (generic for security)
            original_error: Original exception for logging

        Returns:
            HTTPException with consistent 500 error structure
        """
        error = APIError(
            message=message,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error_code="INTERNAL_SERVER_ERROR",
            original_error=original_error,
        )
        error.log_error("error")
        return HTTPException(status_code=error.status_code, detail=cls._create_error_detail(error))

    @classmethod
    def unauthorized(cls, message: str = "Authentication required") -> HTTPException:
        """Create a standardized unauthorized error response."""
        # Use base AuthenticationError and convert to API error
        auth_error = AuthenticationError(message)
        error = ExceptionMapper.to_api_error(auth_error)
        error.log_error("warning")
        return HTTPException(status_code=error.status_code, detail=cls._create_error_detail(error))

    @classmethod
    def forbidden(cls, message: str = "Access denied") -> HTTPException:
        """Create a standardized forbidden error response."""
        # Use base AuthorizationError and convert to API error
        authz_error = AuthorizationError(message)
        error = ExceptionMapper.to_api_error(authz_error)
        error.log_error("warning")
        return HTTPException(status_code=error.status_code, detail=cls._create_error_detail(error))

    @classmethod
    def rate_limit_exceeded(cls, message: str = "Rate limit exceeded") -> HTTPException:
        """Create a standardized rate limit error response."""
        # Use base RateLimitError and convert to API error
        rate_error = RateLimitError(message)
        error = ExceptionMapper.to_api_error(rate_error)
        error.log_error("warning")
        return HTTPException(status_code=error.status_code, detail=cls._create_error_detail(error))

    @classmethod
    def service_unavailable(
        cls, message: str = "Service temporarily unavailable", details: dict[Any, Any] | None = None
    ) -> HTTPException:
        """Create a standardized service unavailable error response."""
        # Use base ServiceUnavailableError and convert to API error
        service_error = ServiceUnavailableError(message, details=details)
        error = ExceptionMapper.to_api_error(service_error)
        error.log_error("error")
        return HTTPException(status_code=error.status_code, detail=cls._create_error_detail(error))

    @classmethod
    def from_sqlalchemy_error(cls, operation: str, sql_error: SQLAlchemyError) -> HTTPException:
        """Convert SQLAlchemy errors to standardized API errors.

        Args:
            operation: Operation that caused the error
            sql_error: Original SQLAlchemy exception

        Returns:
            HTTPException with appropriate error type
        """
        # Use the unified exception mapper
        base_error = ExceptionMapper.from_sqlalchemy_error(operation, sql_error)
        api_error = ExceptionMapper.to_api_error(base_error)
        api_error.log_error("error" if api_error.status_code >= 500 else "warning")
        return HTTPException(
            status_code=api_error.status_code, detail=cls._create_error_detail(api_error)
        )

    @classmethod
    def from_application_error(cls, app_error: BaseApplicationError) -> HTTPException:
        """Convert any application error to an HTTP exception.

        This is the new unified method for handling all application errors.

        Args:
            app_error: Any application error from the unified hierarchy

        Returns:
            HTTPException with appropriate status and structure
        """
        api_error = ExceptionMapper.to_api_error(app_error)
        log_level = "error" if api_error.status_code >= 500 else "warning"
        api_error.log_error(log_level)
        return HTTPException(
            status_code=api_error.status_code, detail=cls._create_error_detail(api_error)
        )

    @classmethod
    def _create_error_detail(cls, error: BaseApplicationError) -> dict[str, Any]:
        """Create standardized error detail structure.

        Args:
            error: Application error instance

        Returns:
            Standardized error detail dictionary
        """
        detail = error.to_dict()

        # Add debug information if enabled (development only)
        if cls._debug_mode and error.original_error:
            detail["debug"] = {
                "original_error": str(error.original_error),
                "error_type": type(error.original_error).__name__,
                "traceback": traceback.format_exc() if error.original_error else None,
            }

        return detail

    @staticmethod
    def _get_timestamp() -> str:
        """Get current timestamp in ISO format."""
        from datetime import UTC, datetime

        return datetime.now(UTC).isoformat().replace("+00:00", "Z")


# =============================================================================
# GLOBAL EXCEPTION HANDLER
# =============================================================================


def create_global_exception_handler() -> Callable[[Any, Exception], Any]:
    """Create global exception handler for FastAPI application.

    Returns:
        Exception handler function that uses unified exception system
    """

    async def global_exception_handler(request: Any, exc: Exception) -> JSONResponse:
        """Global exception handler for uncaught exceptions."""
        logger.error(
            "Uncaught exception in API",
            path=request.url.path,
            method=request.method,
            error=str(exc),
            error_type=type(exc).__name__,
        )

        # Handle application errors with unified system
        if isinstance(exc, BaseApplicationError):
            http_exception = APIErrorFactory.from_application_error(exc)
        else:
            # Handle unexpected exceptions
            http_exception = APIErrorFactory.internal_server_error(
                "An unexpected error occurred", original_error=exc
            )

        return JSONResponse(status_code=http_exception.status_code, content=http_exception.detail)

    return global_exception_handler


# =============================================================================
# EXCEPTION MIDDLEWARE FOR AUTOMATIC CONVERSION
# =============================================================================


class UnifiedExceptionMiddleware:
    """Middleware to automatically convert application errors to HTTP responses."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """ASGI middleware for exception handling."""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def exception_handler(exc: Exception) -> None:
            """Handle exceptions and convert to appropriate HTTP responses."""
            if isinstance(exc, BaseApplicationError):
                http_exception = APIErrorFactory.from_application_error(exc)
                response = JSONResponse(
                    status_code=http_exception.status_code, content=http_exception.detail
                )
                await response(scope, receive, send)
            else:
                # Let other exceptions bubble up
                raise exc

        try:
            await self.app(scope, receive, send)
        except BaseApplicationError as e:
            await exception_handler(e)
