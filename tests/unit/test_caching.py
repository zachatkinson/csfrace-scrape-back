"""Tests for caching functionality."""

import asyncio
import time
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from src.caching.base import CacheBackend, CacheConfig, CacheEntry
from src.caching.file_cache import FileCache
from src.caching.manager import CacheManager


class TestCacheConfig:
    """Test CacheConfig dataclass."""

    def test_default_config(self):
        """Test default cache configuration."""
        config = CacheConfig()

        assert config.backend == CacheBackend.FILE
        assert config.ttl_default == 3600
        assert config.ttl_html == 1800
        assert config.ttl_images == 86400
        assert config.ttl_metadata == 3600
        assert config.ttl_robots == 86400
        assert config.cache_dir == Path(".cache")
        assert config.max_cache_size_mb == 1000
        assert config.compress is True
        assert config.cleanup_on_startup is True

    def test_custom_config(self):
        """Test custom cache configuration."""
        config = CacheConfig(
            backend=CacheBackend.REDIS,
            ttl_html=3600,
            redis_host="custom-redis.example.com",
            redis_port=6380,
            compress=False,
        )

        assert config.backend == CacheBackend.REDIS
        assert config.ttl_html == 3600
        assert config.redis_host == "custom-redis.example.com"
        assert config.redis_port == 6380
        assert config.compress is False


class TestCacheEntry:
    """Test CacheEntry functionality."""

    def test_cache_entry_creation(self):
        """Test cache entry creation."""
        entry = CacheEntry(key="test:key", value="test value", created_at=1000.0, ttl=3600)

        assert entry.key == "test:key"
        assert entry.value == "test value"
        assert entry.created_at == 1000.0
        assert entry.ttl == 3600
        assert entry.content_type == "generic"
        assert entry.size_bytes == 0
        assert not entry.compressed

    def test_expiration_check(self):
        """Test cache entry expiration logic."""
        current_time = time.time()

        # Non-expired entry
        entry = CacheEntry(
            key="test",
            value="value",
            created_at=current_time - 1000,  # 1000 seconds ago
            ttl=3600,  # 1 hour TTL
        )
        assert not entry.is_expired

        # Expired entry
        expired_entry = CacheEntry(
            key="test",
            value="value",
            created_at=current_time - 4000,  # 4000 seconds ago
            ttl=3600,  # 1 hour TTL
        )
        assert expired_entry.is_expired

        # No expiration (TTL <= 0)
        no_expire_entry = CacheEntry(
            key="test",
            value="value",
            created_at=current_time - 10000,  # Very old
            ttl=0,  # No expiration
        )
        assert not no_expire_entry.is_expired

    def test_age_calculation(self):
        """Test cache entry age calculation."""
        current_time = time.time()
        entry = CacheEntry(
            key="test", value="value", created_at=current_time - 100, ttl=3600  # 100 seconds ago
        )

        age = entry.age_seconds
        assert 99 <= age <= 101  # Allow small time variance

    def test_serialization(self):
        """Test cache entry serialization and deserialization."""
        entry = CacheEntry(
            key="test:key",
            value={"nested": "data"},
            created_at=1000.0,
            ttl=3600,
            content_type="json",
            size_bytes=50,
            compressed=True,
        )

        # Test to_dict
        entry_dict = entry.to_dict()
        expected_keys = {
            "key",
            "value",
            "created_at",
            "ttl",
            "content_type",
            "size_bytes",
            "compressed",
        }
        assert set(entry_dict.keys()) == expected_keys
        assert entry_dict["key"] == "test:key"
        assert entry_dict["value"] == {"nested": "data"}

        # Test from_dict
        reconstructed = CacheEntry.from_dict(entry_dict)
        assert reconstructed.key == entry.key
        assert reconstructed.value == entry.value
        assert reconstructed.created_at == entry.created_at
        assert reconstructed.ttl == entry.ttl
        assert reconstructed.content_type == entry.content_type
        assert reconstructed.size_bytes == entry.size_bytes
        assert reconstructed.compressed == entry.compressed


class TestFileCache:
    """Test FileCache functionality."""

    @pytest.fixture
    def temp_dir(self):
        """Provide temporary directory for tests."""
        with TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)

    @pytest.fixture
    def cache_config(self, temp_dir):
        """Provide cache configuration for testing."""
        return CacheConfig(
            backend=CacheBackend.FILE,
            cache_dir=temp_dir / "cache",
            ttl_default=3600,
            compress=True,
            max_cache_size_mb=10,  # Small limit for testing
        )

    @pytest.fixture
    def file_cache(self, cache_config):
        """Provide FileCache instance."""
        return FileCache(cache_config)

    @pytest.mark.asyncio
    async def test_cache_directories_created(self, file_cache):
        """Test that cache directories are created on initialization."""
        assert file_cache.cache_dir.exists()
        assert file_cache.html_dir.exists()
        assert file_cache.image_dir.exists()
        assert file_cache.metadata_dir.exists()
        assert file_cache.robots_dir.exists()
        assert file_cache.generic_dir.exists()

    @pytest.mark.asyncio
    async def test_set_and_get_basic(self, file_cache):
        """Test basic cache set and get operations."""
        key = "test:key"
        value = "test value"

        # Set value
        success = await file_cache.set(key, value, ttl=3600, content_type="html")
        assert success

        # Get value
        entry = await file_cache.get(key)
        assert entry is not None
        assert entry.key == key
        assert entry.value == value
        assert entry.content_type == "html"
        assert entry.ttl == 3600
        assert not entry.is_expired

    @pytest.mark.asyncio
    async def test_get_nonexistent_key(self, file_cache):
        """Test getting non-existent cache key."""
        entry = await file_cache.get("nonexistent:key")
        assert entry is None

    @pytest.mark.asyncio
    async def test_cache_expiration(self, file_cache):
        """Test cache expiration behavior."""
        key = "expire:test"
        value = "will expire"

        # Set with very short TTL
        await file_cache.set(key, value, ttl=1, content_type="generic")

        # Should exist immediately
        entry = await file_cache.get(key)
        assert entry is not None
        assert entry.value == value

        # Wait for expiration
        await asyncio.sleep(1.1)

        # Should be expired and deleted
        entry = await file_cache.get(key)
        assert entry is None

    @pytest.mark.asyncio
    async def test_delete_entry(self, file_cache):
        """Test cache entry deletion."""
        key = "delete:test"
        value = "to be deleted"

        # Set value
        await file_cache.set(key, value)

        # Verify it exists
        entry = await file_cache.get(key)
        assert entry is not None

        # Delete it
        deleted = await file_cache.delete(key)
        assert deleted

        # Verify it's gone
        entry = await file_cache.get(key)
        assert entry is None

        # Delete non-existent key
        deleted = await file_cache.delete("nonexistent")
        assert not deleted

    @pytest.mark.asyncio
    async def test_clear_cache(self, file_cache):
        """Test clearing all cache entries."""
        # Set multiple values
        await file_cache.set("key1", "value1", content_type="html")
        await file_cache.set("key2", "value2", content_type="image")
        await file_cache.set("key3", "value3", content_type="metadata")

        # Verify they exist
        assert await file_cache.get("key1") is not None
        assert await file_cache.get("key2") is not None
        assert await file_cache.get("key3") is not None

        # Clear cache
        success = await file_cache.clear()
        assert success

        # Verify all are gone
        assert await file_cache.get("key1") is None
        assert await file_cache.get("key2") is None
        assert await file_cache.get("key3") is None

    @pytest.mark.asyncio
    async def test_cache_stats(self, file_cache):
        """Test cache statistics."""
        # Initially empty
        stats = await file_cache.stats()
        assert stats["total_entries"] == 0
        assert stats["total_size_bytes"] == 0

        # Add some entries
        await file_cache.set("key1", "value1", content_type="html")
        await file_cache.set("key2", "larger value content", content_type="image")

        stats = await file_cache.stats()
        assert stats["total_entries"] == 2
        assert stats["total_size_bytes"] > 0
        assert stats["total_size_mb"] >= 0
        assert "hit_rate" in stats
        assert "cache_dir" in stats

    @pytest.mark.asyncio
    async def test_cleanup_expired(self, file_cache):
        """Test cleanup of expired entries."""
        # Set entries with different TTLs
        await file_cache.set("short", "expires soon", ttl=1)
        await file_cache.set("long", "expires later", ttl=3600)

        # Wait for short TTL to expire
        await asyncio.sleep(1.1)

        # Cleanup expired entries
        cleaned = await file_cache.cleanup_expired()
        assert cleaned >= 1  # At least the short TTL entry

        # Verify short TTL entry is gone, long TTL remains
        assert await file_cache.get("short") is None
        assert await file_cache.get("long") is not None

    @pytest.mark.asyncio
    async def test_content_type_directories(self, file_cache):
        """Test that different content types use different directories."""
        await file_cache.set("html_key", "html content", content_type="html")
        await file_cache.set("image_key", b"image data", content_type="image")
        await file_cache.set("meta_key", {"title": "test"}, content_type="metadata")

        # Check files were created in correct directories
        assert len(list(file_cache.html_dir.glob("*.cache"))) == 1
        assert len(list(file_cache.image_dir.glob("*.cache"))) == 1
        assert len(list(file_cache.metadata_dir.glob("*.cache"))) == 1


class TestCacheManager:
    """Test CacheManager functionality."""

    @pytest.fixture
    def temp_dir(self):
        """Provide temporary directory for tests."""
        with TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)

    @pytest.fixture
    def cache_config(self, temp_dir):
        """Provide cache configuration for testing."""
        return CacheConfig(
            backend=CacheBackend.FILE,
            cache_dir=temp_dir / "cache",
            ttl_html=1800,
            ttl_images=86400,
            ttl_metadata=3600,
        )

    @pytest.fixture
    async def cache_manager(self, cache_config):
        """Provide initialized CacheManager instance."""
        manager = CacheManager(cache_config)
        await manager.initialize()
        return manager

    @pytest.mark.asyncio
    async def test_manager_initialization(self, cache_config):
        """Test cache manager initialization."""
        manager = CacheManager(cache_config)
        assert not manager._initialized

        await manager.initialize()
        assert manager._initialized
        assert manager.backend is not None
        assert isinstance(manager.backend, FileCache)

    @pytest.mark.asyncio
    async def test_html_caching(self, cache_manager):
        """Test HTML content caching."""
        url = "https://example.com/test"
        html_content = "<html><body>Test</body></html>"

        # Cache HTML
        success = await cache_manager.set_html(url, html_content)
        assert success

        # Retrieve HTML
        cached_html = await cache_manager.get_html(url)
        assert cached_html == html_content

        # Test cache miss
        missing_html = await cache_manager.get_html("https://nonexistent.com")
        assert missing_html is None

    @pytest.mark.asyncio
    async def test_image_caching(self, cache_manager):
        """Test image data caching."""
        image_url = "https://example.com/image.jpg"
        image_data = b"fake image binary data"

        # Cache image
        success = await cache_manager.set_image(image_url, image_data)
        assert success

        # Retrieve image
        cached_image = await cache_manager.get_image(image_url)
        assert cached_image == image_data

    @pytest.mark.asyncio
    async def test_metadata_caching(self, cache_manager):
        """Test metadata caching."""
        url = "https://example.com/post"
        metadata = {"title": "Test Post", "description": "A test post", "tags": ["test", "example"]}

        # Cache metadata
        success = await cache_manager.set_metadata(url, metadata)
        assert success

        # Retrieve metadata
        cached_metadata = await cache_manager.get_metadata(url)
        assert cached_metadata == metadata

    @pytest.mark.asyncio
    async def test_robots_txt_caching(self, cache_manager):
        """Test robots.txt caching."""
        domain = "example.com"
        robots_content = "User-agent: *\nDisallow: /admin/"

        # Cache robots.txt
        success = await cache_manager.set_robots_txt(domain, robots_content)
        assert success

        # Retrieve robots.txt
        cached_robots = await cache_manager.get_robots_txt(domain)
        assert cached_robots == robots_content

    @pytest.mark.asyncio
    async def test_url_invalidation(self, cache_manager):
        """Test invalidating all cached data for a URL."""
        url = "https://example.com/test"

        # Cache HTML and metadata for URL
        await cache_manager.set_html(url, "<html>Test</html>")
        await cache_manager.set_metadata(url, {"title": "Test"})

        # Verify cached
        assert await cache_manager.get_html(url) is not None
        assert await cache_manager.get_metadata(url) is not None

        # Invalidate URL
        invalidated = await cache_manager.invalidate_url(url)
        assert invalidated

        # Verify invalidated
        assert await cache_manager.get_html(url) is None
        assert await cache_manager.get_metadata(url) is None

    @pytest.mark.asyncio
    async def test_cache_stats(self, cache_manager):
        """Test cache statistics retrieval."""
        # Add some cached data
        await cache_manager.set_html("https://example.com/1", "<html>1</html>")
        await cache_manager.set_html("https://example.com/2", "<html>2</html>")
        await cache_manager.set_metadata("https://example.com/1", {"title": "1"})

        stats = await cache_manager.get_cache_stats()

        assert "backend" in stats
        assert stats["backend"] == "file"
        assert "total_entries" in stats
        assert stats["total_entries"] >= 3
        assert "config" in stats
        assert stats["config"]["ttl_html"] == 1800

    @pytest.mark.asyncio
    async def test_cleanup_expired(self, cache_manager):
        """Test cleanup of expired entries."""
        # Set entries with short TTL
        await cache_manager.set_html("https://example.com/expire", "<html>Expire</html>", ttl=1)
        await cache_manager.set_html("https://example.com/keep", "<html>Keep</html>", ttl=3600)

        # Wait for expiration
        await asyncio.sleep(1.1)

        # Cleanup
        cleaned = await cache_manager.cleanup_expired()
        assert cleaned >= 1

        # Verify cleanup worked
        assert await cache_manager.get_html("https://example.com/expire") is None
        assert await cache_manager.get_html("https://example.com/keep") is not None

    @pytest.mark.asyncio
    async def test_clear_cache(self, cache_manager):
        """Test clearing entire cache."""
        # Add some data
        await cache_manager.set_html("https://example.com/1", "<html>1</html>")
        await cache_manager.set_metadata("https://example.com/1", {"title": "1"})

        # Clear cache
        success = await cache_manager.clear_cache()
        assert success

        # Verify cleared
        assert await cache_manager.get_html("https://example.com/1") is None
        assert await cache_manager.get_metadata("https://example.com/1") is None

    @pytest.mark.asyncio
    async def test_key_generation(self, cache_manager):
        """Test cache key generation methods."""
        url = "https://example.com/test"

        html_key = cache_manager._make_html_key(url)
        image_key = cache_manager._make_image_key(url)
        metadata_key = cache_manager._make_metadata_key(url)
        robots_key = cache_manager._make_robots_key("example.com")

        assert html_key.startswith("html:")
        assert image_key.startswith("image:")
        assert metadata_key.startswith("metadata:")
        assert robots_key.startswith("robots:")

        # Keys for same URL should be consistent
        assert cache_manager._make_html_key(url) == html_key

        # Keys for different URLs should be different
        different_url = "https://different.com/test"
        assert cache_manager._make_html_key(different_url) != html_key

    @pytest.mark.asyncio
    async def test_auto_initialization(self, cache_config):
        """Test that manager auto-initializes when needed."""
        manager = CacheManager(cache_config)
        assert not manager._initialized

        # First operation should trigger initialization
        await manager.set_html("https://example.com", "<html>Test</html>")
        assert manager._initialized

    def test_default_configuration(self):
        """Test manager with default configuration."""
        manager = CacheManager()
        assert manager.config.backend == CacheBackend.FILE
        assert manager.config.cache_dir == Path(".cache")
