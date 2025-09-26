"""Dependency injection container following modern Python DI patterns.

This module implements a lightweight dependency injection system that integrates
seamlessly with FastAPI while providing better testability and service lifecycle management.
"""

from __future__ import annotations

import threading
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any, TypeVar, cast, get_type_hints
from weakref import WeakKeyDictionary

from src.utils.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import Callable, Generator
    from types import TracebackType

T = TypeVar("T")

logger = get_logger(__name__)


class DIContainerError(Exception):
    """Dependency injection container error."""


class LifecycleManager:
    """Manages service lifecycle and cleanup."""

    def __init__(self) -> None:
        self._cleanup_handlers: dict[type, list[Callable[[Any], None]]] = {}
        self._instances: WeakKeyDictionary[Any, bool] = WeakKeyDictionary()

    def register_cleanup(self, service_type: type[T], cleanup_fn: Callable[[T], None]) -> None:
        """Register a cleanup function for a service type."""
        if service_type not in self._cleanup_handlers:
            self._cleanup_handlers[service_type] = []
        self._cleanup_handlers[service_type].append(cleanup_fn)

    def track_instance(self, instance: Any) -> None:
        """Track an instance for lifecycle management."""
        self._instances[instance] = True

    def cleanup_instance(self, instance: Any) -> None:
        """Clean up a specific instance."""
        instance_type = type(instance)
        cleanup_handlers = self._cleanup_handlers.get(instance_type, [])

        for handler in cleanup_handlers:
            try:
                handler(instance)
            except Exception as e:
                logger.warning(
                    "Cleanup handler failed", service_type=instance_type.__name__, error=str(e)
                )

    def cleanup_all(self) -> None:
        """Clean up all tracked instances."""
        instances = list(self._instances.keys())
        for instance in instances:
            self.cleanup_instance(instance)


class DependencyContainer:
    """Lightweight dependency injection container with FastAPI integration.

    Provides:
    - Service registration and resolution
    - Singleton and transient lifetimes
    - Automatic dependency injection
    - Lifecycle management
    - Thread-safe operations
    """

    def __init__(self) -> None:
        self._services: dict[type, dict[str, Any]] = {}
        self._singletons: dict[type, Any] = {}
        self._lock = threading.RLock()
        self._lifecycle = LifecycleManager()

    def register_singleton(
        self,
        interface: type[T],
        implementation: type[T] | None = None,
        factory: Callable[[], T] | None = None,
        instance: T | None = None,
    ) -> DependencyContainer:
        """Register a singleton service.

        Args:
            interface: The service interface/type
            implementation: The implementation class (if different from interface)
            factory: Factory function to create the service
            instance: Pre-created instance to use

        Returns:
            Self for method chaining
        """
        with self._lock:
            if instance is not None:
                self._singletons[interface] = instance
                self._lifecycle.track_instance(instance)
            else:
                self._services[interface] = {
                    "lifetime": "singleton",
                    "implementation": implementation or interface,
                    "factory": factory,
                }

        logger.debug(f"Registered singleton service: {interface.__name__}")
        return self

    def register_transient(
        self,
        interface: type[T],
        implementation: type[T] | None = None,
        factory: Callable[[], T] | None = None,
    ) -> DependencyContainer:
        """Register a transient service (new instance each time).

        Args:
            interface: The service interface/type
            implementation: The implementation class (if different from interface)
            factory: Factory function to create the service

        Returns:
            Self for method chaining
        """
        with self._lock:
            self._services[interface] = {
                "lifetime": "transient",
                "implementation": implementation or interface,
                "factory": factory,
            }

        logger.debug(f"Registered transient service: {interface.__name__}")
        return self

    def register_cleanup(
        self, service_type: type[T], cleanup_fn: Callable[[T], None]
    ) -> DependencyContainer:
        """Register a cleanup function for a service type.

        Args:
            service_type: The service type to register cleanup for
            cleanup_fn: Function to call when cleaning up instances

        Returns:
            Self for method chaining
        """
        self._lifecycle.register_cleanup(service_type, cleanup_fn)
        return self

    def resolve(self, service_type: type[T]) -> T:
        """Resolve a service instance.

        Args:
            service_type: The type of service to resolve

        Returns:
            Service instance

        Raises:
            DIContainerError: If service cannot be resolved
        """
        with self._lock:
            # Check for existing singleton
            if service_type in self._singletons:
                return cast("T", self._singletons[service_type])

            # Check for registered service
            if service_type not in self._services:
                # Try to auto-register if it's a concrete class
                if hasattr(service_type, "__init__"):
                    return self._auto_resolve(service_type)
                raise DIContainerError(f"Service {service_type.__name__} not registered")

            service_config = self._services[service_type]
            instance = self._create_instance(service_type, service_config)

            # Store singleton instances
            if service_config["lifetime"] == "singleton":
                self._singletons[service_type] = instance

            self._lifecycle.track_instance(instance)
            return instance

    def _create_instance(self, service_type: type[T], config: dict[str, Any]) -> T:
        """Create a service instance from configuration."""
        if config.get("factory"):
            factory = config["factory"]
            return cast("T", factory())

        implementation = config["implementation"]
        return cast("T", self._auto_resolve(implementation))

    def _auto_resolve(self, service_type: type[T]) -> T:
        """Automatically resolve dependencies for a service type."""
        try:
            # Get constructor signature
            type_hints = get_type_hints(service_type.__init__)

            # Resolve dependencies
            kwargs = {}
            for param_name, param_type in type_hints.items():
                if param_name == "return":
                    continue

                # Skip self parameter
                if param_name == "self":
                    continue

                # Recursively resolve dependencies
                try:
                    kwargs[param_name] = self.resolve(param_type)
                except DIContainerError:
                    # Skip optional dependencies
                    logger.debug(
                        f"Could not resolve dependency {param_name}: {param_type.__name__}"
                    )

            return service_type(**kwargs)

        except Exception as e:
            raise DIContainerError(f"Failed to create {service_type.__name__}: {str(e)}") from e

    def create_scope(self) -> ContainerScope:
        """Create a new container scope for request-scoped services."""
        return ContainerScope(self)

    @contextmanager
    def scope(self) -> Generator[ContainerScope]:
        """Context manager for container scope."""
        container_scope = self.create_scope()
        try:
            yield container_scope
        finally:
            container_scope.dispose()

    def dispose(self) -> None:
        """Dispose of the container and clean up resources."""
        with self._lock:
            self._lifecycle.cleanup_all()
            self._singletons.clear()
            self._services.clear()

        logger.debug("DependencyContainer disposed")


class ContainerScope:
    """Scoped container for request-level dependency management."""

    def __init__(self, parent: DependencyContainer):
        self._parent = parent
        self._scoped_instances: dict[type, Any] = {}
        self._lifecycle = LifecycleManager()

    def resolve(self, service_type: type[T]) -> T:
        """Resolve a service within this scope."""
        # Check for scoped instance first
        if service_type in self._scoped_instances:
            return cast("T", self._scoped_instances[service_type])

        # Resolve from parent container
        instance = self._parent.resolve(service_type)

        # Cache scoped instances
        self._scoped_instances[service_type] = instance
        self._lifecycle.track_instance(instance)

        return instance

    def dispose(self) -> None:
        """Dispose of the scope and clean up scoped instances."""
        self._lifecycle.cleanup_all()
        self._scoped_instances.clear()

    def __enter__(self) -> ContainerScope:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        self.dispose()


# Global container instance
container = DependencyContainer()


# FastAPI integration helpers
def Inject[T](service_type: type[T]) -> T:
    """FastAPI dependency that resolves from the container.

    Usage:
        @router.get("/users")
        async def get_users(user_service: UserService = Inject(UserService)):
            return await user_service.get_all()
    """
    return container.resolve(service_type)


def get_container() -> DependencyContainer:
    """Get the global container instance."""
    return container
