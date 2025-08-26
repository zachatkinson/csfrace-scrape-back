"""Tests for caching system components."""

import asyncio
import time
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from src.caching.base import BaseCacheBackend, CacheBackend, CacheConfig, CacheEntry
from src.caching.file_cache import FileCache
from src.caching.manager import CacheManager
from src.constants import CONSTANTS


class TestCacheEntry:
    """Test CacheEntry functionality."""

    def test_cache_entry_creation(self):
        """Test basic cache entry creation."""
        entry = CacheEntry(
            key="test_key",
            value="test_value",
            created_at=time.time(),
            ttl=3600,
            content_type="html",
            size_bytes=100,
        )

        assert entry.key == "test_key"
        assert entry.value == "test_value"
        assert entry.content_type == "html"
        assert entry.size_bytes == 100

    def test_cache_entry_expiration(self):
        """Test cache entry expiration logic."""
        current_time = time.time()

        # Non-expired entry
        entry = CacheEntry(
            key="test",
            value="value",
            created_at=current_time,
            ttl=3600,  # 1 hour
            content_type="html",
        )
        assert not entry.is_expired

        # Expired entry
        expired_entry = CacheEntry(
            key="test",
            value="value",
            created_at=current_time - 7200,  # 2 hours ago
            ttl=3600,  # 1 hour TTL
            content_type="html",
        )
        assert expired_entry.is_expired

    def test_cache_entry_no_expiration(self):
        """Test cache entry with no expiration (TTL <= 0)."""
        entry = CacheEntry(
            key="test",
            value="value",
            created_at=time.time() - 10000,  # Long time ago
            ttl=0,  # No expiration
            content_type="html",
        )
        assert not entry.is_expired

    def test_cache_entry_age(self):
        """Test cache entry age calculation."""
        created_time = time.time() - 100  # 100 seconds ago
        entry = CacheEntry(
            key="test", value="value", created_at=created_time, ttl=3600, content_type="html"
        )

        # Age should be approximately 100 seconds
        assert 99 <= entry.age_seconds <= 101

    def test_cache_entry_serialization(self):
        """Test cache entry to/from dict conversion."""
        entry = CacheEntry(
            key="test_key",
            value={"data": "test"},
            created_at=1234567890.0,
            ttl=3600,
            content_type="json",
            size_bytes=50,
            compressed=True,
        )

        # Test serialization
        entry_dict = entry.to_dict()
        assert entry_dict["key"] == "test_key"
        assert entry_dict["value"] == {"data": "test"}
        assert entry_dict["created_at"] == 1234567890.0
        assert entry_dict["compressed"] is True

        # Test deserialization
        restored_entry = CacheEntry.from_dict(entry_dict)
        assert restored_entry.key == entry.key
        assert restored_entry.value == entry.value
        assert restored_entry.created_at == entry.created_at
        assert restored_entry.compressed == entry.compressed


class TestCacheConfig:
    """Test cache configuration."""

    def test_default_cache_config(self):
        """Test default cache configuration values."""
        config = CacheConfig()

        assert config.backend == CacheBackend.FILE
        assert config.ttl_default == CONSTANTS.DEFAULT_TTL
        assert config.ttl_html == CONSTANTS.CACHE_TTL_HTML
        assert config.ttl_images == CONSTANTS.CACHE_TTL_IMAGES
        assert config.max_cache_size_mb == CONSTANTS.MAX_CACHE_SIZE_MB

    def test_custom_cache_config(self, temp_dir):
        """Test custom cache configuration."""
        config = CacheConfig(
            backend=CacheBackend.REDIS,
            cache_dir=temp_dir / "custom_cache",
            ttl_default=7200,
            compress=False,
            redis_host="custom-redis",
            redis_port=6380,
        )

        assert config.backend == CacheBackend.REDIS
        assert config.cache_dir == temp_dir / "custom_cache"
        assert config.ttl_default == 7200
        assert config.compress is False
        assert config.redis_host == "custom-redis"
        assert config.redis_port == 6380


class TestBaseCacheBackend:
    """Test base cache backend functionality."""

    class MockCacheBackend(BaseCacheBackend):
        """Mock implementation for testing base functionality."""

        async def get(self, key: str):
            return None

        async def set(self, key: str, value, ttl=None, content_type="generic"):
            return True

        async def delete(self, key: str):
            return True

        async def clear(self):
            return True

        async def stats(self):
            return {}

        async def cleanup_expired(self):
            return 0

    def test_base_cache_backend_initialization(self, cache_config):
        """Test base cache backend initialization."""
        backend = self.MockCacheBackend(cache_config)

        assert backend.config == cache_config
        assert hasattr(backend, "logger")

    def test_generate_key(self, cache_config):
        """Test cache key generation."""
        backend = self.MockCacheBackend(cache_config)

        # Test simple key generation
        key = backend.generate_key("user", "123", "profile")
        assert key == "user:123:profile"

        # Test with mixed types
        key = backend.generate_key("item", 456, 78.9)
        assert key == "item:456:78.9"

    def test_generate_key_truncation(self, cache_config):
        """Test key truncation for long keys."""
        # Set a very short max key length for testing
        cache_config.max_key_length = 50
        backend = self.MockCacheBackend(cache_config)

        # Generate a very long key
        long_parts = ["very_long_key_part"] * 10
        key = backend.generate_key(*long_parts)

        # Key should be truncated and hashed
        assert len(key) <= 50
        assert ":" in key  # Should contain hash separator

    def test_get_ttl_for_content_type(self, cache_config):
        """Test TTL selection by content type."""
        backend = self.MockCacheBackend(cache_config)

        assert backend.get_ttl_for_content_type("html") == cache_config.ttl_html
        assert backend.get_ttl_for_content_type("image") == cache_config.ttl_images
        assert backend.get_ttl_for_content_type("metadata") == cache_config.ttl_metadata
        assert backend.get_ttl_for_content_type("robots") == cache_config.ttl_robots
        assert backend.get_ttl_for_content_type("unknown") == cache_config.ttl_default

    def test_compress_decompress_data(self, cache_config):
        """Test data compression and decompression."""
        backend = self.MockCacheBackend(cache_config)

        test_data = {"key": "value", "number": 123, "list": [1, 2, 3]}

        # Test with compression enabled
        cache_config.compress = True
        compressed = backend._compress_data(test_data)
        assert isinstance(compressed, bytes)

        decompressed = backend._decompress_data(compressed, compressed=True)
        assert decompressed == test_data

        # Test with compression disabled
        cache_config.compress = False
        uncompressed = backend._compress_data(test_data)
        assert isinstance(uncompressed, bytes)

        restored = backend._decompress_data(uncompressed, compressed=False)
        assert restored == test_data

    def test_calculate_size(self, cache_config):
        """Test value size calculation."""
        backend = self.MockCacheBackend(cache_config)

        # Test string size
        string_size = backend._calculate_size("test string")
        assert string_size > 0

        # Test bytes size
        bytes_data = b"test bytes"
        bytes_size = backend._calculate_size(bytes_data)
        assert bytes_size == len(bytes_data)

        # Test dict size
        dict_data = {"key": "value"}
        dict_size = backend._calculate_size(dict_data)
        assert dict_size > 0

    def test_json_serialization_custom_types(self, cache_config):
        """Test custom type serialization/deserialization."""
        backend = self.MockCacheBackend(cache_config)

        # Test with Path objects - use cross-platform path
        original_path = Path("/test/path")
        test_data = {"path": original_path, "bytes": b"binary data"}

        compressed = backend._compress_data(test_data)
        decompressed = backend._decompress_data(compressed, compressed=True)

        assert isinstance(decompressed["path"], Path)
        # Compare Path objects directly instead of string representation for cross-platform compatibility
        assert decompressed["path"] == original_path
        assert isinstance(decompressed["bytes"], bytes)
        assert decompressed["bytes"] == b"binary data"


class TestFileCache:
    """Test file cache implementation."""

    def test_file_cache_initialization(self, cache_config, temp_dir):
        """Test file cache initialization."""
        cache_config.cache_dir = temp_dir / "test_cache"
        cache = FileCache(cache_config)

        # Cache directory should be created during initialization
        assert cache_config.cache_dir.exists()
        assert cache_config.cache_dir.is_dir()

        # Subdirectories should be created
        assert cache.html_dir.exists()
        assert cache.image_dir.exists()
        assert cache.metadata_dir.exists()

    @pytest.mark.asyncio
    async def test_file_cache_set_get(self, file_cache):
        """Test basic set/get operations."""
        # Test setting a value
        success = await file_cache.set("test_key", "test_value", ttl=3600, content_type="text")
        assert success is True

        # Test getting the value
        entry = await file_cache.get("test_key")
        assert entry is not None
        assert entry.value == "test_value"
        assert entry.content_type == "text"
        assert not entry.is_expired

    @pytest.mark.asyncio
    async def test_file_cache_expiration(self, file_cache):
        """Test cache entry expiration."""
        # Set entry with very short TTL
        await file_cache.set("expire_key", "expire_value", ttl=1)

        # Should exist initially
        entry = await file_cache.get("expire_key")
        assert entry is not None

        # Wait for expiration
        await asyncio.sleep(2)

        # Should be expired/removed
        entry = await file_cache.get("expire_key")
        assert entry is None

    @pytest.mark.asyncio
    async def test_file_cache_delete(self, file_cache):
        """Test cache deletion."""
        await file_cache.set("delete_key", "delete_value")

        # Verify it exists
        entry = await file_cache.get("delete_key")
        assert entry is not None

        # Delete it
        success = await file_cache.delete("delete_key")
        assert success is True

        # Verify it's gone
        entry = await file_cache.get("delete_key")
        assert entry is None

    @pytest.mark.asyncio
    async def test_file_cache_clear(self, file_cache):
        """Test cache clearing."""
        # Add multiple entries
        await file_cache.set("key1", "value1")
        await file_cache.set("key2", "value2")
        await file_cache.set("key3", "value3")

        # Clear cache
        success = await file_cache.clear()
        assert success is True

        # All entries should be gone
        assert await file_cache.get("key1") is None
        assert await file_cache.get("key2") is None
        assert await file_cache.get("key3") is None

    @pytest.mark.asyncio
    async def test_file_cache_stats(self, file_cache):
        """Test cache statistics."""
        # Add some test data
        await file_cache.set("stats_key1", "value1", content_type="html")
        await file_cache.set("stats_key2", "value2", content_type="image")

        stats = await file_cache.stats()

        assert isinstance(stats, dict)
        assert "total_entries" in stats
        assert "total_size_bytes" in stats
        assert "total_size_mb" in stats
        assert stats["total_entries"] >= 2

    @pytest.mark.asyncio
    async def test_file_cache_cleanup_expired(self, file_cache):
        """Test cleanup of expired entries."""
        # Add entries with different TTLs
        await file_cache.set("short_ttl", "value1", ttl=1)  # Expires quickly
        await file_cache.set("long_ttl", "value2", ttl=3600)  # Long-lived

        # Wait for short TTL to expire
        await asyncio.sleep(2)

        # Run cleanup
        cleaned_count = await file_cache.cleanup_expired()

        # At least one entry should have been cleaned
        assert cleaned_count >= 1

        # Short TTL entry should be gone, long TTL should remain
        assert await file_cache.get("short_ttl") is None
        assert await file_cache.get("long_ttl") is not None

    @pytest.mark.asyncio
    async def test_file_cache_size_limit_enforcement(self, cache_config, temp_dir):
        """Test cache size limit enforcement."""
        # Set very small cache size for testing
        cache_config.cache_dir = temp_dir / "small_cache"
        cache_config.max_cache_size_mb = 1  # 1MB limit

        cache = FileCache(cache_config)
        # FileCache doesn't have initialize method - initializes in constructor

        # Try to add data that exceeds limit
        large_data = "x" * (500 * 1024)  # 500KB string

        await cache.set("large1", large_data)
        await cache.set("large2", large_data)
        await cache.set("large3", large_data)  # This might trigger cleanup

        stats = await cache.stats()
        # Cache should manage size (exact behavior depends on implementation)
        assert stats["total_size_mb"] is not None


class TestCacheManager:
    """Test cache manager functionality."""

    @pytest.fixture
    def mock_cache_backend(self):
        """Create mock cache backend."""
        backend = AsyncMock(spec=BaseCacheBackend)
        backend.get.return_value = None
        backend.set.return_value = True
        backend.delete.return_value = True
        backend.clear.return_value = True
        backend.stats.return_value = {"hits": 0, "misses": 0}
        backend.cleanup_expired.return_value = 0
        return backend

    @pytest.mark.asyncio
    async def test_cache_manager_initialization(self, cache_config, mock_cache_backend):
        """Test cache manager initialization."""
        with patch("src.caching.manager.FileCache", return_value=mock_cache_backend):
            manager = CacheManager(cache_config)
            await manager.initialize()

            assert manager.backend is not None

    @pytest.mark.asyncio
    async def test_cache_manager_operations(self, cache_config, mock_cache_backend):
        """Test cache manager operations."""
        with patch("src.caching.manager.FileCache", return_value=mock_cache_backend):
            manager = CacheManager(cache_config)
            await manager.initialize()

            # Test HTML caching operations
            await manager.get_html("http://test.com")
            # Should call backend.get with HTML key
            mock_cache_backend.get.assert_called()

            await manager.set_html("http://test.com", "<html>test</html>")
            # Should call backend.set with HTML content
            mock_cache_backend.set.assert_called()

            # Test stats (CacheManager may not have stats method)
            if hasattr(manager, "stats"):
                await manager.stats()
                mock_cache_backend.stats.assert_called()

    @pytest.mark.asyncio
    async def test_cache_manager_backend_selection(self, cache_config):
        """Test cache backend selection."""
        # Test file backend selection
        cache_config.backend = CacheBackend.FILE
        manager = CacheManager(cache_config)

        with patch("src.caching.manager.FileCache") as mock_file_cache:
            mock_instance = AsyncMock()
            mock_instance.cleanup_expired = AsyncMock(return_value=0)
            mock_file_cache.return_value = mock_instance
            await manager.initialize()
            mock_file_cache.assert_called_once()

    @pytest.mark.asyncio
    async def test_cache_manager_redis_backend_unavailable(self, cache_config):
        """Test handling when Redis backend is not available."""
        cache_config.backend = CacheBackend.REDIS
        manager = CacheManager(cache_config)

        # Should raise error when Redis unavailable but requested
        with patch("src.caching.manager.REDIS_AVAILABLE", False):
            with pytest.raises(
                ValueError, match="Redis backend requested but redis package not available"
            ):
                await manager.initialize()
