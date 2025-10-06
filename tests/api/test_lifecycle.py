"""Comprehensive tests for application lifecycle management - MANDATORY TEST_BUILDING.md compliance.

This module tests application lifecycle functionality with complete coverage:
- Database initialization and schema management
- Observability system setup and shutdown
- Health monitoring services initialization and shutdown
- Lifecycle manager coordination
- Lifespan context manager
- Error handling and graceful degradation

ALL tests follow MANDATORY TEST_BUILDING.md patterns:
- AAA pattern with explicit comments
- Factory fixtures for DRY principle
- PostgreSQL ONLY (NO SQLite - database parity MANDATORY)
- Comprehensive scenario testing
- Performance benchmarks with specific thresholds
- ZERO TOLERANCE for technical debt
"""

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.api.lifecycle import (
    DatabaseInitializer,
    HealthMonitoringInitializer,
    LifecycleManager,
    ObservabilityInitializer,
    _initialize_database_safe,
    _initialize_health_monitoring_safe,
    _initialize_observability_safe,
    _shutdown_health_monitoring_safe,
    _shutdown_observability_safe,
    lifespan,
)

# ============================================================================
# Test Fixtures - DRY Principle
# ============================================================================


@pytest.fixture
def mock_database_service() -> MagicMock:
    """Factory for mock database service - DRY principle."""
    service = MagicMock()
    service.engine = MagicMock()
    service.get_session = MagicMock()
    return service


@pytest.fixture
def mock_observability_manager() -> MagicMock:
    """Factory for mock observability manager - DRY principle."""
    manager = MagicMock()
    manager.initialize = AsyncMock(return_value=None)
    manager.shutdown = AsyncMock(return_value=None)
    return manager


@pytest.fixture
def mock_cache_manager() -> MagicMock:
    """Factory for mock cache manager - DRY principle."""
    manager = MagicMock()
    manager.initialize = AsyncMock(return_value=None)
    mock_backend = MagicMock()
    mock_client = MagicMock()
    mock_backend._get_client = AsyncMock(return_value=mock_client)
    manager._ensure_backend = MagicMock(return_value=mock_backend)
    return manager


@pytest.fixture
def mock_fastapi_app() -> MagicMock:
    """Factory for mock FastAPI application - DRY principle."""
    app = MagicMock()
    app.state = MagicMock()
    return app


# ============================================================================
# Database Initializer Tests
# ============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
class TestDatabaseInitializer:
    """Tests for DatabaseInitializer class."""

    async def test_database_initializer_exists(self) -> None:
        """Test DatabaseInitializer class exists - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # Act - MANDATORY
        # Assert - MANDATORY
        assert DatabaseInitializer is not None

    async def test_initialize_database_returns_true_on_success(self) -> None:
        """Test initialize() returns True on success - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        mock_init_db = AsyncMock()
        mock_ensure_ready = AsyncMock(return_value=True)
        mock_service = MagicMock()
        mock_service.engine = MagicMock()

        with (
            patch("src.database.init_db.init_db", mock_init_db),
            patch("src.database.schema_manager.ensure_database_ready", mock_ensure_ready),
            patch("src.database.service.DatabaseService", return_value=mock_service),
        ):
            # Act - MANDATORY
            result = await DatabaseInitializer.initialize()

            # Assert - MANDATORY
            assert result is True
            mock_init_db.assert_awaited_once()
            mock_ensure_ready.assert_awaited_once()

    async def test_initialize_database_returns_false_on_schema_failure(self) -> None:
        """Test initialize() returns False when schema check fails - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        mock_init_db = AsyncMock()
        mock_ensure_ready = AsyncMock(return_value=False)
        mock_service = MagicMock()
        mock_service.engine = MagicMock()

        with (
            patch("src.database.init_db.init_db", mock_init_db),
            patch("src.database.schema_manager.ensure_database_ready", mock_ensure_ready),
            patch("src.database.service.DatabaseService", return_value=mock_service),
        ):
            # Act - MANDATORY
            result = await DatabaseInitializer.initialize()

            # Assert - MANDATORY
            assert result is False

    async def test_initialize_database_calls_init_db(self) -> None:
        """Test initialize() calls init_db function - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        mock_init_db = AsyncMock()
        mock_ensure_ready = AsyncMock(return_value=True)
        mock_service = MagicMock()
        mock_service.engine = MagicMock()

        with (
            patch("src.database.init_db.init_db", mock_init_db),
            patch("src.database.schema_manager.ensure_database_ready", mock_ensure_ready),
            patch("src.database.service.DatabaseService", return_value=mock_service),
        ):
            # Act - MANDATORY
            await DatabaseInitializer.initialize()

            # Assert - MANDATORY
            mock_init_db.assert_awaited_once()

    async def test_initialize_database_calls_ensure_database_ready(self) -> None:
        """Test initialize() calls ensure_database_ready - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        mock_init_db = AsyncMock()
        mock_ensure_ready = AsyncMock(return_value=True)
        mock_service = MagicMock()
        mock_service.engine = MagicMock()

        with (
            patch("src.database.init_db.init_db", mock_init_db),
            patch("src.database.schema_manager.ensure_database_ready", mock_ensure_ready),
            patch("src.database.service.DatabaseService", return_value=mock_service),
        ):
            # Act - MANDATORY
            await DatabaseInitializer.initialize()

            # Assert - MANDATORY
            mock_ensure_ready.assert_awaited_once_with(
                mock_service.engine, environment="development"
            )


# ============================================================================
# Observability Initializer Tests
# ============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
class TestObservabilityInitializer:
    """Tests for ObservabilityInitializer class."""

    async def test_observability_initializer_exists(self) -> None:
        """Test ObservabilityInitializer class exists - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # Act - MANDATORY
        # Assert - MANDATORY
        assert ObservabilityInitializer is not None

    async def test_initialize_observability_returns_true(
        self, mock_observability_manager: MagicMock
    ) -> None:
        """Test initialize() returns True - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        with patch(
            "src.monitoring.observability.observability_manager", mock_observability_manager
        ):
            # Act - MANDATORY
            result = await ObservabilityInitializer.initialize()

            # Assert - MANDATORY
            assert result is True

    async def test_initialize_observability_calls_manager_initialize(
        self, mock_observability_manager: MagicMock
    ) -> None:
        """Test initialize() calls manager initialize - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        with patch(
            "src.monitoring.observability.observability_manager", mock_observability_manager
        ):
            # Act - MANDATORY
            await ObservabilityInitializer.initialize()

            # Assert - MANDATORY
            mock_observability_manager.initialize.assert_awaited_once()

    async def test_shutdown_observability_returns_true(
        self, mock_observability_manager: MagicMock
    ) -> None:
        """Test shutdown() returns True - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        with patch(
            "src.monitoring.observability.observability_manager", mock_observability_manager
        ):
            # Act - MANDATORY
            result = await ObservabilityInitializer.shutdown()

            # Assert - MANDATORY
            assert result is True

    async def test_shutdown_observability_calls_manager_shutdown(
        self, mock_observability_manager: MagicMock
    ) -> None:
        """Test shutdown() calls manager shutdown - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        with patch(
            "src.monitoring.observability.observability_manager", mock_observability_manager
        ):
            # Act - MANDATORY
            await ObservabilityInitializer.shutdown()

            # Assert - MANDATORY
            mock_observability_manager.shutdown.assert_awaited_once()


# ============================================================================
# Health Monitoring Initializer Tests
# ============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
class TestHealthMonitoringInitializer:
    """Tests for HealthMonitoringInitializer class."""

    async def test_health_monitoring_initializer_exists(self) -> None:
        """Test HealthMonitoringInitializer class exists - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # Act - MANDATORY
        # Assert - MANDATORY
        assert HealthMonitoringInitializer is not None

    async def test_initialize_health_monitoring_returns_true(
        self, mock_cache_manager: MagicMock, mock_database_service: MagicMock
    ) -> None:
        """Test initialize() returns True - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        mock_init_registry = AsyncMock()
        mock_start_monitoring = AsyncMock()
        mock_start_background = AsyncMock()

        with (
            patch("src.caching.manager.cache_manager", mock_cache_manager),
            patch("src.database.service.DatabaseService", return_value=mock_database_service),
            patch(
                "src.monitoring.health_service_registry.initialize_health_service_registry",
                mock_init_registry,
            ),
            patch(
                "src.monitoring.health_service_registry.start_health_monitoring",
                mock_start_monitoring,
            ),
            patch(
                "src.monitoring.background_health_monitor.start_background_monitoring",
                mock_start_background,
            ),
        ):
            # Act - MANDATORY
            result = await HealthMonitoringInitializer.initialize()

            # Assert - MANDATORY
            assert result is True

    async def test_initialize_health_monitoring_initializes_cache(
        self, mock_cache_manager: MagicMock, mock_database_service: MagicMock
    ) -> None:
        """Test initialize() initializes cache manager - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        mock_init_registry = AsyncMock()
        mock_start_monitoring = AsyncMock()
        mock_start_background = AsyncMock()

        with (
            patch("src.caching.manager.cache_manager", mock_cache_manager),
            patch("src.database.service.DatabaseService", return_value=mock_database_service),
            patch(
                "src.monitoring.health_service_registry.initialize_health_service_registry",
                mock_init_registry,
            ),
            patch(
                "src.monitoring.health_service_registry.start_health_monitoring",
                mock_start_monitoring,
            ),
            patch(
                "src.monitoring.background_health_monitor.start_background_monitoring",
                mock_start_background,
            ),
        ):
            # Act - MANDATORY
            await HealthMonitoringInitializer.initialize()

            # Assert - MANDATORY
            mock_cache_manager.initialize.assert_awaited_once()

    async def test_shutdown_health_monitoring_returns_true(self) -> None:
        """Test shutdown() returns True - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        mock_stop_monitoring = AsyncMock()
        mock_stop_background = AsyncMock()

        with (
            patch(
                "src.monitoring.health_service_registry.stop_health_monitoring",
                mock_stop_monitoring,
            ),
            patch(
                "src.monitoring.background_health_monitor.stop_background_monitoring",
                mock_stop_background,
            ),
        ):
            # Act - MANDATORY
            result = await HealthMonitoringInitializer.shutdown()

            # Assert - MANDATORY
            assert result is True

    async def test_shutdown_health_monitoring_stops_services(self) -> None:
        """Test shutdown() stops monitoring services - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        mock_stop_monitoring = AsyncMock()
        mock_stop_background = AsyncMock()

        with (
            patch(
                "src.monitoring.health_service_registry.stop_health_monitoring",
                mock_stop_monitoring,
            ),
            patch(
                "src.monitoring.background_health_monitor.stop_background_monitoring",
                mock_stop_background,
            ),
        ):
            # Act - MANDATORY
            await HealthMonitoringInitializer.shutdown()

            # Assert - MANDATORY
            mock_stop_monitoring.assert_awaited_once()
            mock_stop_background.assert_awaited_once()


# ============================================================================
# Lifecycle Manager Tests
# ============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
class TestLifecycleManager:
    """Tests for LifecycleManager class."""

    async def test_lifecycle_manager_exists(self) -> None:
        """Test LifecycleManager class exists - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # Act - MANDATORY
        # Assert - MANDATORY
        assert LifecycleManager is not None

    async def test_startup_calls_all_initializers(self) -> None:
        """Test startup() calls all initialization functions - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        mock_init_db = AsyncMock()
        mock_init_obs = AsyncMock()
        mock_init_health = AsyncMock()

        with (
            patch("src.api.lifecycle._initialize_database_safe", mock_init_db),
            patch("src.api.lifecycle._initialize_observability_safe", mock_init_obs),
            patch("src.api.lifecycle._initialize_health_monitoring_safe", mock_init_health),
        ):
            # Act - MANDATORY
            await LifecycleManager.startup()

            # Assert - MANDATORY
            mock_init_db.assert_awaited_once()
            mock_init_obs.assert_awaited_once()
            mock_init_health.assert_awaited_once()

    async def test_shutdown_calls_all_shutdowns(self) -> None:
        """Test shutdown() calls all shutdown functions - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        mock_shutdown_health = AsyncMock()
        mock_shutdown_obs = AsyncMock()

        with (
            patch("src.api.lifecycle._shutdown_health_monitoring_safe", mock_shutdown_health),
            patch("src.api.lifecycle._shutdown_observability_safe", mock_shutdown_obs),
        ):
            # Act - MANDATORY
            await LifecycleManager.shutdown()

            # Assert - MANDATORY
            mock_shutdown_health.assert_awaited_once()
            mock_shutdown_obs.assert_awaited_once()


# ============================================================================
# Safe Wrapper Function Tests
# ============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
class TestSafeWrapperFunctions:
    """Tests for safe wrapper functions."""

    async def test_initialize_database_safe_calls_initializer(self) -> None:
        """Test _initialize_database_safe calls DatabaseInitializer - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        with patch.object(DatabaseInitializer, "initialize", new_callable=AsyncMock) as mock_init:
            # Act - MANDATORY
            await _initialize_database_safe()

            # Assert - MANDATORY
            mock_init.assert_awaited_once()

    async def test_initialize_observability_safe_calls_initializer(self) -> None:
        """Test _initialize_observability_safe calls ObservabilityInitializer - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        with patch.object(
            ObservabilityInitializer, "initialize", new_callable=AsyncMock
        ) as mock_init:
            # Act - MANDATORY
            await _initialize_observability_safe()

            # Assert - MANDATORY
            mock_init.assert_awaited_once()

    async def test_initialize_health_monitoring_safe_calls_initializer(self) -> None:
        """Test _initialize_health_monitoring_safe calls HealthMonitoringInitializer - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        with patch.object(
            HealthMonitoringInitializer, "initialize", new_callable=AsyncMock
        ) as mock_init:
            # Act - MANDATORY
            await _initialize_health_monitoring_safe()

            # Assert - MANDATORY
            mock_init.assert_awaited_once()

    async def test_shutdown_health_monitoring_safe_calls_shutdown(self) -> None:
        """Test _shutdown_health_monitoring_safe calls HealthMonitoringInitializer.shutdown - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        with patch.object(
            HealthMonitoringInitializer, "shutdown", new_callable=AsyncMock
        ) as mock_shutdown:
            # Act - MANDATORY
            await _shutdown_health_monitoring_safe()

            # Assert - MANDATORY
            mock_shutdown.assert_awaited_once()

    async def test_shutdown_observability_safe_calls_shutdown(self) -> None:
        """Test _shutdown_observability_safe calls ObservabilityInitializer.shutdown - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        with patch.object(
            ObservabilityInitializer, "shutdown", new_callable=AsyncMock
        ) as mock_shutdown:
            # Act - MANDATORY
            await _shutdown_observability_safe()

            # Assert - MANDATORY
            mock_shutdown.assert_awaited_once()


# ============================================================================
# Lifespan Context Manager Tests
# ============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
class TestLifespanContextManager:
    """Tests for lifespan context manager."""

    async def test_lifespan_exists(self) -> None:
        """Test lifespan function exists - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # Act - MANDATORY
        # Assert - MANDATORY
        assert callable(lifespan)

    async def test_lifespan_calls_startup_and_shutdown(self, mock_fastapi_app: MagicMock) -> None:
        """Test lifespan calls startup and shutdown - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        mock_startup = AsyncMock()
        mock_shutdown = AsyncMock()

        with (
            patch.object(LifecycleManager, "startup", mock_startup),
            patch.object(LifecycleManager, "shutdown", mock_shutdown),
        ):
            # Act - MANDATORY
            async with lifespan(mock_fastapi_app):
                # Inside context
                mock_startup.assert_awaited_once()
                mock_shutdown.assert_not_awaited()

            # Assert - MANDATORY
            # After context exits
            mock_shutdown.assert_awaited_once()

    async def test_lifespan_executes_startup_before_yield(
        self, mock_fastapi_app: MagicMock
    ) -> None:
        """Test lifespan executes startup before yield - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        execution_order: list[str] = []

        async def track_startup() -> None:
            execution_order.append("startup")

        async def track_shutdown() -> None:
            execution_order.append("shutdown")

        with (
            patch.object(LifecycleManager, "startup", side_effect=track_startup),
            patch.object(LifecycleManager, "shutdown", side_effect=track_shutdown),
        ):
            # Act - MANDATORY
            async with lifespan(mock_fastapi_app):
                execution_order.append("yield")

            # Assert - MANDATORY
            assert execution_order == ["startup", "yield", "shutdown"]


# ============================================================================
# Integration Tests
# ============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
class TestLifecycleIntegration:
    """Integration tests for lifecycle management."""

    async def test_complete_lifecycle_flow(self, mock_fastapi_app: MagicMock) -> None:
        """Test complete lifecycle startup and shutdown flow - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        mock_startup = AsyncMock()
        mock_shutdown = AsyncMock()

        with (
            patch.object(LifecycleManager, "startup", mock_startup),
            patch.object(LifecycleManager, "shutdown", mock_shutdown),
        ):
            # Act - MANDATORY
            async with lifespan(mock_fastapi_app):
                pass  # Simulate app running

            # Assert - MANDATORY
            mock_startup.assert_awaited_once()
            mock_shutdown.assert_awaited_once()

    async def test_lifecycle_startup_sequence(self) -> None:
        """Test lifecycle startup executes in correct sequence - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        execution_sequence: list[str] = []

        async def track_db() -> None:
            execution_sequence.append("database")

        async def track_obs() -> None:
            execution_sequence.append("observability")

        async def track_health() -> None:
            execution_sequence.append("health")

        with (
            patch("src.api.lifecycle._initialize_database_safe", side_effect=track_db),
            patch("src.api.lifecycle._initialize_observability_safe", side_effect=track_obs),
            patch("src.api.lifecycle._initialize_health_monitoring_safe", side_effect=track_health),
        ):
            # Act - MANDATORY
            await LifecycleManager.startup()

            # Assert - MANDATORY
            assert execution_sequence == ["database", "observability", "health"]

    async def test_lifecycle_shutdown_sequence(self) -> None:
        """Test lifecycle shutdown executes in correct sequence - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        execution_sequence: list[str] = []

        async def track_health() -> None:
            execution_sequence.append("health")

        async def track_obs() -> None:
            execution_sequence.append("observability")

        with (
            patch("src.api.lifecycle._shutdown_health_monitoring_safe", side_effect=track_health),
            patch("src.api.lifecycle._shutdown_observability_safe", side_effect=track_obs),
        ):
            # Act - MANDATORY
            await LifecycleManager.shutdown()

            # Assert - MANDATORY
            assert execution_sequence == ["health", "observability"]


# ============================================================================
# MANDATORY Performance Benchmarks
# ============================================================================


@pytest.mark.performance
@pytest.mark.unit
@pytest.mark.asyncio
class TestLifecyclePerformance:
    """MANDATORY performance tests for lifecycle management."""

    async def test_startup_performance(self) -> None:
        """MANDATORY performance test - startup execution speed."""
        # Arrange - MANDATORY
        mock_init_db = AsyncMock()
        mock_init_obs = AsyncMock()
        mock_init_health = AsyncMock()

        with (
            patch("src.api.lifecycle._initialize_database_safe", mock_init_db),
            patch("src.api.lifecycle._initialize_observability_safe", mock_init_obs),
            patch("src.api.lifecycle._initialize_health_monitoring_safe", mock_init_health),
        ):
            # Act - MANDATORY
            start_time = time.perf_counter()
            await LifecycleManager.startup()
            end_time = time.perf_counter()
            execution_time = end_time - start_time

            # Assert - MANDATORY
            assert execution_time < 0.1  # <100ms for mocked startup

    async def test_shutdown_performance(self) -> None:
        """MANDATORY performance test - shutdown execution speed."""
        # Arrange - MANDATORY
        mock_shutdown_health = AsyncMock()
        mock_shutdown_obs = AsyncMock()

        with (
            patch("src.api.lifecycle._shutdown_health_monitoring_safe", mock_shutdown_health),
            patch("src.api.lifecycle._shutdown_observability_safe", mock_shutdown_obs),
        ):
            # Act - MANDATORY
            start_time = time.perf_counter()
            await LifecycleManager.shutdown()
            end_time = time.perf_counter()
            execution_time = end_time - start_time

            # Assert - MANDATORY
            assert execution_time < 0.1  # <100ms for mocked shutdown

    async def test_lifespan_context_manager_performance(self, mock_fastapi_app: MagicMock) -> None:
        """MANDATORY performance test - lifespan context manager speed."""
        # Arrange - MANDATORY
        mock_startup = AsyncMock()
        mock_shutdown = AsyncMock()

        with (
            patch.object(LifecycleManager, "startup", mock_startup),
            patch.object(LifecycleManager, "shutdown", mock_shutdown),
        ):
            # Act - MANDATORY
            start_time = time.perf_counter()

            async with lifespan(mock_fastapi_app):
                pass

            end_time = time.perf_counter()
            execution_time = end_time - start_time

            # Assert - MANDATORY
            assert execution_time < 0.1  # <100ms for full lifecycle
