"""Comprehensive tests for cache manager functionality."""

import time
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio

from src.caching.base import CacheBackend, CacheConfig, CacheEntry
from src.caching.manager import CacheManager


class TestCacheManagerInitialization:
    """Test cache manager initialization and backend selection."""

    @pytest.mark.asyncio
    async def test_cache_manager_default_initialization(self):
        """Test cache manager with default configuration."""
        manager = CacheManager()

        assert manager.config is not None
        assert manager.config.backend == CacheBackend.FILE
        assert manager.backend is None
        assert not manager._initialized

    @pytest.mark.asyncio
    async def test_cache_manager_custom_config_initialization(self):
        """Test cache manager with custom configuration."""
        config = CacheConfig(backend=CacheBackend.FILE, ttl_html=7200, cleanup_on_startup=False)
        manager = CacheManager(config)

        assert manager.config == config
        assert manager.config.ttl_html == 7200
        assert manager.config.cleanup_on_startup is False

    @pytest.mark.asyncio
    async def test_initialize_file_backend(self):
        """Test initialization with file backend."""
        config = CacheConfig(backend=CacheBackend.FILE)
        manager = CacheManager(config)

        with patch("src.caching.manager.FileCache") as mock_file_cache:
            mock_backend = AsyncMock()
            mock_backend.cleanup_expired = AsyncMock(return_value=0)
            mock_file_cache.return_value = mock_backend

            await manager.initialize()

            mock_file_cache.assert_called_once_with(config)
            assert manager.backend == mock_backend
            assert manager._initialized is True

    @pytest.mark.asyncio
    async def test_initialize_redis_backend_available(self):
        """Test initialization with Redis backend when available."""
        config = CacheConfig(backend=CacheBackend.REDIS)
        manager = CacheManager(config)

        with patch("src.caching.manager.REDIS_AVAILABLE", True):
            with patch("src.caching.manager.RedisCache") as mock_redis_cache:
                mock_backend = AsyncMock()
                mock_backend.initialize = AsyncMock()
                mock_backend.cleanup_expired = AsyncMock(return_value=0)
                mock_redis_cache.return_value = mock_backend

                await manager.initialize()

                mock_redis_cache.assert_called_once_with(config)
                mock_backend.initialize.assert_called_once()
                assert manager.backend == mock_backend
                assert manager._initialized is True

    @pytest.mark.asyncio
    async def test_initialize_redis_backend_unavailable(self):
        """Test initialization with Redis backend when not available."""
        config = CacheConfig(backend=CacheBackend.REDIS)
        manager = CacheManager(config)

        with patch("src.caching.manager.REDIS_AVAILABLE", False):
            with pytest.raises(
                ValueError, match="Redis backend requested but redis package not available"
            ):
                await manager.initialize()

            assert manager.backend is None
            assert manager._initialized is False

    @pytest.mark.asyncio
    async def test_initialize_unsupported_backend(self):
        """Test initialization with unsupported backend."""
        config = CacheConfig()
        # Mock an unsupported backend
        config.backend = "INVALID_BACKEND"
        manager = CacheManager(config)

        with pytest.raises(ValueError, match="Unsupported cache backend"):
            await manager.initialize()

    @pytest.mark.asyncio
    async def test_initialize_with_cleanup_on_startup(self):
        """Test initialization with cleanup on startup enabled."""
        config = CacheConfig(backend=CacheBackend.FILE, cleanup_on_startup=True)
        manager = CacheManager(config)

        with patch("src.caching.manager.FileCache") as mock_file_cache:
            mock_backend = AsyncMock()
            mock_backend.cleanup_expired = AsyncMock(return_value=5)
            mock_file_cache.return_value = mock_backend

            with patch("src.caching.manager.logger") as mock_logger:
                await manager.initialize()

                mock_backend.cleanup_expired.assert_called_once()
                mock_logger.info.assert_called()

    @pytest.mark.asyncio
    async def test_initialize_already_initialized(self):
        """Test that subsequent initialize calls are ignored."""
        config = CacheConfig(backend=CacheBackend.FILE)
        manager = CacheManager(config)

        with patch("src.caching.manager.FileCache") as mock_file_cache:
            mock_backend = AsyncMock()
            mock_backend.cleanup_expired = AsyncMock(return_value=0)
            mock_file_cache.return_value = mock_backend

            await manager.initialize()
            await manager.initialize()  # Second call should be ignored

            # FileCache should only be called once
            mock_file_cache.assert_called_once()

    @pytest.mark.asyncio
    async def test_initialize_error_handling(self):
        """Test error handling during initialization."""
        config = CacheConfig(backend=CacheBackend.FILE)
        manager = CacheManager(config)

        with patch("src.caching.manager.FileCache") as mock_file_cache:
            mock_file_cache.side_effect = Exception("Initialization failed")

            with patch("src.caching.manager.logger") as mock_logger:
                with pytest.raises(Exception, match="Initialization failed"):
                    await manager.initialize()

                mock_logger.error.assert_called_once()
                assert manager.backend is None
                assert manager._initialized is False


class TestCacheManagerHTMLOperations:
    """Test HTML caching operations."""

    @pytest_asyncio.fixture
    async def initialized_manager(self):
        """Create initialized cache manager with mock backend."""
        config = CacheConfig(backend=CacheBackend.FILE)
        manager = CacheManager(config)

        mock_backend = AsyncMock()
        mock_backend.cleanup_expired = AsyncMock(return_value=0)

        with patch("src.caching.manager.FileCache", return_value=mock_backend):
            await manager.initialize()

        return manager, mock_backend

    @pytest.mark.asyncio
    async def test_get_html_cache_hit(self, initialized_manager):
        """Test getting HTML with cache hit."""
        manager, mock_backend = initialized_manager

        test_url = "https://example.com/page"
        test_html = "<html><body>Test content</body></html>"

        mock_entry = CacheEntry(
            key="html:test_key",
            value=test_html,
            created_at=time.time(),
            ttl=3600,
            content_type="html",
        )
        mock_backend.get.return_value = mock_entry

        with patch("src.caching.manager.logger") as mock_logger:
            result = await manager.get_html(test_url)

            assert result == test_html
            mock_backend.get.assert_called_once()
            mock_logger.debug.assert_called_once_with("Cache hit for HTML", url=test_url)

    @pytest.mark.asyncio
    async def test_get_html_cache_miss(self, initialized_manager):
        """Test getting HTML with cache miss."""
        manager, mock_backend = initialized_manager

        test_url = "https://example.com/page"
        mock_backend.get.return_value = None

        result = await manager.get_html(test_url)

        assert result is None
        mock_backend.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_set_html_success(self, initialized_manager):
        """Test setting HTML cache successfully."""
        manager, mock_backend = initialized_manager

        test_url = "https://example.com/page"
        test_html = "<html><body>Test content</body></html>"
        mock_backend.set.return_value = True

        result = await manager.set_html(test_url, test_html)

        assert result is True
        mock_backend.set.assert_called_once()
        call_args = mock_backend.set.call_args
        assert call_args[0][1] == test_html  # html_content argument
        assert call_args[0][3] == "html"  # content_type argument

    @pytest.mark.asyncio
    async def test_set_html_with_custom_ttl(self, initialized_manager):
        """Test setting HTML cache with custom TTL."""
        manager, mock_backend = initialized_manager

        test_url = "https://example.com/page"
        test_html = "<html><body>Test content</body></html>"
        custom_ttl = 7200
        mock_backend.set.return_value = True

        result = await manager.set_html(test_url, test_html, ttl=custom_ttl)

        assert result is True
        mock_backend.set.assert_called_once()
        call_args = mock_backend.set.call_args
        assert call_args[0][2] == custom_ttl  # ttl argument

    @pytest.mark.asyncio
    async def test_html_operations_auto_initialize(self):
        """Test HTML operations automatically initialize manager."""
        config = CacheConfig(backend=CacheBackend.FILE)
        manager = CacheManager(config)

        mock_backend = AsyncMock()
        mock_backend.cleanup_expired = AsyncMock(return_value=0)
        mock_backend.get.return_value = None

        with patch("src.caching.manager.FileCache", return_value=mock_backend):
            # Manager should auto-initialize on first operation
            await manager.get_html("https://example.com")

            assert manager._initialized is True
            assert manager.backend == mock_backend


class TestCacheManagerImageOperations:
    """Test image caching operations."""

    @pytest_asyncio.fixture
    async def initialized_manager(self):
        """Create initialized cache manager with mock backend."""
        config = CacheConfig(backend=CacheBackend.FILE)
        manager = CacheManager(config)

        mock_backend = AsyncMock()
        mock_backend.cleanup_expired = AsyncMock(return_value=0)

        with patch("src.caching.manager.FileCache", return_value=mock_backend):
            await manager.initialize()

        return manager, mock_backend

    @pytest.mark.asyncio
    async def test_get_image_cache_hit(self, initialized_manager):
        """Test getting image with cache hit."""
        manager, mock_backend = initialized_manager

        test_url = "https://example.com/image.jpg"
        test_image_data = b"fake image data"

        mock_entry = CacheEntry(
            key="image:test_key",
            value=test_image_data,
            created_at=time.time(),
            ttl=3600,
            content_type="image",
        )
        mock_backend.get.return_value = mock_entry

        with patch("src.caching.manager.logger") as mock_logger:
            result = await manager.get_image(test_url)

            assert result == test_image_data
            mock_backend.get.assert_called_once()
            mock_logger.debug.assert_called_once_with("Cache hit for image", url=test_url)

    @pytest.mark.asyncio
    async def test_get_image_cache_miss(self, initialized_manager):
        """Test getting image with cache miss."""
        manager, mock_backend = initialized_manager

        test_url = "https://example.com/image.jpg"
        mock_backend.get.return_value = None

        result = await manager.get_image(test_url)

        assert result is None
        mock_backend.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_set_image_success(self, initialized_manager):
        """Test setting image cache successfully."""
        manager, mock_backend = initialized_manager

        test_url = "https://example.com/image.jpg"
        test_image_data = b"fake image data"
        mock_backend.set.return_value = True

        result = await manager.set_image(test_url, test_image_data)

        assert result is True
        mock_backend.set.assert_called_once()
        call_args = mock_backend.set.call_args
        assert call_args[0][1] == test_image_data  # image_data argument
        assert call_args[0][3] == "image"  # content_type argument

    @pytest.mark.asyncio
    async def test_set_image_with_custom_ttl(self, initialized_manager):
        """Test setting image cache with custom TTL."""
        manager, mock_backend = initialized_manager

        test_url = "https://example.com/image.jpg"
        test_image_data = b"fake image data"
        custom_ttl = 86400  # 1 day
        mock_backend.set.return_value = True

        result = await manager.set_image(test_url, test_image_data, ttl=custom_ttl)

        assert result is True
        mock_backend.set.assert_called_once()
        call_args = mock_backend.set.call_args
        assert call_args[0][2] == custom_ttl  # ttl argument


class TestCacheManagerMetadataOperations:
    """Test metadata caching operations."""

    @pytest_asyncio.fixture
    async def initialized_manager(self):
        """Create initialized cache manager with mock backend."""
        config = CacheConfig(backend=CacheBackend.FILE)
        manager = CacheManager(config)

        mock_backend = AsyncMock()
        mock_backend.cleanup_expired = AsyncMock(return_value=0)

        with patch("src.caching.manager.FileCache", return_value=mock_backend):
            await manager.initialize()

        return manager, mock_backend

    @pytest.mark.asyncio
    async def test_get_metadata_cache_hit(self, initialized_manager):
        """Test getting metadata with cache hit."""
        manager, mock_backend = initialized_manager

        test_url = "https://example.com/page"
        test_metadata = {"title": "Test Page", "description": "A test page"}

        mock_entry = CacheEntry(
            key="metadata:test_key",
            value=test_metadata,
            created_at=time.time(),
            ttl=3600,
            content_type="metadata",
        )
        mock_backend.get.return_value = mock_entry

        with patch("src.caching.manager.logger") as mock_logger:
            result = await manager.get_metadata(test_url)

            assert result == test_metadata
            mock_backend.get.assert_called_once()
            mock_logger.debug.assert_called_once_with("Cache hit for metadata", url=test_url)

    @pytest.mark.asyncio
    async def test_get_metadata_cache_miss(self, initialized_manager):
        """Test getting metadata with cache miss."""
        manager, mock_backend = initialized_manager

        test_url = "https://example.com/page"
        mock_backend.get.return_value = None

        result = await manager.get_metadata(test_url)

        assert result is None
        mock_backend.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_set_metadata_success(self, initialized_manager):
        """Test setting metadata cache successfully."""
        manager, mock_backend = initialized_manager

        test_url = "https://example.com/page"
        test_metadata = {"title": "Test Page", "description": "A test page"}
        mock_backend.set.return_value = True

        result = await manager.set_metadata(test_url, test_metadata)

        assert result is True
        mock_backend.set.assert_called_once()
        call_args = mock_backend.set.call_args
        assert call_args[0][1] == test_metadata  # metadata argument
        assert call_args[0][3] == "metadata"  # content_type argument

    @pytest.mark.asyncio
    async def test_set_metadata_with_custom_ttl(self, initialized_manager):
        """Test setting metadata cache with custom TTL."""
        manager, mock_backend = initialized_manager

        test_url = "https://example.com/page"
        test_metadata = {"title": "Test Page", "description": "A test page"}
        custom_ttl = 1800  # 30 minutes
        mock_backend.set.return_value = True

        result = await manager.set_metadata(test_url, test_metadata, ttl=custom_ttl)

        assert result is True
        mock_backend.set.assert_called_once()
        call_args = mock_backend.set.call_args
        assert call_args[0][2] == custom_ttl  # ttl argument


class TestCacheManagerRobotsOperations:
    """Test robots.txt caching operations."""

    @pytest_asyncio.fixture
    async def initialized_manager(self):
        """Create initialized cache manager with mock backend."""
        config = CacheConfig(backend=CacheBackend.FILE)
        manager = CacheManager(config)

        mock_backend = AsyncMock()
        mock_backend.cleanup_expired = AsyncMock(return_value=0)

        with patch("src.caching.manager.FileCache", return_value=mock_backend):
            await manager.initialize()

        return manager, mock_backend

    @pytest.mark.asyncio
    async def test_get_robots_txt_cache_hit(self, initialized_manager):
        """Test getting robots.txt with cache hit."""
        manager, mock_backend = initialized_manager

        test_domain = "example.com"
        test_robots_content = "User-agent: *\nDisallow: /admin/"

        mock_entry = CacheEntry(
            key="robots:example.com",
            value=test_robots_content,
            created_at=time.time(),
            ttl=3600,
            content_type="robots",
        )
        mock_backend.get.return_value = mock_entry

        with patch("src.caching.manager.logger") as mock_logger:
            result = await manager.get_robots_txt(test_domain)

            assert result == test_robots_content
            mock_backend.get.assert_called_once()
            mock_logger.debug.assert_called_once_with(
                "Cache hit for robots.txt", domain=test_domain
            )

    @pytest.mark.asyncio
    async def test_get_robots_txt_cache_miss(self, initialized_manager):
        """Test getting robots.txt with cache miss."""
        manager, mock_backend = initialized_manager

        test_domain = "example.com"
        mock_backend.get.return_value = None

        result = await manager.get_robots_txt(test_domain)

        assert result is None
        mock_backend.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_set_robots_txt_success(self, initialized_manager):
        """Test setting robots.txt cache successfully."""
        manager, mock_backend = initialized_manager

        test_domain = "example.com"
        test_robots_content = "User-agent: *\nDisallow: /admin/"
        mock_backend.set.return_value = True

        result = await manager.set_robots_txt(test_domain, test_robots_content)

        assert result is True
        mock_backend.set.assert_called_once()
        call_args = mock_backend.set.call_args
        assert call_args[0][1] == test_robots_content  # robots_content argument
        assert call_args[0][3] == "robots"  # content_type argument

    @pytest.mark.asyncio
    async def test_set_robots_txt_with_custom_ttl(self, initialized_manager):
        """Test setting robots.txt cache with custom TTL."""
        manager, mock_backend = initialized_manager

        test_domain = "example.com"
        test_robots_content = "User-agent: *\nDisallow: /admin/"
        custom_ttl = 43200  # 12 hours
        mock_backend.set.return_value = True

        result = await manager.set_robots_txt(test_domain, test_robots_content, ttl=custom_ttl)

        assert result is True
        mock_backend.set.assert_called_once()
        call_args = mock_backend.set.call_args
        assert call_args[0][2] == custom_ttl  # ttl argument


class TestCacheManagerUtilityOperations:
    """Test cache manager utility operations."""

    @pytest_asyncio.fixture
    async def initialized_manager(self):
        """Create initialized cache manager with mock backend."""
        config = CacheConfig(backend=CacheBackend.FILE)
        manager = CacheManager(config)

        mock_backend = AsyncMock()
        mock_backend.cleanup_expired = AsyncMock(return_value=0)

        with patch("src.caching.manager.FileCache", return_value=mock_backend):
            await manager.initialize()

        return manager, mock_backend

    @pytest.mark.asyncio
    async def test_invalidate_url_deletes_both_caches(self, initialized_manager):
        """Test invalidating URL deletes both HTML and metadata."""
        manager, mock_backend = initialized_manager

        test_url = "https://example.com/page"
        # Mock both delete calls returning True
        mock_backend.delete.return_value = True

        with patch("src.caching.manager.logger") as mock_logger:
            result = await manager.invalidate_url(test_url)

            assert result is True
            # Should call delete twice (HTML and metadata)
            assert mock_backend.delete.call_count == 2
            mock_logger.debug.assert_called_once()

    @pytest.mark.asyncio
    async def test_invalidate_url_partial_deletion(self, initialized_manager):
        """Test invalidating URL with partial deletion."""
        manager, mock_backend = initialized_manager

        test_url = "https://example.com/page"
        # Mock first delete (HTML) succeeding, second (metadata) failing
        mock_backend.delete.side_effect = [True, False]

        result = await manager.invalidate_url(test_url)

        assert result is True  # Should return True if any deletion succeeded
        assert mock_backend.delete.call_count == 2

    @pytest.mark.asyncio
    async def test_invalidate_url_no_deletions(self, initialized_manager):
        """Test invalidating URL with no deletions."""
        manager, mock_backend = initialized_manager

        test_url = "https://example.com/page"
        # Mock both delete calls returning False
        mock_backend.delete.return_value = False

        result = await manager.invalidate_url(test_url)

        assert result is False
        assert mock_backend.delete.call_count == 2

    @pytest.mark.asyncio
    async def test_get_cache_stats(self, initialized_manager):
        """Test getting cache statistics."""
        manager, mock_backend = initialized_manager

        backend_stats = {"hits": 100, "misses": 25, "total_entries": 50, "total_size_mb": 10.5}
        mock_backend.stats.return_value = backend_stats

        result = await manager.get_cache_stats()

        # Should include backend stats plus config info
        assert result["hits"] == 100
        assert result["misses"] == 25
        assert result["backend"] == "file"
        assert "config" in result
        assert result["config"]["ttl_html"] == manager.config.ttl_html
        assert result["config"]["compress"] == manager.config.compress

    @pytest.mark.asyncio
    async def test_cleanup_expired(self, initialized_manager):
        """Test cleaning up expired entries."""
        manager, mock_backend = initialized_manager

        # Reset mock to ignore initialization call
        mock_backend.cleanup_expired.reset_mock()
        mock_backend.cleanup_expired.return_value = 5

        result = await manager.cleanup_expired()

        assert result == 5
        mock_backend.cleanup_expired.assert_called_once()

    @pytest.mark.asyncio
    async def test_clear_cache(self, initialized_manager):
        """Test clearing all cache entries."""
        manager, mock_backend = initialized_manager

        mock_backend.clear.return_value = True

        result = await manager.clear_cache()

        assert result is True
        mock_backend.clear.assert_called_once()


class TestCacheManagerKeyGeneration:
    """Test cache key generation methods."""

    def test_make_html_key(self):
        """Test HTML key generation."""
        manager = CacheManager()

        with patch.object(manager, "_hash_url", return_value="abcd1234"):
            key = manager._make_html_key("https://example.com/page")
            assert key == "html:abcd1234"

    def test_make_image_key(self):
        """Test image key generation."""
        manager = CacheManager()

        with patch.object(manager, "_hash_url", return_value="efgh5678"):
            key = manager._make_image_key("https://example.com/image.jpg")
            assert key == "image:efgh5678"

    def test_make_metadata_key(self):
        """Test metadata key generation."""
        manager = CacheManager()

        with patch.object(manager, "_hash_url", return_value="ijkl9012"):
            key = manager._make_metadata_key("https://example.com/page")
            assert key == "metadata:ijkl9012"

    def test_make_robots_key(self):
        """Test robots.txt key generation."""
        manager = CacheManager()

        key = manager._make_robots_key("example.com")
        assert key == "robots:example.com"

    def test_hash_url(self):
        """Test URL hashing."""
        manager = CacheManager()

        # Mock the constants module that gets imported inside the method
        with patch("src.constants.CONSTANTS") as mock_constants:
            mock_constants.HASH_LENGTH = 8

            url = "https://example.com/page"
            hash_result = manager._hash_url(url)

            # Should be first 8 characters of SHA256 hash
            assert len(hash_result) == 8
            assert isinstance(hash_result, str)

            # Should be consistent
            hash_result2 = manager._hash_url(url)
            assert hash_result == hash_result2


class TestCacheManagerShutdown:
    """Test cache manager shutdown functionality."""

    @pytest.mark.asyncio
    async def test_shutdown_with_shutdown_method(self):
        """Test shutdown when backend has shutdown method."""
        config = CacheConfig(backend=CacheBackend.FILE)
        manager = CacheManager(config)

        mock_backend = AsyncMock()
        mock_backend.cleanup_expired = AsyncMock(return_value=0)
        mock_backend.shutdown = AsyncMock()

        with patch("src.caching.manager.FileCache", return_value=mock_backend):
            await manager.initialize()

        with patch("src.caching.manager.logger") as mock_logger:
            await manager.shutdown()

            mock_backend.shutdown.assert_called_once()
            assert manager._initialized is False
            mock_logger.info.assert_called_once_with("Cache manager shutdown")

    @pytest.mark.asyncio
    async def test_shutdown_with_close_method(self):
        """Test shutdown when backend has close method but no shutdown."""
        config = CacheConfig(backend=CacheBackend.FILE)
        manager = CacheManager(config)

        mock_backend = AsyncMock()
        mock_backend.cleanup_expired = AsyncMock(return_value=0)
        mock_backend.close = AsyncMock()
        # Remove shutdown method
        del mock_backend.shutdown

        with patch("src.caching.manager.FileCache", return_value=mock_backend):
            await manager.initialize()

        await manager.shutdown()

        mock_backend.close.assert_called_once()
        assert manager._initialized is False

    @pytest.mark.asyncio
    async def test_shutdown_no_backend(self):
        """Test shutdown when no backend is set."""
        manager = CacheManager()

        with patch("src.caching.manager.logger") as mock_logger:
            await manager.shutdown()

            mock_logger.info.assert_called_once_with("Cache manager shutdown")
            assert manager._initialized is False


class TestCacheManagerIntegration:
    """Test cache manager integration scenarios."""

    @pytest.mark.asyncio
    async def test_full_cache_lifecycle_html(self):
        """Test complete HTML cache lifecycle."""
        config = CacheConfig(backend=CacheBackend.FILE)
        manager = CacheManager(config)

        mock_backend = AsyncMock()
        mock_backend.cleanup_expired = AsyncMock(return_value=0)
        mock_backend.get.return_value = None  # Initially no cache
        mock_backend.set.return_value = True

        with patch("src.caching.manager.FileCache", return_value=mock_backend):
            test_url = "https://example.com/page"
            test_html = "<html><body>Test</body></html>"

            # First get should be cache miss
            result = await manager.get_html(test_url)
            assert result is None

            # Set content
            set_result = await manager.set_html(test_url, test_html)
            assert set_result is True

            # Mock cache hit for subsequent get
            mock_entry = CacheEntry(
                key="html:test",
                value=test_html,
                created_at=time.time(),
                ttl=3600,
                content_type="html",
            )
            mock_backend.get.return_value = mock_entry

            # Second get should be cache hit
            result = await manager.get_html(test_url)
            assert result == test_html

    @pytest.mark.asyncio
    async def test_manager_operations_without_explicit_init(self):
        """Test that operations work without explicit initialization."""
        config = CacheConfig(backend=CacheBackend.FILE)
        manager = CacheManager(config)

        mock_backend = AsyncMock()
        mock_backend.cleanup_expired = AsyncMock(return_value=0)
        mock_backend.get.return_value = None
        mock_backend.set.return_value = True
        mock_backend.stats.return_value = {"hits": 0, "misses": 0}
        mock_backend.clear.return_value = True

        with patch("src.caching.manager.FileCache", return_value=mock_backend):
            # All operations should auto-initialize
            await manager.get_html("https://example.com")
            await manager.set_html("https://example.com", "<html></html>")
            await manager.get_cache_stats()
            await manager.clear_cache()

            assert manager._initialized is True

    @pytest.mark.asyncio
    async def test_redis_backend_integration(self):
        """Test Redis backend integration."""
        config = CacheConfig(backend=CacheBackend.REDIS)
        manager = CacheManager(config)

        mock_redis_backend = AsyncMock()
        mock_redis_backend.initialize = AsyncMock()
        mock_redis_backend.cleanup_expired = AsyncMock(return_value=0)
        mock_redis_backend.get.return_value = None
        mock_redis_backend.set.return_value = True

        with patch("src.caching.manager.REDIS_AVAILABLE", True):
            with patch("src.caching.manager.RedisCache", return_value=mock_redis_backend):
                await manager.initialize()

                # Test operations
                await manager.set_html("https://example.com", "<html></html>")
                await manager.get_html("https://example.com")

                mock_redis_backend.initialize.assert_called_once()
                mock_redis_backend.set.assert_called_once()
                mock_redis_backend.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_global_cache_manager_instance(self):
        """Test the global cache manager instance."""
        from src.caching.manager import cache_manager

        # Should be a CacheManager instance
        assert isinstance(cache_manager, CacheManager)
        assert cache_manager.config is not None
        assert not cache_manager._initialized
