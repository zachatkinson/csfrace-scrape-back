"""Custom exceptions for the WordPress to Shopify converter."""



class ConversionError(Exception):
    """Base exception for conversion errors."""

    def __init__(self, message: str, url: str | None = None, cause: Exception | None = None):
        super().__init__(message)
        self.url = url
        self.cause = cause

    def __str__(self) -> str:
        msg = super().__str__()
        if self.url:
            msg = f"{msg} (URL: {self.url})"
        if self.cause:
            msg = f"{msg} (Caused by: {self.cause})"
        return msg


class FetchError(ConversionError):
    """Exception raised when fetching webpage fails."""

    pass


class ProcessingError(ConversionError):
    """Exception raised during content processing."""

    pass


class SaveError(ConversionError):
    """Exception raised when saving files fails."""

    pass


class RateLimitError(ConversionError):
    """Exception raised when rate limits are exceeded."""

    pass


class ConfigurationError(ConversionError):
    """Exception raised for configuration-related errors."""

    pass


class DatabaseError(Exception):
    """Exception raised for database-related errors."""

    def __init__(
        self, message: str, operation: str | None = None, cause: Exception | None = None
    ):
        super().__init__(message)
        self.operation = operation
        self.cause = cause

    def __str__(self) -> str:
        msg = super().__str__()
        if self.operation:
            msg = f"{msg} (Operation: {self.operation})"
        if self.cause:
            msg = f"{msg} (Caused by: {self.cause})"
        return msg


class BatchProcessingError(Exception):
    """Exception raised during batch processing operations."""

    def __init__(
        self, message: str, batch_id: int | None = None, cause: Exception | None = None
    ):
        super().__init__(message)
        self.batch_id = batch_id
        self.cause = cause

    def __str__(self) -> str:
        msg = super().__str__()
        if self.batch_id:
            msg = f"{msg} (Batch ID: {self.batch_id})"
        if self.cause:
            msg = f"{msg} (Caused by: {self.cause})"
        return msg
