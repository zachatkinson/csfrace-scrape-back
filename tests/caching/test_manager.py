"""Unit tests for caching/manager.py following TEST_BUILDING.md ZERO TOLERANCE standards.

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

Tests cache manager following TEST_BUILDING.md with comprehensive coverage.
"""

import time
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from src.caching.base import CacheBackend, CacheConfig
from src.caching.manager import CacheManager

# =============================================================================
# TEST FIXTURES - Factory Pattern for DRY Principle
# =============================================================================


@pytest.fixture
def file_cache_config(tmp_path: Path) -> CacheConfig:
    """Factory for file-based CacheConfig - DRY principle."""
    return CacheConfig(
        backend=CacheBackend.FILE,
        cache_dir=tmp_path / "cache",
        ttl_html=3600,
        ttl_images=7200,
        ttl_metadata=1800,
        ttl_robots=86400,
        compress=True,
        cleanup_on_startup=False,
    )


@pytest.fixture
def cache_manager(file_cache_config: CacheConfig) -> CacheManager:
    """Factory for CacheManager with file backend - DRY principle."""
    return CacheManager(file_cache_config)


@pytest.fixture
def mock_file_backend():
    """Factory for mock file backend - DRY principle."""
    backend = AsyncMock()
    backend.get = AsyncMock(return_value=None)
    backend.set = AsyncMock(return_value=True)
    backend.delete = AsyncMock(return_value=True)
    backend.clear = AsyncMock(return_value=True)
    backend.stats = AsyncMock(
        return_value={
            "hits": 10,
            "misses": 5,
            "total_entries": 100,
            "total_size_mb": 5.2,
        }
    )
    backend.cleanup_expired = AsyncMock(return_value=5)
    return backend


# =============================================================================
# TEST CacheManager - Initialization
# =============================================================================


@pytest.mark.unit
class TestCacheManagerInit:
    """Test CacheManager initialization following MANDATORY AAA pattern."""

    def test_init_creates_manager_with_default_config(self):
        """Test __init__ creates manager with default config - MANDATORY AAA pattern."""
        # Arrange - MANDATORY (no setup needed)

        # Act - MANDATORY
        manager = CacheManager()

        # Assert - MANDATORY
        assert manager.config is not None
        assert isinstance(manager.config, CacheConfig)
        assert manager.backend is None
        assert manager._initialized is False

    def test_init_creates_manager_with_custom_config(self, file_cache_config: CacheConfig):
        """Test __init__ creates manager with custom config - MANDATORY AAA pattern."""
        # Arrange - MANDATORY (file_cache_config fixture)

        # Act - MANDATORY
        manager = CacheManager(file_cache_config)

        # Assert - MANDATORY
        assert manager.config == file_cache_config
        assert manager.backend is None


# =============================================================================
# TEST CacheManager - Backend Management
# =============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
class TestCacheManagerBackend:
    """Test CacheManager backend management following MANDATORY AAA pattern."""

    async def test_initialize_creates_file_backend(self, cache_manager: CacheManager):
        """Test initialize creates file backend - MANDATORY AAA pattern."""
        # Arrange - MANDATORY (cache_manager fixture)

        # Act - MANDATORY
        await cache_manager.initialize()

        # Assert - MANDATORY
        assert cache_manager.backend is not None
        assert cache_manager._initialized is True

    async def test_initialize_idempotent(self, cache_manager: CacheManager):
        """Test initialize is idempotent - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        await cache_manager.initialize()
        first_backend = cache_manager.backend

        # Act - MANDATORY
        await cache_manager.initialize()

        # Assert - MANDATORY
        assert cache_manager.backend is first_backend  # Same instance

    async def test_initialize_handles_unsupported_backend(self):
        """Test initialize handles unsupported backend - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        config = CacheConfig(backend="invalid")  # type: ignore
        manager = CacheManager(config)

        # Act - MANDATORY
        await manager.initialize()  # Error handler catches and logs the error

        # Assert - MANDATORY
        # Backend should not be initialized due to error
        assert manager.backend is None

    def test_ensure_backend_raises_if_not_initialized(self, cache_manager: CacheManager):
        """Test _ensure_backend raises if not initialized - MANDATORY AAA pattern."""
        # Arrange - MANDATORY (cache_manager not initialized)

        # Act & Assert - MANDATORY
        with pytest.raises(RuntimeError, match="not initialized"):
            cache_manager._ensure_backend()


# =============================================================================
# TEST CacheManager - HTML Caching
# =============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
class TestCacheManagerHTML:
    """Test CacheManager HTML caching following MANDATORY AAA pattern."""

    async def test_get_html_returns_none_for_missing(self, cache_manager: CacheManager):
        """Test get_html returns None for missing - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        url = "https://example.com/test"

        # Act - MANDATORY
        result = await cache_manager.get_html(url)

        # Assert - MANDATORY
        assert result is None

    async def test_set_and_get_html(self, cache_manager: CacheManager):
        """Test set and get HTML - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        url = "https://example.com/test"
        html_content = "<html><body>Test</body></html>"

        # Act - MANDATORY
        set_result = await cache_manager.set_html(url, html_content)
        get_result = await cache_manager.get_html(url)

        # Assert - MANDATORY
        assert set_result is True
        assert get_result == html_content

    async def test_set_html_with_custom_ttl(self, cache_manager: CacheManager):
        """Test set_html with custom TTL - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        await cache_manager.initialize()
        cache_manager.backend = AsyncMock()
        cache_manager.backend.set = AsyncMock(return_value=True)

        # Act - MANDATORY
        await cache_manager.set_html("https://example.com", "content", ttl=7200)

        # Assert - MANDATORY
        cache_manager.backend.set.assert_called_once()
        args = cache_manager.backend.set.call_args
        assert args[0][2] == 7200  # ttl parameter


# =============================================================================
# TEST CacheManager - Image Caching
# =============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
class TestCacheManagerImage:
    """Test CacheManager image caching following MANDATORY AAA pattern."""

    async def test_get_image_returns_none_for_missing(self, cache_manager: CacheManager):
        """Test get_image returns None for missing - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        image_url = "https://example.com/image.png"

        # Act - MANDATORY
        result = await cache_manager.get_image(image_url)

        # Assert - MANDATORY
        assert result is None

    async def test_set_and_get_image(self, cache_manager: CacheManager):
        """Test set and get image - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        image_url = "https://example.com/image.png"
        image_data = b"fake_image_data"

        # Act - MANDATORY
        set_result = await cache_manager.set_image(image_url, image_data)
        get_result = await cache_manager.get_image(image_url)

        # Assert - MANDATORY
        assert set_result is True
        assert get_result == image_data


# =============================================================================
# TEST CacheManager - Metadata Caching
# =============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
class TestCacheManagerMetadata:
    """Test CacheManager metadata caching following MANDATORY AAA pattern."""

    async def test_get_metadata_returns_none_for_missing(self, cache_manager: CacheManager):
        """Test get_metadata returns None for missing - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        url = "https://example.com/page"

        # Act - MANDATORY
        result = await cache_manager.get_metadata(url)

        # Assert - MANDATORY
        assert result is None

    async def test_set_and_get_metadata(self, cache_manager: CacheManager):
        """Test set and get metadata - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        url = "https://example.com/page"
        metadata = {"title": "Test Page", "author": "Test Author"}

        # Act - MANDATORY
        set_result = await cache_manager.set_metadata(url, metadata)
        get_result = await cache_manager.get_metadata(url)

        # Assert - MANDATORY
        assert set_result is True
        assert get_result == metadata


# =============================================================================
# TEST CacheManager - Robots.txt Caching
# =============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
class TestCacheManagerRobots:
    """Test CacheManager robots.txt caching following MANDATORY AAA pattern."""

    async def test_get_robots_txt_returns_none_for_missing(self, cache_manager: CacheManager):
        """Test get_robots_txt returns None for missing - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        domain = "example.com"

        # Act - MANDATORY
        result = await cache_manager.get_robots_txt(domain)

        # Assert - MANDATORY
        assert result is None

    async def test_set_and_get_robots_txt(self, cache_manager: CacheManager):
        """Test set and get robots.txt - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        domain = "example.com"
        robots_content = "User-agent: *\nDisallow: /admin/"

        # Act - MANDATORY
        set_result = await cache_manager.set_robots_txt(domain, robots_content)
        get_result = await cache_manager.get_robots_txt(domain)

        # Assert - MANDATORY
        assert set_result is True
        assert get_result == robots_content


# =============================================================================
# TEST CacheManager - Cache Invalidation
# =============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
class TestCacheManagerInvalidation:
    """Test CacheManager cache invalidation following MANDATORY AAA pattern."""

    async def test_invalidate_url_removes_html_and_metadata(self, cache_manager: CacheManager):
        """Test invalidate_url removes HTML and metadata - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        url = "https://example.com/test"
        await cache_manager.set_html(url, "<html>content</html>")
        await cache_manager.set_metadata(url, {"title": "Test"})

        # Act - MANDATORY
        result = await cache_manager.invalidate_url(url)

        # Assert - MANDATORY
        assert result is True
        assert await cache_manager.get_html(url) is None
        assert await cache_manager.get_metadata(url) is None

    async def test_invalidate_url_returns_false_for_nonexistent(self, cache_manager: CacheManager):
        """Test invalidate_url returns False for nonexistent - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        url = "https://example.com/nonexistent"

        # Act - MANDATORY
        result = await cache_manager.invalidate_url(url)

        # Assert - MANDATORY
        assert result is False


# =============================================================================
# TEST CacheManager - Statistics
# =============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
class TestCacheManagerStats:
    """Test CacheManager statistics following MANDATORY AAA pattern."""

    async def test_get_cache_stats_returns_statistics(
        self, cache_manager: CacheManager, mock_file_backend: AsyncMock
    ):
        """Test get_cache_stats returns statistics - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        await cache_manager.initialize()
        cache_manager.backend = mock_file_backend

        # Act - MANDATORY
        stats = await cache_manager.get_cache_stats()

        # Assert - MANDATORY
        assert "backend" in stats
        assert "config" in stats
        assert "hits" in stats
        assert "misses" in stats
        assert stats["backend"] == "file"


# =============================================================================
# TEST CacheManager - Cleanup
# =============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
class TestCacheManagerCleanup:
    """Test CacheManager cleanup following MANDATORY AAA pattern."""

    async def test_cleanup_expired_returns_count(
        self, cache_manager: CacheManager, mock_file_backend: AsyncMock
    ):
        """Test cleanup_expired returns count - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        await cache_manager.initialize()
        cache_manager.backend = mock_file_backend

        # Act - MANDATORY
        cleaned = await cache_manager.cleanup_expired()

        # Assert - MANDATORY
        assert cleaned == 5
        mock_file_backend.cleanup_expired.assert_called_once()

    async def test_clear_cache_clears_all_entries(
        self, cache_manager: CacheManager, mock_file_backend: AsyncMock
    ):
        """Test clear_cache clears all entries - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        await cache_manager.initialize()
        cache_manager.backend = mock_file_backend

        # Act - MANDATORY
        result = await cache_manager.clear_cache()

        # Assert - MANDATORY
        assert result is True
        mock_file_backend.clear.assert_called_once()


# =============================================================================
# TEST CacheManager - Key Generation
# =============================================================================


@pytest.mark.unit
class TestCacheManagerKeyGeneration:
    """Test CacheManager key generation following MANDATORY AAA pattern."""

    def test_make_html_key_creates_consistent_key(self, cache_manager: CacheManager):
        """Test _make_html_key creates consistent key - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        url = "https://example.com/test"

        # Act - MANDATORY
        key1 = cache_manager._make_html_key(url)
        key2 = cache_manager._make_html_key(url)

        # Assert - MANDATORY
        assert key1 == key2
        assert key1.startswith("html:")

    def test_make_image_key_creates_consistent_key(self, cache_manager: CacheManager):
        """Test _make_image_key creates consistent key - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        url = "https://example.com/image.png"

        # Act - MANDATORY
        key1 = cache_manager._make_image_key(url)
        key2 = cache_manager._make_image_key(url)

        # Assert - MANDATORY
        assert key1 == key2
        assert key1.startswith("image:")

    def test_make_robots_key_uses_domain_directly(self, cache_manager: CacheManager):
        """Test _make_robots_key uses domain directly - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        domain = "example.com"

        # Act - MANDATORY
        key = cache_manager._make_robots_key(domain)

        # Assert - MANDATORY
        assert key == f"robots:{domain}"

    def test_hash_url_creates_deterministic_hash(self, cache_manager: CacheManager):
        """Test _hash_url creates deterministic hash - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        url = "https://example.com/test"

        # Act - MANDATORY
        hash1 = cache_manager._hash_url(url)
        hash2 = cache_manager._hash_url(url)

        # Assert - MANDATORY
        assert hash1 == hash2
        assert len(hash1) > 0


# =============================================================================
# TEST CacheManager - Backend Type
# =============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
class TestCacheManagerBackendType:
    """Test CacheManager backend type following MANDATORY AAA pattern."""

    def test_backend_type_returns_not_initialized(self):
        """Test backend_type returns not_initialized - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        manager = CacheManager()

        # Act - MANDATORY
        backend_type = manager.backend_type

        # Assert - MANDATORY
        assert backend_type == "not_initialized"

    async def test_backend_type_returns_file_after_init(self, cache_manager: CacheManager):
        """Test backend_type returns file after init - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        await cache_manager.initialize()

        # Act - MANDATORY
        backend_type = cache_manager.backend_type

        # Assert - MANDATORY
        assert backend_type == "file"


# =============================================================================
# TEST CacheManager - Shutdown
# =============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
class TestCacheManagerShutdown:
    """Test CacheManager shutdown following MANDATORY AAA pattern."""

    async def test_shutdown_closes_backend(
        self, cache_manager: CacheManager, mock_file_backend: AsyncMock
    ):
        """Test shutdown closes backend - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        await cache_manager.initialize()
        mock_file_backend.shutdown = AsyncMock()
        cache_manager.backend = mock_file_backend

        # Act - MANDATORY
        await cache_manager.shutdown()

        # Assert - MANDATORY
        assert cache_manager._initialized is False
        mock_file_backend.shutdown.assert_called_once()


# =============================================================================
# MANDATORY SECURITY TESTS
# =============================================================================


@pytest.mark.security
class TestCacheManagerSecurity:
    """MANDATORY security tests for cache manager."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_set_html_handles_malicious_urls_safely(self, cache_manager: CacheManager):
        """MANDATORY security test - set_html handles malicious URLs safely."""
        # Arrange - MANDATORY
        malicious_urls = [
            "https://example.com/../../etc/passwd",
            "https://example.com/<script>alert('xss')</script>",
            "file:///etc/passwd",
            "javascript:alert(1)",
        ]

        for malicious_url in malicious_urls:
            # Act - MANDATORY
            result = await cache_manager.set_html(malicious_url, "content")

            # Assert - MANDATORY (security check)
            assert result is True
            # URL should be hashed, preventing direct access
            key = cache_manager._make_html_key(malicious_url)
            assert "../" not in key
            assert "<script>" not in key

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_set_metadata_handles_malicious_values_safely(self, cache_manager: CacheManager):
        """MANDATORY security test - set_metadata handles malicious values safely."""
        # Arrange - MANDATORY
        url = "https://example.com/test"
        malicious_metadata = {
            "title": "<script>alert('xss')</script>",
            "sql": "'; DROP TABLE cache; --",
            "path": "../../etc/passwd",
        }

        # Act - MANDATORY
        result = await cache_manager.set_metadata(url, malicious_metadata)

        # Assert - MANDATORY (security check)
        assert result is True
        retrieved = await cache_manager.get_metadata(url)
        assert retrieved == malicious_metadata  # Should store as-is


# =============================================================================
# MANDATORY PERFORMANCE TESTS
# =============================================================================


@pytest.mark.performance
class TestCacheManagerPerformance:
    """MANDATORY performance tests for cache manager."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_set_html_performance_benchmark(self, cache_manager: CacheManager):
        """MANDATORY performance test - set_html completes quickly."""
        # Arrange - MANDATORY
        iterations = 50
        start_time = time.perf_counter()

        # Act - MANDATORY
        for i in range(iterations):
            await cache_manager.set_html(f"https://example.com/page{i}", f"<html>{i}</html>")

        end_time = time.perf_counter()
        execution_time = end_time - start_time

        # Assert - MANDATORY (performance requirement)
        avg_time = execution_time / iterations
        assert avg_time < 0.02  # Less than 20ms per set operation
        assert execution_time < 1.0  # Total under 1 second for 50 sets

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_html_performance_benchmark(self, cache_manager: CacheManager):
        """MANDATORY performance test - get_html completes quickly."""
        # Arrange - MANDATORY
        iterations = 50
        # Pre-populate cache
        for i in range(iterations):
            await cache_manager.set_html(f"https://example.com/page{i}", f"<html>{i}</html>")

        start_time = time.perf_counter()

        # Act - MANDATORY
        for i in range(iterations):
            await cache_manager.get_html(f"https://example.com/page{i}")

        end_time = time.perf_counter()
        execution_time = end_time - start_time

        # Assert - MANDATORY (performance requirement)
        avg_time = execution_time / iterations
        assert avg_time < 0.01  # Less than 10ms per get operation
        assert execution_time < 0.5  # Total under 500ms for 50 gets
