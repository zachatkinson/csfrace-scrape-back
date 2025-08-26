"""Performance tests for caching system components."""

import asyncio
import time

import pytest

from src.caching.base import CacheBackend, CacheConfig
from src.caching.file_cache import FileCache
from src.caching.manager import CacheManager


@pytest.mark.performance
class TestCachePerformance:
    """Test cache performance under various conditions."""

    @pytest.fixture
    def cache_config(self, temp_dir):
        """Create cache configuration for testing."""
        return CacheConfig(
            backend=CacheBackend.FILE,
            cache_dir=temp_dir / "perf_cache",
            ttl_default=3600,
            compress=True,
        )

    @pytest.fixture
    def file_cache(self, cache_config):
        """Create file cache instance for testing."""
        return FileCache(cache_config)

    @pytest.fixture
    def cache_manager(self, cache_config):
        """Create cache manager instance for testing."""
        manager = CacheManager(cache_config)
        return manager

    @pytest.mark.asyncio
    async def test_cache_write_performance(self, file_cache):
        """Test cache write performance with various data sizes."""
        data_sizes = [1024, 10240, 102400, 1024000]  # 1KB to 1MB

        for size in data_sizes:
            test_data = "x" * size
            key = f"perf_test_{size}"

            start_time = time.time()
            success = await file_cache.set(key, test_data, ttl=3600)
            write_time = time.time() - start_time

            # Write should complete quickly even for large data
            assert success is True
            assert write_time < 1.0, f"Write of {size} bytes took {write_time:.3f}s, expected < 1s"

    @pytest.mark.asyncio
    async def test_cache_read_performance(self, file_cache):
        """Test cache read performance with various data sizes."""
        # Pre-populate cache with test data
        data_sizes = [1024, 10240, 102400, 1024000]
        test_keys = []

        for size in data_sizes:
            test_data = "x" * size
            key = f"read_perf_test_{size}"
            await file_cache.set(key, test_data, ttl=3600)
            test_keys.append((key, size))

        # Test read performance
        for key, size in test_keys:
            start_time = time.time()
            entry = await file_cache.get(key)
            read_time = time.time() - start_time

            assert entry is not None
            assert read_time < 0.5, f"Read of {size} bytes took {read_time:.3f}s, expected < 0.5s"

    @pytest.mark.asyncio
    async def test_concurrent_cache_operations(self, file_cache):
        """Test cache performance under concurrent load."""
        num_operations = 50

        async def write_operation(i):
            key = f"concurrent_write_{i}"
            value = f"test_data_{i}" * 100  # ~1KB per entry
            return await file_cache.set(key, value, ttl=3600)

        async def read_operation(i):
            key = f"concurrent_read_{i}"
            # Pre-populate for reads
            await file_cache.set(key, f"read_data_{i}", ttl=3600)
            return await file_cache.get(key)

        # Test concurrent writes
        start_time = time.time()
        write_tasks = [write_operation(i) for i in range(num_operations)]
        write_results = await asyncio.gather(*write_tasks)
        write_time = time.time() - start_time

        assert all(result is True for result in write_results)
        assert write_time < 5.0, f"Concurrent writes took {write_time:.2f}s, expected < 5s"

        # Test concurrent reads
        start_time = time.time()
        read_tasks = [read_operation(i) for i in range(num_operations)]
        read_results = await asyncio.gather(*read_tasks)
        read_time = time.time() - start_time

        assert all(result is not None for result in read_results)
        assert read_time < 2.0, f"Concurrent reads took {read_time:.2f}s, expected < 2s"

    @pytest.mark.asyncio
    async def test_cache_compression_performance(self, cache_config, temp_dir):
        """Test compression performance impact."""
        large_data = {"content": "x" * 50000, "metadata": {"size": "large"}}

        # Test without compression
        cache_config.compress = False
        cache_no_compress = FileCache(cache_config)

        start_time = time.time()
        await cache_no_compress.set("no_compress_test", large_data, ttl=3600)
        no_compress_time = time.time() - start_time

        # Test with compression
        cache_config.compress = True
        cache_config.cache_dir = temp_dir / "compressed_cache"
        cache_compress = FileCache(cache_config)

        start_time = time.time()
        await cache_compress.set("compress_test", large_data, ttl=3600)
        compress_time = time.time() - start_time

        # Compression shouldn't add too much overhead
        assert compress_time < (no_compress_time * 3), (
            f"Compression added too much overhead: {compress_time:.3f}s vs {no_compress_time:.3f}s"
        )

    @pytest.mark.asyncio
    async def test_cache_cleanup_performance(self, file_cache):
        """Test cache cleanup performance with many entries."""
        num_entries = 100

        # Create entries with short TTL
        for i in range(num_entries):
            key = f"cleanup_test_{i}"
            await file_cache.set(key, f"data_{i}", ttl=1)  # 1 second TTL

        # Wait for entries to expire
        await asyncio.sleep(2)

        # Test cleanup performance
        start_time = time.time()
        cleaned_count = await file_cache.cleanup_expired()
        cleanup_time = time.time() - start_time

        assert cleaned_count >= num_entries
        assert cleanup_time < 2.0, f"Cleanup took {cleanup_time:.2f}s, expected < 2s"

    @pytest.mark.asyncio
    async def test_cache_stats_performance(self, file_cache):
        """Test cache statistics calculation performance."""
        # Add various entries
        for i in range(50):
            await file_cache.set(f"stats_test_{i}", f"data_{i}" * 100)

        start_time = time.time()
        stats = await file_cache.stats()
        stats_time = time.time() - start_time

        assert isinstance(stats, dict)
        assert "total_entries" in stats
        assert stats["total_entries"] >= 50
        assert stats_time < 1.0, f"Stats calculation took {stats_time:.3f}s, expected < 1s"

    @pytest.mark.asyncio
    async def test_cache_manager_performance(self, cache_manager):
        """Test cache manager performance for typical operations."""
        await cache_manager.initialize()

        # Test HTML caching performance
        html_content = "<html><body><h1>Test</h1></body></html>" * 100
        url = "https://example.com/test"

        start_time = time.time()
        await cache_manager.set_html(url, html_content)
        set_time = time.time() - start_time

        start_time = time.time()
        cached_html = await cache_manager.get_html(url)
        get_time = time.time() - start_time

        assert cached_html == html_content
        assert set_time < 0.5, f"HTML cache set took {set_time:.3f}s, expected < 0.5s"
        assert get_time < 0.1, f"HTML cache get took {get_time:.3f}s, expected < 0.1s"

    @pytest.mark.asyncio
    async def test_cache_key_generation_performance(self, file_cache):
        """Test cache key generation performance."""
        num_keys = 1000

        start_time = time.time()
        keys = []
        for i in range(num_keys):
            key = file_cache.generate_key("url", f"https://example.com/page/{i}")
            keys.append(key)
        key_gen_time = time.time() - start_time

        # Key generation should be very fast
        assert len(keys) == num_keys
        assert len(set(keys)) == num_keys  # All keys should be unique
        assert key_gen_time < 0.5, f"Key generation took {key_gen_time:.3f}s, expected < 0.5s"

    def test_simple_cache_benchmark(self, benchmark, file_cache):
        """Simple benchmark test for cache operations."""
        test_key = "benchmark_test"
        test_data = "test data" * 100  # Small test data

        def cache_operation():
            # Since benchmark doesn't handle async, we use asyncio.run
            import asyncio

            asyncio.run(file_cache.set(test_key, test_data, ttl=3600))
            return asyncio.run(file_cache.get(test_key))

        result = benchmark(cache_operation)
        assert result is not None
        assert result.value == test_data
