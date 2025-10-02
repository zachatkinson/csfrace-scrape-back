"""Structured logging hierarchy for perfect DRY/SOLID compliance.

This module creates a hierarchical logging system with:
- Base logger configuration with service-specific children
- Consistent error context across all services
- Proper logger inheritance and specialization
- Centralized format and level management
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum
from typing import TYPE_CHECKING, Any, ClassVar

if TYPE_CHECKING:
    from structlog import BoundLogger


class LogLevel(Enum):
    """Standardized log levels with numeric values."""

    DEBUG = 10
    INFO = 20
    WARNING = 30
    ERROR = 40
    CRITICAL = 50


class ServiceType(Enum):
    """Service types for specialized logging behavior."""

    DATABASE = "database"
    AUTH = "auth"
    CACHE = "cache"
    MONITORING = "monitoring"
    API = "api"
    JOB = "job"
    SCRAPING = "scraping"
    GENERAL = "general"


class BaseLogger(ABC):
    """Abstract base logger defining the interface for all service loggers."""

    def __init__(self, name: str, service_type: ServiceType):
        """Initialize base logger with service-specific configuration.

        Args:
            name: Logger name (usually module name)
            service_type: Type of service for specialized behavior
        """
        self.name = name
        self.service_type = service_type
        self._logger = self._create_logger()

    @abstractmethod
    def _create_logger(self) -> BoundLogger:
        """Create the underlying logger instance."""
        pass

    @property
    def logger(self) -> BoundLogger:
        """Get the configured logger instance."""
        return self._logger

    def with_context(self, **kwargs: Any) -> BoundLogger:
        """Create logger with additional context."""
        return self._logger.bind(**kwargs)


class ServiceLogger(BaseLogger):
    """Concrete service logger with hierarchical configuration."""

    # Service-specific default log levels
    _SERVICE_LOG_LEVELS: ClassVar[dict[ServiceType, LogLevel]] = {
        ServiceType.DATABASE: LogLevel.INFO,
        ServiceType.AUTH: LogLevel.WARNING,  # Security sensitive
        ServiceType.CACHE: LogLevel.INFO,
        ServiceType.MONITORING: LogLevel.DEBUG,
        ServiceType.API: LogLevel.INFO,
        ServiceType.JOB: LogLevel.INFO,
        ServiceType.SCRAPING: LogLevel.INFO,
        ServiceType.GENERAL: LogLevel.INFO,
    }

    # Service-specific context fields
    _SERVICE_CONTEXTS: ClassVar[dict[ServiceType, dict[str, Any]]] = {
        ServiceType.DATABASE: {"component": "database", "layer": "persistence"},
        ServiceType.AUTH: {"component": "auth", "layer": "security", "sensitive": True},
        ServiceType.CACHE: {"component": "cache", "layer": "caching"},
        ServiceType.MONITORING: {"component": "monitoring", "layer": "observability"},
        ServiceType.API: {"component": "api", "layer": "presentation"},
        ServiceType.JOB: {"component": "job", "layer": "processing"},
        ServiceType.SCRAPING: {"component": "scraping", "layer": "extraction"},
        ServiceType.GENERAL: {"component": "general", "layer": "application"},
    }

    def _create_logger(self) -> BoundLogger:
        """Create service-specific logger with proper context."""
        # Get base logger from LoggerFactory
        from ..utils.logging import get_logger

        base_logger = get_logger(self.name)

        # Add service-specific context
        service_context = self._SERVICE_CONTEXTS.get(self.service_type, {})
        service_context.update(
            {
                "service_type": self.service_type.value,
                "logger_name": self.name,
            }
        )

        return base_logger.bind(**service_context)

    def get_default_level(self) -> LogLevel:
        """Get the default log level for this service type."""
        return self._SERVICE_LOG_LEVELS.get(self.service_type, LogLevel.INFO)

    def debug(self, msg: str, **kwargs: Any) -> None:
        """Log debug message."""
        self._logger.debug(msg, **kwargs)

    def info(self, msg: str, **kwargs: Any) -> None:
        """Log info message."""
        self._logger.info(msg, **kwargs)

    def warning(self, msg: str, **kwargs: Any) -> None:
        """Log warning message."""
        self._logger.warning(msg, **kwargs)

    def error(self, msg: str, **kwargs: Any) -> None:
        """Log error message."""
        self._logger.error(msg, **kwargs)

    def critical(self, msg: str, **kwargs: Any) -> None:
        """Log critical message."""
        self._logger.critical(msg, **kwargs)

    def bind(self, **kwargs: Any) -> BoundLogger:
        """Create logger with additional context (alias for with_context)."""
        return self._logger.bind(**kwargs)

    def exception(self, msg: str, **kwargs: Any) -> None:
        """Log exception message with traceback."""
        self._logger.exception(msg, **kwargs)


class LoggerHierarchy:
    """Central registry and factory for all service loggers."""

    _loggers: ClassVar[dict[str, ServiceLogger]] = {}
    _configured = False

    @classmethod
    def configure(cls, base_level: LogLevel = LogLevel.INFO) -> None:
        """Configure the logging hierarchy globally.

        Args:
            base_level: Base log level for all services
        """
        if cls._configured:
            return

        # Configure the underlying LoggerFactory
        from ..utils.logging import configure_logging

        configure_logging(base_level.name)
        cls._configured = True

    @classmethod
    def get_service_logger(cls, name: str, service_type: ServiceType) -> ServiceLogger:
        """Get or create a service logger.

        Args:
            name: Logger name (usually module name)
            service_type: Type of service

        Returns:
            Configured service logger
        """
        if not cls._configured:
            cls.configure()

        # Create unique key for this logger
        logger_key = f"{service_type.value}:{name}"

        if logger_key not in cls._loggers:
            cls._loggers[logger_key] = ServiceLogger(name, service_type)

        return cls._loggers[logger_key]

    @classmethod
    def get_database_logger(cls, name: str) -> ServiceLogger:
        """Get database service logger."""
        return cls.get_service_logger(name, ServiceType.DATABASE)

    @classmethod
    def get_auth_logger(cls, name: str) -> ServiceLogger:
        """Get auth service logger."""
        return cls.get_service_logger(name, ServiceType.AUTH)

    @classmethod
    def get_cache_logger(cls, name: str) -> ServiceLogger:
        """Get cache service logger."""
        return cls.get_service_logger(name, ServiceType.CACHE)

    @classmethod
    def get_monitoring_logger(cls, name: str) -> ServiceLogger:
        """Get monitoring service logger."""
        return cls.get_service_logger(name, ServiceType.MONITORING)

    @classmethod
    def get_api_logger(cls, name: str) -> ServiceLogger:
        """Get API service logger."""
        return cls.get_service_logger(name, ServiceType.API)

    @classmethod
    def get_job_logger(cls, name: str) -> ServiceLogger:
        """Get job processing logger."""
        return cls.get_service_logger(name, ServiceType.JOB)

    @classmethod
    def get_scraping_logger(cls, name: str) -> ServiceLogger:
        """Get scraping service logger."""
        return cls.get_service_logger(name, ServiceType.SCRAPING)

    @classmethod
    def get_general_logger(cls, name: str) -> ServiceLogger:
        """Get general purpose logger."""
        return cls.get_service_logger(name, ServiceType.GENERAL)


# Convenience functions for each service type
def get_database_logger(name: str | None = None) -> ServiceLogger:
    """Get database service logger with auto-detection of module name."""
    if name is None:
        import inspect

        frame = inspect.currentframe()
        if frame and frame.f_back:
            name = frame.f_back.f_globals.get("__name__", "unknown")
        else:
            name = "unknown"

    return LoggerHierarchy.get_database_logger(name)


def get_auth_logger(name: str | None = None) -> ServiceLogger:
    """Get auth service logger with auto-detection of module name."""
    if name is None:
        import inspect

        frame = inspect.currentframe()
        if frame and frame.f_back:
            name = frame.f_back.f_globals.get("__name__", "unknown")
        else:
            name = "unknown"

    return LoggerHierarchy.get_auth_logger(name)


def get_cache_logger(name: str | None = None) -> ServiceLogger:
    """Get cache service logger with auto-detection of module name."""
    if name is None:
        import inspect

        frame = inspect.currentframe()
        if frame and frame.f_back:
            name = frame.f_back.f_globals.get("__name__", "unknown")
        else:
            name = "unknown"

    return LoggerHierarchy.get_cache_logger(name)


def get_monitoring_logger(name: str | None = None) -> ServiceLogger:
    """Get monitoring service logger with auto-detection of module name."""
    if name is None:
        import inspect

        frame = inspect.currentframe()
        if frame and frame.f_back:
            name = frame.f_back.f_globals.get("__name__", "unknown")
        else:
            name = "unknown"

    return LoggerHierarchy.get_monitoring_logger(name)


def get_api_logger(name: str | None = None) -> ServiceLogger:
    """Get API service logger with auto-detection of module name."""
    if name is None:
        import inspect

        frame = inspect.currentframe()
        if frame and frame.f_back:
            name = frame.f_back.f_globals.get("__name__", "unknown")
        else:
            name = "unknown"

    return LoggerHierarchy.get_api_logger(name)


def get_job_logger(name: str | None = None) -> ServiceLogger:
    """Get job processing logger with auto-detection of module name."""
    if name is None:
        import inspect

        frame = inspect.currentframe()
        if frame and frame.f_back:
            name = frame.f_back.f_globals.get("__name__", "unknown")
        else:
            name = "unknown"

    return LoggerHierarchy.get_job_logger(name)


def get_scraping_logger(name: str | None = None) -> ServiceLogger:
    """Get scraping service logger with auto-detection of module name."""
    if name is None:
        import inspect

        frame = inspect.currentframe()
        if frame and frame.f_back:
            name = frame.f_back.f_globals.get("__name__", "unknown")
        else:
            name = "unknown"

    return LoggerHierarchy.get_scraping_logger(name)


def get_general_logger(name: str | None = None) -> ServiceLogger:
    """Get general purpose logger with auto-detection of module name."""
    if name is None:
        import inspect

        frame = inspect.currentframe()
        if frame and frame.f_back:
            name = frame.f_back.f_globals.get("__name__", "unknown")
        else:
            name = "unknown"

    return LoggerHierarchy.get_general_logger(name)


def get_core_logger(name: str | None = None) -> ServiceLogger:
    """Get core service logger with auto-detection of module name."""
    if name is None:
        import inspect

        frame = inspect.currentframe()
        if frame and frame.f_back:
            name = frame.f_back.f_globals.get("__name__", "unknown")
        else:
            name = "unknown"

    return LoggerHierarchy.get_general_logger(name)


# Enhanced LoggingMixin that uses the hierarchy
class ServiceLoggingMixin:
    """Mixin class providing service-specific logging capabilities."""

    # Subclasses should override this to specify their service type
    _service_type: ServiceType = ServiceType.GENERAL

    @property
    def logger(self) -> ServiceLogger:
        """Get service-specific logger for this class."""
        class_name = f"{self.__class__.__module__}.{self.__class__.__name__}"
        return LoggerHierarchy.get_service_logger(class_name, self._service_type)

    def log_with_context(self, **kwargs: Any) -> BoundLogger:
        """Get logger with additional context for this operation."""
        return self.logger.with_context(class_name=self.__class__.__name__, **kwargs)


# Specialized mixins for each service type
class DatabaseLoggingMixin(ServiceLoggingMixin):
    """Database service logging mixin."""

    _service_type = ServiceType.DATABASE


class AuthLoggingMixin(ServiceLoggingMixin):
    """Auth service logging mixin."""

    _service_type = ServiceType.AUTH


class CacheLoggingMixin(ServiceLoggingMixin):
    """Cache service logging mixin."""

    _service_type = ServiceType.CACHE


class MonitoringLoggingMixin(ServiceLoggingMixin):
    """Monitoring service logging mixin."""

    _service_type = ServiceType.MONITORING


class APILoggingMixin(ServiceLoggingMixin):
    """API service logging mixin."""

    _service_type = ServiceType.API


class JobLoggingMixin(ServiceLoggingMixin):
    """Job processing logging mixin."""

    _service_type = ServiceType.JOB


class ScrapingLoggingMixin(ServiceLoggingMixin):
    """Scraping service logging mixin."""

    _service_type = ServiceType.SCRAPING
