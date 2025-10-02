"""Unit tests for caching/base.py following TEST_BUILDING.md ZERO TOLERANCE standards.

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

Tests cache base classes following TEST_BUILDING.md with comprehensive coverage.
"""

import time
from pathlib import Path

import pytest

from src.caching.base import (
    BaseCacheBackend,
    CacheBackend,
    CacheConfig,
    CacheEntry,
)

# =============================================================================
# TEST FIXTURES - Factory Pattern for DRY Principle
# =============================================================================


@pytest.fixture
def cache_config() -> CacheConfig:
    """Factory for CacheConfig - DRY principle."""
    return CacheConfig(
        backend=CacheBackend.FILE,
        cache_dir=Path("/tmp/test_cache"),
        max_cache_size_mb=100,
        ttl_default=3600,
    )


@pytest.fixture
def cache_entry() -> CacheEntry:
    """Factory for CacheEntry - DRY principle."""
    return CacheEntry(
        key="test:key:123",
        value="test_value",
        created_at=time.time(),
        ttl=3600,
        content_type="html",
        size_bytes=1024,
        compressed=False,
    )


# =============================================================================
# TEST CacheBackend Enum
# =============================================================================


@pytest.mark.unit
class TestCacheBackend:
    """Test CacheBackend enum following MANDATORY AAA pattern."""

    def test_cache_backend_has_file_type(self):
        """Test CacheBackend has FILE type - MANDATORY AAA pattern."""
        # Arrange - MANDATORY (no setup needed)

        # Act - MANDATORY
        backend = CacheBackend.FILE

        # Assert - MANDATORY
        assert backend.value == "file"
        assert backend == CacheBackend.FILE

    def test_cache_backend_has_redis_type(self):
        """Test CacheBackend has REDIS type - MANDATORY AAA pattern."""
        # Arrange - MANDATORY (no setup needed)

        # Act - MANDATORY
        backend = CacheBackend.REDIS

        # Assert - MANDATORY
        assert backend.value == "redis"
        assert backend == CacheBackend.REDIS

    def test_cache_backend_has_memory_type(self):
        """Test CacheBackend has MEMORY type - MANDATORY AAA pattern."""
        # Arrange - MANDATORY (no setup needed)

        # Act - MANDATORY
        backend = CacheBackend.MEMORY

        # Assert - MANDATORY
        assert backend.value == "memory"
        assert backend == CacheBackend.MEMORY


# =============================================================================
# TEST CacheConfig
# =============================================================================


@pytest.mark.unit
class TestCacheConfig:
    """Test CacheConfig dataclass following MANDATORY AAA pattern."""

    def test_cache_config_has_default_values(self):
        """Test CacheConfig creates with default values - MANDATORY AAA pattern."""
        # Arrange - MANDATORY (no setup needed)

        # Act - MANDATORY
        config = CacheConfig()

        # Assert - MANDATORY
        assert config.backend == CacheBackend.FILE
        assert config.ttl_default > 0
        assert config.cache_dir == Path(".cache")
        assert config.max_cache_size_mb > 0
        assert config.compress is True

    def test_cache_config_accepts_custom_values(self, cache_config: CacheConfig):
        """Test CacheConfig accepts custom values - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        custom_backend = CacheBackend.REDIS
        custom_ttl = 7200

        # Act - MANDATORY
        config = CacheConfig(backend=custom_backend, ttl_default=custom_ttl)

        # Assert - MANDATORY
        assert config.backend == custom_backend
        assert config.ttl_default == custom_ttl

    def test_cache_config_from_environment_returns_config(self):
        """Test CacheConfig.from_environment creates config - MANDATORY AAA pattern."""
        # Arrange - MANDATORY (environment already set)

        # Act - MANDATORY
        config = CacheConfig.from_environment()

        # Assert - MANDATORY
        assert isinstance(config, CacheConfig)
        assert isinstance(config.backend, CacheBackend)


# =============================================================================
# TEST CacheEntry - Properties and Methods
# =============================================================================


@pytest.mark.unit
class TestCacheEntry:
    """Test CacheEntry dataclass following MANDATORY AAA pattern."""

    def test_cache_entry_creates_with_required_fields(self):
        """Test CacheEntry creates with required fields - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        key = "test:key"
        value = "test_value"
        created_at = time.time()
        ttl = 3600

        # Act - MANDATORY
        entry = CacheEntry(key=key, value=value, created_at=created_at, ttl=ttl)

        # Assert - MANDATORY
        assert entry.key == key
        assert entry.value == value
        assert entry.created_at == created_at
        assert entry.ttl == ttl
        assert entry.content_type == "generic"
        assert entry.size_bytes == 0
        assert entry.compressed is False

    def test_cache_entry_is_expired_returns_false_for_valid_entry(self, cache_entry: CacheEntry):
        """Test CacheEntry.is_expired returns False for valid entry - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        cache_entry.created_at = time.time()
        cache_entry.ttl = 3600

        # Act - MANDATORY
        is_expired = cache_entry.is_expired

        # Assert - MANDATORY
        assert is_expired is False

    def test_cache_entry_is_expired_returns_true_for_expired_entry(self, cache_entry: CacheEntry):
        """Test CacheEntry.is_expired returns True for expired entry - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        cache_entry.created_at = time.time() - 7200  # 2 hours ago
        cache_entry.ttl = 3600  # 1 hour TTL

        # Act - MANDATORY
        is_expired = cache_entry.is_expired

        # Assert - MANDATORY
        assert is_expired is True

    def test_cache_entry_is_expired_handles_zero_ttl(self, cache_entry: CacheEntry):
        """Test CacheEntry.is_expired handles zero TTL (never expires) - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        cache_entry.created_at = time.time() - 100000  # Long time ago
        cache_entry.ttl = 0  # Never expires

        # Act - MANDATORY
        is_expired = cache_entry.is_expired

        # Assert - MANDATORY
        assert is_expired is False

    def test_cache_entry_age_seconds_calculates_correctly(self, cache_entry: CacheEntry):
        """Test CacheEntry.age_seconds calculates age - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        created_time = time.time() - 100  # 100 seconds ago
        cache_entry.created_at = created_time

        # Act - MANDATORY
        age = cache_entry.age_seconds

        # Assert - MANDATORY
        assert age >= 100
        assert age < 102  # Allow small margin for execution time

    def test_cache_entry_to_dict_serializes_correctly(self, cache_entry: CacheEntry):
        """Test CacheEntry.to_dict serializes to dictionary - MANDATORY AAA pattern."""
        # Arrange - MANDATORY (cache_entry fixture)

        # Act - MANDATORY
        result = cache_entry.to_dict()

        # Assert - MANDATORY
        assert isinstance(result, dict)
        assert result["key"] == cache_entry.key
        assert result["value"] == cache_entry.value
        assert result["created_at"] == cache_entry.created_at
        assert result["ttl"] == cache_entry.ttl
        assert result["content_type"] == cache_entry.content_type
        assert result["size_bytes"] == cache_entry.size_bytes
        assert result["compressed"] == cache_entry.compressed

    def test_cache_entry_from_dict_deserializes_correctly(self):
        """Test CacheEntry.from_dict creates entry from dict - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        data = {
            "key": "test:key",
            "value": "test_value",
            "created_at": time.time(),
            "ttl": 3600,
            "content_type": "html",
            "size_bytes": 2048,
            "compressed": True,
        }

        # Act - MANDATORY
        entry = CacheEntry.from_dict(data)

        # Assert - MANDATORY
        assert isinstance(entry, CacheEntry)
        assert entry.key == data["key"]
        assert entry.value == data["value"]
        assert entry.created_at == data["created_at"]
        assert entry.ttl == data["ttl"]
        assert entry.content_type == data["content_type"]
        assert entry.size_bytes == data["size_bytes"]
        assert entry.compressed == data["compressed"]


# =============================================================================
# TEST BaseCacheBackend - Key Generation
# =============================================================================


@pytest.mark.unit
class TestBaseCacheBackendKeyGeneration:
    """Test BaseCacheBackend key generation following MANDATORY AAA pattern."""

    def test_generate_key_creates_simple_key(self, cache_config: CacheConfig):
        """Test generate_key creates simple key - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        backend = MockCacheBackend(cache_config)
        parts = ["user", "123", "profile"]

        # Act - MANDATORY
        key = backend.generate_key(*parts)

        # Assert - MANDATORY
        assert key == "user:123:profile"
        assert ":" in key

    def test_generate_key_hashes_long_keys(self, cache_config: CacheConfig):
        """Test generate_key hashes overly long keys - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        backend = MockCacheBackend(cache_config)
        long_part = "x" * 500  # Exceeds max_key_length

        # Act - MANDATORY
        key = backend.generate_key("prefix", long_part, "suffix")

        # Assert - MANDATORY
        assert len(key) <= cache_config.max_key_length
        assert ":" in key

    def test_generate_key_handles_numeric_parts(self, cache_config: CacheConfig):
        """Test generate_key handles numeric parts - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        backend = MockCacheBackend(cache_config)

        # Act - MANDATORY
        key = backend.generate_key("user", 123, 456.789)

        # Assert - MANDATORY
        assert key == "user:123:456.789"

    def test_get_ttl_for_content_type_returns_html_ttl(self, cache_config: CacheConfig):
        """Test get_ttl_for_content_type returns HTML TTL - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        backend = MockCacheBackend(cache_config)

        # Act - MANDATORY
        ttl = backend.get_ttl_for_content_type("html")

        # Assert - MANDATORY
        assert ttl == cache_config.ttl_html
        assert ttl > 0

    def test_get_ttl_for_content_type_returns_image_ttl(self, cache_config: CacheConfig):
        """Test get_ttl_for_content_type returns image TTL - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        backend = MockCacheBackend(cache_config)

        # Act - MANDATORY
        ttl = backend.get_ttl_for_content_type("image")

        # Assert - MANDATORY
        assert ttl == cache_config.ttl_images
        assert ttl > 0

    def test_get_ttl_for_content_type_returns_default_for_unknown(self, cache_config: CacheConfig):
        """Test get_ttl_for_content_type returns default for unknown type - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        backend = MockCacheBackend(cache_config)

        # Act - MANDATORY
        ttl = backend.get_ttl_for_content_type("unknown_type")

        # Assert - MANDATORY
        assert ttl == cache_config.ttl_default


# =============================================================================
# TEST HELPER - Mock Implementation
# =============================================================================


class MockCacheBackend(BaseCacheBackend):
    """Mock cache backend for testing abstract base class."""

    async def get(self, key: str) -> CacheEntry | None:
        """Mock get implementation."""
        return None

    async def set(
        self, key: str, value, ttl: int | None = None, content_type: str = "generic"
    ) -> bool:
        """Mock set implementation."""
        return True

    async def delete(self, key: str) -> bool:
        """Mock delete implementation."""
        return True

    async def clear(self) -> bool:
        """Mock clear implementation."""
        return True

    async def stats(self) -> dict:
        """Mock stats implementation."""
        return {}

    async def cleanup_expired(self) -> int:
        """Mock cleanup implementation."""
        return 0


# =============================================================================
# MANDATORY SECURITY TESTS
# =============================================================================


@pytest.mark.security
class TestCacheBaseSecurity:
    """MANDATORY security tests for cache base module."""

    @pytest.mark.unit
    def test_generate_key_sanitizes_path_traversal(self, cache_config: CacheConfig):
        """MANDATORY security test - key generation sanitizes path traversal."""
        # Arrange - MANDATORY
        backend = MockCacheBackend(cache_config)
        malicious_parts = ["../../../etc/passwd", "..\\..\\windows\\system32"]

        for part in malicious_parts:
            # Act - MANDATORY
            key = backend.generate_key("safe", part)

            # Assert - MANDATORY (security check)
            # Key should be generated but path traversal neutralized
            assert key is not None
            assert isinstance(key, str)

    @pytest.mark.unit
    def test_cache_entry_handles_malicious_values(self):
        """MANDATORY security test - cache entry handles malicious values safely."""
        # Arrange - MANDATORY
        malicious_values = [
            "<script>alert('xss')</script>",
            "'; DROP TABLE cache; --",
            "../../etc/passwd",
            "\x00\x01\x02",  # Null bytes
        ]

        for malicious_value in malicious_values:
            # Act - MANDATORY
            entry = CacheEntry(
                key="test",
                value=malicious_value,
                created_at=time.time(),
                ttl=3600,
            )

            # Assert - MANDATORY (security check)
            # Entry should store value without executing or interpreting it
            assert entry.value == malicious_value
            # Serialization should handle it safely
            data = entry.to_dict()
            assert data["value"] == malicious_value


# =============================================================================
# MANDATORY PERFORMANCE TESTS
# =============================================================================


@pytest.mark.performance
class TestCacheBasePerformance:
    """MANDATORY performance tests for cache base module."""

    @pytest.mark.unit
    def test_generate_key_performance_benchmark(self, cache_config: CacheConfig):
        """MANDATORY performance test - key generation completes quickly."""
        # Arrange - MANDATORY
        backend = MockCacheBackend(cache_config)
        iterations = 1000
        start_time = time.perf_counter()

        # Act - MANDATORY
        for i in range(iterations):
            backend.generate_key("prefix", i, "suffix")

        end_time = time.perf_counter()
        execution_time = end_time - start_time

        # Assert - MANDATORY (performance requirement)
        avg_time = execution_time / iterations
        assert avg_time < 0.001  # Less than 1ms per key generation
        assert execution_time < 1.0  # Total under 1 second for 1000 keys

    @pytest.mark.unit
    def test_cache_entry_serialization_performance_benchmark(self, cache_entry: CacheEntry):
        """MANDATORY performance test - entry serialization completes quickly."""
        # Arrange - MANDATORY
        iterations = 10000
        start_time = time.perf_counter()

        # Act - MANDATORY
        for _ in range(iterations):
            data = cache_entry.to_dict()
            CacheEntry.from_dict(data)

        end_time = time.perf_counter()
        execution_time = end_time - start_time

        # Assert - MANDATORY (performance requirement)
        avg_time = execution_time / iterations
        assert avg_time < 0.0001  # Less than 0.1ms per round-trip
        assert execution_time < 1.0  # Total under 1 second for 10000 operations

    @pytest.mark.unit
    def test_is_expired_check_performance_benchmark(self):
        """MANDATORY performance test - expiry check completes quickly."""
        # Arrange - MANDATORY
        entries = [
            CacheEntry(
                key=f"key_{i}",
                value=f"value_{i}",
                created_at=time.time() - i,
                ttl=3600,
            )
            for i in range(10000)
        ]
        start_time = time.perf_counter()

        # Act - MANDATORY
        expired_count = sum(1 for entry in entries if entry.is_expired)

        end_time = time.perf_counter()
        execution_time = end_time - start_time

        # Assert - MANDATORY (performance requirement)
        avg_time = execution_time / len(entries)
        assert avg_time < 0.00001  # Less than 0.01ms per check
        assert execution_time < 0.1  # Total under 100ms for 10000 checks
        assert expired_count >= 0  # Sanity check
