"""Integration tests for Redis caching backend."""

from pathlib import Path

import pytest

from src.caching.base import CacheBackend, CacheConfig
from src.caching.manager import CacheManager


@pytest.mark.asyncio
async def test_redis_cache_integration():
    """Test Redis cache integration if Redis is available."""

    try:
        # Try to create Redis cache manager
        config = CacheConfig(
            backend=CacheBackend.REDIS,
            redis_host="localhost",
            redis_port=6379,
            redis_db=1,  # Use db 1 for tests
            redis_key_prefix="test:",
            ttl_html=300,
            ttl_images=600,
        )

        cache = CacheManager(config)
        await cache.initialize()

        # Test HTML caching
        test_url = "https://example.com/redis-test"
        test_html = "<html><body><h1>Redis Test</h1></body></html>"

        success = await cache.set_html(test_url, test_html)
        assert success, "Failed to cache HTML in Redis"

        cached_html = await cache.get_html(test_url)
        assert cached_html == test_html, "Retrieved HTML doesn't match cached HTML"

        # Test image caching with binary data
        image_url = "https://example.com/test.jpg"
        image_data = b"\x89PNG\r\n\x1a\nfake image data"

        success = await cache.set_image(image_url, image_data)
        assert success, "Failed to cache image in Redis"

        cached_image = await cache.get_image(image_url)
        assert cached_image == image_data, "Retrieved image data doesn't match cached data"

        # Test metadata caching
        metadata = {
            "title": "Redis Test Page",
            "description": "Testing Redis caching",
            "tags": ["redis", "cache", "test"],
            "nested": {"data": "value"},
        }

        success = await cache.set_metadata(test_url, metadata)
        assert success, "Failed to cache metadata in Redis"

        cached_metadata = await cache.get_metadata(test_url)
        assert cached_metadata == metadata, "Retrieved metadata doesn't match cached metadata"

        # Test cache stats
        stats = await cache.get_cache_stats()
        assert "redis_version" in stats, "Redis stats should include version"
        assert stats["total_entries"] >= 3, "Should have cached at least 3 items"
        assert stats["backend"] == "redis", "Backend should be Redis"

        # Test cache invalidation
        invalidated = await cache.invalidate_url(test_url)
        assert invalidated, "Should have invalidated cached data"

        # Verify invalidation worked
        assert await cache.get_html(test_url) is None, "HTML should be invalidated"
        assert await cache.get_metadata(test_url) is None, "Metadata should be invalidated"

        # Image should still exist (different URL)
        cached_image_after = await cache.get_image(image_url)
        assert cached_image_after == image_data, "Image should still be cached"

        # Cleanup
        await cache.clear_cache()
        await cache.shutdown()

    except Exception as e:
        if "redis" in str(e).lower() or "connection" in str(e).lower():
            pytest.skip(f"Redis not available for testing: {e}")
        else:
            raise


@pytest.mark.asyncio
async def test_redis_vs_file_cache_compatibility():
    """Test that Redis and file cache backends are compatible."""

    # Test data
    test_url = "https://example.com/compatibility-test"
    test_html = "<html><body>Compatibility test</body></html>"
    test_metadata = {"title": "Compatibility Test", "source": "test"}

    try:
        # Test with Redis first
        redis_config = CacheConfig(
            backend=CacheBackend.REDIS,
            redis_db=2,  # Different DB for this test
            redis_key_prefix="compat:",
        )

        redis_cache = CacheManager(redis_config)
        await redis_cache.initialize()

        # Cache data in Redis
        await redis_cache.set_html(test_url, test_html)
        await redis_cache.set_metadata(test_url, test_metadata)

        # Verify Redis cache
        redis_html = await redis_cache.get_html(test_url)
        redis_metadata = await redis_cache.get_metadata(test_url)

        assert redis_html == test_html
        assert redis_metadata == test_metadata

        await redis_cache.shutdown()

        # Test with File cache
        file_config = CacheConfig(backend=CacheBackend.FILE, cache_dir=Path("test_compat_cache"))

        file_cache = CacheManager(file_config)
        await file_cache.initialize()

        # Cache same data in file cache
        await file_cache.set_html(test_url, test_html)
        await file_cache.set_metadata(test_url, test_metadata)

        # Verify file cache
        file_html = await file_cache.get_html(test_url)
        file_metadata = await file_cache.get_metadata(test_url)

        assert file_html == test_html
        assert file_metadata == test_metadata

        # Both backends should produce identical results
        assert redis_html == file_html
        assert redis_metadata == file_metadata

        await file_cache.shutdown()

        # Cleanup
        import shutil

        shutil.rmtree("test_compat_cache", ignore_errors=True)

    except Exception as e:
        if "redis" in str(e).lower() or "connection" in str(e).lower():
            pytest.skip(f"Redis not available for testing: {e}")
        else:
            raise
