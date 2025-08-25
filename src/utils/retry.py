"""Retry utilities with exponential backoff."""

import asyncio
import functools
from collections.abc import Awaitable
from typing import Any, Callable, Optional, TypeVar

import structlog
from aiohttp import ClientError, ServerTimeoutError
from tenacity import (
    AsyncRetrying,
    before_sleep_log,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from ..core.config import config
from ..core.exceptions import RateLimitError

logger = structlog.get_logger(__name__)

T = TypeVar("T")


def with_retry(
    max_attempts: int = config.max_retries,
    backoff_factor: float = config.backoff_factor,
    retry_on: tuple = (ClientError, ServerTimeoutError, asyncio.TimeoutError),
    reraise_on: tuple = (RateLimitError,),
) -> Callable[[Callable[..., Awaitable[T]]], Callable[..., Awaitable[T]]]:
    """Decorator for adding retry logic with exponential backoff.

    Args:
        max_attempts: Maximum number of retry attempts
        backoff_factor: Exponential backoff factor
        retry_on: Exception types to retry on
        reraise_on: Exception types to immediately reraise

    Returns:
        Decorated function with retry logic
    """

    def decorator(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            # Create retry configuration
            retry_config = AsyncRetrying(
                stop=stop_after_attempt(max_attempts),
                wait=wait_exponential(multiplier=1, min=1, max=60, base=backoff_factor),
                retry=retry_if_exception_type(retry_on),
                before_sleep=before_sleep_log(logger, logging_level=20),  # INFO level
                reraise=True,
            )

            async for attempt in retry_config:
                with attempt:
                    try:
                        return await func(*args, **kwargs)
                    except reraise_on:
                        # Don't retry these exceptions
                        raise
                    except retry_on as e:
                        logger.warning(
                            "Retrying after failure",
                            function=func.__name__,
                            attempt=attempt.retry_state.attempt_number,
                            error=str(e),
                        )
                        raise

        return wrapper

    return decorator


class CircuitBreaker:
    """Simple circuit breaker implementation."""

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        expected_exception: type[Exception] = Exception,
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception

        self.failure_count = 0
        self.last_failure_time: Optional[float] = None
        self.state = "closed"  # closed, open, half-open

    async def __aenter__(self):
        if self.state == "open":
            if asyncio.get_event_loop().time() - self.last_failure_time < self.recovery_timeout:
                raise RateLimitError("Circuit breaker is open")
            else:
                self.state = "half-open"

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            # Success
            if self.state == "half-open":
                self.state = "closed"
                self.failure_count = 0
        elif issubclass(exc_type, self.expected_exception):
            # Expected failure
            self.failure_count += 1
            self.last_failure_time = asyncio.get_event_loop().time()

            if self.failure_count >= self.failure_threshold:
                self.state = "open"
                logger.warning(
                    "Circuit breaker opened",
                    failure_count=self.failure_count,
                    threshold=self.failure_threshold,
                )

        return False
