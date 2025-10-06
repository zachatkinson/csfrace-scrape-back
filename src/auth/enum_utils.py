"""Enum handling utilities following SOLID and DRY principles.

This module provides centralized enum handling to prevent code duplication
and ensure consistent enum processing across the authentication system.
"""

from enum import Enum
from typing import TypeVar

from .models import OAuthProvider

# Generic type for enum handling - Interface Segregation Principle
T = TypeVar("T", bound=Enum)


class EnumHandler:
    """Centralized enum handling utility - Single Responsibility Principle.

    This class handles all enum-related operations to eliminate code duplication
    and provide a consistent interface for enum processing.
    """

    @staticmethod
    def ensure_enum(value: T | str, enum_class: type[T]) -> T:
        """Convert string or enum to proper enum instance - DRY principle.

        Args:
            value: String or enum value to convert
            enum_class: Target enum class

        Returns:
            Proper enum instance

        Raises:
            ValueError: If value cannot be converted to enum
        """
        if isinstance(value, enum_class):
            return value
        if isinstance(value, str):
            try:
                return enum_class(value)
            except ValueError as e:
                raise ValueError(f"Invalid {enum_class.__name__} value: {value}") from e
        raise ValueError(f"Cannot convert {type(value)} to {enum_class.__name__}")

    @staticmethod
    def get_enum_value(enum_or_string: T | str) -> str:
        """Safely get string value from enum or string - DRY principle.

        Args:
            enum_or_string: Enum instance or string value

        Returns:
            String representation of the enum value
        """
        if hasattr(enum_or_string, "value"):
            value_str: str = str(enum_or_string.value)
            return value_str
        return str(enum_or_string)

    @staticmethod
    def ensure_oauth_provider(value: OAuthProvider | str) -> OAuthProvider:
        """Specialized OAuth provider handling - Open/Closed Principle.

        Args:
            value: OAuth provider as enum or string

        Returns:
            OAuthProvider enum instance
        """
        return EnumHandler.ensure_enum(value, OAuthProvider)

    @staticmethod
    def get_oauth_provider_value(provider: OAuthProvider | str) -> str:
        """Safely get OAuth provider string value - DRY principle.

        Args:
            provider: OAuth provider enum or string

        Returns:
            String value of OAuth provider
        """
        return EnumHandler.get_enum_value(provider)


# Convenience functions following Liskov Substitution Principle
def ensure_oauth_provider(value: OAuthProvider | str) -> OAuthProvider:
    """Convenience function for OAuth provider handling."""
    return EnumHandler.ensure_oauth_provider(value)


def get_oauth_provider_value(provider: OAuthProvider | str) -> str:
    """Convenience function for OAuth provider value extraction."""
    return EnumHandler.get_oauth_provider_value(provider)
