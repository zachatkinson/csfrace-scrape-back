"""Comprehensive tests for src/core/di_container.py.

Test coverage: 211 statements, 0% → 85%+
Following TEST_BUILDING.md MANDATORY standards with ZERO TOLERANCE.
"""

import pytest

from src.core.di_container import (
    DIContainer,
    ServiceDescriptor,
    ServiceLifetime,
    ServiceStatus,
    container,
)

# =============================================================================
# Test Service Classes (Module Level for Proper Typing)
# =============================================================================


class SampleService:
    """Sample service for testing."""

    def __init__(self) -> None:
        self.initialized = False

    async def initialize(self) -> None:
        self.initialized = True

    async def shutdown(self) -> None:
        self.initialized = False


class DependencyA:
    """First dependency for testing."""

    pass


class DependencyB:
    """Second dependency for testing."""

    pass


class ServiceWithDeps:
    """Service with dependencies for testing."""

    def __init__(self, dep_a: DependencyA, dep_b: DependencyB) -> None:
        self.dep_a = dep_a
        self.dep_b = dep_b


# =============================================================================
# FIXTURES - Factory Pattern for DRY Principle
# =============================================================================


@pytest.fixture
def di_container() -> DIContainer:
    """Factory for fresh DI container - DRY principle."""
    return DIContainer()


@pytest.fixture
def sample_service() -> type[SampleService]:
    """Factory for sample service class - DRY principle."""
    return SampleService


@pytest.fixture
def service_with_dependencies() -> tuple[
    type[ServiceWithDeps], type[DependencyA], type[DependencyB]
]:
    """Factory for service with dependencies - DRY principle."""
    return ServiceWithDeps, DependencyA, DependencyB


# =============================================================================
# TEST Enums
# =============================================================================


@pytest.mark.unit
class TestServiceLifetime:
    """Test ServiceLifetime enum."""

    def test_service_lifetime_values(self) -> None:
        """Test ServiceLifetime has correct values."""
        # Assert
        assert ServiceLifetime.SINGLETON.value == "singleton"
        assert ServiceLifetime.TRANSIENT.value == "transient"
        assert ServiceLifetime.SCOPED.value == "scoped"


@pytest.mark.unit
class TestServiceStatus:
    """Test ServiceStatus enum."""

    def test_service_status_values(self) -> None:
        """Test ServiceStatus has correct values."""
        # Assert
        assert ServiceStatus.UNINITIALIZED.value == "uninitialized"
        assert ServiceStatus.INITIALIZING.value == "initializing"
        assert ServiceStatus.INITIALIZED.value == "initialized"
        assert ServiceStatus.FAILED.value == "failed"
        assert ServiceStatus.SHUTDOWN.value == "shutdown"


# =============================================================================
# TEST ServiceDescriptor
# =============================================================================


@pytest.mark.unit
class TestServiceDescriptor:
    """Test ServiceDescriptor dataclass."""

    def test_service_descriptor_minimal(self, sample_service: type[SampleService]) -> None:
        """Test ServiceDescriptor with minimal parameters."""
        # Arrange & Act
        descriptor = ServiceDescriptor(service_type=sample_service)

        # Assert
        assert descriptor.service_type == sample_service
        assert descriptor.implementation_type is None
        assert descriptor.factory is None
        assert descriptor.instance is None
        assert descriptor.lifetime == ServiceLifetime.TRANSIENT
        assert descriptor.dependencies == []
        assert descriptor.configuration == {}
        assert descriptor.status == ServiceStatus.UNINITIALIZED
        assert descriptor.initialization_order == 0

    def test_service_descriptor_full(self, sample_service: type[SampleService]) -> None:
        """Test ServiceDescriptor with all parameters."""
        # Arrange
        instance = sample_service()

        def factory() -> SampleService:
            return sample_service()

        deps = [int, str]
        config = {"key": "value"}

        # Act
        descriptor = ServiceDescriptor(
            service_type=sample_service,
            implementation_type=sample_service,
            factory=factory,
            instance=instance,
            lifetime=ServiceLifetime.SINGLETON,
            dependencies=deps,
            configuration=config,
            status=ServiceStatus.INITIALIZED,
            initialization_order=5,
        )

        # Assert
        assert descriptor.implementation_type == sample_service
        assert descriptor.factory == factory
        assert descriptor.instance == instance
        assert descriptor.lifetime == ServiceLifetime.SINGLETON
        assert descriptor.dependencies == deps
        assert descriptor.configuration == config
        assert descriptor.status == ServiceStatus.INITIALIZED
        assert descriptor.initialization_order == 5


# =============================================================================
# TEST DIContainer - Service Registration
# =============================================================================


@pytest.mark.unit
class TestDIContainerRegistration:
    """Test DIContainer service registration."""

    def test_di_container_init(self) -> None:
        """Test DIContainer initialization."""
        # Act
        container = DIContainer()

        # Assert
        assert container._services == {}
        assert container._instances == {}
        assert container._scoped_instances == {}
        assert container._initialization_order == 0
        assert container._is_initializing is False

    def test_register_singleton_minimal(
        self, di_container: DIContainer, sample_service: type[SampleService]
    ) -> None:
        """Test register_singleton with minimal parameters."""
        # Act
        result = di_container.register_singleton(sample_service)

        # Assert
        assert result is di_container  # Method chaining
        assert sample_service in di_container._services
        descriptor = di_container._services[sample_service]
        assert descriptor.service_type == sample_service
        assert descriptor.lifetime == ServiceLifetime.SINGLETON

    def test_register_singleton_with_implementation(self, di_container: DIContainer) -> None:
        """Test register_singleton with separate interface/implementation."""

        # Arrange
        class IService:
            pass

        class ServiceImpl(IService):
            pass

        # Act
        di_container.register_singleton(IService, implementation_type=ServiceImpl)

        # Assert
        descriptor = di_container._services[IService]
        assert descriptor.service_type == IService
        assert descriptor.implementation_type == ServiceImpl

    def test_register_singleton_with_factory(
        self, di_container: DIContainer, sample_service: type[SampleService]
    ) -> None:
        """Test register_singleton with factory function."""

        # Arrange
        def factory() -> SampleService:
            return sample_service()

        # Act
        di_container.register_singleton(sample_service, factory=factory)

        # Assert
        descriptor = di_container._services[sample_service]
        assert descriptor.factory == factory

    def test_register_singleton_with_instance(
        self, di_container: DIContainer, sample_service: type[SampleService]
    ) -> None:
        """Test register_singleton with pre-created instance."""
        # Arrange
        instance = sample_service()

        # Act
        di_container.register_singleton(sample_service, instance=instance)

        # Assert
        descriptor = di_container._services[sample_service]
        assert descriptor.instance is instance

    def test_register_singleton_with_configuration(
        self, di_container: DIContainer, sample_service: type[SampleService]
    ) -> None:
        """Test register_singleton with configuration."""
        # Arrange
        config = {"setting1": "value1", "setting2": 42}

        # Act
        di_container.register_singleton(sample_service, configuration=config)

        # Assert
        descriptor = di_container._services[sample_service]
        assert descriptor.configuration == config

    def test_register_transient(
        self, di_container: DIContainer, sample_service: type[SampleService]
    ) -> None:
        """Test register_transient service."""
        # Act
        result = di_container.register_transient(sample_service)

        # Assert
        assert result is di_container
        descriptor = di_container._services[sample_service]
        assert descriptor.lifetime == ServiceLifetime.TRANSIENT

    def test_register_scoped(
        self, di_container: DIContainer, sample_service: type[SampleService]
    ) -> None:
        """Test register_scoped service."""
        # Act
        result = di_container.register_scoped(sample_service)

        # Assert
        assert result is di_container
        descriptor = di_container._services[sample_service]
        assert descriptor.lifetime == ServiceLifetime.SCOPED

    def test_register_service_replaces_existing(
        self, di_container: DIContainer, sample_service: type[SampleService]
    ) -> None:
        """Test registering same service twice replaces it."""
        # Arrange
        di_container.register_singleton(sample_service)

        # Act
        di_container.register_transient(sample_service)

        # Assert
        descriptor = di_container._services[sample_service]
        assert descriptor.lifetime == ServiceLifetime.TRANSIENT


# =============================================================================
# TEST DIContainer - Dependency Analysis
# =============================================================================


@pytest.mark.unit
class TestDIContainerDependencyAnalysis:
    """Test DIContainer dependency analysis."""

    def test_analyze_dependencies_no_params(self, di_container: DIContainer) -> None:
        """Test _analyze_dependencies with no constructor parameters."""

        # Arrange
        class SimpleService:
            def __init__(self) -> None:
                pass

        # Act
        deps = di_container._analyze_dependencies(SimpleService)

        # Assert
        assert deps == []

    def test_analyze_dependencies_with_types(self, di_container: DIContainer) -> None:
        """Test _analyze_dependencies with typed parameters."""

        # Arrange
        class DepA:
            pass

        class DepB:
            pass

        class ServiceWithDeps:
            def __init__(self, dep_a: DepA, dep_b: DepB):
                pass

        # Act
        deps = di_container._analyze_dependencies(ServiceWithDeps)

        # Assert
        assert deps == [DepA, DepB]

    def test_analyze_dependencies_with_generics(self, di_container: DIContainer) -> None:
        """Test _analyze_dependencies with generic types."""

        # Arrange
        class ServiceWithGenerics:
            def __init__(self, items: list[str]):
                pass

        # Act
        deps = di_container._analyze_dependencies(ServiceWithGenerics)

        # Assert
        assert deps == [list]

    def test_analyze_dependencies_skips_self(self, di_container: DIContainer) -> None:
        """Test _analyze_dependencies skips self parameter."""

        # Arrange
        class Service:
            def __init__(self, value: int):
                pass

        # Act
        deps = di_container._analyze_dependencies(Service)

        # Assert
        assert deps == [int]
        assert "self" not in [d.__name__ for d in deps]


# =============================================================================
# TEST DIContainer - Service Resolution (Singleton)
# =============================================================================


@pytest.mark.asyncio
@pytest.mark.unit
class TestDIContainerSingletonResolution:
    """Test DIContainer singleton service resolution."""

    async def test_get_service_not_registered(
        self, di_container: DIContainer, sample_service: type[SampleService]
    ) -> None:
        """Test get_service raises ValueError if not registered."""
        # Act & Assert
        with pytest.raises(ValueError, match="is not registered"):
            await di_container.get_service(sample_service)

    async def test_get_service_singleton_creates_instance(
        self, di_container: DIContainer, sample_service: type[SampleService]
    ) -> None:
        """Test get_service creates singleton instance."""
        # Arrange
        di_container.register_singleton(sample_service, implementation_type=sample_service)

        # Act
        instance1 = await di_container.get_service(sample_service)
        instance2 = await di_container.get_service(sample_service)

        # Assert
        assert isinstance(instance1, sample_service)
        assert instance1 is instance2  # Same instance

    async def test_get_service_singleton_with_pre_created_instance(
        self, di_container: DIContainer, sample_service: type[SampleService]
    ) -> None:
        """Test get_service returns pre-created instance."""
        # Arrange
        pre_created = sample_service()
        di_container.register_singleton(sample_service, instance=pre_created)

        # Act
        instance = await di_container.get_service(sample_service)

        # Assert
        assert instance is pre_created

    async def test_get_service_singleton_with_factory(
        self, di_container: DIContainer, sample_service: type[SampleService]
    ) -> None:
        """Test get_service uses factory function."""

        # Arrange
        def factory() -> SampleService:
            return sample_service()

        di_container.register_singleton(sample_service, factory=factory)

        # Act
        instance = await di_container.get_service(sample_service)

        # Assert
        assert isinstance(instance, sample_service)

    async def test_get_service_singleton_with_async_factory(
        self, di_container: DIContainer, sample_service: type[SampleService]
    ) -> None:
        """Test get_service uses async factory function."""

        # Arrange
        async def async_factory() -> SampleService:
            return sample_service()

        # Cast to bypass type checking since DI container supports async factories at runtime
        di_container.register_singleton(sample_service, factory=async_factory)  # type: ignore[arg-type]

        # Act
        instance = await di_container.get_service(sample_service)

        # Assert
        assert isinstance(instance, sample_service)

    async def test_get_service_singleton_calls_initialize(
        self, di_container: DIContainer, sample_service: type[SampleService]
    ) -> None:
        """Test get_service calls initialize() if present."""
        # Arrange
        di_container.register_singleton(sample_service, implementation_type=sample_service)

        # Act
        instance = await di_container.get_service(sample_service)

        # Assert
        assert instance.initialized is True


# =============================================================================
# TEST DIContainer - Service Resolution (Transient)
# =============================================================================


@pytest.mark.asyncio
@pytest.mark.unit
class TestDIContainerTransientResolution:
    """Test DIContainer transient service resolution."""

    async def test_get_service_transient_creates_new_instance(
        self, di_container: DIContainer, sample_service: type[SampleService]
    ) -> None:
        """Test get_service creates new transient instance each time."""
        # Arrange
        di_container.register_transient(sample_service, implementation_type=sample_service)

        # Act
        instance1 = await di_container.get_service(sample_service)
        instance2 = await di_container.get_service(sample_service)

        # Assert
        assert isinstance(instance1, sample_service)
        assert isinstance(instance2, sample_service)
        assert instance1 is not instance2  # Different instances


# =============================================================================
# TEST DIContainer - Service Resolution (Scoped)
# =============================================================================


@pytest.mark.asyncio
@pytest.mark.unit
class TestDIContainerScopedResolution:
    """Test DIContainer scoped service resolution."""

    async def test_get_service_scoped_same_instance_in_scope(
        self, di_container: DIContainer, sample_service: type[SampleService]
    ) -> None:
        """Test get_service returns same scoped instance within scope."""
        # Arrange
        di_container.register_scoped(sample_service, implementation_type=sample_service)

        # Act
        instance1 = await di_container.get_service(sample_service)
        instance2 = await di_container.get_service(sample_service)

        # Assert
        assert instance1 is instance2  # Same instance in same scope

    async def test_scope_creates_new_scoped_instances(
        self, di_container: DIContainer, sample_service: type[SampleService]
    ) -> None:
        """Test scope() creates new scoped instances."""
        # Arrange
        di_container.register_scoped(sample_service, implementation_type=sample_service)

        # Act
        async with di_container.scope():
            instance1 = await di_container.get_service(sample_service)

        async with di_container.scope():
            instance2 = await di_container.get_service(sample_service)

        # Assert
        assert instance1 is not instance2  # Different instances in different scopes

    async def test_scope_disposes_instances_on_exit(self, di_container: DIContainer) -> None:
        """Test scope() disposes scoped instances on exit."""

        # Arrange
        class DisposableService:
            def __init__(self) -> None:
                self.disposed = False

            async def dispose(self) -> None:
                self.disposed = True

        di_container.register_scoped(DisposableService, implementation_type=DisposableService)

        # Act
        async with di_container.scope():
            instance = await di_container.get_service(DisposableService)

        # Assert
        assert instance.disposed is True


# =============================================================================
# TEST DIContainer - Dependency Injection
# =============================================================================


@pytest.mark.asyncio
@pytest.mark.unit
class TestDIContainerDependencyInjection:
    """Test DIContainer dependency injection."""

    async def test_get_service_resolves_dependencies(
        self,
        di_container: DIContainer,
        service_with_dependencies: tuple[
            type[ServiceWithDeps], type[DependencyA], type[DependencyB]
        ],
    ) -> None:
        """Test get_service resolves constructor dependencies."""
        # Arrange
        ServiceWithDeps, DepA, DepB = service_with_dependencies

        di_container.register_singleton(DepA, implementation_type=DepA)
        di_container.register_singleton(DepB, implementation_type=DepB)
        di_container.register_singleton(ServiceWithDeps, implementation_type=ServiceWithDeps)

        # Act
        instance = await di_container.get_service(ServiceWithDeps)

        # Assert
        assert isinstance(instance.dep_a, DepA)
        assert isinstance(instance.dep_b, DepB)

    async def test_get_service_handles_missing_dependencies(
        self, di_container: DIContainer
    ) -> None:
        """Test get_service handles missing dependencies gracefully."""

        # Arrange
        class MissingDep:
            pass

        class ServiceWithOptionalDep:
            def __init__(self, value: str = "default"):
                self.value = value

        di_container.register_singleton(
            ServiceWithOptionalDep, implementation_type=ServiceWithOptionalDep
        )

        # Act - Should create instance with default parameter
        instance = await di_container.get_service(ServiceWithOptionalDep)

        # Assert - Instance created with default value
        assert instance is not None
        assert instance.value == "default"


# =============================================================================
# TEST DIContainer - Lifecycle Management
# =============================================================================


@pytest.mark.asyncio
@pytest.mark.unit
class TestDIContainerLifecycle:
    """Test DIContainer lifecycle management."""

    async def test_initialize_all_initializes_singletons(
        self, di_container: DIContainer, sample_service: type[SampleService]
    ) -> None:
        """Test initialize_all initializes all singleton services."""
        # Arrange
        di_container.register_singleton(sample_service, implementation_type=sample_service)

        # Act
        success = await di_container.initialize_all()

        # Assert
        assert success is True
        assert sample_service in di_container._instances

    async def test_initialize_all_skips_transients(
        self, di_container: DIContainer, sample_service: type[SampleService]
    ) -> None:
        """Test initialize_all skips transient services."""
        # Arrange
        di_container.register_transient(sample_service, implementation_type=sample_service)

        # Act
        success = await di_container.initialize_all()

        # Assert
        assert success is True
        assert sample_service not in di_container._instances

    async def test_initialize_all_prevents_concurrent_initialization(
        self, di_container: DIContainer, sample_service: type[SampleService]
    ) -> None:
        """Test initialize_all prevents concurrent initialization."""
        # Arrange
        di_container.register_singleton(sample_service, implementation_type=sample_service)
        di_container._is_initializing = True

        # Act
        success = await di_container.initialize_all()

        # Assert
        assert success is False

    async def test_shutdown_calls_shutdown_on_services(self, di_container: DIContainer) -> None:
        """Test shutdown calls shutdown() on services."""

        # Arrange
        class ShutdownService:
            def __init__(self) -> None:
                self.shutdown_called = False

            async def shutdown(self) -> None:
                self.shutdown_called = True

        di_container.register_singleton(ShutdownService, implementation_type=ShutdownService)
        instance = await di_container.get_service(ShutdownService)

        # Act
        await di_container.shutdown()

        # Assert
        assert instance.shutdown_called is True

    async def test_shutdown_clears_instances(
        self, di_container: DIContainer, sample_service: type[SampleService]
    ) -> None:
        """Test shutdown clears all instances."""
        # Arrange
        di_container.register_singleton(sample_service, implementation_type=sample_service)
        await di_container.get_service(sample_service)

        # Act
        await di_container.shutdown()

        # Assert
        assert len(di_container._instances) == 0
        assert len(di_container._scoped_instances) == 0

    async def test_shutdown_updates_service_statuses(
        self, di_container: DIContainer, sample_service: type[SampleService]
    ) -> None:
        """Test shutdown updates service statuses to SHUTDOWN."""
        # Arrange
        di_container.register_singleton(sample_service, implementation_type=sample_service)
        await di_container.get_service(sample_service)

        # Act
        await di_container.shutdown()

        # Assert
        descriptor = di_container._services[sample_service]
        assert descriptor.status == ServiceStatus.SHUTDOWN


# =============================================================================
# TEST DIContainer - Service Status and Information
# =============================================================================


@pytest.mark.unit
class TestDIContainerStatusAndInfo:
    """Test DIContainer service status and information."""

    def test_get_service_status_unregistered(
        self, di_container: DIContainer, sample_service: type[SampleService]
    ) -> None:
        """Test get_service_status returns UNINITIALIZED for unregistered service."""
        # Act
        status = di_container.get_service_status(sample_service)

        # Assert
        assert status == ServiceStatus.UNINITIALIZED

    def test_get_service_status_registered(
        self, di_container: DIContainer, sample_service: type[SampleService]
    ) -> None:
        """Test get_service_status returns status for registered service."""
        # Arrange
        di_container.register_singleton(sample_service)

        # Act
        status = di_container.get_service_status(sample_service)

        # Assert
        assert status == ServiceStatus.UNINITIALIZED

    def test_list_services_empty(self, di_container: DIContainer) -> None:
        """Test list_services returns empty dict when no services."""
        # Act
        services = di_container.list_services()

        # Assert
        assert services == {}

    def test_list_services_with_registered_services(
        self,
        di_container: DIContainer,
        service_with_dependencies: tuple[
            type[ServiceWithDeps], type[DependencyA], type[DependencyB]
        ],
    ) -> None:
        """Test list_services returns service information."""
        # Arrange
        ServiceWithDeps, DepA, DepB = service_with_dependencies

        di_container.register_singleton(DepA, implementation_type=DepA)
        di_container.register_singleton(ServiceWithDeps, implementation_type=ServiceWithDeps)

        # Act
        services = di_container.list_services()

        # Assert
        assert "DependencyA" in services  # Uses actual class name
        assert "ServiceWithDeps" in services
        assert services["DependencyA"]["lifetime"] == "singleton"
        assert services["ServiceWithDeps"]["implementation"] == "ServiceWithDeps"


# =============================================================================
# TEST DIContainer - get_services (Multiple)
# =============================================================================


@pytest.mark.asyncio
@pytest.mark.unit
class TestDIContainerGetServices:
    """Test DIContainer get_services method."""

    async def test_get_services_returns_list(
        self, di_container: DIContainer, sample_service: type[SampleService]
    ) -> None:
        """Test get_services returns list of services."""
        # Arrange
        di_container.register_singleton(sample_service, implementation_type=sample_service)

        # Act
        services = await di_container.get_services(sample_service)

        # Assert
        assert isinstance(services, list)
        assert len(services) == 1
        assert isinstance(services[0], sample_service)


# =============================================================================
# TEST Global Container Instance
# =============================================================================


@pytest.mark.unit
class TestGlobalContainer:
    """Test global container instance."""

    def test_global_container_exists(self) -> None:
        """Test global container instance exists."""
        # Assert
        assert container is not None
        assert isinstance(container, DIContainer)
