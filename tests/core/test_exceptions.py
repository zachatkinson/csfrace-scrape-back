"""Comprehensive tests for src/core/exceptions.py.

Test coverage: 122 statements, 53% → 85%+
Following TEST_BUILDING.md MANDATORY standards with ZERO TOLERANCE.
"""

import pytest

from src.core.exceptions import (
    APIBusinessLogicError,
    APIDatabaseError,
    APIError,
    APINotFoundError,
    APIValidationError,
    AuthenticationError,
    AuthorizationError,
    BaseApplicationError,
    BusinessLogicError,
    ConfigurationError,
    ConversionError,
    DatabaseError,
    ExceptionMapper,
    FetchError,
    ProcessingError,
    RateLimitError,
    ResourceNotFoundError,
    SaveError,
    ServiceUnavailableError,
    ValidationError,
)

# =============================================================================
# FIXTURES - Factory Pattern for DRY Principle
# =============================================================================


@pytest.fixture
def sample_original_error():
    """Factory for original error - DRY principle."""
    return ValueError("Original error message")


@pytest.fixture
def sample_details():
    """Factory for error details - DRY principle."""
    return {"key1": "value1", "key2": "value2"}


@pytest.fixture
def sample_context():
    """Factory for error context - DRY principle."""
    return {"context_key": "context_value"}


# =============================================================================
# TEST BaseApplicationError - Core Exception Class
# =============================================================================


@pytest.mark.unit
class TestBaseApplicationError:
    """Test BaseApplicationError core functionality."""

    def test_base_error_init_minimal(self):
        """Test BaseApplicationError with minimal parameters."""
        # Arrange & Act
        error = BaseApplicationError("Test error")

        # Assert
        assert error.message == "Test error"
        assert error.error_code == "APPLICATION_ERROR"
        assert error.details == {}
        assert error.original_error is None
        assert error.context == {}
        assert isinstance(error.timestamp, str)

    def test_base_error_init_full(self, sample_original_error, sample_details, sample_context):
        """Test BaseApplicationError with all parameters."""
        # Arrange & Act
        error = BaseApplicationError(
            message="Test error",
            error_code="TEST_ERROR",
            details=sample_details,
            original_error=sample_original_error,
            context=sample_context,
        )

        # Assert
        assert error.message == "Test error"
        assert error.error_code == "TEST_ERROR"
        assert error.details == sample_details
        assert error.original_error == sample_original_error
        assert error.context == sample_context

    def test_base_error_str_minimal(self):
        """Test string representation with minimal parameters."""
        # Arrange
        error = BaseApplicationError("Test error")

        # Act
        result = str(error)

        # Assert
        assert result == "Test error"

    def test_base_error_str_with_context(self):
        """Test string representation with context."""
        # Arrange
        error = BaseApplicationError("Test error", context={"url": "http://example.com"})

        # Act
        result = str(error)

        # Assert
        assert "Test error" in result
        assert "url=http://example.com" in result

    def test_base_error_str_with_original_error(self, sample_original_error):
        """Test string representation with original error."""
        # Arrange
        error = BaseApplicationError("Test error", original_error=sample_original_error)

        # Act
        result = str(error)

        # Assert
        assert "Test error" in result
        assert "Caused by: Original error message" in result

    def test_base_error_to_dict(self, sample_original_error, sample_details, sample_context):
        """Test to_dict conversion."""
        # Arrange
        error = BaseApplicationError(
            message="Test error",
            error_code="TEST_ERROR",
            details=sample_details,
            original_error=sample_original_error,
            context=sample_context,
        )

        # Act
        result = error.to_dict()

        # Assert
        assert result["error"] is True
        assert result["message"] == "Test error"
        assert result["error_code"] == "TEST_ERROR"
        assert result["details"] == sample_details
        assert result["context"] == sample_context
        assert result["original_error"] == "Original error message"
        assert result["original_error_type"] == "ValueError"
        assert isinstance(result["timestamp"], str)

    def test_base_error_to_dict_no_original_error(self):
        """Test to_dict conversion without original error."""
        # Arrange
        error = BaseApplicationError("Test error")

        # Act
        result = error.to_dict()

        # Assert
        assert result["original_error"] is None
        assert result["original_error_type"] is None

    def test_base_error_log_error_default(self, mocker):
        """Test log_error with default level."""
        # Arrange
        mock_logger = mocker.patch("src.core.exceptions.logger.error")
        error = BaseApplicationError("Test error")

        # Act
        error.log_error()

        # Assert
        mock_logger.assert_called_once()
        call_args = mock_logger.call_args
        assert "Application error: APPLICATION_ERROR" in call_args[0]

    def test_base_error_log_error_warning_level(self, mocker):
        """Test log_error with warning level."""
        # Arrange
        mock_logger = mocker.patch("src.core.exceptions.logger.warning")
        error = BaseApplicationError("Test error")

        # Act
        error.log_error(log_level="warning")

        # Assert
        mock_logger.assert_called_once()


# =============================================================================
# TEST Domain-Specific Exceptions
# =============================================================================


@pytest.mark.unit
class TestValidationError:
    """Test ValidationError exception."""

    def test_validation_error_minimal(self):
        """Test ValidationError with minimal parameters."""
        # Arrange & Act
        error = ValidationError("Invalid input")

        # Assert
        assert error.message == "Invalid input"
        assert error.error_code == "VALIDATION_ERROR"

    def test_validation_error_with_field(self):
        """Test ValidationError with field."""
        # Arrange & Act
        error = ValidationError("Invalid email", field="email")

        # Assert
        assert error.details["field"] == "email"

    def test_validation_error_with_value(self):
        """Test ValidationError with value."""
        # Arrange & Act
        error = ValidationError("Invalid email", value="not-an-email")

        # Assert
        assert error.details["invalid_value"] == "not-an-email"


@pytest.mark.unit
class TestResourceNotFoundError:
    """Test ResourceNotFoundError exception."""

    def test_resource_not_found_error(self):
        """Test ResourceNotFoundError construction."""
        # Arrange & Act
        error = ResourceNotFoundError("User", "user-123")

        # Assert
        assert "User 'user-123' not found" in error.message
        assert error.error_code == "RESOURCE_NOT_FOUND"
        assert error.context["resource_type"] == "User"
        assert error.context["identifier"] == "user-123"


@pytest.mark.unit
class TestConfigurationError:
    """Test ConfigurationError exception."""

    def test_configuration_error_default_message(self):
        """Test ConfigurationError with default message."""
        # Arrange & Act
        error = ConfigurationError("DATABASE_URL")

        # Assert
        assert "Configuration error for 'DATABASE_URL'" in error.message
        assert error.error_code == "CONFIGURATION_ERROR"
        assert error.context["config_key"] == "DATABASE_URL"

    def test_configuration_error_custom_message(self):
        """Test ConfigurationError with custom message."""
        # Arrange & Act
        error = ConfigurationError("DATABASE_URL", message="Custom error message")

        # Assert
        assert error.message == "Custom error message"


@pytest.mark.unit
class TestDatabaseError:
    """Test DatabaseError exception."""

    def test_database_error(self, sample_original_error):
        """Test DatabaseError construction."""
        # Arrange & Act
        error = DatabaseError("SELECT users", sample_original_error)

        # Assert
        assert "Database operation failed: SELECT users" in error.message
        assert error.error_code == "DATABASE_ERROR"
        assert error.original_error == sample_original_error
        assert error.context["operation"] == "SELECT users"


@pytest.mark.unit
class TestBusinessLogicError:
    """Test BusinessLogicError exception."""

    def test_business_logic_error_default(self):
        """Test BusinessLogicError with default error code."""
        # Arrange & Act
        error = BusinessLogicError("Cannot process refund")

        # Assert
        assert error.message == "Cannot process refund"
        assert error.error_code == "BUSINESS_LOGIC_ERROR"

    def test_business_logic_error_custom_code(self):
        """Test BusinessLogicError with custom error code."""
        # Arrange & Act
        error = BusinessLogicError("Cannot process refund", error_code="REFUND_ERROR")

        # Assert
        assert error.error_code == "REFUND_ERROR"


@pytest.mark.unit
class TestAuthenticationError:
    """Test AuthenticationError exception."""

    def test_authentication_error_default(self):
        """Test AuthenticationError with default message."""
        # Arrange & Act
        error = AuthenticationError()

        # Assert
        assert error.message == "Authentication required"
        assert error.error_code == "AUTHENTICATION_ERROR"

    def test_authentication_error_custom_message(self):
        """Test AuthenticationError with custom message."""
        # Arrange & Act
        error = AuthenticationError("Invalid credentials")

        # Assert
        assert error.message == "Invalid credentials"


@pytest.mark.unit
class TestAuthorizationError:
    """Test AuthorizationError exception."""

    def test_authorization_error_default(self):
        """Test AuthorizationError with default message."""
        # Arrange & Act
        error = AuthorizationError()

        # Assert
        assert error.message == "Access denied"
        assert error.error_code == "AUTHORIZATION_ERROR"

    def test_authorization_error_with_resource(self):
        """Test AuthorizationError with resource."""
        # Arrange & Act
        error = AuthorizationError(resource="user_profile")

        # Assert
        assert error.context["resource"] == "user_profile"

    def test_authorization_error_with_action(self):
        """Test AuthorizationError with action."""
        # Arrange & Act
        error = AuthorizationError(action="delete")

        # Assert
        assert error.context["action"] == "delete"


@pytest.mark.unit
class TestRateLimitError:
    """Test RateLimitError exception."""

    def test_rate_limit_error_default(self):
        """Test RateLimitError with default message."""
        # Arrange & Act
        error = RateLimitError()

        # Assert
        assert error.message == "Rate limit exceeded"
        assert error.error_code == "RATE_LIMIT_EXCEEDED"

    def test_rate_limit_error_with_limit_and_window(self):
        """Test RateLimitError with limit and window."""
        # Arrange & Act
        error = RateLimitError(limit=100, window="per hour")

        # Assert
        assert error.context["limit"] == 100
        assert error.context["window"] == "per hour"


@pytest.mark.unit
class TestServiceUnavailableError:
    """Test ServiceUnavailableError exception."""

    def test_service_unavailable_error_default(self):
        """Test ServiceUnavailableError with default message."""
        # Arrange & Act
        error = ServiceUnavailableError()

        # Assert
        assert error.message == "Service temporarily unavailable"
        assert error.error_code == "SERVICE_UNAVAILABLE"

    def test_service_unavailable_error_with_service_name(self):
        """Test ServiceUnavailableError with service name."""
        # Arrange & Act
        error = ServiceUnavailableError(service_name="Database")

        # Assert
        assert error.context["service"] == "Database"


# =============================================================================
# TEST Conversion-Specific Exceptions
# =============================================================================


@pytest.mark.unit
class TestConversionError:
    """Test ConversionError exception."""

    def test_conversion_error_minimal(self):
        """Test ConversionError with minimal parameters."""
        # Arrange & Act
        error = ConversionError("Conversion failed")

        # Assert
        assert error.message == "Conversion failed"
        assert error.error_code == "CONVERSION_ERROR"

    def test_conversion_error_with_url(self):
        """Test ConversionError with URL."""
        # Arrange & Act
        error = ConversionError("Conversion failed", url="http://example.com")

        # Assert
        assert error.context["url"] == "http://example.com"


@pytest.mark.unit
class TestFetchError:
    """Test FetchError exception."""

    def test_fetch_error_minimal(self):
        """Test FetchError with minimal parameters."""
        # Arrange & Act
        error = FetchError("Failed to fetch page")

        # Assert
        assert error.message == "Failed to fetch page"
        assert error.error_code == "FETCH_ERROR"

    def test_fetch_error_with_status_code(self):
        """Test FetchError with status code."""
        # Arrange & Act
        error = FetchError("Failed to fetch page", status_code=404)

        # Assert
        assert error.context["status_code"] == 404


@pytest.mark.unit
class TestProcessingError:
    """Test ProcessingError exception."""

    def test_processing_error_minimal(self):
        """Test ProcessingError with minimal parameters."""
        # Arrange & Act
        error = ProcessingError("Processing failed")

        # Assert
        assert error.message == "Processing failed"
        assert error.error_code == "PROCESSING_ERROR"

    def test_processing_error_with_processor(self):
        """Test ProcessingError with processor name."""
        # Arrange & Act
        error = ProcessingError("Processing failed", processor="HTMLProcessor")

        # Assert
        assert error.context["processor"] == "HTMLProcessor"


@pytest.mark.unit
class TestSaveError:
    """Test SaveError exception."""

    def test_save_error_minimal(self):
        """Test SaveError with minimal parameters."""
        # Arrange & Act
        error = SaveError("Failed to save file")

        # Assert
        assert error.message == "Failed to save file"
        assert error.error_code == "SAVE_ERROR"

    def test_save_error_with_file_path(self):
        """Test SaveError with file path."""
        # Arrange & Act
        error = SaveError("Failed to save file", file_path="/tmp/output.html")

        # Assert
        assert error.context["file_path"] == "/tmp/output.html"


# =============================================================================
# TEST API-Specific Exceptions
# =============================================================================


@pytest.mark.unit
class TestAPIError:
    """Test APIError exception."""

    def test_api_error_default(self):
        """Test APIError with default status code."""
        # Arrange & Act
        error = APIError("API error occurred")

        # Assert
        assert error.message == "API error occurred"
        assert error.status_code == 500
        assert error.error_code == "API_ERROR"

    def test_api_error_custom_status(self):
        """Test APIError with custom status code."""
        # Arrange & Act
        error = APIError("Not found", status_code=404)

        # Assert
        assert error.status_code == 404


@pytest.mark.unit
class TestAPIValidationError:
    """Test APIValidationError exception."""

    def test_api_validation_error(self):
        """Test APIValidationError construction."""
        # Arrange & Act
        error = APIValidationError("Invalid email", field="email", value="not-an-email")

        # Assert
        assert error.message == "Invalid email"
        assert error.status_code == 422
        assert error.error_code == "API_VALIDATION_ERROR"
        assert error.details["field"] == "email"


@pytest.mark.unit
class TestAPINotFoundError:
    """Test APINotFoundError exception."""

    def test_api_not_found_error(self):
        """Test APINotFoundError construction."""
        # Arrange & Act
        error = APINotFoundError("User", "user-123")

        # Assert
        assert "User 'user-123' not found" in error.message
        assert error.status_code == 404
        assert error.error_code == "API_NOT_FOUND"


@pytest.mark.unit
class TestAPIDatabaseError:
    """Test APIDatabaseError exception."""

    def test_api_database_error(self, sample_original_error):
        """Test APIDatabaseError construction."""
        # Arrange & Act
        error = APIDatabaseError("SELECT users", sample_original_error)

        # Assert
        assert "Database operation failed: SELECT users" in error.message
        assert error.status_code == 500
        assert error.error_code == "API_DATABASE_ERROR"


@pytest.mark.unit
class TestAPIBusinessLogicError:
    """Test APIBusinessLogicError exception."""

    def test_api_business_logic_error_default(self):
        """Test APIBusinessLogicError with default code."""
        # Arrange & Act
        error = APIBusinessLogicError("Cannot process refund")

        # Assert
        assert error.message == "Cannot process refund"
        assert error.status_code == 400
        assert error.error_code == "API_BUSINESS_LOGIC_ERROR"

    def test_api_business_logic_error_custom_code(self):
        """Test APIBusinessLogicError with custom code."""
        # Arrange & Act
        error = APIBusinessLogicError("Cannot process refund", error_code="REFUND_ERROR")

        # Assert
        assert error.error_code == "REFUND_ERROR"


# =============================================================================
# TEST ExceptionMapper - Conversion Utilities
# =============================================================================


@pytest.mark.unit
class TestExceptionMapper:
    """Test ExceptionMapper utility class."""

    def test_to_api_error_already_api_error(self):
        """Test to_api_error with already API error."""
        # Arrange
        api_error = APIError("Test error", status_code=400)

        # Act
        result = ExceptionMapper.to_api_error(api_error)

        # Assert
        assert result is api_error

    def test_to_api_error_validation_error(self):
        """Test to_api_error with ValidationError."""
        # Arrange
        validation_error = ValidationError("Invalid input")

        # Act
        result = ExceptionMapper.to_api_error(validation_error)

        # Assert
        assert isinstance(result, APIError)
        assert result.status_code == 422
        assert result.error_code == "API_VALIDATION_ERROR"

    def test_to_api_error_resource_not_found(self):
        """Test to_api_error with ResourceNotFoundError."""
        # Arrange
        not_found_error = ResourceNotFoundError("User", "user-123")

        # Act
        result = ExceptionMapper.to_api_error(not_found_error)

        # Assert
        assert result.status_code == 404

    def test_to_api_error_authentication_error(self):
        """Test to_api_error with AuthenticationError."""
        # Arrange
        auth_error = AuthenticationError()

        # Act
        result = ExceptionMapper.to_api_error(auth_error)

        # Assert
        assert result.status_code == 401

    def test_to_api_error_authorization_error(self):
        """Test to_api_error with AuthorizationError."""
        # Arrange
        authz_error = AuthorizationError()

        # Act
        result = ExceptionMapper.to_api_error(authz_error)

        # Assert
        assert result.status_code == 403

    def test_to_api_error_rate_limit_error(self):
        """Test to_api_error with RateLimitError."""
        # Arrange
        rate_limit_error = RateLimitError()

        # Act
        result = ExceptionMapper.to_api_error(rate_limit_error)

        # Assert
        assert result.status_code == 429

    def test_to_api_error_service_unavailable_error(self):
        """Test to_api_error with ServiceUnavailableError."""
        # Arrange
        service_error = ServiceUnavailableError()

        # Act
        result = ExceptionMapper.to_api_error(service_error)

        # Assert
        assert result.status_code == 503

    def test_to_api_error_database_error(self, sample_original_error):
        """Test to_api_error with DatabaseError."""
        # Arrange
        db_error = DatabaseError("SELECT users", sample_original_error)

        # Act
        result = ExceptionMapper.to_api_error(db_error)

        # Assert
        assert result.status_code == 500

    def test_to_api_error_fetch_error(self):
        """Test to_api_error with FetchError."""
        # Arrange
        fetch_error = FetchError("Failed to fetch")

        # Act
        result = ExceptionMapper.to_api_error(fetch_error)

        # Assert
        assert result.status_code == 502

    def test_to_api_error_unknown_error_code(self):
        """Test to_api_error with unknown error code."""
        # Arrange
        custom_error = BaseApplicationError("Custom error", error_code="CUSTOM_ERROR")

        # Act
        result = ExceptionMapper.to_api_error(custom_error)

        # Assert
        assert result.status_code == 500
        assert result.error_code == "API_CUSTOM_ERROR"

    def test_from_sqlalchemy_error_duplicate_key(self):
        """Test from_sqlalchemy_error with duplicate key error."""
        # Arrange
        sql_error = Exception("duplicate key value violates unique constraint")

        # Act
        result = ExceptionMapper.from_sqlalchemy_error("INSERT user", sql_error)

        # Assert
        assert isinstance(result, ValidationError)
        assert "Duplicate resource" in result.message
        assert result.details["constraint_type"] == "unique"

    def test_from_sqlalchemy_error_unique_constraint(self):
        """Test from_sqlalchemy_error with unique constraint error."""
        # Arrange
        sql_error = Exception("UNIQUE constraint failed: users.email")

        # Act
        result = ExceptionMapper.from_sqlalchemy_error("INSERT user", sql_error)

        # Assert
        assert isinstance(result, ValidationError)
        assert result.details["constraint_type"] == "unique"

    def test_from_sqlalchemy_error_foreign_key(self):
        """Test from_sqlalchemy_error with foreign key error."""
        # Arrange
        sql_error = Exception("foreign key constraint failed")

        # Act
        result = ExceptionMapper.from_sqlalchemy_error("INSERT post", sql_error)

        # Assert
        assert isinstance(result, ValidationError)
        assert "Invalid reference" in result.message
        assert result.details["constraint_type"] == "foreign_key"

    def test_from_sqlalchemy_error_not_null(self):
        """Test from_sqlalchemy_error with not null error."""
        # Arrange
        sql_error = Exception("NOT NULL constraint failed: users.email")

        # Act
        result = ExceptionMapper.from_sqlalchemy_error("INSERT user", sql_error)

        # Assert
        assert isinstance(result, ValidationError)
        assert "Required field missing" in result.message
        assert result.details["constraint_type"] == "not_null"

    def test_from_sqlalchemy_error_generic(self):
        """Test from_sqlalchemy_error with generic error."""
        # Arrange
        sql_error = Exception("Connection timeout")

        # Act
        result = ExceptionMapper.from_sqlalchemy_error("SELECT users", sql_error)

        # Assert
        assert isinstance(result, DatabaseError)
        assert result.context["operation"] == "SELECT users"
