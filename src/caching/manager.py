"""Cache manager for coordinating cache operations and strategies."""

import hashlib
from typing import Any, TYPE_CHECKING

import structlog

from .base import BaseCacheBackend, CacheBackend, CacheConfig
from .file_cache import FileCache

# Import Redis cache only if available
if TYPE_CHECKING:
    from .redis_cache import RedisCache

try:
    from .redis_cache import RedisCache
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    
    # Create a dummy RedisCache class for runtime
    class RedisCache(BaseCacheBackend):  # type: ignore[misc]
        def __init__(self, *args, **kwargs):
            raise ImportError("Redis package not available")

logger = structlog.get_logger(__name__)


class CacheManager:
    """High-level cache manager that coordinates multiple cache backends."""

    def __init__(self, config: CacheConfig | None = None):
        """Initialize cache manager.

        Args:
            config: Cache configuration (defaults to file-based cache)
        """
        self.config = config or CacheConfig()
        self.backend: BaseCacheBackend | None = None
        self._initialized = False

    def _ensure_backend(self) -> BaseCacheBackend:
        """Ensure backend is initialized and return it."""
        if self.backend is None:
            raise RuntimeError("Cache manager not initialized. Call initialize() first.")
        return self.backend

    async def initialize(self) -> None:
        """Initialize the cache backend."""
        if self._initialized:
            return

        try:
            # Create appropriate backend
            if self.config.backend == CacheBackend.FILE:
                self.backend = FileCache(self.config)
            elif self.config.backend == CacheBackend.REDIS:
                if not REDIS_AVAILABLE:
                    raise ValueError(
                        "Redis backend requested but redis package not available. Install with: pip install redis"
                    )
                self.backend = RedisCache(self.config)
                # Initialize Redis connection - this will test connectivity
                await self.backend.initialize()
            else:
                raise ValueError(f"Unsupported cache backend: {self.config.backend}")

            # Cleanup expired entries on startup if configured
            if self.config.cleanup_on_startup:
                backend = self._ensure_backend()
                cleaned = await backend.cleanup_expired()
                if cleaned > 0:
                    logger.info("Startup cache cleanup completed", cleaned_entries=cleaned)

            self._initialized = True
            logger.info("Cache manager initialized", backend=self.config.backend.value)

        except Exception as e:
            logger.error("Failed to initialize cache manager", error=str(e))
            raise

    async def get_html(self, url: str) -> str | None:
        """Get cached HTML content for a URL.

        Args:
            url: URL to get HTML for

        Returns:
            Cached HTML content or None if not found/expired
        """
        if not self._initialized:
            await self.initialize()

        key = self._make_html_key(url)
        backend = self._ensure_backend()
        entry = await backend.get(key)

        if entry:
            logger.debug("Cache hit for HTML", url=url)
            return entry.value

        return None

    async def set_html(self, url: str, html_content: str, ttl: int | None = None) -> bool:
        """Cache HTML content for a URL.

        Args:
            url: URL the HTML content came from
            html_content: HTML content to cache
            ttl: Custom TTL in seconds

        Returns:
            True if successfully cached
        """
        if not self._initialized:
            await self.initialize()

        key = self._make_html_key(url)
        backend = self._ensure_backend()
        return await backend.set(key, html_content, ttl, "html")

    async def get_image(self, image_url: str) -> bytes | None:
        """Get cached image data.

        Args:
            image_url: URL of the image

        Returns:
            Cached image data or None if not found/expired
        """
        if not self._initialized:
            await self.initialize()

        key = self._make_image_key(image_url)
        backend = self._ensure_backend()
        entry = await backend.get(key)

        if entry:
            logger.debug("Cache hit for image", url=image_url)
            return entry.value

        return None

    async def set_image(self, image_url: str, image_data: bytes, ttl: int | None = None) -> bool:
        """Cache image data.

        Args:
            image_url: URL of the image
            image_data: Image data to cache
            ttl: Custom TTL in seconds

        Returns:
            True if successfully cached
        """
        if not self._initialized:
            await self.initialize()

        key = self._make_image_key(image_url)
        backend = self._ensure_backend()
        return await backend.set(key, image_data, ttl, "image")

    async def get_metadata(self, url: str) -> dict[str, Any] | None:
        """Get cached metadata for a URL.

        Args:
            url: URL to get metadata for

        Returns:
            Cached metadata or None if not found/expired
        """
        if not self._initialized:
            await self.initialize()

        key = self._make_metadata_key(url)
        backend = self._ensure_backend()
        entry = await backend.get(key)

        if entry:
            logger.debug("Cache hit for metadata", url=url)
            return entry.value

        return None

    async def set_metadata(
        self, url: str, metadata: dict[str, Any], ttl: int | None = None
    ) -> bool:
        """Cache metadata for a URL.

        Args:
            url: URL the metadata came from
            metadata: Metadata to cache
            ttl: Custom TTL in seconds

        Returns:
            True if successfully cached
        """
        if not self._initialized:
            await self.initialize()

        key = self._make_metadata_key(url)
        backend = self._ensure_backend()
        return await backend.set(key, metadata, ttl, "metadata")

    async def get_robots_txt(self, domain: str) -> str | None:
        """Get cached robots.txt content for a domain.

        Args:
            domain: Domain to get robots.txt for

        Returns:
            Cached robots.txt content or None if not found/expired
        """
        if not self._initialized:
            await self.initialize()

        key = self._make_robots_key(domain)
        backend = self._ensure_backend()
        entry = await backend.get(key)

        if entry:
            logger.debug("Cache hit for robots.txt", domain=domain)
            return entry.value

        return None

    async def set_robots_txt(
        self, domain: str, robots_content: str, ttl: int | None = None
    ) -> bool:
        """Cache robots.txt content for a domain.

        Args:
            domain: Domain the robots.txt came from
            robots_content: Robots.txt content to cache
            ttl: Custom TTL in seconds

        Returns:
            True if successfully cached
        """
        if not self._initialized:
            await self.initialize()

        key = self._make_robots_key(domain)
        backend = self._ensure_backend()
        return await backend.set(key, robots_content, ttl, "robots")

    async def invalidate_url(self, url: str) -> bool:
        """Invalidate all cached data for a URL.

        Args:
            url: URL to invalidate

        Returns:
            True if any cache entries were deleted
        """
        if not self._initialized:
            await self.initialize()

        deleted_any = False

        # Delete HTML cache
        html_key = self._make_html_key(url)
        backend = self._ensure_backend()
        if await backend.delete(html_key):
            deleted_any = True

        # Delete metadata cache
        metadata_key = self._make_metadata_key(url)
        if await backend.delete(metadata_key):
            deleted_any = True

        logger.debug("Invalidated cache for URL", url=url, deleted=deleted_any)
        return deleted_any

    async def get_cache_stats(self) -> dict[str, Any]:
        """Get comprehensive cache statistics.

        Returns:
            Dictionary with cache statistics
        """
        if not self._initialized:
            await self.initialize()

        backend = self._ensure_backend()
        stats = await backend.stats()
        stats["backend"] = self.config.backend.value
        stats["config"] = {
            "ttl_html": self.config.ttl_html,
            "ttl_images": self.config.ttl_images,
            "ttl_metadata": self.config.ttl_metadata,
            "ttl_robots": self.config.ttl_robots,
            "compress": self.config.compress,
        }

        return stats

    async def cleanup_expired(self) -> int:
        """Clean up expired cache entries.

        Returns:
            Number of entries cleaned up
        """
        if not self._initialized:
            await self.initialize()

        backend = self._ensure_backend()
        return await backend.cleanup_expired()

    async def clear_cache(self) -> bool:
        """Clear all cache entries.

        Returns:
            True if cache was cleared successfully
        """
        if not self._initialized:
            await self.initialize()

        backend = self._ensure_backend()
        return await backend.clear()

    def _make_html_key(self, url: str) -> str:
        """Create cache key for HTML content."""
        return f"html:{self._hash_url(url)}"

    def _make_image_key(self, image_url: str) -> str:
        """Create cache key for image data."""
        return f"image:{self._hash_url(image_url)}"

    def _make_metadata_key(self, url: str) -> str:
        """Create cache key for metadata."""
        return f"metadata:{self._hash_url(url)}"

    def _make_robots_key(self, domain: str) -> str:
        """Create cache key for robots.txt."""
        return f"robots:{domain}"

    def _hash_url(self, url: str) -> str:
        """Create a hash of a URL for use in cache keys."""
        from ..constants import CONSTANTS

        return hashlib.sha256(url.encode()).hexdigest()[: CONSTANTS.HASH_LENGTH]

    async def shutdown(self) -> None:
        """Shutdown cache manager and backend."""
        if self.backend:
            if hasattr(self.backend, "shutdown"):
                await self.backend.shutdown()
            elif hasattr(self.backend, "close"):
                await self.backend.close()

        self._initialized = False
        logger.info("Cache manager shutdown")


# Global cache manager instance
cache_manager = CacheManager()
