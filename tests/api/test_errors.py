"""Comprehensive tests for src/api/errors.py module.

This test module provides comprehensive coverage for all API error handling
in the API errors module to achieve 80%+ coverage as required.
"""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy.exc import DatabaseError, IntegrityError

from src.api.errors import (
    APIError,
    APIErrorFactory,
    BusinessLogicError,
    DatabaseError as APIDBError,
    ValidationError,
    business_logic_error,
    create_global_exception_handler,
    database_error,
    internal_server_error,
    not_found,
    validation_error,
)
from src.core.exceptions import APINotFoundError


class TestAPIErrorClasses:
    """Test custom API error classes."""

    def test_api_error_default_values(self):
        """Test APIError with default values."""
        error = APIError("Test message")

        assert error.message == "Test message"
        assert error.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert error.error_code == "API_ERROR"
        assert error.details == {}
        assert error.original_error is None

    def test_api_error_custom_values(self):
        """Test APIError with custom values."""
        original_exc = ValueError("Original error")
        details = {"field": "value"}

        error = APIError(
            message="Custom message",
            status_code=status.HTTP_400_BAD_REQUEST,
            error_code="CUSTOM_ERROR",
            details=details,
            original_error=original_exc,
        )

        assert error.message == "Custom message"
        assert error.status_code == status.HTTP_400_BAD_REQUEST
        assert error.error_code == "CUSTOM_ERROR"
        assert error.details == details
        assert error.original_error == original_exc

    def test_validation_error_creation(self):
        """Test ValidationError specific behavior."""
        error = ValidationError("Invalid field", field="email")

        assert error.message == "Invalid field"
        assert error.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert error.error_code == "API_VALIDATION_ERROR"
        assert error.details["field"] == "email"

    def test_validation_error_without_field(self):
        """Test ValidationError without field parameter."""
        error = ValidationError("Invalid request")

        assert error.message == "Invalid request"
        assert "field" not in error.details

    def test_resource_not_found_error(self):
        """Test APINotFoundError creation."""
        error = APINotFoundError("User", "123")

        assert error.message == "User '123' not found"
        assert error.status_code == status.HTTP_404_NOT_FOUND
        assert error.error_code == "API_NOT_FOUND"
        assert error.context["resource_type"] == "User"
        assert error.context["identifier"] == "123"

    def test_database_error_creation(self):
        """Test DatabaseError creation."""
        original_exc = IntegrityError("statement", "params", "orig")
        error = APIDBError("create user", original_exc)

        assert error.message == "Database operation failed: create user"
        assert error.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert error.error_code == "API_DATABASE_ERROR"
        assert error.context["operation"] == "create user"
        assert error.original_error == original_exc

    def test_business_logic_error_default(self):
        """Test BusinessLogicError with default error code."""
        error = BusinessLogicError("Invalid operation")

        assert error.message == "Invalid operation"
        assert error.status_code == status.HTTP_400_BAD_REQUEST
        assert error.error_code == "API_BUSINESS_LOGIC_ERROR"

    def test_business_logic_error_custom_code(self):
        """Test BusinessLogicError with custom error code."""
        error = BusinessLogicError("Insufficient balance", "INSUFFICIENT_FUNDS")

        assert error.message == "Insufficient balance"
        assert error.error_code == "INSUFFICIENT_FUNDS"


class TestAPIErrorFactory:
    """Test APIErrorFactory methods."""

    def test_not_found_factory(self):
        """Test not_found factory method."""
        exc = APIErrorFactory.not_found("Job", "123")

        assert isinstance(exc, HTTPException)
        assert exc.status_code == status.HTTP_404_NOT_FOUND
        assert "Job '123' not found" in str(exc.detail)
        assert "API_NOT_FOUND" in str(exc.detail)

    def test_database_error_factory(self):
        """Test database_error factory method."""
        original_exc = Exception("Database connection failed")
        exc = APIErrorFactory.database_error("update record", original_exc)

        assert isinstance(exc, HTTPException)
        assert exc.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert "Database operation failed: update record" in str(exc.detail)
        assert "API_DATABASE_ERROR" in str(exc.detail)

    def test_validation_error_factory(self):
        """Test validation_error factory method."""
        exc = APIErrorFactory.validation_error("Invalid email", field="email")

        assert isinstance(exc, HTTPException)
        assert exc.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert "Invalid email" in str(exc.detail)

    def test_business_logic_error_factory(self):
        """Test business_logic_error factory method."""
        exc = APIErrorFactory.business_logic_error("Operation not allowed")

        assert isinstance(exc, HTTPException)
        assert exc.status_code == status.HTTP_400_BAD_REQUEST
        assert "Operation not allowed" in str(exc.detail)

    def test_internal_server_error_factory(self):
        """Test internal_server_error factory method."""
        original_exc = Exception("Something went wrong")
        exc = APIErrorFactory.internal_server_error("Server error", original_exc)

        assert isinstance(exc, HTTPException)
        assert exc.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert "Server error" in str(exc.detail)

    def test_unauthorized_factory(self):
        """Test unauthorized factory method."""
        exc = APIErrorFactory.unauthorized("Invalid token")

        assert isinstance(exc, HTTPException)
        assert exc.status_code == status.HTTP_401_UNAUTHORIZED
        assert "Invalid token" in str(exc.detail)

    def test_forbidden_factory(self):
        """Test forbidden factory method."""
        exc = APIErrorFactory.forbidden("Access denied")

        assert isinstance(exc, HTTPException)
        assert exc.status_code == status.HTTP_403_FORBIDDEN
        assert "Access denied" in str(exc.detail)

    def test_rate_limit_exceeded_factory(self):
        """Test rate_limit_exceeded factory method."""
        exc = APIErrorFactory.rate_limit_exceeded("Too many requests")

        assert isinstance(exc, HTTPException)
        assert exc.status_code == status.HTTP_429_TOO_MANY_REQUESTS
        assert "Too many requests" in str(exc.detail)

    def test_service_unavailable_factory(self):
        """Test service_unavailable factory method."""
        details = {"retry_after": 60}
        exc = APIErrorFactory.service_unavailable("Service down", details)

        assert isinstance(exc, HTTPException)
        assert exc.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        assert "Service down" in str(exc.detail)

    def test_from_sqlalchemy_error_duplicate_key(self):
        """Test SQLAlchemy error conversion for duplicate key."""
        sql_error = IntegrityError(
            "statement", "params", "duplicate key value violates unique constraint"
        )
        exc = APIErrorFactory.from_sqlalchemy_error("create user", sql_error)

        assert exc.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert "Duplicate resource" in str(exc.detail)

    def test_from_sqlalchemy_error_foreign_key(self):
        """Test SQLAlchemy error conversion for foreign key violation."""
        sql_error = IntegrityError("statement", "params", "foreign key constraint fails")
        exc = APIErrorFactory.from_sqlalchemy_error("update record", sql_error)

        assert exc.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert "Invalid reference" in str(exc.detail)

    def test_from_sqlalchemy_error_not_null(self):
        """Test SQLAlchemy error conversion for not null violation."""
        sql_error = IntegrityError("statement", "params", "NOT NULL constraint failed")
        exc = APIErrorFactory.from_sqlalchemy_error("insert record", sql_error)

        assert exc.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert "Required field missing" in str(exc.detail)

    def test_from_sqlalchemy_error_generic(self):
        """Test SQLAlchemy error conversion for generic database error."""
        sql_error = DatabaseError("statement", "params", "connection lost")
        exc = APIErrorFactory.from_sqlalchemy_error("query data", sql_error)

        assert exc.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert "Database operation failed: query data" in str(exc.detail)

    def test_create_error_detail_basic(self):
        """Test _create_error_detail with basic error."""
        error = APIError("Test error", error_code="TEST_ERROR")
        detail = APIErrorFactory._create_error_detail(error)

        assert detail["error"] is True
        assert detail["message"] == "Test error"
        assert detail["error_code"] == "TEST_ERROR"
        # Timestamp should be present and valid ISO format
        assert "timestamp" in detail
        assert detail["timestamp"].endswith("Z")

    @patch("src.api.errors.APIErrorFactory._get_timestamp")
    def test_create_error_detail_with_details(self, mock_timestamp):
        """Test _create_error_detail with additional details."""
        mock_timestamp.return_value = "2024-01-01T00:00:00Z"

        error = APIError("Test error", details={"field": "value"})
        detail = APIErrorFactory._create_error_detail(error)

        assert detail["details"] == {"field": "value"}

    @patch("src.core.environment.EnvironmentLoader.get_bool")
    @patch("src.api.errors.APIErrorFactory._get_timestamp")
    def test_create_error_detail_debug_mode(self, mock_timestamp, mock_get_bool):
        """Test _create_error_detail with debug mode enabled."""
        mock_timestamp.return_value = "2024-01-01T00:00:00Z"
        mock_get_bool.return_value = True  # Enable debug mode

        original_exc = ValueError("Original error")
        error = APIError("Test error", original_error=original_exc)

        with patch("traceback.format_exc", return_value="Traceback details"):
            detail = APIErrorFactory._create_error_detail(error)

        assert "debug" in detail
        assert detail["debug"]["original_error"] == "Original error"
        assert detail["debug"]["error_type"] == "ValueError"
        assert detail["debug"]["traceback"] == "Traceback details"

    @patch("src.core.environment.EnvironmentLoader.get_bool")
    def test_create_error_detail_debug_mode_disabled(self, mock_get_bool):
        """Test _create_error_detail with debug mode disabled."""
        mock_get_bool.return_value = False  # Disable debug mode

        original_exc = ValueError("Original error")
        error = APIError("Test error", original_error=original_exc)
        detail = APIErrorFactory._create_error_detail(error)

        assert "debug" not in detail

    @patch("src.api.errors.logger")
    def test_log_error_500_level(self, mock_logger):
        """Test error logging for 500-level errors."""
        error = APIError("Server error", status_code=500)
        error.log_error("error")

        mock_logger.error.assert_called_once()

    @patch("src.api.errors.logger")
    def test_log_error_400_level(self, mock_logger):
        """Test error logging for 400-level errors."""
        error = APIError("Client error", status_code=400)
        error.log_error("warning")

        mock_logger.warning.assert_called_once()

    @patch("src.api.errors.logger")
    def test_log_error_200_level(self, mock_logger):
        """Test error logging for 200-level responses."""
        error = APIError("Success", status_code=200)
        error.log_error("info")

        mock_logger.info.assert_called_once()

    def test_get_timestamp_format(self):
        """Test timestamp format is correct."""
        timestamp = APIErrorFactory._get_timestamp()

        # Should be ISO format ending with Z
        assert timestamp.endswith("Z")
        assert "T" in timestamp

        # Should be parseable as datetime
        parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        assert isinstance(parsed, datetime)


class TestConvenienceFunctions:
    """Test convenience functions for backward compatibility."""

    @patch("src.api.errors.APIErrorFactory.not_found")
    def test_not_found_convenience(self, mock_factory):
        """Test not_found convenience function."""
        mock_factory.return_value = HTTPException(status_code=404, detail="Not found")

        result = not_found("User", "123")

        mock_factory.assert_called_once_with("User", "123")
        assert isinstance(result, HTTPException)

    @patch("src.api.errors.APIErrorFactory.internal_server_error")
    def test_internal_server_error_convenience(self, mock_factory):
        """Test internal_server_error convenience function."""
        mock_factory.return_value = HTTPException(status_code=500, detail="Server error")
        original_exc = Exception("Original")

        result = internal_server_error("Error message", original_exc)

        mock_factory.assert_called_once_with("Error message", original_exc)
        assert isinstance(result, HTTPException)

    @patch("src.api.errors.APIErrorFactory.validation_error")
    def test_validation_error_convenience(self, mock_factory):
        """Test validation_error convenience function."""
        mock_factory.return_value = HTTPException(status_code=422, detail="Validation error")

        result = validation_error("Invalid field", "email")

        mock_factory.assert_called_once_with("Invalid field", "email")
        assert isinstance(result, HTTPException)

    @patch("src.api.errors.APIErrorFactory.database_error")
    def test_database_error_convenience(self, mock_factory):
        """Test database_error convenience function."""
        mock_factory.return_value = HTTPException(status_code=500, detail="DB error")
        original_exc = DatabaseError("statement", "params", "orig")

        result = database_error("create record", original_exc)

        mock_factory.assert_called_once_with("create record", original_exc)
        assert isinstance(result, HTTPException)

    @patch("src.api.errors.APIErrorFactory.business_logic_error")
    def test_business_logic_error_convenience(self, mock_factory):
        """Test business_logic_error convenience function."""
        mock_factory.return_value = HTTPException(status_code=400, detail="Logic error")

        result = business_logic_error("Invalid operation", "INVALID_OP")

        mock_factory.assert_called_once_with("Invalid operation", "INVALID_OP")
        assert isinstance(result, HTTPException)


class TestGlobalExceptionHandler:
    """Test global exception handler."""

    @pytest.mark.asyncio
    async def test_global_exception_handler_creation(self):
        """Test creation of global exception handler."""
        handler = create_global_exception_handler()

        assert callable(handler)

    @pytest.mark.asyncio
    @patch("structlog.get_logger")
    @patch("src.api.errors.APIErrorFactory.internal_server_error")
    async def test_global_exception_handler_execution(self, mock_factory, mock_get_logger):
        """Test execution of global exception handler."""
        # Setup mocks
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger

        mock_http_exc = HTTPException(status_code=500, detail={"error": "Internal error"})
        mock_factory.return_value = mock_http_exc

        # Create mock request
        mock_request = MagicMock()
        mock_request.url.path = "/test/path"
        mock_request.method = "GET"

        # Create exception
        test_exception = Exception("Test error")

        # Create and execute handler
        handler = create_global_exception_handler()
        response = await handler(mock_request, test_exception)

        # Verify logging
        mock_logger.error.assert_called_once()
        log_call = mock_logger.error.call_args
        assert "Uncaught exception in API" in log_call[0][0]

        # Verify error factory call
        mock_factory.assert_called_once_with(
            "An unexpected error occurred", original_error=test_exception
        )

        # Verify response
        assert isinstance(response, JSONResponse)
        assert response.status_code == 500

    @pytest.mark.asyncio
    @patch("structlog.get_logger")
    @patch("src.api.errors.APIErrorFactory.internal_server_error")
    async def test_global_exception_handler_adds_path(self, mock_factory, mock_get_logger):
        """Test that global exception handler adds request path to error details."""
        # Setup mocks
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger

        # Create a mock HTTPException with dict detail
        mock_detail = {"error": "Internal error"}
        mock_http_exc = HTTPException(status_code=500, detail=mock_detail)
        mock_factory.return_value = mock_http_exc

        # Create mock request
        mock_request = MagicMock()
        mock_request.url.path = "/api/test"
        mock_request.method = "POST"

        # Create and execute handler
        handler = create_global_exception_handler()
        response = await handler(mock_request, Exception("Test"))

        # Verify path was added to detail
        assert mock_detail["path"] == "/api/test"


class TestErrorIntegration:
    """Integration tests for error handling patterns."""

    def test_error_hierarchy_consistency(self):
        """Test that all custom errors inherit from APIError properly."""
        validation_err = ValidationError("Test")
        not_found_err = APINotFoundError("User", "123")
        db_err = APIDBError("operation", Exception())
        business_err = BusinessLogicError("Test")

        # All should be instances of APIError
        assert isinstance(validation_err, APIError)
        assert isinstance(not_found_err, APIError)
        assert isinstance(db_err, APIError)
        assert isinstance(business_err, APIError)

        # All should be instances of Exception
        assert isinstance(validation_err, Exception)
        assert isinstance(not_found_err, Exception)
        assert isinstance(db_err, Exception)
        assert isinstance(business_err, Exception)

    def test_factory_error_consistency(self):
        """Test that factory methods produce consistent error structures."""
        errors = [
            APIErrorFactory.not_found("User", "123"),
            APIErrorFactory.validation_error("Invalid"),
            APIErrorFactory.database_error("operation", Exception()),
            APIErrorFactory.business_logic_error("Invalid"),
            APIErrorFactory.internal_server_error("Error"),
        ]

        for error in errors:
            assert isinstance(error, HTTPException)
            assert hasattr(error, "status_code")
            assert hasattr(error, "detail")
            assert isinstance(error.detail, dict)
            assert "error" in error.detail
            assert "message" in error.detail
            assert "error_code" in error.detail
            assert "timestamp" in error.detail
