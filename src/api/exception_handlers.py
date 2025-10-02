"""FastAPI exception handlers following Single Responsibility Principle.

This module contains all application exception handlers including:
- Rate limit exception handler
- Global exception handler
- Specialized error handling for different exception types
"""

from typing import TYPE_CHECKING

from fastapi import Request
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded

from src.core.decorators import api_error_handler
from src.core.logging_hierarchy import get_api_logger

from .errors import APIErrorFactory

if TYPE_CHECKING:
    from fastapi import FastAPI

logger = get_api_logger()


class RateLimitHandler:
    """Handler for rate limiting exceptions."""

    @staticmethod
    @api_error_handler("handle rate limit")
    async def handle_rate_limit_exceeded(_request: Request, exc: Exception) -> JSONResponse:
        """Handle rate limit exceeded exceptions with proper headers using APIErrorFactory."""
        # Cast to RateLimitExceeded to access .detail attribute
        if isinstance(exc, RateLimitExceeded):
            detail_str = str(exc.detail)
        else:
            detail_str = "Rate limit exceeded"

        logger.warning("Rate limit exceeded", detail=detail_str)
        http_exc = APIErrorFactory.rate_limit_exceeded(f"Rate limit exceeded: {detail_str}")

        response = JSONResponse(status_code=http_exc.status_code, content=http_exc.detail)
        # Headers are automatically injected by SlowAPI when headers_enabled=True
        return response


class GlobalExceptionHandler:
    """Global exception handler for unhandled errors."""

    @staticmethod
    @api_error_handler("handle global exception")
    async def handle_global_exception(request: Request, exc: Exception) -> JSONResponse:
        """Global exception handler for unhandled errors using APIErrorFactory."""
        logger.error(
            "Unhandled exception occurred",
            path=str(request.url.path),
            method=request.method,
            error=str(exc),
            exception_type=type(exc).__name__,
        )

        http_exc = APIErrorFactory.internal_server_error(
            "An unexpected error occurred", original_error=exc
        )

        # Add request path to error details for debugging
        if isinstance(http_exc.detail, dict):
            http_exc.detail["path"] = str(request.url.path)

        return JSONResponse(status_code=http_exc.status_code, content=http_exc.detail)


def setup_exception_handlers(app: "FastAPI") -> None:
    """Setup all application exception handlers following SOLID principles.

    Args:
        app: FastAPI application instance
    """
    logger.info("Setting up application exception handlers")

    # Register rate limit exception handler
    app.add_exception_handler(RateLimitExceeded, RateLimitHandler.handle_rate_limit_exceeded)

    # Register global exception handler
    app.add_exception_handler(Exception, GlobalExceptionHandler.handle_global_exception)

    logger.info("Application exception handlers setup completed")
