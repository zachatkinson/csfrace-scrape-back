"""Redis-based cache backend implementation."""

import time
from typing import Any, Optional

from ..constants import CONSTANTS
from .base import BaseCacheBackend, CacheConfig, CacheEntry

try:
    import redis.asyncio as redis

    REDIS_AVAILABLE = True
    RedisType = redis.Redis
except ImportError:
    REDIS_AVAILABLE = False
    redis = None
    RedisType = None


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

        self.redis_client = None
        self._stats = {"hits": 0, "misses": 0, "sets": 0, "deletes": 0, "errors": 0}

    async def initialize(self):
        """Initialize Redis connection and test connectivity."""
        await self._get_client()  # This will establish and test the connection

    async def shutdown(self):
        """Close Redis connection."""
        if self.redis_client:
            await self.redis_client.aclose()
            self.redis_client = None
            self.logger.info("Redis connection closed")

    async def _get_client(self):
        """Get Redis client, creating connection if needed."""
        if self.redis_client is None:
            try:
                from ..constants import CONSTANTS

                self.redis_client = redis.Redis(
                    host=self.config.redis_host,
                    port=self.config.redis_port,
                    db=self.config.redis_db,
                    password=self.config.redis_password,
                    decode_responses=False,  # We handle encoding ourselves
                    socket_connect_timeout=CONSTANTS.REDIS_SOCKET_CONNECT_TIMEOUT,
                    socket_timeout=CONSTANTS.REDIS_SOCKET_TIMEOUT,
                )

                # Test connection - this will raise an exception if connection fails
                await self.redis_client.ping()
                self.logger.info(
                    "Redis connection established",
                    host=self.config.redis_host,
                    port=self.config.redis_port,
                )

            except Exception as e:
                self.logger.error("Failed to connect to Redis", error=str(e))
                # Clean up failed connection attempt
                if self.redis_client:
                    try:
                        await self.redis_client.aclose()
                    except Exception as cleanup_error:
                        self.logger.warning(
                            "Failed to cleanup Redis connection", error=str(cleanup_error)
                        )
                    self.redis_client = None
                raise

        return self.redis_client

    def _make_redis_key(self, key: str) -> str:
        """Create Redis key with prefix.

        Args:
            key: Cache key

        Returns:
            Redis key with prefix
        """
        return f"{self.config.redis_key_prefix}{key}"

    async def get(self, key: str) -> Optional[CacheEntry]:
        """Get a cache entry by key."""
        try:
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

        except Exception as e:
            self._stats["errors"] += 1
            self.logger.warning("Cache get failed", key=key, error=str(e))
            return None

    async def set(
        self, key: str, value: Any, ttl: Optional[int] = None, content_type: str = "generic"
    ) -> bool:
        """Set a cache entry."""
        try:
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

        except Exception as e:
            self._stats["errors"] += 1
            self.logger.error("Cache set failed", key=key, error=str(e))
            return False

    async def delete(self, key: str) -> bool:
        """Delete a cache entry."""
        try:
            client = await self._get_client()
            redis_key = self._make_redis_key(key)

            deleted = await client.delete(redis_key)

            if deleted:
                self._stats["deletes"] += 1
                self.logger.debug("Cache delete", key=key)

            return bool(deleted)

        except Exception as e:
            self._stats["errors"] += 1
            self.logger.error("Cache delete failed", key=key, error=str(e))
            return False

    async def clear(self) -> bool:
        """Clear all cache entries with our prefix."""
        try:
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

        except Exception as e:
            self._stats["errors"] += 1
            self.logger.error("Cache clear failed", error=str(e))
            return False

    async def stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        try:
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
                # Sample a few keys to estimate average size
                sample_keys = keys[: min(CONSTANTS.SAMPLE_KEY_COUNT, len(keys))]
                sample_sizes = []

                for key in sample_keys:
                    try:
                        data = await client.get(key)
                        if data:
                            sample_sizes.append(len(data))
                    except (redis.RedisError, OSError) as e:
                        # Skip keys that cause Redis errors or network issues
                        logger.debug(f"Failed to sample key {key}: {e}")
                        continue

                if sample_sizes:
                    avg_size = sum(sample_sizes) / len(sample_sizes)
                    total_size = int(avg_size * total_entries)

            return {
                **self._stats,
                "total_entries": total_entries,
                "total_size_bytes": total_size,
                "total_size_mb": round(total_size / CONSTANTS.BYTES_PER_MB, 2),
                "redis_version": redis_info.get("redis_version", "unknown"),
                "redis_memory_used": redis_info.get("used_memory_human", "unknown"),
                "redis_connected_clients": redis_info.get("connected_clients", 0),
                "hit_rate": (
                    self._stats["hits"] / max(1, self._stats["hits"] + self._stats["misses"])
                )
                * 100,
            }

        except Exception as e:
            self.logger.error("Cache stats failed", error=str(e))
            return {"error": str(e)}

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
            try:
                await self.redis_client.close()
                self.logger.info("Redis connection closed")
            except Exception as e:
                self.logger.error("Error closing Redis connection", error=str(e))
            finally:
                self.redis_client = None
