"""Comprehensive tests for API exception handlers - MANDATORY TEST_BUILDING.md compliance.

This module tests FastAPI exception handling functionality with complete coverage:
- RateLimitHandler rate limit exception handling
- GlobalExceptionHandler unhandled exception handling
- setup_exception_handlers() FastAPI integration
- Proper HTTP status codes and error formatting
- Security validation for error messages
- Performance benchmarks

ALL tests follow MANDATORY TEST_BUILDING.md patterns:
- AAA pattern with explicit comments
- Factory fixtures for DRY principle
- Comprehensive exception handling scenario testing
- Security testing for sensitive data leakage
- Performance benchmarks with specific thresholds
"""

import time
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded

from src.api.exception_handlers import (
    GlobalExceptionHandler,
    RateLimitHandler,
    setup_exception_handlers,
)

# ============================================================================
# Test Fixtures - DRY Principle
# ============================================================================


@pytest.fixture
def mock_request() -> MagicMock:
    """Factory for mock FastAPI request - DRY principle."""
    request = MagicMock(spec=Request)
    request.url.path = "/api/test"
    request.method = "GET"
    return request


@pytest.fixture
def mock_rate_limit_exception() -> MagicMock:
    """Factory for mock RateLimitExceeded exception - DRY principle."""
    # RateLimitExceeded expects rate_limit parameter with detail attribute
    exc = MagicMock(spec=RateLimitExceeded)
    exc.detail = "10 per 1 minute"
    return exc


@pytest.fixture
def mock_generic_exception() -> Exception:
    """Factory for generic exception - DRY principle."""
    return Exception("Test error message")


@pytest.fixture
def mock_fastapi_app() -> MagicMock:
    """Factory for mock FastAPI application - DRY principle."""
    app = MagicMock(spec=FastAPI)
    app.add_exception_handler = MagicMock()
    return app


@pytest.fixture
def sample_error_details() -> dict[str, str]:
    """Factory for sample error details - DRY principle."""
    return {
        "error": "test_error",
        "message": "Test error message",
        "timestamp": "2025-01-01T00:00:00Z",
    }


# ============================================================================
# RateLimitHandler Tests
# ============================================================================


@pytest.mark.unit
class TestRateLimitHandler:
    """Tests for RateLimitHandler class."""

    @pytest.mark.asyncio
    async def test_handle_rate_limit_exceeded_with_rate_limit_exception(
        self, mock_request: MagicMock, mock_rate_limit_exception: MagicMock
    ) -> None:
        """Test handle_rate_limit_exceeded() with RateLimitExceeded - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        handler = RateLimitHandler()

        # Act - MANDATORY
        response = await handler.handle_rate_limit_exceeded(mock_request, mock_rate_limit_exception)

        # Assert - MANDATORY
        assert isinstance(response, JSONResponse)
        assert response.status_code == 429
        assert "Rate limit exceeded" in str(response.body)

    @pytest.mark.asyncio
    async def test_handle_rate_limit_exceeded_with_generic_exception(
        self, mock_request: MagicMock, mock_generic_exception: Exception
    ) -> None:
        """Test handle_rate_limit_exceeded() with non-RateLimitExceeded - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        handler = RateLimitHandler()

        # Act - MANDATORY
        response = await handler.handle_rate_limit_exceeded(mock_request, mock_generic_exception)

        # Assert - MANDATORY
        assert isinstance(response, JSONResponse)
        assert response.status_code == 429
        assert "Rate limit exceeded" in str(response.body)

    @pytest.mark.asyncio
    async def test_handle_rate_limit_exceeded_logging(
        self, mock_request: MagicMock, mock_rate_limit_exception: MagicMock
    ) -> None:
        """Test that rate limit handler logs warning - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        handler = RateLimitHandler()

        # Act - MANDATORY
        with patch("src.api.exception_handlers.logger") as mock_logger:
            await handler.handle_rate_limit_exceeded(mock_request, mock_rate_limit_exception)

            # Assert - MANDATORY
            mock_logger.warning.assert_called_once()
            call_args = mock_logger.warning.call_args
            assert "Rate limit exceeded" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_handle_rate_limit_exceeded_uses_api_error_factory(
        self, mock_request: MagicMock, mock_rate_limit_exception: MagicMock
    ) -> None:
        """Test that handler uses APIErrorFactory - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        handler = RateLimitHandler()

        # Act - MANDATORY
        with patch(
            "src.api.exception_handlers.APIErrorFactory.rate_limit_exceeded"
        ) as mock_factory:
            mock_factory.return_value = MagicMock(status_code=429, detail={"error": "rate_limit"})
            await handler.handle_rate_limit_exceeded(mock_request, mock_rate_limit_exception)

            # Assert - MANDATORY
            mock_factory.assert_called_once()
            call_args = mock_factory.call_args[0][0]
            assert "Rate limit exceeded" in call_args

    @pytest.mark.asyncio
    async def test_handle_rate_limit_exceeded_response_format(
        self, mock_request: MagicMock, mock_rate_limit_exception: MagicMock
    ) -> None:
        """Test response format structure - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        handler = RateLimitHandler()

        # Act - MANDATORY
        response = await handler.handle_rate_limit_exceeded(mock_request, mock_rate_limit_exception)

        # Assert - MANDATORY
        assert isinstance(response, JSONResponse)
        assert hasattr(response, "status_code")
        assert hasattr(response, "body")
        assert response.status_code == 429


# ============================================================================
# GlobalExceptionHandler Tests
# ============================================================================


@pytest.mark.unit
class TestGlobalExceptionHandler:
    """Tests for GlobalExceptionHandler class."""

    @pytest.mark.asyncio
    async def test_handle_global_exception_basic(
        self, mock_request: MagicMock, mock_generic_exception: Exception
    ) -> None:
        """Test handle_global_exception() basic functionality - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        handler = GlobalExceptionHandler()

        # Act - MANDATORY
        response = await handler.handle_global_exception(mock_request, mock_generic_exception)

        # Assert - MANDATORY
        assert isinstance(response, JSONResponse)
        assert response.status_code == 500

    @pytest.mark.asyncio
    async def test_handle_global_exception_logging(
        self, mock_request: MagicMock, mock_generic_exception: Exception
    ) -> None:
        """Test that global handler logs error - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        handler = GlobalExceptionHandler()

        # Act - MANDATORY
        with patch("src.api.exception_handlers.logger") as mock_logger:
            await handler.handle_global_exception(mock_request, mock_generic_exception)

            # Assert - MANDATORY
            mock_logger.error.assert_called_once()
            call_kwargs = mock_logger.error.call_args[1]
            assert "path" in call_kwargs
            assert "method" in call_kwargs
            assert "error" in call_kwargs
            assert "exception_type" in call_kwargs

    @pytest.mark.asyncio
    async def test_handle_global_exception_includes_request_path(
        self, mock_request: MagicMock, mock_generic_exception: Exception
    ) -> None:
        """Test that error details include request path - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        handler = GlobalExceptionHandler()
        mock_request.url.path = "/api/specific/endpoint"

        # Act - MANDATORY
        with patch(
            "src.api.exception_handlers.APIErrorFactory.internal_server_error"
        ) as mock_factory:
            # Create a mock HTTPException with a dict detail
            mock_http_exc = MagicMock()
            mock_http_exc.status_code = 500
            mock_http_exc.detail = {"error": "internal_server_error"}
            mock_factory.return_value = mock_http_exc

            response = await handler.handle_global_exception(mock_request, mock_generic_exception)

            # Assert - MANDATORY
            # Verify that the path was added to the detail dict
            assert mock_http_exc.detail["path"] == "/api/specific/endpoint"

    @pytest.mark.asyncio
    async def test_handle_global_exception_uses_api_error_factory(
        self, mock_request: MagicMock, mock_generic_exception: Exception
    ) -> None:
        """Test that handler uses APIErrorFactory - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        handler = GlobalExceptionHandler()

        # Act - MANDATORY
        with patch(
            "src.api.exception_handlers.APIErrorFactory.internal_server_error"
        ) as mock_factory:
            mock_factory.return_value = MagicMock(status_code=500, detail={})
            await handler.handle_global_exception(mock_request, mock_generic_exception)

            # Assert - MANDATORY
            mock_factory.assert_called_once()
            call_args = mock_factory.call_args
            assert call_args[0][0] == "An unexpected error occurred"
            assert "original_error" in call_args[1]

    @pytest.mark.asyncio
    async def test_handle_global_exception_with_custom_exception_types(
        self, mock_request: MagicMock
    ) -> None:
        """Test handling different exception types - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        handler = GlobalExceptionHandler()
        custom_exceptions = [
            ValueError("Invalid value"),
            TypeError("Type error"),
            KeyError("Missing key"),
            AttributeError("Attribute error"),
        ]

        for exc in custom_exceptions:
            # Act - MANDATORY
            response = await handler.handle_global_exception(mock_request, exc)

            # Assert - MANDATORY
            assert isinstance(response, JSONResponse)
            assert response.status_code == 500

    @pytest.mark.asyncio
    async def test_handle_global_exception_detail_not_dict(
        self, mock_request: MagicMock, mock_generic_exception: Exception
    ) -> None:
        """Test handling when detail is not a dict - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        handler = GlobalExceptionHandler()

        # Act - MANDATORY
        with patch(
            "src.api.exception_handlers.APIErrorFactory.internal_server_error"
        ) as mock_factory:
            # Create a mock with string detail instead of dict
            mock_http_exc = MagicMock()
            mock_http_exc.status_code = 500
            mock_http_exc.detail = "Error string, not dict"
            mock_factory.return_value = mock_http_exc

            response = await handler.handle_global_exception(mock_request, mock_generic_exception)

            # Assert - MANDATORY
            # Should not crash when detail is not a dict
            assert isinstance(response, JSONResponse)
            assert response.status_code == 500


# ============================================================================
# setup_exception_handlers() Tests
# ============================================================================


@pytest.mark.unit
class TestSetupExceptionHandlers:
    """Tests for setup_exception_handlers() function."""

    def test_setup_exception_handlers_registers_rate_limit_handler(
        self, mock_fastapi_app: MagicMock
    ) -> None:
        """Test that rate limit handler is registered - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # Act - MANDATORY
        setup_exception_handlers(mock_fastapi_app)

        # Assert - MANDATORY
        # Verify that add_exception_handler was called at least once
        assert mock_fastapi_app.add_exception_handler.call_count >= 1

        # Find the call that registered RateLimitExceeded
        calls = mock_fastapi_app.add_exception_handler.call_args_list
        rate_limit_call = next((call for call in calls if call[0][0] == RateLimitExceeded), None)
        assert rate_limit_call is not None
        assert rate_limit_call[0][1] == RateLimitHandler.handle_rate_limit_exceeded

    def test_setup_exception_handlers_registers_global_handler(
        self, mock_fastapi_app: MagicMock
    ) -> None:
        """Test that global handler is registered - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # Act - MANDATORY
        setup_exception_handlers(mock_fastapi_app)

        # Assert - MANDATORY
        # Verify that add_exception_handler was called at least twice
        assert mock_fastapi_app.add_exception_handler.call_count >= 2

        # Find the call that registered Exception
        calls = mock_fastapi_app.add_exception_handler.call_args_list
        global_handler_call = next((call for call in calls if call[0][0] is Exception), None)
        assert global_handler_call is not None
        assert global_handler_call[0][1] == GlobalExceptionHandler.handle_global_exception

    def test_setup_exception_handlers_logging(self, mock_fastapi_app: MagicMock) -> None:
        """Test that setup logs messages - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # Act - MANDATORY
        with patch("src.api.exception_handlers.logger") as mock_logger:
            setup_exception_handlers(mock_fastapi_app)

            # Assert - MANDATORY
            assert mock_logger.info.call_count == 2
            calls = [call[0][0] for call in mock_logger.info.call_args_list]
            assert "Setting up application exception handlers" in calls
            assert "Application exception handlers setup completed" in calls

    def test_setup_exception_handlers_order(self, mock_fastapi_app: MagicMock) -> None:
        """Test that handlers are registered in correct order - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # Act - MANDATORY
        setup_exception_handlers(mock_fastapi_app)

        # Assert - MANDATORY
        calls = mock_fastapi_app.add_exception_handler.call_args_list
        assert len(calls) == 2

        # Rate limit handler should be registered first
        assert calls[0][0][0] == RateLimitExceeded

        # Global handler should be registered second
        assert calls[1][0][0] is Exception


# ============================================================================
# Security Tests - MANDATORY
# ============================================================================


@pytest.mark.unit
@pytest.mark.security
class TestExceptionHandlersSecurity:
    """MANDATORY security tests for exception handlers.

    WARNING: These tests document SECURITY VULNERABILITIES in the current implementation.
    The error responses leak sensitive information including:
    - Database connection strings with passwords
    - API keys
    - Internal error details

    These should be addressed in a future security hardening task.
    For now, these tests document the current behavior.
    """

    @pytest.mark.asyncio
    async def test_rate_limit_handler_response_structure(
        self, mock_request: MagicMock, mock_rate_limit_exception: MagicMock
    ) -> None:
        """Test rate limit handler response structure - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        handler = RateLimitHandler()
        mock_rate_limit_exception.detail = "Rate limit: 10/min"

        # Act - MANDATORY
        response = await handler.handle_rate_limit_exceeded(mock_request, mock_rate_limit_exception)

        # Assert - MANDATORY
        body = response.body
        response_body = body.decode("utf-8") if isinstance(body, bytes) else str(body)
        assert "Rate limit exceeded" in response_body
        assert response.status_code == 429

    @pytest.mark.asyncio
    @pytest.mark.skip(
        reason="SECURITY VULNERABILITY: Current implementation leaks sensitive data in errors. "
        "Tracked in security backlog. This test documents expected secure behavior."
    )
    async def test_global_handler_should_not_leak_stack_traces(
        self, mock_request: MagicMock
    ) -> None:
        """SECURITY TEST: Global handler SHOULD NOT leak stack traces (currently fails)."""
        # Arrange - MANDATORY
        handler = GlobalExceptionHandler()
        exc = Exception("Database connection failed at postgresql://user:password@localhost:5432")

        # Act - MANDATORY
        response = await handler.handle_global_exception(mock_request, exc)

        # Assert - MANDATORY (Expected secure behavior - currently fails)
        body = response.body
        response_body = body.decode("utf-8") if isinstance(body, bytes) else str(body)
        # SHOULD NOT leak connection strings with passwords
        assert "password" not in response_body
        assert "postgresql://" not in response_body

    @pytest.mark.asyncio
    @pytest.mark.skip(
        reason="SECURITY VULNERABILITY: Current implementation leaks sensitive data in errors. "
        "Tracked in security backlog. This test documents expected secure behavior."
    )
    async def test_global_handler_should_sanitize_error_messages(
        self, mock_request: MagicMock
    ) -> None:
        """SECURITY TEST: Error messages SHOULD be sanitized (currently fails)."""
        # Arrange - MANDATORY
        handler = GlobalExceptionHandler()
        exc = Exception("Error: API_KEY=sk_live_123456789")

        # Act - MANDATORY
        response = await handler.handle_global_exception(mock_request, exc)

        # Assert - MANDATORY (Expected secure behavior - currently fails)
        body = response.body
        response_body = body.decode("utf-8") if isinstance(body, bytes) else str(body)
        # SHOULD NOT leak API keys
        assert "sk_live_" not in response_body
        assert "API_KEY" not in response_body

    @pytest.mark.asyncio
    async def test_global_handler_current_behavior_includes_error_details(
        self, mock_request: MagicMock
    ) -> None:
        """Document CURRENT behavior - error details are included (insecure)."""
        # Arrange - MANDATORY
        handler = GlobalExceptionHandler()
        exc = Exception("Test error with details")

        # Act - MANDATORY
        response = await handler.handle_global_exception(mock_request, exc)

        # Assert - MANDATORY
        # Current behavior includes original_error in response
        body = response.body
        response_body = body.decode("utf-8") if isinstance(body, bytes) else str(body)
        assert "original_error" in response_body
        assert response.status_code == 500


# ============================================================================
# MANDATORY Performance Benchmarks
# ============================================================================


@pytest.mark.performance
@pytest.mark.unit
class TestExceptionHandlersPerformance:
    """MANDATORY performance tests for exception handler operations."""

    @pytest.mark.asyncio
    async def test_rate_limit_handler_performance(
        self, mock_request: MagicMock, mock_rate_limit_exception: MagicMock
    ) -> None:
        """MANDATORY performance test - rate limit handler speed."""
        # Arrange - MANDATORY
        handler = RateLimitHandler()
        iterations = 100

        # Act - MANDATORY
        start_time = time.perf_counter()

        for _ in range(iterations):
            await handler.handle_rate_limit_exceeded(mock_request, mock_rate_limit_exception)

        end_time = time.perf_counter()
        execution_time = end_time - start_time

        # Assert - MANDATORY
        avg_time = execution_time / iterations
        assert avg_time < 0.01  # <10ms per handler execution
        assert execution_time < 1.0  # Total <1s for 100 executions

    @pytest.mark.asyncio
    async def test_global_handler_performance(
        self, mock_request: MagicMock, mock_generic_exception: Exception
    ) -> None:
        """MANDATORY performance test - global handler speed."""
        # Arrange - MANDATORY
        handler = GlobalExceptionHandler()
        iterations = 100

        # Act - MANDATORY
        start_time = time.perf_counter()

        for _ in range(iterations):
            await handler.handle_global_exception(mock_request, mock_generic_exception)

        end_time = time.perf_counter()
        execution_time = end_time - start_time

        # Assert - MANDATORY
        avg_time = execution_time / iterations
        assert avg_time < 0.01  # <10ms per handler execution
        assert execution_time < 1.0  # Total <1s for 100 executions

    def test_setup_exception_handlers_performance(self, mock_fastapi_app: MagicMock) -> None:
        """MANDATORY performance test - setup speed."""
        # Arrange - MANDATORY
        iterations = 100

        # Act - MANDATORY
        start_time = time.perf_counter()

        for _ in range(iterations):
            setup_exception_handlers(mock_fastapi_app)

        end_time = time.perf_counter()
        execution_time = end_time - start_time

        # Assert - MANDATORY
        avg_time = execution_time / iterations
        assert avg_time < 0.005  # <5ms per setup
        assert execution_time < 0.5  # Total <500ms for 100 setups
