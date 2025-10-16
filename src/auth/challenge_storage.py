"""WebAuthn challenge storage implementations following SOLID principles.

Provides abstract interface and implementations for storing WebAuthn challenges:
- InMemoryChallengeStorage: For development and single-instance deployments
- RedisChallengeStorage: For production multi-instance deployments

Following SOLID principles:
- Single Responsibility: Only handles challenge persistence
- Open/Closed: Easy to add new storage backends
- Liskov Substitution: All implementations work identically
- Interface Segregation: Focused challenge storage interface
- Dependency Inversion: Service depends on abstraction
"""

import json
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from typing import Any

from src.caching.manager import cache_manager
from src.core.logging_hierarchy import get_auth_logger

logger = get_auth_logger()


class IChallengeStorage(ABC):
    """Abstract interface for WebAuthn challenge storage.

    Following Dependency Inversion Principle - services depend on this interface.
    """

    @abstractmethod
    async def store_challenge(
        self, challenge_key: str, challenge_data: dict[str, Any], ttl_seconds: int = 600
    ) -> None:
        """Store challenge data with expiration.

        Args:
            challenge_key: Unique key for the challenge
            challenge_data: Challenge metadata to store
            ttl_seconds: Time-to-live in seconds (default 10 minutes)
        """

    @abstractmethod
    async def get_challenge(self, challenge_key: str) -> dict[str, Any] | None:
        """Retrieve challenge data.

        Args:
            challenge_key: Unique key for the challenge

        Returns:
            Challenge data if found and not expired, None otherwise
        """

    @abstractmethod
    async def delete_challenge(self, challenge_key: str) -> bool:
        """Delete challenge data after use.

        Args:
            challenge_key: Unique key for the challenge

        Returns:
            True if challenge was deleted, False if not found
        """

    @abstractmethod
    async def cleanup_expired(self, max_age_minutes: int = 10) -> int:
        """Cleanup expired challenges (maintenance operation).

        Args:
            max_age_minutes: Maximum age in minutes before cleanup

        Returns:
            Number of expired challenges removed
        """


class InMemoryChallengeStorage(IChallengeStorage):
    """In-memory challenge storage for development and single-instance deployments.

    Following Single Responsibility Principle - only manages in-memory challenge storage.
    Perfect for development and single-instance production deployments.
    """

    def __init__(self) -> None:
        """Initialize in-memory storage."""
        self._challenges: dict[str, dict[str, Any]] = {}
        logger.info("InMemoryChallengeStorage initialized")

    async def store_challenge(
        self, challenge_key: str, challenge_data: dict[str, Any], ttl_seconds: int = 600
    ) -> None:
        """Store challenge in memory with expiration timestamp."""
        self._challenges[challenge_key] = {
            **challenge_data,
            "_stored_at": datetime.now(UTC),
            "_ttl_seconds": ttl_seconds,
        }
        logger.debug("Challenge stored in memory", challenge_key=challenge_key)

    async def get_challenge(self, challenge_key: str) -> dict[str, Any] | None:
        """Retrieve challenge from memory if not expired."""
        if challenge_key not in self._challenges:
            return None

        challenge_data = self._challenges[challenge_key]
        stored_at = challenge_data.get("_stored_at")
        ttl_seconds = challenge_data.get("_ttl_seconds", 600)

        # Check expiration
        if stored_at:
            age_seconds = (datetime.now(UTC) - stored_at).total_seconds()
            if age_seconds > ttl_seconds:
                # Challenge expired, delete it
                del self._challenges[challenge_key]
                logger.debug("Challenge expired and removed", challenge_key=challenge_key)
                return None

        # Remove internal metadata before returning
        result = {k: v for k, v in challenge_data.items() if not k.startswith("_")}
        return result

    async def delete_challenge(self, challenge_key: str) -> bool:
        """Delete challenge from memory."""
        if challenge_key in self._challenges:
            del self._challenges[challenge_key]
            logger.debug("Challenge deleted from memory", challenge_key=challenge_key)
            return True
        return False

    async def cleanup_expired(self, max_age_minutes: int = 10) -> int:
        """Cleanup expired challenges from memory."""
        current_time = datetime.now(UTC)
        expired_keys = []

        for key, data in self._challenges.items():
            stored_at = data.get("_stored_at")
            ttl_seconds = data.get("_ttl_seconds", 600)

            if stored_at:
                age_seconds = (current_time - stored_at).total_seconds()
                if age_seconds > ttl_seconds:
                    expired_keys.append(key)

        for key in expired_keys:
            del self._challenges[key]

        if expired_keys:
            logger.info("Cleaned up expired challenges", count=len(expired_keys))

        return len(expired_keys)


class RedisChallengeStorage(IChallengeStorage):
    """Redis-based challenge storage for production multi-instance deployments.

    Following Single Responsibility Principle - only manages Redis challenge storage.
    Enables horizontal scaling with multiple backend instances.
    """

    def __init__(self) -> None:
        """Initialize Redis storage connection."""
        self._redis_client = None
        self._initialized = False
        logger.info("RedisChallengeStorage initialized (lazy connection)")

    async def _ensure_redis(self) -> Any:
        """Lazy initialize Redis connection.

        Returns:
            Redis client instance

        Raises:
            RuntimeError: If Redis connection cannot be established
        """
        if not self._initialized or self._redis_client is None:
            try:
                # Get Redis client from cache manager (DRY - reuse existing connection)
                self._redis_client = await cache_manager._ensure_backend()._get_client()  # type: ignore[attr-defined]
                self._initialized = True
                logger.info("Redis connection established for challenge storage")
            except Exception as e:
                logger.error("Failed to connect to Redis for challenge storage", error=str(e))
                raise RuntimeError(
                    "Redis connection required for RedisChallengeStorage but unavailable"
                ) from e

        return self._redis_client

    async def store_challenge(
        self, challenge_key: str, challenge_data: dict[str, Any], ttl_seconds: int = 600
    ) -> None:
        """Store challenge in Redis with automatic expiration."""
        redis = await self._ensure_redis()

        # Serialize challenge data to JSON
        challenge_json = json.dumps(challenge_data)

        # Store in Redis with TTL (Redis handles expiration automatically)
        await redis.setex(f"webauthn:challenge:{challenge_key}", ttl_seconds, challenge_json)

        logger.debug(
            "Challenge stored in Redis",
            challenge_key=challenge_key,
            ttl_seconds=ttl_seconds,
        )

    async def get_challenge(self, challenge_key: str) -> dict[str, Any] | None:
        """Retrieve challenge from Redis."""
        redis = await self._ensure_redis()

        # Retrieve from Redis
        challenge_json = await redis.get(f"webauthn:challenge:{challenge_key}")

        if challenge_json is None:
            return None

        # Deserialize from JSON
        try:
            challenge_data: dict[str, Any] = json.loads(challenge_json)
            return challenge_data
        except json.JSONDecodeError as e:
            logger.error("Failed to decode challenge JSON from Redis", error=str(e))
            return None

    async def delete_challenge(self, challenge_key: str) -> bool:
        """Delete challenge from Redis."""
        redis = await self._ensure_redis()

        # Delete from Redis
        deleted_count = await redis.delete(f"webauthn:challenge:{challenge_key}")

        if deleted_count > 0:
            logger.debug("Challenge deleted from Redis", challenge_key=challenge_key)
            return True

        return False

    async def cleanup_expired(self, max_age_minutes: int = 10) -> int:
        """Cleanup expired challenges from Redis.

        Note: Redis automatically expires keys with TTL, so this is a no-op.
        Included for interface compatibility.

        Args:
            max_age_minutes: Not used (Redis handles expiration automatically)

        Returns:
            0 (Redis handles cleanup automatically)
        """
        logger.debug("Redis automatic expiration handles cleanup (no-op)")
        return 0


# Default storage instance (can be overridden for testing or configuration)
_default_storage: IChallengeStorage | None = None


def get_challenge_storage(use_redis: bool = False) -> IChallengeStorage:
    """Get challenge storage instance (singleton pattern).

    DRY: Single storage instance across the application.

    Args:
        use_redis: If True, use Redis storage; otherwise use in-memory storage

    Returns:
        IChallengeStorage instance
    """
    global _default_storage

    if _default_storage is None:
        if use_redis:
            _default_storage = RedisChallengeStorage()
            logger.info("Using RedisChallengeStorage for WebAuthn challenges")
        else:
            _default_storage = InMemoryChallengeStorage()
            logger.info("Using InMemoryChallengeStorage for WebAuthn challenges")

    return _default_storage


def set_challenge_storage(storage: IChallengeStorage) -> None:
    """Override default storage instance (for testing or custom configuration).

    Args:
        storage: Custom IChallengeStorage implementation
    """
    global _default_storage
    _default_storage = storage
    logger.info("Challenge storage overridden", storage_type=type(storage).__name__)
