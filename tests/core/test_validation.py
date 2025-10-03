"""Unit tests for ValidationEngine following TEST_BUILDING.md MANDATORY standards.

MANDATORY COMPLIANCE:
- AAA Pattern (Arrange-Act-Assert) - NON-NEGOTIABLE
- SOLID principles testing
- Factory Pattern for test data
- 85%+ coverage target
- Focus on validation edge cases and security

Tests ValidationEngine centralized validation methods.
"""

from datetime import datetime, timedelta
from uuid import uuid4

import pytest

from src.core.validation import (
    MAX_DESCRIPTION_LENGTH,
    MAX_EMAIL_LENGTH,
    MAX_FILENAME_LENGTH,
    MAX_PAGE_SIZE,
    MAX_URL_LENGTH,
    MAX_USERNAME_LENGTH,
    MIN_USERNAME_LENGTH,
    BulkValidator,
    ValidationEngine,
    ValidationError,
)

# ============================================================================
# MANDATORY Fixtures Following TEST_BUILDING.md Factory Pattern
# ============================================================================


@pytest.fixture
def valid_uuid():
    """Factory for valid UUID - DRY principle."""
    return str(uuid4())


@pytest.fixture
def valid_url():
    """Factory for valid HTTP URL."""
    return "https://example.com/page"


@pytest.fixture
def valid_username():
    """Factory for valid username."""
    return "testuser123"


@pytest.fixture
def valid_email():
    """Factory for valid email."""
    return "test@example.com"


# ============================================================================
# Test Suite 1: URL Validation (10 tests) - Lines 62-96
# ============================================================================


class TestValidateUrl:
    """Test URL validation method - Lines 62-96."""

    @pytest.mark.unit
    def test_url_valid_https(self):
        """Test url validates HTTPS URL."""
        # Arrange
        url = "https://example.com/page"

        # Act
        result = ValidationEngine.url(url)

        # Assert
        assert result == url

    @pytest.mark.unit
    def test_url_valid_http(self):
        """Test url validates HTTP URL."""
        # Arrange
        url = "http://example.com/page"

        # Act
        result = ValidationEngine.url(url)

        # Assert
        assert result == url

    @pytest.mark.unit
    def test_url_empty_raises(self):
        """Test url raises ValidationError for empty string."""
        # Act & Assert
        with pytest.raises(ValidationError, match="url cannot be empty"):
            ValidationEngine.url("")

    @pytest.mark.unit
    def test_url_whitespace_only_raises(self):
        """Test url raises ValidationError for whitespace."""
        # Act & Assert
        with pytest.raises(ValidationError, match="url cannot be empty"):
            ValidationEngine.url("   ")

    @pytest.mark.unit
    def test_url_too_long_raises(self):
        """Test url raises ValidationError when exceeding max length."""
        # Arrange
        long_url = "https://example.com/" + "a" * MAX_URL_LENGTH

        # Act & Assert
        with pytest.raises(ValidationError, match="too long"):
            ValidationEngine.url(long_url)

    @pytest.mark.unit
    def test_url_invalid_scheme_raises(self):
        """Test url raises ValidationError for non-HTTP scheme."""
        # Act & Assert
        with pytest.raises(ValidationError, match="must use HTTP or HTTPS"):
            ValidationEngine.url("ftp://example.com")

    @pytest.mark.unit
    def test_url_no_netloc_raises(self):
        """Test url raises ValidationError for URL without netloc."""
        # Act & Assert
        with pytest.raises(ValidationError, match="must be a valid URL"):
            ValidationEngine.url("https://")

    @pytest.mark.unit
    def test_url_localhost_forbidden(self):
        """Test url raises ValidationError for localhost."""
        # Act & Assert
        with pytest.raises(ValidationError, match="forbidden patterns"):
            ValidationEngine.url("http://localhost:8000")

    @pytest.mark.unit
    def test_url_127_0_0_1_forbidden(self):
        """Test url raises ValidationError for 127.0.0.1."""
        # Act & Assert
        with pytest.raises(ValidationError, match="forbidden patterns"):
            ValidationEngine.url("http://127.0.0.1/page")

    @pytest.mark.unit
    def test_url_strips_whitespace(self):
        """Test url strips surrounding whitespace."""
        # Arrange
        url = "  https://example.com  "

        # Act
        result = ValidationEngine.url(url)

        # Assert
        assert result == "https://example.com"


# ============================================================================
# Test Suite 2: Pagination Validation (4 tests) - Lines 98-112
# ============================================================================


class TestValidatePagination:
    """Test pagination validation method - Lines 98-112."""

    @pytest.mark.unit
    def test_pagination_valid(self):
        """Test pagination with valid values."""
        # Act
        skip, limit = ValidationEngine.pagination(0, 10)

        # Assert
        assert skip == 0
        assert limit == 10

    @pytest.mark.unit
    def test_pagination_negative_skip_raises(self):
        """Test pagination raises ValidationError for negative skip."""
        # Act & Assert
        with pytest.raises(ValidationError, match="Skip must be non-negative"):
            ValidationEngine.pagination(-1, 10)

    @pytest.mark.unit
    def test_pagination_zero_limit_raises(self):
        """Test pagination raises ValidationError for zero limit."""
        # Act & Assert
        with pytest.raises(ValidationError, match="Limit must be positive"):
            ValidationEngine.pagination(0, 0)

    @pytest.mark.unit
    def test_pagination_exceeds_max_raises(self):
        """Test pagination raises ValidationError when exceeding max page size."""
        # Act & Assert
        with pytest.raises(ValidationError, match=f"cannot exceed {MAX_PAGE_SIZE}"):
            ValidationEngine.pagination(0, MAX_PAGE_SIZE + 1)


# ============================================================================
# Test Suite 3: User ID Validation (4 tests) - Lines 114-129
# ============================================================================


class TestValidateUserId:
    """Test user_id validation method - Lines 114-129."""

    @pytest.mark.unit
    def test_user_id_valid_uuid(self, valid_uuid):
        """Test user_id with valid UUID."""
        # Act
        result = ValidationEngine.user_id(valid_uuid)

        # Assert
        assert result == valid_uuid

    @pytest.mark.unit
    def test_user_id_empty_raises(self):
        """Test user_id raises ValidationError for empty string."""
        # Act & Assert
        with pytest.raises(ValidationError, match="user_id cannot be empty"):
            ValidationEngine.user_id("")

    @pytest.mark.unit
    def test_user_id_invalid_format_raises(self):
        """Test user_id raises ValidationError for invalid UUID format."""
        # Act & Assert
        with pytest.raises(ValidationError, match="must be a valid UUID"):
            ValidationEngine.user_id("not-a-uuid")

    @pytest.mark.unit
    def test_user_id_strips_whitespace(self, valid_uuid):
        """Test user_id strips surrounding whitespace."""
        # Arrange
        padded_uuid = f"  {valid_uuid}  "

        # Act
        result = ValidationEngine.user_id(padded_uuid)

        # Assert
        assert result == valid_uuid


# ============================================================================
# Test Suite 4: Username Validation (6 tests) - Lines 131-160
# ============================================================================


class TestValidateUsername:
    """Test username validation method - Lines 131-160."""

    @pytest.mark.unit
    def test_username_valid(self, valid_username):
        """Test username with valid format."""
        # Act
        result = ValidationEngine.username(valid_username)

        # Assert
        assert result == valid_username

    @pytest.mark.unit
    def test_username_empty_raises(self):
        """Test username raises ValidationError for empty string."""
        # Act & Assert
        with pytest.raises(ValidationError, match="username cannot be empty"):
            ValidationEngine.username("")

    @pytest.mark.unit
    def test_username_too_short_raises(self):
        """Test username raises ValidationError when too short."""
        # Arrange
        short_name = "ab"  # Less than MIN_USERNAME_LENGTH

        # Act & Assert
        with pytest.raises(ValidationError, match=f"at least {MIN_USERNAME_LENGTH} characters"):
            ValidationEngine.username(short_name)

    @pytest.mark.unit
    def test_username_too_long_raises(self):
        """Test username raises ValidationError when too long."""
        # Arrange
        long_name = "a" * (MAX_USERNAME_LENGTH + 1)

        # Act & Assert
        with pytest.raises(ValidationError, match=f"cannot exceed {MAX_USERNAME_LENGTH}"):
            ValidationEngine.username(long_name)

    @pytest.mark.unit
    def test_username_invalid_characters_raises(self):
        """Test username raises ValidationError for invalid characters."""
        # Act & Assert
        with pytest.raises(ValidationError, match="can only contain"):
            ValidationEngine.username("user@name")

    @pytest.mark.unit
    def test_username_allows_underscores_hyphens(self):
        """Test username allows underscores and hyphens."""
        # Arrange
        username = "user_name-123"

        # Act
        result = ValidationEngine.username(username)

        # Assert
        assert result == username

    @pytest.mark.unit
    def test_username_rejects_dots_by_default(self):
        """Test username rejects dots when allow_dots=False (default)."""
        # Arrange
        username = "user.name"

        # Act & Assert
        with pytest.raises(
            ValidationError, match="can only contain letters, numbers, hyphens, and underscores"
        ):
            ValidationEngine.username(username)

    @pytest.mark.unit
    def test_username_allows_dots_when_enabled(self):
        """Test username allows dots when allow_dots=True (OAuth usernames)."""
        # Arrange
        username = "user.name123"

        # Act
        result = ValidationEngine.username(username, allow_dots=True)

        # Assert
        assert result == username

    @pytest.mark.unit
    def test_username_oauth_with_multiple_dots(self):
        """Test OAuth username with multiple dots (e.g., Google usernames)."""
        # Arrange
        username = "zach.atkinson85"

        # Act
        result = ValidationEngine.username(username, allow_dots=True)

        # Assert
        assert result == username

    @pytest.mark.unit
    def test_username_oauth_complex_format(self):
        """Test OAuth username with dots, underscores, and hyphens."""
        # Arrange
        username = "user.name_test-123"

        # Act
        result = ValidationEngine.username(username, allow_dots=True)

        # Assert
        assert result == username


# ============================================================================
# Test Suite 5: Email Validation (4 tests) - Lines 162-179
# ============================================================================


class TestValidateEmail:
    """Test email validation method - Lines 162-179."""

    @pytest.mark.unit
    def test_email_valid(self, valid_email):
        """Test email with valid format."""
        # Act
        result = ValidationEngine.email(valid_email)

        # Assert
        assert result == valid_email

    @pytest.mark.unit
    def test_email_empty_raises(self):
        """Test email raises ValidationError for empty string."""
        # Act & Assert
        with pytest.raises(ValidationError, match="email cannot be empty"):
            ValidationEngine.email("")

    @pytest.mark.unit
    def test_email_too_long_raises(self):
        """Test email raises ValidationError when exceeding max length."""
        # Arrange
        long_email = "a" * MAX_EMAIL_LENGTH + "@example.com"

        # Act & Assert
        with pytest.raises(ValidationError, match="too long"):
            ValidationEngine.email(long_email)

    @pytest.mark.unit
    def test_email_strips_whitespace(self, valid_email):
        """Test email strips surrounding whitespace."""
        # Arrange
        padded_email = f"  {valid_email}  "

        # Act
        result = ValidationEngine.email(padded_email)

        # Assert
        assert result == valid_email


# ============================================================================
# Test Suite 6: Job ID Validation (3 tests) - Lines 181-196
# ============================================================================


class TestValidateJobId:
    """Test job_id validation method - Lines 181-196."""

    @pytest.mark.unit
    def test_job_id_valid_uuid(self, valid_uuid):
        """Test job_id with valid UUID."""
        # Act
        result = ValidationEngine.job_id(valid_uuid)

        # Assert
        assert result == valid_uuid

    @pytest.mark.unit
    def test_job_id_empty_raises(self):
        """Test job_id raises ValidationError for empty string."""
        # Act & Assert
        with pytest.raises(ValidationError, match="job_id cannot be empty"):
            ValidationEngine.job_id("")

    @pytest.mark.unit
    def test_job_id_invalid_format_raises(self):
        """Test job_id raises ValidationError for invalid UUID format."""
        # Act & Assert
        with pytest.raises(ValidationError, match="must be a valid UUID"):
            ValidationEngine.job_id("invalid-job-id")


# ============================================================================
# Test Suite 7: Priority Validation (4 tests) - Lines 198-214
# ============================================================================


class TestValidatePriority:
    """Test priority validation method - Lines 198-214."""

    @pytest.mark.unit
    def test_priority_valid_values(self):
        """Test priority accepts all valid values."""
        # Arrange
        valid_priorities = ["low", "normal", "high", "urgent"]

        # Act & Assert
        for priority in valid_priorities:
            result = ValidationEngine.priority(priority)
            assert result == priority

    @pytest.mark.unit
    def test_priority_empty_raises(self):
        """Test priority raises ValidationError for empty string."""
        # Act & Assert
        with pytest.raises(ValidationError, match="priority cannot be empty"):
            ValidationEngine.priority("")

    @pytest.mark.unit
    def test_priority_invalid_value_raises(self):
        """Test priority raises ValidationError for invalid value."""
        # Act & Assert
        with pytest.raises(ValidationError, match="must be one of"):
            ValidationEngine.priority("critical")

    @pytest.mark.unit
    def test_priority_case_insensitive(self):
        """Test priority normalizes to lowercase."""
        # Act
        result = ValidationEngine.priority("HIGH")

        # Assert
        assert result == "high"


# ============================================================================
# Test Suite 8: Timeout Validation (4 tests) - Lines 216-233
# ============================================================================


class TestValidateTimeout:
    """Test timeout validation method - Lines 216-233."""

    @pytest.mark.unit
    def test_timeout_valid_value(self):
        """Test timeout with valid value."""
        # Act
        result = ValidationEngine.timeout(30)

        # Assert
        assert result == 30

    @pytest.mark.unit
    def test_timeout_below_min_raises(self):
        """Test timeout raises ValidationError below minimum."""
        # Act & Assert
        with pytest.raises(ValidationError, match="must be at least"):
            ValidationEngine.timeout(0)

    @pytest.mark.unit
    def test_timeout_above_max_raises(self):
        """Test timeout raises ValidationError above maximum."""
        # Act & Assert
        with pytest.raises(ValidationError, match="cannot exceed"):
            ValidationEngine.timeout(4000)

    @pytest.mark.unit
    def test_timeout_custom_limits(self):
        """Test timeout with custom min/max limits."""
        # Act
        result = ValidationEngine.timeout(50, min_timeout=10, max_timeout=100)

        # Assert
        assert result == 50


# ============================================================================
# Test Suite 9: OAuth Provider Validation (4 tests) - Lines 235-251
# ============================================================================


class TestValidateOAuthProvider:
    """Test oauth_provider validation method - Lines 235-251."""

    @pytest.mark.unit
    def test_oauth_provider_valid_values(self):
        """Test oauth_provider accepts all valid providers."""
        # Arrange
        valid_providers = ["google", "github", "microsoft", "facebook", "apple"]

        # Act & Assert
        for provider in valid_providers:
            result = ValidationEngine.oauth_provider(provider)
            assert result == provider

    @pytest.mark.unit
    def test_oauth_provider_empty_raises(self):
        """Test oauth_provider raises ValidationError for empty string."""
        # Act & Assert
        with pytest.raises(ValidationError, match="provider cannot be empty"):
            ValidationEngine.oauth_provider("")

    @pytest.mark.unit
    def test_oauth_provider_invalid_raises(self):
        """Test oauth_provider raises ValidationError for invalid provider."""
        # Act & Assert
        with pytest.raises(ValidationError, match="must be one of"):
            ValidationEngine.oauth_provider("twitter")

    @pytest.mark.unit
    def test_oauth_provider_case_insensitive(self):
        """Test oauth_provider normalizes to lowercase."""
        # Act
        result = ValidationEngine.oauth_provider("GOOGLE")

        # Assert
        assert result == "google"


# ============================================================================
# Test Suite 10: OAuth Code Validation (4 tests) - Lines 253-268
# ============================================================================


class TestValidateOAuthCode:
    """Test oauth_code validation method - Lines 253-268."""

    @pytest.mark.unit
    def test_oauth_code_valid(self):
        """Test oauth_code with valid code."""
        # Arrange
        code = "authorization_code_12345"

        # Act
        result = ValidationEngine.oauth_code(code)

        # Assert
        assert result == code

    @pytest.mark.unit
    def test_oauth_code_empty_raises(self):
        """Test oauth_code raises ValidationError for empty string."""
        # Act & Assert
        with pytest.raises(ValidationError, match="code cannot be empty"):
            ValidationEngine.oauth_code("")

    @pytest.mark.unit
    def test_oauth_code_too_short_raises(self):
        """Test oauth_code raises ValidationError for short code."""
        # Act & Assert
        with pytest.raises(ValidationError, match="too short"):
            ValidationEngine.oauth_code("short")

    @pytest.mark.unit
    def test_oauth_code_too_long_raises(self):
        """Test oauth_code raises ValidationError for very long code."""
        # Arrange
        long_code = "a" * 1001

        # Act & Assert
        with pytest.raises(ValidationError, match="too long"):
            ValidationEngine.oauth_code(long_code)


# ============================================================================
# Test Suite 11: OAuth State Validation (4 tests) - Lines 270-287
# ============================================================================


class TestValidateOAuthState:
    """Test oauth_state validation method - Lines 270-287."""

    @pytest.mark.unit
    def test_oauth_state_valid(self):
        """Test oauth_state with valid state."""
        # Arrange
        state = "secure_random_state_12345"

        # Act
        result = ValidationEngine.oauth_state(state)

        # Assert
        assert result == state

    @pytest.mark.unit
    def test_oauth_state_empty_raises(self):
        """Test oauth_state raises ValidationError for empty string."""
        # Act & Assert
        with pytest.raises(ValidationError, match="state cannot be empty"):
            ValidationEngine.oauth_state("")

    @pytest.mark.unit
    def test_oauth_state_too_short_raises(self):
        """Test oauth_state raises ValidationError for short state."""
        # Act & Assert
        with pytest.raises(ValidationError, match="too short for security"):
            ValidationEngine.oauth_state("short")

    @pytest.mark.unit
    def test_oauth_state_too_long_raises(self):
        """Test oauth_state raises ValidationError for very long state."""
        # Arrange
        long_state = "a" * 201

        # Act & Assert
        with pytest.raises(ValidationError, match="too long"):
            ValidationEngine.oauth_state(long_state)


# ============================================================================
# Test Suite 12: Description Validation (4 tests) - Lines 289-307
# ============================================================================


class TestValidateDescription:
    """Test description validation method - Lines 289-307."""

    @pytest.mark.unit
    def test_description_valid(self):
        """Test description with valid text."""
        # Arrange
        desc = "This is a valid description"

        # Act
        result = ValidationEngine.description(desc)

        # Assert
        assert result == desc

    @pytest.mark.unit
    def test_description_none_returns_none(self):
        """Test description returns None for None input."""
        # Act
        result = ValidationEngine.description(None)

        # Assert
        assert result is None

    @pytest.mark.unit
    def test_description_empty_returns_none(self):
        """Test description returns None for empty string."""
        # Act
        result = ValidationEngine.description("   ")

        # Assert
        assert result is None

    @pytest.mark.unit
    def test_description_too_long_raises(self):
        """Test description raises ValidationError when too long."""
        # Arrange
        long_desc = "a" * (MAX_DESCRIPTION_LENGTH + 1)

        # Act & Assert
        with pytest.raises(ValidationError, match="too long"):
            ValidationEngine.description(long_desc)


# ============================================================================
# Test Suite 13: Filename Validation (5 tests) - Lines 309-331
# ============================================================================


class TestValidateFilename:
    """Test filename validation method - Lines 309-331."""

    @pytest.mark.unit
    def test_filename_valid(self):
        """Test filename with valid name."""
        # Arrange
        filename = "document.pdf"

        # Act
        result = ValidationEngine.filename(filename)

        # Assert
        assert result == filename

    @pytest.mark.unit
    def test_filename_empty_raises(self):
        """Test filename raises ValidationError for empty string."""
        # Act & Assert
        with pytest.raises(ValidationError, match="filename cannot be empty"):
            ValidationEngine.filename("")

    @pytest.mark.unit
    def test_filename_too_long_raises(self):
        """Test filename raises ValidationError when too long."""
        # Arrange
        long_filename = "a" * (MAX_FILENAME_LENGTH + 1) + ".txt"

        # Act & Assert
        with pytest.raises(ValidationError, match="too long"):
            ValidationEngine.filename(long_filename)

    @pytest.mark.unit
    def test_filename_dangerous_characters_raises(self):
        """Test filename raises ValidationError for dangerous characters."""
        # Arrange
        dangerous_filenames = [
            "../file.txt",
            "file/path.txt",
            "file<script>.txt",
            'file"name.txt',
            "file|pipe.txt",
        ]

        # Act & Assert
        for filename in dangerous_filenames:
            with pytest.raises(ValidationError, match="invalid characters"):
                ValidationEngine.filename(filename)

    @pytest.mark.unit
    def test_filename_safe_characters(self):
        """Test filename allows safe characters."""
        # Arrange
        safe_filename = "my_document-v2.pdf"

        # Act
        result = ValidationEngine.filename(safe_filename)

        # Assert
        assert result == safe_filename


# ============================================================================
# Test Suite 14: Datetime Range Validation (3 tests) - Lines 333-348
# ============================================================================


class TestValidateDatetimeRange:
    """Test datetime_range validation method - Lines 333-348."""

    @pytest.mark.unit
    def test_datetime_range_valid(self):
        """Test datetime_range with valid start before end."""
        # Arrange
        start = datetime.now()
        end = start + timedelta(days=1)

        # Act
        result_start, result_end = ValidationEngine.datetime_range(start, end)

        # Assert
        assert result_start == start
        assert result_end == end

    @pytest.mark.unit
    def test_datetime_range_none_values(self):
        """Test datetime_range accepts None values."""
        # Act
        result_start, result_end = ValidationEngine.datetime_range(None, None)

        # Assert
        assert result_start is None
        assert result_end is None

    @pytest.mark.unit
    def test_datetime_range_start_after_end_raises(self):
        """Test datetime_range raises ValidationError when start >= end."""
        # Arrange
        start = datetime.now()
        end = start - timedelta(days=1)

        # Act & Assert
        with pytest.raises(ValidationError, match="Start datetime must be before end"):
            ValidationEngine.datetime_range(start, end)


# ============================================================================
# Test Suite 15: JSON Data Validation (4 tests) - Lines 350-373
# ============================================================================


class TestValidateJsonData:
    """Test json_data validation method - Lines 350-373."""

    @pytest.mark.unit
    def test_json_data_valid_dict(self):
        """Test json_data with valid dictionary."""
        # Arrange
        data = {"key": "value", "nested": {"data": [1, 2, 3]}}

        # Act
        result = ValidationEngine.json_data(data)

        # Assert
        assert result == data

    @pytest.mark.unit
    def test_json_data_valid_list(self):
        """Test json_data with valid list."""
        # Arrange
        data = [1, 2, {"key": "value"}]

        # Act
        result = ValidationEngine.json_data(data)

        # Assert
        assert result == data

    @pytest.mark.unit
    def test_json_data_none_returns_none(self):
        """Test json_data returns None for None input."""
        # Act
        result = ValidationEngine.json_data(None)

        # Assert
        assert result is None

    @pytest.mark.unit
    def test_json_data_too_deep_raises(self):
        """Test json_data raises ValidationError for excessive nesting."""
        # Arrange - Create deeply nested structure
        data = {"level": 1}
        current = data
        for i in range(2, 15):  # Create 14 levels of nesting
            current["nested"] = {"level": i}
            current = current["nested"]

        # Act & Assert
        with pytest.raises(ValidationError, match="nesting too deep"):
            ValidationEngine.json_data(data, max_depth=10)


# ============================================================================
# Test Suite 16: Bulk User IDs Validation (4 tests) - Lines 379-393
# ============================================================================


class TestValidateBulkUserIds:
    """Test validate_user_ids bulk validation - Lines 379-393."""

    @pytest.mark.unit
    def test_bulk_user_ids_valid(self):
        """Test validate_user_ids with valid UUID list."""
        # Arrange
        user_ids = [str(uuid4()) for _ in range(5)]

        # Act
        result = BulkValidator.validate_user_ids(user_ids)

        # Assert
        assert result == user_ids
        assert len(result) == 5

    @pytest.mark.unit
    def test_bulk_user_ids_empty_list_raises(self):
        """Test validate_user_ids raises ValidationError for empty list."""
        # Act & Assert
        with pytest.raises(ValidationError, match="cannot be empty"):
            BulkValidator.validate_user_ids([])

    @pytest.mark.unit
    def test_bulk_user_ids_too_many_raises(self):
        """Test validate_user_ids raises ValidationError for too many IDs."""
        # Arrange
        user_ids = [str(uuid4()) for _ in range(101)]

        # Act & Assert
        with pytest.raises(ValidationError, match="Too many user IDs"):
            BulkValidator.validate_user_ids(user_ids)

    @pytest.mark.unit
    def test_bulk_user_ids_invalid_id_raises(self):
        """Test validate_user_ids raises ValidationError for invalid UUID."""
        # Arrange
        user_ids = [str(uuid4()), "invalid-uuid", str(uuid4())]

        # Act & Assert
        with pytest.raises(ValidationError, match="must be a valid UUID"):
            BulkValidator.validate_user_ids(user_ids)


# ============================================================================
# Test Suite 17: Bulk URLs Validation (4 tests) - Lines 395-409
# ============================================================================


class TestValidateBulkUrls:
    """Test validate_urls bulk validation - Lines 395-409."""

    @pytest.mark.unit
    def test_bulk_urls_valid(self):
        """Test validate_urls with valid URL list."""
        # Arrange
        urls = [
            "https://example.com/page1",
            "https://example.com/page2",
            "https://example.com/page3",
        ]

        # Act
        result = BulkValidator.validate_urls(urls)

        # Assert
        assert result == urls
        assert len(result) == 3

    @pytest.mark.unit
    def test_bulk_urls_empty_list_raises(self):
        """Test validate_urls raises ValidationError for empty list."""
        # Act & Assert
        with pytest.raises(ValidationError, match="cannot be empty"):
            BulkValidator.validate_urls([])

    @pytest.mark.unit
    def test_bulk_urls_too_many_raises(self):
        """Test validate_urls raises ValidationError for too many URLs."""
        # Arrange
        urls = [f"https://example.com/page{i}" for i in range(51)]

        # Act & Assert
        with pytest.raises(ValidationError, match="Too many URLs"):
            BulkValidator.validate_urls(urls)

    @pytest.mark.unit
    def test_bulk_urls_invalid_url_raises(self):
        """Test validate_urls raises ValidationError for invalid URL."""
        # Arrange
        urls = ["https://example.com/valid", "not-a-url", "https://example.com/valid2"]

        # Act & Assert
        with pytest.raises(ValidationError, match="must be a valid URL"):
            BulkValidator.validate_urls(urls)
