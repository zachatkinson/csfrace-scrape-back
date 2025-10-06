"""Unified exception hierarchy for the entire application.

This module consolidates both APIError and ConversionError hierarchies into a
single, coherent exception system following DRY/SOLID principles.
"""

from datetime import UTC, datetime
from typing import Any

from src.core.logging_hierarchy import get_core_logger

logger = get_core_logger()


class BaseApplicationError(Exception):
    """Root base class for all application exceptions.

    Provides consistent error structure and context across all
    application domains (API, conversion, database, etc.).
    """

    def __init__(
        self,
        message: str,
        error_code: str = "APPLICATION_ERROR",
        details: dict[str, Any] | None = None,
        original_error: Exception | None = None,
        context: dict[str, Any] | None = None,
    ):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        self.original_error = original_error
        self.context = context or {}
        self.timestamp = datetime.now(UTC).isoformat().replace("+00:00", "Z")

    def __str__(self) -> str:
        """String representation with context."""
        msg = self.message
        if self.context:
            context_str = ", ".join(f"{k}={v}" for k, v in self.context.items())
            msg = f"{msg} ({context_str})"
        if self.original_error:
            msg = f"{msg} [Caused by: {self.original_error}]"
        return msg

    def to_dict(self) -> dict[str, Any]:
        """Convert exception to dictionary for serialization."""
        return {
            "error": True,
            "message": self.message,
            "error_code": self.error_code,
            "timestamp": self.timestamp,
            "details": self.details,
            "context": self.context,
            "original_error": str(self.original_error) if self.original_error else None,
            "original_error_type": type(self.original_error).__name__
            if self.original_error
            else None,
        }

    def log_error(self, log_level: str = "error") -> None:
        """Log this exception with appropriate level."""
        log_data = self.to_dict()
        log_func = getattr(logger, log_level, logger.error)
        log_func(f"Application error: {self.error_code}", **log_data)


# =============================================================================
# DOMAIN-SPECIFIC EXCEPTIONS
# =============================================================================


class ValidationError(BaseApplicationError):
    """Error for validation failures across all domains."""

    def __init__(
        self,
        message: str,
        field: str | None = None,
        value: Any = None,
        details: dict[str, Any] | None = None,
    ):
        super().__init__(
            message=message,
            error_code="VALIDATION_ERROR",
            details=details or {},
        )
        if field:
            self.details["field"] = field
        if value is not None:
            self.details["invalid_value"] = str(value)


class ResourceNotFoundError(BaseApplicationError):
    """Error for resource not found cases."""

    def __init__(
        self,
        resource_type: str,
        identifier: Any,
        details: dict[str, Any] | None = None,
    ):
        message = f"{resource_type} '{identifier}' not found"
        super().__init__(
            message=message,
            error_code="RESOURCE_NOT_FOUND",
            details=details or {},
            context={"resource_type": resource_type, "identifier": str(identifier)},
        )


class ConfigurationError(BaseApplicationError):
    """Error for configuration-related failures."""

    def __init__(
        self,
        config_key: str,
        message: str | None = None,
        details: dict[str, Any] | None = None,
    ):
        error_message = message or f"Configuration error for '{config_key}'"
        super().__init__(
            message=error_message,
            error_code="CONFIGURATION_ERROR",
            details=details or {},
            context={"config_key": config_key},
        )


class DatabaseError(BaseApplicationError):
    """Error for database operation failures."""

    def __init__(
        self,
        operation: str,
        original_error: Exception,
        details: dict[str, Any] | None = None,
    ):
        message = f"Database operation failed: {operation}"
        super().__init__(
            message=message,
            error_code="DATABASE_ERROR",
            details=details or {},
            original_error=original_error,
            context={"operation": operation},
        )


class BusinessLogicError(BaseApplicationError):
    """Error for business logic violations."""

    def __init__(
        self,
        message: str,
        error_code: str = "BUSINESS_LOGIC_ERROR",
        details: dict[str, Any] | None = None,
    ):
        super().__init__(
            message=message,
            error_code=error_code,
            details=details or {},
        )


class AuthenticationError(BaseApplicationError):
    """Error for authentication failures."""

    def __init__(
        self,
        message: str = "Authentication required",
        details: dict[str, Any] | None = None,
    ):
        super().__init__(
            message=message,
            error_code="AUTHENTICATION_ERROR",
            details=details or {},
        )


class AuthorizationError(BaseApplicationError):
    """Error for authorization failures."""

    def __init__(
        self,
        message: str = "Access denied",
        resource: str | None = None,
        action: str | None = None,
        details: dict[str, Any] | None = None,
    ):
        super().__init__(
            message=message,
            error_code="AUTHORIZATION_ERROR",
            details=details or {},
            context={
                k: v for k, v in [("resource", resource), ("action", action)] if v is not None
            },
        )


class AccountMergeRequiredError(BaseApplicationError):
    """Error raised when account merge is required to proceed with OAuth linking.

    This exception carries the AccountMergeDetection data and is caught by the
    router to return the appropriate response to the frontend.
    """

    def __init__(
        self,
        merge_detection: Any,  # AccountMergeDetection from auth.models
        message: str = "Account merge required to proceed",
        details: dict[str, Any] | None = None,
    ):
        super().__init__(
            message=message,
            error_code="ACCOUNT_MERGE_REQUIRED",
            details=details or {},
        )
        self.merge_detection = merge_detection


class RateLimitError(BaseApplicationError):
    """Error for rate limiting violations."""

    def __init__(
        self,
        message: str = "Rate limit exceeded",
        limit: int | None = None,
        window: str | None = None,
        details: dict[str, Any] | None = None,
    ):
        super().__init__(
            message=message,
            error_code="RATE_LIMIT_EXCEEDED",
            details=details or {},
            context={k: v for k, v in [("limit", limit), ("window", window)] if v is not None},
        )


class ServiceUnavailableError(BaseApplicationError):
    """Error for service unavailability."""

    def __init__(
        self,
        message: str = "Service temporarily unavailable",
        service_name: str | None = None,
        details: dict[str, Any] | None = None,
    ):
        super().__init__(
            message=message,
            error_code="SERVICE_UNAVAILABLE",
            details=details or {},
            context={"service": service_name} if service_name else {},
        )


# =============================================================================
# CONVERSION-SPECIFIC EXCEPTIONS
# =============================================================================


class ConversionError(BaseApplicationError):
    """Base exception for WordPress to Shopify conversion errors."""

    def __init__(
        self,
        message: str,
        url: str | None = None,
        error_code: str = "CONVERSION_ERROR",
        details: dict[str, Any] | None = None,
        original_error: Exception | None = None,
    ):
        super().__init__(
            message=message,
            error_code=error_code,
            details=details or {},
            original_error=original_error,
            context={"url": url} if url else {},
        )


class FetchError(ConversionError):
    """Exception raised when fetching webpage fails."""

    def __init__(
        self,
        message: str,
        url: str | None = None,
        status_code: int | None = None,
        details: dict[str, Any] | None = None,
        original_error: Exception | None = None,
    ):
        super().__init__(
            message=message,
            url=url,
            error_code="FETCH_ERROR",
            details=details or {},
            original_error=original_error,
        )
        if status_code:
            self.context["status_code"] = status_code


class ProcessingError(ConversionError):
    """Exception raised during content processing."""

    def __init__(
        self,
        message: str,
        url: str | None = None,
        processor: str | None = None,
        details: dict[str, Any] | None = None,
        original_error: Exception | None = None,
    ):
        super().__init__(
            message=message,
            url=url,
            error_code="PROCESSING_ERROR",
            details=details or {},
            original_error=original_error,
        )
        if processor:
            self.context["processor"] = processor


class SaveError(ConversionError):
    """Exception raised when saving files fails."""

    def __init__(
        self,
        message: str,
        url: str | None = None,
        file_path: str | None = None,
        details: dict[str, Any] | None = None,
        original_error: Exception | None = None,
    ):
        super().__init__(
            message=message,
            url=url,
            error_code="SAVE_ERROR",
            details=details or {},
            original_error=original_error,
        )
        if file_path:
            self.context["file_path"] = file_path


# =============================================================================
# API-SPECIFIC EXCEPTIONS (HTTP-aware)
# =============================================================================


class APIError(BaseApplicationError):
    """Base class for HTTP API-specific errors."""

    def __init__(
        self,
        message: str,
        status_code: int = 500,
        error_code: str = "API_ERROR",
        details: dict[str, Any] | None = None,
        original_error: Exception | None = None,
    ):
        super().__init__(
            message=message,
            error_code=error_code,
            details=details or {},
            original_error=original_error,
        )
        self.status_code = status_code


class APIValidationError(ValidationError, APIError):
    """API-specific validation error with HTTP status."""

    def __init__(
        self,
        message: str,
        field: str | None = None,
        value: Any = None,
        details: dict[str, Any] | None = None,
    ):
        # Call ValidationError.__init__ properly
        ValidationError.__init__(
            self,
            message=message,
            field=field,
            value=value,
            details=details,
        )
        # Set API-specific attributes
        self.status_code = 422
        self.error_code = "API_VALIDATION_ERROR"


class APINotFoundError(ResourceNotFoundError, APIError):
    """API-specific not found error with HTTP status."""

    def __init__(
        self,
        resource_type: str,
        identifier: Any,
        details: dict[str, Any] | None = None,
    ):
        # Call BaseApplicationError.__init__ directly to avoid MRO issues
        message = f"{resource_type} '{identifier}' not found"
        BaseApplicationError.__init__(
            self,
            message=message,
            error_code="API_NOT_FOUND",
            details=details or {},
        )
        # Set API-specific attributes
        self.status_code = 404
        self.context = {"resource_type": resource_type, "identifier": str(identifier)}


class APIDatabaseError(DatabaseError, APIError):
    """API-specific database error with HTTP status."""

    def __init__(
        self,
        operation: str,
        original_error: Exception,
        details: dict[str, Any] | None = None,
    ):
        # Call BaseApplicationError.__init__ directly to avoid MRO issues
        message = f"Database operation failed: {operation}"
        BaseApplicationError.__init__(
            self,
            message=message,
            error_code="API_DATABASE_ERROR",
            details=details or {},
            original_error=original_error,
        )
        # Set API-specific attributes
        self.status_code = 500
        self.context = {"operation": operation}


class APIBusinessLogicError(BusinessLogicError, APIError):
    """API-specific business logic error with HTTP status."""

    def __init__(
        self,
        message: str,
        error_code: str = "API_BUSINESS_LOGIC_ERROR",
        details: dict[str, Any] | None = None,
    ):
        # Call BusinessLogicError.__init__ properly
        BusinessLogicError.__init__(
            self,
            message=message,
            error_code=error_code,
            details=details,
        )
        # Set API-specific attributes
        self.status_code = 400
        self.error_code = error_code


# =============================================================================
# EXCEPTION MAPPING AND CONVERSION UTILITIES
# =============================================================================


class ExceptionMapper:
    """Utility class for mapping between exception types."""

    @staticmethod
    def to_api_error(exc: BaseApplicationError) -> APIError:
        """Convert any application error to an API error."""
        if isinstance(exc, APIError):
            return exc

        # Map specific types to appropriate HTTP status codes
        status_map = {
            "VALIDATION_ERROR": 422,
            "RESOURCE_NOT_FOUND": 404,
            "AUTHENTICATION_ERROR": 401,
            "AUTHORIZATION_ERROR": 403,
            "RATE_LIMIT_EXCEEDED": 429,
            "SERVICE_UNAVAILABLE": 503,
            "DATABASE_ERROR": 500,
            "CONVERSION_ERROR": 500,
            "FETCH_ERROR": 502,
            "PROCESSING_ERROR": 500,
            "SAVE_ERROR": 500,
        }

        status_code = status_map.get(exc.error_code, 500)
        api_error_code = f"API_{exc.error_code}"

        return APIError(
            message=exc.message,
            status_code=status_code,
            error_code=api_error_code,
            details=exc.details,
            original_error=exc.original_error,
        )

    @staticmethod
    def from_sqlalchemy_error(operation: str, sql_error: Exception) -> BaseApplicationError:
        """Convert SQLAlchemy errors to standardized database errors."""
        error_message = str(sql_error)

        # Determine specific error type based on message
        if "duplicate key" in error_message.lower() or "unique constraint" in error_message.lower():
            return ValidationError(
                message=f"Duplicate resource in {operation}",
                details={"operation": operation, "constraint_type": "unique"},
            )
        elif "foreign key" in error_message.lower():
            return ValidationError(
                message=f"Invalid reference in {operation}",
                details={"operation": operation, "constraint_type": "foreign_key"},
            )
        elif "not null" in error_message.lower():
            return ValidationError(
                message=f"Required field missing in {operation}",
                details={"operation": operation, "constraint_type": "not_null"},
            )
        else:
            return DatabaseError(operation, sql_error)
