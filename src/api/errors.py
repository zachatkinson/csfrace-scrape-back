"""Centralized API error handling and response factory.

Eliminates DRY violations in error response creation and ensures
consistent error handling patterns across all API endpoints.
"""

import traceback
from typing import Any

import structlog
from fastapi import HTTPException, status
from sqlalchemy.exc import SQLAlchemyError

from ..core.environment import EnvironmentLoader

logger = structlog.get_logger(__name__)


class APIError(Exception):
    """Base class for all API-specific errors.

    Provides consistent error structure and context for all
    application-level errors.
    """

    def __init__(
        self,
        message: str,
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        error_code: str = "INTERNAL_ERROR",
        details: dict[str, Any] | None = None,
        original_error: Exception | None = None,
    ):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.error_code = error_code
        self.details = details or {}
        self.original_error = original_error


class ValidationError(APIError):
    """Error for request validation failures."""

    def __init__(self, message: str, field: str = None, details: dict[str, Any] = None):
        super().__init__(
            message=message,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            error_code="VALIDATION_ERROR",
            details=details or {},
        )
        if field:
            self.details["field"] = field


class ResourceNotFoundError(APIError):
    """Error for resource not found cases."""

    def __init__(self, resource_type: str, identifier: Any, details: dict[str, Any] = None):
        message = f"{resource_type} '{identifier}' not found"
        super().__init__(
            message=message,
            status_code=status.HTTP_404_NOT_FOUND,
            error_code="RESOURCE_NOT_FOUND",
            details=details or {},
        )
        self.details.update({"resource_type": resource_type, "identifier": str(identifier)})


class DatabaseError(APIError):
    """Error for database operation failures."""

    def __init__(self, operation: str, original_error: Exception, details: dict[str, Any] = None):
        message = f"Database operation failed: {operation}"
        super().__init__(
            message=message,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error_code="DATABASE_ERROR",
            details=details or {},
            original_error=original_error,
        )
        self.details["operation"] = operation


class BusinessLogicError(APIError):
    """Error for business logic violations."""

    def __init__(
        self, message: str, error_code: str = "BUSINESS_LOGIC_ERROR", details: dict[str, Any] = None
    ):
        super().__init__(
            message=message,
            status_code=status.HTTP_400_BAD_REQUEST,
            error_code=error_code,
            details=details or {},
        )


class APIErrorFactory:
    """Factory for creating consistent API error responses.

    Eliminates DRY violations by centralizing all error response
    creation with consistent structure and logging.
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
        error = ResourceNotFoundError(resource, identifier)
        cls._log_error(error)

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
        error = DatabaseError(operation, original_error)
        cls._log_error(error)

        return HTTPException(status_code=error.status_code, detail=cls._create_error_detail(error))

    @classmethod
    def validation_error(
        cls, message: str, field: str = None, details: dict[str, Any] = None
    ) -> HTTPException:
        """Create a standardized validation error response.

        Args:
            message: Validation error message
            field: Specific field that failed validation
            details: Additional validation details

        Returns:
            HTTPException with consistent validation error structure
        """
        error = ValidationError(message, field, details)
        cls._log_error(error)

        return HTTPException(status_code=error.status_code, detail=cls._create_error_detail(error))

    @classmethod
    def business_logic_error(cls, message: str, error_code: str = None) -> HTTPException:
        """Create a standardized business logic error response.

        Args:
            message: Business logic error message
            error_code: Specific error code for client handling

        Returns:
            HTTPException with consistent business logic error structure
        """
        error = BusinessLogicError(message, error_code or "BUSINESS_LOGIC_ERROR")
        cls._log_error(error)

        return HTTPException(status_code=error.status_code, detail=cls._create_error_detail(error))

    @classmethod
    def internal_server_error(
        cls, message: str = "Internal server error", original_error: Exception = None
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
        cls._log_error(error)

        return HTTPException(status_code=error.status_code, detail=cls._create_error_detail(error))

    @classmethod
    def unauthorized(cls, message: str = "Authentication required") -> HTTPException:
        """Create a standardized unauthorized error response."""
        error = APIError(
            message=message, status_code=status.HTTP_401_UNAUTHORIZED, error_code="UNAUTHORIZED"
        )
        cls._log_error(error)

        return HTTPException(status_code=error.status_code, detail=cls._create_error_detail(error))

    @classmethod
    def forbidden(cls, message: str = "Access denied") -> HTTPException:
        """Create a standardized forbidden error response."""
        error = APIError(
            message=message, status_code=status.HTTP_403_FORBIDDEN, error_code="FORBIDDEN"
        )
        cls._log_error(error)

        return HTTPException(status_code=error.status_code, detail=cls._create_error_detail(error))

    @classmethod
    def rate_limit_exceeded(cls, message: str = "Rate limit exceeded") -> HTTPException:
        """Create a standardized rate limit error response."""
        error = APIError(
            message=message,
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            error_code="RATE_LIMIT_EXCEEDED",
        )
        cls._log_error(error)

        return HTTPException(status_code=error.status_code, detail=cls._create_error_detail(error))

    @classmethod
    def service_unavailable(
        cls, message: str = "Service temporarily unavailable", details: dict = None
    ) -> HTTPException:
        """Create a standardized service unavailable error response."""
        error = APIError(
            message=message,
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            error_code="SERVICE_UNAVAILABLE",
            details=details or {},
        )
        cls._log_error(error)

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
        # Map specific SQLAlchemy errors to appropriate HTTP responses
        error_message = str(sql_error)

        if "duplicate key" in error_message.lower() or "unique constraint" in error_message.lower():
            return cls.validation_error(f"Duplicate resource in {operation}")
        elif "foreign key" in error_message.lower():
            return cls.validation_error(f"Invalid reference in {operation}")
        elif "not null" in error_message.lower():
            return cls.validation_error(f"Required field missing in {operation}")
        else:
            return cls.database_error(operation, sql_error)

    @classmethod
    def _create_error_detail(cls, error: APIError) -> dict[str, Any]:
        """Create standardized error detail structure.

        Args:
            error: API error instance

        Returns:
            Standardized error detail dictionary
        """
        detail = {
            "error": True,
            "message": error.message,
            "error_code": error.error_code,
            "timestamp": cls._get_timestamp(),
        }

        # Add details if present
        if error.details:
            detail["details"] = error.details

        # Add debug information if enabled (development only)
        if cls._debug_mode and error.original_error:
            detail["debug"] = {
                "original_error": str(error.original_error),
                "error_type": type(error.original_error).__name__,
                "traceback": traceback.format_exc() if error.original_error else None,
            }

        return detail

    @classmethod
    def _log_error(cls, error: APIError) -> None:
        """Log error with consistent structure.

        Args:
            error: API error to log
        """
        log_data = {
            "error_code": error.error_code,
            "status_code": error.status_code,
            "message": error.message,
        }

        if error.details:
            log_data["details"] = error.details

        if error.original_error:
            log_data["original_error"] = str(error.original_error)
            log_data["original_error_type"] = type(error.original_error).__name__

        if error.status_code >= 500:
            logger.error("API error occurred", **log_data)
        elif error.status_code >= 400:
            logger.warning("Client error occurred", **log_data)
        else:
            logger.info("API response", **log_data)

    @staticmethod
    def _get_timestamp() -> str:
        """Get current timestamp in ISO format."""
        from datetime import datetime

        return datetime.utcnow().isoformat() + "Z"


# Convenience functions for backward compatibility and common patterns
def not_found(resource: str, identifier: Any) -> HTTPException:
    """Convenience function for 404 errors."""
    return APIErrorFactory.not_found(resource, identifier)


def internal_server_error(message: str, original_error: Exception = None) -> HTTPException:
    """Convenience function for 500 errors."""
    return APIErrorFactory.internal_server_error(message, original_error)


def validation_error(message: str, field: str = None) -> HTTPException:
    """Convenience function for validation errors."""
    return APIErrorFactory.validation_error(message, field)


def database_error(operation: str, error: Exception) -> HTTPException:
    """Convenience function for database errors."""
    return APIErrorFactory.database_error(operation, error)


def business_logic_error(message: str, error_code: str = None) -> HTTPException:
    """Convenience function for business logic errors."""
    return APIErrorFactory.business_logic_error(message, error_code)


# Error handler for uncaught exceptions
def create_global_exception_handler():
    """Create global exception handler for FastAPI application.

    Returns:
        Exception handler function
    """

    async def global_exception_handler(request, exc: Exception):
        """Global exception handler for uncaught exceptions."""
        logger.error(
            "Uncaught exception in API",
            path=request.url.path,
            method=request.method,
            error=str(exc),
        )

        return APIErrorFactory.internal_server_error(
            "An unexpected error occurred", original_error=exc
        )

    return global_exception_handler
