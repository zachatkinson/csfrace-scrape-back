"""Comprehensive tests for retry utilities - MANDATORY TEST_BUILDING.md compliance.

This module tests retry, circuit breaker, and bulkhead resilience patterns:
- RetryConfig validation and delay calculation
- Exponential backoff with jitter
- with_retry decorator functionality
- Circuit breaker state transitions
- Bulkhead resource isolation
- ResilienceManager pattern orchestration
- Comprehensive error handling
- Performance benchmarks

ALL tests follow MANDATORY TEST_BUILDING.md patterns:
- AAA pattern with explicit comments
- Factory fixtures for DRY principle
- Comprehensive resilience pattern testing
- Performance benchmarks with specific thresholds
"""

import time

import asyncio
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

# ============================================================================
# Test Fixtures - DRY Principle
# ============================================================================


@pytest.fixture
def default_retry_config() -> RetryConfig:
    """Factory for default RetryConfig - DRY principle."""
    return RetryConfig()


@pytest.fixture
def custom_retry_config() -> RetryConfig:
    """Factory for custom RetryConfig - DRY principle."""
    return RetryConfig(
        max_attempts=5,
        base_delay=2.0,
        max_delay=30.0,
        backoff_factor=3.0,
        jitter=False,
        jitter_factor=0.2,
    )


@pytest.fixture
def circuit_breaker() -> CircuitBreaker:
    """Factory for CircuitBreaker - DRY principle."""
    return CircuitBreaker(
        failure_threshold=3,
        recovery_timeout=5.0,
        half_open_max_calls=2,
        name="test_breaker",
    )


@pytest.fixture
def bulkhead() -> BulkheadPattern:
    """Factory for BulkheadPattern - DRY principle."""
    return BulkheadPattern(max_concurrent_operations=5, name="test_bulkhead")


@pytest.fixture
def resilience_manager(
    custom_retry_config: RetryConfig,
    circuit_breaker: CircuitBreaker,
    bulkhead: BulkheadPattern,
) -> ResilienceManager:
    """Factory for ResilienceManager - DRY principle."""
    return ResilienceManager(
        retry_config=custom_retry_config,
        circuit_breaker=circuit_breaker,
        bulkhead=bulkhead,
        name="test_manager",
    )


# ============================================================================
# RetryConfig Tests
# ============================================================================


@pytest.mark.unit
class TestRetryConfig:
    """Tests for RetryConfig initialization and validation."""

    def test_retry_config_initialization_with_defaults(self):
        """Test RetryConfig initializes with defaults - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # (no setup needed)

        # Act - MANDATORY
        config = RetryConfig()

        # Assert - MANDATORY
        assert config.max_attempts >= 1
        assert config.base_delay > 0
        assert config.max_delay > config.base_delay
        assert config.backoff_factor >= 1
        assert config.jitter is True
        assert 0 <= config.jitter_factor <= 1

    def test_retry_config_initialization_with_custom_values(self):
        """Test RetryConfig with custom values - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        max_attempts = 5
        base_delay = 2.0
        max_delay = 30.0
        backoff_factor = 3.0

        # Act - MANDATORY
        config = RetryConfig(
            max_attempts=max_attempts,
            base_delay=base_delay,
            max_delay=max_delay,
            backoff_factor=backoff_factor,
        )

        # Assert - MANDATORY
        assert config.max_attempts == max_attempts
        assert config.base_delay == base_delay
        assert config.max_delay == max_delay
        assert config.backoff_factor == backoff_factor

    def test_retry_config_validates_max_attempts(self):
        """Test RetryConfig validates max_attempts - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        invalid_max_attempts = 0

        # Act & Assert - MANDATORY
        with pytest.raises(ValueError, match="max_attempts must be at least 1"):
            RetryConfig(max_attempts=invalid_max_attempts)

    def test_retry_config_validates_base_delay(self):
        """Test RetryConfig validates base_delay - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        invalid_base_delay = -1.0

        # Act & Assert - MANDATORY
        with pytest.raises(ValueError, match="base_delay must be positive"):
            RetryConfig(base_delay=invalid_base_delay)

    def test_retry_config_validates_backoff_factor(self):
        """Test RetryConfig validates backoff_factor - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        invalid_backoff_factor = 0.5

        # Act & Assert - MANDATORY
        with pytest.raises(ValueError, match="backoff_factor must be at least 1"):
            RetryConfig(backoff_factor=invalid_backoff_factor)

    def test_retry_config_validates_jitter_factor(self):
        """Test RetryConfig validates jitter_factor - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        invalid_jitter_factor = 1.5

        # Act & Assert - MANDATORY
        with pytest.raises(ValueError, match="jitter_factor must be between 0 and 1"):
            RetryConfig(jitter_factor=invalid_jitter_factor)

    def test_calculate_delay_without_jitter(self):
        """Test delay calculation without jitter - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        config = RetryConfig(base_delay=1.0, backoff_factor=2.0, jitter=False)

        # Act - MANDATORY
        delay_0 = config.calculate_delay(0)
        delay_1 = config.calculate_delay(1)
        delay_2 = config.calculate_delay(2)

        # Assert - MANDATORY
        assert delay_0 == 1.0  # 1.0 * 2^0
        assert delay_1 == 2.0  # 1.0 * 2^1
        assert delay_2 == 4.0  # 1.0 * 2^2

    def test_calculate_delay_with_jitter(self):
        """Test delay calculation with jitter - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        config = RetryConfig(base_delay=1.0, backoff_factor=2.0, jitter=True)

        # Act - MANDATORY
        delays = [config.calculate_delay(1) for _ in range(10)]

        # Assert - MANDATORY
        # All delays should be >= minimum delay (0.1)
        assert all(delay >= 0.1 for delay in delays)
        # Delays should vary (jitter applied)
        assert len(set(delays)) > 1  # Should have variation

    def test_calculate_delay_respects_max_delay(self):
        """Test delay calculation respects max_delay - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        config = RetryConfig(base_delay=1.0, backoff_factor=10.0, max_delay=5.0, jitter=False)

        # Act - MANDATORY
        delay_10 = config.calculate_delay(10)

        # Assert - MANDATORY
        assert delay_10 <= config.max_delay


# ============================================================================
# with_retry Decorator Tests
# ============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
class TestWithRetryDecorator:
    """Tests for with_retry decorator functionality."""

    async def test_with_retry_succeeds_on_first_attempt(self):
        """Test with_retry succeeds immediately - MANDATORY AAA pattern."""

        # Arrange - MANDATORY
        @with_retry()
        async def successful_func():
            return "success"

        # Act - MANDATORY
        result = await successful_func()

        # Assert - MANDATORY
        assert result == "success"

    async def test_with_retry_retries_on_client_error(self):
        """Test with_retry retries on ClientError - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        attempt_count = 0

        @with_retry(retry_config=RetryConfig(max_attempts=3, base_delay=0.01, jitter=False))
        async def failing_then_success():
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count < 3:
                raise ClientError("Test error")
            return "success"

        # Act - MANDATORY
        result = await failing_then_success()

        # Assert - MANDATORY
        assert result == "success"
        assert attempt_count == 3

    async def test_with_retry_retries_on_timeout_error(self):
        """Test with_retry retries on TimeoutError - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        attempt_count = 0

        @with_retry(retry_config=RetryConfig(max_attempts=2, base_delay=0.01, jitter=False))
        async def timeout_then_success():
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count < 2:
                raise TimeoutError("Timeout")
            return "recovered"

        # Act - MANDATORY
        result = await timeout_then_success()

        # Assert - MANDATORY
        assert result == "recovered"
        assert attempt_count == 2

    async def test_with_retry_immediately_reraises_rate_limit_error(self):
        """Test with_retry immediately reraises RateLimitError - MANDATORY AAA pattern."""

        # Arrange - MANDATORY
        @with_retry()
        async def rate_limited_func():
            raise RateLimitError("Rate limited")

        # Act & Assert - MANDATORY
        with pytest.raises(RateLimitError, match="Rate limited"):
            await rate_limited_func()

    async def test_with_retry_exhausts_all_attempts(self):
        """Test with_retry exhausts all attempts - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        attempt_count = 0

        @with_retry(retry_config=RetryConfig(max_attempts=3, base_delay=0.01, jitter=False))
        async def always_fails():
            nonlocal attempt_count
            attempt_count += 1
            raise ClientError("Persistent error")

        # Act & Assert - MANDATORY
        with pytest.raises(ClientError, match="Persistent error"):
            await always_fails()

        assert attempt_count == 3

    async def test_with_retry_custom_retry_on_exceptions(self):
        """Test with_retry with custom retry_on exceptions - MANDATORY AAA pattern."""

        # Arrange - MANDATORY
        class CustomError(Exception):
            pass

        @with_retry(
            retry_on=(CustomError,),
            retry_config=RetryConfig(max_attempts=2, base_delay=0.01, jitter=False),
        )
        async def custom_error_func():
            raise CustomError("Custom")

        # Act & Assert - MANDATORY
        with pytest.raises(CustomError):
            await custom_error_func()

    async def test_with_retry_propagates_unexpected_exceptions(self):
        """Test with_retry propagates unexpected exceptions - MANDATORY AAA pattern."""

        # Arrange - MANDATORY
        @with_retry(retry_config=RetryConfig(max_attempts=3, base_delay=0.01))
        async def unexpected_error():
            raise ValueError("Unexpected")

        # Act & Assert - MANDATORY
        with pytest.raises(ValueError, match="Unexpected"):
            await unexpected_error()


# ============================================================================
# CircuitBreaker Tests
# ============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
class TestCircuitBreaker:
    """Tests for CircuitBreaker pattern implementation."""

    async def test_circuit_breaker_initialization(self):
        """Test CircuitBreaker initializes correctly - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        failure_threshold = 5
        recovery_timeout = 10.0

        # Act - MANDATORY
        breaker = CircuitBreaker(
            failure_threshold=failure_threshold,
            recovery_timeout=recovery_timeout,
            name="test",
        )

        # Assert - MANDATORY
        assert breaker.failure_threshold == failure_threshold
        assert breaker.recovery_timeout == recovery_timeout
        assert breaker.state == CircuitBreakerState.CLOSED
        assert breaker.failure_count == 0

    async def test_circuit_breaker_allows_requests_when_closed(
        self, circuit_breaker: CircuitBreaker
    ):
        """Test circuit breaker allows requests when closed - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        assert circuit_breaker.state == CircuitBreakerState.CLOSED

        # Act - MANDATORY
        async with circuit_breaker:
            result = "success"

        # Assert - MANDATORY
        assert result == "success"
        assert circuit_breaker.state == CircuitBreakerState.CLOSED

    async def test_circuit_breaker_opens_after_threshold_failures(self):
        """Test circuit breaker opens after threshold - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        breaker = CircuitBreaker(failure_threshold=2, name="test_open")

        # Act - MANDATORY
        # First failure
        try:
            async with breaker:
                raise Exception("Failure 1")
        except Exception:
            pass

        # Second failure - should open circuit
        try:
            async with breaker:
                raise Exception("Failure 2")
        except Exception:
            pass

        # Assert - MANDATORY
        assert breaker.state == CircuitBreakerState.OPEN
        assert breaker.failure_count == 2

    async def test_circuit_breaker_blocks_requests_when_open(self):
        """Test circuit breaker blocks requests when open - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        breaker = CircuitBreaker(failure_threshold=1, name="test_block")

        # Open the circuit
        try:
            async with breaker:
                raise Exception("Open circuit")
        except Exception:
            pass

        # Act & Assert - MANDATORY
        assert breaker.state == CircuitBreakerState.OPEN
        with pytest.raises(RateLimitError, match="Circuit breaker.*is open"):
            async with breaker:
                pass

    async def test_circuit_breaker_transitions_to_half_open(self):
        """Test circuit breaker transitions to half-open - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        breaker = CircuitBreaker(
            failure_threshold=1,
            recovery_timeout=0.1,
            name="test_half_open",
        )

        # Open the circuit
        try:
            async with breaker:
                raise Exception("Open")
        except Exception:
            pass

        # Act - MANDATORY
        # Wait for recovery timeout
        await asyncio.sleep(0.15)

        # Try a request - should transition to half-open
        async with breaker:
            pass

        # Assert - MANDATORY (state is checked internally in _should_allow_request)
        # After successful request in half-open, might still be half-open or closed
        # depending on half_open_max_calls
        assert breaker.state in (CircuitBreakerState.HALF_OPEN, CircuitBreakerState.CLOSED)

    async def test_circuit_breaker_closes_after_recovery(self):
        """Test circuit breaker closes after successful recovery - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        breaker = CircuitBreaker(
            failure_threshold=1,
            recovery_timeout=0.1,
            half_open_max_calls=2,
            name="test_close",
        )

        # Open the circuit
        try:
            async with breaker:
                raise Exception("Open")
        except Exception:
            pass

        # Wait for recovery
        await asyncio.sleep(0.15)

        # Act - MANDATORY
        # Successful requests in half-open state
        async with breaker:
            pass
        async with breaker:
            pass

        # Assert - MANDATORY
        assert breaker.state == CircuitBreakerState.CLOSED
        assert breaker.failure_count == 0

    async def test_circuit_breaker_metrics(self, circuit_breaker: CircuitBreaker):
        """Test circuit breaker provides metrics - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # Make some calls
        async with circuit_breaker:
            pass

        # Act - MANDATORY
        metrics = circuit_breaker.metrics

        # Assert - MANDATORY
        assert "name" in metrics
        assert "state" in metrics
        assert "total_calls" in metrics
        assert "successful_calls" in metrics
        assert "failed_calls" in metrics
        assert metrics["total_calls"] >= 1


# ============================================================================
# BulkheadPattern Tests
# ============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
class TestBulkheadPattern:
    """Tests for BulkheadPattern resource isolation."""

    async def test_bulkhead_initialization(self):
        """Test BulkheadPattern initializes correctly - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        max_concurrent = 10

        # Act - MANDATORY
        bulkhead = BulkheadPattern(max_concurrent_operations=max_concurrent, name="test")

        # Assert - MANDATORY
        assert bulkhead.max_concurrent_operations == max_concurrent
        assert bulkhead.active_requests == 0
        assert bulkhead.total_requests == 0

    async def test_bulkhead_executes_within_limit(self, bulkhead: BulkheadPattern):
        """Test bulkhead executes within limit - MANDATORY AAA pattern."""

        # Arrange - MANDATORY
        async def test_func():
            return "success"

        # Act - MANDATORY
        result = await bulkhead.execute(test_func)

        # Assert - MANDATORY
        assert result == "success"
        assert bulkhead.total_requests == 1

    async def test_bulkhead_enforces_concurrency_limit(self):
        """Test bulkhead enforces concurrency limit - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        bulkhead = BulkheadPattern(max_concurrent_operations=2, name="test_limit")

        async def slow_func():
            await asyncio.sleep(0.1)
            return "done"

        # Act & Assert - MANDATORY
        # Start 2 concurrent operations (at limit)
        task1 = asyncio.create_task(bulkhead.execute(slow_func))
        task2 = asyncio.create_task(bulkhead.execute(slow_func))

        # Wait a bit for tasks to start
        await asyncio.sleep(0.01)

        # Third operation should be rejected
        with pytest.raises(RateLimitError, match="resource limit exceeded"):
            await bulkhead.execute(slow_func)

        # Wait for tasks to complete
        await task1
        await task2

    async def test_bulkhead_metrics(self, bulkhead: BulkheadPattern):
        """Test bulkhead provides metrics - MANDATORY AAA pattern."""

        # Arrange - MANDATORY
        async def test_func():
            return "test"

        await bulkhead.execute(test_func)

        # Act - MANDATORY
        metrics = bulkhead.metrics

        # Assert - MANDATORY
        assert "name" in metrics
        assert "max_concurrent" in metrics
        assert "total_requests" in metrics
        assert "rejected_requests" in metrics
        assert "acceptance_rate" in metrics


# ============================================================================
# ResilienceManager Tests
# ============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
class TestResilienceManager:
    """Tests for ResilienceManager pattern orchestration."""

    async def test_resilience_manager_initialization(self, resilience_manager: ResilienceManager):
        """Test ResilienceManager initializes correctly - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # (resilience_manager from fixture)

        # Act - MANDATORY
        # (initialization done in fixture)

        # Assert - MANDATORY
        assert resilience_manager.retry_config is not None
        assert resilience_manager.circuit_breaker is not None
        assert resilience_manager.bulkhead is not None
        assert resilience_manager.name == "test_manager"

    async def test_resilience_manager_executes_successfully(self):
        """Test ResilienceManager executes successfully - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        manager = ResilienceManager(name="test_exec")

        async def test_func():
            return "success"

        # Act - MANDATORY
        result = await manager.execute(test_func)

        # Assert - MANDATORY
        assert result == "success"

    async def test_resilience_manager_applies_retry_pattern(self):
        """Test ResilienceManager applies retry pattern - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        manager = ResilienceManager(
            retry_config=RetryConfig(max_attempts=3, base_delay=0.01, jitter=False),
            name="test_retry",
        )

        attempt_count = 0

        async def failing_func():
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count < 3:
                raise ClientError("Retry")
            return "recovered"

        # Act - MANDATORY
        result = await manager.execute(failing_func)

        # Assert - MANDATORY
        assert result == "recovered"
        assert attempt_count == 3

    async def test_resilience_manager_metrics(self, resilience_manager: ResilienceManager):
        """Test ResilienceManager provides comprehensive metrics - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # (resilience_manager from fixture)

        # Act - MANDATORY
        metrics = resilience_manager.metrics

        # Assert - MANDATORY
        assert "name" in metrics
        assert "retry_config" in metrics
        assert "circuit_breaker" in metrics
        assert "bulkhead" in metrics


# ============================================================================
# MANDATORY Performance Benchmarks
# ============================================================================


@pytest.mark.performance
@pytest.mark.unit
class TestRetryPerformance:
    """MANDATORY performance tests for retry utilities."""

    def test_retry_config_initialization_performance(self):
        """MANDATORY performance test - RetryConfig initialization speed."""
        # Arrange - MANDATORY
        iterations = 10000

        # Act - MANDATORY
        start_time = time.perf_counter()

        for _ in range(iterations):
            RetryConfig()

        end_time = time.perf_counter()
        execution_time = end_time - start_time

        # Assert - MANDATORY
        avg_time = execution_time / iterations
        assert avg_time < 0.0001  # <0.1ms per initialization
        assert execution_time < 1.0  # Total <1s for 10000 initializations

    def test_delay_calculation_performance(self, default_retry_config: RetryConfig):
        """MANDATORY performance test - delay calculation speed."""
        # Arrange - MANDATORY
        iterations = 100000

        # Act - MANDATORY
        start_time = time.perf_counter()

        for i in range(iterations):
            default_retry_config.calculate_delay(i % 10)

        end_time = time.perf_counter()
        execution_time = end_time - start_time

        # Assert - MANDATORY
        avg_time = execution_time / iterations
        assert avg_time < 0.00001  # <0.01ms per calculation
        assert execution_time < 1.0  # Total <1s for 100000 calculations

    @pytest.mark.asyncio
    async def test_circuit_breaker_overhead_performance(self):
        """MANDATORY performance test - circuit breaker overhead."""
        # Arrange - MANDATORY
        breaker = CircuitBreaker(name="perf_test")
        iterations = 1000

        async def fast_func():
            return "done"

        # Act - MANDATORY
        start_time = time.perf_counter()

        for _ in range(iterations):
            async with breaker:
                await fast_func()

        end_time = time.perf_counter()
        execution_time = end_time - start_time

        # Assert - MANDATORY
        avg_time = execution_time / iterations
        assert avg_time < 0.001  # <1ms per operation with circuit breaker
        assert execution_time < 1.0  # Total <1s for 1000 operations
