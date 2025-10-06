"""Dependency Injection Container following Dependency Inversion Principle.

This module provides a comprehensive DI container system that manages service
dependencies, lifecycle, and configuration following SOLID principles.
"""

from __future__ import annotations

import inspect
from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any, TypeVar, cast, get_origin

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable

from src.core.decorators import api_error_handler
from src.core.logging_hierarchy import get_general_logger

logger = get_general_logger(__name__)

T = TypeVar("T")


class ServiceLifetime(Enum):
    """Service lifetime management strategies."""

    SINGLETON = "singleton"
    TRANSIENT = "transient"
    SCOPED = "scoped"


class ServiceStatus(Enum):
    """Service status levels."""

    UNINITIALIZED = "uninitialized"
    INITIALIZING = "initializing"
    INITIALIZED = "initialized"
    FAILED = "failed"
    SHUTDOWN = "shutdown"


@dataclass
class ServiceDescriptor:
    """Describes how a service should be created and managed."""

    service_type: type
    implementation_type: type | None = None
    factory: Callable[..., Any] | None = None
    instance: Any = None
    lifetime: ServiceLifetime = ServiceLifetime.TRANSIENT
    dependencies: list[type] = field(default_factory=list)
    configuration: dict[str, Any] = field(default_factory=dict)
    status: ServiceStatus = ServiceStatus.UNINITIALIZED
    initialization_order: int = 0


class ServiceProvider(ABC):
    """Abstract base for service providers."""

    @abstractmethod
    async def get_service(self, service_type: type[T]) -> T:
        """Get service instance of specified type."""
        pass

    @abstractmethod
    async def get_services(self, service_type: type[T]) -> list[T]:
        """Get all service instances of specified type."""
        pass


class DIContainer(ServiceProvider):
    """Dependency Injection Container with lifecycle management.

    Provides comprehensive dependency injection following SOLID principles:
    - Single Responsibility: Each service has one clear responsibility
    - Open/Closed: Easy to extend with new services without modification
    - Liskov Substitution: Services can be substituted with compatible implementations
    - Interface Segregation: Services depend only on interfaces they need
    - Dependency Inversion: High-level modules depend on abstractions
    """

    def __init__(self) -> None:
        """Initialize dependency injection container."""
        self._services: dict[type, ServiceDescriptor] = {}
        self._instances: dict[type, Any] = {}
        self._scoped_instances: dict[type, Any] = {}
        self._initialization_order: int = 0
        self._is_initializing = False
        logger.info("DI Container initialized")

    def register_singleton(
        self,
        service_type: type[T],
        implementation_type: type[T] | None = None,
        factory: Callable[..., T] | None = None,
        instance: T | None = None,
        configuration: dict[str, Any] | None = None,
    ) -> DIContainer:
        """Register a singleton service.

        Args:
            service_type: Service interface/abstract type
            implementation_type: Concrete implementation type
            factory: Factory function to create service
            instance: Pre-created instance
            configuration: Service configuration

        Returns:
            Self for method chaining
        """
        return self._register_service(
            service_type,
            implementation_type,
            factory,
            instance,
            ServiceLifetime.SINGLETON,
            configuration or {},
        )

    def register_transient(
        self,
        service_type: type[T],
        implementation_type: type[T] | None = None,
        factory: Callable[..., T] | None = None,
        configuration: dict[str, Any] | None = None,
    ) -> DIContainer:
        """Register a transient service (new instance each time).

        Args:
            service_type: Service interface/abstract type
            implementation_type: Concrete implementation type
            factory: Factory function to create service
            configuration: Service configuration

        Returns:
            Self for method chaining
        """
        return self._register_service(
            service_type,
            implementation_type,
            factory,
            None,
            ServiceLifetime.TRANSIENT,
            configuration or {},
        )

    def register_scoped(
        self,
        service_type: type[T],
        implementation_type: type[T] | None = None,
        factory: Callable[..., T] | None = None,
        configuration: dict[str, Any] | None = None,
    ) -> DIContainer:
        """Register a scoped service (one instance per scope).

        Args:
            service_type: Service interface/abstract type
            implementation_type: Concrete implementation type
            factory: Factory function to create service
            configuration: Service configuration

        Returns:
            Self for method chaining
        """
        return self._register_service(
            service_type,
            implementation_type,
            factory,
            None,
            ServiceLifetime.SCOPED,
            configuration or {},
        )

    def _register_service(
        self,
        service_type: type,
        implementation_type: type | None,
        factory: Callable[..., Any] | None,
        instance: Any,
        lifetime: ServiceLifetime,
        configuration: dict[str, Any],
    ) -> DIContainer:
        """Internal method to register a service."""
        if service_type in self._services:
            logger.warning(f"Service {service_type.__name__} already registered, replacing")

        # Determine implementation type
        impl_type = implementation_type or service_type

        # Analyze dependencies from constructor
        dependencies = self._analyze_dependencies(impl_type)

        descriptor = ServiceDescriptor(
            service_type=service_type,
            implementation_type=impl_type,
            factory=factory,
            instance=instance,
            lifetime=lifetime,
            dependencies=dependencies,
            configuration=configuration,
            initialization_order=self._initialization_order,
        )

        self._services[service_type] = descriptor
        self._initialization_order += 1

        logger.debug(
            f"Registered {lifetime.value} service",
            service_type=service_type.__name__,
            implementation_type=impl_type.__name__ if impl_type else None,
            dependencies=[dep.__name__ for dep in dependencies],
        )

        return self

    def _analyze_dependencies(self, service_type: type) -> list[type]:
        """Analyze constructor dependencies using type hints."""
        try:
            signature = inspect.signature(service_type)
            dependencies = []

            for param_name, param in signature.parameters.items():
                if param_name == "self":
                    continue

                if param.annotation != inspect.Parameter.empty:
                    # Handle generic types and type hints
                    annotation = param.annotation
                    origin = get_origin(annotation)

                    if origin is None:
                        # Simple type
                        dependencies.append(annotation)
                    else:
                        # Generic type - use the origin
                        dependencies.append(origin)

            return dependencies
        except Exception as e:
            logger.warning(f"Failed to analyze dependencies for {service_type.__name__}: {e}")
            return []

    async def get_service(self, service_type: type[T]) -> T:
        """Get service instance of specified type.

        Args:
            service_type: Type of service to retrieve

        Returns:
            Service instance

        Raises:
            ValueError: If service is not registered
            RuntimeError: If circular dependency detected
        """
        if service_type not in self._services:
            raise ValueError(f"Service {service_type.__name__} is not registered")

        descriptor = self._services[service_type]

        # Handle different lifetime strategies
        if descriptor.lifetime == ServiceLifetime.SINGLETON:
            return await self._get_singleton(service_type, descriptor)
        elif descriptor.lifetime == ServiceLifetime.SCOPED:
            return await self._get_scoped(service_type, descriptor)
        else:  # TRANSIENT
            return await self._create_instance(service_type, descriptor)

    @api_error_handler("get service instance")
    async def _get_service_safe(self, service_type: type[T]) -> T:
        """Get service instance with error handling."""
        return await self.get_service(service_type)

    async def get_services(self, service_type: type[T]) -> list[T]:
        """Get all service instances of specified type.

        Args:
            service_type: Type of services to retrieve

        Returns:
            List of service instances
        """
        # For simplicity, return single service in list
        # Could be extended to support multiple implementations
        service = await self._get_service_safe(service_type)
        return [service] if service else []

    async def _get_singleton(self, service_type: type[T], descriptor: ServiceDescriptor) -> T:
        """Get or create singleton instance."""
        if service_type in self._instances:
            return cast("T", self._instances[service_type])

        # Create new singleton instance
        instance = await self._create_instance(service_type, descriptor)
        self._instances[service_type] = instance

        logger.debug(f"Created singleton instance of {service_type.__name__}")
        return instance

    async def _get_scoped(self, service_type: type[T], descriptor: ServiceDescriptor) -> T:
        """Get or create scoped instance."""
        if service_type in self._scoped_instances:
            return cast("T", self._scoped_instances[service_type])

        # Create new scoped instance
        instance = await self._create_instance(service_type, descriptor)
        self._scoped_instances[service_type] = instance

        logger.debug(f"Created scoped instance of {service_type.__name__}")
        return instance

    @api_error_handler("create service instance")
    async def _create_instance(self, service_type: type[T], descriptor: ServiceDescriptor) -> T:
        """Create new service instance with dependency injection."""
        descriptor.status = ServiceStatus.INITIALIZING

        # Use pre-created instance if available
        if descriptor.instance is not None:
            descriptor.status = ServiceStatus.INITIALIZED
            return cast("T", descriptor.instance)

        # Use factory if available
        if descriptor.factory is not None:
            instance = await self._invoke_factory(descriptor.factory, descriptor.dependencies)
            descriptor.status = ServiceStatus.INITIALIZED
            return cast("T", instance)

        # Create instance using constructor with dependency injection
        if descriptor.implementation_type is None:
            raise ValueError(f"No implementation type for {service_type.__name__}")

        # Resolve dependencies
        resolved_dependencies = []
        for dep_type in descriptor.dependencies:
            if dep_type in self._services:
                dep_instance: Any = await self.get_service(dep_type)
                resolved_dependencies.append(dep_instance)
            else:
                logger.warning(
                    f"Dependency {dep_type.__name__} not registered for {service_type.__name__}"
                )

        # Create instance
        if resolved_dependencies:
            instance = descriptor.implementation_type(*resolved_dependencies)
        else:
            instance = descriptor.implementation_type()

        # Apply configuration if available
        if descriptor.configuration and hasattr(instance, "configure"):
            await instance.configure(descriptor.configuration)

        # Initialize if async initializer available
        if hasattr(instance, "initialize"):
            await instance.initialize()

        descriptor.status = ServiceStatus.INITIALIZED
        logger.debug(f"Created instance of {service_type.__name__}")

        return cast("T", instance)

    async def _invoke_factory(self, factory: Callable[..., Any], dependencies: list[type]) -> Any:
        """Invoke factory function with dependency injection."""
        # Resolve dependencies for factory
        resolved_dependencies = []
        for dep_type in dependencies:
            if dep_type in self._services:
                dep_instance: Any = await self.get_service(dep_type)
                resolved_dependencies.append(dep_instance)

        # Invoke factory
        if inspect.iscoroutinefunction(factory):
            return await factory(*resolved_dependencies)
        else:
            return factory(*resolved_dependencies)

    @asynccontextmanager
    async def scope(self) -> AsyncIterator[DIContainer]:
        """Create a new scope for scoped services.

        Within this scope, scoped services will return the same instance.
        When the scope exits, scoped instances are disposed.
        """
        logger.debug("Creating DI scope")
        old_scoped = self._scoped_instances.copy()
        self._scoped_instances.clear()

        try:
            yield self
        finally:
            # Dispose scoped instances
            for instance in self._scoped_instances.values():
                if hasattr(instance, "dispose"):
                    await self._dispose_instance_safe(instance)

            self._scoped_instances = old_scoped
            logger.debug("DI scope closed")

    async def initialize_all(self) -> bool:
        """Initialize all registered singleton services.

        Returns:
            True if all services initialized successfully
        """
        if self._is_initializing:
            logger.warning("Container is already initializing")
            return False

        self._is_initializing = True
        logger.info("Initializing all DI container services")

        try:
            # Sort services by initialization order
            sorted_services = sorted(
                self._services.items(), key=lambda x: x[1].initialization_order
            )

            success_count = 0
            total_count = len(
                [s for s in sorted_services if s[1].lifetime == ServiceLifetime.SINGLETON]
            )

            for service_type, descriptor in sorted_services:
                if descriptor.lifetime == ServiceLifetime.SINGLETON:
                    result = await self._initialize_service_safe(service_type)
                    if result:
                        success_count += 1
                        logger.debug(f"Initialized singleton service: {service_type.__name__}")

            success = success_count == total_count
            logger.info(
                "DI container initialization complete",
                success=success,
                initialized=success_count,
                total=total_count,
            )

            return success

        finally:
            self._is_initializing = False

    async def shutdown(self) -> bool:
        """Shutdown all services and clean up resources.

        Returns:
            True if shutdown successful
        """
        logger.info("Shutting down DI container")
        return await self._shutdown_container_safe()

    @api_error_handler("shutdown DI container")
    async def _shutdown_container_safe(self) -> bool:
        """Shutdown container with error handling."""
        # Shutdown singletons in reverse order
        for instance in reversed(list(self._instances.values())):
            if hasattr(instance, "shutdown"):
                await self._shutdown_instance_safe(instance)

        # Shutdown scoped instances
        for instance in self._scoped_instances.values():
            if hasattr(instance, "shutdown"):
                await self._shutdown_instance_safe(instance)

        # Clear all instances
        self._instances.clear()
        self._scoped_instances.clear()

        # Update service statuses
        for descriptor in self._services.values():
            descriptor.status = ServiceStatus.SHUTDOWN

        logger.info("DI container shutdown completed")
        return True

    def get_service_status(self, service_type: type) -> ServiceStatus:
        """Get status of a registered service.

        Args:
            service_type: Type of service to check

        Returns:
            Service status
        """
        if service_type not in self._services:
            return ServiceStatus.UNINITIALIZED

        return self._services[service_type].status

    def list_services(self) -> dict[str, dict[str, Any]]:
        """List all registered services with their details.

        Returns:
            Dictionary of service information
        """
        services = {}
        for service_type, descriptor in self._services.items():
            services[service_type.__name__] = {
                "implementation": descriptor.implementation_type.__name__
                if descriptor.implementation_type
                else None,
                "lifetime": descriptor.lifetime.value,
                "status": descriptor.status.value,
                "dependencies": [dep.__name__ for dep in descriptor.dependencies],
                "has_instance": service_type in self._instances
                or service_type in self._scoped_instances,
            }

        return services

    @api_error_handler("dispose service instance")
    async def _dispose_instance_safe(self, instance: Any) -> None:
        """Dispose service instance with error handling."""
        await instance.dispose()

    @api_error_handler("shutdown service instance")
    async def _shutdown_instance_safe(self, instance: Any) -> None:
        """Shutdown service instance with error handling."""
        await instance.shutdown()

    @api_error_handler("initialize service")
    async def _initialize_service_safe(self, service_type: type) -> bool:
        """Initialize service with error handling."""
        await self.get_service(service_type)
        return True


# Global DI container instance
container = DIContainer()
