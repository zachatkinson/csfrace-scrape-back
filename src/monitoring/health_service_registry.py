"""Health Service Registry - Event-driven health monitoring following Astro MCP best practices.

This module implements the Health Service Registry pattern where each service is responsible
for monitoring and emitting its own health status. This follows DRY and SOLID principles
by giving each service a single responsibility for its health monitoring.

Architecture:
- Each service has its own health emitter
- Services publish health events to Redis pub/sub
- Backend aggregates these events and forwards via SSE
- Zero polling - pure event-driven architecture
"""

from __future__ import annotations

import contextlib
import json
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from enum import Enum
from typing import TYPE_CHECKING, Any, cast

import asyncio

from src.core.decorators import monitoring_error_handler
from src.core.logging_hierarchy import get_monitoring_logger

if TYPE_CHECKING:
    from redis.asyncio import Redis

logger = get_monitoring_logger()


def serialize_health_data(data: dict[str, Any]) -> dict[str, Any]:
    """Serialize health data, converting non-JSON-serializable types."""

    def convert_value(value: Any) -> Any:
        if isinstance(value, Decimal):
            return float(value)
        elif isinstance(value, datetime):
            return value.isoformat()
        elif isinstance(value, dict):
            return {k: convert_value(v) for k, v in value.items()}
        elif isinstance(value, list):
            return [convert_value(item) for item in value]
        else:
            return value

    return {k: convert_value(v) for k, v in data.items()}


class ServiceStatus(Enum):
    """Service health status levels."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class ServiceHealthData:
    """Health data structure for services."""

    service_name: str
    status: ServiceStatus
    timestamp: datetime
    response_time_ms: float
    details: dict[str, Any]
    version: str | None = None
    port: str | None = None
    framework: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        base_data = {
            "service": self.service_name,
            "status": self.status.value,
            "timestamp": self.timestamp.isoformat(),
            "response_time_ms": self.response_time_ms,
            "details": self.details,
            "version": self.version,
            "port": self.port,
            "framework": self.framework,
        }
        # Serialize all data to handle Decimal types and other non-JSON types
        return serialize_health_data(base_data)


class HealthEmitter(ABC):
    """Abstract base class for service health emitters following SOLID principles."""

    def __init__(self, service_name: str, redis_client: Redis, check_interval: float = 30.0):
        self.service_name = service_name
        self.redis_client = redis_client
        self.check_interval = check_interval
        self._running = False
        self._task: asyncio.Task[None] | None = None
        self._logger = logger.bind(service=service_name)

    @abstractmethod
    async def check_health(self) -> ServiceHealthData:
        """Check service health and return health data."""

    async def start_monitoring(self) -> None:
        """Start health monitoring loop."""
        if self._running:
            return

        self._running = True
        self._task = asyncio.create_task(self._monitoring_loop())
        self._logger.info("Started health monitoring", interval=self.check_interval)

    async def stop_monitoring(self) -> None:
        """Stop health monitoring."""
        if not self._running:
            return

        self._running = False
        if self._task:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task

        self._logger.info("Stopped health monitoring")

    @monitoring_error_handler("health monitoring loop")
    async def _monitoring_loop(self) -> None:
        """Main monitoring loop."""
        while self._running:
            # Check health
            health_data = await self.check_health()

            # Publish to Redis
            await self._publish_health_status(health_data)

            # Wait for next check
            await asyncio.sleep(self.check_interval)

    @monitoring_error_handler("health status publishing")
    async def _publish_health_status(self, health_data: ServiceHealthData) -> None:
        """Publish health status to Redis pub/sub."""
        health_json = json.dumps(health_data.to_dict())
        subscribers = await self.redis_client.publish("health_events", health_json)

        self._logger.debug(
            "Health status published",
            status=health_data.status.value,
            subscribers=subscribers,
            response_time=health_data.response_time_ms,
        )


class RedisHealthEmitter(HealthEmitter):
    """Redis service health emitter."""

    def __init__(self, redis_client: Redis, check_interval: float = 30.0):
        super().__init__("redis", redis_client, check_interval)

    @monitoring_error_handler("Redis health check")
    async def check_health(self) -> ServiceHealthData:
        """Check Redis health."""
        start_time = time.time()
        # Test Redis connection with PING
        response = await self.redis_client.ping()
        response_time_ms = (time.time() - start_time) * 1000

        if response:
            # Get Redis info
            info = await self.redis_client.info()

            details = {
                "connected": True,
                "version": info.get("redis_version", "unknown"),
                "uptime_seconds": info.get("uptime_in_seconds", 0),
                "connected_clients": info.get("connected_clients", 0),
                "used_memory_human": info.get("used_memory_human", "unknown"),
                "keyspace_hits": info.get("keyspace_hits", 0),
                "keyspace_misses": info.get("keyspace_misses", 0),
            }

            # Determine status based on response time
            if response_time_ms > 1000 or response_time_ms > 100:  # 1 second
                status = ServiceStatus.DEGRADED
            else:
                status = ServiceStatus.HEALTHY

            return ServiceHealthData(
                service_name="redis",
                status=status,
                timestamp=datetime.now(UTC),
                response_time_ms=response_time_ms,
                details=details,
                version=info.get("redis_version"),
                port="6379",
                framework="Redis",
            )
        else:
            raise Exception("Redis PING returned False")


class PostgreSQLHealthEmitter(HealthEmitter):
    """PostgreSQL service health emitter."""

    def __init__(self, redis_client: Redis, db_session_factory: Any, check_interval: float = 30.0):
        super().__init__("postgresql", redis_client, check_interval)
        self.db_session_factory = db_session_factory

    @monitoring_error_handler("PostgreSQL health check")
    async def check_health(self) -> ServiceHealthData:
        """Check PostgreSQL health."""
        from sqlalchemy import text

        start_time = time.time()

        # Test database connection using async session factory
        # Best Practice: All database operations must complete INSIDE the async with block
        async with self.db_session_factory() as session:
            # Simple query to test connectivity and get version
            result_obj = await session.execute(
                text("SELECT version(), current_database(), current_user")
            )
            result = result_obj.fetchone()
            response_time_ms = (time.time() - start_time) * 1000

            if not result:
                raise Exception("Database query returned no results")

            version_info = result[0] if result[0] else "unknown"
            database_name = result[1] if result[1] else "unknown"
            current_user = result[2] if result[2] else "unknown"

            # Get additional stats - MUST be inside the same session context
            stats_result_obj = await session.execute(
                text("""
                SELECT
                    pg_database_size(current_database()) as db_size,
                    (SELECT count(*) FROM pg_stat_activity WHERE state = 'active') as active_connections,
                    (SELECT setting FROM pg_settings WHERE name = 'max_connections') as max_connections
            """)
            )
            stats_result = stats_result_obj.fetchone()

            db_size = stats_result[0] if stats_result and stats_result[0] else 0
            active_connections = stats_result[1] if stats_result and stats_result[1] else 0
            max_connections = stats_result[2] if stats_result and stats_result[2] else 0

            # Build details dict - all data extracted from session
            details = {
                "connected": True,
                "database": database_name,
                "user": current_user,
                "version_info": version_info.split()[0:2],  # PostgreSQL version
                "database_size_bytes": int(db_size) if db_size else 0,
                "database_size_mb": round(int(db_size) / 1024 / 1024, 2) if db_size else 0,
                "active_connections": int(active_connections) if active_connections else 0,
                "max_connections": int(max_connections) if max_connections else 0,
                "connection_usage_percent": round(
                    (int(active_connections) / int(max_connections)) * 100, 2
                )
                if max_connections and int(max_connections) > 0
                else 0,
            }

            # Determine status based on response time and connection usage
            connection_usage = cast("float", details["connection_usage_percent"])
            if response_time_ms > 2000 or connection_usage > 90:  # 2 seconds or >90% connections
                status = ServiceStatus.UNHEALTHY
            elif response_time_ms > 1000 or connection_usage > 75:  # 1 second or >75% connections
                status = ServiceStatus.DEGRADED
            else:
                status = ServiceStatus.HEALTHY

            # Extract PostgreSQL version
            pg_version = version_info.split()[1] if len(version_info.split()) > 1 else "unknown"

            # Session will be automatically committed and closed by context manager
            # All data must be extracted and converted to Python types before exiting block
            return ServiceHealthData(
                service_name="postgresql",
                status=status,
                timestamp=datetime.now(UTC),
                response_time_ms=response_time_ms,
                details=details,
                version=pg_version,
                port="5432",
                framework="PostgreSQL",
            )


class FrontendHealthEmitter(HealthEmitter):
    """Frontend service health emitter (runs from backend for coordination)."""

    def __init__(
        self,
        redis_client: Redis,
        frontend_url: str = "http://frontend:3000",
        check_interval: float = 30.0,
    ):
        super().__init__("frontend", redis_client, check_interval)
        self.frontend_url = frontend_url

    @monitoring_error_handler("Frontend health check")
    async def check_health(self) -> ServiceHealthData:
        """Check Frontend health by making HTTP request."""
        import aiohttp

        start_time = time.time()

        async with (
            aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session,
            session.get(f"{self.frontend_url}/") as response,
        ):
            response_time_ms = (time.time() - start_time) * 1000

            details = {
                "connected": True,
                "status_code": response.status,
                "content_length": response.headers.get("content-length", "unknown"),
                "server": response.headers.get("server", "unknown"),
            }

            # Determine status based on HTTP status and response time
            if response.status >= 500:
                status = ServiceStatus.UNHEALTHY
            elif (
                response.status >= 400 or response_time_ms > 5000 or response_time_ms > 2000
            ):  # 5 seconds
                status = ServiceStatus.DEGRADED
            else:
                status = ServiceStatus.HEALTHY

            return ServiceHealthData(
                service_name="frontend",
                status=status,
                timestamp=datetime.now(UTC),
                response_time_ms=response_time_ms,
                details=details,
                version="5.13.7",  # Astro version
                port="3000",
                framework="Astro + React + TypeScript",
            )


class BackendHealthEmitter(HealthEmitter):
    """Backend service health emitter (self-monitoring)."""

    def __init__(self, redis_client: Redis, check_interval: float = 30.0):
        super().__init__("backend", redis_client, check_interval)

    @monitoring_error_handler("Backend health check")
    async def check_health(self) -> ServiceHealthData:
        """Check Backend health (self-monitoring)."""
        start_time = time.time()

        # Simple health check - always healthy since we're running
        response_time_ms = (time.time() - start_time) * 1000

        # Get system info
        import psutil

        cpu_percent = psutil.cpu_percent(interval=0.1)
        memory = psutil.virtual_memory()

        details = {
            "connected": True,
            "cpu_percent": cpu_percent,
            "memory_percent": memory.percent,
            "memory_available_gb": round(memory.available / (1024**3), 2),
            "status": "operational",
        }

        # Determine status based on resource usage
        if cpu_percent > 90 or memory.percent > 90:
            status = ServiceStatus.UNHEALTHY
        elif cpu_percent > 75 or memory.percent > 75:
            status = ServiceStatus.DEGRADED
        else:
            status = ServiceStatus.HEALTHY

        return ServiceHealthData(
            service_name="backend",
            status=status,
            timestamp=datetime.now(UTC),
            response_time_ms=response_time_ms,
            details=details,
            version="1.0.0",  # Application version
            port="8000",
            framework="FastAPI + Python 3.13",
        )


class HealthServiceRegistry:
    """
    Health Service Registry - Coordinates all service health emitters.

    This follows Astro MCP best practices by:
    1. Single Responsibility: Each service manages its own health
    2. DRY: No duplicate health checking logic
    3. Event-driven: Services emit events instead of being polled
    4. SOLID: Open/closed principle - easy to add new services
    """

    def __init__(self, redis_client: Redis):
        self.redis_client = redis_client
        self.emitters: dict[str, HealthEmitter] = {}
        self._logger = logger.bind(component="health_service_registry")

    def register_service(self, emitter: HealthEmitter) -> None:
        """Register a service health emitter."""
        self.emitters[emitter.service_name] = emitter
        self._logger.info("Service registered", service=emitter.service_name)

    def unregister_service(self, service_name: str) -> None:
        """Unregister a service health emitter."""
        if service_name in self.emitters:
            del self.emitters[service_name]
            self._logger.info("Service unregistered", service=service_name)

    @monitoring_error_handler("start all monitoring")
    async def start_all_monitoring(self) -> None:
        """Start monitoring for all registered services."""
        for service_name, emitter in self.emitters.items():
            await emitter.start_monitoring()
            self._logger.info("Started monitoring", service=service_name)

    @monitoring_error_handler("stop all monitoring")
    async def stop_all_monitoring(self) -> None:
        """Stop monitoring for all registered services."""
        for service_name, emitter in self.emitters.items():
            await emitter.stop_monitoring()
            self._logger.info("Stopped monitoring", service=service_name)

    async def initialize_default_services(
        self, db_session_factory: Any, frontend_url: str = "http://frontend:3000"
    ) -> None:
        """Initialize all default service emitters."""
        # Register Redis health emitter
        redis_emitter = RedisHealthEmitter(self.redis_client)
        self.register_service(redis_emitter)

        # Register PostgreSQL health emitter
        postgres_emitter = PostgreSQLHealthEmitter(self.redis_client, db_session_factory)
        self.register_service(postgres_emitter)

        # Register Frontend health emitter
        frontend_emitter = FrontendHealthEmitter(self.redis_client, frontend_url)
        self.register_service(frontend_emitter)

        # Register Backend health emitter (self-monitoring)
        backend_emitter = BackendHealthEmitter(self.redis_client)
        self.register_service(backend_emitter)

        self._logger.info("All default services initialized", services=list(self.emitters.keys()))

    def get_registered_services(self) -> list[str]:
        """Get list of registered service names."""
        return list(self.emitters.keys())


# Global registry instance
health_service_registry: HealthServiceRegistry | None = None


async def initialize_health_service_registry(
    redis_client: Redis, db_session_factory: Any
) -> HealthServiceRegistry:
    """Initialize the global health service registry."""
    global health_service_registry

    health_service_registry = HealthServiceRegistry(redis_client)
    await health_service_registry.initialize_default_services(db_session_factory)

    logger.info("Health Service Registry initialized following Astro MCP best practices")
    return health_service_registry


async def start_health_monitoring() -> None:
    """Start health monitoring for all services."""
    if health_service_registry:
        await health_service_registry.start_all_monitoring()
        logger.info("Event-driven health monitoring started for all services")
    else:
        logger.warning("Health Service Registry not initialized")


async def stop_health_monitoring() -> None:
    """Stop health monitoring for all services."""
    if health_service_registry:
        await health_service_registry.stop_all_monitoring()
        logger.info("Health monitoring stopped for all services")
