"""Unit tests for environment following TEST_BUILDING.md MANDATORY standards.

MANDATORY COMPLIANCE:
- AAA Pattern (Arrange-Act-Assert) - NON-NEGOTIABLE
- SOLID principles testing
- Factory Pattern for test data
- 85%+ coverage target
- Focus on environment variable validation

Tests EnvironmentLoader and EnvironmentValidator classes.
"""

import os

import pytest

from src.core.environment import EnvironmentLoader, EnvironmentValidator

# ============================================================================
# MANDATORY Fixtures Following TEST_BUILDING.md Factory Pattern
# ============================================================================


@pytest.fixture
def clean_environment(monkeypatch):
    """Factory for clean environment - DRY principle."""
    # Clear all environment variables for isolation
    for key in list(os.environ.keys()):
        if key.startswith("TEST_"):
            monkeypatch.delenv(key, raising=False)
    return monkeypatch


# ============================================================================
# Test Suite 1: EnvironmentLoader.get_required (6 tests) - Lines 14-33
# ============================================================================


class TestGetRequired:
    """Test get_required method - Lines 14-33."""

    @pytest.mark.unit
    def test_get_required_returns_value(self, clean_environment):
        """Test get_required returns value when variable is set."""
        # Arrange
        clean_environment.setenv("TEST_REQUIRED_VAR", "test_value")

        # Act
        result = EnvironmentLoader.get_required("TEST_REQUIRED_VAR")

        # Assert
        assert result == "test_value"

    @pytest.mark.unit
    def test_get_required_strips_whitespace(self, clean_environment):
        """Test get_required strips surrounding whitespace."""
        # Arrange
        clean_environment.setenv("TEST_REQUIRED_VAR", "  test_value  ")

        # Act
        result = EnvironmentLoader.get_required("TEST_REQUIRED_VAR")

        # Assert
        assert result == "test_value"

    @pytest.mark.unit
    def test_get_required_raises_when_not_set(self, clean_environment):
        """Test get_required raises ValueError when variable not set."""
        # Act & Assert
        with pytest.raises(
            ValueError, match="Required environment variable 'TEST_MISSING' not set"
        ):
            EnvironmentLoader.get_required("TEST_MISSING")

    @pytest.mark.unit
    def test_get_required_raises_when_empty(self, clean_environment):
        """Test get_required raises ValueError when variable is empty string."""
        # Arrange
        clean_environment.setenv("TEST_EMPTY_VAR", "")

        # Act & Assert
        with pytest.raises(
            ValueError, match="Required environment variable 'TEST_EMPTY_VAR' not set"
        ):
            EnvironmentLoader.get_required("TEST_EMPTY_VAR")

    @pytest.mark.unit
    def test_get_required_raises_when_whitespace_only(self, clean_environment):
        """Test get_required raises ValueError when variable is whitespace only."""
        # Arrange
        clean_environment.setenv("TEST_WHITESPACE_VAR", "   ")

        # Act & Assert
        with pytest.raises(
            ValueError, match="Required environment variable 'TEST_WHITESPACE_VAR' not set"
        ):
            EnvironmentLoader.get_required("TEST_WHITESPACE_VAR")

    @pytest.mark.unit
    def test_get_required_includes_description_in_error(self, clean_environment):
        """Test get_required includes description in error message."""
        # Act & Assert
        with pytest.raises(ValueError, match="Database connection string"):
            EnvironmentLoader.get_required("TEST_DB_URL", description="Database connection string")


# ============================================================================
# Test Suite 2: EnvironmentLoader.get_optional (4 tests) - Lines 36-47
# ============================================================================


class TestGetOptional:
    """Test get_optional method - Lines 36-47."""

    @pytest.mark.unit
    def test_get_optional_returns_value(self, clean_environment):
        """Test get_optional returns value when variable is set."""
        # Arrange
        clean_environment.setenv("TEST_OPTIONAL_VAR", "optional_value")

        # Act
        result = EnvironmentLoader.get_optional("TEST_OPTIONAL_VAR")

        # Assert
        assert result == "optional_value"

    @pytest.mark.unit
    def test_get_optional_returns_default_when_not_set(self, clean_environment):
        """Test get_optional returns default when variable not set."""
        # Act
        result = EnvironmentLoader.get_optional("TEST_MISSING_OPTIONAL", default="default_value")

        # Assert
        assert result == "default_value"

    @pytest.mark.unit
    def test_get_optional_returns_empty_string_by_default(self, clean_environment):
        """Test get_optional returns empty string when no default provided."""
        # Act
        result = EnvironmentLoader.get_optional("TEST_MISSING_OPTIONAL")

        # Assert
        assert result == ""

    @pytest.mark.unit
    def test_get_optional_strips_whitespace(self, clean_environment):
        """Test get_optional strips surrounding whitespace."""
        # Arrange
        clean_environment.setenv("TEST_OPTIONAL_VAR", "  optional  ")

        # Act
        result = EnvironmentLoader.get_optional("TEST_OPTIONAL_VAR")

        # Assert
        assert result == "optional"


# ============================================================================
# Test Suite 3: EnvironmentLoader.get_int (8 tests) - Lines 50-80
# ============================================================================


class TestGetInt:
    """Test get_int method - Lines 50-80."""

    @pytest.mark.unit
    def test_get_int_returns_value(self, clean_environment):
        """Test get_int returns integer value."""
        # Arrange
        clean_environment.setenv("TEST_INT_VAR", "42")

        # Act
        result = EnvironmentLoader.get_int("TEST_INT_VAR", default=0)

        # Assert
        assert result == 42
        assert isinstance(result, int)

    @pytest.mark.unit
    def test_get_int_returns_default_when_not_set(self, clean_environment):
        """Test get_int returns default when variable not set."""
        # Act
        result = EnvironmentLoader.get_int("TEST_MISSING_INT", default=10)

        # Assert
        assert result == 10

    @pytest.mark.unit
    def test_get_int_raises_on_invalid_format(self, clean_environment):
        """Test get_int raises ValueError for non-integer value."""
        # Arrange
        clean_environment.setenv("TEST_INVALID_INT", "not_a_number")

        # Act & Assert
        with pytest.raises(ValueError, match="must be an integer"):
            EnvironmentLoader.get_int("TEST_INVALID_INT", default=0)

    @pytest.mark.unit
    def test_get_int_validates_min_value(self, clean_environment):
        """Test get_int validates minimum value."""
        # Arrange
        clean_environment.setenv("TEST_INT_VAR", "5")

        # Act & Assert
        with pytest.raises(ValueError, match="must be >= 10"):
            EnvironmentLoader.get_int("TEST_INT_VAR", default=0, min_value=10)

    @pytest.mark.unit
    def test_get_int_validates_max_value(self, clean_environment):
        """Test get_int validates maximum value."""
        # Arrange
        clean_environment.setenv("TEST_INT_VAR", "100")

        # Act & Assert
        with pytest.raises(ValueError, match="must be <= 50"):
            EnvironmentLoader.get_int("TEST_INT_VAR", default=0, max_value=50)

    @pytest.mark.unit
    def test_get_int_accepts_value_in_range(self, clean_environment):
        """Test get_int accepts value within min/max range."""
        # Arrange
        clean_environment.setenv("TEST_INT_VAR", "25")

        # Act
        result = EnvironmentLoader.get_int("TEST_INT_VAR", default=0, min_value=10, max_value=50)

        # Assert
        assert result == 25

    @pytest.mark.unit
    def test_get_int_accepts_value_at_min_boundary(self, clean_environment):
        """Test get_int accepts value at minimum boundary."""
        # Arrange
        clean_environment.setenv("TEST_INT_VAR", "10")

        # Act
        result = EnvironmentLoader.get_int("TEST_INT_VAR", default=0, min_value=10)

        # Assert
        assert result == 10

    @pytest.mark.unit
    def test_get_int_accepts_value_at_max_boundary(self, clean_environment):
        """Test get_int accepts value at maximum boundary."""
        # Arrange
        clean_environment.setenv("TEST_INT_VAR", "50")

        # Act
        result = EnvironmentLoader.get_int("TEST_INT_VAR", default=0, max_value=50)

        # Assert
        assert result == 50


# ============================================================================
# Test Suite 4: EnvironmentLoader.get_bool (6 tests) - Lines 83-94
# ============================================================================


class TestGetBool:
    """Test get_bool method - Lines 83-94."""

    @pytest.mark.unit
    def test_get_bool_returns_true_for_true_string(self, clean_environment):
        """Test get_bool returns True for 'true' string."""
        # Arrange
        clean_environment.setenv("TEST_BOOL_VAR", "true")

        # Act
        result = EnvironmentLoader.get_bool("TEST_BOOL_VAR")

        # Assert
        assert result is True

    @pytest.mark.unit
    def test_get_bool_returns_true_for_one(self, clean_environment):
        """Test get_bool returns True for '1' string."""
        # Arrange
        clean_environment.setenv("TEST_BOOL_VAR", "1")

        # Act
        result = EnvironmentLoader.get_bool("TEST_BOOL_VAR")

        # Assert
        assert result is True

    @pytest.mark.unit
    def test_get_bool_returns_true_for_yes(self, clean_environment):
        """Test get_bool returns True for 'yes' string."""
        # Arrange
        clean_environment.setenv("TEST_BOOL_VAR", "yes")

        # Act
        result = EnvironmentLoader.get_bool("TEST_BOOL_VAR")

        # Assert
        assert result is True

    @pytest.mark.unit
    def test_get_bool_returns_true_for_on(self, clean_environment):
        """Test get_bool returns True for 'on' string."""
        # Arrange
        clean_environment.setenv("TEST_BOOL_VAR", "on")

        # Act
        result = EnvironmentLoader.get_bool("TEST_BOOL_VAR")

        # Assert
        assert result is True

    @pytest.mark.unit
    def test_get_bool_returns_false_for_false_string(self, clean_environment):
        """Test get_bool returns False for 'false' string."""
        # Arrange
        clean_environment.setenv("TEST_BOOL_VAR", "false")

        # Act
        result = EnvironmentLoader.get_bool("TEST_BOOL_VAR")

        # Assert
        assert result is False

    @pytest.mark.unit
    def test_get_bool_returns_default_when_not_set(self, clean_environment):
        """Test get_bool returns default when variable not set."""
        # Act
        result = EnvironmentLoader.get_bool("TEST_MISSING_BOOL", default=True)

        # Assert
        assert result is True


# ============================================================================
# Test Suite 5: EnvironmentLoader.get_url (6 tests) - Lines 97-119
# ============================================================================


class TestGetUrl:
    """Test get_url method - Lines 97-119."""

    @pytest.mark.unit
    def test_get_url_returns_http_url(self, clean_environment):
        """Test get_url returns HTTP URL."""
        # Arrange
        clean_environment.setenv("TEST_URL_VAR", "http://example.com")

        # Act
        result = EnvironmentLoader.get_url("TEST_URL_VAR")

        # Assert
        assert result == "http://example.com"

    @pytest.mark.unit
    def test_get_url_returns_https_url(self, clean_environment):
        """Test get_url returns HTTPS URL."""
        # Arrange
        clean_environment.setenv("TEST_URL_VAR", "https://example.com/path")

        # Act
        result = EnvironmentLoader.get_url("TEST_URL_VAR")

        # Assert
        assert result == "https://example.com/path"

    @pytest.mark.unit
    def test_get_url_returns_default_when_not_set(self, clean_environment):
        """Test get_url returns default when variable not set."""
        # Act
        result = EnvironmentLoader.get_url("TEST_MISSING_URL", default="http://default.com")

        # Assert
        assert result == "http://default.com"

    @pytest.mark.unit
    def test_get_url_raises_when_required_not_set(self, clean_environment):
        """Test get_url raises ValueError when required URL not set."""
        # Act & Assert
        with pytest.raises(ValueError, match="Required URL environment variable"):
            EnvironmentLoader.get_url("TEST_MISSING_URL", required=True)

    @pytest.mark.unit
    def test_get_url_raises_on_invalid_scheme(self, clean_environment):
        """Test get_url raises ValueError for invalid URL scheme."""
        # Arrange
        clean_environment.setenv("TEST_URL_VAR", "ftp://example.com")

        # Act & Assert
        with pytest.raises(ValueError, match="must be a valid URL"):
            EnvironmentLoader.get_url("TEST_URL_VAR")

    @pytest.mark.unit
    def test_get_url_raises_on_no_scheme(self, clean_environment):
        """Test get_url raises ValueError for URL without scheme."""
        # Arrange
        clean_environment.setenv("TEST_URL_VAR", "example.com")

        # Act & Assert
        with pytest.raises(ValueError, match="must be a valid URL"):
            EnvironmentLoader.get_url("TEST_URL_VAR")


# ============================================================================
# Test Suite 6: EnvironmentLoader.get_list (5 tests) - Lines 122-140
# ============================================================================


class TestGetList:
    """Test get_list method - Lines 122-140."""

    @pytest.mark.unit
    def test_get_list_returns_parsed_list(self, clean_environment):
        """Test get_list parses comma-separated values."""
        # Arrange
        clean_environment.setenv("TEST_LIST_VAR", "item1,item2,item3")

        # Act
        result = EnvironmentLoader.get_list("TEST_LIST_VAR")

        # Assert
        assert result == ["item1", "item2", "item3"]

    @pytest.mark.unit
    def test_get_list_strips_whitespace_from_items(self, clean_environment):
        """Test get_list strips whitespace from each item."""
        # Arrange
        clean_environment.setenv("TEST_LIST_VAR", " item1 , item2 , item3 ")

        # Act
        result = EnvironmentLoader.get_list("TEST_LIST_VAR")

        # Assert
        assert result == ["item1", "item2", "item3"]

    @pytest.mark.unit
    def test_get_list_returns_default_when_not_set(self, clean_environment):
        """Test get_list returns default when variable not set."""
        # Act
        result = EnvironmentLoader.get_list("TEST_MISSING_LIST", default=["default1", "default2"])

        # Assert
        assert result == ["default1", "default2"]

    @pytest.mark.unit
    def test_get_list_returns_empty_list_by_default(self, clean_environment):
        """Test get_list returns empty list when no default provided."""
        # Act
        result = EnvironmentLoader.get_list("TEST_MISSING_LIST")

        # Assert
        assert result == []

    @pytest.mark.unit
    def test_get_list_supports_custom_separator(self, clean_environment):
        """Test get_list supports custom separator."""
        # Arrange
        clean_environment.setenv("TEST_LIST_VAR", "item1;item2;item3")

        # Act
        result = EnvironmentLoader.get_list("TEST_LIST_VAR", separator=";")

        # Assert
        assert result == ["item1", "item2", "item3"]


# ============================================================================
# Test Suite 7: EnvironmentValidator.validate_required_vars (3 tests) - Lines 147-163
# ============================================================================


class TestValidateRequiredVars:
    """Test validate_required_vars method - Lines 147-163."""

    @pytest.mark.unit
    def test_validate_required_vars_returns_empty_when_all_set(self, clean_environment):
        """Test validate_required_vars returns empty list when all variables set."""
        # Arrange
        clean_environment.setenv("TEST_VAR1", "value1")
        clean_environment.setenv("TEST_VAR2", "value2")
        required_vars = {
            "TEST_VAR1": "First variable",
            "TEST_VAR2": "Second variable",
        }

        # Act
        result = EnvironmentValidator.validate_required_vars(required_vars)

        # Assert
        assert result == []

    @pytest.mark.unit
    def test_validate_required_vars_returns_missing_variables(self, clean_environment):
        """Test validate_required_vars returns list of missing variables."""
        # Arrange
        clean_environment.setenv("TEST_VAR1", "value1")
        required_vars = {
            "TEST_VAR1": "First variable",
            "TEST_MISSING_VAR": "Missing variable",
        }

        # Act
        result = EnvironmentValidator.validate_required_vars(required_vars)

        # Assert
        assert len(result) == 1
        assert "TEST_MISSING_VAR (Missing variable)" in result

    @pytest.mark.unit
    def test_validate_required_vars_includes_descriptions(self, clean_environment):
        """Test validate_required_vars includes descriptions in output."""
        # Arrange
        required_vars = {
            "TEST_MISSING1": "Database connection",
            "TEST_MISSING2": "API secret key",
        }

        # Act
        result = EnvironmentValidator.validate_required_vars(required_vars)

        # Assert
        assert len(result) == 2
        assert any("Database connection" in item for item in result)
        assert any("API secret key" in item for item in result)


# ============================================================================
# Test Suite 8: EnvironmentValidator.validate_startup_environment (2 tests) - Lines 166-183
# ============================================================================


class TestValidateStartupEnvironment:
    """Test validate_startup_environment method - Lines 166-183."""

    @pytest.mark.unit
    def test_validate_startup_environment_passes_when_vars_set(self, clean_environment):
        """Test validate_startup_environment passes when required variables set."""
        # Arrange
        clean_environment.setenv("SECRET_KEY", "test_secret_key")
        clean_environment.setenv("DATABASE_URL", "postgresql://localhost/test")

        # Act & Assert - should not raise
        EnvironmentValidator.validate_startup_environment()

    @pytest.mark.unit
    def test_validate_startup_environment_raises_when_vars_missing(self, clean_environment):
        """Test validate_startup_environment raises RuntimeError when variables missing."""
        # Arrange - ensure required vars are not set
        clean_environment.delenv("SECRET_KEY", raising=False)
        clean_environment.delenv("DATABASE_URL", raising=False)

        # Act & Assert
        with pytest.raises(RuntimeError, match="Missing required environment variables"):
            EnvironmentValidator.validate_startup_environment()
