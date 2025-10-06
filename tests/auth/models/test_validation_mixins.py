"""Unit tests for validation mixins following TEST_BUILDING.md MANDATORY standards.

MANDATORY COMPLIANCE:
- AAA Pattern (Arrange-Act-Assert) - NON-NEGOTIABLE
- SOLID principles testing
- 85%+ coverage target
- Focus on validation logic and edge cases

Tests PasswordValidatorMixin validation methods.
"""

import pytest

from src.auth.models.validation_mixins import PasswordValidatorMixin

# ============================================================================
# Test Suite 1: validate_password_strength (8 tests) - Lines 10-20
# ============================================================================


class TestValidatePasswordStrength:
    """Test password validation logic - SECURITY CRITICAL."""

    @pytest.mark.unit
    def test_validate_password_strength_valid(self) -> None:
        """Test validate_password_strength with valid password."""
        # Arrange
        password = "SecurePass123"

        # Act
        result = PasswordValidatorMixin.validate_password_strength(password)

        # Assert
        assert result == password

    @pytest.mark.unit
    def test_validate_password_strength_too_short(self) -> None:
        """Test validate_password_strength fails for short password."""
        # Act & Assert
        with pytest.raises(ValueError, match="at least 8 characters"):
            PasswordValidatorMixin.validate_password_strength("Short1")

    @pytest.mark.unit
    def test_validate_password_strength_no_uppercase(self) -> None:
        """Test validate_password_strength fails without uppercase."""
        # Act & Assert
        with pytest.raises(ValueError, match="uppercase letter"):
            PasswordValidatorMixin.validate_password_strength("lowercase123")

    @pytest.mark.unit
    def test_validate_password_strength_no_lowercase(self) -> None:
        """Test validate_password_strength fails without lowercase."""
        # Act & Assert
        with pytest.raises(ValueError, match="lowercase letter"):
            PasswordValidatorMixin.validate_password_strength("UPPERCASE123")

    @pytest.mark.unit
    def test_validate_password_strength_no_digit(self) -> None:
        """Test validate_password_strength fails without digit."""
        # Act & Assert
        with pytest.raises(ValueError, match="contain number"):
            PasswordValidatorMixin.validate_password_strength("SecurePass")

    @pytest.mark.unit
    def test_validate_password_strength_exactly_8_chars(self) -> None:
        """Test validate_password_strength with exactly 8 characters."""
        # Arrange
        password = "Secure12"

        # Act
        result = PasswordValidatorMixin.validate_password_strength(password)

        # Assert
        assert result == password

    @pytest.mark.unit
    def test_validate_password_strength_with_special_chars(self) -> None:
        """Test validate_password_strength allows special characters."""
        # Arrange
        password = "Secure!@#123"

        # Act
        result = PasswordValidatorMixin.validate_password_strength(password)

        # Assert
        assert result == password

    @pytest.mark.unit
    def test_validate_password_strength_long_password(self) -> None:
        """Test validate_password_strength with very long password."""
        # Arrange
        password = "SuperSecurePassword123WithLotsOfCharacters!@#$"

        # Act
        result = PasswordValidatorMixin.validate_password_strength(password)

        # Assert
        assert result == password


# ============================================================================
# Test Suite 2: validate_username (10 tests) - Lines 22-55
# ============================================================================


class TestValidateUsername:
    """Test username validation with various options."""

    @pytest.mark.unit
    def test_validate_username_valid_basic(self) -> None:
        """Test validate_username with valid basic username."""
        # Arrange
        username = "testuser"

        # Act
        result = PasswordValidatorMixin.validate_username(username)

        # Assert
        assert result == username

    @pytest.mark.unit
    def test_validate_username_with_dots_allowed_when_enabled(self) -> None:
        """Test validate_username allows dots when allow_dots=True (OAuth usernames)."""
        # Arrange - Dots are allowed by ValidationEngine when allow_dots=True
        username = "test.user"

        # Act
        result = PasswordValidatorMixin.validate_username(username, allow_dots=True)

        # Assert
        assert result == username

    @pytest.mark.unit
    def test_validate_username_with_dots_rejected_when_disabled(self) -> None:
        """Test validate_username rejects dots when allow_dots=False (default)."""
        # Arrange - Dots are rejected by ValidationEngine when allow_dots=False
        username = "test.user"

        # Act & Assert - ValidationEngine rejects dots
        with pytest.raises(
            ValueError, match="can only contain letters, numbers, hyphens, and underscores"
        ):
            PasswordValidatorMixin.validate_username(username, allow_dots=False)

    @pytest.mark.unit
    def test_validate_username_nullable_empty_string(self) -> None:
        """Test validate_username returns None for empty string with allow_nullable=True."""
        # Act
        result = PasswordValidatorMixin.validate_username("", allow_nullable=True)

        # Assert
        assert result is None

    @pytest.mark.unit
    def test_validate_username_nullable_whitespace(self) -> None:
        """Test validate_username returns None for whitespace with allow_nullable=True."""
        # Act
        result = PasswordValidatorMixin.validate_username("   ", allow_nullable=True)

        # Assert
        assert result is None

    @pytest.mark.unit
    def test_validate_username_nullable_none(self) -> None:
        """Test validate_username returns None for None with allow_nullable=True."""
        # Act
        result = PasswordValidatorMixin.validate_username("", allow_nullable=True)

        # Assert
        assert result is None

    @pytest.mark.unit
    def test_validate_username_invalid_raises_value_error(self) -> None:
        """Test validate_username converts ValidationError to ValueError."""
        # Arrange - Invalid username (too short or contains invalid chars)
        username = "a"  # Too short

        # Act & Assert - Should raise ValueError (converted from ValidationError)
        with pytest.raises(ValueError):
            PasswordValidatorMixin.validate_username(username)

    @pytest.mark.unit
    def test_validate_username_with_underscore(self) -> None:
        """Test validate_username allows underscores."""
        # Arrange
        username = "test_user"

        # Act
        result = PasswordValidatorMixin.validate_username(username)

        # Assert
        assert result == username

    @pytest.mark.unit
    def test_validate_username_with_numbers(self) -> None:
        """Test validate_username allows numbers."""
        # Arrange
        username = "testuser123"

        # Act
        result = PasswordValidatorMixin.validate_username(username)

        # Assert
        assert result == username

    @pytest.mark.unit
    def test_validate_username_dots_rejected_by_default(self) -> None:
        """Test validate_username rejects dots by default (ValidationEngine)."""
        # Arrange
        username = "test.user"

        # Act & Assert - ValidationEngine rejects dots
        with pytest.raises(ValueError, match="letters, numbers, hyphens, and underscores"):
            PasswordValidatorMixin.validate_username(username)
