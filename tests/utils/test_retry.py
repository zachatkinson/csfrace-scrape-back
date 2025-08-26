"""Comprehensive tests for enhanced retry mechanisms with jitter and resilience patterns.

This test module ensures all retry patterns meet CLAUDE.md requirements for
production-ready reliability and error handling.
"""

import asyncio
import time
from unittest.mock import AsyncMock

import pytest
from aiohttp import ClientError

from src.core.exceptions import RateLimitError
from src.utils.retry import (
    BulkheadPattern,
    CircuitBreaker,
    CircuitBreakerState,
    ResilienceManager,
    RetryConfig,
    with_retry,
)


class TestRetryConfig:
    """Test suite for RetryConfig with jitter support."""

    def test_retry_config_defaults(self):
        """Test RetryConfig uses proper defaults."""
        config = RetryConfig()

        assert config.max_attempts == 3  # From CONSTANTS.MAX_RETRIES
        assert config.base_delay == 1.0
        assert config.max_delay == 60.0
        assert config.backoff_factor == 2.0  # From CONSTANTS.BACKOFF_FACTOR
        assert config.jitter is True
        assert config.jitter_factor == 0.1

    def test_retry_config_validation(self):
        """Test RetryConfig parameter validation."""
        # Invalid max_attempts
        with pytest.raises(ValueError, match="max_attempts must be at least 1"):
            RetryConfig(max_attempts=0)

        # Invalid base_delay
        with pytest.raises(ValueError, match="base_delay must be positive"):
            RetryConfig(base_delay=0)

        # Invalid backoff_factor
        with pytest.raises(ValueError, match="backoff_factor must be greater than 1"):
            RetryConfig(backoff_factor=1.0)

        # Invalid jitter_factor
        with pytest.raises(ValueError, match="jitter_factor must be between 0 and 1"):
            RetryConfig(jitter_factor=1.5)

    def test_calculate_delay_without_jitter(self):
        """Test delay calculation without jitter."""
        config = RetryConfig(base_delay=1.0, backoff_factor=2.0, max_delay=10.0, jitter=False)

        # Test exponential backoff without jitter
        assert config.calculate_delay(0) == 1.0
        assert config.calculate_delay(1) == 2.0
        assert config.calculate_delay(2) == 4.0
        assert config.calculate_delay(3) == 8.0
        assert config.calculate_delay(4) == 10.0  # Max delay reached

    def test_calculate_delay_with_jitter(self):
        """Test delay calculation with full jitter."""
        config = RetryConfig(base_delay=2.0, backoff_factor=2.0, max_delay=16.0, jitter=True)

        # With jitter, delay should be random between 0 and calculated delay
        for attempt in range(5):
            delay = config.calculate_delay(attempt)
            expected_max = min(2.0 * (2.0**attempt), 16.0)

            assert 0.1 <= delay <= expected_max  # Minimum 0.1 enforced

        # Test multiple calls return different values (probabilistic test)
        delays = [config.calculate_delay(2) for _ in range(10)]
        assert len(set(delays)) > 1  # Should have variance with jitter


class TestEnhancedRetryDecorator:
    """Test suite for enhanced retry decorator with jitter."""

    @pytest.mark.asyncio
    async def test_retry_success_immediate(self):
        """Test successful operation on first attempt."""
        mock_func = AsyncMock(return_value="success")

        @with_retry()
        async def decorated_func():
            return await mock_func()

        result = await decorated_func()

        assert result == "success"
        assert mock_func.call_count == 1

    @pytest.mark.asyncio
    async def test_retry_success_after_failures(self):
        """Test successful operation after retries."""
        mock_func = AsyncMock(
            side_effect=[ClientError("First failure"), ClientError("Second failure"), "success"]
        )

        retry_config = RetryConfig(max_attempts=3, base_delay=0.01, jitter=False)

        @with_retry(retry_config=retry_config)
        async def decorated_func():
            return await mock_func()

        start_time = time.time()
        result = await decorated_func()
        duration = time.time() - start_time

        assert result == "success"
        assert mock_func.call_count == 3
        # Should have delays (0.01 + 0.02 = 0.03 minimum)
        assert duration >= 0.03

    @pytest.mark.asyncio
    async def test_retry_exhausted(self):
        """Test all retry attempts exhausted."""
        mock_func = AsyncMock(side_effect=ClientError("Persistent failure"))

        retry_config = RetryConfig(max_attempts=2, base_delay=0.01, jitter=False)

        @with_retry(retry_config=retry_config)
        async def decorated_func():
            return await mock_func()

        with pytest.raises(ClientError, match="Persistent failure"):
            await decorated_func()

        assert mock_func.call_count == 2

    @pytest.mark.asyncio
    async def test_retry_reraise_exceptions(self):
        """Test exceptions that should not be retried."""
        mock_func = AsyncMock(side_effect=RateLimitError("Rate limited"))

        @with_retry()
        async def decorated_func():
            return await mock_func()

        with pytest.raises(RateLimitError, match="Rate limited"):
            await decorated_func()

        # Should not retry RateLimitError
        assert mock_func.call_count == 1

    @pytest.mark.asyncio
    async def test_retry_unexpected_exceptions(self):
        """Test handling of unexpected exceptions."""
        mock_func = AsyncMock(side_effect=ValueError("Unexpected error"))

        @with_retry()
        async def decorated_func():
            return await mock_func()

        with pytest.raises(ValueError, match="Unexpected error"):
            await decorated_func()

        # Should not retry unexpected exceptions
        assert mock_func.call_count == 1

    @pytest.mark.asyncio
    async def test_retry_with_jitter_timing(self):
        """Test retry timing with jitter enabled."""
        mock_func = AsyncMock(side_effect=[ClientError("First failure"), "success"])

        retry_config = RetryConfig(max_attempts=2, base_delay=0.1, jitter=True, jitter_factor=0.5)

        @with_retry(retry_config=retry_config)
        async def decorated_func():
            return await mock_func()

        start_time = time.time()
        result = await decorated_func()
        duration = time.time() - start_time

        assert result == "success"
        assert mock_func.call_count == 2
        # With jitter, delay should be between 0.1 and base_delay (0.1)
        # Minimum enforced delay is 0.1
        assert duration >= 0.05  # Allow some test timing variance


class TestCircuitBreaker:
    """Test suite for enhanced CircuitBreaker implementation."""

    @pytest.mark.asyncio
    async def test_circuit_breaker_closed_state(self):
        """Test circuit breaker in closed state."""
        cb = CircuitBreaker(failure_threshold=2, name="test")
        mock_func = AsyncMock(return_value="success")

        async with cb:
            result = await mock_func()

        assert result == "success"
        assert cb.state == CircuitBreakerState.CLOSED
        assert cb.successful_calls == 1
        assert cb.failed_calls == 0

    @pytest.mark.asyncio
    async def test_circuit_breaker_opens_on_failures(self):
        """Test circuit breaker opens after threshold failures."""
        cb = CircuitBreaker(failure_threshold=2, name="test")

        # First failure
        with pytest.raises(ClientError):
            async with cb:
                raise ClientError("First failure")

        assert cb.state == CircuitBreakerState.CLOSED
        assert cb.failure_count == 1

        # Second failure - should open circuit
        with pytest.raises(ClientError):
            async with cb:
                raise ClientError("Second failure")

        assert cb.state == CircuitBreakerState.OPEN
        assert cb.failure_count == 2

    @pytest.mark.asyncio
    async def test_circuit_breaker_rejects_when_open(self):
        """Test circuit breaker rejects requests when open."""
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=10.0, name="test")

        # Force circuit to open
        with pytest.raises(ClientError):
            async with cb:
                raise ClientError("Failure to open circuit")

        assert cb.state == CircuitBreakerState.OPEN

        # Next request should be rejected
        with pytest.raises(RateLimitError, match="Circuit breaker 'test' is open"):
            async with cb:
                pass

    @pytest.mark.asyncio
    async def test_circuit_breaker_half_open_recovery(self):
        """Test circuit breaker half-open state and recovery."""
        cb = CircuitBreaker(
            failure_threshold=1,
            recovery_timeout=0.01,  # Very short for testing
            half_open_max_calls=2,
            name="test",
        )

        # Force circuit to open
        with pytest.raises(ClientError):
            async with cb:
                raise ClientError("Force open")

        assert cb.state == CircuitBreakerState.OPEN

        # Wait for recovery timeout
        await asyncio.sleep(0.02)

        # First request should transition to half-open
        async with cb:
            pass  # Success

        assert cb.state == CircuitBreakerState.HALF_OPEN
        assert cb.success_count == 1

        # Second success should close circuit
        async with cb:
            pass  # Success

        assert cb.state == CircuitBreakerState.CLOSED
        assert cb.failure_count == 0

    @pytest.mark.asyncio
    async def test_circuit_breaker_reopens_on_half_open_failure(self):
        """Test circuit breaker reopens on failure in half-open state."""
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.01, name="test")

        # Force circuit to open
        with pytest.raises(ClientError):
            async with cb:
                raise ClientError("Force open")

        # Wait for recovery timeout
        await asyncio.sleep(0.02)

        # Failure in half-open should reopen circuit
        with pytest.raises(ClientError):
            async with cb:
                raise ClientError("Half-open failure")

        assert cb.state == CircuitBreakerState.OPEN
        assert cb.success_count == 0

    def test_circuit_breaker_metrics(self):
        """Test circuit breaker metrics collection."""
        cb = CircuitBreaker(name="test")

        metrics = cb.metrics

        assert metrics["name"] == "test"
        assert metrics["state"] == CircuitBreakerState.CLOSED.value
        assert metrics["total_calls"] == 0
        assert metrics["successful_calls"] == 0
        assert metrics["failed_calls"] == 0
        assert metrics["success_rate"] == 0


class TestBulkheadPattern:
    """Test suite for BulkheadPattern resource isolation."""

    @pytest.mark.asyncio
    async def test_bulkhead_allows_concurrent_requests(self):
        """Test bulkhead allows requests within limit."""
        bulkhead = BulkheadPattern(max_concurrent_operations=2, name="test")

        async def slow_operation():
            await asyncio.sleep(0.1)
            return "success"

        # Start two concurrent operations (within limit)
        task1 = asyncio.create_task(bulkhead.execute(slow_operation))
        task2 = asyncio.create_task(bulkhead.execute(slow_operation))

        results = await asyncio.gather(task1, task2)

        assert results == ["success", "success"]
        assert bulkhead.total_requests == 2
        assert bulkhead.rejected_requests == 0

    @pytest.mark.asyncio
    async def test_bulkhead_rejects_excess_requests(self):
        """Test bulkhead rejects requests exceeding limit."""
        bulkhead = BulkheadPattern(max_concurrent_operations=1, name="test")

        async def slow_operation():
            await asyncio.sleep(0.1)
            return "success"

        # Start operation that will hold the semaphore
        task1 = asyncio.create_task(bulkhead.execute(slow_operation))

        # Give first task time to acquire semaphore
        await asyncio.sleep(0.01)

        # Second operation should be rejected
        with pytest.raises(RateLimitError, match="Bulkhead 'test' resource limit exceeded"):
            await bulkhead.execute(slow_operation)

        # Complete first task
        result = await task1
        assert result == "success"
        assert bulkhead.total_requests == 2
        assert bulkhead.rejected_requests == 1

    def test_bulkhead_metrics(self):
        """Test bulkhead metrics collection."""
        bulkhead = BulkheadPattern(max_concurrent_operations=5, name="test")

        metrics = bulkhead.metrics

        assert metrics["name"] == "test"
        assert metrics["max_concurrent"] == 5
        assert metrics["active_requests"] == 0
        assert metrics["total_requests"] == 0
        assert metrics["rejected_requests"] == 0
        assert metrics["acceptance_rate"] == 0


class TestResilienceManager:
    """Test suite for ResilienceManager orchestrating all patterns."""

    @pytest.mark.asyncio
    async def test_resilience_manager_retry_only(self):
        """Test resilience manager with only retry pattern."""
        retry_config = RetryConfig(max_attempts=2, base_delay=0.01, jitter=False)
        manager = ResilienceManager(retry_config=retry_config, name="test")

        mock_func = AsyncMock(side_effect=[ClientError("Fail"), "success"])

        result = await manager.execute(mock_func)

        assert result == "success"
        assert mock_func.call_count == 2

    @pytest.mark.asyncio
    async def test_resilience_manager_with_circuit_breaker(self):
        """Test resilience manager with circuit breaker pattern."""
        cb = CircuitBreaker(failure_threshold=1, name="cb_test")
        manager = ResilienceManager(circuit_breaker=cb, name="test")

        mock_func = AsyncMock(return_value="success")

        result = await manager.execute(mock_func)

        assert result == "success"
        assert cb.successful_calls == 1

    @pytest.mark.asyncio
    async def test_resilience_manager_with_bulkhead(self):
        """Test resilience manager with bulkhead pattern."""
        bulkhead = BulkheadPattern(max_concurrent_operations=1, name="bulkhead_test")
        manager = ResilienceManager(bulkhead=bulkhead, name="test")

        mock_func = AsyncMock(return_value="success")

        result = await manager.execute(mock_func)

        assert result == "success"
        assert bulkhead.total_requests == 1

    @pytest.mark.asyncio
    async def test_resilience_manager_all_patterns(self):
        """Test resilience manager with all patterns combined."""
        retry_config = RetryConfig(max_attempts=2, base_delay=0.01)
        cb = CircuitBreaker(failure_threshold=2, name="cb_test")
        bulkhead = BulkheadPattern(max_concurrent_operations=5, name="bulkhead_test")

        manager = ResilienceManager(
            retry_config=retry_config, circuit_breaker=cb, bulkhead=bulkhead, name="test"
        )

        mock_func = AsyncMock(return_value="success")

        result = await manager.execute(mock_func)

        assert result == "success"
        assert cb.successful_calls == 1
        assert bulkhead.total_requests == 1

    def test_resilience_manager_metrics(self):
        """Test comprehensive metrics from resilience manager."""
        retry_config = RetryConfig(max_attempts=3, base_delay=1.0)
        cb = CircuitBreaker(name="cb_test")
        bulkhead = BulkheadPattern(max_concurrent_operations=10, name="bulkhead_test")

        manager = ResilienceManager(
            retry_config=retry_config, circuit_breaker=cb, bulkhead=bulkhead, name="test"
        )

        metrics = manager.metrics

        assert metrics["name"] == "test"
        assert metrics["retry_config"]["max_attempts"] == 3
        assert metrics["retry_config"]["base_delay"] == 1.0
        assert metrics["retry_config"]["jitter_enabled"] is True
        assert "circuit_breaker" in metrics
        assert "bulkhead" in metrics
        assert metrics["circuit_breaker"]["name"] == "cb_test"
        assert metrics["bulkhead"]["name"] == "bulkhead_test"


@pytest.mark.integration
class TestResiliencePatternsIntegration:
    """Integration tests for all resilience patterns working together."""

    @pytest.mark.asyncio
    async def test_full_resilience_stack_failure_recovery(self):
        """Test complete resilience stack handling failures and recovery."""
        # Configure settings that allow recovery within circuit breaker limits
        retry_config = RetryConfig(
            max_attempts=2,  # Reduced to stay within circuit breaker threshold
            base_delay=0.01,
            backoff_factor=1.5,
            jitter=True,
        )
        cb = CircuitBreaker(
            failure_threshold=3,  # Allow more failures before opening
            recovery_timeout=0.05,
            name="integration_cb",
        )
        bulkhead = BulkheadPattern(max_concurrent_operations=3, name="integration_bulkhead")

        manager = ResilienceManager(
            retry_config=retry_config,
            circuit_breaker=cb,
            bulkhead=bulkhead,
            name="integration_test",
        )

        call_count = 0

        async def flaky_operation():
            nonlocal call_count
            call_count += 1

            # Fail first time, then succeed
            if call_count == 1:
                raise ClientError(f"Failure #{call_count}")
            return f"success_after_{call_count}_attempts"

        # Should succeed after retries
        result = await manager.execute(flaky_operation)

        assert result == "success_after_2_attempts"
        assert call_count == 2
        assert cb.successful_calls == 1
        assert bulkhead.total_requests == 2  # One for each retry attempt

        # Verify all metrics
        metrics = manager.metrics
        assert metrics["circuit_breaker"]["state"] == CircuitBreakerState.CLOSED.value
        assert metrics["bulkhead"]["acceptance_rate"] == 1.0

    @pytest.mark.asyncio
    async def test_circuit_breaker_prevents_cascading_failures(self):
        """Test circuit breaker prevents cascade failures across the stack."""
        # Configure retry to not interfere with circuit breaker test
        retry_config = RetryConfig(max_attempts=1)  # No retries
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=10.0, name="protection_cb")
        bulkhead = BulkheadPattern(max_concurrent_operations=5, name="protection_bulkhead")

        manager = ResilienceManager(
            retry_config=retry_config,
            circuit_breaker=cb,
            bulkhead=bulkhead,
            name="cascade_protection",
        )

        # First operation fails and opens circuit
        with pytest.raises(ClientError):
            await manager.execute(AsyncMock(side_effect=ClientError("Force open")))

        assert cb.state == CircuitBreakerState.OPEN

        # Subsequent operations should be rejected by circuit breaker
        # without consuming bulkhead resources
        initial_bulkhead_requests = bulkhead.total_requests

        with pytest.raises(RateLimitError, match="Circuit breaker"):
            await manager.execute(AsyncMock(return_value="should_not_execute"))

        # Bulkhead should not see additional requests due to circuit breaker protection
        assert bulkhead.total_requests == initial_bulkhead_requests
        assert cb.failed_calls == 1  # Only the first failure
