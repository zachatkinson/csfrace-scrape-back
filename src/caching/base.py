"""Base cache interfaces and types."""

import abc
import hashlib
import json
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Optional, Union

import structlog

from ..constants import CONSTANTS

logger = structlog.get_logger(__name__)


class CacheBackend(Enum):
    """Supported cache backend types."""

    FILE = "file"
    REDIS = "redis"
    MEMORY = "memory"


@dataclass
class CacheConfig:
    """Configuration for caching system using centralized constants."""

    backend: CacheBackend = CacheBackend.FILE
    ttl_default: int = CONSTANTS.DEFAULT_TTL
    ttl_html: int = CONSTANTS.CACHE_TTL_HTML
    ttl_images: int = CONSTANTS.CACHE_TTL_IMAGES
    ttl_metadata: int = CONSTANTS.CACHE_TTL_METADATA
    ttl_robots: int = CONSTANTS.ROBOTS_CACHE_DURATION

    # File cache settings
    cache_dir: Path = Path(".cache")
    max_cache_size_mb: int = CONSTANTS.MAX_CACHE_SIZE_MB

    # Redis cache settings - using centralized constants
    redis_host: str = CONSTANTS.REDIS_HOST
    redis_port: int = CONSTANTS.REDIS_PORT
    redis_db: int = CONSTANTS.REDIS_DB
    redis_password: Optional[str] = None
    redis_key_prefix: str = CONSTANTS.REDIS_KEY_PREFIX

    # General settings
    compress: bool = True
    cleanup_on_startup: bool = True
    max_key_length: int = CONSTANTS.MAX_KEY_LENGTH


@dataclass
class CacheEntry:
    """Represents a cache entry with metadata."""

    key: str
    value: Any
    created_at: float
    ttl: int
    content_type: str = "generic"
    size_bytes: int = 0
    compressed: bool = False

    @property
    def is_expired(self) -> bool:
        """Check if cache entry has expired."""
        if self.ttl <= 0:  # TTL of 0 or negative means no expiration
            return False
        return time.time() > (self.created_at + self.ttl)

    @property
    def age_seconds(self) -> float:
        """Get age of cache entry in seconds."""
        return time.time() - self.created_at

    def to_dict(self) -> dict[str, Any]:
        """Convert cache entry to dictionary for serialization."""
        return {
            "key": self.key,
            "value": self.value,
            "created_at": self.created_at,
            "ttl": self.ttl,
            "content_type": self.content_type,
            "size_bytes": self.size_bytes,
            "compressed": self.compressed,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CacheEntry":
        """Create cache entry from dictionary."""
        return cls(**data)


class BaseCacheBackend(abc.ABC):
    """Abstract base class for cache backends."""

    def __init__(self, config: CacheConfig):
        """Initialize cache backend.

        Args:
            config: Cache configuration
        """
        self.config = config
        self.logger = structlog.get_logger(self.__class__.__name__)

    @abc.abstractmethod
    async def get(self, key: str) -> Optional[CacheEntry]:
        """Get a cache entry by key.

        Args:
            key: Cache key

        Returns:
            Cache entry if found and not expired, None otherwise
        """
        pass

    @abc.abstractmethod
    async def set(
        self, key: str, value: Any, ttl: Optional[int] = None, content_type: str = "generic"
    ) -> bool:
        """Set a cache entry.

        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live in seconds (uses default if None)
            content_type: Type of content being cached

        Returns:
            True if successfully cached
        """
        pass

    @abc.abstractmethod
    async def delete(self, key: str) -> bool:
        """Delete a cache entry.

        Args:
            key: Cache key to delete

        Returns:
            True if entry was deleted
        """
        pass

    @abc.abstractmethod
    async def clear(self) -> bool:
        """Clear all cache entries.

        Returns:
            True if cache was cleared successfully
        """
        pass

    @abc.abstractmethod
    async def stats(self) -> dict[str, Any]:
        """Get cache statistics.

        Returns:
            Dictionary with cache statistics
        """
        pass

    @abc.abstractmethod
    async def cleanup_expired(self) -> int:
        """Clean up expired cache entries.

        Returns:
            Number of entries cleaned up
        """
        pass

    def generate_key(self, *parts: Union[str, int, float]) -> str:
        """Generate a cache key from parts.

        Args:
            *parts: Key components

        Returns:
            Generated cache key
        """
        # Create key from parts
        key_parts = [str(part) for part in parts]
        raw_key = ":".join(key_parts)

        # Hash if too long
        if len(raw_key) > self.config.max_key_length:
            key_hash = hashlib.sha256(raw_key.encode()).hexdigest()[: CONSTANTS.HASH_LENGTH]
            # Keep some readable part + hash
            readable_part = raw_key[: self.config.max_key_length - CONSTANTS.KEY_READABLE_OFFSET]
            return f"{readable_part}:{key_hash}"

        return raw_key

    def get_ttl_for_content_type(self, content_type: str) -> int:
        """Get appropriate TTL for content type.

        Args:
            content_type: Type of content

        Returns:
            TTL in seconds
        """
        ttl_mapping = {
            "html": self.config.ttl_html,
            "image": self.config.ttl_images,
            "metadata": self.config.ttl_metadata,
            "robots": self.config.ttl_robots,
        }

        return ttl_mapping.get(content_type, self.config.ttl_default)

    def _compress_data(self, data: Any) -> bytes:
        """Compress data if compression is enabled.

        Args:
            data: Data to compress

        Returns:
            Compressed data as bytes
        """
        if not self.config.compress:
            return json.dumps(data, default=self._json_serializer).encode("utf-8")

        import gzip

        json_data = json.dumps(data, default=self._json_serializer).encode("utf-8")
        return gzip.compress(json_data)

    def _decompress_data(self, data: bytes, compressed: bool = False) -> Any:
        """Decompress data if it was compressed.

        Args:
            data: Compressed data
            compressed: Whether data is compressed

        Returns:
            Decompressed data
        """
        if not compressed or not self.config.compress:
            json_str = data.decode("utf-8")
        else:
            import gzip

            decompressed = gzip.decompress(data)
            json_str = decompressed.decode("utf-8")

        # Parse JSON with custom object hook
        return json.loads(json_str, object_hook=self._json_deserializer)

    def _json_deserializer(self, obj: dict) -> Any:
        """Custom JSON deserializer for non-standard types.

        Args:
            obj: Dictionary from JSON parsing

        Returns:
            Deserialized object
        """
        if isinstance(obj, dict) and "__type__" in obj and "__value__" in obj:
            obj_type = obj["__type__"]
            obj_value = obj["__value__"]

            if obj_type == "bytes":
                import base64

                return base64.b64decode(obj_value.encode("ascii"))
            elif obj_type == "Path":
                return Path(obj_value)

        return obj

    def _calculate_size(self, value: Any) -> int:
        """Calculate the size of a value in bytes.

        Args:
            value: Value to measure

        Returns:
            Size in bytes
        """
        try:
            if isinstance(value, (str, bytes)):
                return len(value.encode("utf-8") if isinstance(value, str) else value)
            else:
                return len(json.dumps(value, default=self._json_serializer).encode("utf-8"))
        except (TypeError, ValueError):
            return 0

    def _json_serializer(self, obj: Any) -> Any:
        """Custom JSON serializer for non-standard types.

        Args:
            obj: Object to serialize

        Returns:
            Serializable representation
        """
        if isinstance(obj, bytes):
            import base64

            return {"__type__": "bytes", "__value__": base64.b64encode(obj).decode("ascii")}
        elif isinstance(obj, Path):
            return {"__type__": "Path", "__value__": str(obj)}

        raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")
