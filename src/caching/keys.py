"""Centralized cache key generation for PERFECT DRY compliance.

ZERO TOLERANCE for duplicate cache key patterns.
Single source of truth for ALL cache keys across the entire system.
"""

import hashlib
from typing import Any
from urllib.parse import quote

from src.core.logging_hierarchy import get_cache_logger

logger = get_cache_logger()


# Cache namespace constants for perfect organization
class CacheNamespaces:
    """Perfect namespace organization - zero hardcoded keys."""

    # Core entities
    JOB = "job"
    USER = "user"
    SESSION = "session"
    AUTH = "auth"
    OAUTH = "oauth"

    # Features
    RATE_LIMIT = "rate_limit"
    HEALTH = "health"
    METRICS = "metrics"
    QUEUE = "queue"
    LOCK = "lock"

    # External APIs
    EXTERNAL_API = "ext_api"
    WEBHOOK = "webhook"

    # Temporary data
    TEMP = "temp"
    CHALLENGE = "challenge"


class CacheKeys:
    """Perfect cache key generation - zero duplication allowed."""

    # Key separator for consistent formatting
    SEPARATOR = ":"

    @classmethod
    def _build_key(cls, *parts: str) -> str:
        """Perfect key building - used internally everywhere."""
        # Filter out None/empty parts and sanitize
        clean_parts = []
        for part in parts:
            if part:
                # URL-encode to handle special characters safely
                clean_part = quote(str(part), safe="")
                clean_parts.append(clean_part)

        if not clean_parts:
            raise ValueError("Cannot build cache key from empty parts")

        return cls.SEPARATOR.join(clean_parts)

    @classmethod
    def _hash_long_key(cls, key: str, max_length: int = 250) -> str:
        """Perfect key hashing for long keys - prevents Redis key length issues."""
        if len(key) <= max_length:
            return key

        # Hash the key but keep prefix for debugging
        parts = key.split(cls.SEPARATOR)
        if len(parts) >= 2:
            prefix = f"{parts[0]}{cls.SEPARATOR}{parts[1]}"
            hash_suffix = hashlib.sha256(key.encode()).hexdigest()[:16]
            return f"{prefix}{cls.SEPARATOR}h_{hash_suffix}"
        else:
            # Full hash if we can't preserve meaningful prefix
            return f"hash_{hashlib.sha256(key.encode()).hexdigest()[:32]}"

    # User-related cache keys
    @classmethod
    def user(cls, user_id: str) -> str:
        """Perfect user cache key - used everywhere."""
        return cls._build_key(CacheNamespaces.USER, user_id)

    @classmethod
    def user_profile(cls, user_id: str) -> str:
        """Perfect user profile cache key - used everywhere."""
        return cls._build_key(CacheNamespaces.USER, "profile", user_id)

    @classmethod
    def user_settings(cls, user_id: str) -> str:
        """Perfect user settings cache key - used everywhere."""
        return cls._build_key(CacheNamespaces.USER, "settings", user_id)

    @classmethod
    def user_sessions(cls, user_id: str) -> str:
        """Perfect user sessions cache key - used everywhere."""
        return cls._build_key(CacheNamespaces.USER, "sessions", user_id)

    # Session-related cache keys
    @classmethod
    def session(cls, session_id: str) -> str:
        """Perfect session cache key - used everywhere."""
        return cls._build_key(CacheNamespaces.SESSION, session_id)

    @classmethod
    def user_session(cls, user_id: str, session_id: str) -> str:
        """Perfect user session cache key - used everywhere."""
        return cls._build_key(CacheNamespaces.SESSION, user_id, session_id)

    @classmethod
    def session_data(cls, session_id: str, data_type: str) -> str:
        """Perfect session data cache key - used everywhere."""
        return cls._build_key(CacheNamespaces.SESSION, session_id, data_type)

    # Job-related cache keys
    @classmethod
    def job(cls, job_id: str) -> str:
        """Perfect job cache key - used everywhere."""
        return cls._build_key(CacheNamespaces.JOB, job_id)

    @classmethod
    def job_status(cls, job_id: str) -> str:
        """Perfect job status cache key - used everywhere."""
        return cls._build_key(CacheNamespaces.JOB, "status", job_id)

    @classmethod
    def job_result(cls, job_id: str) -> str:
        """Perfect job result cache key - used everywhere."""
        return cls._build_key(CacheNamespaces.JOB, "result", job_id)

    @classmethod
    def job_metadata(cls, job_id: str) -> str:
        """Perfect job metadata cache key - used everywhere."""
        return cls._build_key(CacheNamespaces.JOB, "metadata", job_id)

    @classmethod
    def user_jobs(cls, user_id: str, status: str | None = None) -> str:
        """Perfect user jobs cache key - used everywhere."""
        if status:
            return cls._build_key(CacheNamespaces.JOB, "user", user_id, status)
        return cls._build_key(CacheNamespaces.JOB, "user", user_id)

    @classmethod
    def job_queue(cls, priority: str) -> str:
        """Perfect job queue cache key - used everywhere."""
        return cls._build_key(CacheNamespaces.QUEUE, "jobs", priority)

    # Rate limiting cache keys
    @classmethod
    def rate_limit(cls, user_id: str, endpoint: str) -> str:
        """Perfect rate limit cache key - used everywhere."""
        return cls._build_key(CacheNamespaces.RATE_LIMIT, user_id, endpoint)

    @classmethod
    def rate_limit_global(cls, endpoint: str) -> str:
        """Perfect global rate limit cache key - used everywhere."""
        return cls._build_key(CacheNamespaces.RATE_LIMIT, "global", endpoint)

    @classmethod
    def rate_limit_ip(cls, ip_address: str, endpoint: str) -> str:
        """Perfect IP rate limit cache key - used everywhere."""
        return cls._build_key(CacheNamespaces.RATE_LIMIT, "ip", ip_address, endpoint)

    # Authentication cache keys
    @classmethod
    def auth_token(cls, token_id: str) -> str:
        """Perfect auth token cache key - used everywhere."""
        return cls._build_key(CacheNamespaces.AUTH, "token", token_id)

    @classmethod
    def revoked_token(cls, jti: str) -> str:
        """Perfect revoked token cache key - used everywhere."""
        return cls._build_key(CacheNamespaces.AUTH, "revoked", jti)

    @classmethod
    def user_tokens(cls, user_id: str) -> str:
        """Perfect user tokens cache key - used everywhere."""
        return cls._build_key(CacheNamespaces.AUTH, "user_tokens", user_id)

    @classmethod
    def failed_login_attempts(cls, identifier: str) -> str:
        """Perfect failed login cache key - used everywhere."""
        return cls._build_key(CacheNamespaces.AUTH, "failed_attempts", identifier)

    # OAuth cache keys
    @classmethod
    def oauth_state(cls, state: str) -> str:
        """Perfect OAuth state cache key - used everywhere."""
        return cls._build_key(CacheNamespaces.OAUTH, "state", state)

    @classmethod
    def oauth_user_info(cls, provider: str, provider_user_id: str) -> str:
        """Perfect OAuth user info cache key - used everywhere."""
        return cls._build_key(CacheNamespaces.OAUTH, "user_info", provider, provider_user_id)

    @classmethod
    def oauth_provider_tokens(cls, user_id: str, provider: str) -> str:
        """Perfect OAuth provider tokens cache key - used everywhere."""
        return cls._build_key(CacheNamespaces.OAUTH, "tokens", user_id, provider)

    @classmethod
    def oauth_callback_data(cls, state: str) -> str:
        """Perfect OAuth callback cache key - used everywhere."""
        return cls._build_key(CacheNamespaces.OAUTH, "callback", state)

    # WebAuthn/Passkey cache keys
    @classmethod
    def webauthn_challenge(cls, challenge_key: str) -> str:
        """Perfect WebAuthn challenge cache key - used everywhere."""
        return cls._build_key(CacheNamespaces.CHALLENGE, "webauthn", challenge_key)

    @classmethod
    def webauthn_registration(cls, user_id: str, challenge_key: str) -> str:
        """Perfect WebAuthn registration cache key - used everywhere."""
        return cls._build_key(CacheNamespaces.CHALLENGE, "webauthn", "reg", user_id, challenge_key)

    @classmethod
    def webauthn_authentication(cls, challenge_key: str) -> str:
        """Perfect WebAuthn authentication cache key - used everywhere."""
        return cls._build_key(CacheNamespaces.CHALLENGE, "webauthn", "auth", challenge_key)

    @classmethod
    def user_credentials(cls, user_id: str) -> str:
        """Perfect user credentials cache key - used everywhere."""
        return cls._build_key(CacheNamespaces.USER, "credentials", user_id)

    # Health and monitoring cache keys
    @classmethod
    def health_status(cls, component: str) -> str:
        """Perfect health status cache key - used everywhere."""
        return cls._build_key(CacheNamespaces.HEALTH, component)

    @classmethod
    def system_health(cls) -> str:
        """Perfect system health cache key - used everywhere."""
        return cls._build_key(CacheNamespaces.HEALTH, "system")

    @classmethod
    def component_metrics(cls, component: str, metric_type: str) -> str:
        """Perfect component metrics cache key - used everywhere."""
        return cls._build_key(CacheNamespaces.METRICS, component, metric_type)

    @classmethod
    def performance_metrics(cls, operation: str, time_window: str) -> str:
        """Perfect performance metrics cache key - used everywhere."""
        return cls._build_key(CacheNamespaces.METRICS, "performance", operation, time_window)

    # External API cache keys
    @classmethod
    def external_api_response(cls, api_name: str, endpoint: str, params_hash: str) -> str:
        """Perfect external API cache key - used everywhere."""
        key = cls._build_key(CacheNamespaces.EXTERNAL_API, api_name, endpoint, params_hash)
        return cls._hash_long_key(key)  # API keys can be long

    @classmethod
    def api_rate_limit(cls, api_name: str) -> str:
        """Perfect API rate limit cache key - used everywhere."""
        return cls._build_key(CacheNamespaces.EXTERNAL_API, "rate_limit", api_name)

    @classmethod
    def webhook_delivery(cls, webhook_id: str, attempt: int) -> str:
        """Perfect webhook delivery cache key - used everywhere."""
        return cls._build_key(CacheNamespaces.WEBHOOK, "delivery", webhook_id, str(attempt))

    # Locking cache keys
    @classmethod
    def operation_lock(cls, operation: str, resource_id: str) -> str:
        """Perfect operation lock cache key - used everywhere."""
        return cls._build_key(CacheNamespaces.LOCK, operation, resource_id)

    @classmethod
    def user_operation_lock(cls, user_id: str, operation: str) -> str:
        """Perfect user operation lock cache key - used everywhere."""
        return cls._build_key(CacheNamespaces.LOCK, "user", user_id, operation)

    @classmethod
    def global_operation_lock(cls, operation: str) -> str:
        """Perfect global operation lock cache key - used everywhere."""
        return cls._build_key(CacheNamespaces.LOCK, "global", operation)

    # Temporary data cache keys
    @classmethod
    def temp_data(cls, data_type: str, identifier: str) -> str:
        """Perfect temporary data cache key - used everywhere."""
        return cls._build_key(CacheNamespaces.TEMP, data_type, identifier)

    @classmethod
    def temp_upload(cls, upload_id: str) -> str:
        """Perfect temporary upload cache key - used everywhere."""
        return cls._build_key(CacheNamespaces.TEMP, "upload", upload_id)

    @classmethod
    def temp_export(cls, export_id: str) -> str:
        """Perfect temporary export cache key - used everywhere."""
        return cls._build_key(CacheNamespaces.TEMP, "export", export_id)


class CacheKeyBuilder:
    """Perfect dynamic cache key builder for complex scenarios."""

    @staticmethod
    def build_query_key(operation: str, filters: dict[str, Any]) -> str:
        """Perfect query cache key builder - used everywhere."""
        # Sort filters for consistent keys
        sorted_filters = sorted(filters.items())

        # Build filter string
        filter_parts = []
        for key, value in sorted_filters:
            if value is not None:
                if isinstance(value, (list, tuple)):
                    # Sort lists for consistency
                    sorted_value = sorted(str(v) for v in value)
                    filter_parts.append(f"{key}={','.join(sorted_value)}")
                else:
                    filter_parts.append(f"{key}={value}")

        filter_string = "&".join(filter_parts)

        # Hash if too long
        if len(filter_string) > 100:
            filter_hash = hashlib.sha256(filter_string.encode()).hexdigest()[:16]
            return CacheKeys._build_key("query", operation, f"h_{filter_hash}")

        return CacheKeys._build_key("query", operation, filter_string)

    @staticmethod
    def build_aggregation_key(
        entity: str, aggregation_type: str, time_window: str, filters: dict[str, Any] | None = None
    ) -> str:
        """Perfect aggregation cache key builder - used everywhere."""
        parts = ["agg", entity, aggregation_type, time_window]

        if filters:
            filter_hash = hashlib.sha256(str(sorted(filters.items())).encode()).hexdigest()[:16]
            parts.append(f"f_{filter_hash}")

        return CacheKeys._build_key(*parts)

    @staticmethod
    def build_list_key(
        entity: str,
        page: int,
        limit: int,
        sort_by: str | None = None,
        filters: dict[str, Any] | None = None,
    ) -> str:
        """Perfect list cache key builder - used everywhere."""
        parts = ["list", entity, f"p{page}", f"l{limit}"]

        if sort_by:
            parts.append(f"s_{sort_by}")

        if filters:
            filter_hash = hashlib.sha256(str(sorted(filters.items())).encode()).hexdigest()[:16]
            parts.append(f"f_{filter_hash}")

        return CacheKeys._build_key(*parts)


# Convenience aliases for perfect DRY usage
build_user_key = CacheKeys.user
build_job_key = CacheKeys.job
build_session_key = CacheKeys.session
build_rate_limit_key = CacheKeys.rate_limit
build_oauth_key = CacheKeys.oauth_state
build_health_key = CacheKeys.health_status
build_lock_key = CacheKeys.operation_lock
build_temp_key = CacheKeys.temp_data
build_query_key = CacheKeyBuilder.build_query_key
build_list_key = CacheKeyBuilder.build_list_key
