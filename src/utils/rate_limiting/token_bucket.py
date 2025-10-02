"""Token bucket algorithm implementation for advanced rate limiting.

Provides burst handling and smooth rate limiting with better user experience
compared to simple window-based rate limiting.
"""

import time
from dataclasses import dataclass

import asyncio

from src.core.logging_hierarchy import get_core_logger

logger = get_core_logger()


@dataclass
class TokenBucketConfig:
    """Configuration for token bucket rate limiter."""

    capacity: int  # Maximum number of tokens in bucket
    refill_rate: float  # Tokens added per second
    initial_tokens: int | None = None  # Initial tokens (defaults to capacity)

    def __post_init__(self) -> None:
        """Validate configuration after initialization."""
        if self.capacity <= 0:
            raise ValueError("Capacity must be positive")
        if self.refill_rate <= 0:
            raise ValueError("Refill rate must be positive")
        if self.initial_tokens is None:
            self.initial_tokens = self.capacity
        if self.initial_tokens < 0 or self.initial_tokens > self.capacity:
            raise ValueError("Initial tokens must be between 0 and capacity")


class TokenBucket:
    """Thread-safe token bucket implementation for rate limiting.

    The token bucket algorithm allows for burst traffic while maintaining
    an average rate over time. This provides a better user experience
    compared to strict window-based rate limiting.

    Example:
        # Allow 10 requests per second with burst of 20
        bucket = TokenBucket(TokenBucketConfig(capacity=20, refill_rate=10.0))

        if await bucket.consume(1):
            # Request allowed
            process_request()
        else:
            # Rate limited
            return_rate_limit_error()
    """

    def __init__(self, config: TokenBucketConfig) -> None:
        """Initialize token bucket with configuration."""
        self.config = config
        self._tokens = float(
            config.initial_tokens if config.initial_tokens is not None else config.capacity
        )
        self._last_refill = time.monotonic()
        self._lock = asyncio.Lock()

        logger.debug(
            "Token bucket initialized",
            capacity=config.capacity,
            refill_rate=config.refill_rate,
            initial_tokens=config.initial_tokens,
        )

    async def consume(self, tokens: int = 1) -> bool:
        """Attempt to consume tokens from the bucket.

        Args:
            tokens: Number of tokens to consume

        Returns:
            True if tokens were consumed, False if rate limited
        """
        if tokens <= 0:
            raise ValueError("Token count must be positive")
        if tokens > self.config.capacity:
            # Request exceeds bucket capacity - always deny
            logger.warning(
                "Token request exceeds bucket capacity",
                requested=tokens,
                capacity=self.config.capacity,
            )
            return False

        async with self._lock:
            await self._refill()

            if self._tokens >= tokens:
                self._tokens -= tokens
                logger.debug(
                    "Tokens consumed",
                    consumed=tokens,
                    remaining=self._tokens,
                )
                return True
            else:
                logger.debug(
                    "Rate limited - insufficient tokens",
                    requested=tokens,
                    available=self._tokens,
                )
                return False

    async def _refill(self) -> None:
        """Refill bucket based on elapsed time."""
        now = time.monotonic()
        elapsed = now - self._last_refill

        if elapsed > 0:
            tokens_to_add = elapsed * self.config.refill_rate
            self._tokens = min(self.config.capacity, self._tokens + tokens_to_add)
            self._last_refill = now

            logger.debug(
                "Bucket refilled",
                elapsed=elapsed,
                tokens_added=tokens_to_add,
                current_tokens=self._tokens,
            )

    async def get_available_tokens(self) -> float:
        """Get current number of available tokens."""
        async with self._lock:
            await self._refill()
            return self._tokens

    async def get_wait_time(self, tokens: int = 1) -> float:
        """Get time to wait until enough tokens are available.

        Args:
            tokens: Number of tokens needed

        Returns:
            Seconds to wait, or 0 if tokens are immediately available
        """
        if tokens > self.config.capacity:
            # Request exceeds capacity - would never be fulfilled
            return float("inf")

        async with self._lock:
            await self._refill()

            if self._tokens >= tokens:
                return 0.0

            tokens_needed = tokens - self._tokens
            wait_time = tokens_needed / self.config.refill_rate

            logger.debug(
                "Calculated wait time",
                tokens_needed=tokens_needed,
                wait_time=wait_time,
            )

            return wait_time

    async def reset(self) -> None:
        """Reset bucket to initial state."""
        async with self._lock:
            self._tokens = float(self.config.initial_tokens or self.config.capacity)
            self._last_refill = time.monotonic()

            logger.debug("Token bucket reset")


class TokenBucketPool:
    """Pool of token buckets for different rate limiting contexts.

    Manages multiple token buckets identified by keys (e.g., user IDs, IP addresses).
    Automatically creates buckets on demand and provides cleanup for unused buckets.
    """

    def __init__(self, default_config: TokenBucketConfig, max_buckets: int = 10000) -> None:
        """Initialize bucket pool.

        Args:
            default_config: Default configuration for new buckets
            max_buckets: Maximum number of buckets to maintain
        """
        self.default_config = default_config
        self.max_buckets = max_buckets
        self._buckets: dict[str, TokenBucket] = {}
        self._access_times: dict[str, float] = {}
        self._lock = asyncio.Lock()

        logger.debug(
            "Token bucket pool initialized",
            max_buckets=max_buckets,
            default_capacity=default_config.capacity,
        )

    async def get_bucket(self, key: str) -> TokenBucket:
        """Get or create a token bucket for the given key."""
        async with self._lock:
            now = time.monotonic()
            self._access_times[key] = now

            if key not in self._buckets:
                # Create new bucket
                self._buckets[key] = TokenBucket(self.default_config)
                logger.debug("Created new token bucket", key=key)

                # Cleanup old buckets if needed
                if len(self._buckets) > self.max_buckets:
                    await self._cleanup_old_buckets()

            return self._buckets[key]

    async def consume(self, key: str, tokens: int = 1) -> bool:
        """Consume tokens from the bucket identified by key."""
        bucket = await self.get_bucket(key)
        return await bucket.consume(tokens)

    async def get_wait_time(self, key: str, tokens: int = 1) -> float:
        """Get wait time for the bucket identified by key."""
        bucket = await self.get_bucket(key)
        return await bucket.get_wait_time(tokens)

    async def _cleanup_old_buckets(self) -> None:
        """Remove least recently used buckets when pool is full."""
        if len(self._buckets) <= self.max_buckets:
            return

        # Sort by access time and remove oldest 25%
        sorted_keys = sorted(self._access_times.keys(), key=lambda k: self._access_times[k])

        cleanup_count = len(self._buckets) // 4  # Remove 25%
        for key in sorted_keys[:cleanup_count]:
            self._buckets.pop(key, None)
            self._access_times.pop(key, None)

        logger.debug(
            "Cleaned up token buckets",
            removed_count=cleanup_count,
            remaining_count=len(self._buckets),
        )

    async def reset_bucket(self, key: str) -> None:
        """Reset a specific bucket."""
        async with self._lock:
            if key in self._buckets:
                await self._buckets[key].reset()

    async def get_bucket_count(self) -> int:
        """Get current number of buckets in pool."""
        return len(self._buckets)
