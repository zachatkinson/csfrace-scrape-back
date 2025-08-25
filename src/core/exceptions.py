"""Custom exceptions for the WordPress to Shopify converter."""

from typing import Optional


class ConversionError(Exception):
    """Base exception for conversion errors."""
    
    def __init__(self, message: str, url: Optional[str] = None, cause: Optional[Exception] = None):
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