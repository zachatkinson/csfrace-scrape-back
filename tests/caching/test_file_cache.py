"""Unit tests for caching/file_cache.py following TEST_BUILDING.md ZERO TOLERANCE standards.

MANDATORY REQUIREMENTS (NON-NEGOTIABLE):
- NO vestigial code - every line serves a purpose
- NO legacy patterns - modern Python 3.11+ only
- NO backwards compatibility - clean implementations only
- NO broad exceptions - specific exceptions required
- SOLID principles compliance mandatory
- DRY compliance mandatory - no duplication
- Production-ready implementations only
- AAA pattern (Arrange-Act-Assert) for ALL tests
- Security tests for ALL input handlers
- Performance benchmarks for ALL critical paths

Tests file-based cache backend following TEST_BUILDING.md with comprehensive coverage.
"""

import time
from pathlib import Path

import asyncio
import pytest

from src.caching.base import CacheConfig, CacheEntry
from src.caching.file_cache import FileCache

# =============================================================================
# TEST FIXTURES - Factory Pattern for DRY Principle
# =============================================================================


@pytest.fixture
def cache_config(tmp_path: Path) -> CacheConfig:
    """Factory for CacheConfig with temp directory - DRY principle."""
    return CacheConfig(
        cache_dir=tmp_path / "cache",
        max_cache_size_mb=10,
        ttl_default=3600,
        ttl_html=7200,
        ttl_images=86400,
        compress=True,
    )


@pytest.fixture
def file_cache(cache_config: CacheConfig) -> FileCache:
    """Factory for FileCache - DRY principle."""
    return FileCache(cache_config)


@pytest.fixture
def sample_cache_entry() -> CacheEntry:
    """Factory for sample CacheEntry - DRY principle."""
    return CacheEntry(
        key="test:key:123",
        value="test_content",
        created_at=time.time(),
        ttl=3600,
        content_type="html",
        size_bytes=1024,
        compressed=True,
    )


# =============================================================================
# TEST FileCache - Initialization
# =============================================================================


@pytest.mark.unit
class TestFileCacheInit:
    """Test FileCache initialization following MANDATORY AAA pattern."""

    def test_init_creates_cache_directories(self, file_cache: FileCache):
        """Test __init__ creates cache directories - MANDATORY AAA pattern."""
        # Arrange - MANDATORY (file_cache fixture)

        # Act - MANDATORY (initialization already done by fixture)
        cache_dir = file_cache.cache_dir

        # Assert - MANDATORY
        assert cache_dir.exists()
        assert file_cache.html_dir.exists()
        assert file_cache.image_dir.exists()
        assert file_cache.metadata_dir.exists()
        assert file_cache.robots_dir.exists()
        assert file_cache.generic_dir.exists()

    def test_init_creates_stats_dictionary(self, file_cache: FileCache):
        """Test __init__ creates stats dictionary - MANDATORY AAA pattern."""
        # Arrange - MANDATORY (file_cache fixture)

        # Act - MANDATORY
        stats = file_cache._stats

        # Assert - MANDATORY
        assert "hits" in stats
        assert "misses" in stats
        assert "sets" in stats
        assert "deletes" in stats
        assert "errors" in stats
        assert stats["hits"] == 0
        assert stats["misses"] == 0


# =============================================================================
# TEST FileCache - Cache Path Generation
# =============================================================================


@pytest.mark.unit
class TestFileCachePath:
    """Test FileCache path generation following MANDATORY AAA pattern."""

    def test_get_cache_path_returns_html_path(self, file_cache: FileCache):
        """Test _get_cache_path returns HTML path - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        key = "test:html:key"
        content_type = "html"

        # Act - MANDATORY
        cache_path = file_cache._get_cache_path(key, content_type)

        # Assert - MANDATORY
        assert cache_path.parent == file_cache.html_dir
        assert cache_path.suffix == ".cache"
        assert cache_path.name != key  # Should be hashed

    def test_get_cache_path_returns_image_path(self, file_cache: FileCache):
        """Test _get_cache_path returns image path - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        key = "test:image:key"
        content_type = "image"

        # Act - MANDATORY
        cache_path = file_cache._get_cache_path(key, content_type)

        # Assert - MANDATORY
        assert cache_path.parent == file_cache.image_dir
        assert cache_path.suffix == ".cache"

    def test_get_cache_path_uses_generic_for_unknown_type(self, file_cache: FileCache):
        """Test _get_cache_path uses generic for unknown type - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        key = "test:unknown:key"
        content_type = "unknown_type"

        # Act - MANDATORY
        cache_path = file_cache._get_cache_path(key, content_type)

        # Assert - MANDATORY
        assert cache_path.parent == file_cache.generic_dir


# =============================================================================
# TEST FileCache - Get Operation
# =============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
class TestFileCacheGet:
    """Test FileCache get operation following MANDATORY AAA pattern."""

    async def test_get_returns_none_for_missing_entry(self, file_cache: FileCache):
        """Test get returns None for missing entry - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        key = "nonexistent:key"

        # Act - MANDATORY
        result = await file_cache.get(key)

        # Assert - MANDATORY
        assert result is None
        assert file_cache._stats["misses"] == 1

    async def test_get_returns_entry_for_valid_cache(self, file_cache: FileCache):
        """Test get returns entry for valid cache - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        key = "test:valid:key"
        value = "test_content"
        await file_cache.set(key, value, ttl=3600, content_type="html")

        # Act - MANDATORY
        result = await file_cache.get(key)

        # Assert - MANDATORY
        assert result is not None
        assert result.key == key
        assert result.value == value
        assert file_cache._stats["hits"] == 1

    async def test_get_returns_none_for_expired_entry(self, file_cache: FileCache):
        """Test get returns None for expired entry - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        key = "test:expired:key"
        value = "expired_content"
        await file_cache.set(key, value, ttl=1, content_type="html")
        await asyncio.sleep(1.1)  # Wait for expiration

        # Act - MANDATORY
        result = await file_cache.get(key)

        # Assert - MANDATORY
        assert result is None
        assert file_cache._stats["misses"] == 1


# =============================================================================
# TEST FileCache - Set Operation
# =============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
class TestFileCacheSet:
    """Test FileCache set operation following MANDATORY AAA pattern."""

    async def test_set_creates_cache_file(self, file_cache: FileCache):
        """Test set creates cache file - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        key = "test:set:key"
        value = "test_content"

        # Act - MANDATORY
        result = await file_cache.set(key, value, ttl=3600, content_type="html")

        # Assert - MANDATORY
        assert result is True
        assert file_cache._stats["sets"] == 1
        cache_path = file_cache._get_cache_path(key, "html")
        assert cache_path.exists()

    async def test_set_with_custom_ttl(self, file_cache: FileCache):
        """Test set with custom TTL - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        key = "test:custom:ttl"
        value = "content"
        custom_ttl = 7200

        # Act - MANDATORY
        await file_cache.set(key, value, ttl=custom_ttl, content_type="html")
        result = await file_cache.get(key)

        # Assert - MANDATORY
        assert result is not None
        assert result.ttl == custom_ttl

    async def test_set_overwrites_existing_entry(self, file_cache: FileCache):
        """Test set overwrites existing entry - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        key = "test:overwrite:key"
        await file_cache.set(key, "old_value", ttl=3600, content_type="html")

        # Act - MANDATORY
        await file_cache.set(key, "new_value", ttl=3600, content_type="html")
        result = await file_cache.get(key)

        # Assert - MANDATORY
        assert result is not None
        assert result.value == "new_value"


# =============================================================================
# TEST FileCache - Delete Operation
# =============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
class TestFileCacheDelete:
    """Test FileCache delete operation following MANDATORY AAA pattern."""

    async def test_delete_removes_cache_file(self, file_cache: FileCache):
        """Test delete removes cache file - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        key = "test:delete:key"
        await file_cache.set(key, "content", ttl=3600, content_type="html")

        # Act - MANDATORY
        result = await file_cache.delete(key)

        # Assert - MANDATORY
        assert result is True
        assert file_cache._stats["deletes"] == 1
        cache_path = file_cache._get_cache_path(key, "html")
        assert not cache_path.exists()

    async def test_delete_returns_false_for_nonexistent_key(self, file_cache: FileCache):
        """Test delete returns False for nonexistent key - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        key = "nonexistent:key"

        # Act - MANDATORY
        result = await file_cache.delete(key)

        # Assert - MANDATORY
        assert result is False


# =============================================================================
# TEST FileCache - Clear Operation
# =============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
class TestFileCacheClear:
    """Test FileCache clear operation following MANDATORY AAA pattern."""

    async def test_clear_removes_all_cache_files(self, file_cache: FileCache):
        """Test clear removes all cache files - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        await file_cache.set("key1", "value1", ttl=3600, content_type="html")
        await file_cache.set("key2", "value2", ttl=3600, content_type="image")
        await file_cache.set("key3", "value3", ttl=3600, content_type="metadata")

        # Act - MANDATORY
        result = await file_cache.clear()

        # Assert - MANDATORY
        assert result is True
        assert file_cache._stats["hits"] == 0
        assert file_cache._stats["misses"] == 0
        assert file_cache._stats["sets"] == 0

        # Verify no cache files exist
        html_files = list(file_cache.html_dir.glob("*.cache"))
        image_files = list(file_cache.image_dir.glob("*.cache"))
        metadata_files = list(file_cache.metadata_dir.glob("*.cache"))
        assert len(html_files) == 0
        assert len(image_files) == 0
        assert len(metadata_files) == 0


# =============================================================================
# TEST FileCache - Stats Operation
# =============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
class TestFileCacheStats:
    """Test FileCache stats operation following MANDATORY AAA pattern."""

    async def test_stats_returns_empty_cache_stats(self, file_cache: FileCache):
        """Test stats returns empty cache stats - MANDATORY AAA pattern."""
        # Arrange - MANDATORY (empty cache)

        # Act - MANDATORY
        stats = await file_cache.stats()

        # Assert - MANDATORY
        assert stats["total_entries"] == 0
        assert stats["total_size_bytes"] == 0
        assert stats["total_size_mb"] == 0
        assert stats["hits"] == 0
        assert stats["misses"] == 0

    async def test_stats_returns_populated_cache_stats(self, file_cache: FileCache):
        """Test stats returns populated cache stats - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        await file_cache.set("key1", "value1", ttl=3600, content_type="html")
        await file_cache.set("key2", "value2", ttl=3600, content_type="image")

        # Act - MANDATORY
        stats = await file_cache.stats()

        # Assert - MANDATORY
        assert stats["total_entries"] == 2
        assert stats["total_size_bytes"] > 0
        assert stats["total_size_mb"] >= 0  # May be 0.0 due to rounding for small files
        assert stats["sets"] == 2

    async def test_stats_calculates_hit_rate(self, file_cache: FileCache):
        """Test stats calculates hit rate - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        await file_cache.set("key1", "value1", ttl=3600, content_type="html")
        await file_cache.get("key1")  # Hit
        await file_cache.get("nonexistent")  # Miss

        # Act - MANDATORY
        stats = await file_cache.stats()

        # Assert - MANDATORY
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["hit_rate"] == 50.0


# =============================================================================
# TEST FileCache - Cleanup Operations
# =============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
class TestFileCacheCleanup:
    """Test FileCache cleanup operations following MANDATORY AAA pattern."""

    async def test_cleanup_expired_removes_expired_entries(self, file_cache: FileCache):
        """Test cleanup_expired removes expired entries - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        await file_cache.set("key1", "value1", ttl=1, content_type="html")
        await file_cache.set("key2", "value2", ttl=3600, content_type="html")
        await asyncio.sleep(1.1)  # Wait for first entry to expire

        # Act - MANDATORY
        cleaned = await file_cache.cleanup_expired()

        # Assert - MANDATORY
        assert cleaned == 1
        result1 = await file_cache.get("key1")
        result2 = await file_cache.get("key2")
        assert result1 is None
        assert result2 is not None

    async def test_cleanup_expired_returns_zero_for_no_expired(self, file_cache: FileCache):
        """Test cleanup_expired returns zero for no expired - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        await file_cache.set("key1", "value1", ttl=3600, content_type="html")

        # Act - MANDATORY
        cleaned = await file_cache.cleanup_expired()

        # Assert - MANDATORY
        assert cleaned == 0


# =============================================================================
# MANDATORY SECURITY TESTS
# =============================================================================


@pytest.mark.security
class TestFileCacheSecurity:
    """MANDATORY security tests for file cache."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_set_sanitizes_malicious_keys(self, file_cache: FileCache):
        """MANDATORY security test - set sanitizes malicious keys."""
        # Arrange - MANDATORY
        malicious_keys = [
            "../../../etc/passwd",
            "..\\..\\..\\windows\\system32\\config\\sam",
            "/absolute/path/traversal",
            "key;rm -rf /",
            "key`whoami`",
        ]

        for malicious_key in malicious_keys:
            # Act - MANDATORY
            result = await file_cache.set(malicious_key, "content", ttl=3600, content_type="html")

            # Assert - MANDATORY (security check)
            assert result is True
            # Key should be hashed, preventing directory traversal
            cache_path = file_cache._get_cache_path(malicious_key, "html")
            assert cache_path.parent == file_cache.html_dir
            assert "../" not in str(cache_path)
            assert "..\\" not in str(cache_path)

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_set_handles_malicious_values_safely(self, file_cache: FileCache):
        """MANDATORY security test - set handles malicious values safely."""
        # Arrange - MANDATORY
        malicious_values = [
            "<script>alert('xss')</script>",
            "'; DROP TABLE cache; --",
            "../../sensitive_data",
            "\x00\x01\x02",  # Null bytes
            "A" * 1000000,  # Large value
        ]

        for malicious_value in malicious_values:
            # Act - MANDATORY
            key = f"test:security:{hash(malicious_value)}"
            result = await file_cache.set(key, malicious_value, ttl=3600, content_type="html")

            # Assert - MANDATORY (security check)
            assert result is True
            retrieved = await file_cache.get(key)
            assert retrieved is not None
            assert retrieved.value == malicious_value  # Should store as-is


# =============================================================================
# MANDATORY PERFORMANCE TESTS
# =============================================================================


@pytest.mark.performance
class TestFileCachePerformance:
    """MANDATORY performance tests for file cache."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_set_performance_benchmark(self, file_cache: FileCache):
        """MANDATORY performance test - set completes quickly."""
        # Arrange - MANDATORY
        iterations = 100
        start_time = time.perf_counter()

        # Act - MANDATORY
        for i in range(iterations):
            await file_cache.set(f"key:{i}", f"value_{i}", ttl=3600, content_type="html")

        end_time = time.perf_counter()
        execution_time = end_time - start_time

        # Assert - MANDATORY (performance requirement)
        avg_time = execution_time / iterations
        assert avg_time < 0.01  # Less than 10ms per set operation
        assert execution_time < 1.0  # Total under 1 second for 100 sets

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_performance_benchmark(self, file_cache: FileCache):
        """MANDATORY performance test - get completes quickly."""
        # Arrange - MANDATORY
        iterations = 100
        # Pre-populate cache
        for i in range(iterations):
            await file_cache.set(f"key:{i}", f"value_{i}", ttl=3600, content_type="html")

        start_time = time.perf_counter()

        # Act - MANDATORY
        for i in range(iterations):
            await file_cache.get(f"key:{i}")

        end_time = time.perf_counter()
        execution_time = end_time - start_time

        # Assert - MANDATORY (performance requirement)
        avg_time = execution_time / iterations
        assert avg_time < 0.005  # Less than 5ms per get operation
        assert execution_time < 0.5  # Total under 500ms for 100 gets

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_cleanup_performance_benchmark(self, file_cache: FileCache):
        """MANDATORY performance test - cleanup completes quickly."""
        # Arrange - MANDATORY
        entry_count = 500
        # Create entries with short TTL
        for i in range(entry_count):
            await file_cache.set(f"key:{i}", f"value_{i}", ttl=1, content_type="html")

        await asyncio.sleep(1.1)  # Wait for expiration
        start_time = time.perf_counter()

        # Act - MANDATORY
        cleaned = await file_cache.cleanup_expired()

        end_time = time.perf_counter()
        execution_time = end_time - start_time

        # Assert - MANDATORY (performance requirement)
        assert cleaned == entry_count
        assert execution_time < 5.0  # Should complete within 5 seconds for 500 entries
