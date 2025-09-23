"""Tests for token bucket rate limiting implementation."""

import time

import asyncio
import pytest

from src.utils.rate_limiting.token_bucket import TokenBucket, TokenBucketConfig, TokenBucketPool


class TestTokenBucketConfig:
    """Test TokenBucketConfig validation and initialization."""

    def test_config_valid_initialization(self):
        """Test valid configuration initialization."""
        config = TokenBucketConfig(capacity=10, refill_rate=2.0)
        assert config.capacity == 10
        assert config.refill_rate == 2.0
        assert config.initial_tokens == 10  # Should default to capacity

    def test_config_custom_initial_tokens(self):
        """Test configuration with custom initial tokens."""
        config = TokenBucketConfig(capacity=10, refill_rate=2.0, initial_tokens=5)
        assert config.initial_tokens == 5

    def test_config_validation_negative_capacity(self):
        """Test configuration validation for negative capacity."""
        with pytest.raises(ValueError, match="Capacity must be positive"):
            TokenBucketConfig(capacity=0, refill_rate=1.0)

    def test_config_validation_negative_refill_rate(self):
        """Test configuration validation for negative refill rate."""
        with pytest.raises(ValueError, match="Refill rate must be positive"):
            TokenBucketConfig(capacity=10, refill_rate=-1.0)

    def test_config_validation_initial_tokens_too_high(self):
        """Test configuration validation for initial tokens exceeding capacity."""
        with pytest.raises(ValueError, match="Initial tokens must be between 0 and capacity"):
            TokenBucketConfig(capacity=10, refill_rate=1.0, initial_tokens=15)

    def test_config_validation_negative_initial_tokens(self):
        """Test configuration validation for negative initial tokens."""
        with pytest.raises(ValueError, match="Initial tokens must be between 0 and capacity"):
            TokenBucketConfig(capacity=10, refill_rate=1.0, initial_tokens=-1)


class TestTokenBucket:
    """Test TokenBucket functionality."""

    @pytest.mark.asyncio
    async def test_consume_success(self):
        """Test successful token consumption."""
        config = TokenBucketConfig(capacity=10, refill_rate=1.0, initial_tokens=5)
        bucket = TokenBucket(config)

        result = await bucket.consume(3)
        assert result is True

        # Check remaining tokens (allow small tolerance for timing)
        remaining = await bucket.get_available_tokens()
        assert abs(remaining - 2.0) < 0.1

    @pytest.mark.asyncio
    async def test_consume_insufficient_tokens(self):
        """Test consumption when insufficient tokens available."""
        config = TokenBucketConfig(capacity=10, refill_rate=1.0, initial_tokens=2)
        bucket = TokenBucket(config)

        result = await bucket.consume(5)
        assert result is False

        # Tokens should remain unchanged
        remaining = await bucket.get_available_tokens()
        assert remaining == 2.0

    @pytest.mark.asyncio
    async def test_consume_exceeds_capacity(self):
        """Test consumption request exceeding bucket capacity."""
        config = TokenBucketConfig(capacity=5, refill_rate=1.0)
        bucket = TokenBucket(config)

        result = await bucket.consume(10)
        assert result is False

    @pytest.mark.asyncio
    async def test_consume_invalid_token_count(self):
        """Test consumption with invalid token count."""
        config = TokenBucketConfig(capacity=10, refill_rate=1.0)
        bucket = TokenBucket(config)

        with pytest.raises(ValueError, match="Token count must be positive"):
            await bucket.consume(0)

        with pytest.raises(ValueError, match="Token count must be positive"):
            await bucket.consume(-1)

    @pytest.mark.asyncio
    async def test_refill_over_time(self):
        """Test token refill over time."""
        config = TokenBucketConfig(capacity=10, refill_rate=2.0, initial_tokens=0)
        bucket = TokenBucket(config)

        # Initially no tokens
        result = await bucket.consume(1)
        assert result is False

        # Wait for refill (2 tokens per second)
        await asyncio.sleep(1.1)  # Sleep slightly more than 1 second

        # Should now have at least 2 tokens
        result = await bucket.consume(2)
        assert result is True

    @pytest.mark.asyncio
    async def test_refill_capped_at_capacity(self):
        """Test that refill doesn't exceed capacity."""
        config = TokenBucketConfig(capacity=5, refill_rate=10.0, initial_tokens=0)
        bucket = TokenBucket(config)

        # Wait for more time than needed to fill beyond capacity
        await asyncio.sleep(1.0)  # Would generate 10 tokens, but capacity is 5

        available = await bucket.get_available_tokens()
        assert available == 5.0  # Should be capped at capacity

    @pytest.mark.asyncio
    async def test_get_wait_time(self):
        """Test wait time calculation."""
        config = TokenBucketConfig(capacity=10, refill_rate=2.0, initial_tokens=1)
        bucket = TokenBucket(config)

        # Need 3 tokens, have 1, need 2 more at rate of 2/second = 1 second wait
        wait_time = await bucket.get_wait_time(3)
        assert abs(wait_time - 1.0) < 0.1  # Allow small tolerance

    @pytest.mark.asyncio
    async def test_get_wait_time_immediately_available(self):
        """Test wait time when tokens are immediately available."""
        config = TokenBucketConfig(capacity=10, refill_rate=1.0, initial_tokens=5)
        bucket = TokenBucket(config)

        wait_time = await bucket.get_wait_time(3)
        assert wait_time == 0.0

    @pytest.mark.asyncio
    async def test_get_wait_time_exceeds_capacity(self):
        """Test wait time for request exceeding capacity."""
        config = TokenBucketConfig(capacity=5, refill_rate=1.0)
        bucket = TokenBucket(config)

        wait_time = await bucket.get_wait_time(10)
        assert wait_time == float("inf")

    @pytest.mark.asyncio
    async def test_reset(self):
        """Test bucket reset functionality."""
        config = TokenBucketConfig(capacity=10, refill_rate=1.0, initial_tokens=10)
        bucket = TokenBucket(config)

        # Consume some tokens
        await bucket.consume(5)
        remaining = await bucket.get_available_tokens()
        assert remaining == 5.0

        # Reset
        await bucket.reset()
        remaining = await bucket.get_available_tokens()
        assert remaining == 10.0  # Back to initial tokens

    @pytest.mark.asyncio
    async def test_concurrent_access(self):
        """Test thread-safe concurrent access."""
        config = TokenBucketConfig(capacity=100, refill_rate=10.0, initial_tokens=100)
        bucket = TokenBucket(config)

        async def consumer():
            return await bucket.consume(1)

        # Run multiple consumers concurrently
        tasks = [consumer() for _ in range(50)]
        results = await asyncio.gather(*tasks)

        # All should succeed since we have enough tokens
        assert all(results)

        # Check that exactly 50 tokens were consumed
        remaining = await bucket.get_available_tokens()
        assert remaining == 50.0


class TestTokenBucketPool:
    """Test TokenBucketPool functionality."""

    @pytest.mark.asyncio
    async def test_get_bucket_creates_new(self):
        """Test that get_bucket creates new buckets."""
        config = TokenBucketConfig(capacity=10, refill_rate=1.0)
        pool = TokenBucketPool(config, max_buckets=100)

        bucket1 = await pool.get_bucket("user1")
        bucket2 = await pool.get_bucket("user2")

        assert bucket1 is not bucket2
        assert isinstance(bucket1, TokenBucket)
        assert isinstance(bucket2, TokenBucket)

    @pytest.mark.asyncio
    async def test_get_bucket_reuses_existing(self):
        """Test that get_bucket reuses existing buckets."""
        config = TokenBucketConfig(capacity=10, refill_rate=1.0)
        pool = TokenBucketPool(config, max_buckets=100)

        bucket1 = await pool.get_bucket("user1")
        bucket2 = await pool.get_bucket("user1")

        assert bucket1 is bucket2

    @pytest.mark.asyncio
    async def test_consume_through_pool(self):
        """Test consuming tokens through pool interface."""
        config = TokenBucketConfig(capacity=10, refill_rate=1.0, initial_tokens=5)
        pool = TokenBucketPool(config, max_buckets=100)

        result = await pool.consume("user1", 3)
        assert result is True

        # Should have created and used a bucket for user1
        bucket = await pool.get_bucket("user1")
        remaining = await bucket.get_available_tokens()
        assert abs(remaining - 2.0) < 0.1

    @pytest.mark.asyncio
    async def test_get_wait_time_through_pool(self):
        """Test wait time calculation through pool interface."""
        config = TokenBucketConfig(capacity=10, refill_rate=2.0, initial_tokens=1)
        pool = TokenBucketPool(config, max_buckets=100)

        wait_time = await pool.get_wait_time("user1", 3)
        assert abs(wait_time - 1.0) < 0.1

    @pytest.mark.asyncio
    async def test_pool_cleanup_when_full(self):
        """Test that pool cleans up old buckets when max_buckets is reached."""
        config = TokenBucketConfig(capacity=10, refill_rate=1.0)
        pool = TokenBucketPool(config, max_buckets=5)

        # Create more buckets than max_buckets
        for i in range(10):
            await pool.get_bucket(f"user{i}")
            await asyncio.sleep(0.01)  # Small delay to ensure different access times

        # Should have cleaned up to stay under limit
        bucket_count = await pool.get_bucket_count()
        assert bucket_count <= 5

    @pytest.mark.asyncio
    async def test_reset_bucket(self):
        """Test resetting a specific bucket in pool."""
        config = TokenBucketConfig(capacity=10, refill_rate=1.0, initial_tokens=10)
        pool = TokenBucketPool(config, max_buckets=100)

        # Use some tokens
        await pool.consume("user1", 5)

        # Reset the bucket
        await pool.reset_bucket("user1")

        # Should be back to initial tokens
        bucket = await pool.get_bucket("user1")
        remaining = await bucket.get_available_tokens()
        assert remaining == 10.0

    @pytest.mark.asyncio
    async def test_isolated_buckets(self):
        """Test that different keys have isolated token buckets."""
        config = TokenBucketConfig(capacity=10, refill_rate=1.0, initial_tokens=5)
        pool = TokenBucketPool(config, max_buckets=100)

        # Consume from user1
        result1 = await pool.consume("user1", 5)
        assert result1 is True

        # user2 should still have full tokens
        result2 = await pool.consume("user2", 5)
        assert result2 is True

        # user1 should be empty
        result3 = await pool.consume("user1", 1)
        assert result3 is False


class TestTokenBucketEdgeCases:
    """Test edge cases and error conditions."""

    @pytest.mark.asyncio
    async def test_very_small_refill_rate(self):
        """Test bucket with very small refill rate."""
        config = TokenBucketConfig(capacity=1, refill_rate=0.01, initial_tokens=0)
        bucket = TokenBucket(config)

        # Should not have tokens initially
        result = await bucket.consume(1)
        assert result is False

        # Wait for some refill
        await asyncio.sleep(0.1)  # Should add 0.001 tokens, still not enough

        result = await bucket.consume(1)
        assert result is False

    @pytest.mark.asyncio
    async def test_very_large_capacity(self):
        """Test bucket with very large capacity."""
        config = TokenBucketConfig(capacity=1000000, refill_rate=100.0)
        bucket = TokenBucket(config)

        # Should be able to consume large amounts
        result = await bucket.consume(500000)
        assert result is True

        remaining = await bucket.get_available_tokens()
        assert remaining == 500000.0

    @pytest.mark.asyncio
    async def test_fractional_tokens(self):
        """Test consuming fractional tokens (should not be allowed but test behavior)."""
        config = TokenBucketConfig(capacity=10, refill_rate=1.0)
        bucket = TokenBucket(config)

        # Implementation should handle this gracefully
        # (Current implementation requires int, but testing for robustness)
        with pytest.raises(TypeError):
            await bucket.consume(1.5)

    @pytest.mark.asyncio
    async def test_rapid_sequential_consumption(self):
        """Test rapid sequential token consumption."""
        config = TokenBucketConfig(capacity=100, refill_rate=10.0, initial_tokens=100)
        bucket = TokenBucket(config)

        # Rapidly consume tokens
        for i in range(100):
            result = await bucket.consume(1)
            if i < 100:
                assert result is True
            else:
                assert result is False

        # Should be empty
        remaining = await bucket.get_available_tokens()
        assert remaining == 0.0


class TestTokenBucketPerformance:
    """Performance tests for token bucket implementation."""

    @pytest.mark.asyncio
    async def test_performance_many_sequential_operations(self):
        """Test performance with many sequential operations."""
        config = TokenBucketConfig(capacity=10000, refill_rate=100.0)
        bucket = TokenBucket(config)

        start_time = time.time()

        # Perform many operations
        for _ in range(1000):
            await bucket.consume(1)

        elapsed = time.time() - start_time

        # Should complete quickly (less than 1 second for 1000 operations)
        assert elapsed < 1.0

    @pytest.mark.asyncio
    async def test_performance_concurrent_operations(self):
        """Test performance with concurrent operations."""
        config = TokenBucketConfig(capacity=1000, refill_rate=100.0)
        bucket = TokenBucket(config)

        async def consumer():
            return await bucket.consume(1)

        start_time = time.time()

        # Run many consumers concurrently
        tasks = [consumer() for _ in range(500)]
        results = await asyncio.gather(*tasks)

        elapsed = time.time() - start_time

        # Should complete quickly and most should succeed
        assert elapsed < 2.0
        success_count = sum(1 for r in results if r)
        assert success_count >= 500  # Should have enough capacity
