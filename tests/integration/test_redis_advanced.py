"""Advanced Redis testing following best practices."""

import pytest
import asyncio
import time
from pathlib import Path

from src.caching.manager import CacheManager
from src.caching.base import CacheConfig, CacheBackend


@pytest.fixture
async def redis_cache():
    """Fixture providing isolated Redis cache for testing."""
    config = CacheConfig(
        backend=CacheBackend.REDIS,
        redis_host="localhost",
        redis_port=6379,
        redis_db=15,  # Use highest DB number for tests
        redis_key_prefix="pytest:",
        ttl_default=60
    )
    
    cache = CacheManager(config)
    
    try:
        await cache.initialize()
        # Clear any existing test data
        await cache.clear_cache()
        yield cache
    except Exception as e:
        if "redis" in str(e).lower() or "connection" in str(e).lower():
            pytest.skip(f"Redis not available: {e}")
    finally:
        if hasattr(cache, 'backend') and cache.backend:
            await cache.clear_cache()  # Cleanup
            await cache.shutdown()


class TestRedisAdvanced:
    """Advanced Redis testing following best practices."""
    
    @pytest.mark.asyncio
    async def test_connection_retry_and_failover(self):
        """Test Redis connection resilience."""
        # Test with invalid config (should fail gracefully)
        bad_config = CacheConfig(
            backend=CacheBackend.REDIS,
            redis_host="nonexistent-redis-host.local",
            redis_port=9999,
            redis_db=0
        )
        
        cache = CacheManager(bad_config)
        
        with pytest.raises(Exception):
            await cache.initialize()
    
    @pytest.mark.asyncio
    async def test_ttl_expiration(self, redis_cache):
        """Test TTL expiration behavior."""
        # Set with short TTL
        await redis_cache.set_html("https://test.com/expire", "<html>Expires soon</html>", ttl=1)
        
        # Should exist immediately
        cached = await redis_cache.get_html("https://test.com/expire")
        assert cached is not None
        
        # Wait for expiration
        await asyncio.sleep(1.5)
        
        # Should be expired
        expired = await redis_cache.get_html("https://test.com/expire")
        assert expired is None
    
    @pytest.mark.asyncio
    async def test_large_data_handling(self, redis_cache):
        """Test handling of large data sets."""
        # Test large HTML content
        large_html = "<html><body>" + "x" * 100000 + "</body></html>"
        
        success = await redis_cache.set_html("https://test.com/large", large_html)
        assert success
        
        retrieved = await redis_cache.get_html("https://test.com/large")
        assert retrieved == large_html
        
        # Test large binary data
        large_image = b"binary_data" * 10000
        
        success = await redis_cache.set_image("https://test.com/large.jpg", large_image)
        assert success
        
        retrieved_image = await redis_cache.get_image("https://test.com/large.jpg")
        assert retrieved_image == large_image
    
    @pytest.mark.asyncio
    async def test_concurrent_access(self, redis_cache):
        """Test concurrent cache operations."""
        async def cache_worker(worker_id, count):
            for i in range(count):
                url = f"https://test.com/worker{worker_id}/item{i}"
                content = f"<html>Worker {worker_id} Item {i}</html>"
                
                await redis_cache.set_html(url, content)
                retrieved = await redis_cache.get_html(url)
                assert retrieved == content
        
        # Run 5 workers concurrently, each doing 10 operations
        workers = [cache_worker(i, 10) for i in range(5)]
        await asyncio.gather(*workers)
        
        # Verify stats
        stats = await redis_cache.get_cache_stats()
        assert stats['total_entries'] >= 50  # Should have at least 50 entries
    
    @pytest.mark.asyncio
    async def test_memory_usage_monitoring(self, redis_cache):
        """Test Redis memory usage monitoring."""
        # Add some data
        for i in range(100):
            await redis_cache.set_html(f"https://test.com/memory{i}", f"<html>Content {i}</html>")
        
        stats = await redis_cache.get_cache_stats()
        
        # Should have memory usage info
        assert 'redis_memory_used' in stats
        assert stats['total_entries'] >= 100
        assert stats['total_size_bytes'] > 0
    
    @pytest.mark.asyncio
    async def test_key_collision_handling(self, redis_cache):
        """Test handling of key collisions and overwrites."""
        url = "https://test.com/collision"
        
        # Set initial value
        await redis_cache.set_html(url, "<html>Version 1</html>")
        assert await redis_cache.get_html(url) == "<html>Version 1</html>"
        
        # Overwrite with new value
        await redis_cache.set_html(url, "<html>Version 2</html>")
        assert await redis_cache.get_html(url) == "<html>Version 2</html>"
        
        # Should only have one entry for this URL
        stats = await redis_cache.get_cache_stats()
        # Count entries with our test prefix
        import redis.asyncio as redis_client
        client = redis_client.Redis(host="localhost", port=6379, db=15)
        keys = await client.keys("pytest:html:*collision*")
        await client.close()
        
        assert len(keys) == 1  # Should only have one key for this URL
    
    @pytest.mark.asyncio
    async def test_unicode_and_special_characters(self, redis_cache):
        """Test handling of Unicode and special characters."""
        test_cases = [
            ("https://test.com/unicode", "<html>🚀 Unicode: 中文 العربية русский</html>"),
            ("https://test.com/special", "<html>Special: \"quotes\" 'apostrophes' &amp; entities</html>"),
            ("https://test.com/emoji", "<html>Emojis: 👨‍💻 🌟 🎉 🔥</html>"),
        ]
        
        # Cache all test cases
        for url, content in test_cases:
            success = await redis_cache.set_html(url, content)
            assert success, f"Failed to cache {url}"
        
        # Verify all test cases
        for url, expected_content in test_cases:
            retrieved = await redis_cache.get_html(url)
            assert retrieved == expected_content, f"Content mismatch for {url}"
    
    @pytest.mark.asyncio
    async def test_performance_benchmarking(self, redis_cache):
        """Basic performance benchmarking of Redis operations."""
        # Warm up
        await redis_cache.set_html("https://test.com/warmup", "<html>warmup</html>")
        
        # Benchmark write operations
        write_count = 100
        write_start = time.perf_counter()
        
        for i in range(write_count):
            await redis_cache.set_html(f"https://test.com/perf{i}", f"<html>Content {i}</html>")
        
        write_duration = time.perf_counter() - write_start
        write_ops_per_sec = write_count / write_duration
        
        # Benchmark read operations
        read_start = time.perf_counter()
        
        for i in range(write_count):
            content = await redis_cache.get_html(f"https://test.com/perf{i}")
            assert content is not None
        
        read_duration = time.perf_counter() - read_start
        read_ops_per_sec = write_count / read_duration
        
        print(f"\nRedis Performance:")
        print(f"  Write: {write_ops_per_sec:.0f} ops/sec")
        print(f"  Read:  {read_ops_per_sec:.0f} ops/sec")
        
        # Basic performance assertions (adjust based on your requirements)
        assert write_ops_per_sec > 50, "Write performance too slow"
        assert read_ops_per_sec > 100, "Read performance too slow"
    
    @pytest.mark.asyncio
    async def test_redis_configuration_validation(self):
        """Test Redis configuration validation."""
        configs_to_test = [
            # Valid config
            {
                "redis_host": "localhost",
                "redis_port": 6379,
                "redis_db": 0,
                "should_work": True
            },
            # Invalid host
            {
                "redis_host": "invalid-host-that-does-not-exist",
                "redis_port": 6379,
                "redis_db": 0,
                "should_work": False
            },
            # Invalid port
            {
                "redis_host": "localhost",
                "redis_port": 99999,
                "redis_db": 0,
                "should_work": False
            }
        ]
        
        for config_test in configs_to_test:
            config = CacheConfig(
                backend=CacheBackend.REDIS,
                redis_host=config_test["redis_host"],
                redis_port=config_test["redis_port"],
                redis_db=config_test["redis_db"]
            )
            
            cache = CacheManager(config)
            
            if config_test["should_work"]:
                try:
                    await cache.initialize()
                    await cache.shutdown()
                except Exception:
                    pytest.fail(f"Valid config should work: {config_test}")
            else:
                with pytest.raises(Exception):
                    await cache.initialize()


@pytest.mark.asyncio
async def test_redis_fallback_behavior():
    """Test graceful fallback when Redis is unavailable."""
    from src.caching.redis_cache import REDIS_AVAILABLE
    
    if REDIS_AVAILABLE:
        # Test what happens when Redis connection fails
        config = CacheConfig(
            backend=CacheBackend.REDIS,
            redis_host="nonexistent.example.com",
            redis_port=6379
        )
        
        cache = CacheManager(config)
        
        # Should raise an exception (not hang or crash)
        with pytest.raises(Exception):
            await cache.initialize()
    else:
        # Redis client not available
        with pytest.raises(ImportError):
            from src.caching.redis_cache import RedisCache
            config = CacheConfig(backend=CacheBackend.REDIS)
            cache = CacheManager(config)
            await cache.initialize()