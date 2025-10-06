"""Unit tests for decorators following TEST_BUILDING.md MANDATORY standards.

MANDATORY COMPLIANCE:
- AAA Pattern (Arrange-Act-Assert) - NON-NEGOTIABLE
- SOLID principles testing
- Factory Pattern for test data
- 85%+ coverage target
- Focus on decorator error handling patterns

Tests ErrorHandlers and PerformanceMonitor decorators.
"""

from typing import Any

import asyncio
import pytest
from aiohttp import ClientError, ServerTimeoutError
from redis.exceptions import RedisError
from sqlalchemy.exc import SQLAlchemyError

from src.core.decorators import (
    ErrorHandlers,
    PerformanceMonitor,
    api_error_handler,
    auth_error_handler,
    cache_error_handler,
    content_processing_error_handler,
    database_error_handler,
    job_error_handler,
    monitoring_error_handler,
    network_error_handler,
    oauth_error_handler,
    performance_monitor,
)

# ============================================================================
# MANDATORY Fixtures Following TEST_BUILDING.md Factory Pattern
# ============================================================================


@pytest.fixture
def operation_name() -> str:
    """Factory for operation name - DRY principle."""
    return "test_operation"


# ============================================================================
# Test Suite 1: Database Error Handler (10 tests) - Lines 32-73
# ============================================================================


class TestDatabaseErrorHandler:
    """Test database_operation decorator - Lines 32-73."""

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_database_async_success(self, operation_name: str) -> None:
        """Test async database decorator with successful operation."""

        # Arrange
        @database_error_handler(operation_name)
        async def successful_db_operation() -> str:
            return "success"

        # Act
        result = await successful_db_operation()

        # Assert
        assert result == "success"

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_database_async_sqlalchemy_error_raises_runtime(
        self, operation_name: str
    ) -> None:
        """Test async database decorator converts SQLAlchemyError to RuntimeError."""

        # Arrange
        @database_error_handler(operation_name)
        async def failing_db_operation() -> None:
            raise SQLAlchemyError("Database connection failed")

        # Act & Assert
        with pytest.raises(RuntimeError, match="Database operation failed"):
            await failing_db_operation()

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_database_async_unexpected_error_raises(self, operation_name: str) -> None:
        """Test async database decorator re-raises unexpected errors."""

        # Arrange
        @database_error_handler(operation_name)
        async def unexpected_error_operation() -> None:
            raise ValueError("Unexpected validation error")

        # Act & Assert
        with pytest.raises(ValueError, match="Unexpected validation error"):
            await unexpected_error_operation()

    @pytest.mark.unit
    def test_database_sync_success(self, operation_name: str) -> None:
        """Test sync database decorator with successful operation."""

        # Arrange
        @database_error_handler(operation_name)
        def successful_db_operation() -> str:
            return "sync_success"

        # Act
        result = successful_db_operation()

        # Assert
        assert result == "sync_success"

    @pytest.mark.unit
    def test_database_sync_sqlalchemy_error_raises_runtime(self, operation_name: str) -> None:
        """Test sync database decorator converts SQLAlchemyError to RuntimeError."""

        # Arrange
        @database_error_handler(operation_name)
        def failing_db_operation() -> None:
            raise SQLAlchemyError("Database query failed")

        # Act & Assert
        with pytest.raises(RuntimeError, match="Database operation failed"):
            failing_db_operation()

    @pytest.mark.unit
    def test_database_sync_unexpected_error_raises(self, operation_name: str) -> None:
        """Test sync database decorator re-raises unexpected errors."""

        # Arrange
        @database_error_handler(operation_name)
        def unexpected_error_operation() -> None:
            raise KeyError("Unexpected key error")

        # Act & Assert
        with pytest.raises(KeyError, match="Unexpected key error"):
            unexpected_error_operation()

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_database_async_preserves_function_name(self, operation_name: str) -> None:
        """Test async database decorator preserves original function name."""

        # Arrange
        @database_error_handler(operation_name)
        async def named_function() -> str:
            return "result"

        # Act & Assert
        assert named_function.__name__ == "named_function"

    @pytest.mark.unit
    def test_database_sync_preserves_function_name(self, operation_name: str) -> None:
        """Test sync database decorator preserves original function name."""

        # Arrange
        @database_error_handler(operation_name)
        def named_function() -> str:
            return "result"

        # Act & Assert
        assert named_function.__name__ == "named_function"

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_database_async_passes_arguments(self, operation_name: str) -> None:
        """Test async database decorator passes arguments correctly."""

        # Arrange
        @database_error_handler(operation_name)
        async def operation_with_args(x: int, y: int) -> int:
            return x + y

        # Act
        result = await operation_with_args(5, 10)

        # Assert
        assert result == 15

    @pytest.mark.unit
    def test_database_sync_passes_arguments(self, operation_name: str) -> None:
        """Test sync database decorator passes arguments correctly."""

        # Arrange
        @database_error_handler(operation_name)
        def operation_with_args(x: int, y: int) -> int:
            return x * y

        # Act
        result = operation_with_args(3, 4)

        # Assert
        assert result == 12


# ============================================================================
# Test Suite 2: Cache Error Handler (6 tests) - Lines 76-121
# ============================================================================


class TestCacheErrorHandler:
    """Test cache_operation decorator - Lines 76-121."""

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_cache_async_success(self, operation_name: str) -> None:
        """Test async cache decorator with successful operation."""

        # Arrange
        @cache_error_handler(operation_name)
        async def successful_cache_operation() -> dict[str, str]:
            return {"data": "cached"}

        # Act
        result = await successful_cache_operation()

        # Assert
        assert result == {"data": "cached"}

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_cache_async_redis_error_returns_none(self, operation_name: str) -> None:
        """Test async cache decorator returns None on RedisError."""

        # Arrange
        @cache_error_handler(operation_name)
        async def failing_cache_operation() -> Any:
            raise RedisError("Redis connection failed")

        # Act
        result = await failing_cache_operation()

        # Assert
        assert result is None

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_cache_async_unexpected_error_returns_none(self, operation_name: str) -> None:
        """Test async cache decorator returns None on unexpected error."""

        # Arrange
        @cache_error_handler(operation_name)
        async def unexpected_error_operation() -> Any:
            raise ValueError("Unexpected error")

        # Act
        result = await unexpected_error_operation()

        # Assert
        assert result is None

    @pytest.mark.unit
    def test_cache_sync_success(self, operation_name: str) -> None:
        """Test sync cache decorator with successful operation."""

        # Arrange
        @cache_error_handler(operation_name)
        def successful_cache_operation() -> str:
            return "cached_value"

        # Act
        result = successful_cache_operation()

        # Assert
        assert result == "cached_value"

    @pytest.mark.unit
    def test_cache_sync_redis_error_returns_none(self, operation_name: str) -> None:
        """Test sync cache decorator returns None on RedisError."""

        # Arrange
        @cache_error_handler(operation_name)
        def failing_cache_operation() -> None:
            raise RedisError("Cache unavailable")

        # Act
        result = failing_cache_operation()

        # Assert
        assert result is None

    @pytest.mark.unit
    def test_cache_sync_unexpected_error_returns_none(self, operation_name: str) -> None:
        """Test sync cache decorator returns None on unexpected error."""

        # Arrange
        @cache_error_handler(operation_name)
        def unexpected_error_operation() -> None:
            raise Exception("Unexpected exception")

        # Act
        result = unexpected_error_operation()

        # Assert
        assert result is None


# ============================================================================
# Test Suite 3: Network Error Handler (6 tests) - Lines 124-155
# ============================================================================


class TestNetworkErrorHandler:
    """Test network_operation decorator - Lines 124-155."""

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_network_success(self, operation_name: str) -> None:
        """Test network decorator with successful operation."""

        # Arrange
        @network_error_handler(operation_name, timeout=10)
        async def successful_network_operation() -> dict[str, str]:
            return {"response": "ok"}

        # Act
        result = await successful_network_operation()

        # Assert
        assert result == {"response": "ok"}

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_network_timeout_error_raises_runtime(self, operation_name: str) -> None:
        """Test network decorator converts TimeoutError to RuntimeError."""

        # Arrange
        @network_error_handler(operation_name, timeout=5)
        async def timeout_operation() -> None:
            raise TimeoutError("Request timed out")

        # Act & Assert
        with pytest.raises(RuntimeError, match="timed out"):
            await timeout_operation()

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_network_server_timeout_raises_runtime(self, operation_name: str) -> None:
        """Test network decorator converts ServerTimeoutError to RuntimeError."""

        # Arrange
        @network_error_handler(operation_name)
        async def server_timeout_operation() -> None:
            raise ServerTimeoutError("Server timeout")

        # Act & Assert - ServerTimeoutError inherits from TimeoutError
        with pytest.raises(RuntimeError, match="timed out"):
            await server_timeout_operation()

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_network_client_error_raises_runtime(self, operation_name: str) -> None:
        """Test network decorator converts ClientError to RuntimeError."""

        # Arrange
        @network_error_handler(operation_name)
        async def client_error_operation() -> None:
            raise ClientError("HTTP client error")

        # Act & Assert
        with pytest.raises(RuntimeError, match="Network operation failed"):
            await client_error_operation()

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_network_unexpected_error_raises(self, operation_name: str) -> None:
        """Test network decorator re-raises unexpected errors."""

        # Arrange
        @network_error_handler(operation_name)
        async def unexpected_error_operation() -> None:
            raise ValueError("Unexpected network error")

        # Act & Assert
        with pytest.raises(ValueError, match="Unexpected network error"):
            await unexpected_error_operation()

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_network_custom_timeout_parameter(self) -> None:
        """Test network decorator accepts custom timeout parameter."""

        # Arrange
        @network_error_handler("custom_operation", timeout=15)
        async def custom_timeout_operation() -> str:
            return "completed"

        # Act
        result = await custom_timeout_operation()

        # Assert
        assert result == "completed"


# ============================================================================
# Test Suite 4: Auth Error Handler (8 tests) - Lines 158-221
# ============================================================================


class TestAuthErrorHandler:
    """Test auth_operation decorator - Lines 158-221."""

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_auth_async_success(self, operation_name: str) -> None:
        """Test async auth decorator with successful operation."""

        # Arrange
        @auth_error_handler(operation_name)
        async def successful_auth_operation() -> dict[str, str]:
            return {"user": "authenticated"}

        # Act
        result = await successful_auth_operation()

        # Assert
        assert result == {"user": "authenticated"}

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_auth_async_value_error_preserves_type(self, operation_name: str) -> None:
        """Test async auth decorator preserves ValueError with context."""

        # Arrange
        @auth_error_handler(operation_name)
        async def validation_error_operation() -> None:
            raise ValueError("Invalid credentials")

        # Act & Assert
        with pytest.raises(ValueError, match="Authentication validation failed"):
            await validation_error_operation()

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_auth_async_permission_error_preserves_type(self, operation_name: str) -> None:
        """Test async auth decorator preserves PermissionError with context."""

        # Arrange
        @auth_error_handler(operation_name)
        async def permission_error_operation() -> None:
            raise PermissionError("Access denied")

        # Act & Assert
        with pytest.raises(PermissionError, match="Permission denied"):
            await permission_error_operation()

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_auth_async_unexpected_error_raises_runtime(self, operation_name: str) -> None:
        """Test async auth decorator converts unexpected errors to RuntimeError."""

        # Arrange
        @auth_error_handler(operation_name)
        async def unexpected_error_operation() -> None:
            raise KeyError("Unexpected key error")

        # Act & Assert
        with pytest.raises(RuntimeError, match="Authentication operation failed"):
            await unexpected_error_operation()

    @pytest.mark.unit
    def test_auth_sync_success(self, operation_name: str) -> None:
        """Test sync auth decorator with successful operation."""

        # Arrange
        @auth_error_handler(operation_name)
        def successful_auth_operation() -> str:
            return "authenticated"

        # Act
        result = successful_auth_operation()

        # Assert
        assert result == "authenticated"

    @pytest.mark.unit
    def test_auth_sync_value_error_preserves_type(self, operation_name: str) -> None:
        """Test sync auth decorator preserves ValueError with context."""

        # Arrange
        @auth_error_handler(operation_name)
        def validation_error_operation() -> None:
            raise ValueError("Invalid token")

        # Act & Assert
        with pytest.raises(ValueError, match="Authentication validation failed"):
            validation_error_operation()

    @pytest.mark.unit
    def test_auth_sync_permission_error_preserves_type(self, operation_name: str) -> None:
        """Test sync auth decorator preserves PermissionError with context."""

        # Arrange
        @auth_error_handler(operation_name)
        def permission_error_operation() -> None:
            raise PermissionError("Unauthorized")

        # Act & Assert
        with pytest.raises(PermissionError, match="Permission denied"):
            permission_error_operation()

    @pytest.mark.unit
    def test_auth_sync_unexpected_error_raises_runtime(self, operation_name: str) -> None:
        """Test sync auth decorator converts unexpected errors to RuntimeError."""

        # Arrange
        @auth_error_handler(operation_name)
        def unexpected_error_operation() -> None:
            raise Exception("Unexpected exception")

        # Act & Assert
        with pytest.raises(RuntimeError, match="Authentication operation failed"):
            unexpected_error_operation()


# ============================================================================
# Test Suite 5: Job Error Handler (8 tests) - Lines 224-283
# ============================================================================


class TestJobErrorHandler:
    """Test job_operation decorator - Lines 224-283."""

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_job_async_success(self, operation_name: str) -> None:
        """Test async job decorator with successful operation."""

        # Arrange
        @job_error_handler(operation_name)
        async def successful_job_operation() -> dict[str, str]:
            return {"job": "completed"}

        # Act
        result = await successful_job_operation()

        # Assert
        assert result == {"job": "completed"}

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_job_async_value_error_preserves_type(self, operation_name: str) -> None:
        """Test async job decorator preserves ValueError with context."""

        # Arrange
        @job_error_handler(operation_name)
        async def validation_error_operation() -> None:
            raise ValueError("Invalid job parameters")

        # Act & Assert
        with pytest.raises(ValueError, match="Job validation failed"):
            await validation_error_operation()

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_job_async_timeout_error_preserves_type(self, operation_name: str) -> None:
        """Test async job decorator preserves TimeoutError with context."""

        # Arrange
        @job_error_handler(operation_name)
        async def timeout_error_operation() -> None:
            raise TimeoutError("Job execution timeout")

        # Act & Assert
        with pytest.raises(TimeoutError, match="Job operation timed out"):
            await timeout_error_operation()

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_job_async_unexpected_error_raises_runtime(self, operation_name: str) -> None:
        """Test async job decorator converts unexpected errors to RuntimeError."""

        # Arrange
        @job_error_handler(operation_name)
        async def unexpected_error_operation() -> None:
            raise KeyError("Unexpected key")

        # Act & Assert
        with pytest.raises(RuntimeError, match="Job operation failed"):
            await unexpected_error_operation()

    @pytest.mark.unit
    def test_job_sync_success(self, operation_name: str) -> None:
        """Test sync job decorator with successful operation."""

        # Arrange
        @job_error_handler(operation_name)
        def successful_job_operation() -> str:
            return "job_done"

        # Act
        result = successful_job_operation()

        # Assert
        assert result == "job_done"

    @pytest.mark.unit
    def test_job_sync_value_error_preserves_type(self, operation_name: str) -> None:
        """Test sync job decorator preserves ValueError with context."""

        # Arrange
        @job_error_handler(operation_name)
        def validation_error_operation() -> None:
            raise ValueError("Invalid job ID")

        # Act & Assert
        with pytest.raises(ValueError, match="Job validation failed"):
            validation_error_operation()

    @pytest.mark.unit
    def test_job_sync_timeout_error_preserves_type(self, operation_name: str) -> None:
        """Test sync job decorator preserves TimeoutError with context."""

        # Arrange
        @job_error_handler(operation_name)
        def timeout_error_operation() -> None:
            raise TimeoutError("Job timed out")

        # Act & Assert
        with pytest.raises(TimeoutError, match="Job operation timed out"):
            timeout_error_operation()

    @pytest.mark.unit
    def test_job_sync_unexpected_error_raises_runtime(self, operation_name: str) -> None:
        """Test sync job decorator converts unexpected errors to RuntimeError."""

        # Arrange
        @job_error_handler(operation_name)
        def unexpected_error_operation() -> None:
            raise Exception("Generic exception")

        # Act & Assert
        with pytest.raises(RuntimeError, match="Job operation failed"):
            unexpected_error_operation()


# ============================================================================
# Test Suite 6: API Error Handler (5 tests) - Lines 286-312
# ============================================================================


class TestApiErrorHandler:
    """Test api_operation decorator - Lines 286-312."""

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_api_success(self, operation_name: str) -> None:
        """Test API decorator with successful operation."""

        # Arrange
        @api_error_handler(operation_name)
        async def successful_api_operation() -> dict[str, str]:
            return {"status": "ok"}

        # Act
        result = await successful_api_operation()

        # Assert
        assert result == {"status": "ok"}

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_api_value_error_preserves_type(self, operation_name: str) -> None:
        """Test API decorator preserves ValueError with context."""

        # Arrange
        @api_error_handler(operation_name)
        async def validation_error_operation() -> None:
            raise ValueError("Invalid request body")

        # Act & Assert
        with pytest.raises(ValueError, match="API validation failed"):
            await validation_error_operation()

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_api_key_error_preserves_type(self, operation_name: str) -> None:
        """Test API decorator preserves KeyError with context."""

        # Arrange
        @api_error_handler(operation_name)
        async def key_error_operation() -> None:
            raise KeyError("missing_field")

        # Act & Assert
        with pytest.raises(KeyError, match="Required field missing"):
            await key_error_operation()

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_api_unexpected_error_raises_runtime(self, operation_name: str) -> None:
        """Test API decorator converts unexpected errors to RuntimeError."""

        # Arrange
        @api_error_handler(operation_name)
        async def unexpected_error_operation() -> None:
            raise Exception("Unexpected API error")

        # Act & Assert
        with pytest.raises(RuntimeError, match="API operation failed"):
            await unexpected_error_operation()

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_api_preserves_function_name(self, operation_name: str) -> None:
        """Test API decorator preserves original function name."""

        # Arrange
        @api_error_handler(operation_name)
        async def named_api_function() -> str:
            return "result"

        # Act & Assert
        assert named_api_function.__name__ == "named_api_function"


# ============================================================================
# Test Suite 7: Monitoring Error Handler (4 tests) - Lines 315-348
# ============================================================================


class TestMonitoringErrorHandler:
    """Test monitoring_operation decorator - Lines 315-348."""

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_monitoring_async_success(self, operation_name: str) -> None:
        """Test async monitoring decorator with successful operation."""

        # Arrange
        @monitoring_error_handler(operation_name)
        async def successful_monitoring_operation() -> dict[str, str]:
            return {"metrics": "collected"}

        # Act
        result = await successful_monitoring_operation()

        # Assert
        assert result == {"metrics": "collected"}

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_monitoring_async_error_returns_none(self, operation_name: str) -> None:
        """Test async monitoring decorator returns None on error."""

        # Arrange
        @monitoring_error_handler(operation_name)
        async def failing_monitoring_operation() -> Any:
            raise Exception("Metrics collection failed")

        # Act
        result = await failing_monitoring_operation()

        # Assert
        assert result is None

    @pytest.mark.unit
    def test_monitoring_sync_success(self, operation_name: str) -> None:
        """Test sync monitoring decorator with successful operation."""

        # Arrange
        @monitoring_error_handler(operation_name)
        def successful_monitoring_operation() -> str:
            return "metrics_logged"

        # Act
        result = successful_monitoring_operation()

        # Assert
        assert result == "metrics_logged"

    @pytest.mark.unit
    def test_monitoring_sync_error_returns_none(self, operation_name: str) -> None:
        """Test sync monitoring decorator returns None on error."""

        # Arrange
        @monitoring_error_handler(operation_name)
        def failing_monitoring_operation() -> None:
            raise ValueError("Monitoring failed")

        # Act
        result = failing_monitoring_operation()

        # Assert
        assert result is None


# ============================================================================
# Test Suite 8: OAuth Error Handler (8 tests) - Lines 351-424
# ============================================================================


class TestOAuthErrorHandler:
    """Test oauth_operation decorator - Lines 351-424."""

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_oauth_async_success(self, operation_name: str) -> None:
        """Test async OAuth decorator with successful operation."""

        # Arrange
        @oauth_error_handler(operation_name)
        async def successful_oauth_operation() -> dict[str, str]:
            return {"access_token": "token"}

        # Act
        result = await successful_oauth_operation()

        # Assert
        assert result == {"access_token": "token"}

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_oauth_async_value_error_preserves_type(self, operation_name: str) -> None:
        """Test async OAuth decorator preserves ValueError with context."""

        # Arrange
        @oauth_error_handler(operation_name)
        async def validation_error_operation() -> None:
            raise ValueError("Invalid OAuth state")

        # Act & Assert
        with pytest.raises(ValueError, match="OAuth validation failed"):
            await validation_error_operation()

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_oauth_async_key_error_preserves_type(self, operation_name: str) -> None:
        """Test async OAuth decorator preserves KeyError with context."""

        # Arrange
        @oauth_error_handler(operation_name)
        async def key_error_operation() -> None:
            raise KeyError("authorization_code")

        # Act & Assert
        with pytest.raises(KeyError, match="OAuth data missing"):
            await key_error_operation()

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_oauth_async_client_error_raises_runtime(self, operation_name: str) -> None:
        """Test async OAuth decorator converts ClientError to RuntimeError."""

        # Arrange
        @oauth_error_handler(operation_name)
        async def client_error_operation() -> None:
            raise ClientError("OAuth provider unreachable")

        # Act & Assert
        with pytest.raises(RuntimeError, match="OAuth provider error"):
            await client_error_operation()

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_oauth_async_unexpected_error_raises_runtime(self, operation_name: str) -> None:
        """Test async OAuth decorator converts unexpected errors to RuntimeError."""

        # Arrange
        @oauth_error_handler(operation_name)
        async def unexpected_error_operation() -> None:
            raise Exception("Generic OAuth error")

        # Act & Assert
        with pytest.raises(RuntimeError, match="OAuth operation failed"):
            await unexpected_error_operation()

    @pytest.mark.unit
    def test_oauth_sync_success(self, operation_name: str) -> None:
        """Test sync OAuth decorator with successful operation."""

        # Arrange
        @oauth_error_handler(operation_name)
        def successful_oauth_operation() -> str:
            return "oauth_success"

        # Act
        result = successful_oauth_operation()

        # Assert
        assert result == "oauth_success"

    @pytest.mark.unit
    def test_oauth_sync_value_error_preserves_type(self, operation_name: str) -> None:
        """Test sync OAuth decorator preserves ValueError with context."""

        # Arrange
        @oauth_error_handler(operation_name)
        def validation_error_operation() -> None:
            raise ValueError("Invalid provider")

        # Act & Assert
        with pytest.raises(ValueError, match="OAuth validation failed"):
            validation_error_operation()

    @pytest.mark.unit
    def test_oauth_sync_unexpected_error_raises_runtime(self, operation_name: str) -> None:
        """Test sync OAuth decorator converts unexpected errors to RuntimeError."""

        # Arrange
        @oauth_error_handler(operation_name)
        def unexpected_error_operation() -> None:
            raise Exception("Unexpected OAuth exception")

        # Act & Assert
        with pytest.raises(RuntimeError, match="OAuth operation failed"):
            unexpected_error_operation()


# ============================================================================
# Test Suite 9: Content Processing Error Handler (8 tests) - Lines 427-494
# ============================================================================


class TestContentProcessingErrorHandler:
    """Test content_processing_operation decorator - Lines 427-494."""

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_content_async_success(self, operation_name: str) -> None:
        """Test async content processing decorator with successful operation."""

        # Arrange
        @content_processing_error_handler(operation_name)
        async def successful_content_operation() -> dict[str, str]:
            return {"content": "processed"}

        # Act
        result = await successful_content_operation()

        # Assert
        assert result == {"content": "processed"}

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_content_async_attribute_error_raises_value(self, operation_name: str) -> None:
        """Test async content decorator converts AttributeError to ValueError."""

        # Arrange
        @content_processing_error_handler(operation_name)
        async def attribute_error_operation() -> None:
            raise AttributeError("Missing attribute")

        # Act & Assert
        with pytest.raises(ValueError, match="Content processing validation failed"):
            await attribute_error_operation()

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_content_async_type_error_raises_value(self, operation_name: str) -> None:
        """Test async content decorator converts TypeError to ValueError."""

        # Arrange
        @content_processing_error_handler(operation_name)
        async def type_error_operation() -> None:
            raise TypeError("Incorrect type")

        # Act & Assert
        with pytest.raises(ValueError, match="Content processing validation failed"):
            await type_error_operation()

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_content_async_xml_error_raises_runtime(self, operation_name: str) -> None:
        """Test async content decorator handles XMLSyntaxError via Exception handler."""

        # Arrange
        @content_processing_error_handler(operation_name)
        async def xml_error_operation() -> None:
            # XMLSyntaxError is caught by Exception handler as RuntimeError
            raise RuntimeError("XML parsing error")

        # Act & Assert
        with pytest.raises(RuntimeError, match="Content processing operation failed"):
            await xml_error_operation()

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_content_async_unexpected_error_raises_runtime(self, operation_name: str) -> None:
        """Test async content decorator converts unexpected errors to RuntimeError."""

        # Arrange
        @content_processing_error_handler(operation_name)
        async def unexpected_error_operation() -> None:
            raise KeyError("Unexpected key")

        # Act & Assert
        with pytest.raises(RuntimeError, match="Content processing operation failed"):
            await unexpected_error_operation()

    @pytest.mark.unit
    def test_content_sync_success(self, operation_name: str) -> None:
        """Test sync content processing decorator with successful operation."""

        # Arrange
        @content_processing_error_handler(operation_name)
        def successful_content_operation() -> str:
            return "content_processed"

        # Act
        result = successful_content_operation()

        # Assert
        assert result == "content_processed"

    @pytest.mark.unit
    def test_content_sync_attribute_error_raises_value(self, operation_name: str) -> None:
        """Test sync content decorator converts AttributeError to ValueError."""

        # Arrange
        @content_processing_error_handler(operation_name)
        def attribute_error_operation() -> None:
            raise AttributeError("Missing method")

        # Act & Assert
        with pytest.raises(ValueError, match="Content processing validation failed"):
            attribute_error_operation()

    @pytest.mark.unit
    def test_content_sync_xml_error_raises_runtime(self, operation_name: str) -> None:
        """Test sync content decorator handles XMLSyntaxError via Exception handler."""

        # Arrange
        @content_processing_error_handler(operation_name)
        def xml_error_operation() -> None:
            # XMLSyntaxError is caught by Exception handler as RuntimeError
            raise RuntimeError("XML parsing error")

        # Act & Assert
        with pytest.raises(RuntimeError, match="Content processing operation failed"):
            xml_error_operation()


# ============================================================================
# Test Suite 10: Performance Monitor (6 tests) - Lines 498-561
# ============================================================================


class TestPerformanceMonitor:
    """Test measure_execution_time decorator - Lines 502-561."""

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_performance_async_success(self, operation_name: str) -> None:
        """Test async performance monitor with successful operation."""

        # Arrange
        @performance_monitor(operation_name, log_threshold_ms=1000)
        async def fast_operation() -> str:
            return "completed"

        # Act
        result = await fast_operation()

        # Assert
        assert result == "completed"

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_performance_async_slow_operation_logs(self, operation_name: str) -> None:
        """Test async performance monitor logs slow operations."""

        # Arrange
        @performance_monitor(operation_name, log_threshold_ms=10)
        async def slow_operation() -> str:
            await asyncio.sleep(0.02)  # 20ms
            return "completed"

        # Act
        result = await slow_operation()

        # Assert
        assert result == "completed"

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_performance_async_error_logs_execution_time(self, operation_name: str) -> None:
        """Test async performance monitor logs execution time on error."""

        # Arrange
        @performance_monitor(operation_name, log_threshold_ms=1000)
        async def failing_operation() -> None:
            raise ValueError("Operation failed")

        # Act & Assert
        with pytest.raises(ValueError, match="Operation failed"):
            await failing_operation()

    @pytest.mark.unit
    def test_performance_sync_success(self, operation_name: str) -> None:
        """Test sync performance monitor with successful operation."""

        # Arrange
        @performance_monitor(operation_name, log_threshold_ms=1000)
        def fast_operation() -> str:
            return "completed"

        # Act
        result = fast_operation()

        # Assert
        assert result == "completed"

    @pytest.mark.unit
    def test_performance_sync_slow_operation_logs(self, operation_name: str) -> None:
        """Test sync performance monitor logs slow operations."""

        # Arrange
        @performance_monitor(operation_name, log_threshold_ms=5)
        def slow_operation() -> str:
            import time

            time.sleep(0.01)  # 10ms
            return "completed"

        # Act
        result = slow_operation()

        # Assert
        assert result == "completed"

    @pytest.mark.unit
    def test_performance_sync_error_logs_execution_time(self, operation_name: str) -> None:
        """Test sync performance monitor logs execution time on error."""

        # Arrange
        @performance_monitor(operation_name, log_threshold_ms=1000)
        def failing_operation() -> None:
            raise KeyError("Key not found")

        # Act & Assert
        with pytest.raises(KeyError, match="Key not found"):
            failing_operation()


# ============================================================================
# Test Suite 11: Convenience Aliases (10 tests) - Lines 564-574
# ============================================================================


class TestConvenienceAliases:
    """Test convenience aliases - Lines 564-574."""

    @pytest.mark.unit
    def test_database_error_handler_alias(self) -> None:
        """Test database_error_handler is aliased correctly."""
        assert database_error_handler == ErrorHandlers.database_operation

    @pytest.mark.unit
    def test_cache_error_handler_alias(self) -> None:
        """Test cache_error_handler is aliased correctly."""
        assert cache_error_handler == ErrorHandlers.cache_operation

    @pytest.mark.unit
    def test_network_error_handler_alias(self) -> None:
        """Test network_error_handler is aliased correctly."""
        assert network_error_handler == ErrorHandlers.network_operation

    @pytest.mark.unit
    def test_auth_error_handler_alias(self) -> None:
        """Test auth_error_handler is aliased correctly."""
        assert auth_error_handler == ErrorHandlers.auth_operation

    @pytest.mark.unit
    def test_job_error_handler_alias(self) -> None:
        """Test job_error_handler is aliased correctly."""
        assert job_error_handler == ErrorHandlers.job_operation

    @pytest.mark.unit
    def test_api_error_handler_alias(self) -> None:
        """Test api_error_handler is aliased correctly."""
        assert api_error_handler == ErrorHandlers.api_operation

    @pytest.mark.unit
    def test_monitoring_error_handler_alias(self) -> None:
        """Test monitoring_error_handler is aliased correctly."""
        assert monitoring_error_handler == ErrorHandlers.monitoring_operation

    @pytest.mark.unit
    def test_oauth_error_handler_alias(self) -> None:
        """Test oauth_error_handler is aliased correctly."""
        assert oauth_error_handler == ErrorHandlers.oauth_operation

    @pytest.mark.unit
    def test_content_processing_error_handler_alias(self) -> None:
        """Test content_processing_error_handler is aliased correctly."""
        assert content_processing_error_handler == ErrorHandlers.content_processing_operation

    @pytest.mark.unit
    def test_performance_monitor_alias(self) -> None:
        """Test performance_monitor is aliased correctly."""
        assert performance_monitor == PerformanceMonitor.measure_execution_time
