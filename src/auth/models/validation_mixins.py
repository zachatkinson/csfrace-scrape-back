"""Validation mixins for DRY principle compliance."""

from src.core.validation import ValidationEngine


class PasswordValidatorMixin:
    """DRY principle: Shared password validation logic."""

    @staticmethod
    def validate_password_strength(password: str) -> str:
        """Centralized password validation to eliminate code duplication."""
        if len(password) < 8:
            raise ValueError("Password must be at least 8 characters")
        if not any(c.isupper() for c in password):
            raise ValueError("Password must contain uppercase letter")
        if not any(c.islower() for c in password):
            raise ValueError("Password must contain lowercase letter")
        if not any(c.isdigit() for c in password):
            raise ValueError("Password must contain number")
        return password

    @staticmethod
    def validate_username(
        username: str, allow_dots: bool = False, allow_nullable: bool = False
    ) -> str | None:
        """Use centralized validation - NO DUPLICATE LOGIC (ZERO TOLERANCE).

        Args:
            username: Username to validate
            allow_dots: Whether to allow dots in username (for OAuth)
            allow_nullable: Whether to allow None/empty values (for WebAuthn)

        Returns:
            Validated username or None if allow_nullable=True and input is empty

        Raises:
            ValueError: If username doesn't meet validation criteria
        """
        # Handle nullable case for WebAuthn
        if allow_nullable and (not username or not username.strip()):
            return None

        try:
            # Use centralized ValidationEngine with allow_dots parameter - ZERO TOLERANCE for duplication
            validated = ValidationEngine.username(username, allow_dots=allow_dots)
            return validated

        except Exception as e:
            # Convert ValidationError to ValueError for backward compatibility
            raise ValueError(str(e)) from e
