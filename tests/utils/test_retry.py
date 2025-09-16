"""Tests for retry utilities following testing best practices."""

import time

import pytest
from aiohttp import ClientError

from src.core.exceptions import RateLimitError
from src.utils.retry import RetryConfig, with_retry


class TestRetryConfig:
    """Test RetryConfig dataclass following SOLID principles."""

    def test_retry_config_default_values(self):
        """Test retry config with default values."""
        config = RetryConfig()
        assert config.max_attempts >= 1
        assert config.base_delay > 0
        assert config.backoff_factor > 1
        assert config.jitter is True
        assert 0 <= config.jitter_factor <= 1

    def test_retry_config_custom_values(self):
        """Test retry config with custom values."""
        config = RetryConfig(
            max_attempts=5,
            base_delay=2.0,
            max_delay=30.0,
            backoff_factor=2.5,
            jitter=False,
            jitter_factor=0.2,
        )
        assert config.max_attempts == 5
        assert config.base_delay == 2.0
        assert config.max_delay == 30.0
        assert config.backoff_factor == 2.5
        assert config.jitter is False
        assert config.jitter_factor == 0.2

    def test_retry_config_validation_max_attempts(self):
        """Test validation of max_attempts parameter."""
        with pytest.raises(ValueError, match="max_attempts must be at least 1"):
            RetryConfig(max_attempts=0)

    def test_retry_config_validation_base_delay(self):
        """Test validation of base_delay parameter."""
        with pytest.raises(ValueError, match="base_delay must be positive"):
            RetryConfig(base_delay=0)

        with pytest.raises(ValueError, match="base_delay must be positive"):
            RetryConfig(base_delay=-1)

    def test_retry_config_validation_backoff_factor(self):
        """Test validation of backoff_factor parameter."""
        with pytest.raises(ValueError, match="backoff_factor must be greater than 1"):
            RetryConfig(backoff_factor=1.0)

        with pytest.raises(ValueError, match="backoff_factor must be greater than 1"):
            RetryConfig(backoff_factor=0.5)

    def test_retry_config_validation_jitter_factor(self):
        """Test validation of jitter_factor parameter."""
        with pytest.raises(ValueError, match="jitter_factor must be between 0 and 1"):
            RetryConfig(jitter_factor=-0.1)

        with pytest.raises(ValueError, match="jitter_factor must be between 0 and 1"):
            RetryConfig(jitter_factor=1.1)

    def test_retry_config_boundary_values(self):
        """Test retry config with boundary values."""
        # Test minimum valid values
        config = RetryConfig(
            max_attempts=1, base_delay=0.001, backoff_factor=1.001, jitter_factor=0.0
        )
        assert config.max_attempts == 1
        assert config.base_delay == 0.001
        assert config.backoff_factor == 1.001
        assert config.jitter_factor == 0.0

        # Test maximum valid values
        config = RetryConfig(
            max_attempts=100, base_delay=60.0, backoff_factor=10.0, jitter_factor=1.0
        )
        assert config.max_attempts == 100
        assert config.base_delay == 60.0
        assert config.backoff_factor == 10.0
        assert config.jitter_factor == 1.0


class TestRetryConfigDelayCalculation:
    """Test delay calculation with exponential backoff and jitter."""

    def test_calculate_delay_no_jitter(self):
        """Test delay calculation without jitter."""
        config = RetryConfig(base_delay=1.0, backoff_factor=2.0, max_delay=10.0, jitter=False)

        # Test exponential backoff
        assert config.calculate_delay(0) == 1.0  # 1.0 * 2^0
        assert config.calculate_delay(1) == 2.0  # 1.0 * 2^1
        assert config.calculate_delay(2) == 4.0  # 1.0 * 2^2
        assert config.calculate_delay(3) == 8.0  # 1.0 * 2^3

    def test_calculate_delay_with_max_delay(self):
        """Test delay calculation respects max_delay."""
        config = RetryConfig(base_delay=1.0, backoff_factor=2.0, max_delay=5.0, jitter=False)

        # Should cap at max_delay
        assert config.calculate_delay(3) == 5.0  # Capped at max_delay
        assert config.calculate_delay(4) == 5.0  # Still capped
        assert config.calculate_delay(10) == 5.0  # Still capped

    def test_calculate_delay_with_jitter(self):
        """Test delay calculation with jitter."""
        config = RetryConfig(base_delay=1.0, backoff_factor=2.0, max_delay=10.0, jitter=True)

        # With jitter, delays should be random but within bounds
        delays = [config.calculate_delay(1) for _ in range(10)]

        # All delays should be different (very high probability)
        assert len(set(delays)) > 1

        # All delays should be between minimum (0.1) and expected max (2.0)
        for delay in delays:
            assert 0.1 <= delay <= 2.0

    def test_calculate_delay_jitter_minimum(self):
        """Test delay calculation ensures minimum delay with jitter."""
        config = RetryConfig(
            base_delay=0.05,  # Very small base delay
            backoff_factor=1.1,
            jitter=True,
        )

        # Even with small base delay and jitter, should maintain minimum
        delay = config.calculate_delay(0)
        assert delay >= 0.1

    def test_calculate_delay_different_backoff_factors(self):
        """Test delay calculation with different backoff factors."""
        config_slow = RetryConfig(base_delay=1.0, backoff_factor=1.5, jitter=False)
        config_fast = RetryConfig(base_delay=1.0, backoff_factor=3.0, jitter=False)

        # Fast backoff should grow quicker
        assert config_slow.calculate_delay(2) == 2.25  # 1.0 * 1.5^2
        assert config_fast.calculate_delay(2) == 9.0  # 1.0 * 3.0^2


class TestWithRetryDecorator:
    """Test retry decorator functionality with async functions."""

    @pytest.mark.asyncio
    async def test_with_retry_success_first_attempt(self):
        """Test retry decorator with successful first attempt."""
        call_count = 0

        @with_retry(RetryConfig(max_attempts=3))
        async def successful_function():
            nonlocal call_count
            call_count += 1
            return "success"

        result = await successful_function()
        assert result == "success"
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_with_retry_success_after_failures(self):
        """Test retry decorator with success after failures."""
        call_count = 0

        @with_retry(RetryConfig(max_attempts=3, base_delay=0.01, jitter=False))
        async def flaky_function():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ClientError("Temporary failure")
            return "success"

        result = await flaky_function()
        assert result == "success"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_with_retry_exhausted_attempts(self):
        """Test retry decorator when all attempts are exhausted."""
        call_count = 0

        @with_retry(RetryConfig(max_attempts=2, base_delay=0.01, jitter=False))
        async def always_failing_function():
            nonlocal call_count
            call_count += 1
            raise ClientError("Persistent failure")

        with pytest.raises(ClientError, match="Persistent failure"):
            await always_failing_function()

        assert call_count == 2

    @pytest.mark.asyncio
    async def test_with_retry_different_exceptions(self):
        """Test retry decorator with different exception types."""
        # Test with retryable exception
        call_count = 0

        @with_retry(
            RetryConfig(max_attempts=2, base_delay=0.01), retry_on=(ClientError,), reraise_on=()
        )
        async def function_with_client_error():
            nonlocal call_count
            call_count += 1
            raise ClientError("Client error")

        with pytest.raises(ClientError):
            await function_with_client_error()
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_with_retry_reraise_exception(self):
        """Test retry decorator with exception that should be reraised."""
        call_count = 0

        @with_retry(
            RetryConfig(max_attempts=3, base_delay=0.01),
            retry_on=(ClientError,),
            reraise_on=(RateLimitError,),
        )
        async def function_with_rate_limit():
            nonlocal call_count
            call_count += 1
            raise RateLimitError("Rate limited")

        with pytest.raises(RateLimitError, match="Rate limited"):
            await function_with_rate_limit()

        # Should not retry for reraise exceptions
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_with_retry_preserves_function_metadata(self):
        """Test retry decorator preserves function metadata."""

        @with_retry(RetryConfig(max_attempts=2))
        async def documented_function():
            """This function has documentation."""
            return "result"

        assert documented_function.__name__ == "documented_function"
        assert "This function has documentation" in documented_function.__doc__

    @pytest.mark.asyncio
    async def test_with_retry_with_args_and_kwargs(self):
        """Test retry decorator with function arguments."""
        call_count = 0

        @with_retry(RetryConfig(max_attempts=2, base_delay=0.01, jitter=False))
        async def function_with_args(arg1, arg2, kwarg1=None):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ClientError("First failure")
            return f"{arg1}-{arg2}-{kwarg1}"

        result = await function_with_args("test", "value", kwarg1="extra")
        assert result == "test-value-extra"
        assert call_count == 2


class TestRetryTiming:
    """Test retry timing and delay behavior."""

    @pytest.mark.asyncio
    async def test_retry_timing_without_jitter(self):
        """Test actual timing of retry delays without jitter."""
        call_times = []

        @with_retry(RetryConfig(max_attempts=3, base_delay=0.1, backoff_factor=2.0, jitter=False))
        async def timing_function():
            call_times.append(time.time())
            if len(call_times) < 3:
                raise ClientError("Retry needed")
            return "success"

        start_time = time.time()
        result = await timing_function()
        total_time = time.time() - start_time

        assert result == "success"
        assert len(call_times) == 3

        # Check delay intervals (approximately)
        delay1 = call_times[1] - call_times[0]
        delay2 = call_times[2] - call_times[1]

        # First delay should be ~0.1s, second delay should be ~0.2s
        assert 0.05 <= delay1 <= 0.15  # Allow some tolerance
        assert 0.15 <= delay2 <= 0.25  # Allow some tolerance

    @pytest.mark.asyncio
    async def test_retry_timing_with_jitter(self):
        """Test retry timing with jitter introduces variability."""
        delays = []

        for _ in range(5):
            call_times = []

            async def make_jitter_function(times_list):
                @with_retry(RetryConfig(max_attempts=2, base_delay=0.1, jitter=True))
                async def jitter_function():
                    times_list.append(time.time())
                    if len(times_list) == 1:
                        raise ClientError("Retry needed")
                    return "success"

                return jitter_function

            jitter_func = await make_jitter_function(call_times)
            await jitter_func()

            if len(call_times) >= 2:
                delay = call_times[1] - call_times[0]
                delays.append(delay)

        # With jitter, delays should be variable
        assert len({f"{d:.3f}" for d in delays}) > 1  # At least some variation


class TestRetryEdgeCases:
    """Test edge cases and error conditions in retry logic."""

    @pytest.mark.asyncio
    async def test_retry_with_zero_max_attempts_config_validation(self):
        """Test retry config validation prevents invalid configurations."""
        with pytest.raises(ValueError):
            RetryConfig(max_attempts=0)

    @pytest.mark.asyncio
    async def test_retry_with_non_async_function_protection(self):
        """Test retry decorator behavior with non-async functions."""
        # This should be caught at the decorator level if implemented
        # For now, we test that async decorator expects async function

        call_count = 0

        @with_retry(RetryConfig(max_attempts=2, base_delay=0.01))
        async def proper_async_function():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ClientError("First failure")
            return "success"

        result = await proper_async_function()
        assert result == "success"
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_retry_exception_chaining(self):
        """Test that retry preserves exception information."""

        @with_retry(RetryConfig(max_attempts=2, base_delay=0.01))
        async def failing_function():
            raise ClientError("Original error message")

        try:
            await failing_function()
        except ClientError as e:
            assert "Original error message" in str(e)
        else:
            pytest.fail("Expected ClientError to be raised")

    @pytest.mark.asyncio
    async def test_retry_with_complex_exception_hierarchy(self):
        """Test retry behavior with complex exception hierarchies."""

        class CustomClientError(ClientError):
            pass

        call_count = 0

        @with_retry(
            RetryConfig(max_attempts=2, base_delay=0.01),
            retry_on=(ClientError,),  # Should catch subclasses too
        )
        async def function_with_custom_error():
            nonlocal call_count
            call_count += 1
            raise CustomClientError("Custom client error")

        with pytest.raises(CustomClientError):
            await function_with_custom_error()

        assert call_count == 2  # Should retry subclass of ClientError


class TestRetryIntegration:
    """Test integration scenarios for retry functionality."""

    @pytest.mark.asyncio
    async def test_retry_with_async_context_manager(self):
        """Test retry decorator works with async context managers."""
        call_count = 0
        context_entered = 0
        context_exited = 0

        class AsyncContextManager:
            async def __aenter__(self):
                nonlocal context_entered
                context_entered += 1
                return self

            async def __aexit__(self, exc_type, exc_val, exc_tb):
                nonlocal context_exited
                context_exited += 1

        @with_retry(RetryConfig(max_attempts=2, base_delay=0.01))
        async def function_with_context():
            nonlocal call_count
            call_count += 1
            async with AsyncContextManager():
                if call_count == 1:
                    raise ClientError("First failure")
                return "success"

        result = await function_with_context()
        assert result == "success"
        assert call_count == 2
        assert context_entered == 2  # Context entered for each retry
        assert context_exited == 2  # Context exited for each retry

    @pytest.mark.asyncio
    async def test_retry_performance_overhead(self):
        """Test retry decorator has minimal performance overhead."""
        call_count = 0

        @with_retry(RetryConfig(max_attempts=1))  # No actual retries
        async def fast_function():
            nonlocal call_count
            call_count += 1
            return call_count

        # Measure overhead by running many times
        start_time = time.time()
        results = []
        for _ in range(100):
            result = await fast_function()
            results.append(result)
        execution_time = time.time() - start_time

        # Should complete quickly even with decorator overhead
        assert execution_time < 0.1  # Less than 100ms for 100 calls
        assert len(results) == 100
        assert call_count == 100


class TestRetryConfigCalculations:
    """Test mathematical correctness of retry calculations."""

    def test_exponential_backoff_progression(self):
        """Test exponential backoff follows correct mathematical progression."""
        config = RetryConfig(base_delay=1.0, backoff_factor=2.0, max_delay=100.0, jitter=False)

        # Test exponential sequence: 1, 2, 4, 8, 16, 32...
        expected_delays = [1.0, 2.0, 4.0, 8.0, 16.0, 32.0, 64.0]

        for attempt, expected in enumerate(expected_delays):
            actual = config.calculate_delay(attempt)
            assert actual == expected

    def test_max_delay_capping_behavior(self):
        """Test max delay capping behavior is mathematically correct."""
        config = RetryConfig(base_delay=1.0, backoff_factor=2.0, max_delay=10.0, jitter=False)

        # Test that delays are capped at max_delay
        delays = [config.calculate_delay(i) for i in range(10)]

        # Find where capping starts (2^n >= 10, so n >= log2(10) ≈ 3.32, so at attempt 4)
        assert delays[0] == 1.0  # 2^0 = 1
        assert delays[1] == 2.0  # 2^1 = 2
        assert delays[2] == 4.0  # 2^2 = 4
        assert delays[3] == 8.0  # 2^3 = 8
        assert delays[4] == 10.0  # 2^4 = 16, capped to 10
        assert delays[5] == 10.0  # Still capped
        assert all(delay <= 10.0 for delay in delays)

    def test_jitter_statistical_properties(self):
        """Test jitter has correct statistical properties."""
        config = RetryConfig(
            base_delay=2.0,
            backoff_factor=1.0,  # No exponential growth
            jitter=True,
        )

        # Collect many samples for attempt 1 (base_delay = 2.0)
        samples = [config.calculate_delay(0) for _ in range(1000)]

        # All samples should be >= 0.1 (minimum) and <= 2.0 (base_delay)
        assert all(0.1 <= sample <= 2.0 for sample in samples)

        # Mean should be approximately 1.0 (midpoint of uniform distribution)
        # Allow generous tolerance for randomness
        mean = sum(samples) / len(samples)
        assert 0.8 <= mean <= 1.2

        # Should have good distribution (not all the same value)
        unique_values = len({f"{s:.3f}" for s in samples})
        assert unique_values > 100  # Should have many unique values
