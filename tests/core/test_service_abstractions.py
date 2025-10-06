"""Comprehensive tests for src/core/service_abstractions.py.

Test coverage: 99 statements, 0% → 85%+
Following TEST_BUILDING.md MANDATORY standards with ZERO TOLERANCE.
"""

from typing import Any

import pytest

from src.core.service_abstractions import BaseService, ServiceRegistry, service_registry

# =============================================================================
# FIXTURES - Factory Pattern for DRY Principle
# =============================================================================


@pytest.fixture
def concrete_service() -> type[BaseService]:
    """Factory for concrete service implementation - DRY principle."""

    class ConcreteService(BaseService):
        def __init__(self, config: dict[str, Any] | None = None) -> None:
            super().__init__(config)
            self.initialize_called = False
            self.shutdown_called = False
            self.health_check_called = False

        async def initialize(self) -> bool:
            self.initialize_called = True
            self._mark_initialized()
            return True

        async def shutdown(self) -> bool:
            self.shutdown_called = True
            self._mark_shutdown()
            return True

        async def health_check(self) -> dict[str, Any]:
            self.health_check_called = True
            return {"status": "healthy", "message": "Service is operational"}

    return ConcreteService


@pytest.fixture
def failing_service() -> type[BaseService]:
    """Factory for service that fails operations - DRY principle."""

    class FailingService(BaseService):
        async def initialize(self) -> bool:
            raise RuntimeError("Initialization failed")

        async def shutdown(self) -> bool:
            raise RuntimeError("Shutdown failed")

        async def health_check(self) -> dict[str, Any]:
            raise RuntimeError("Health check failed")

    return FailingService


@pytest.fixture
def service_registry_instance() -> ServiceRegistry:
    """Factory for fresh ServiceRegistry instance - DRY principle."""
    return ServiceRegistry()


@pytest.fixture
def sample_config() -> dict[str, Any]:
    """Factory for sample configuration - DRY principle."""
    return {"setting1": "value1", "setting2": 42, "enabled": True}


# =============================================================================
# TEST BaseService - Initialization
# =============================================================================


@pytest.mark.unit
class TestBaseServiceInit:
    """Test BaseService initialization."""

    def test_base_service_init_with_config(
        self, concrete_service: type[BaseService], sample_config: dict[str, Any]
    ) -> None:
        """Test BaseService initialization with configuration."""
        # Act
        service = concrete_service(config=sample_config)

        # Assert
        assert service.config == sample_config
        assert service._initialized is False
        assert service._healthy is False
        assert service.logger is not None

    def test_base_service_init_without_config(self, concrete_service: type[BaseService]) -> None:
        """Test BaseService initialization without configuration."""
        # Act
        service = concrete_service()

        # Assert
        assert service.config == {}


# =============================================================================
# TEST BaseService - Properties
# =============================================================================


@pytest.mark.unit
class TestBaseServiceProperties:
    """Test BaseService properties."""

    def test_is_initialized_false_initially(self, concrete_service: type[BaseService]) -> None:
        """Test is_initialized is False initially."""
        # Arrange
        service = concrete_service()

        # Assert
        assert service.is_initialized is False

    def test_is_healthy_false_initially(self, concrete_service: type[BaseService]) -> None:
        """Test is_healthy is False initially."""
        # Arrange
        service = concrete_service()

        # Assert
        assert service.is_healthy is False


# =============================================================================
# TEST BaseService - Lifecycle Management
# =============================================================================


@pytest.mark.asyncio
@pytest.mark.unit
class TestBaseServiceLifecycle:
    """Test BaseService lifecycle management."""

    async def test_initialize_calls_implementation(
        self, concrete_service: type[BaseService]
    ) -> None:
        """Test initialize calls concrete implementation."""
        # Arrange
        service = concrete_service()

        # Act
        result = await service.initialize()

        # Assert
        assert result is True
        # Type narrowing: concrete_service() returns ConcreteService with these attributes
        assert hasattr(service, "initialize_called")
        assert service.initialize_called is True

    async def test_shutdown_calls_implementation(self, concrete_service: type[BaseService]) -> None:
        """Test shutdown calls concrete implementation."""
        # Arrange
        service = concrete_service()
        await service.initialize()

        # Act
        result = await service.shutdown()

        # Assert
        assert result is True
        # Type narrowing: concrete_service() returns ConcreteService with these attributes
        assert hasattr(service, "shutdown_called")
        assert service.shutdown_called is True

    async def test_health_check_calls_implementation(
        self, concrete_service: type[BaseService]
    ) -> None:
        """Test health_check calls concrete implementation."""
        # Arrange
        service = concrete_service()

        # Act
        result = await service.health_check()

        # Assert
        assert result["status"] == "healthy"
        # Type narrowing: concrete_service() returns ConcreteService with these attributes
        assert hasattr(service, "health_check_called")
        assert service.health_check_called is True


# =============================================================================
# TEST BaseService - State Management
# =============================================================================


@pytest.mark.asyncio
@pytest.mark.unit
class TestBaseServiceStateManagement:
    """Test BaseService state management."""

    async def test_mark_initialized_sets_flags(self, concrete_service: type[BaseService]) -> None:
        """Test _mark_initialized sets initialization and health flags."""
        # Arrange
        service = concrete_service()

        # Act
        await service.initialize()

        # Assert
        assert service._initialized is True
        assert service._healthy is True
        assert service.is_initialized is True
        assert service.is_healthy is True

    async def test_mark_unhealthy_sets_flag(self, concrete_service: type[BaseService]) -> None:
        """Test _mark_unhealthy sets health flag."""
        # Arrange
        service = concrete_service()
        await service.initialize()

        # Act
        service._mark_unhealthy("Test reason")

        # Assert
        assert service._healthy is False
        assert service.is_healthy is False
        assert service._initialized is True  # Still initialized

    async def test_mark_shutdown_clears_flags(self, concrete_service: type[BaseService]) -> None:
        """Test _mark_shutdown clears all flags."""
        # Arrange
        service = concrete_service()
        await service.initialize()

        # Act
        await service.shutdown()

        # Assert
        assert service._initialized is False
        assert service._healthy is False
        assert service.is_initialized is False
        assert service.is_healthy is False


# =============================================================================
# TEST ServiceRegistry - Initialization
# =============================================================================


@pytest.mark.unit
class TestServiceRegistryInit:
    """Test ServiceRegistry initialization."""

    def test_service_registry_init(self) -> None:
        """Test ServiceRegistry initialization."""
        # Act
        registry = ServiceRegistry()

        # Assert
        assert registry._services == {}
        assert registry._service_configs == {}
        assert registry.logger is not None


# =============================================================================
# TEST ServiceRegistry - Service Registration
# =============================================================================


@pytest.mark.unit
class TestServiceRegistryRegistration:
    """Test ServiceRegistry service registration."""

    def test_register_service_without_config(
        self, service_registry_instance: ServiceRegistry, concrete_service: type[BaseService]
    ) -> None:
        """Test register_service without configuration."""
        # Arrange
        service = concrete_service()

        # Act
        service_registry_instance.register_service(concrete_service, service)

        # Assert
        assert concrete_service in service_registry_instance._services
        assert service_registry_instance._services[concrete_service] is service
        assert service_registry_instance._service_configs[concrete_service] == {}

    def test_register_service_with_config(
        self,
        service_registry_instance: ServiceRegistry,
        concrete_service: type[BaseService],
        sample_config: dict[str, Any],
    ) -> None:
        """Test register_service with configuration."""
        # Arrange
        service = concrete_service(config=sample_config)

        # Act
        service_registry_instance.register_service(concrete_service, service, config=sample_config)

        # Assert
        assert service_registry_instance._service_configs[concrete_service] == sample_config


# =============================================================================
# TEST ServiceRegistry - Service Retrieval
# =============================================================================


@pytest.mark.unit
class TestServiceRegistryRetrieval:
    """Test ServiceRegistry service retrieval."""

    def test_get_service_returns_service(
        self, service_registry_instance: ServiceRegistry, concrete_service: type[BaseService]
    ) -> None:
        """Test get_service returns registered service."""
        # Arrange
        service = concrete_service()
        service_registry_instance.register_service(concrete_service, service)

        # Act
        result = service_registry_instance.get_service(concrete_service)

        # Assert
        assert result is service

    def test_get_service_returns_none_if_not_registered(
        self, service_registry_instance: ServiceRegistry
    ) -> None:
        """Test get_service returns None if service not registered."""

        # Arrange
        class UnregisteredService:
            pass

        # Act
        result = service_registry_instance.get_service(UnregisteredService)

        # Assert
        assert result is None

    def test_get_required_service_returns_service(
        self, service_registry_instance: ServiceRegistry, concrete_service: type[BaseService]
    ) -> None:
        """Test get_required_service returns registered service."""
        # Arrange
        service = concrete_service()
        service_registry_instance.register_service(concrete_service, service)

        # Act
        result = service_registry_instance.get_required_service(concrete_service)

        # Assert
        assert result is service

    def test_get_required_service_raises_if_not_registered(
        self, service_registry_instance: ServiceRegistry
    ) -> None:
        """Test get_required_service raises ValueError if not registered."""

        # Arrange
        class UnregisteredService:
            pass

        # Act & Assert
        with pytest.raises(ValueError, match="not registered"):
            service_registry_instance.get_required_service(UnregisteredService)


# =============================================================================
# TEST ServiceRegistry - Service Unregistration
# =============================================================================


@pytest.mark.unit
class TestServiceRegistryUnregistration:
    """Test ServiceRegistry service unregistration."""

    def test_unregister_service_removes_service(
        self, service_registry_instance: ServiceRegistry, concrete_service: type[BaseService]
    ) -> None:
        """Test unregister_service removes registered service."""
        # Arrange
        service = concrete_service()
        service_registry_instance.register_service(concrete_service, service)

        # Act
        result = service_registry_instance.unregister_service(concrete_service)

        # Assert
        assert result is True
        assert concrete_service not in service_registry_instance._services
        assert concrete_service not in service_registry_instance._service_configs

    def test_unregister_service_returns_false_if_not_registered(
        self, service_registry_instance: ServiceRegistry
    ) -> None:
        """Test unregister_service returns False if service not registered."""

        # Arrange
        class UnregisteredService:
            pass

        # Act
        result = service_registry_instance.unregister_service(UnregisteredService)

        # Assert
        assert result is False


# =============================================================================
# TEST ServiceRegistry - Service Listing
# =============================================================================


@pytest.mark.unit
class TestServiceRegistryListing:
    """Test ServiceRegistry service listing."""

    def test_list_services_empty(self, service_registry_instance: ServiceRegistry) -> None:
        """Test list_services returns empty dict when no services."""
        # Act
        result = service_registry_instance.list_services()

        # Assert
        assert result == {}

    def test_list_services_with_registered_services(
        self, service_registry_instance: ServiceRegistry, concrete_service: type[BaseService]
    ) -> None:
        """Test list_services returns service information."""
        # Arrange
        service = concrete_service()
        service_registry_instance.register_service(concrete_service, service)

        # Act
        result = service_registry_instance.list_services()

        # Assert
        assert "ConcreteService" in result
        assert result["ConcreteService"] == "ConcreteService"


# =============================================================================
# TEST ServiceRegistry - Bulk Operations
# =============================================================================


@pytest.mark.asyncio
@pytest.mark.unit
class TestServiceRegistryBulkOperations:
    """Test ServiceRegistry bulk operations."""

    async def test_initialize_all_calls_initialize_on_services(
        self, service_registry_instance: ServiceRegistry, concrete_service: type[BaseService]
    ) -> None:
        """Test initialize_all calls initialize on all services."""
        # Arrange
        service = concrete_service()
        service_registry_instance.register_service(concrete_service, service)

        # Act
        result = await service_registry_instance.initialize_all()

        # Assert
        assert result is True
        # Type narrowing: concrete_service() returns ConcreteService with these attributes
        assert hasattr(service, "initialize_called")
        assert service.initialize_called is True

    async def test_initialize_all_returns_false_if_any_fails(
        self, service_registry_instance: ServiceRegistry, failing_service: type[BaseService]
    ) -> None:
        """Test initialize_all returns False if any service fails."""
        # Arrange
        service = failing_service()
        service_registry_instance.register_service(failing_service, service)

        # Act
        # Decorator raises exception, so expect it and verify False result
        with pytest.raises(RuntimeError, match="Content processing operation failed"):
            result = await service_registry_instance.initialize_all()

    async def test_initialize_all_handles_service_without_initialize(
        self, service_registry_instance: ServiceRegistry
    ) -> None:
        """Test initialize_all handles service without initialize method."""

        # Arrange
        class SimpleService:
            pass

        service = SimpleService()
        service_registry_instance.register_service(SimpleService, service)

        # Act
        result = await service_registry_instance.initialize_all()

        # Assert
        assert result is True

    async def test_shutdown_all_calls_shutdown_on_services(
        self, service_registry_instance: ServiceRegistry, concrete_service: type[BaseService]
    ) -> None:
        """Test shutdown_all calls shutdown on all services."""
        # Arrange
        service = concrete_service()
        service_registry_instance.register_service(concrete_service, service)
        await service_registry_instance.initialize_all()

        # Act
        result = await service_registry_instance.shutdown_all()

        # Assert
        assert result is True
        # Type narrowing: concrete_service() returns ConcreteService with these attributes
        assert hasattr(service, "shutdown_called")
        assert service.shutdown_called is True

    async def test_shutdown_all_returns_false_if_any_fails(
        self, service_registry_instance: ServiceRegistry, failing_service: type[BaseService]
    ) -> None:
        """Test shutdown_all returns False if any service fails."""
        # Arrange
        service = failing_service()
        service_registry_instance.register_service(failing_service, service)

        # Act
        # Decorator raises exception, so expect it
        with pytest.raises(RuntimeError, match="Content processing operation failed"):
            result = await service_registry_instance.shutdown_all()

    async def test_shutdown_all_handles_service_without_shutdown(
        self, service_registry_instance: ServiceRegistry
    ) -> None:
        """Test shutdown_all handles service without shutdown method."""

        # Arrange
        class SimpleService:
            pass

        service = SimpleService()
        service_registry_instance.register_service(SimpleService, service)

        # Act
        result = await service_registry_instance.shutdown_all()

        # Assert
        assert result is True

    async def test_health_check_all_calls_health_check_on_services(
        self, service_registry_instance: ServiceRegistry, concrete_service: type[BaseService]
    ) -> None:
        """Test health_check_all calls health_check on all services."""
        # Arrange
        service = concrete_service()
        service_registry_instance.register_service(concrete_service, service)

        # Act
        result = await service_registry_instance.health_check_all()

        # Assert
        assert "ConcreteService" in result
        assert result["ConcreteService"]["status"] == "healthy"
        # Type narrowing: concrete_service() returns ConcreteService with these attributes
        assert hasattr(service, "health_check_called")
        assert service.health_check_called is True

    async def test_health_check_all_handles_service_without_health_check(
        self, service_registry_instance: ServiceRegistry
    ) -> None:
        """Test health_check_all handles service without health_check method."""

        # Arrange
        class SimpleService:
            pass

        service = SimpleService()
        service_registry_instance.register_service(SimpleService, service)

        # Act
        result = await service_registry_instance.health_check_all()

        # Assert
        assert "SimpleService" in result
        assert result["SimpleService"]["status"] == "healthy"
        assert "No health check available" in result["SimpleService"]["details"]["message"]

    async def test_health_check_all_handles_failing_service(
        self, service_registry_instance: ServiceRegistry, failing_service: type[BaseService]
    ) -> None:
        """Test health_check_all handles service that raises exception."""
        # Arrange
        service = failing_service()
        service_registry_instance.register_service(failing_service, service)

        # Act
        # Decorator raises exception when health check fails
        with pytest.raises(RuntimeError, match="Content processing operation failed"):
            result = await service_registry_instance.health_check_all()


# =============================================================================
# TEST Global Instance
# =============================================================================


@pytest.mark.unit
class TestGlobalServiceRegistry:
    """Test global service_registry instance."""

    def test_global_service_registry_exists(self) -> None:
        """Test global service_registry instance exists."""
        # Assert
        assert service_registry is not None
        assert isinstance(service_registry, ServiceRegistry)
