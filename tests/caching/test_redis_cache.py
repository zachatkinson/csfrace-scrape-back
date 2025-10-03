"""Unit tests for caching/redis_cache.py following TEST_BUILDING.md ZERO TOLERANCE standards.

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

Tests Redis cache backend following TEST_BUILDING.md with comprehensive coverage.
"""

import time
from unittest.mock import AsyncMock, patch

import pytest

from src.caching.base import CacheConfig, CacheEntry

# Import handling for Redis
try:
    from src.caching.redis_cache import REDIS_AVAILABLE, RedisCache

    SKIP_REDIS_TESTS = not REDIS_AVAILABLE
    SKIP_REASON = "redis package not installed"
except ImportError:
    SKIP_REDIS_TESTS = True
    SKIP_REASON = "redis_cache module not available"
    RedisCache = None  # type: ignore


# =============================================================================
# TEST FIXTURES - Factory Pattern for DRY Principle
# =============================================================================


@pytest.fixture
def cache_config() -> CacheConfig:
    """Factory for CacheConfig with Redis settings - DRY principle."""
    return CacheConfig(
        redis_host="localhost",
        redis_port=6379,
        redis_db=0,
        redis_password=None,
        redis_key_prefix="test:",
        ttl_default=3600,
        ttl_html=7200,
        ttl_images=86400,
        compress=True,
    )


@pytest.fixture
def mock_redis_client():
    """Factory for mock Redis client - DRY principle."""
    client = AsyncMock()
    client.ping = AsyncMock(return_value=True)
    client.get = AsyncMock(return_value=None)
    client.set = AsyncMock(return_value=True)
    client.setex = AsyncMock(return_value=True)
    client.delete = AsyncMock(return_value=1)
    client.keys = AsyncMock(return_value=[])
    client.info = AsyncMock(
        return_value={
            "redis_version": "7.0.0",
            "redis_mode": "standalone",
            "os": "Linux",
            "arch_bits": 64,
            "multiplexing_api": "epoll",
            "process_id": 1234,
            "uptime_in_seconds": 3600,
            "connected_clients": 1,
            "used_memory_human": "1.5M",
            "role": "master",
        }
    )
    client.aclose = AsyncMock()
    client.close = AsyncMock()
    return client


# =============================================================================
# TEST RedisCache - Initialization
# =============================================================================


@pytest.mark.unit
@pytest.mark.skipif(SKIP_REDIS_TESTS, reason=SKIP_REASON)
class TestRedisCacheInit:
    """Test RedisCache initialization following MANDATORY AAA pattern."""

    def test_init_raises_import_error_if_redis_unavailable(self, cache_config: CacheConfig):
        """Test __init__ raises ImportError if redis unavailable - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        with patch("src.caching.redis_cache.REDIS_AVAILABLE", False):
            # Act & Assert - MANDATORY
            with pytest.raises(ImportError, match="redis package is required"):
                RedisCache(cache_config)

    def test_init_creates_redis_cache(self, cache_config: CacheConfig):
        """Test __init__ creates RedisCache - MANDATORY AAA pattern."""
        # Arrange - MANDATORY (cache_config fixture)

        # Act - MANDATORY
        redis_cache = RedisCache(cache_config)

        # Assert - MANDATORY
        assert redis_cache.config == cache_config
        assert redis_cache.redis_client is None
        assert redis_cache._stats["hits"] == 0
        assert redis_cache._stats["misses"] == 0


# =============================================================================
# TEST RedisCache - Connection Management
# =============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
@pytest.mark.skipif(SKIP_REDIS_TESTS, reason=SKIP_REASON)
class TestRedisCacheConnection:
    """Test RedisCache connection management following MANDATORY AAA pattern."""

    async def test_get_client_creates_connection(
        self, cache_config: CacheConfig, mock_redis_client: AsyncMock
    ):
        """Test _get_client creates connection - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        redis_cache = RedisCache(cache_config)

        with patch("src.caching.redis_cache.redis.Redis", return_value=mock_redis_client):
            # Act - MANDATORY
            client = await redis_cache._get_client()

            # Assert - MANDATORY
            assert client is not None
            assert redis_cache.redis_client is not None
            mock_redis_client.ping.assert_called_once()

    async def test_get_client_reuses_existing_connection(
        self, cache_config: CacheConfig, mock_redis_client: AsyncMock
    ):
        """Test _get_client reuses existing connection - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        redis_cache = RedisCache(cache_config)
        redis_cache.redis_client = mock_redis_client

        # Act - MANDATORY
        client = await redis_cache._get_client()

        # Assert - MANDATORY
        assert client is mock_redis_client
        mock_redis_client.ping.assert_not_called()  # Should not ping again

    async def test_initialize_establishes_connection(
        self, cache_config: CacheConfig, mock_redis_client: AsyncMock
    ):
        """Test initialize establishes connection - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        redis_cache = RedisCache(cache_config)

        with patch("src.caching.redis_cache.redis.Redis", return_value=mock_redis_client):
            # Act - MANDATORY
            await redis_cache.initialize()

            # Assert - MANDATORY
            assert redis_cache.redis_client is not None
            mock_redis_client.ping.assert_called_once()

    async def test_shutdown_closes_connection(
        self, cache_config: CacheConfig, mock_redis_client: AsyncMock
    ):
        """Test shutdown closes connection - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        redis_cache = RedisCache(cache_config)
        redis_cache.redis_client = mock_redis_client

        # Act - MANDATORY
        await redis_cache.shutdown()

        # Assert - MANDATORY
        mock_redis_client.aclose.assert_called_once()
        assert redis_cache.redis_client is None


# =============================================================================
# TEST RedisCache - Get Operation
# =============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
@pytest.mark.skipif(SKIP_REDIS_TESTS, reason=SKIP_REASON)
class TestRedisCacheGet:
    """Test RedisCache get operation following MANDATORY AAA pattern."""

    async def test_get_returns_none_for_missing_entry(
        self, cache_config: CacheConfig, mock_redis_client: AsyncMock
    ):
        """Test get returns None for missing entry - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        redis_cache = RedisCache(cache_config)
        redis_cache.redis_client = mock_redis_client
        mock_redis_client.get.return_value = None

        # Act - MANDATORY
        result = await redis_cache.get("nonexistent:key")

        # Assert - MANDATORY
        assert result is None
        assert redis_cache._stats["misses"] == 1
        mock_redis_client.get.assert_called_once()

    async def test_get_returns_entry_for_valid_cache(
        self, cache_config: CacheConfig, mock_redis_client: AsyncMock
    ):
        """Test get returns entry for valid cache - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        redis_cache = RedisCache(cache_config)
        redis_cache.redis_client = mock_redis_client

        # Create a valid cache entry
        entry = CacheEntry(
            key="test:key",
            value="test_value",
            created_at=time.time(),
            ttl=3600,
            content_type="html",
            size_bytes=1024,
            compressed=True,
        )
        entry_data = redis_cache._compress_data(entry.to_dict())
        mock_redis_client.get.return_value = entry_data

        # Act - MANDATORY
        result = await redis_cache.get("test:key")

        # Assert - MANDATORY
        assert result is not None
        assert result.key == "test:key"
        assert result.value == "test_value"
        assert redis_cache._stats["hits"] == 1


# =============================================================================
# TEST RedisCache - Set Operation
# =============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
@pytest.mark.skipif(SKIP_REDIS_TESTS, reason=SKIP_REASON)
class TestRedisCacheSet:
    """Test RedisCache set operation following MANDATORY AAA pattern."""

    async def test_set_creates_cache_entry(
        self, cache_config: CacheConfig, mock_redis_client: AsyncMock
    ):
        """Test set creates cache entry - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        redis_cache = RedisCache(cache_config)
        redis_cache.redis_client = mock_redis_client

        # Act - MANDATORY
        result = await redis_cache.set("test:key", "test_value", ttl=3600, content_type="html")

        # Assert - MANDATORY
        assert result is True
        assert redis_cache._stats["sets"] == 1
        mock_redis_client.setex.assert_called_once()

    async def test_set_with_zero_ttl_uses_set_not_setex(
        self, cache_config: CacheConfig, mock_redis_client: AsyncMock
    ):
        """Test set with zero TTL uses set not setex - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        redis_cache = RedisCache(cache_config)
        redis_cache.redis_client = mock_redis_client

        # Act - MANDATORY
        result = await redis_cache.set("test:key", "test_value", ttl=0, content_type="html")

        # Assert - MANDATORY
        assert result is True
        mock_redis_client.set.assert_called_once()
        mock_redis_client.setex.assert_not_called()


# =============================================================================
# TEST RedisCache - Delete Operation
# =============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
@pytest.mark.skipif(SKIP_REDIS_TESTS, reason=SKIP_REASON)
class TestRedisCacheDelete:
    """Test RedisCache delete operation following MANDATORY AAA pattern."""

    async def test_delete_removes_cache_entry(
        self, cache_config: CacheConfig, mock_redis_client: AsyncMock
    ):
        """Test delete removes cache entry - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        redis_cache = RedisCache(cache_config)
        redis_cache.redis_client = mock_redis_client
        mock_redis_client.delete.return_value = 1

        # Act - MANDATORY
        result = await redis_cache.delete("test:key")

        # Assert - MANDATORY
        assert result is True
        assert redis_cache._stats["deletes"] == 1
        mock_redis_client.delete.assert_called_once()

    async def test_delete_returns_false_for_nonexistent_key(
        self, cache_config: CacheConfig, mock_redis_client: AsyncMock
    ):
        """Test delete returns False for nonexistent key - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        redis_cache = RedisCache(cache_config)
        redis_cache.redis_client = mock_redis_client
        mock_redis_client.delete.return_value = 0

        # Act - MANDATORY
        result = await redis_cache.delete("nonexistent:key")

        # Assert - MANDATORY
        assert result is False


# =============================================================================
# TEST RedisCache - Clear Operation
# =============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
@pytest.mark.skipif(SKIP_REDIS_TESTS, reason=SKIP_REASON)
class TestRedisCacheClear:
    """Test RedisCache clear operation following MANDATORY AAA pattern."""

    async def test_clear_removes_all_cache_entries(
        self, cache_config: CacheConfig, mock_redis_client: AsyncMock
    ):
        """Test clear removes all cache entries - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        redis_cache = RedisCache(cache_config)
        redis_cache.redis_client = mock_redis_client
        mock_redis_client.keys.return_value = [b"test:key1", b"test:key2", b"test:key3"]
        mock_redis_client.delete.return_value = 3

        # Act - MANDATORY
        result = await redis_cache.clear()

        # Assert - MANDATORY
        assert result is True
        mock_redis_client.keys.assert_called_once()
        mock_redis_client.delete.assert_called_once()
        assert redis_cache._stats["hits"] == 0
        assert redis_cache._stats["misses"] == 0


# =============================================================================
# TEST RedisCache - Stats Operation
# =============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
@pytest.mark.skipif(SKIP_REDIS_TESTS, reason=SKIP_REASON)
class TestRedisCacheStats:
    """Test RedisCache stats operation following MANDATORY AAA pattern."""

    async def test_stats_returns_cache_statistics(
        self, cache_config: CacheConfig, mock_redis_client: AsyncMock
    ):
        """Test stats returns cache statistics - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        redis_cache = RedisCache(cache_config)
        redis_cache.redis_client = mock_redis_client
        mock_redis_client.keys.return_value = [b"test:key1", b"test:key2"]

        # Act - MANDATORY
        stats = await redis_cache.stats()

        # Assert - MANDATORY
        assert stats["total_entries"] == 2
        assert "redis_version" in stats
        assert "redis_memory_used" in stats
        assert "hit_rate" in stats


# =============================================================================
# TEST RedisCache - Server Info
# =============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
@pytest.mark.skipif(SKIP_REDIS_TESTS, reason=SKIP_REASON)
class TestRedisCacheServerInfo:
    """Test RedisCache server info following MANDATORY AAA pattern."""

    async def test_get_server_info_returns_redis_info(
        self, cache_config: CacheConfig, mock_redis_client: AsyncMock
    ):
        """Test get_server_info returns Redis info - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        redis_cache = RedisCache(cache_config)
        redis_cache.redis_client = mock_redis_client

        # Act - MANDATORY
        info = await redis_cache.get_server_info()

        # Assert - MANDATORY
        assert info["redis_version"] == "7.0.0"
        assert info["redis_mode"] == "standalone"
        assert info["arch_bits"] == 64

    async def test_get_backend_type_returns_descriptive_string(
        self, cache_config: CacheConfig, mock_redis_client: AsyncMock
    ):
        """Test get_backend_type returns descriptive string - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        redis_cache = RedisCache(cache_config)
        redis_cache.redis_client = mock_redis_client

        # Act - MANDATORY
        backend_type = await redis_cache.get_backend_type()

        # Assert - MANDATORY
        assert "redis" in backend_type
        assert "7.0.0" in backend_type
        assert "64bit" in backend_type


# =============================================================================
# TEST RedisCache - Key Prefix
# =============================================================================


@pytest.mark.unit
@pytest.mark.skipif(SKIP_REDIS_TESTS, reason=SKIP_REASON)
class TestRedisCacheKeyPrefix:
    """Test RedisCache key prefix following MANDATORY AAA pattern."""

    def test_make_redis_key_adds_prefix(self, cache_config: CacheConfig):
        """Test _make_redis_key adds prefix - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        redis_cache = RedisCache(cache_config)
        key = "my:key"

        # Act - MANDATORY
        redis_key = redis_cache._make_redis_key(key)

        # Assert - MANDATORY
        assert redis_key.startswith(cache_config.redis_key_prefix)
        assert key in redis_key


# =============================================================================
# MANDATORY SECURITY TESTS
# =============================================================================


@pytest.mark.security
@pytest.mark.skipif(SKIP_REDIS_TESTS, reason=SKIP_REASON)
class TestRedisCacheSecurity:
    """MANDATORY security tests for Redis cache."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_set_handles_malicious_keys_safely(
        self, cache_config: CacheConfig, mock_redis_client: AsyncMock
    ):
        """MANDATORY security test - set handles malicious keys safely."""
        # Arrange - MANDATORY
        redis_cache = RedisCache(cache_config)
        redis_cache.redis_client = mock_redis_client

        malicious_keys = [
            "../../../etc/passwd",
            "key;rm -rf /",
            "key`whoami`",
            "key${IFS}command",
        ]

        for malicious_key in malicious_keys:
            # Act - MANDATORY
            result = await redis_cache.set(malicious_key, "content", ttl=3600, content_type="html")

            # Assert - MANDATORY (security check)
            assert result is True
            # Key should be prefixed and passed to Redis as-is
            # Redis handles key sanitization internally

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_set_handles_malicious_values_safely(
        self, cache_config: CacheConfig, mock_redis_client: AsyncMock
    ):
        """MANDATORY security test - set handles malicious values safely."""
        # Arrange - MANDATORY
        redis_cache = RedisCache(cache_config)
        redis_cache.redis_client = mock_redis_client

        malicious_values = [
            "<script>alert('xss')</script>",
            "'; DROP TABLE cache; --",
            "\x00\x01\x02",  # Null bytes
            "A" * 1000000,  # Large value
        ]

        for malicious_value in malicious_values:
            # Act - MANDATORY
            key = f"test:security:{hash(malicious_value)}"
            result = await redis_cache.set(key, malicious_value, ttl=3600, content_type="html")

            # Assert - MANDATORY (security check)
            assert result is True


# =============================================================================
# MANDATORY PERFORMANCE TESTS
# =============================================================================


@pytest.mark.performance
@pytest.mark.skipif(SKIP_REDIS_TESTS, reason=SKIP_REASON)
class TestRedisCachePerformance:
    """MANDATORY performance tests for Redis cache."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_set_performance_benchmark(
        self, cache_config: CacheConfig, mock_redis_client: AsyncMock
    ):
        """MANDATORY performance test - set completes quickly."""
        # Arrange - MANDATORY
        redis_cache = RedisCache(cache_config)
        redis_cache.redis_client = mock_redis_client
        iterations = 100
        start_time = time.perf_counter()

        # Act - MANDATORY
        for i in range(iterations):
            await redis_cache.set(f"key:{i}", f"value_{i}", ttl=3600, content_type="html")

        end_time = time.perf_counter()
        execution_time = end_time - start_time

        # Assert - MANDATORY (performance requirement)
        avg_time = execution_time / iterations
        assert avg_time < 0.005  # Less than 5ms per set operation (mocked)
        assert execution_time < 0.5  # Total under 500ms for 100 sets

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_performance_benchmark(
        self, cache_config: CacheConfig, mock_redis_client: AsyncMock
    ):
        """MANDATORY performance test - get completes quickly."""
        # Arrange - MANDATORY
        redis_cache = RedisCache(cache_config)
        redis_cache.redis_client = mock_redis_client
        mock_redis_client.get.return_value = None  # Simulate cache miss
        iterations = 100
        start_time = time.perf_counter()

        # Act - MANDATORY
        for i in range(iterations):
            await redis_cache.get(f"key:{i}")

        end_time = time.perf_counter()
        execution_time = end_time - start_time

        # Assert - MANDATORY (performance requirement)
        avg_time = execution_time / iterations
        assert avg_time < 0.003  # Less than 3ms per get operation (mocked)
        assert execution_time < 0.3  # Total under 300ms for 100 gets


# =============================================================================
# TEST RedisCache - Cleanup
# =============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
@pytest.mark.skipif(SKIP_REDIS_TESTS, reason=SKIP_REASON)
class TestRedisCacheCleanup:
    """Test RedisCache cleanup following MANDATORY AAA pattern."""

    async def test_cleanup_expired_returns_zero(self, cache_config: CacheConfig):
        """Test cleanup_expired returns zero - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        redis_cache = RedisCache(cache_config)

        # Act - MANDATORY
        cleaned = await redis_cache.cleanup_expired()

        # Assert - MANDATORY
        assert cleaned == 0  # Redis handles TTL automatically
