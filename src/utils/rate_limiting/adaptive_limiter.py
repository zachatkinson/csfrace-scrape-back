"""Adaptive rate limiter that adjusts based on system performance and errors.

Automatically tightens rate limits when errors increase and loosens them
when the system is performing well. This provides automatic backpressure
without manual intervention.
"""

import contextlib
import time
from dataclasses import dataclass

import asyncio

from src.core.logging_hierarchy import get_core_logger

from .token_bucket import TokenBucket, TokenBucketConfig

logger = get_core_logger()


@dataclass
class AdaptiveConfig:
    """Configuration for adaptive rate limiter."""

    base_capacity: int  # Base bucket capacity
    base_refill_rate: float  # Base refill rate
    min_capacity: int  # Minimum allowed capacity
    max_capacity: int  # Maximum allowed capacity
    adjustment_factor: float = 0.1  # How aggressively to adjust (0.0-1.0)
    error_threshold: float = 0.05  # Error rate threshold to trigger tightening
    success_threshold: float = 0.99  # Success rate to trigger loosening
    evaluation_window: float = 60.0  # Seconds to evaluate performance

    def __post_init__(self) -> None:
        """Validate configuration."""
        if self.min_capacity <= 0:
            raise ValueError("Min capacity must be positive")
        if self.max_capacity < self.min_capacity:
            raise ValueError("Max capacity must be >= min capacity")
        if not (self.min_capacity <= self.base_capacity <= self.max_capacity):
            raise ValueError("Base capacity must be between min and max")
        if not (0.0 < self.adjustment_factor <= 1.0):
            raise ValueError("Adjustment factor must be between 0 and 1")
        if not (0.0 <= self.error_threshold <= 1.0):
            raise ValueError("Error threshold must be between 0 and 1")
        if not (0.0 <= self.success_threshold <= 1.0):
            raise ValueError("Success threshold must be between 0 and 1")


class AdaptiveRateLimiter:
    """Rate limiter that adapts based on system performance.

    Monitors request success/failure rates and automatically adjusts
    rate limits to provide backpressure when the system is struggling
    and allow more throughput when it's healthy.

    Example:
        limiter = AdaptiveRateLimiter(AdaptiveConfig(
            base_capacity=100,
            base_refill_rate=10.0,
            min_capacity=20,
            max_capacity=200,
        ))

        if await limiter.consume("user123"):
            try:
                result = process_request()
                await limiter.record_success("user123")
                return result
            except Exception as e:
                await limiter.record_failure("user123")
                raise
        else:
            return rate_limit_error()
    """

    def __init__(self, config: AdaptiveConfig) -> None:
        """Initialize adaptive rate limiter."""
        self.config = config
        self._buckets: dict[str, TokenBucket] = {}
        self._bucket_configs: dict[str, TokenBucketConfig] = {}
        self._performance_data: dict[str, dict[str, float]] = {}
        self._lock = asyncio.Lock()

        # Start background adjustment task
        self._adjustment_task = asyncio.create_task(self._adjustment_loop())

        logger.info(
            "Adaptive rate limiter initialized",
            base_capacity=config.base_capacity,
            base_refill_rate=config.base_refill_rate,
            adjustment_factor=config.adjustment_factor,
        )

    async def consume(self, key: str, tokens: int = 1) -> bool:
        """Attempt to consume tokens for the given key."""
        bucket = await self._get_or_create_bucket(key)
        return await bucket.consume(tokens)

    async def record_success(self, key: str) -> None:
        """Record a successful request for the given key."""
        await self._record_outcome(key, success=True)

    async def record_failure(self, key: str) -> None:
        """Record a failed request for the given key."""
        await self._record_outcome(key, success=False)

    async def _record_outcome(self, key: str, success: bool) -> None:
        """Record request outcome for performance tracking."""
        async with self._lock:
            now = time.time()

            if key not in self._performance_data:
                self._performance_data[key] = {
                    "successes": 0,
                    "failures": 0,
                    "last_reset": now,
                }

            data = self._performance_data[key]

            # Reset counters if evaluation window has passed
            if now - data["last_reset"] > self.config.evaluation_window:
                data["successes"] = 0
                data["failures"] = 0
                data["last_reset"] = now

            if success:
                data["successes"] += 1
            else:
                data["failures"] += 1

            logger.debug(
                "Recorded request outcome",
                key=key,
                success=success,
                total_successes=data["successes"],
                total_failures=data["failures"],
            )

    async def _get_or_create_bucket(self, key: str) -> TokenBucket:
        """Get or create a token bucket for the given key."""
        async with self._lock:
            if key not in self._buckets:
                # Create new bucket with base configuration
                bucket_config = TokenBucketConfig(
                    capacity=self.config.base_capacity,
                    refill_rate=self.config.base_refill_rate,
                )
                self._buckets[key] = TokenBucket(bucket_config)
                self._bucket_configs[key] = bucket_config

                logger.debug("Created adaptive bucket", key=key)

            return self._buckets[key]

    async def _adjustment_loop(self) -> None:
        """Background task to adjust rate limits based on performance."""
        while True:
            try:
                await asyncio.sleep(self.config.evaluation_window)
                await self._adjust_rate_limits()
            except asyncio.CancelledError:
                logger.info("Adaptive adjustment loop cancelled")
                break
            except Exception as e:
                logger.error("Error in adjustment loop", error=str(e))
                await asyncio.sleep(10)  # Back off on error

    async def _adjust_rate_limits(self) -> None:
        """Adjust rate limits based on recent performance data."""
        async with self._lock:
            for key, data in list(self._performance_data.items()):
                total_requests = data["successes"] + data["failures"]

                if total_requests == 0:
                    continue  # No data to work with

                error_rate = data["failures"] / total_requests
                success_rate = data["successes"] / total_requests

                current_config = self._bucket_configs[key]
                new_capacity = current_config.capacity
                new_refill_rate = current_config.refill_rate

                # Tighten limits if error rate is high
                if error_rate > self.config.error_threshold:
                    adjustment = 1.0 - self.config.adjustment_factor
                    new_capacity = max(
                        self.config.min_capacity, int(current_config.capacity * adjustment)
                    )
                    new_refill_rate = max(
                        self.config.min_capacity / 60.0,  # At least 1 token per minute
                        current_config.refill_rate * adjustment,
                    )

                    logger.info(
                        "Tightening rate limit due to high error rate",
                        key=key,
                        error_rate=error_rate,
                        old_capacity=current_config.capacity,
                        new_capacity=new_capacity,
                    )

                # Loosen limits if success rate is high and we're below base
                elif (
                    success_rate > self.config.success_threshold
                    and current_config.capacity < self.config.base_capacity
                ):
                    adjustment = 1.0 + self.config.adjustment_factor
                    new_capacity = min(
                        self.config.max_capacity, int(current_config.capacity * adjustment)
                    )
                    new_refill_rate = min(
                        self.config.max_capacity / 10.0,  # Max 1/10 capacity per second
                        current_config.refill_rate * adjustment,
                    )

                    logger.info(
                        "Loosening rate limit due to high success rate",
                        key=key,
                        success_rate=success_rate,
                        old_capacity=current_config.capacity,
                        new_capacity=new_capacity,
                    )

                # Apply changes if significant
                if (
                    abs(new_capacity - current_config.capacity) > 1
                    or abs(new_refill_rate - current_config.refill_rate) > 0.1
                ):
                    # Create new bucket with updated configuration
                    new_config = TokenBucketConfig(
                        capacity=new_capacity,
                        refill_rate=new_refill_rate,
                    )

                    # Preserve current token count if possible
                    old_bucket = self._buckets[key]
                    current_tokens = await old_bucket.get_available_tokens()
                    preserved_tokens = min(current_tokens, new_capacity)

                    new_config.initial_tokens = int(preserved_tokens)

                    self._buckets[key] = TokenBucket(new_config)
                    self._bucket_configs[key] = new_config

                    logger.info(
                        "Applied rate limit adjustment",
                        key=key,
                        new_capacity=new_capacity,
                        new_refill_rate=new_refill_rate,
                        preserved_tokens=preserved_tokens,
                    )

    async def get_bucket_stats(self, key: str) -> dict[str, float] | None:
        """Get performance statistics for a specific key."""
        async with self._lock:
            if key not in self._performance_data:
                return None

            data = self._performance_data[key]
            total_requests = data["successes"] + data["failures"]

            if total_requests == 0:
                return {
                    "total_requests": 0,
                    "success_rate": 0.0,
                    "error_rate": 0.0,
                }

            return {
                "total_requests": total_requests,
                "success_rate": data["successes"] / total_requests,
                "error_rate": data["failures"] / total_requests,
                "successes": data["successes"],
                "failures": data["failures"],
            }

    async def get_current_limits(self, key: str) -> dict[str, float] | None:
        """Get current rate limit configuration for a key."""
        async with self._lock:
            if key not in self._bucket_configs:
                return None

            config = self._bucket_configs[key]
            bucket = self._buckets[key]
            available_tokens = await bucket.get_available_tokens()

            return {
                "capacity": config.capacity,
                "refill_rate": config.refill_rate,
                "available_tokens": available_tokens,
            }

    async def shutdown(self) -> None:
        """Clean shutdown of the adaptive limiter."""
        if self._adjustment_task and not self._adjustment_task.done():
            self._adjustment_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._adjustment_task

        logger.info("Adaptive rate limiter shut down")
