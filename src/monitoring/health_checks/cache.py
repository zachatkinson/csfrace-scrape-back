"""Cache-related health checks."""

from ...utils.logging import get_logger
from .base import HealthCheck, HealthCheckResult, HealthStatus

logger = get_logger(__name__)


class RedisHealthCheck(HealthCheck):
    """Health check for Redis connectivity."""

    def __init__(
        self, name: str = "redis", timeout_seconds: float = 5.0, redis_url: str | None = None
    ):
        super().__init__(name, timeout_seconds)
        self.redis_url = redis_url

    async def check(self) -> HealthCheckResult:
        """Check Redis connectivity."""
        import time

        start_time = time.time()

        try:
            # Try to import redis
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
                r = redis.from_url(self.redis_url)
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

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            logger.error(f"Redis health check failed: {e}")
            return HealthCheckResult(
                name=self.name,
                status=HealthStatus.UNHEALTHY,
                message=f"Redis connection failed: {str(e)}",
                duration_ms=duration_ms,
                details={"error_type": type(e).__name__},
            )


class CacheHealthCheck(HealthCheck):
    """Generic cache health check that can work with different cache backends."""

    def __init__(self, name: str = "cache", timeout_seconds: float = 5.0):
        super().__init__(name, timeout_seconds)

    async def check(self) -> HealthCheckResult:
        """Check cache system health."""
        import time

        start_time = time.time()

        try:
            # Try to import and test the caching system
            from ...caching.manager import CacheManager

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
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            logger.error(f"Cache health check failed: {e}")
            return HealthCheckResult(
                name=self.name,
                status=HealthStatus.UNHEALTHY,
                message=f"Cache system failed: {str(e)}",
                duration_ms=duration_ms,
                details={"error_type": type(e).__name__},
            )
