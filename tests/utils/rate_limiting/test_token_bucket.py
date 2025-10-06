"""Comprehensive tests for token bucket rate limiter - MANDATORY TEST_BUILDING.md compliance.

This module tests token bucket algorithm implementation with complete coverage:
- TokenBucketConfig validation and initialization
- TokenBucket consume and refill operations
- Token availability and wait time calculations
- TokenBucketPool management and cleanup
- Concurrent access and thread safety
- Performance benchmarks

ALL tests follow MANDATORY TEST_BUILDING.md patterns:
- AAA pattern with explicit comments
- Factory fixtures for DRY principle
- Comprehensive rate limiting scenario testing
- Performance benchmarks with specific thresholds
"""

import time

import asyncio
import pytest

from src.utils.rate_limiting.token_bucket import (
    TokenBucket,
    TokenBucketConfig,
    TokenBucketPool,
)

# ============================================================================
# Test Fixtures - DRY Principle
# ============================================================================


@pytest.fixture
def standard_config() -> TokenBucketConfig:
    """Factory for standard token bucket config - DRY principle."""
    return TokenBucketConfig(capacity=10, refill_rate=2.0)


@pytest.fixture
def burst_config() -> TokenBucketConfig:
    """Factory for burst-capable config - DRY principle."""
    return TokenBucketConfig(capacity=100, refill_rate=10.0, initial_tokens=100)


@pytest.fixture
def token_bucket(standard_config: TokenBucketConfig) -> TokenBucket:
    """Factory for token bucket instance - DRY principle."""
    return TokenBucket(standard_config)


@pytest.fixture
def token_bucket_pool(standard_config: TokenBucketConfig) -> TokenBucketPool:
    """Factory for token bucket pool - DRY principle."""
    return TokenBucketPool(default_config=standard_config, max_buckets=100)


# ============================================================================
# TokenBucketConfig Tests
# ============================================================================


@pytest.mark.unit
class TestTokenBucketConfig:
    """Tests for TokenBucketConfig dataclass."""

    def test_token_bucket_config_valid_initialization(self) -> None:
        """Test config with valid parameters - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        capacity = 10
        refill_rate = 2.0

        # Act - MANDATORY
        config = TokenBucketConfig(capacity=capacity, refill_rate=refill_rate)

        # Assert - MANDATORY
        assert config.capacity == capacity
        assert config.refill_rate == refill_rate
        assert config.initial_tokens == capacity  # Defaults to capacity

    def test_token_bucket_config_with_custom_initial_tokens(self) -> None:
        """Test config with custom initial tokens - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        capacity = 10
        refill_rate = 2.0
        initial_tokens = 5

        # Act - MANDATORY
        config = TokenBucketConfig(
            capacity=capacity, refill_rate=refill_rate, initial_tokens=initial_tokens
        )

        # Assert - MANDATORY
        assert config.initial_tokens == initial_tokens

    def test_token_bucket_config_invalid_capacity_raises_error(self) -> None:
        """Test config with invalid capacity - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        capacity = 0
        refill_rate = 2.0

        # Act & Assert - MANDATORY
        with pytest.raises(ValueError, match="Capacity must be positive"):
            TokenBucketConfig(capacity=capacity, refill_rate=refill_rate)

    def test_token_bucket_config_negative_capacity_raises_error(self) -> None:
        """Test config with negative capacity - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        capacity = -5
        refill_rate = 2.0

        # Act & Assert - MANDATORY
        with pytest.raises(ValueError, match="Capacity must be positive"):
            TokenBucketConfig(capacity=capacity, refill_rate=refill_rate)

    def test_token_bucket_config_invalid_refill_rate_raises_error(self) -> None:
        """Test config with invalid refill rate - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        capacity = 10
        refill_rate = 0

        # Act & Assert - MANDATORY
        with pytest.raises(ValueError, match="Refill rate must be positive"):
            TokenBucketConfig(capacity=capacity, refill_rate=refill_rate)

    def test_token_bucket_config_negative_refill_rate_raises_error(self) -> None:
        """Test config with negative refill rate - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        capacity = 10
        refill_rate = -1.0

        # Act & Assert - MANDATORY
        with pytest.raises(ValueError, match="Refill rate must be positive"):
            TokenBucketConfig(capacity=capacity, refill_rate=refill_rate)

    def test_token_bucket_config_initial_tokens_exceeds_capacity(self) -> None:
        """Test config with initial tokens > capacity - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        capacity = 10
        refill_rate = 2.0
        initial_tokens = 20

        # Act & Assert - MANDATORY
        with pytest.raises(ValueError, match="Initial tokens must be between 0 and capacity"):
            TokenBucketConfig(
                capacity=capacity, refill_rate=refill_rate, initial_tokens=initial_tokens
            )

    def test_token_bucket_config_negative_initial_tokens(self) -> None:
        """Test config with negative initial tokens - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        capacity = 10
        refill_rate = 2.0
        initial_tokens = -1

        # Act & Assert - MANDATORY
        with pytest.raises(ValueError, match="Initial tokens must be between 0 and capacity"):
            TokenBucketConfig(
                capacity=capacity, refill_rate=refill_rate, initial_tokens=initial_tokens
            )


# ============================================================================
# TokenBucket Tests
# ============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
class TestTokenBucket:
    """Tests for TokenBucket class."""

    async def test_token_bucket_initialization(self, standard_config: TokenBucketConfig) -> None:
        """Test token bucket initialization - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # Use fixture config

        # Act - MANDATORY
        bucket = TokenBucket(standard_config)

        # Assert - MANDATORY
        assert bucket.config == standard_config
        tokens = await bucket.get_available_tokens()
        assert tokens == standard_config.capacity

    async def test_token_bucket_consume_single_token(self, token_bucket: TokenBucket) -> None:
        """Test consuming single token - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        tokens_to_consume = 1

        # Act - MANDATORY
        result = await token_bucket.consume(tokens_to_consume)

        # Assert - MANDATORY
        assert result is True
        remaining = await token_bucket.get_available_tokens()
        # Allow for slight refill during test execution
        assert remaining == pytest.approx(9, abs=0.1)  # 10 initial - 1 consumed

    async def test_token_bucket_consume_multiple_tokens(self, token_bucket: TokenBucket) -> None:
        """Test consuming multiple tokens - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        tokens_to_consume = 5

        # Act - MANDATORY
        result = await token_bucket.consume(tokens_to_consume)

        # Assert - MANDATORY
        assert result is True
        remaining = await token_bucket.get_available_tokens()
        assert remaining == pytest.approx(5, abs=0.1)  # 10 initial - 5 consumed

    async def test_token_bucket_consume_all_tokens(self, token_bucket: TokenBucket) -> None:
        """Test consuming all available tokens - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        tokens_to_consume = 10

        # Act - MANDATORY
        result = await token_bucket.consume(tokens_to_consume)

        # Assert - MANDATORY
        assert result is True
        remaining = await token_bucket.get_available_tokens()
        assert remaining == pytest.approx(0, abs=0.1)

    async def test_token_bucket_consume_more_than_available(
        self, token_bucket: TokenBucket
    ) -> None:
        """Test consuming more tokens than available - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        await token_bucket.consume(8)  # Consume 8, leaving 2

        # Act - MANDATORY
        result = await token_bucket.consume(5)  # Try to consume 5

        # Assert - MANDATORY
        assert result is False  # Should be rate limited
        remaining = await token_bucket.get_available_tokens()
        assert remaining == pytest.approx(2, abs=0.1)  # Should still have 2 tokens

    async def test_token_bucket_consume_exceeds_capacity(self, token_bucket: TokenBucket) -> None:
        """Test consuming more than bucket capacity - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        tokens_to_consume = 15  # Exceeds capacity of 10

        # Act - MANDATORY
        result = await token_bucket.consume(tokens_to_consume)

        # Assert - MANDATORY
        assert result is False

    async def test_token_bucket_consume_zero_tokens_raises_error(
        self, token_bucket: TokenBucket
    ) -> None:
        """Test consuming zero tokens raises error - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        tokens_to_consume = 0

        # Act & Assert - MANDATORY
        with pytest.raises(ValueError, match="Token count must be positive"):
            await token_bucket.consume(tokens_to_consume)

    async def test_token_bucket_consume_negative_tokens_raises_error(
        self, token_bucket: TokenBucket
    ) -> None:
        """Test consuming negative tokens raises error - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        tokens_to_consume = -1

        # Act & Assert - MANDATORY
        with pytest.raises(ValueError, match="Token count must be positive"):
            await token_bucket.consume(tokens_to_consume)

    async def test_token_bucket_refill_over_time(self, standard_config: TokenBucketConfig) -> None:
        """Test bucket refills over time - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        bucket = TokenBucket(standard_config)
        await bucket.consume(10)  # Consume all tokens

        # Act - MANDATORY
        await asyncio.sleep(1.0)  # Wait 1 second (refill rate = 2.0 tokens/sec)
        tokens_after_wait = await bucket.get_available_tokens()

        # Assert - MANDATORY
        # Should have ~2 tokens after 1 second (refill_rate = 2.0)
        assert tokens_after_wait >= 1.8  # Allow for timing variance

    async def test_token_bucket_refill_caps_at_capacity(
        self, standard_config: TokenBucketConfig
    ) -> None:
        """Test bucket refill caps at capacity - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        bucket = TokenBucket(standard_config)

        # Act - MANDATORY
        await asyncio.sleep(10.0)  # Wait long enough to exceed capacity
        tokens = await bucket.get_available_tokens()

        # Assert - MANDATORY
        assert tokens == standard_config.capacity  # Should cap at 10

    async def test_token_bucket_get_wait_time_immediate(self, token_bucket: TokenBucket) -> None:
        """Test get_wait_time when tokens available - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        tokens_needed = 5

        # Act - MANDATORY
        wait_time = await token_bucket.get_wait_time(tokens_needed)

        # Assert - MANDATORY
        assert wait_time == 0.0  # Tokens immediately available

    async def test_token_bucket_get_wait_time_after_consumption(
        self, token_bucket: TokenBucket
    ) -> None:
        """Test get_wait_time after consuming tokens - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        await token_bucket.consume(10)  # Consume all tokens

        # Act - MANDATORY
        wait_time = await token_bucket.get_wait_time(4)  # Need 4 tokens

        # Assert - MANDATORY
        # Wait time = 4 tokens / 2.0 tokens per second = 2.0 seconds
        assert wait_time == pytest.approx(2.0, abs=0.1)

    async def test_token_bucket_get_wait_time_exceeds_capacity(
        self, token_bucket: TokenBucket
    ) -> None:
        """Test get_wait_time for request exceeding capacity - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        tokens_needed = 15  # Exceeds capacity of 10

        # Act - MANDATORY
        wait_time = await token_bucket.get_wait_time(tokens_needed)

        # Assert - MANDATORY
        assert wait_time == float("inf")  # Never fulfilled

    async def test_token_bucket_reset(self, token_bucket: TokenBucket) -> None:
        """Test bucket reset functionality - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        await token_bucket.consume(8)  # Consume some tokens

        # Act - MANDATORY
        await token_bucket.reset()

        # Assert - MANDATORY
        tokens = await token_bucket.get_available_tokens()
        assert tokens == 10  # Should be back to initial capacity


# ============================================================================
# TokenBucketPool Tests
# ============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
class TestTokenBucketPool:
    """Tests for TokenBucketPool class."""

    async def test_token_bucket_pool_initialization(
        self, standard_config: TokenBucketConfig
    ) -> None:
        """Test pool initialization - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        max_buckets = 100

        # Act - MANDATORY
        pool = TokenBucketPool(default_config=standard_config, max_buckets=max_buckets)

        # Assert - MANDATORY
        assert pool.default_config == standard_config
        assert pool.max_buckets == max_buckets
        count = await pool.get_bucket_count()
        assert count == 0  # No buckets initially

    async def test_token_bucket_pool_get_bucket_creates_new(
        self, token_bucket_pool: TokenBucketPool
    ) -> None:
        """Test get_bucket creates new bucket - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        key = "user_123"

        # Act - MANDATORY
        bucket = await token_bucket_pool.get_bucket(key)

        # Assert - MANDATORY
        assert bucket is not None
        count = await token_bucket_pool.get_bucket_count()
        assert count == 1

    async def test_token_bucket_pool_get_bucket_returns_existing(
        self, token_bucket_pool: TokenBucketPool
    ) -> None:
        """Test get_bucket returns existing bucket - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        key = "user_123"
        bucket1 = await token_bucket_pool.get_bucket(key)

        # Act - MANDATORY
        bucket2 = await token_bucket_pool.get_bucket(key)

        # Assert - MANDATORY
        assert bucket1 is bucket2  # Same instance
        count = await token_bucket_pool.get_bucket_count()
        assert count == 1  # Still only 1 bucket

    async def test_token_bucket_pool_consume_from_key(
        self, token_bucket_pool: TokenBucketPool
    ) -> None:
        """Test consuming tokens via pool key - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        key = "user_123"
        tokens = 5

        # Act - MANDATORY
        result = await token_bucket_pool.consume(key, tokens)

        # Assert - MANDATORY
        assert result is True

    async def test_token_bucket_pool_get_wait_time_from_key(
        self, token_bucket_pool: TokenBucketPool
    ) -> None:
        """Test get_wait_time via pool key - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        key = "user_123"
        tokens = 5

        # Act - MANDATORY
        wait_time = await token_bucket_pool.get_wait_time(key, tokens)

        # Assert - MANDATORY
        assert wait_time == 0.0  # Tokens immediately available

    async def test_token_bucket_pool_multiple_keys(
        self, token_bucket_pool: TokenBucketPool
    ) -> None:
        """Test pool with multiple keys - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        keys = ["user_1", "user_2", "user_3"]

        # Act - MANDATORY
        for key in keys:
            await token_bucket_pool.get_bucket(key)

        # Assert - MANDATORY
        count = await token_bucket_pool.get_bucket_count()
        assert count == 3

    async def test_token_bucket_pool_cleanup_when_full(
        self, standard_config: TokenBucketConfig
    ) -> None:
        """Test pool cleanup when max buckets reached - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        pool = TokenBucketPool(default_config=standard_config, max_buckets=10)

        # Act - MANDATORY
        # Create 15 buckets to trigger cleanup
        for i in range(15):
            await pool.get_bucket(f"user_{i}")
            await asyncio.sleep(0.01)  # Small delay for access time tracking

        # Assert - MANDATORY
        count = await pool.get_bucket_count()
        # Should have cleaned up ~25% when exceeding max
        assert count <= 10

    async def test_token_bucket_pool_reset_bucket(self, token_bucket_pool: TokenBucketPool) -> None:
        """Test resetting specific bucket in pool - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        key = "user_123"
        await token_bucket_pool.consume(key, 8)  # Consume tokens

        # Act - MANDATORY
        await token_bucket_pool.reset_bucket(key)

        # Assert - MANDATORY
        bucket = await token_bucket_pool.get_bucket(key)
        tokens = await bucket.get_available_tokens()
        assert tokens == 10  # Should be reset to capacity


# ============================================================================
# Concurrent Access Tests
# ============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
class TestTokenBucketConcurrency:
    """Tests for concurrent access to token buckets."""

    async def test_token_bucket_concurrent_consume(
        self, standard_config: TokenBucketConfig
    ) -> None:
        """Test concurrent token consumption - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        bucket = TokenBucket(standard_config)
        concurrent_requests = 20

        # Act - MANDATORY
        results = await asyncio.gather(*[bucket.consume(1) for _ in range(concurrent_requests)])

        # Assert - MANDATORY
        # Only 10 should succeed (capacity = 10)
        successful = sum(1 for r in results if r is True)
        assert successful == 10

    async def test_token_bucket_pool_concurrent_access(
        self, token_bucket_pool: TokenBucketPool
    ) -> None:
        """Test concurrent pool access - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        keys = [f"user_{i}" for i in range(10)]

        # Act - MANDATORY
        results = await asyncio.gather(*[token_bucket_pool.get_bucket(key) for key in keys])

        # Assert - MANDATORY
        assert len(results) == 10
        count = await token_bucket_pool.get_bucket_count()
        assert count == 10


# ============================================================================
# MANDATORY Performance Benchmarks
# ============================================================================


@pytest.mark.performance
@pytest.mark.unit
@pytest.mark.asyncio
class TestTokenBucketPerformance:
    """MANDATORY performance tests for token bucket."""

    async def test_token_bucket_consume_performance(
        self, standard_config: TokenBucketConfig
    ) -> None:
        """MANDATORY performance test - consume operation speed."""
        # Arrange - MANDATORY
        bucket = TokenBucket(standard_config)
        iterations = 1000

        # Act - MANDATORY
        start_time = time.perf_counter()

        for _ in range(iterations):
            await bucket.consume(1)
            await bucket.reset()  # Reset to allow more consumption

        end_time = time.perf_counter()
        execution_time = end_time - start_time

        # Assert - MANDATORY
        avg_time = execution_time / iterations
        assert avg_time < 0.001  # <1ms per consume operation
        assert execution_time < 1.0  # Total <1s for 1000 operations

    async def test_token_bucket_pool_get_bucket_performance(
        self, token_bucket_pool: TokenBucketPool
    ) -> None:
        """MANDATORY performance test - get_bucket speed."""
        # Arrange - MANDATORY
        iterations = 1000

        # Act - MANDATORY
        start_time = time.perf_counter()

        for i in range(iterations):
            await token_bucket_pool.get_bucket(f"user_{i % 100}")

        end_time = time.perf_counter()
        execution_time = end_time - start_time

        # Assert - MANDATORY
        avg_time = execution_time / iterations
        assert avg_time < 0.001  # <1ms per get_bucket operation
        assert execution_time < 1.0  # Total <1s for 1000 operations
