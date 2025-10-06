"""Cache-related health checks."""

from ...core.decorators import monitoring_error_handler
from ...core.logging_hierarchy import get_monitoring_logger
from .base import HealthCheck, HealthCheckResult, HealthStatus

logger = get_monitoring_logger()


class RedisHealthCheck(HealthCheck):
    """Health check for Redis connectivity."""

    def __init__(
        self, name: str = "redis", timeout_seconds: float = 5.0, redis_url: str | None = None
    ):
        super().__init__(name, timeout_seconds)
        self.redis_url = redis_url

    @monitoring_error_handler("redis health check")
    async def check(self) -> HealthCheckResult:
        """Check Redis connectivity."""
        import time

        start_time = time.time()

        # Handle ImportError specifically for Redis
        try:
            import redis.asyncio as redis
        except ImportError:
            duration_ms = (time.time() - start_time) * 1000
            return HealthCheckResult(
                name=self.name,
                status=HealthStatus.UNHEALTHY,
                message="Redis library not available",
                duration_ms=duration_ms,
                details={"error": "redis package not installed"},
            )

        # Create Redis connection
        if self.redis_url:
            r = redis.from_url(self.redis_url)  # type: ignore[no-untyped-call]
        else:
            r = redis.Redis(host="localhost", port=6379, db=0, decode_responses=True)

        # Test basic operations
        test_key = "health_check:test"
        test_value = "health_check_value"

        # Set a test value
        await r.set(test_key, test_value, ex=10)  # Expire in 10 seconds

        # Get the test value
        retrieved_value = await r.get(test_key)

        # Clean up
        await r.delete(test_key)
        await r.aclose()

        if retrieved_value == test_value:
            duration_ms = (time.time() - start_time) * 1000
            return HealthCheckResult(
                name=self.name,
                status=HealthStatus.HEALTHY,
                message="Redis connection successful and operations working",
                duration_ms=duration_ms,
                details={"test_operation": "set/get/delete completed successfully"},
            )
        else:
            duration_ms = (time.time() - start_time) * 1000
            return HealthCheckResult(
                name=self.name,
                status=HealthStatus.UNHEALTHY,
                message="Redis operations failed - value mismatch",
                duration_ms=duration_ms,
                details={"expected": test_value, "retrieved": retrieved_value},
            )
        # Enhanced decorator will handle generic Exception case


class CacheHealthCheck(HealthCheck):
    """Generic cache health check that can work with different cache backends."""

    def __init__(self, name: str = "cache", timeout_seconds: float = 5.0):
        super().__init__(name, timeout_seconds)

    @monitoring_error_handler("cache health check")
    async def check(self) -> HealthCheckResult:
        """Check cache system health."""
        import time

        start_time = time.time()

        # Handle ImportError specifically for cache system
        try:
            from ...caching.manager import CacheManager
        except ImportError as e:
            duration_ms = (time.time() - start_time) * 1000
            logger.warning(f"Cache system not available: {e}")
            return HealthCheckResult(
                name=self.name,
                status=HealthStatus.DEGRADED,
                message="Cache system not available - running without cache",
                duration_ms=duration_ms,
                details={"error": str(e), "impact": "degraded_performance"},
            )

        # Create cache manager instance
        cache_manager = CacheManager()

        # Initialize the cache manager
        await cache_manager.initialize()

        # Test basic cache operations using the specific methods
        test_url = "http://health_check_test/page"
        test_data = {"test": "data", "timestamp": "2025-01-01"}

        # Test set/get operations using metadata methods
        await cache_manager.set_metadata(test_url, test_data, ttl=10)

        # Test get operation
        retrieved_data = await cache_manager.get_metadata(test_url)

        # Test delete operation (via invalidation)
        await cache_manager.invalidate_url(test_url)

        # Verify the data matches
        if retrieved_data == test_data:
            duration_ms = (time.time() - start_time) * 1000
            return HealthCheckResult(
                name=self.name,
                status=HealthStatus.HEALTHY,
                message="Cache system is working correctly",
                duration_ms=duration_ms,
                details={
                    "operations_tested": ["set", "get", "delete"],
                    "test_successful": True,
                },
            )
        else:
            duration_ms = (time.time() - start_time) * 1000
            return HealthCheckResult(
                name=self.name,
                status=HealthStatus.DEGRADED,
                message="Cache operations partially working - data mismatch",
                duration_ms=duration_ms,
                details={
                    "expected": test_data,
                    "retrieved": retrieved_data,
                    "operations_tested": ["set", "get", "delete"],
                },
            )
        # Enhanced decorator will handle generic Exception case
