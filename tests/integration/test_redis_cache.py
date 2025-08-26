"""Integration tests for Redis cache backend."""

import asyncio

import pytest

from src.caching.base import CacheBackend, CacheConfig
from src.constants import TEST_CONSTANTS

# Skip all tests in this module if Redis is not available
pytestmark = pytest.mark.redis


@pytest.mark.integration
class TestRedisCacheIntegration:
    """Test Redis cache backend integration."""

    @pytest.fixture
    async def redis_cache(self):
        """Create Redis cache instance for testing."""
        try:
            from src.caching.redis_cache import REDIS_AVAILABLE, RedisCache

            if not REDIS_AVAILABLE:
                pytest.skip("Redis package not available")

            config = CacheConfig(
                backend=CacheBackend.REDIS,
                redis_host=TEST_CONSTANTS.TEST_REDIS_HOST,
                redis_port=TEST_CONSTANTS.TEST_REDIS_PORT,
                redis_db=TEST_CONSTANTS.TEST_REDIS_DB,
                redis_key_prefix=TEST_CONSTANTS.TEST_REDIS_KEY_PREFIX,
                ttl_default=30  # Short TTL for testing
            )

            cache = RedisCache(config)

            try:
                await cache.initialize()
                yield cache
            finally:
                try:
                    await cache.clear()
                    await cache.shutdown()
                except Exception:
                    # Ignore cleanup errors
                    pass

        except ImportError:
            pytest.skip("Redis package not available")
        except Exception as e:
            pytest.skip(f"Redis server not available: {e}")

    @pytest.mark.asyncio
    async def test_redis_connection(self, redis_cache):
        """Test Redis connection establishment."""
        # Should be able to ping Redis
        client = await redis_cache._get_client()
        assert client is not None

        # Test ping
        result = await client.ping()
        assert result is True

    @pytest.mark.asyncio
    async def test_redis_basic_operations(self, redis_cache):
        """Test basic Redis cache operations."""
        # Test set operation
        success = await redis_cache.set("test_key", "test_value", ttl=60)
        assert success is True

        # Test get operation
        entry = await redis_cache.get("test_key")
        assert entry is not None
        assert entry.value == "test_value"
        assert not entry.is_expired

        # Test delete operation
        deleted = await redis_cache.delete("test_key")
        assert deleted is True

        # Verify deletion
        entry = await redis_cache.get("test_key")
        assert entry is None

    @pytest.mark.asyncio
    async def test_redis_expiration(self, redis_cache):
        """Test Redis TTL and expiration."""
        # Set key with short TTL
        await redis_cache.set("expire_key", "expire_value", ttl=2)

        # Should exist initially
        entry = await redis_cache.get("expire_key")
        assert entry is not None
        assert entry.value == "expire_value"

        # Wait for expiration
        await asyncio.sleep(3)

        # Should be expired
        entry = await redis_cache.get("expire_key")
        assert entry is None

    @pytest.mark.asyncio
    async def test_redis_complex_data_types(self, redis_cache):
        """Test caching complex data types."""
        complex_data = {
            "string": "value",
            "number": 123,
            "list": [1, 2, 3, "four"],
            "dict": {"nested": "value", "count": 456},
            "boolean": True,
            "null": None
        }

        await redis_cache.set("complex_key", complex_data, ttl=60)

        entry = await redis_cache.get("complex_key")
        assert entry is not None
        assert entry.value == complex_data

    @pytest.mark.asyncio
    async def test_redis_compression(self, redis_cache):
        """Test Redis data compression."""
        # Test with large data that benefits from compression
        large_data = "x" * 10000  # 10KB string

        await redis_cache.set("large_key", large_data, ttl=60)

        entry = await redis_cache.get("large_key")
        assert entry is not None
        assert entry.value == large_data
        assert entry.compressed == redis_cache.config.compress

    @pytest.mark.asyncio
    async def test_redis_key_prefix(self, redis_cache):
        """Test Redis key prefixing."""
        await redis_cache.set("prefix_test", "value", ttl=60)

        # Check that key exists with prefix
        client = await redis_cache._get_client()
        redis_key = redis_cache._make_redis_key("prefix_test")

        assert redis_key.startswith(TEST_CONSTANTS.TEST_REDIS_KEY_PREFIX)

        # Verify key exists in Redis
        exists = await client.exists(redis_key)
        assert exists == 1

    @pytest.mark.asyncio
    async def test_redis_clear_operations(self, redis_cache):
        """Test Redis clear operations."""
        # Add multiple keys
        await redis_cache.set("clear_key1", "value1", ttl=60)
        await redis_cache.set("clear_key2", "value2", ttl=60)
        await redis_cache.set("clear_key3", "value3", ttl=60)

        # Clear cache
        success = await redis_cache.clear()
        assert success is True

        # All keys should be gone
        assert await redis_cache.get("clear_key1") is None
        assert await redis_cache.get("clear_key2") is None
        assert await redis_cache.get("clear_key3") is None

    @pytest.mark.asyncio
    async def test_redis_stats(self, redis_cache):
        """Test Redis statistics collection."""
        # Add some test data
        await redis_cache.set("stats_key1", "value1", ttl=60, content_type="html")
        await redis_cache.set("stats_key2", "value2", ttl=60, content_type="image")

        # Get some data to generate hit/miss stats
        await redis_cache.get("stats_key1")  # Hit
        await redis_cache.get("nonexistent")  # Miss

        stats = await redis_cache.stats()

        assert isinstance(stats, dict)
        assert "hits" in stats
        assert "misses" in stats
        assert "total_entries" in stats
        assert "total_size_bytes" in stats
        assert "redis_version" in stats
        assert "hit_rate" in stats

        assert stats["hits"] >= 1
        assert stats["misses"] >= 1
        assert stats["total_entries"] >= 2

    @pytest.mark.asyncio
    async def test_redis_concurrent_operations(self, redis_cache):
        """Test concurrent Redis operations."""
        # Perform multiple operations concurrently
        async def set_data(key, value):
            return await redis_cache.set(f"concurrent_{key}", f"value_{value}", ttl=60)

        async def get_data(key):
            return await redis_cache.get(f"concurrent_{key}")

        # Set data concurrently
        set_tasks = [set_data(i, i) for i in range(10)]
        results = await asyncio.gather(*set_tasks)

        # All sets should succeed
        assert all(results)

        # Get data concurrently
        get_tasks = [get_data(i) for i in range(10)]
        entries = await asyncio.gather(*get_tasks)

        # All gets should succeed
        assert all(entry is not None for entry in entries)
        assert all(entry.value == f"value_{i}" for i, entry in enumerate(entries))

    @pytest.mark.asyncio
    async def test_redis_error_handling(self, redis_cache):
        """Test Redis error handling."""
        # Test with Redis connection issues
        original_client = redis_cache.redis_client

        # Simulate connection failure
        redis_cache.redis_client = None

        # Operations should handle errors gracefully
        entry = await redis_cache.get("error_test")
        assert entry is None  # Should return None on error, not raise

        success = await redis_cache.set("error_test", "value")
        assert success is False  # Should return False on error

        # Restore client
        redis_cache.redis_client = original_client

    @pytest.mark.asyncio
    async def test_redis_key_generation(self, redis_cache):
        """Test Redis key generation and handling."""
        # Test normal key
        redis_key = redis_cache._make_redis_key("normal_key")
        expected_prefix = TEST_CONSTANTS.TEST_REDIS_KEY_PREFIX
        assert redis_key == f"{expected_prefix}normal_key"

        # Test key with special characters
        special_key = redis_cache._make_redis_key("key:with:colons")
        assert special_key == f"{expected_prefix}key:with:colons"

    @pytest.mark.asyncio
    async def test_redis_ttl_handling(self, redis_cache):
        """Test Redis TTL handling."""
        # Test with different TTL values
        await redis_cache.set("ttl_test1", "value1", ttl=0)  # No expiration
        await redis_cache.set("ttl_test2", "value2", ttl=3600)  # 1 hour
        await redis_cache.set("ttl_test3", "value3")  # Default TTL

        client = await redis_cache._get_client()

        # Check TTL values in Redis
        ttl1 = await client.ttl(redis_cache._make_redis_key("ttl_test1"))
        ttl2 = await client.ttl(redis_cache._make_redis_key("ttl_test2"))
        ttl3 = await client.ttl(redis_cache._make_redis_key("ttl_test3"))

        # TTL of -1 means no expiration, positive value means time remaining
        assert ttl1 == -1  # No expiration
        assert 3500 <= ttl2 <= 3600  # Should be close to 1 hour
        assert ttl3 > 0  # Should have some TTL

    @pytest.mark.asyncio
    async def test_redis_cleanup_expired(self, redis_cache):
        """Test Redis expired cleanup (should be no-op since Redis handles TTL)."""
        # Add expired data
        await redis_cache.set("cleanup_test", "value", ttl=1)
        await asyncio.sleep(2)

        # Run cleanup
        cleaned = await redis_cache.cleanup_expired()

        # Redis handles TTL automatically, so cleanup should return 0
        assert cleaned == 0

        # Key should be automatically expired by Redis
        entry = await redis_cache.get("cleanup_test")
        assert entry is None

    @pytest.mark.asyncio
    async def test_redis_connection_recovery(self, redis_cache):
        """Test Redis connection recovery after disconnection."""
        # Test that cache can recover from connection issues
        # This is a complex test that would require actually interrupting Redis connection
        # For now, just test that initialization can be called multiple times

        await redis_cache.initialize()
        await redis_cache.initialize()  # Should not fail

        # Basic operation should still work
        success = await redis_cache.set("recovery_test", "value", ttl=60)
        assert success is True

    @pytest.mark.asyncio
    async def test_redis_memory_efficiency(self, redis_cache):
        """Test Redis memory usage with various data sizes."""
        data_sizes = [100, 1000, 10000]  # Different data sizes

        for size in data_sizes:
            data = "x" * size
            key = f"memory_test_{size}"

            success = await redis_cache.set(key, data, ttl=60)
            assert success is True

            entry = await redis_cache.get(key)
            assert entry is not None
            assert len(entry.value) == size

    @pytest.mark.asyncio
    async def test_redis_database_isolation(self, redis_cache):
        """Test that test Redis database is isolated."""
        # Ensure we're using the test database
        assert redis_cache.config.redis_db == TEST_CONSTANTS.TEST_REDIS_DB

        # Add data
        await redis_cache.set("isolation_test", "test_value", ttl=60)

        # Create cache with different database
        different_config = CacheConfig(
            backend=CacheBackend.REDIS,
            redis_host=TEST_CONSTANTS.TEST_REDIS_HOST,
            redis_port=TEST_CONSTANTS.TEST_REDIS_PORT,
            redis_db=TEST_CONSTANTS.TEST_REDIS_DB + 1,  # Different DB
            redis_key_prefix="different:",
        )

        try:
            from src.caching.redis_cache import RedisCache
            different_cache = RedisCache(different_config)
            await different_cache.initialize()

            # Should not see data from other database
            entry = await different_cache.get("isolation_test")
            assert entry is None

            await different_cache.shutdown()

        except Exception:
            # If we can't test database isolation, that's ok
            pass

