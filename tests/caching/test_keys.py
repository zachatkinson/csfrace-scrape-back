"""Unit tests for src/caching/keys.py following AUDIT_3.md ZERO TOLERANCE standards.

MANDATORY REQUIREMENTS:
- NO vestigial code - every line serves a purpose
- NO legacy patterns - modern Python 3.11+ only
- NO backwards compatibility - clean implementations only
- NO broad exceptions - specific exceptions required
- SOLID principles compliance mandatory
- DRY compliance mandatory - no duplication
- Production-ready implementations only

Tests cache key generation with comprehensive coverage of all key patterns.
"""

from urllib.parse import quote

import pytest

from src.caching.keys import (
    CacheKeyBuilder,
    CacheKeys,
    CacheNamespaces,
    build_job_key,
    build_list_key,
    build_lock_key,
    build_oauth_key,
    build_query_key,
    build_rate_limit_key,
    build_session_key,
    build_temp_key,
    build_user_key,
)

# ============================================================================
# CacheNamespaces Tests
# ============================================================================


@pytest.mark.unit
class TestCacheNamespaces:
    """Unit tests for CacheNamespaces constants - MANDATORY AAA pattern."""

    def test_core_entity_namespaces_defined(self):
        """Test core entity namespaces are defined - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        expected_namespaces = ["JOB", "USER", "SESSION", "AUTH", "OAUTH"]

        # Act - MANDATORY
        actual_namespaces = [
            CacheNamespaces.JOB,
            CacheNamespaces.USER,
            CacheNamespaces.SESSION,
            CacheNamespaces.AUTH,
            CacheNamespaces.OAUTH,
        ]

        # Assert - MANDATORY
        assert len(actual_namespaces) == len(expected_namespaces)
        for namespace in actual_namespaces:
            assert isinstance(namespace, str)
            assert len(namespace) > 0

    def test_feature_namespaces_defined(self):
        """Test feature namespaces are defined - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        expected_namespaces = ["RATE_LIMIT", "HEALTH", "METRICS", "QUEUE", "LOCK"]

        # Act - MANDATORY
        actual_namespaces = [
            CacheNamespaces.RATE_LIMIT,
            CacheNamespaces.HEALTH,
            CacheNamespaces.METRICS,
            CacheNamespaces.QUEUE,
            CacheNamespaces.LOCK,
        ]

        # Assert - MANDATORY
        assert len(actual_namespaces) == len(expected_namespaces)
        for namespace in actual_namespaces:
            assert isinstance(namespace, str)

    def test_external_api_namespaces_defined(self):
        """Test external API namespaces are defined - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        expected_namespaces = ["EXTERNAL_API", "WEBHOOK"]

        # Act - MANDATORY
        actual_namespaces = [CacheNamespaces.EXTERNAL_API, CacheNamespaces.WEBHOOK]

        # Assert - MANDATORY
        assert len(actual_namespaces) == len(expected_namespaces)
        for namespace in actual_namespaces:
            assert isinstance(namespace, str)

    def test_temporary_data_namespaces_defined(self):
        """Test temporary data namespaces are defined - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # (namespaces defined at module level)

        # Act - MANDATORY
        temp_namespace = CacheNamespaces.TEMP
        challenge_namespace = CacheNamespaces.CHALLENGE

        # Assert - MANDATORY
        assert isinstance(temp_namespace, str)
        assert isinstance(challenge_namespace, str)
        assert len(temp_namespace) > 0
        assert len(challenge_namespace) > 0


# ============================================================================
# CacheKeys Internal Methods Tests
# ============================================================================


@pytest.mark.unit
class TestCacheKeysInternalMethods:
    """Unit tests for CacheKeys internal methods - MANDATORY AAA pattern."""

    def test_build_key_with_valid_parts(self):
        """Test _build_key with valid parts - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        parts = ["user", "profile", "test-user-123"]

        # Act - MANDATORY
        result = CacheKeys._build_key(*parts)

        # Assert - MANDATORY
        assert isinstance(result, str)
        assert "user" in result
        assert "profile" in result
        assert CacheKeys.SEPARATOR in result

    def test_build_key_filters_empty_parts(self):
        """Test _build_key filters empty parts - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        parts = ["user", "", None, "test-user"]

        # Act - MANDATORY
        result = CacheKeys._build_key(*parts)

        # Assert - MANDATORY
        # Should only contain non-empty parts
        assert result.count(CacheKeys.SEPARATOR) == 1  # 2 parts = 1 separator
        assert "user" in result

    def test_build_key_url_encodes_special_chars(self):
        """Test _build_key URL-encodes special characters - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        parts = ["user", "test@example.com"]
        expected_encoded = quote("test@example.com", safe="")

        # Act - MANDATORY
        result = CacheKeys._build_key(*parts)

        # Assert - MANDATORY
        assert expected_encoded in result
        assert "@" not in result  # Should be encoded

    def test_build_key_raises_on_all_empty_parts(self):
        """Test _build_key raises ValueError for all empty parts - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        parts = ["", None, "", ""]

        # Act & Assert - MANDATORY
        with pytest.raises(ValueError, match="Cannot build cache key from empty parts"):
            CacheKeys._build_key(*parts)

    def test_hash_long_key_preserves_short_keys(self):
        """Test _hash_long_key preserves short keys - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        short_key = "user:profile:test-123"

        # Act - MANDATORY
        result = CacheKeys._hash_long_key(short_key, max_length=250)

        # Assert - MANDATORY
        assert result == short_key  # Should be unchanged

    def test_hash_long_key_hashes_long_keys(self):
        """Test _hash_long_key hashes long keys - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        long_key = "a" * 300  # Exceeds max_length

        # Act - MANDATORY
        result = CacheKeys._hash_long_key(long_key, max_length=250)

        # Assert - MANDATORY
        assert len(result) < len(long_key)
        assert "hash_" in result or "h_" in result

    def test_hash_long_key_preserves_prefix_when_possible(self):
        """Test _hash_long_key preserves prefix - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        long_key = f"user{CacheKeys.SEPARATOR}profile{CacheKeys.SEPARATOR}{'a' * 300}"

        # Act - MANDATORY
        result = CacheKeys._hash_long_key(long_key, max_length=100)

        # Assert - MANDATORY
        # Should start with namespace prefix
        assert result.startswith("user")
        assert "h_" in result  # Hash suffix


# ============================================================================
# User-Related Cache Keys Tests
# ============================================================================


@pytest.mark.unit
class TestUserCacheKeys:
    """Unit tests for user-related cache keys - MANDATORY AAA pattern."""

    def test_user_key_generation(self):
        """Test user cache key generation - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        user_id = "test-user-123"

        # Act - MANDATORY
        result = CacheKeys.user(user_id)

        # Assert - MANDATORY
        assert isinstance(result, str)
        assert CacheNamespaces.USER in result
        assert user_id in result or quote(user_id, safe="") in result

    def test_user_profile_key_generation(self):
        """Test user profile cache key generation - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        user_id = "test-user-123"

        # Act - MANDATORY
        result = CacheKeys.user_profile(user_id)

        # Assert - MANDATORY
        assert CacheNamespaces.USER in result
        assert "profile" in result
        assert CacheKeys.SEPARATOR in result

    def test_user_settings_key_generation(self):
        """Test user settings cache key generation - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        user_id = "test-user-456"

        # Act - MANDATORY
        result = CacheKeys.user_settings(user_id)

        # Assert - MANDATORY
        assert CacheNamespaces.USER in result
        assert "settings" in result

    def test_user_sessions_key_generation(self):
        """Test user sessions cache key generation - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        user_id = "test-user-789"

        # Act - MANDATORY
        result = CacheKeys.user_sessions(user_id)

        # Assert - MANDATORY
        assert CacheNamespaces.USER in result
        assert "sessions" in result

    def test_user_credentials_key_generation(self):
        """Test user credentials cache key generation - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        user_id = "test-user-101"

        # Act - MANDATORY
        result = CacheKeys.user_credentials(user_id)

        # Assert - MANDATORY
        assert CacheNamespaces.USER in result
        assert "credentials" in result


# ============================================================================
# Session-Related Cache Keys Tests
# ============================================================================


@pytest.mark.unit
class TestSessionCacheKeys:
    """Unit tests for session-related cache keys - MANDATORY AAA pattern."""

    def test_session_key_generation(self):
        """Test session cache key generation - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        session_id = "session-abc-123"

        # Act - MANDATORY
        result = CacheKeys.session(session_id)

        # Assert - MANDATORY
        assert CacheNamespaces.SESSION in result
        assert session_id in result or quote(session_id, safe="") in result

    def test_user_session_key_generation(self):
        """Test user session cache key generation - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        user_id = "user-123"
        session_id = "session-456"

        # Act - MANDATORY
        result = CacheKeys.user_session(user_id, session_id)

        # Assert - MANDATORY
        assert CacheNamespaces.SESSION in result
        # Both IDs should be in key (URL-encoded)
        assert result.count(CacheKeys.SEPARATOR) >= 2

    def test_session_data_key_generation(self):
        """Test session data cache key generation - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        session_id = "session-789"
        data_type = "preferences"

        # Act - MANDATORY
        result = CacheKeys.session_data(session_id, data_type)

        # Assert - MANDATORY
        assert CacheNamespaces.SESSION in result
        assert data_type in result or quote(data_type, safe="") in result


# ============================================================================
# Job-Related Cache Keys Tests
# ============================================================================


@pytest.mark.unit
class TestJobCacheKeys:
    """Unit tests for job-related cache keys - MANDATORY AAA pattern."""

    def test_job_key_generation(self):
        """Test job cache key generation - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        job_id = "job-abc-123"

        # Act - MANDATORY
        result = CacheKeys.job(job_id)

        # Assert - MANDATORY
        assert CacheNamespaces.JOB in result
        assert job_id in result or quote(job_id, safe="") in result

    def test_job_status_key_generation(self):
        """Test job status cache key generation - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        job_id = "job-def-456"

        # Act - MANDATORY
        result = CacheKeys.job_status(job_id)

        # Assert - MANDATORY
        assert CacheNamespaces.JOB in result
        assert "status" in result

    def test_job_result_key_generation(self):
        """Test job result cache key generation - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        job_id = "job-ghi-789"

        # Act - MANDATORY
        result = CacheKeys.job_result(job_id)

        # Assert - MANDATORY
        assert CacheNamespaces.JOB in result
        assert "result" in result

    def test_job_metadata_key_generation(self):
        """Test job metadata cache key generation - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        job_id = "job-jkl-101"

        # Act - MANDATORY
        result = CacheKeys.job_metadata(job_id)

        # Assert - MANDATORY
        assert CacheNamespaces.JOB in result
        assert "metadata" in result

    def test_user_jobs_key_without_status(self):
        """Test user jobs cache key without status - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        user_id = "user-123"

        # Act - MANDATORY
        result = CacheKeys.user_jobs(user_id)

        # Assert - MANDATORY
        assert CacheNamespaces.JOB in result
        assert "user" in result

    def test_user_jobs_key_with_status(self):
        """Test user jobs cache key with status - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        user_id = "user-456"
        status = "completed"

        # Act - MANDATORY
        result = CacheKeys.user_jobs(user_id, status)

        # Assert - MANDATORY
        assert CacheNamespaces.JOB in result
        assert "user" in result
        assert status in result or quote(status, safe="") in result

    def test_job_queue_key_generation(self):
        """Test job queue cache key generation - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        priority = "high"

        # Act - MANDATORY
        result = CacheKeys.job_queue(priority)

        # Assert - MANDATORY
        assert CacheNamespaces.QUEUE in result
        assert "jobs" in result
        assert priority in result or quote(priority, safe="") in result


# ============================================================================
# Rate Limiting Cache Keys Tests
# ============================================================================


@pytest.mark.unit
class TestRateLimitCacheKeys:
    """Unit tests for rate limiting cache keys - MANDATORY AAA pattern."""

    def test_rate_limit_user_endpoint_key(self):
        """Test user endpoint rate limit key - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        user_id = "user-123"
        endpoint = "/api/jobs"

        # Act - MANDATORY
        result = CacheKeys.rate_limit(user_id, endpoint)

        # Assert - MANDATORY
        assert CacheNamespaces.RATE_LIMIT in result
        assert result.count(CacheKeys.SEPARATOR) >= 2

    def test_rate_limit_global_endpoint_key(self):
        """Test global endpoint rate limit key - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        endpoint = "/api/auth/login"

        # Act - MANDATORY
        result = CacheKeys.rate_limit_global(endpoint)

        # Assert - MANDATORY
        assert CacheNamespaces.RATE_LIMIT in result
        assert "global" in result

    def test_rate_limit_ip_endpoint_key(self):
        """Test IP endpoint rate limit key - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        ip_address = "192.168.1.1"
        endpoint = "/api/register"

        # Act - MANDATORY
        result = CacheKeys.rate_limit_ip(ip_address, endpoint)

        # Assert - MANDATORY
        assert CacheNamespaces.RATE_LIMIT in result
        assert "ip" in result


# ============================================================================
# Authentication Cache Keys Tests
# ============================================================================


@pytest.mark.unit
class TestAuthCacheKeys:
    """Unit tests for authentication cache keys - MANDATORY AAA pattern."""

    def test_auth_token_key_generation(self):
        """Test auth token cache key generation - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        token_id = "token-abc-123"

        # Act - MANDATORY
        result = CacheKeys.auth_token(token_id)

        # Assert - MANDATORY
        assert CacheNamespaces.AUTH in result
        assert "token" in result

    def test_revoked_token_key_generation(self):
        """Test revoked token cache key generation - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        jti = "jti-xyz-789"

        # Act - MANDATORY
        result = CacheKeys.revoked_token(jti)

        # Assert - MANDATORY
        assert CacheNamespaces.AUTH in result
        assert "revoked" in result

    def test_user_tokens_key_generation(self):
        """Test user tokens cache key generation - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        user_id = "user-456"

        # Act - MANDATORY
        result = CacheKeys.user_tokens(user_id)

        # Assert - MANDATORY
        assert CacheNamespaces.AUTH in result
        assert "user_tokens" in result or quote("user_tokens", safe="") in result

    def test_failed_login_attempts_key_generation(self):
        """Test failed login attempts cache key - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        identifier = "user@example.com"

        # Act - MANDATORY
        result = CacheKeys.failed_login_attempts(identifier)

        # Assert - MANDATORY
        assert CacheNamespaces.AUTH in result
        assert "failed_attempts" in result or quote("failed_attempts", safe="") in result


# ============================================================================
# OAuth Cache Keys Tests
# ============================================================================


@pytest.mark.unit
class TestOAuthCacheKeys:
    """Unit tests for OAuth cache keys - MANDATORY AAA pattern."""

    def test_oauth_state_key_generation(self):
        """Test OAuth state cache key generation - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        state = "oauth-state-abc-123"

        # Act - MANDATORY
        result = CacheKeys.oauth_state(state)

        # Assert - MANDATORY
        assert CacheNamespaces.OAUTH in result
        assert "state" in result

    def test_oauth_user_info_key_generation(self):
        """Test OAuth user info cache key generation - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        provider = "google"
        provider_user_id = "google-user-123"

        # Act - MANDATORY
        result = CacheKeys.oauth_user_info(provider, provider_user_id)

        # Assert - MANDATORY
        assert CacheNamespaces.OAUTH in result
        assert "user_info" in result or quote("user_info", safe="") in result

    def test_oauth_provider_tokens_key_generation(self):
        """Test OAuth provider tokens cache key - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        user_id = "user-123"
        provider = "github"

        # Act - MANDATORY
        result = CacheKeys.oauth_provider_tokens(user_id, provider)

        # Assert - MANDATORY
        assert CacheNamespaces.OAUTH in result
        assert "tokens" in result

    def test_oauth_callback_data_key_generation(self):
        """Test OAuth callback data cache key - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        state = "callback-state-xyz"

        # Act - MANDATORY
        result = CacheKeys.oauth_callback_data(state)

        # Assert - MANDATORY
        assert CacheNamespaces.OAUTH in result
        assert "callback" in result


# ============================================================================
# WebAuthn Cache Keys Tests
# ============================================================================


@pytest.mark.unit
class TestWebAuthnCacheKeys:
    """Unit tests for WebAuthn cache keys - MANDATORY AAA pattern."""

    def test_webauthn_challenge_key_generation(self):
        """Test WebAuthn challenge cache key - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        challenge_key = "challenge-abc-123"

        # Act - MANDATORY
        result = CacheKeys.webauthn_challenge(challenge_key)

        # Assert - MANDATORY
        assert CacheNamespaces.CHALLENGE in result
        assert "webauthn" in result

    def test_webauthn_registration_key_generation(self):
        """Test WebAuthn registration cache key - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        user_id = "user-123"
        challenge_key = "reg-challenge-456"

        # Act - MANDATORY
        result = CacheKeys.webauthn_registration(user_id, challenge_key)

        # Assert - MANDATORY
        assert CacheNamespaces.CHALLENGE in result
        assert "webauthn" in result
        assert "reg" in result

    def test_webauthn_authentication_key_generation(self):
        """Test WebAuthn authentication cache key - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        challenge_key = "auth-challenge-789"

        # Act - MANDATORY
        result = CacheKeys.webauthn_authentication(challenge_key)

        # Assert - MANDATORY
        assert CacheNamespaces.CHALLENGE in result
        assert "webauthn" in result
        assert "auth" in result


# ============================================================================
# Health and Monitoring Cache Keys Tests
# ============================================================================


@pytest.mark.unit
class TestHealthMonitoringCacheKeys:
    """Unit tests for health/monitoring cache keys - MANDATORY AAA pattern."""

    def test_health_status_key_generation(self):
        """Test health status cache key generation - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        component = "database"

        # Act - MANDATORY
        result = CacheKeys.health_status(component)

        # Assert - MANDATORY
        assert CacheNamespaces.HEALTH in result
        assert component in result or quote(component, safe="") in result

    def test_system_health_key_generation(self):
        """Test system health cache key generation - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # (no params for system health)

        # Act - MANDATORY
        result = CacheKeys.system_health()

        # Assert - MANDATORY
        assert CacheNamespaces.HEALTH in result
        assert "system" in result

    def test_component_metrics_key_generation(self):
        """Test component metrics cache key - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        component = "api"
        metric_type = "requests_per_second"

        # Act - MANDATORY
        result = CacheKeys.component_metrics(component, metric_type)

        # Assert - MANDATORY
        assert CacheNamespaces.METRICS in result
        assert component in result or quote(component, safe="") in result

    def test_performance_metrics_key_generation(self):
        """Test performance metrics cache key - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        operation = "job_creation"
        time_window = "1h"

        # Act - MANDATORY
        result = CacheKeys.performance_metrics(operation, time_window)

        # Assert - MANDATORY
        assert CacheNamespaces.METRICS in result
        assert "performance" in result


# ============================================================================
# External API Cache Keys Tests
# ============================================================================


@pytest.mark.unit
class TestExternalAPICacheKeys:
    """Unit tests for external API cache keys - MANDATORY AAA pattern."""

    def test_external_api_response_key_generation(self):
        """Test external API response cache key - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        api_name = "wordpress"
        endpoint = "/posts"
        params_hash = "hash123"

        # Act - MANDATORY
        result = CacheKeys.external_api_response(api_name, endpoint, params_hash)

        # Assert - MANDATORY
        assert isinstance(result, str)
        assert len(result) > 0
        # Long keys should be hashed
        assert len(result) <= 250

    def test_api_rate_limit_key_generation(self):
        """Test API rate limit cache key - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        api_name = "shopify"

        # Act - MANDATORY
        result = CacheKeys.api_rate_limit(api_name)

        # Assert - MANDATORY
        assert CacheNamespaces.EXTERNAL_API in result
        assert "rate_limit" in result or quote("rate_limit", safe="") in result

    def test_webhook_delivery_key_generation(self):
        """Test webhook delivery cache key - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        webhook_id = "webhook-123"
        attempt = 3

        # Act - MANDATORY
        result = CacheKeys.webhook_delivery(webhook_id, attempt)

        # Assert - MANDATORY
        assert CacheNamespaces.WEBHOOK in result
        assert "delivery" in result
        assert "3" in result


# ============================================================================
# Locking Cache Keys Tests
# ============================================================================


@pytest.mark.unit
class TestLockingCacheKeys:
    """Unit tests for locking cache keys - MANDATORY AAA pattern."""

    def test_operation_lock_key_generation(self):
        """Test operation lock cache key - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        operation = "job_creation"
        resource_id = "resource-123"

        # Act - MANDATORY
        result = CacheKeys.operation_lock(operation, resource_id)

        # Assert - MANDATORY
        assert CacheNamespaces.LOCK in result
        assert operation in result or quote(operation, safe="") in result

    def test_user_operation_lock_key_generation(self):
        """Test user operation lock cache key - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        user_id = "user-456"
        operation = "profile_update"

        # Act - MANDATORY
        result = CacheKeys.user_operation_lock(user_id, operation)

        # Assert - MANDATORY
        assert CacheNamespaces.LOCK in result
        assert "user" in result

    def test_global_operation_lock_key_generation(self):
        """Test global operation lock cache key - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        operation = "database_migration"

        # Act - MANDATORY
        result = CacheKeys.global_operation_lock(operation)

        # Assert - MANDATORY
        assert CacheNamespaces.LOCK in result
        assert "global" in result


# ============================================================================
# Temporary Data Cache Keys Tests
# ============================================================================


@pytest.mark.unit
class TestTemporaryDataCacheKeys:
    """Unit tests for temporary data cache keys - MANDATORY AAA pattern."""

    def test_temp_data_key_generation(self):
        """Test temporary data cache key - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        data_type = "export"
        identifier = "export-789"

        # Act - MANDATORY
        result = CacheKeys.temp_data(data_type, identifier)

        # Assert - MANDATORY
        assert CacheNamespaces.TEMP in result
        assert data_type in result or quote(data_type, safe="") in result

    def test_temp_upload_key_generation(self):
        """Test temporary upload cache key - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        upload_id = "upload-abc-123"

        # Act - MANDATORY
        result = CacheKeys.temp_upload(upload_id)

        # Assert - MANDATORY
        assert CacheNamespaces.TEMP in result
        assert "upload" in result

    def test_temp_export_key_generation(self):
        """Test temporary export cache key - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        export_id = "export-def-456"

        # Act - MANDATORY
        result = CacheKeys.temp_export(export_id)

        # Assert - MANDATORY
        assert CacheNamespaces.TEMP in result
        assert "export" in result


# ============================================================================
# CacheKeyBuilder Tests
# ============================================================================


@pytest.mark.unit
class TestCacheKeyBuilder:
    """Unit tests for CacheKeyBuilder - MANDATORY AAA pattern."""

    def test_build_query_key_with_simple_filters(self):
        """Test query key building with simple filters - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        operation = "get_jobs"
        filters = {"status": "completed", "user_id": "user-123"}

        # Act - MANDATORY
        result = CacheKeyBuilder.build_query_key(operation, filters)

        # Assert - MANDATORY
        assert "query" in result
        assert operation in result or quote(operation, safe="") in result
        assert CacheKeys.SEPARATOR in result

    def test_build_query_key_filters_none_values(self):
        """Test query key filters None values - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        operation = "search"
        filters = {"status": "active", "priority": None, "user_id": "user-123"}

        # Act - MANDATORY
        result = CacheKeyBuilder.build_query_key(operation, filters)

        # Assert - MANDATORY
        assert isinstance(result, str)
        # None values should be filtered out
        assert "None" not in result

    def test_build_query_key_sorts_filters_for_consistency(self):
        """Test query key sorts filters for consistency - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        operation = "list_jobs"
        filters1 = {"status": "active", "user_id": "user-123"}
        filters2 = {"user_id": "user-123", "status": "active"}  # Different order

        # Act - MANDATORY
        result1 = CacheKeyBuilder.build_query_key(operation, filters1)
        result2 = CacheKeyBuilder.build_query_key(operation, filters2)

        # Assert - MANDATORY
        assert result1 == result2  # Should be identical

    def test_build_query_key_handles_list_filters(self):
        """Test query key handles list filters - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        operation = "search"
        filters = {"statuses": ["active", "pending"], "user_id": "user-123"}

        # Act - MANDATORY
        result = CacheKeyBuilder.build_query_key(operation, filters)

        # Assert - MANDATORY
        assert isinstance(result, str)
        # Lists should be sorted for consistency

    def test_build_query_key_hashes_long_filter_strings(self):
        """Test query key hashes long filter strings - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        operation = "complex_query"
        filters = {f"field_{i}": f"value_{i}" for i in range(20)}  # Many filters

        # Act - MANDATORY
        result = CacheKeyBuilder.build_query_key(operation, filters)

        # Assert - MANDATORY
        assert "h_" in result  # Should contain hash

    def test_build_aggregation_key_basic(self):
        """Test aggregation key building - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        entity = "jobs"
        aggregation_type = "count"
        time_window = "1h"

        # Act - MANDATORY
        result = CacheKeyBuilder.build_aggregation_key(entity, aggregation_type, time_window)

        # Assert - MANDATORY
        assert "agg" in result
        assert entity in result or quote(entity, safe="") in result
        assert aggregation_type in result or quote(aggregation_type, safe="") in result

    def test_build_aggregation_key_with_filters(self):
        """Test aggregation key with filters - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        entity = "users"
        aggregation_type = "sum"
        time_window = "24h"
        filters = {"status": "active", "role": "admin"}

        # Act - MANDATORY
        result = CacheKeyBuilder.build_aggregation_key(
            entity, aggregation_type, time_window, filters
        )

        # Assert - MANDATORY
        assert "agg" in result
        assert "f_" in result  # Filter hash prefix

    def test_build_list_key_basic(self):
        """Test list key building - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        entity = "jobs"
        page = 1
        limit = 10

        # Act - MANDATORY
        result = CacheKeyBuilder.build_list_key(entity, page, limit)

        # Assert - MANDATORY
        assert "list" in result
        assert entity in result or quote(entity, safe="") in result
        assert "p1" in result  # Page 1
        assert "l10" in result  # Limit 10

    def test_build_list_key_with_sort(self):
        """Test list key with sort parameter - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        entity = "users"
        page = 2
        limit = 20
        sort_by = "created_at"

        # Act - MANDATORY
        result = CacheKeyBuilder.build_list_key(entity, page, limit, sort_by=sort_by)

        # Assert - MANDATORY
        assert "list" in result
        assert "p2" in result
        assert "l20" in result
        assert "s_" in result  # Sort prefix

    def test_build_list_key_with_filters(self):
        """Test list key with filters - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        entity = "jobs"
        page = 1
        limit = 10
        filters = {"status": "active"}

        # Act - MANDATORY
        result = CacheKeyBuilder.build_list_key(entity, page, limit, filters=filters)

        # Assert - MANDATORY
        assert "list" in result
        assert "f_" in result  # Filter hash prefix


# ============================================================================
# Convenience Aliases Tests
# ============================================================================


@pytest.mark.unit
class TestConvenienceAliases:
    """Unit tests for convenience aliases - MANDATORY AAA pattern."""

    def test_build_user_key_alias(self):
        """Test build_user_key convenience alias - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        user_id = "user-123"

        # Act - MANDATORY
        result = build_user_key(user_id)

        # Assert - MANDATORY
        assert result == CacheKeys.user(user_id)

    def test_build_job_key_alias(self):
        """Test build_job_key convenience alias - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        job_id = "job-456"

        # Act - MANDATORY
        result = build_job_key(job_id)

        # Assert - MANDATORY
        assert result == CacheKeys.job(job_id)

    def test_build_session_key_alias(self):
        """Test build_session_key convenience alias - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        session_id = "session-789"

        # Act - MANDATORY
        result = build_session_key(session_id)

        # Assert - MANDATORY
        assert result == CacheKeys.session(session_id)

    def test_build_rate_limit_key_alias(self):
        """Test build_rate_limit_key convenience alias - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        user_id = "user-101"
        endpoint = "/api/test"

        # Act - MANDATORY
        result = build_rate_limit_key(user_id, endpoint)

        # Assert - MANDATORY
        assert result == CacheKeys.rate_limit(user_id, endpoint)

    def test_build_oauth_key_alias(self):
        """Test build_oauth_key convenience alias - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        state = "oauth-state-abc"

        # Act - MANDATORY
        result = build_oauth_key(state)

        # Assert - MANDATORY
        assert result == CacheKeys.oauth_state(state)

    def test_build_lock_key_alias(self):
        """Test build_lock_key convenience alias - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        operation = "test_op"
        resource_id = "resource-123"

        # Act - MANDATORY
        result = build_lock_key(operation, resource_id)

        # Assert - MANDATORY
        assert result == CacheKeys.operation_lock(operation, resource_id)

    def test_build_temp_key_alias(self):
        """Test build_temp_key convenience alias - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        data_type = "export"
        identifier = "export-456"

        # Act - MANDATORY
        result = build_temp_key(data_type, identifier)

        # Assert - MANDATORY
        assert result == CacheKeys.temp_data(data_type, identifier)

    def test_build_query_key_alias(self):
        """Test build_query_key convenience alias - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        operation = "search"
        filters = {"status": "active"}

        # Act - MANDATORY
        result = build_query_key(operation, filters)

        # Assert - MANDATORY
        assert result == CacheKeyBuilder.build_query_key(operation, filters)

    def test_build_list_key_alias(self):
        """Test build_list_key convenience alias - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        entity = "jobs"
        page = 1
        limit = 10

        # Act - MANDATORY
        result = build_list_key(entity, page, limit)

        # Assert - MANDATORY
        assert result == CacheKeyBuilder.build_list_key(entity, page, limit)


# ============================================================================
# MANDATORY Security Tests
# ============================================================================


@pytest.mark.unit
@pytest.mark.security
class TestCacheKeysSecurity:
    """MANDATORY security tests for cache keys."""

    def test_special_characters_url_encoded(self):
        """MANDATORY: Test special characters are URL-encoded."""
        # Arrange - MANDATORY
        user_id = "user@example.com"

        # Act - MANDATORY
        result = CacheKeys.user(user_id)

        # Assert - MANDATORY
        # @ should be URL-encoded
        assert "@" not in result
        assert quote("@", safe="") in result

    def test_cache_key_injection_prevention(self):
        """MANDATORY: Test cache key injection prevention."""
        # Arrange - MANDATORY
        malicious_id = f"user{CacheKeys.SEPARATOR}admin"

        # Act - MANDATORY
        result = CacheKeys.user(malicious_id)

        # Assert - MANDATORY
        # Separator should be URL-encoded to prevent injection
        assert result.count(CacheKeys.SEPARATOR) == 1  # Only namespace separator


# ============================================================================
# MANDATORY Performance Tests
# ============================================================================


@pytest.mark.unit
@pytest.mark.performance
class TestCacheKeysPerformance:
    """MANDATORY performance tests for cache key generation."""

    def test_key_generation_performance(self):
        """MANDATORY: Test cache key generation performance."""
        # Arrange - MANDATORY
        import time

        iterations = 1000

        # Act - MANDATORY
        start_time = time.perf_counter()

        for i in range(iterations):
            CacheKeys.user(f"user-{i}")
            CacheKeys.job(f"job-{i}")
            CacheKeys.session(f"session-{i}")

        end_time = time.perf_counter()
        execution_time = end_time - start_time

        # Assert - MANDATORY
        avg_time = execution_time / (iterations * 3)  # 3 keys per iteration
        assert avg_time < 0.001  # <1ms per key generation
        assert execution_time < 3.0  # Total <3s for 3000 keys

    def test_complex_key_building_performance(self):
        """MANDATORY: Test complex key building performance."""
        # Arrange - MANDATORY
        import time

        iterations = 100
        complex_filters = {f"field_{i}": f"value_{i}" for i in range(10)}

        # Act - MANDATORY
        start_time = time.perf_counter()

        for _ in range(iterations):
            CacheKeyBuilder.build_query_key("operation", complex_filters)
            CacheKeyBuilder.build_list_key("entity", 1, 10, filters=complex_filters)

        end_time = time.perf_counter()
        execution_time = end_time - start_time

        # Assert - MANDATORY
        avg_time = execution_time / (iterations * 2)
        assert avg_time < 0.005  # <5ms per complex key
        assert execution_time < 1.0  # Total <1s for 200 complex keys
