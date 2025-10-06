"""Centralized logging utility following DRY principles.

This module provides a single point of configuration for structured logging
across the entire application, eliminating duplicate import patterns.
"""

import os
import sys
from typing import TYPE_CHECKING, Any, cast

import structlog

if TYPE_CHECKING:
    from collections.abc import Callable


class LoggerFactory:
    """Factory for creating consistent structured loggers across the application."""

    _configured = False
    _log_level = "INFO"

    @classmethod
    def configure(
        cls,
        log_level: str = "INFO",
        enable_json: bool | None = None,
        enable_colors: bool | None = None,
    ) -> None:
        """Configure structlog globally for the application.

        Args:
            log_level: Log level (DEBUG, INFO, WARNING, ERROR)
            enable_json: Force JSON output (None = auto-detect)
            enable_colors: Force colored output (None = auto-detect)
        """
        if cls._configured:
            return

        cls._log_level = log_level

        # Auto-detect output format based on environment
        if enable_json is None:
            enable_json = not sys.stderr.isatty() or os.getenv("LOG_FORMAT") == "json"

        if enable_colors is None:
            enable_colors = sys.stderr.isatty() and os.getenv("NO_COLOR") is None

        # Configure processors (compatible with PrintLoggerFactory)
        processors: list[Callable[..., Any]] = [
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
        ]

        # Add appropriate renderer
        if enable_json:
            processors.append(structlog.processors.JSONRenderer())
        else:
            if enable_colors:
                processors.append(structlog.dev.ConsoleRenderer(colors=True))
            else:
                processors.append(structlog.dev.ConsoleRenderer(colors=False))

        # Configure structlog
        structlog.configure(
            processors=processors,
            wrapper_class=structlog.make_filtering_bound_logger(
                getattr(structlog, log_level.upper(), 20)
            ),
            logger_factory=structlog.PrintLoggerFactory(),
            cache_logger_on_first_use=True,
        )

        cls._configured = True

    @classmethod
    def get_logger(cls, name: str | None = None) -> structlog.BoundLogger:
        """Get a configured logger instance.

        Args:
            name: Logger name (defaults to caller's module name)

        Returns:
            Configured structured logger
        """
        # Auto-configure if not already done
        if not cls._configured:
            cls.configure()

        # Use provided name or auto-detect from caller
        if name is None:
            import inspect

            frame = inspect.currentframe()
            if frame is not None and frame.f_back is not None:
                name = frame.f_back.f_globals.get("__name__", "unknown")
            else:
                name = "unknown"

        return cast("structlog.BoundLogger", structlog.get_logger(name))


def get_logger(name: str | None = None) -> structlog.BoundLogger:
    """Convenience function to get a logger instance.

    This is the main entry point that all modules should use:

    ```python
    from src.core.logging_hierarchy import get_core_logger

    logger = get_core_logger()  # or just get_logger()
    ```

    Args:
        name: Logger name (auto-detected if None)

    Returns:
        Configured structured logger
    """
    return LoggerFactory.get_logger(name)


def configure_logging(
    log_level: str | None = None,
    enable_json: bool | None = None,
    enable_colors: bool | None = None,
) -> None:
    """Configure application logging from environment variables.

    Environment variables:
        LOG_LEVEL: DEBUG, INFO, WARNING, ERROR (default: INFO)
        LOG_FORMAT: json, console (default: auto-detect)
        NO_COLOR: Set to disable colored output

    Args:
        log_level: Override environment LOG_LEVEL
        enable_json: Override format auto-detection
        enable_colors: Override color auto-detection
    """
    # Get log level from environment or parameter
    if log_level is None:
        log_level = os.getenv("LOG_LEVEL", "INFO")

    LoggerFactory.configure(
        log_level=log_level, enable_json=enable_json, enable_colors=enable_colors
    )


def with_context(**kwargs: Any) -> structlog.BoundLogger:
    """Create a logger with additional context.

    Args:
        **kwargs: Context key-value pairs to bind to logger

    Returns:
        Logger with bound context

    Example:
        ```python
        logger = with_context(user_id=123, request_id="abc-def")
        logger.info("User action performed")
        ```
    """
    import inspect

    frame = inspect.currentframe()
    if frame is not None and frame.f_back is not None:
        name = frame.f_back.f_globals.get("__name__", "unknown")
    else:
        name = "unknown"

    return get_logger(name).bind(**kwargs)


# Common logging patterns as utilities
class LoggingMixin:
    """Mixin class to add logging capabilities to any class."""

    @property
    def logger(self) -> structlog.BoundLogger:
        """Get a logger bound to this class."""
        class_name = f"{self.__class__.__module__}.{self.__class__.__name__}"
        return get_logger(class_name)
