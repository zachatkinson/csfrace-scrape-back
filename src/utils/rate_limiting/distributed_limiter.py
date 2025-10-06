"""Distributed token bucket implementation using Redis for multi-instance rate limiting.

Provides consistent rate limiting across multiple application instances
using Redis as a shared state store.
"""

import time
from typing import TYPE_CHECKING, Optional

import asyncio

from src.core.decorators import cache_error_handler, monitoring_error_handler
from src.core.logging_hierarchy import get_core_logger

from .token_bucket import TokenBucketConfig

if TYPE_CHECKING:
    import redis.asyncio as redis

logger = get_core_logger()

try:
    REDIS_AVAILABLE = True
except ImportError:
    logger.warning("Redis not available - distributed rate limiting disabled")
    REDIS_AVAILABLE = False


class DistributedTokenBucket:
    """Redis-backed token bucket for distributed rate limiting.

    Uses Redis for shared state across multiple application instances.
    Falls back to local token bucket if Redis is unavailable.

    Example:
        # With Redis connection
        redis_client = redis.Redis(host='localhost', port=6379)
        bucket = DistributedTokenBucket(
            config=TokenBucketConfig(capacity=100, refill_rate=10.0),
            redis_client=redis_client,
            key_prefix="rate_limit:"
        )

        if await bucket.consume("user123"):
            process_request()
        else:
            return_rate_limit_error()
    """

    def __init__(
        self,
        config: TokenBucketConfig,
        redis_client: Optional["redis.Redis"] = None,
        key_prefix: str = "rate_limit:",
        fallback_to_local: bool = True,
    ) -> None:
        """Initialize distributed token bucket.

        Args:
            config: Token bucket configuration
            redis_client: Redis client instance (optional)
            key_prefix: Prefix for Redis keys
            fallback_to_local: Whether to fall back to local bucket if Redis fails
        """
        self.config = config
        self.redis_client = redis_client if REDIS_AVAILABLE else None
        self.key_prefix = key_prefix
        self.fallback_to_local = fallback_to_local

        # Local fallback bucket
        from .token_bucket import TokenBucket

        if fallback_to_local:
            self._local_bucket: TokenBucket | None = TokenBucket(config)
        else:
            self._local_bucket = None

        # Lua script for atomic token consumption
        self._consume_script = """
        local key = KEYS[1]
        local capacity = tonumber(ARGV[1])
        local refill_rate = tonumber(ARGV[2])
        local tokens_requested = tonumber(ARGV[3])
        local now = tonumber(ARGV[4])

        -- Get current state
        local state = redis.call('HMGET', key, 'tokens', 'last_refill')
        local current_tokens = tonumber(state[1]) or capacity
        local last_refill = tonumber(state[2]) or now

        -- Calculate refill
        local elapsed = now - last_refill
        if elapsed > 0 then
            local tokens_to_add = elapsed * refill_rate
            current_tokens = math.min(capacity, current_tokens + tokens_to_add)
        end

        -- Check if we can consume
        if current_tokens >= tokens_requested then
            current_tokens = current_tokens - tokens_requested

            -- Update state with TTL
            redis.call('HMSET', key, 'tokens', current_tokens, 'last_refill', now)
            redis.call('EXPIRE', key, 3600)  -- 1 hour TTL

            return {1, current_tokens}  -- Success
        else
            -- Update state even if we can't consume (for accurate refill)
            redis.call('HMSET', key, 'tokens', current_tokens, 'last_refill', now)
            redis.call('EXPIRE', key, 3600)

            return {0, current_tokens}  -- Failure
        end
        """

        logger.debug(
            "Distributed token bucket initialized",
            redis_available=self.redis_client is not None,
            fallback_enabled=fallback_to_local,
            capacity=config.capacity,
        )

    async def consume(self, key: str, tokens: int = 1) -> bool:
        """Attempt to consume tokens from the distributed bucket.

        Args:
            key: Unique identifier for the bucket
            tokens: Number of tokens to consume

        Returns:
            True if tokens were consumed, False if rate limited
        """
        if tokens <= 0:
            raise ValueError("Token count must be positive")
        if tokens > self.config.capacity:
            return False

        # Try Redis first
        if self.redis_client is not None:
            return await self._consume_redis_with_fallback(key, tokens)

        # Fall back to local bucket
        if self._local_bucket:
            return await self._local_bucket.consume(tokens)

        # No Redis and no fallback - deny request
        logger.error("No rate limiting available - denying request", key=key)
        return False

    async def _consume_redis(self, key: str, tokens: int) -> bool:
        """Consume tokens using Redis atomic script."""
        if self.redis_client is None:
            raise RuntimeError("Redis client not available")

        redis_key = f"{self.key_prefix}{key}"
        now = time.time()

        result = await self.redis_client.eval(  # type: ignore[misc]
            self._consume_script,
            1,  # Number of keys
            redis_key,
            str(self.config.capacity),
            str(self.config.refill_rate),
            str(tokens),
            str(now),
        )

        success = bool(result[0])
        remaining_tokens = result[1]

        logger.debug(
            "Redis token consumption",
            key=key,
            success=success,
            tokens_requested=tokens,
            remaining_tokens=remaining_tokens,
        )

        return success

    @cache_error_handler("consume Redis tokens with fallback")
    async def _consume_redis_with_fallback(self, key: str, tokens: int) -> bool:
        """Consume tokens from Redis with fallback handling."""
        result = await self._consume_redis(key, tokens)
        logger.warning(
            "Redis consume failed, falling back to local",
            key=key,
        )
        if not self.fallback_to_local:
            raise
        return result

    async def get_available_tokens(self, key: str) -> float:
        """Get current number of available tokens."""
        if self.redis_client is not None:
            return await self._get_available_redis_with_fallback(key)

        if self._local_bucket:
            return await self._local_bucket.get_available_tokens()

        return 0.0

    async def _get_available_redis(self, key: str) -> float:
        """Get available tokens from Redis."""
        if self.redis_client is None:
            raise RuntimeError("Redis client not available")

        redis_key = f"{self.key_prefix}{key}"
        now = time.time()

        # Use a simpler Lua script for just getting tokens
        get_script = """
        local key = KEYS[1]
        local capacity = tonumber(ARGV[1])
        local refill_rate = tonumber(ARGV[2])
        local now = tonumber(ARGV[3])

        local state = redis.call('HMGET', key, 'tokens', 'last_refill')
        local current_tokens = tonumber(state[1]) or capacity
        local last_refill = tonumber(state[2]) or now

        local elapsed = now - last_refill
        if elapsed > 0 then
            local tokens_to_add = elapsed * refill_rate
            current_tokens = math.min(capacity, current_tokens + tokens_to_add)

            -- Update state
            redis.call('HMSET', key, 'tokens', current_tokens, 'last_refill', now)
            redis.call('EXPIRE', key, 3600)
        end

        return current_tokens
        """

        result = await self.redis_client.eval(  # type: ignore[misc]
            get_script,
            1,
            redis_key,
            str(self.config.capacity),
            str(self.config.refill_rate),
            str(now),
        )

        return float(result)

    @cache_error_handler("get available Redis tokens with fallback")
    async def _get_available_redis_with_fallback(self, key: str) -> float:
        """Get available tokens from Redis with fallback handling."""
        result = await self._get_available_redis(key)
        logger.warning(
            "Redis get_available failed, falling back to local",
            key=key,
        )
        if not self.fallback_to_local:
            raise
        return result

    async def reset(self, key: str) -> None:
        """Reset bucket to initial state."""
        if self.redis_client:
            return await self._reset_redis_with_fallback(key)

        if self._local_bucket:
            await self._local_bucket.reset()

    @cache_error_handler("reset Redis bucket with fallback")
    async def _reset_redis_with_fallback(self, key: str) -> None:
        """Reset Redis bucket with fallback handling."""
        if self.redis_client is None:
            return
        redis_key = f"{self.key_prefix}{key}"
        await self.redis_client.delete(redis_key)
        logger.debug("Reset Redis bucket", key=key)
        return

    @monitoring_error_handler("check Redis health")
    async def _check_redis_health(self, health: dict[str, str | bool | int]) -> None:
        """Check Redis health with error handling."""
        if self.redis_client is None:
            health["redis_available"] = False
            return
        await self.redis_client.ping()
        health["redis_available"] = True

    async def health_check(self) -> dict[str, str | bool | int]:
        """Check health of distributed rate limiting components."""
        health: dict[str, str | bool | int] = {
            "redis_available": False,
            "local_fallback_available": self._local_bucket is not None,
        }

        if self.redis_client:
            await self._check_redis_health(health)

        return health


class DistributedTokenBucketPool:
    """Pool of distributed token buckets for different contexts.

    Similar to TokenBucketPool but uses Redis for distributed state.
    """

    def __init__(
        self,
        default_config: TokenBucketConfig,
        redis_client: Optional["redis.Redis"] = None,
        key_prefix: str = "rate_limit_pool:",
        fallback_to_local: bool = True,
    ) -> None:
        """Initialize distributed bucket pool."""
        self.default_config = default_config
        self.redis_client = redis_client
        self.key_prefix = key_prefix
        self.fallback_to_local = fallback_to_local

        # Cache buckets locally to avoid recreating
        self._bucket_cache: dict[str, DistributedTokenBucket] = {}
        self._lock = asyncio.Lock()

        logger.debug(
            "Distributed token bucket pool initialized",
            redis_available=redis_client is not None,
            fallback_enabled=fallback_to_local,
        )

    async def get_bucket(self, key: str) -> DistributedTokenBucket:
        """Get or create a distributed token bucket for the given key."""
        async with self._lock:
            if key not in self._bucket_cache:
                bucket_key_prefix = f"{self.key_prefix}{key}:"
                self._bucket_cache[key] = DistributedTokenBucket(
                    config=self.default_config,
                    redis_client=self.redis_client,
                    key_prefix=bucket_key_prefix,
                    fallback_to_local=self.fallback_to_local,
                )

                logger.debug("Created distributed bucket", key=key)

            return self._bucket_cache[key]

    async def consume(self, key: str, tokens: int = 1) -> bool:
        """Consume tokens from the bucket identified by key."""
        bucket = await self.get_bucket(key)
        return await bucket.consume("default", tokens)

    async def get_available_tokens(self, key: str) -> float:
        """Get available tokens for the bucket identified by key."""
        bucket = await self.get_bucket(key)
        return await bucket.get_available_tokens("default")

    async def reset_bucket(self, key: str) -> None:
        """Reset a specific bucket."""
        bucket = await self.get_bucket(key)
        await bucket.reset("default")

    async def health_check(self) -> dict[str, str | bool | int]:
        """Check health of all distributed components."""
        if not self._bucket_cache:
            # Create a test bucket to check health
            test_bucket = DistributedTokenBucket(
                config=self.default_config,
                redis_client=self.redis_client,
                key_prefix=f"{self.key_prefix}health_check:",
                fallback_to_local=self.fallback_to_local,
            )
            health = await test_bucket.health_check()
        else:
            # Use an existing bucket
            bucket = next(iter(self._bucket_cache.values()))
            health = await bucket.health_check()

        health["cached_buckets"] = len(self._bucket_cache)
        return health
