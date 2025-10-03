"""Service abstractions following Dependency Inversion Principle.

This module defines abstract interfaces for core application services,
allowing concrete implementations to be swapped without changing dependent code.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Protocol, TypeVar

from src.core.decorators import content_processing_error_handler
from src.core.logging_hierarchy import get_core_logger

logger = get_core_logger()

# Type variable for service registry
T = TypeVar("T")


class DatabaseServiceProtocol(Protocol):
    """Protocol for database service implementations."""

    async def get_session(self) -> Any:
        """Get database session."""
        ...

    async def execute_query(self, query: str, params: dict[str, Any] | None = None) -> Any:
        """Execute database query."""
        ...

    async def health_check(self) -> dict[str, Any]:
        """Perform database health check."""
        ...

    async def initialize(self) -> bool:
        """Initialize database connection."""
        ...

    async def shutdown(self) -> bool:
        """Shutdown database connection."""
        ...


class CacheServiceProtocol(Protocol):
    """Protocol for cache service implementations."""

    async def get(self, key: str) -> Any:
        """Get value from cache."""
        ...

    async def set(self, key: str, value: Any, ttl: int | None = None) -> bool:
        """Set value in cache."""
        ...

    async def delete(self, key: str) -> bool:
        """Delete value from cache."""
        ...

    async def clear(self) -> bool:
        """Clear all cache entries."""
        ...

    async def health_check(self) -> dict[str, Any]:
        """Perform cache health check."""
        ...


class AuthServiceProtocol(Protocol):
    """Protocol for authentication service implementations."""

    async def authenticate_user(self, token: str) -> dict[str, Any] | None:
        """Authenticate user from token."""
        ...

    async def create_token(self, user_id: str) -> str:
        """Create authentication token."""
        ...

    async def revoke_token(self, token: str) -> bool:
        """Revoke authentication token."""
        ...

    async def validate_permissions(self, user_id: str, resource: str, action: str) -> bool:
        """Validate user permissions."""
        ...


class JobServiceProtocol(Protocol):
    """Protocol for job service implementations."""

    async def create_job(self, job_data: dict[str, Any]) -> str:
        """Create new job."""
        ...

    async def get_job(self, job_id: str) -> dict[str, Any] | None:
        """Get job by ID."""
        ...

    async def update_job_status(self, job_id: str, status: str) -> bool:
        """Update job status."""
        ...

    async def list_jobs(self, filters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        """List jobs with optional filters."""
        ...

    async def cancel_job(self, job_id: str) -> bool:
        """Cancel running job."""
        ...


class NotificationServiceProtocol(Protocol):
    """Protocol for notification service implementations."""

    async def send_notification(
        self, message: str, recipients: list[str], channel: str = "email"
    ) -> bool:
        """Send notification to recipients."""
        ...

    async def send_alert(self, alert_data: dict[str, Any], severity: str = "info") -> bool:
        """Send alert notification."""
        ...


class ConfigurationServiceProtocol(Protocol):
    """Protocol for configuration service implementations."""

    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value."""
        ...

    def set(self, key: str, value: Any) -> bool:
        """Set configuration value."""
        ...

    def get_section(self, section: str) -> dict[str, Any]:
        """Get configuration section."""
        ...

    async def reload(self) -> bool:
        """Reload configuration."""
        ...


class BaseService(ABC):
    """Abstract base class for application services.

    Provides common service functionality while enforcing
    initialization and lifecycle management contracts.
    """

    def __init__(self, config: dict[str, Any] | None = None):
        """Initialize service.

        Args:
            config: Service configuration
        """
        self.config = config or {}
        self.logger = get_core_logger()
        self._initialized = False
        self._healthy = False

    @abstractmethod
    async def initialize(self) -> bool:
        """Initialize the service.

        Returns:
            True if initialization successful
        """
        pass

    @abstractmethod
    async def shutdown(self) -> bool:
        """Shutdown the service.

        Returns:
            True if shutdown successful
        """
        pass

    @abstractmethod
    async def health_check(self) -> dict[str, Any]:
        """Perform service health check.

        Returns:
            Health check results
        """
        pass

    @property
    def is_initialized(self) -> bool:
        """Check if service is initialized."""
        return self._initialized

    @property
    def is_healthy(self) -> bool:
        """Check if service is healthy."""
        return self._healthy

    def _mark_initialized(self) -> None:
        """Mark service as initialized."""
        self._initialized = True
        self._healthy = True
        self.logger.info(f"{self.__class__.__name__} initialized successfully")

    def _mark_unhealthy(self, reason: str) -> None:
        """Mark service as unhealthy."""
        self._healthy = False
        self.logger.warning(f"{self.__class__.__name__} marked unhealthy", reason=reason)

    def _mark_shutdown(self) -> None:
        """Mark service as shutdown."""
        self._initialized = False
        self._healthy = False
        self.logger.info(f"{self.__class__.__name__} shutdown completed")


class ServiceRegistry:
    """Registry for managing service instances and dependencies.

    Provides centralized service discovery and lifecycle management
    following the Service Locator pattern with dependency injection.
    """

    def __init__(self) -> None:
        """Initialize service registry."""
        self._services: dict[type, Any] = {}
        self._service_configs: dict[type, dict[str, Any]] = {}
        self.logger = get_core_logger()

    def register_service(
        self, service_type: type, service_instance: Any, config: dict[str, Any] | None = None
    ) -> None:
        """Register service instance.

        Args:
            service_type: Service type/interface
            service_instance: Service implementation instance
            config: Service configuration
        """
        self._services[service_type] = service_instance
        self._service_configs[service_type] = config or {}

        self.logger.info(
            "Registered service",
            service_type=service_type.__name__,
            implementation=service_instance.__class__.__name__,
        )

    def get_service(self, service_type: type[T]) -> T | None:
        """Get service instance by type.

        Args:
            service_type: Type of service to retrieve

        Returns:
            Service instance or None if not found
        """
        return self._services.get(service_type)

    def get_required_service(self, service_type: type[T]) -> T:
        """Get required service instance by type.

        Args:
            service_type: Type of service to retrieve

        Returns:
            Service instance

        Raises:
            ValueError: If service not found
        """
        service = self.get_service(service_type)
        if service is None:
            raise ValueError(f"Required service {service_type.__name__} not registered")
        return service

    def unregister_service(self, service_type: type) -> bool:
        """Unregister service.

        Args:
            service_type: Type of service to unregister

        Returns:
            True if service was registered and removed
        """
        if service_type in self._services:
            del self._services[service_type]
            self._service_configs.pop(service_type, None)

            self.logger.info("Unregistered service", service_type=service_type.__name__)
            return True

        return False

    def list_services(self) -> dict[str, str]:
        """List all registered services.

        Returns:
            Dictionary mapping service type names to implementation names
        """
        return {
            service_type.__name__: service_instance.__class__.__name__
            for service_type, service_instance in self._services.items()
        }

    async def initialize_all(self) -> bool:
        """Initialize all registered services.

        Returns:
            True if all services initialized successfully
        """
        self.logger.info("Initializing all registered services")

        success_count = 0
        total_count = len(self._services)

        for service_type, service_instance in self._services.items():
            if await self._initialize_service_safe(service_type, service_instance):
                success_count += 1

        success = success_count == total_count
        self.logger.info(
            "Service initialization complete",
            success=success,
            initialized=success_count,
            total=total_count,
        )

        return success

    async def shutdown_all(self) -> bool:
        """Shutdown all registered services.

        Returns:
            True if all services shut down successfully
        """
        self.logger.info("Shutting down all registered services")

        success_count = 0
        total_count = len(self._services)

        # Shutdown in reverse registration order
        for service_type, service_instance in reversed(list(self._services.items())):
            if await self._shutdown_service_safe(service_type, service_instance):
                success_count += 1

        success = success_count == total_count
        self.logger.info(
            "Service shutdown complete", success=success, shutdown=success_count, total=total_count
        )

        return success

    async def health_check_all(self) -> dict[str, dict[str, Any]]:
        """Perform health check on all services.

        Returns:
            Dictionary of health check results by service type
        """
        results = {}

        for service_type, service_instance in self._services.items():
            results[service_type.__name__] = await self._health_check_service_safe(
                service_type, service_instance
            )

        return results

    @content_processing_error_handler("initialize service")
    async def _initialize_service_safe(self, service_type: type, service_instance: Any) -> bool:
        """Initialize a single service with error handling."""
        if hasattr(service_instance, "initialize"):
            await service_instance.initialize()
            self.logger.debug(f"Initialized service: {service_type.__name__}")
        # Service doesn't need initialization
        return True

    @content_processing_error_handler("shutdown service")
    async def _shutdown_service_safe(self, service_type: type, service_instance: Any) -> bool:
        """Shutdown a single service with error handling."""
        if hasattr(service_instance, "shutdown"):
            await service_instance.shutdown()
            self.logger.debug(f"Shutdown service: {service_type.__name__}")
        # Service doesn't need shutdown
        return True

    @content_processing_error_handler("health check service")
    async def _health_check_service_safe(
        self, service_type: type, service_instance: Any
    ) -> dict[str, Any]:
        """Perform health check on a single service with error handling."""
        if hasattr(service_instance, "health_check"):
            result = await service_instance.health_check()
            return {"status": "healthy", "details": result}
        return {"status": "healthy", "details": {"message": "No health check available"}}


# Global service registry instance
service_registry = ServiceRegistry()
