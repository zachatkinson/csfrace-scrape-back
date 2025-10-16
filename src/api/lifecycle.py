"""FastAPI application lifecycle management following Single Responsibility Principle.

This module handles application startup and shutdown logic including:
- Database initialization and schema management
- Observability system setup
- Health monitoring services
- Service cleanup and shutdown
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from src.core.decorators import api_error_handler
from src.core.logging_hierarchy import get_api_logger

if TYPE_CHECKING:
    from fastapi import FastAPI

logger = get_api_logger()


class DatabaseInitializer:
    """Handles database initialization and schema management."""

    @staticmethod
    @api_error_handler("initialize database")
    async def initialize() -> bool:
        """Initialize database connection and schema using Alembic migrations.

        BEST PRACTICE: Use Alembic migrations as single source of truth for schema management.
        This replaces manual SQL table creation for enterprise-grade database lifecycle.
        """
        import subprocess

        from ..database.init_db import init_db

        logger.info("Starting database initialization")

        # First, initialize basic database connection
        await init_db()

        # Run Alembic migrations to create/update schema
        # This is the industry standard approach for database schema management
        try:
            logger.info("Running Alembic migrations (alembic upgrade head)")
            result = subprocess.run(
                ["alembic", "upgrade", "head"],  # noqa: S607
                capture_output=True,
                text=True,
                check=True,
                cwd="/app",  # Run from project root where alembic.ini is located
            )
            logger.info(f"Alembic migrations completed successfully: {result.stdout}")
            logger.info("Enterprise-grade database schema ready via migrations")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Alembic migration failed: {e.stderr}")
            logger.warning("Database migration failed, but allowing startup to continue")
            return False
        except Exception as e:
            logger.error(f"Unexpected error during migration: {e}")
            logger.warning("Database migration error, but allowing startup to continue")
            return False


class ObservabilityInitializer:
    """Handles observability system initialization."""

    @staticmethod
    @api_error_handler("initialize observability")
    async def initialize() -> bool:
        """Initialize observability system."""
        from ..monitoring.observability import observability_manager

        logger.info("Starting observability system initialization")

        await observability_manager.initialize()
        logger.info("Observability system initialized successfully")
        return True

    @staticmethod
    @api_error_handler("shutdown observability")
    async def shutdown() -> bool:
        """Shutdown observability system."""
        from ..monitoring.observability import observability_manager

        logger.info("Starting observability system shutdown")

        await observability_manager.shutdown()
        logger.info("Observability system shutdown completed")
        return True


class EventSystemInitializer:
    """Handles event system initialization."""

    @staticmethod
    @api_error_handler("initialize event system")
    async def initialize() -> bool:
        """Initialize event system and background publishing."""
        from ..core.events.background import start_event_publishing
        from ..monitoring.redis_event_bridge import get_redis_event_bridge

        logger.info("Starting event system initialization")

        # Start background event publishing
        await start_event_publishing()
        logger.info("Event system initialized and background publishing started")

        # Start Redis-to-EventBus bridge for job events
        redis_bridge = get_redis_event_bridge()
        await redis_bridge.start()
        logger.info("Redis event bridge started - job events now flow to SSE clients")

        return True

    @staticmethod
    @api_error_handler("shutdown event system")
    async def shutdown() -> bool:
        """Shutdown event system."""
        from ..core.events.background import stop_event_publishing
        from ..monitoring.redis_event_bridge import get_redis_event_bridge

        logger.info("Starting event system shutdown")

        # Stop Redis event bridge
        redis_bridge = get_redis_event_bridge()
        await redis_bridge.stop()
        logger.info("Redis event bridge stopped")

        # Stop background event publishing
        await stop_event_publishing()
        logger.info("Event system shutdown completed")

        return True


class HealthMonitoringInitializer:
    """Handles health monitoring services initialization."""

    @staticmethod
    @api_error_handler("initialize health monitoring")
    async def initialize() -> bool:
        """Initialize health monitoring services."""
        from ..api.dependencies import async_session
        from ..caching.manager import cache_manager
        from ..monitoring.background_health_monitor import start_background_monitoring
        from ..monitoring.health_service_registry import (
            initialize_health_service_registry,
            start_health_monitoring,
        )

        logger.info("Starting health monitoring initialization")

        # Initialize cache manager to get Redis client
        await cache_manager.initialize()
        redis_client = await cache_manager._ensure_backend()._get_client()  # type: ignore[attr-defined]

        # FIXED: Use async_session factory instead of sync DatabaseService.get_session
        # This ensures PostgreSQLHealthEmitter can use async with correctly
        await initialize_health_service_registry(redis_client, async_session)

        # Start event-driven health monitoring for all services
        await start_health_monitoring()
        logger.info("Event-driven Health Service Registry initialized and started")

        # Start background health monitoring for real-time events (legacy system)
        await start_background_monitoring(check_interval=30)
        logger.info("Background health monitoring started successfully")

        return True

    @staticmethod
    @api_error_handler("shutdown health monitoring")
    async def shutdown() -> bool:
        """Shutdown health monitoring services."""
        from ..monitoring.background_health_monitor import stop_background_monitoring
        from ..monitoring.health_service_registry import stop_health_monitoring

        logger.info("Starting health monitoring shutdown")

        # Stop event-driven health monitoring
        await stop_health_monitoring()
        logger.info("Event-driven health monitoring stopped")

        # Stop background health monitoring
        await stop_background_monitoring()
        logger.info("Background health monitoring stopped")

        return True


class LifecycleManager:
    """Coordinates application startup and shutdown lifecycle."""

    @staticmethod
    @api_error_handler("application startup")
    async def startup() -> None:
        """Handle application startup sequence."""
        logger.info("Starting application startup sequence")

        # Database initialization (allow app to start even if fails)
        await _initialize_database_safe()

        # Observability initialization (allow app to start even if fails)
        await _initialize_observability_safe()

        # Event system initialization (allow app to start even if fails)
        await _initialize_event_system_safe()

        # Health monitoring initialization (allow app to start even if fails)
        await _initialize_health_monitoring_safe()

        logger.info("Application startup sequence completed")

    @staticmethod
    @api_error_handler("application shutdown")
    async def shutdown() -> None:
        """Handle application shutdown sequence."""
        logger.info("Starting application shutdown sequence")

        # Health monitoring shutdown
        await _shutdown_health_monitoring_safe()

        # Event system shutdown
        await _shutdown_event_system_safe()

        # Observability shutdown
        await _shutdown_observability_safe()

        logger.info("Application shutdown sequence completed")


@asynccontextmanager
async def lifespan(_app: "FastAPI") -> AsyncIterator[None]:
    """Application lifespan manager using structured lifecycle management."""
    # Startup
    await LifecycleManager.startup()

    yield

    # Shutdown
    await LifecycleManager.shutdown()


@api_error_handler("database initialization")
async def _initialize_database_safe() -> None:
    """Safely initialize database, allowing app to start even if it fails."""
    await DatabaseInitializer.initialize()


@api_error_handler("observability initialization")
async def _initialize_observability_safe() -> None:
    """Safely initialize observability, allowing app to start even if it fails."""
    await ObservabilityInitializer.initialize()


@api_error_handler("health monitoring initialization")
async def _initialize_health_monitoring_safe() -> None:
    """Safely initialize health monitoring, allowing app to start even if it fails."""
    await HealthMonitoringInitializer.initialize()


@api_error_handler("health monitoring shutdown")
async def _shutdown_health_monitoring_safe() -> None:
    """Safely shutdown health monitoring."""
    await HealthMonitoringInitializer.shutdown()


@api_error_handler("event system initialization")
async def _initialize_event_system_safe() -> None:
    """Safely initialize event system, allowing app to start even if it fails."""
    await EventSystemInitializer.initialize()


@api_error_handler("event system shutdown")
async def _shutdown_event_system_safe() -> None:
    """Safely shutdown event system."""
    await EventSystemInitializer.shutdown()


@api_error_handler("observability shutdown")
async def _shutdown_observability_safe() -> None:
    """Safely shutdown observability."""
    await ObservabilityInitializer.shutdown()
