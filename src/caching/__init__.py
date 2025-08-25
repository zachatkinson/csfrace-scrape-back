"""Caching layer for improved performance and reduced HTTP requests."""

from .base import CacheBackend, CacheEntry, CacheConfig
from .file_cache import FileCache
from .manager import CacheManager

# Import Redis cache only if available
try:
    from .redis_cache import RedisCache
    __all__ = ['CacheBackend', 'CacheEntry', 'CacheConfig', 'FileCache', 'RedisCache', 'CacheManager']
except ImportError:
    __all__ = ['CacheBackend', 'CacheEntry', 'CacheConfig', 'FileCache', 'CacheManager']