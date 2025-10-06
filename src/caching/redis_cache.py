"""Redis-based cache backend implementation."""

import time
from typing import TYPE_CHECKING, Any

from src.core.decorators import cache_error_handler
from src.core.logging_hierarchy import get_cache_logger

from ..constants.caching import REDIS_SOCKET_CONNECT_TIMEOUT, REDIS_SOCKET_TIMEOUT, SAMPLE_KEY_COUNT
from ..constants.database import BYTES_PER_MB
from .base import BaseCacheBackend, CacheConfig, CacheEntry

logger = get_cache_logger()

# Runtime imports with proper error handling
try:
    import redis.asyncio as redis
    from redis.asyncio import Redis as RedisType

    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    if TYPE_CHECKING:
        import redis.asyncio as redis
        from redis.asyncio import Redis as RedisType
    else:
        redis = None  # type: ignore[assignment]
        RedisType = None  # type: ignore[misc,assignment]


class RedisCache(BaseCacheBackend):
    """Redis-based cache backend for high-performance caching."""

    def __init__(self, config: CacheConfig):
        """Initialize Redis cache.

        Args:
            config: Cache configuration

        Raises:
            ImportError: If redis package is not available
        """
        if not REDIS_AVAILABLE:
            raise ImportError(
                "redis package is required for Redis caching. Install with: pip install redis"
            )

        super().__init__(config)

        self.redis_client: RedisType | None = None
        self._stats = {"hits": 0, "misses": 0, "sets": 0, "deletes": 0, "errors": 0}

    async def initialize(self) -> None:
        """Initialize Redis connection and test connectivity."""
        await self._get_client()  # This will establish and test the connection

    async def shutdown(self) -> None:
        """Close Redis connection."""
        if self.redis_client:
            await self.redis_client.aclose()
            self.redis_client = None
            self.logger.info("Redis connection closed")

    @cache_error_handler("Redis client connection")
    async def _get_client(self) -> RedisType:
        """Get Redis client, creating connection if needed."""
        if self.redis_client is None:
            self.redis_client = redis.Redis(
                host=self.config.redis_host,
                port=self.config.redis_port,
                db=self.config.redis_db,
                password=self.config.redis_password,
                decode_responses=False,  # We handle encoding ourselves
                socket_connect_timeout=REDIS_SOCKET_CONNECT_TIMEOUT,
                socket_timeout=REDIS_SOCKET_TIMEOUT,
            )

            # Test connection - this will raise an exception if connection fails
            assert self.redis_client is not None, "Redis client should be initialized"
            await self.redis_client.ping()
            self.logger.info(
                "Redis connection established",
                host=self.config.redis_host,
                port=self.config.redis_port,
            )

        return self.redis_client

    @cache_error_handler("get server info")
    async def get_server_info(self) -> dict[str, Any]:
        """Get Redis server information following Redis best practices.

        Returns:
            Dictionary containing Redis server information
        """
        client = await self._get_client()
        info = await client.info()

        # Extract key information following Redis documentation patterns
        server_info = {
            "redis_version": info.get("redis_version", "unknown"),
            "redis_mode": info.get("redis_mode", "standalone"),
            "os": info.get("os", "unknown"),
            "arch_bits": info.get("arch_bits", "unknown"),
            "multiplexing_api": info.get("multiplexing_api", "unknown"),
            "process_id": info.get("process_id", "unknown"),
            "uptime_in_seconds": info.get("uptime_in_seconds", 0),
            "connected_clients": info.get("connected_clients", 0),
            "used_memory_human": info.get("used_memory_human", "unknown"),
            "role": info.get("role", "unknown"),  # master/slave for replication
        }

        return server_info

    @cache_error_handler("get backend type")
    async def get_backend_type(self) -> str:
        """Get detailed backend type information following Redis best practices.

        Returns:
            Detailed backend type string
        """
        server_info = await self.get_server_info()

        if "error" in server_info:
            return "redis_error"

        # Build descriptive backend type following Redis documentation patterns
        version = server_info.get("redis_version", "unknown")
        mode = server_info.get("redis_mode", "standalone")
        arch = server_info.get("arch_bits", "unknown")

        return f"redis_{mode}_{version}_{arch}bit"

    def _make_redis_key(self, key: str) -> str:
        """Create Redis key with prefix.

        Args:
            key: Cache key

        Returns:
            Redis key with prefix
        """
        return f"{self.config.redis_key_prefix}{key}"

    @cache_error_handler("cache get")
    async def get(self, key: str) -> CacheEntry | None:
        """Get a cache entry by key."""
        client = await self._get_client()
        redis_key = self._make_redis_key(key)

        # Get entry data
        data = await client.get(redis_key)
        if data is None:
            self._stats["misses"] += 1
            return None

        # Deserialize entry
        entry_data = self._decompress_data(data, compressed=True)
        entry = CacheEntry.from_dict(entry_data)

        # Redis TTL handling means we shouldn't get expired entries,
        # but check anyway for safety
        if entry.is_expired:
            await self.delete(key)
            self._stats["misses"] += 1
            return None

        self._stats["hits"] += 1
        self.logger.debug("Cache hit", key=key, age_seconds=entry.age_seconds)
        return entry

    @cache_error_handler("cache set")
    async def set(
        self, key: str, value: Any, ttl: int | None = None, content_type: str = "generic"
    ) -> bool:
        """Set a cache entry."""
        if ttl is None:
            ttl = self.get_ttl_for_content_type(content_type)

        # Create cache entry
        entry = CacheEntry(
            key=key,
            value=value,
            created_at=time.time(),
            ttl=ttl,
            content_type=content_type,
            size_bytes=self._calculate_size(value),
            compressed=self.config.compress,
        )

        # Serialize and compress entry
        entry_data = self._compress_data(entry.to_dict())

        # Store in Redis
        client = await self._get_client()
        redis_key = self._make_redis_key(key)

        if ttl > 0:
            await client.setex(redis_key, ttl, entry_data)
        else:
            await client.set(redis_key, entry_data)

        self._stats["sets"] += 1
        self.logger.debug("Cache set", key=key, size_bytes=entry.size_bytes, ttl=ttl)

        return True

    @cache_error_handler("cache delete")
    async def delete(self, key: str) -> bool:
        """Delete a cache entry."""
        client = await self._get_client()
        redis_key = self._make_redis_key(key)

        deleted = await client.delete(redis_key)

        if deleted:
            self._stats["deletes"] += 1
            self.logger.debug("Cache delete", key=key)

        return bool(deleted)

    @cache_error_handler("cache clear")
    async def clear(self) -> bool:
        """Clear all cache entries with our prefix."""
        client = await self._get_client()

        # Find all keys with our prefix
        pattern = f"{self.config.redis_key_prefix}*"
        keys = await client.keys(pattern)

        if keys:
            deleted = await client.delete(*keys)
            self.logger.info("Cache cleared", deleted_keys=deleted)
        else:
            self.logger.info("Cache was already empty")

        # Reset stats
        self._stats = {"hits": 0, "misses": 0, "sets": 0, "deletes": 0, "errors": 0}

        return True

    @cache_error_handler("cache stats")
    async def stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        client = await self._get_client()

        # Get Redis info
        redis_info = await client.info()

        # Count our keys
        pattern = f"{self.config.redis_key_prefix}*"
        keys = await client.keys(pattern)
        total_entries = len(keys)

        # Calculate total size (approximate)
        total_size = 0
        if keys:
            total_size = await self._calculate_total_size_safe(client, keys)

        return {
            **self._stats,
            "total_entries": total_entries,
            "total_size_bytes": total_size,
            "total_size_mb": round(total_size / BYTES_PER_MB, 2),
            "redis_version": redis_info.get("redis_version", "unknown"),
            "redis_memory_used": redis_info.get("used_memory_human", "unknown"),
            "redis_connected_clients": redis_info.get("connected_clients", 0),
            "hit_rate": (self._stats["hits"] / max(1, self._stats["hits"] + self._stats["misses"]))
            * 100,
        }

    @cache_error_handler("calculate total cache size")
    async def _calculate_total_size_safe(self, client: RedisType, keys: list[bytes]) -> int:
        """Safely calculate total cache size by sampling keys."""
        # Sample a few keys to estimate average size
        sample_keys = keys[: min(SAMPLE_KEY_COUNT, len(keys))]
        sample_sizes: list[int] = []

        for key in sample_keys:
            data = await client.get(key)
            if data:
                sample_sizes.append(len(data))

        if sample_sizes:
            avg_size = sum(sample_sizes) / len(sample_sizes)
            return int(avg_size * len(keys))

        return 0

    async def cleanup_expired(self) -> int:
        """Clean up expired cache entries.

        Note: Redis automatically handles TTL expiration, so this is mainly
        for consistency with the interface. Returns 0 since Redis handles it.
        """
        # Redis handles TTL automatically, so we don't need to do manual cleanup
        self.logger.debug("Redis handles TTL automatically, no manual cleanup needed")
        return 0

    async def close(self) -> None:
        """Close Redis connection."""
        if self.redis_client:
            await self._close_redis_connection_safe()

    @cache_error_handler("close Redis connection")
    async def _close_redis_connection_safe(self) -> None:
        """Safely close Redis connection."""
        assert self.redis_client is not None, "Redis client should exist before closing"
        await self.redis_client.close()
        self.logger.info("Redis connection closed")
        self.redis_client = None
