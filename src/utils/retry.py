"""Enhanced retry utilities with exponential backoff, jitter, and resilience patterns.

This module implements production-ready retry mechanisms following the patterns
specified in CLAUDE.md, including:
- Exponential backoff with jitter
- Circuit breaker pattern
- Bulkhead pattern for resource isolation
- Comprehensive error handling and observability
"""

import asyncio
import functools
import secrets
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from enum import Enum
from typing import Any, TypeVar

import structlog
from aiohttp import ClientError, ServerTimeoutError

from ..core.config import config
from ..core.exceptions import RateLimitError

logger = structlog.get_logger(__name__)

T = TypeVar("T")


class CircuitBreakerState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass(frozen=True)
class RetryConfig:
    """Enhanced configuration for retry behavior with jitter support.

    This configuration follows CLAUDE.md standards for centralized
    configuration management with environment variable support.
    """

    max_attempts: int = config.max_retries
    base_delay: float = 1.0
    max_delay: float = 60.0
    backoff_factor: float = config.backoff_factor
    jitter: bool = True
    jitter_factor: float = 0.1  # Add up to 10% random variation

    def __post_init__(self):
        """Validate configuration parameters."""
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        if self.base_delay <= 0:
            raise ValueError("base_delay must be positive")
        if self.backoff_factor <= 1:
            raise ValueError("backoff_factor must be greater than 1")
        if not 0 <= self.jitter_factor <= 1:
            raise ValueError("jitter_factor must be between 0 and 1")

    def calculate_delay(self, attempt: int) -> float:
        """Calculate delay with exponential backoff and jitter.

        Uses the latest jitter implementation with full decorrelated jitter
        to prevent thundering herd problems effectively.

        Args:
            attempt: Current attempt number (0-indexed)

        Returns:
            Calculated delay in seconds with jitter applied
        """
        # Calculate exponential backoff
        delay = min(self.base_delay * (self.backoff_factor**attempt), self.max_delay)

        # Apply full decorrelated jitter - latest implementation
        if self.jitter:
            # Full jitter: delay = random(0, delay)
            # This is more effective than proportional jitter
            delay = secrets.SystemRandom().uniform(0, delay)
            # Ensure minimum delay to prevent too aggressive retries
            delay = max(0.1, delay)

        return delay


def with_retry(
    retry_config: RetryConfig | None = None,
    retry_on: tuple = (ClientError, ServerTimeoutError, asyncio.TimeoutError),
    reraise_on: tuple = (RateLimitError,),
) -> Callable[[Callable[..., Awaitable[T]]], Callable[..., Awaitable[T]]]:
    """Enhanced decorator for adding retry logic with exponential backoff and jitter.

    This implementation follows CLAUDE.md requirements for production-ready
    retry mechanisms with comprehensive observability and latest jitter algorithms.

    Args:
        retry_config: Retry configuration object (uses defaults if None)
        retry_on: Exception types to retry on
        reraise_on: Exception types to immediately reraise

    Returns:
        Decorated function with enhanced retry logic
    """
    if retry_config is None:
        retry_config = RetryConfig()

    def decorator(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            last_exception = None

            for attempt in range(retry_config.max_attempts):
                try:
                    result = await func(*args, **kwargs)

                    # Log successful retry recovery
                    if attempt > 0:
                        logger.info(
                            "Successfully recovered after retries",
                            function=func.__name__,
                            attempts=attempt + 1,
                            total_attempts=retry_config.max_attempts,
                        )

                    return result

                except reraise_on as e:
                    # Don't retry these exceptions - immediate failure
                    logger.error(
                        "Non-retryable exception encountered",
                        function=func.__name__,
                        exception=type(e).__name__,
                        message=str(e),
                    )
                    raise

                except retry_on as e:
                    last_exception = e

                    # Don't sleep on final attempt
                    if attempt == retry_config.max_attempts - 1:
                        break

                    delay = retry_config.calculate_delay(attempt)

                    logger.warning(
                        "Retrying after failure with exponential backoff and full jitter",
                        function=func.__name__,
                        attempt=attempt + 1,
                        max_attempts=retry_config.max_attempts,
                        delay=round(delay, 2),
                        exception=type(e).__name__,
                        error=str(e),
                    )

                    await asyncio.sleep(delay)

                except Exception as e:
                    # Unexpected exception - log and reraise immediately
                    logger.error(
                        "Unexpected exception during retry",
                        function=func.__name__,
                        exception=type(e).__name__,
                        message=str(e),
                        attempt=attempt + 1,
                    )
                    raise

            # All retries exhausted - raise the last exception
            logger.error(
                "All retry attempts exhausted",
                function=func.__name__,
                max_attempts=retry_config.max_attempts,
                final_exception=type(last_exception).__name__ if last_exception else "Unknown",
            )

            if last_exception:
                raise last_exception
            else:
                raise RuntimeError(f"All {retry_config.max_attempts} retry attempts failed")

        return wrapper

    return decorator


class CircuitBreaker:
    """Enhanced circuit breaker implementation with comprehensive state management.

    This implementation follows CLAUDE.md patterns for production-ready
    resilience with proper observability and error handling.
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        half_open_max_calls: int = 3,
        expected_exception: type[Exception] = Exception,
        name: str = "default",
    ):
        """Initialize circuit breaker with enhanced configuration.

        Args:
            failure_threshold: Number of failures before opening circuit
            recovery_timeout: Time to wait before attempting recovery
            half_open_max_calls: Maximum calls allowed in half-open state
            expected_exception: Exception type to monitor
            name: Circuit breaker name for logging
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls
        self.expected_exception = expected_exception
        self.name = name

        # State tracking
        self.failure_count = 0
        self.success_count = 0
        self.half_open_calls = 0
        self.last_failure_time: float | None = None
        self.state = CircuitBreakerState.CLOSED

        # Metrics tracking
        self.total_calls = 0
        self.successful_calls = 0
        self.failed_calls = 0

        logger.info(
            "Circuit breaker initialized",
            name=self.name,
            failure_threshold=self.failure_threshold,
            recovery_timeout=self.recovery_timeout,
        )

    def _should_allow_request(self) -> bool:
        """Determine if request should be allowed based on current state."""
        current_time = time.time()

        if self.state == CircuitBreakerState.CLOSED:
            return True
        elif self.state == CircuitBreakerState.OPEN:
            if current_time - (self.last_failure_time or 0) >= self.recovery_timeout:
                self.state = CircuitBreakerState.HALF_OPEN
                self.half_open_calls = 0
                logger.info(
                    "Circuit breaker transitioning to half-open",
                    name=self.name,
                    recovery_timeout=self.recovery_timeout,
                )
                return True
            return False
        elif self.state == CircuitBreakerState.HALF_OPEN:
            return self.half_open_calls < self.half_open_max_calls

        return False

    async def __aenter__(self):
        """Context manager entry - check if request should be allowed."""
        if not self._should_allow_request():
            self.total_calls += 1
            raise RateLimitError(f"Circuit breaker '{self.name}' is {self.state.value}")

        self.total_calls += 1
        if self.state == CircuitBreakerState.HALF_OPEN:
            self.half_open_calls += 1

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - update state based on result."""
        if exc_type is None:
            # Success case
            self.successful_calls += 1
            self._handle_success()
        elif exc_type and issubclass(exc_type, self.expected_exception):
            # Expected failure
            self.failed_calls += 1
            self._handle_failure()
        else:
            # Unexpected exception - don't affect circuit breaker state
            logger.debug(
                "Unexpected exception in circuit breaker",
                name=self.name,
                exception=exc_type.__name__ if exc_type else None,
            )

        return False

    def _handle_success(self):
        """Handle successful operation."""
        if self.state == CircuitBreakerState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.half_open_max_calls:
                self.state = CircuitBreakerState.CLOSED
                self.failure_count = 0
                self.success_count = 0
                logger.info(
                    "Circuit breaker closed after successful recovery",
                    name=self.name,
                    recovery_attempts=self.success_count,
                )
        else:
            # Reset failure count on success in closed state
            self.failure_count = max(0, self.failure_count - 1)

    def _handle_failure(self):
        """Handle failed operation."""
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.state == CircuitBreakerState.HALF_OPEN:
            # Failure in half-open state - go back to open
            self.state = CircuitBreakerState.OPEN
            self.success_count = 0
            logger.warning(
                "Circuit breaker reopened after failure in half-open state",
                name=self.name,
                failure_count=self.failure_count,
            )
        elif self.failure_count >= self.failure_threshold:
            # Too many failures - open the circuit
            self.state = CircuitBreakerState.OPEN
            logger.warning(
                "Circuit breaker opened due to failure threshold exceeded",
                name=self.name,
                failure_count=self.failure_count,
                threshold=self.failure_threshold,
            )

    @property
    def metrics(self) -> dict[str, Any]:
        """Get circuit breaker metrics for monitoring."""
        return {
            "name": self.name,
            "state": self.state.value,
            "total_calls": self.total_calls,
            "successful_calls": self.successful_calls,
            "failed_calls": self.failed_calls,
            "failure_count": self.failure_count,
            "success_rate": (
                self.successful_calls / self.total_calls if self.total_calls > 0 else 0
            ),
            "last_failure_time": self.last_failure_time,
        }


class BulkheadPattern:
    """Bulkhead pattern implementation for resource isolation.

    This pattern prevents cascade failures by isolating resources
    and limiting concurrent operations as specified in CLAUDE.md.
    """

    def __init__(self, max_concurrent_operations: int = 10, name: str = "default"):
        """Initialize bulkhead with resource limits.

        Args:
            max_concurrent_operations: Maximum concurrent operations allowed
            name: Bulkhead name for logging and metrics
        """
        self.max_concurrent_operations = max_concurrent_operations
        self.name = name
        self.semaphore = asyncio.Semaphore(max_concurrent_operations)

        # Metrics tracking
        self.total_requests = 0
        self.rejected_requests = 0
        self.active_requests = 0

        logger.info(
            "Bulkhead initialized",
            name=self.name,
            max_concurrent=max_concurrent_operations,
        )

    async def execute(self, func: Callable[..., Awaitable[T]], *args, **kwargs) -> T:
        """Execute function with resource isolation.

        Args:
            func: Async function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments

        Returns:
            Function result

        Raises:
            RateLimitError: If resource limits exceeded
        """
        self.total_requests += 1

        if self.semaphore.locked():
            self.rejected_requests += 1
            logger.warning(
                "Bulkhead request rejected - resource limit exceeded",
                name=self.name,
                active_requests=self.active_requests,
                max_concurrent=self.max_concurrent_operations,
            )
            raise RateLimitError(f"Bulkhead '{self.name}' resource limit exceeded")

        async with self.semaphore:
            self.active_requests += 1
            try:
                logger.debug(
                    "Executing request in bulkhead",
                    name=self.name,
                    active_requests=self.active_requests,
                )
                result = await func(*args, **kwargs)
                return result
            finally:
                self.active_requests -= 1

    @property
    def metrics(self) -> dict[str, Any]:
        """Get bulkhead metrics for monitoring."""
        return {
            "name": self.name,
            "max_concurrent": self.max_concurrent_operations,
            "active_requests": self.active_requests,
            "total_requests": self.total_requests,
            "rejected_requests": self.rejected_requests,
            "acceptance_rate": (
                (self.total_requests - self.rejected_requests) / self.total_requests
                if self.total_requests > 0
                else 0
            ),
        }


class ResilienceManager:
    """Comprehensive resilience manager combining multiple patterns.

    This class orchestrates retry, circuit breaker, and bulkhead patterns
    for maximum reliability as specified in CLAUDE.md.
    """

    def __init__(
        self,
        retry_config: RetryConfig | None = None,
        circuit_breaker: CircuitBreaker | None = None,
        bulkhead: BulkheadPattern | None = None,
        name: str = "default",
    ):
        """Initialize resilience manager with all patterns.

        Args:
            retry_config: Retry configuration
            circuit_breaker: Circuit breaker instance
            bulkhead: Bulkhead pattern instance
            name: Manager name for logging
        """
        self.retry_config = retry_config or RetryConfig()
        self.circuit_breaker = circuit_breaker
        self.bulkhead = bulkhead
        self.name = name

        logger.info(
            "Resilience manager initialized",
            name=self.name,
            has_circuit_breaker=circuit_breaker is not None,
            has_bulkhead=bulkhead is not None,
        )

    async def execute(
        self,
        func: Callable[..., Awaitable[T]],
        *args,
        retry_on: tuple = (ClientError, ServerTimeoutError, asyncio.TimeoutError),
        reraise_on: tuple = (RateLimitError,),
        **kwargs,
    ) -> T:
        """Execute function with all resilience patterns applied.

        Args:
            func: Async function to execute
            *args: Function arguments
            retry_on: Exception types to retry on
            reraise_on: Exception types to immediately reraise
            **kwargs: Function keyword arguments

        Returns:
            Function result with all resilience patterns applied
        """

        async def _execute_with_patterns():
            """Execute with circuit breaker and bulkhead patterns."""
            if self.circuit_breaker and self.bulkhead:
                # Apply both circuit breaker and bulkhead
                async with self.circuit_breaker:
                    return await self.bulkhead.execute(func, *args, **kwargs)
            elif self.circuit_breaker:
                # Apply only circuit breaker
                async with self.circuit_breaker:
                    return await func(*args, **kwargs)
            elif self.bulkhead:
                # Apply only bulkhead
                return await self.bulkhead.execute(func, *args, **kwargs)
            else:
                # No additional patterns
                return await func(*args, **kwargs)

        # Apply retry pattern
        retry_decorator = with_retry(
            retry_config=self.retry_config,
            retry_on=retry_on,
            reraise_on=reraise_on,
        )

        return await retry_decorator(_execute_with_patterns)()

    @property
    def metrics(self) -> dict[str, Any]:
        """Get comprehensive metrics from all patterns."""
        metrics = {
            "name": self.name,
            "retry_config": {
                "max_attempts": self.retry_config.max_attempts,
                "base_delay": self.retry_config.base_delay,
                "backoff_factor": self.retry_config.backoff_factor,
                "jitter_enabled": self.retry_config.jitter,
            },
        }

        if self.circuit_breaker:
            metrics["circuit_breaker"] = self.circuit_breaker.metrics

        if self.bulkhead:
            metrics["bulkhead"] = self.bulkhead.metrics

        return metrics
