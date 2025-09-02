"""Structured logging configuration using structlog."""

import logging

import structlog
from rich.logging import RichHandler


def setup_logging(verbose: bool = False) -> None:
    """Configure structured logging with Rich formatting.

    Args:
        verbose: Enable debug logging if True
    """
    log_level = logging.DEBUG if verbose else logging.INFO

    # Configure standard library logging
    logging.basicConfig(
        level=log_level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(rich_tracebacks=True)],
    )

    # Configure structlog without format_exc_info to avoid warnings
    # when we don't need exception tracebacks in structured logs
    structlog.configure(
        processors=[
            # Filter out log entries by level
            structlog.stdlib.filter_by_level,
            # Add log level and logger name
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            # Add timestamp
            structlog.processors.TimeStamper(fmt="ISO"),
            # Handle stack info if provided
            structlog.processors.StackInfoRenderer(),
            # Note: format_exc_info processor intentionally omitted to avoid
            # "Remove format_exc_info from your processor chain" warnings
            # when not using exception tracebacks in structured logs
            # Pretty print for development, JSON for production
            structlog.dev.ConsoleRenderer() if verbose else structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        context_class=dict,
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.BoundLogger:
    """Get a configured logger instance.

    Args:
        name: Logger name (usually __name__)

    Returns:
        Configured structlog logger
    """
    return structlog.get_logger(name)
