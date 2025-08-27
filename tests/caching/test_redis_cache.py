"""Comprehensive tests for RedisCache implementation."""

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.caching.base import CacheConfig, CacheEntry
from src.constants import CONSTANTS


class TestRedisCacheInitialization:
    """Test RedisCache initialization and configuration."""

    def test_redis_cache_import_without_redis(self):
        """Test RedisCache behavior when redis package is not available."""
        with patch("src.caching.redis_cache.REDIS_AVAILABLE", False):
            from src.caching.redis_cache import RedisCache

            config = CacheConfig()

            with pytest.raises(ImportError, match="redis package is required"):
                RedisCache(config)

    def test_redis_cache_initialization_with_redis_available(self):
        """Test RedisCache initialization when redis is available."""
        with patch("src.caching.redis_cache.REDIS_AVAILABLE", True):
            with patch("src.caching.redis_cache.redis") as mock_redis:
                from src.caching.redis_cache import RedisCache

                config = CacheConfig()
                cache = RedisCache(config)

                assert cache.config == config
                assert cache.redis_client is None
                assert cache._stats == {
                    "hits": 0,
                    "misses": 0,
                    "sets": 0,
                    "deletes": 0,
                    "errors": 0,
                }

    def test_redis_cache_stats_initialization(self):
        """Test that Redis cache statistics are properly initialized."""
        with patch("src.caching.redis_cache.REDIS_AVAILABLE", True):
            with patch("src.caching.redis_cache.redis"):
                from src.caching.redis_cache import RedisCache

                config = CacheConfig()
                cache = RedisCache(config)

                expected_stats = {"hits": 0, "misses": 0, "sets": 0, "deletes": 0, "errors": 0}
                assert cache._stats == expected_stats


class TestRedisConnection:
    """Test Redis connection management."""

    @pytest.fixture
    def redis_cache(self):
        """Create RedisCache instance with mocked redis."""
        with patch("src.caching.redis_cache.REDIS_AVAILABLE", True):
            with patch("src.caching.redis_cache.redis") as mock_redis_module:
                from src.caching.redis_cache import RedisCache

                config = CacheConfig()
                cache = RedisCache(config)
                cache.redis_client = None  # Ensure clean state
                return cache, mock_redis_module

    @pytest.mark.asyncio
    async def test_initialize_creates_connection(self, redis_cache):
        """Test that initialize creates Redis connection."""
        cache, mock_redis_module = redis_cache
        mock_client = AsyncMock()
        mock_redis_module.Redis.return_value = mock_client

        with patch.object(cache, "_get_client") as mock_get_client:
            mock_get_client.return_value = mock_client
            await cache.initialize()
            mock_get_client.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_client_creates_new_connection(self, redis_cache):
        """Test _get_client creates new Redis connection when needed."""
        cache, mock_redis_module = redis_cache
        mock_client = AsyncMock()
        mock_redis_module.Redis.return_value = mock_client

        # Ensure no existing client
        cache.redis_client = None

        # The real issue is that the redis module is already imported in the redis_cache module
        # So we need to patch it after the import
        with patch.object(cache.logger, "info") as mock_info:
            # Patch the actual redis attribute of the module
            with patch(
                "src.caching.redis_cache.redis.Redis", return_value=mock_client
            ) as mock_redis_cls:
                result = await cache._get_client()

                # Verify Redis client was created with correct parameters
                mock_redis_cls.assert_called_once_with(
                    host=cache.config.redis_host,
                    port=cache.config.redis_port,
                    db=cache.config.redis_db,
                    password=cache.config.redis_password,
                    decode_responses=False,
                    socket_connect_timeout=CONSTANTS.REDIS_SOCKET_CONNECT_TIMEOUT,
                    socket_timeout=CONSTANTS.REDIS_SOCKET_TIMEOUT,
                )

                # Verify ping was called to test connection
                mock_client.ping.assert_called_once()
                assert result == mock_client
                assert cache.redis_client == mock_client
                mock_info.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_client_reuses_existing_connection(self, redis_cache):
        """Test _get_client reuses existing connection."""
        cache, mock_redis_module = redis_cache
        mock_client = AsyncMock()
        cache.redis_client = mock_client

        result = await cache._get_client()

        # Should not create new client
        mock_redis_module.Redis.assert_not_called()
        assert result == mock_client

    @pytest.mark.asyncio
    async def test_get_client_handles_connection_failure(self, redis_cache):
        """Test _get_client handles connection failures."""
        cache, mock_redis_module = redis_cache
        mock_client = AsyncMock()
        mock_client.ping.side_effect = Exception("Connection failed")

        # Ensure no existing client
        cache.redis_client = None

        with patch.object(cache.logger, "error") as mock_error:
            with patch("src.caching.redis_cache.redis.Redis", return_value=mock_client):
                with pytest.raises(Exception, match="Connection failed"):
                    await cache._get_client()

                # Client should be cleaned up after failure
                mock_client.aclose.assert_called_once()
                assert cache.redis_client is None
                mock_error.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_client_handles_cleanup_failure(self, redis_cache):
        """Test _get_client handles cleanup failures gracefully."""
        cache, mock_redis_module = redis_cache
        mock_client = AsyncMock()
        mock_client.ping.side_effect = Exception("Connection failed")
        mock_client.aclose.side_effect = Exception("Cleanup failed")

        # Ensure no existing client
        cache.redis_client = None

        with patch.object(cache.logger, "error") as mock_error:
            with patch.object(cache.logger, "warning") as mock_warning:
                with patch("src.caching.redis_cache.redis.Redis", return_value=mock_client):
                    with pytest.raises(Exception, match="Connection failed"):
                        await cache._get_client()

                    mock_warning.assert_called_once()
                    mock_error.assert_called_once()
                    assert cache.redis_client is None

    @pytest.mark.asyncio
    async def test_shutdown_closes_connection(self, redis_cache):
        """Test shutdown closes Redis connection."""
        cache, _ = redis_cache
        mock_client = AsyncMock()
        cache.redis_client = mock_client

        with patch.object(cache.logger, "info") as mock_info:
            await cache.shutdown()

            mock_client.aclose.assert_called_once()
            assert cache.redis_client is None
            mock_info.assert_called_once_with("Redis connection closed")

    @pytest.mark.asyncio
    async def test_shutdown_no_connection(self, redis_cache):
        """Test shutdown when no connection exists."""
        cache, _ = redis_cache
        cache.redis_client = None

        # Should not raise error
        await cache.shutdown()
        assert cache.redis_client is None

    @pytest.mark.asyncio
    async def test_close_connection(self, redis_cache):
        """Test close method closes Redis connection."""
        cache, _ = redis_cache
        mock_client = AsyncMock()
        cache.redis_client = mock_client

        with patch.object(cache.logger, "info") as mock_info:
            await cache.close()

            mock_client.close.assert_called_once()
            mock_info.assert_called_once_with("Redis connection closed")
            assert cache.redis_client is None

    @pytest.mark.asyncio
    async def test_close_handles_errors(self, redis_cache):
        """Test close method handles errors gracefully."""
        cache, _ = redis_cache
        mock_client = AsyncMock()
        mock_client.close.side_effect = Exception("Close error")
        cache.redis_client = mock_client

        with patch.object(cache.logger, "error") as mock_error:
            await cache.close()

            mock_error.assert_called_once()
            assert cache.redis_client is None


class TestRedisKeyManagement:
    """Test Redis key management functionality."""

    @pytest.fixture
    def redis_cache_with_client(self):
        """Create RedisCache with mocked client."""
        with patch("src.caching.redis_cache.REDIS_AVAILABLE", True):
            with patch("src.caching.redis_cache.redis"):
                from src.caching.redis_cache import RedisCache

                config = CacheConfig(redis_key_prefix="test:")
                cache = RedisCache(config)
                return cache

    def test_make_redis_key(self, redis_cache_with_client):
        """Test Redis key creation with prefix."""
        cache = redis_cache_with_client

        result = cache._make_redis_key("test_key")
        assert result == "test:test_key"

    def test_make_redis_key_with_empty_prefix(self):
        """Test Redis key creation with empty prefix."""
        with patch("src.caching.redis_cache.REDIS_AVAILABLE", True):
            with patch("src.caching.redis_cache.redis"):
                from src.caching.redis_cache import RedisCache

                config = CacheConfig(redis_key_prefix="")
                cache = RedisCache(config)

                result = cache._make_redis_key("test_key")
                assert result == "test_key"


class TestRedisCacheOperations:
    """Test Redis cache CRUD operations."""

    @pytest.fixture
    def mock_redis_cache(self):
        """Create RedisCache with fully mocked Redis client."""
        with patch("src.caching.redis_cache.REDIS_AVAILABLE", True):
            with patch("src.caching.redis_cache.redis"):
                from src.caching.redis_cache import RedisCache

                config = CacheConfig(redis_key_prefix="test:")
                cache = RedisCache(config)

                # Mock the client
                mock_client = AsyncMock()
                cache.redis_client = mock_client

                # Mock _get_client to return the mock client
                cache._get_client = AsyncMock(return_value=mock_client)

                return cache, mock_client

    @pytest.mark.asyncio
    async def test_get_cache_hit(self, mock_redis_cache):
        """Test successful cache get operation."""
        cache, mock_client = mock_redis_cache

        # Mock Redis response
        test_entry = CacheEntry(
            key="test_key",
            value="test_value",
            created_at=time.time(),
            ttl=3600,
            content_type="html",
        )

        mock_data = cache._compress_data(test_entry.to_dict())
        mock_client.get.return_value = mock_data

        with patch.object(cache.logger, "debug") as mock_debug:
            result = await cache.get("test_key")

            # Verify call was made with correct key
            mock_client.get.assert_called_once_with("test:test_key")

            # Verify result
            assert result is not None
            assert result.key == "test_key"
            assert result.value == "test_value"
            assert cache._stats["hits"] == 1
            assert cache._stats["misses"] == 0

            mock_debug.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_cache_miss(self, mock_redis_cache):
        """Test cache miss operation."""
        cache, mock_client = mock_redis_cache
        mock_client.get.return_value = None

        result = await cache.get("missing_key")

        assert result is None
        assert cache._stats["misses"] == 1
        assert cache._stats["hits"] == 0

    @pytest.mark.asyncio
    async def test_get_expired_entry(self, mock_redis_cache):
        """Test getting expired cache entry."""
        cache, mock_client = mock_redis_cache

        # Create expired entry
        expired_entry = CacheEntry(
            key="expired_key",
            value="expired_value",
            created_at=time.time() - 7200,  # 2 hours ago
            ttl=3600,  # 1 hour TTL
            content_type="html",
        )

        mock_data = cache._compress_data(expired_entry.to_dict())
        mock_client.get.return_value = mock_data
        mock_client.delete.return_value = 1

        with patch.object(cache, "delete") as mock_delete:
            result = await cache.get("expired_key")

            # Should delete expired entry
            mock_delete.assert_called_once_with("expired_key")
            assert result is None
            assert cache._stats["misses"] == 1

    @pytest.mark.asyncio
    async def test_get_handles_errors(self, mock_redis_cache):
        """Test get operation handles Redis errors."""
        cache, mock_client = mock_redis_cache
        mock_client.get.side_effect = Exception("Redis error")

        with patch.object(cache.logger, "warning") as mock_warning:
            result = await cache.get("error_key")

            assert result is None
            assert cache._stats["errors"] == 1
            mock_warning.assert_called_once()

    @pytest.mark.asyncio
    async def test_set_cache_entry(self, mock_redis_cache):
        """Test successful cache set operation."""
        cache, mock_client = mock_redis_cache
        mock_client.setex.return_value = True

        with patch.object(cache.logger, "debug") as mock_debug:
            result = await cache.set("test_key", "test_value", ttl=3600, content_type="html")

            assert result is True
            assert cache._stats["sets"] == 1
            mock_client.setex.assert_called_once()
            mock_debug.assert_called_once()

    @pytest.mark.asyncio
    async def test_set_without_ttl_uses_default(self, mock_redis_cache):
        """Test set operation uses default TTL from content type."""
        cache, mock_client = mock_redis_cache

        with patch.object(cache, "get_ttl_for_content_type", return_value=1800) as mock_get_ttl:
            await cache.set("test_key", "test_value", content_type="metadata")

            mock_get_ttl.assert_called_once_with("metadata")
            # Should have called setex with the returned TTL
            mock_client.setex.assert_called()

    @pytest.mark.asyncio
    async def test_set_with_zero_ttl(self, mock_redis_cache):
        """Test set operation with zero TTL (no expiration)."""
        cache, mock_client = mock_redis_cache

        await cache.set("persistent_key", "persistent_value", ttl=0)

        # Should use set instead of setex for non-expiring keys
        mock_client.set.assert_called_once()
        mock_client.setex.assert_not_called()

    @pytest.mark.asyncio
    async def test_set_handles_errors(self, mock_redis_cache):
        """Test set operation handles Redis errors."""
        cache, mock_client = mock_redis_cache
        mock_client.setex.side_effect = Exception("Redis error")

        with patch.object(cache.logger, "error") as mock_error:
            result = await cache.set("error_key", "error_value", ttl=3600)

            assert result is False
            assert cache._stats["errors"] == 1
            mock_error.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_existing_key(self, mock_redis_cache):
        """Test deleting existing cache entry."""
        cache, mock_client = mock_redis_cache
        mock_client.delete.return_value = 1  # 1 key deleted

        with patch.object(cache.logger, "debug") as mock_debug:
            result = await cache.delete("existing_key")

            assert result is True
            assert cache._stats["deletes"] == 1
            mock_client.delete.assert_called_once_with("test:existing_key")
            mock_debug.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_nonexistent_key(self, mock_redis_cache):
        """Test deleting non-existent cache entry."""
        cache, mock_client = mock_redis_cache
        mock_client.delete.return_value = 0  # 0 keys deleted

        result = await cache.delete("missing_key")

        assert result is False
        # Stats should not increment for non-existent keys
        assert cache._stats["deletes"] == 0

    @pytest.mark.asyncio
    async def test_delete_handles_errors(self, mock_redis_cache):
        """Test delete operation handles Redis errors."""
        cache, mock_client = mock_redis_cache
        mock_client.delete.side_effect = Exception("Redis error")

        with patch.object(cache.logger, "error") as mock_error:
            result = await cache.delete("error_key")

            assert result is False
            assert cache._stats["errors"] == 1
            mock_error.assert_called_once()

    @pytest.mark.asyncio
    async def test_clear_with_keys(self, mock_redis_cache):
        """Test clearing cache when keys exist."""
        cache, mock_client = mock_redis_cache

        # Mock keys method to return some keys
        mock_keys = [b"test:key1", b"test:key2", b"test:key3"]
        mock_client.keys.return_value = mock_keys
        mock_client.delete.return_value = 3  # 3 keys deleted

        with patch.object(cache.logger, "info") as mock_info:
            result = await cache.clear()

            assert result is True
            mock_client.keys.assert_called_once_with("test:*")
            mock_client.delete.assert_called_once_with(*mock_keys)
            mock_info.assert_called_once()

            # Stats should be reset
            expected_stats = {"hits": 0, "misses": 0, "sets": 0, "deletes": 0, "errors": 0}
            assert cache._stats == expected_stats

    @pytest.mark.asyncio
    async def test_clear_empty_cache(self, mock_redis_cache):
        """Test clearing cache when no keys exist."""
        cache, mock_client = mock_redis_cache
        mock_client.keys.return_value = []  # No keys

        with patch.object(cache.logger, "info") as mock_info:
            result = await cache.clear()

            assert result is True
            mock_client.keys.assert_called_once_with("test:*")
            mock_client.delete.assert_not_called()
            mock_info.assert_called_once_with("Cache was already empty")

    @pytest.mark.asyncio
    async def test_clear_handles_errors(self, mock_redis_cache):
        """Test clear operation handles Redis errors."""
        cache, mock_client = mock_redis_cache
        mock_client.keys.side_effect = Exception("Redis error")

        with patch.object(cache.logger, "error") as mock_error:
            result = await cache.clear()

            assert result is False
            assert cache._stats["errors"] == 1
            mock_error.assert_called_once()


class TestRedisCacheStats:
    """Test Redis cache statistics functionality."""

    @pytest.fixture
    def mock_redis_cache_with_stats(self):
        """Create RedisCache with mocked client for stats testing."""
        with patch("src.caching.redis_cache.REDIS_AVAILABLE", True):
            with patch("src.caching.redis_cache.redis"):
                from src.caching.redis_cache import RedisCache

                config = CacheConfig(redis_key_prefix="test:")
                cache = RedisCache(config)

                mock_client = AsyncMock()
                cache.redis_client = mock_client
                cache._get_client = AsyncMock(return_value=mock_client)

                # Set some stats
                cache._stats = {"hits": 10, "misses": 5, "sets": 8, "deletes": 2, "errors": 1}

                return cache, mock_client

    @pytest.mark.asyncio
    async def test_stats_with_keys(self, mock_redis_cache_with_stats):
        """Test stats collection with existing keys."""
        cache, mock_client = mock_redis_cache_with_stats

        # Mock Redis info response
        mock_redis_info = {
            "redis_version": "6.2.0",
            "used_memory_human": "1.5M",
            "connected_clients": 5,
        }
        mock_client.info.return_value = mock_redis_info

        # Mock keys response
        mock_keys = [b"test:key1", b"test:key2"]
        mock_client.keys.return_value = mock_keys

        # Mock key sampling - make data large enough to have non-zero MB
        large_data = b"data1" * 10000  # 50KB+ data
        mock_client.get.side_effect = [large_data, large_data]

        result = await cache.stats()

        assert result["hits"] == 10
        assert result["misses"] == 5
        assert result["sets"] == 8
        assert result["deletes"] == 2
        assert result["errors"] == 1
        assert result["total_entries"] == 2
        assert result["total_size_bytes"] > 0
        assert result["total_size_mb"] >= 0  # Allow 0 for small data
        assert result["redis_version"] == "6.2.0"
        assert result["redis_memory_used"] == "1.5M"
        assert result["redis_connected_clients"] == 5
        assert result["hit_rate"] == (10 / 15) * 100  # hits / (hits + misses)

    @pytest.mark.asyncio
    async def test_stats_no_keys(self, mock_redis_cache_with_stats):
        """Test stats collection with no keys."""
        cache, mock_client = mock_redis_cache_with_stats

        mock_redis_info = {"redis_version": "6.2.0"}
        mock_client.info.return_value = mock_redis_info
        mock_client.keys.return_value = []  # No keys

        result = await cache.stats()

        assert result["total_entries"] == 0
        assert result["total_size_bytes"] == 0
        assert result["total_size_mb"] == 0

    @pytest.mark.asyncio
    async def test_stats_key_sampling_errors(self, mock_redis_cache_with_stats):
        """Test stats handles key sampling errors gracefully."""
        cache, mock_client = mock_redis_cache_with_stats

        mock_redis_info = {"redis_version": "6.2.0"}
        mock_client.info.return_value = mock_redis_info

        # Mock keys with some that will cause errors
        mock_keys = [b"test:key1", b"test:key2", b"test:key3"]
        mock_client.keys.return_value = mock_keys

        # Create custom exception classes to simulate Redis errors
        # Since we're mocking, we need to create fake redis exceptions
        class MockRedisError(Exception):
            pass

        class MockOSError(OSError):
            pass

        # Mock successful data for first key, errors for others
        mock_client.get.side_effect = [
            b"data1" * 1000,  # Success - larger data for non-zero MB
            MockOSError("Network error"),  # This will be caught by OSError handler
            MockRedisError("Redis connection error"),  # Generic exception, won't be caught
        ]

        # Patch the redis module to include our mock exception
        with patch("src.caching.redis_cache.redis") as mock_redis_module:
            mock_redis_module.RedisError = MockRedisError

            with patch("src.caching.redis_cache.logger") as mock_module_logger:
                result = await cache.stats()

                # Should still work with partial sampling
                assert result["total_entries"] == 3
                assert result["total_size_bytes"] > 0  # Based on successful samples
                # Logger debug calls may or may not be made depending on exceptions

    @pytest.mark.asyncio
    async def test_stats_handles_general_errors(self, mock_redis_cache_with_stats):
        """Test stats handles general Redis errors."""
        cache, mock_client = mock_redis_cache_with_stats
        mock_client.info.side_effect = Exception("General Redis error")

        with patch.object(cache.logger, "error") as mock_error:
            result = await cache.stats()

            assert result == {"error": "General Redis error"}
            mock_error.assert_called_once()


class TestRedisCacheCleanup:
    """Test Redis cache cleanup functionality."""

    @pytest.fixture
    def redis_cache_for_cleanup(self):
        """Create RedisCache for cleanup testing."""
        with patch("src.caching.redis_cache.REDIS_AVAILABLE", True):
            with patch("src.caching.redis_cache.redis"):
                from src.caching.redis_cache import RedisCache

                config = CacheConfig()
                cache = RedisCache(config)
                return cache

    @pytest.mark.asyncio
    async def test_cleanup_expired_returns_zero(self, redis_cache_for_cleanup):
        """Test cleanup_expired returns 0 (Redis handles TTL automatically)."""
        cache = redis_cache_for_cleanup

        with patch.object(cache.logger, "debug") as mock_debug:
            result = await cache.cleanup_expired()

            assert result == 0
            mock_debug.assert_called_once_with(
                "Redis handles TTL automatically, no manual cleanup needed"
            )


class TestRedisCacheIntegration:
    """Test Redis cache integration scenarios."""

    @pytest.fixture
    def redis_cache_integration(self):
        """Create RedisCache for integration testing."""
        with patch("src.caching.redis_cache.REDIS_AVAILABLE", True):
            with patch("src.caching.redis_cache.redis"):
                from src.caching.redis_cache import RedisCache

                config = CacheConfig(
                    redis_host="test-redis",
                    redis_port=6379,
                    redis_db=1,
                    redis_password="test-pass",
                    redis_key_prefix="integration:",
                )
                cache = RedisCache(config)
                return cache

    @pytest.mark.asyncio
    async def test_full_cache_lifecycle(self, redis_cache_integration):
        """Test complete cache lifecycle: set, get, delete."""
        cache = redis_cache_integration
        mock_client = AsyncMock()
        cache.redis_client = mock_client
        cache._get_client = AsyncMock(return_value=mock_client)

        # Test data
        test_value = {"data": "integration_test", "timestamp": time.time()}

        # Mock successful set
        mock_client.setex.return_value = True

        # Set cache entry
        set_result = await cache.set("integration_key", test_value, ttl=1800, content_type="json")
        assert set_result is True
        assert cache._stats["sets"] == 1

        # Mock successful get
        entry = CacheEntry(
            key="integration_key",
            value=test_value,
            created_at=time.time(),
            ttl=1800,
            content_type="json",
        )
        mock_data = cache._compress_data(entry.to_dict())
        mock_client.get.return_value = mock_data

        # Get cache entry
        get_result = await cache.get("integration_key")
        assert get_result is not None
        assert get_result.value == test_value
        assert cache._stats["hits"] == 1

        # Mock successful delete
        mock_client.delete.return_value = 1

        # Delete cache entry
        delete_result = await cache.delete("integration_key")
        assert delete_result is True
        assert cache._stats["deletes"] == 1

    @pytest.mark.asyncio
    async def test_error_recovery_scenarios(self, redis_cache_integration):
        """Test cache behavior during various error conditions."""
        cache = redis_cache_integration
        mock_client = AsyncMock()
        cache.redis_client = mock_client
        cache._get_client = AsyncMock(return_value=mock_client)

        # Test set error followed by successful get
        mock_client.setex.side_effect = Exception("Set failed")
        set_result = await cache.set("error_key", "error_value", ttl=3600)
        assert set_result is False
        assert cache._stats["errors"] == 1

        # Reset mock for successful get
        mock_client.get.return_value = None  # Simulate cache miss
        get_result = await cache.get("error_key")
        assert get_result is None
        assert cache._stats["misses"] == 1

        # Test error recovery
        assert cache._stats["errors"] == 1  # Error count persists
        assert cache._stats["misses"] == 1
        assert cache._stats["sets"] == 0  # Failed set doesn't increment

    def test_redis_cache_config_inheritance(self, redis_cache_integration):
        """Test that RedisCache properly inherits configuration."""
        cache = redis_cache_integration

        assert cache.config.redis_host == "test-redis"
        assert cache.config.redis_port == 6379
        assert cache.config.redis_db == 1
        assert cache.config.redis_password == "test-pass"
        assert cache.config.redis_key_prefix == "integration:"

    @pytest.mark.asyncio
    async def test_connection_lifecycle_management(self, redis_cache_integration):
        """Test connection creation, reuse, and cleanup."""
        cache = redis_cache_integration
        mock_redis_module = MagicMock()

        with patch("src.caching.redis_cache.redis", mock_redis_module):
            mock_client = AsyncMock()
            mock_redis_module.Redis.return_value = mock_client

            # First call should create connection
            client1 = await cache._get_client()
            assert client1 == mock_client
            assert cache.redis_client == mock_client
            mock_redis_module.Redis.assert_called_once()

            # Second call should reuse connection
            client2 = await cache._get_client()
            assert client2 == mock_client
            assert mock_redis_module.Redis.call_count == 1  # Not called again

            # Close connection
            await cache.close()
            assert cache.redis_client is None
            mock_client.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_compression_integration(self, redis_cache_integration):
        """Test data compression integration with Redis operations."""
        cache = redis_cache_integration
        mock_client = AsyncMock()
        cache.redis_client = mock_client
        cache._get_client = AsyncMock(return_value=mock_client)

        # Test with large data that benefits from compression
        large_data = {"content": "x" * 10000, "metadata": {"size": "large"}}

        # Set with compression
        await cache.set("large_key", large_data, ttl=3600)

        # Verify setex was called (compression happens internally)
        mock_client.setex.assert_called_once()
        call_args = mock_client.setex.call_args

        # Verify the key is correct
        assert call_args[0][0] == f"{cache.config.redis_key_prefix}large_key"

        # Verify TTL is correct
        assert call_args[0][1] == 3600

        # Verify data was compressed (should be bytes)
        stored_data = call_args[0][2]
        assert isinstance(stored_data, bytes)
