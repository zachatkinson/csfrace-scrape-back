"""OAuth token revocation service with provider-specific implementations.

This module provides abstract interfaces and a registry pattern for OAuth token
revocation across multiple providers. Follows SOLID principles:

- Single Responsibility: Each revoker handles one provider's revocation logic
- Open/Closed: New providers can be added without modifying existing code
- Liskov Substitution: All revokers implement the same interface
- Interface Segregation: Clean, focused interface for token revocation
- Dependency Inversion: Depends on abstractions (OAuthTokenRevoker), not concrete implementations

Supports graceful degradation if revocation fails (tokens expire naturally).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, ClassVar

from src.core.logging_hierarchy import get_auth_logger

if TYPE_CHECKING:
    from .models import OAuthProvider

logger = get_auth_logger(__name__)


class OAuthRevocationError(Exception):
    """Base exception for OAuth revocation errors."""

    pass


class ProviderNotRegisteredError(OAuthRevocationError):
    """Raised when attempting to revoke tokens for unregistered provider."""

    pass


class TokenRevocationFailedError(OAuthRevocationError):
    """Raised when token revocation fails at the provider."""

    pass


class OAuthTokenRevoker(ABC):
    """Abstract base class for OAuth token revocation.

    Each OAuth provider should implement this interface to handle
    provider-specific token revocation logic. Supports graceful
    degradation if revocation fails (tokens expire naturally).

    Implementation Guidelines:
    - Return True if revocation succeeds
    - Return False if revocation fails but is non-critical
    - Raise TokenRevocationFailedError for critical failures
    - Log all revocation attempts for security auditing
    """

    @abstractmethod
    async def revoke_access_token(self, access_token: str) -> bool:
        """Revoke an OAuth access token with the provider.

        This method should make an HTTP request to the provider's
        revocation endpoint to invalidate the access token.

        Args:
            access_token: The access token to revoke

        Returns:
            True if successfully revoked, False if revocation failed
            but is non-critical (token will expire naturally)

        Raises:
            TokenRevocationFailedError: If revocation is critical and failed

        Example:
            >>> revoker = GoogleTokenRevoker()
            >>> success = await revoker.revoke_access_token("ya29.a0...")
            >>> if success:
            ...     print("Token revoked successfully")
        """
        pass

    @abstractmethod
    async def revoke_all_tokens(self, user_id: str, access_token: str) -> bool:
        """Revoke all tokens/permissions for a user.

        This should revoke all access granted to the application for
        the specified user, including refresh tokens and persistent grants.

        Args:
            user_id: The user ID (provider-specific format)
            access_token: Access token for authentication with provider

        Returns:
            True if successfully revoked all tokens, False otherwise

        Raises:
            TokenRevocationFailedError: If revocation is critical and failed

        Example:
            >>> revoker = GoogleTokenRevoker()
            >>> success = await revoker.revoke_all_tokens("user123", "ya29.a0...")
            >>> if success:
            ...     print("All tokens revoked for user")
        """
        pass

    def supports_refresh_token_revocation(self) -> bool:
        """Check if provider supports refresh token revocation.

        Some providers (like Google) allow revoking refresh tokens directly,
        while others only support access token revocation.

        Returns:
            True if provider supports refresh token revocation, False otherwise

        Example:
            >>> revoker = GoogleTokenRevoker()
            >>> if revoker.supports_refresh_token_revocation():
            ...     await revoker.revoke_refresh_token(refresh_token)
        """
        return False  # Default implementation - override if supported

    async def revoke_refresh_token(self, refresh_token: str) -> bool:
        """Revoke a refresh token (optional, provider-dependent).

        Override this method if the provider supports refresh token revocation.
        Check supports_refresh_token_revocation() before calling.

        Args:
            refresh_token: The refresh token to revoke

        Returns:
            True if successfully revoked, False otherwise

        Raises:
            NotImplementedError: If provider doesn't support refresh token revocation

        Example:
            >>> revoker = GoogleTokenRevoker()
            >>> if revoker.supports_refresh_token_revocation():
            ...     await revoker.revoke_refresh_token("1//0abc...")
        """
        logger.warning(f"{self.__class__.__name__} does not support refresh token revocation")
        raise NotImplementedError(
            f"{self.__class__.__name__} does not support refresh token revocation"
        )


class OAuthRevocationRegistry:
    """Registry for OAuth token revokers - SOLID Open/Closed Principle.

    This registry allows new providers to be registered without modifying
    existing code. Uses Factory Method pattern for revoker instantiation.

    Thread-safe singleton registry for managing OAuth token revokers across
    all supported providers.

    Example:
        >>> # Register a new provider
        >>> registry = OAuthRevocationRegistry()
        >>> registry.register_revoker(OAuthProvider.GOOGLE, GoogleTokenRevoker())
        >>>
        >>> # Get a revoker
        >>> revoker = registry.get_revoker(OAuthProvider.GOOGLE)
        >>> await revoker.revoke_access_token(token)
    """

    # Class-level registry shared across all instances
    _revokers: ClassVar[dict[OAuthProvider, OAuthTokenRevoker]] = {}

    @classmethod
    def register_revoker(
        cls,
        provider: OAuthProvider,
        revoker: OAuthTokenRevoker,
    ) -> None:
        """Register an OAuth token revoker for a provider.

        Args:
            provider: The OAuth provider (e.g., OAuthProvider.GOOGLE)
            revoker: The token revoker instance implementing OAuthTokenRevoker

        Example:
            >>> OAuthRevocationRegistry.register_revoker(
            ...     OAuthProvider.GOOGLE,
            ...     GoogleTokenRevoker()
            ... )
        """
        if provider in cls._revokers:
            logger.warning(
                f"Overriding existing revoker for provider: {provider.value}",
                provider=provider.value,
                old_revoker=cls._revokers[provider].__class__.__name__,
                new_revoker=revoker.__class__.__name__,
            )

        cls._revokers[provider] = revoker
        logger.info(
            f"Registered token revoker for provider: {provider.value}",
            provider=provider.value,
            revoker_class=revoker.__class__.__name__,
        )

    @classmethod
    def get_revoker(cls, provider: OAuthProvider) -> OAuthTokenRevoker:
        """Get registered revoker for a provider.

        Args:
            provider: The OAuth provider to get revoker for

        Returns:
            The registered OAuthTokenRevoker instance

        Raises:
            ProviderNotRegisteredError: If no revoker is registered for provider

        Example:
            >>> revoker = OAuthRevocationRegistry.get_revoker(OAuthProvider.GOOGLE)
            >>> await revoker.revoke_access_token(token)
        """
        if provider not in cls._revokers:
            logger.error(
                f"No revoker registered for provider: {provider.value}",
                provider=provider.value,
                available_providers=[p.value for p in cls._revokers],
            )
            raise ProviderNotRegisteredError(
                f"No token revoker registered for provider: {provider.value}. "
                f"Available providers: {[p.value for p in cls._revokers]}"
            )

        revoker = cls._revokers[provider]
        logger.debug(
            f"Retrieved revoker for provider: {provider.value}",
            provider=provider.value,
            revoker_class=revoker.__class__.__name__,
        )

        return revoker

    @classmethod
    def is_registered(cls, provider: OAuthProvider) -> bool:
        """Check if a provider has a registered revoker.

        Args:
            provider: The OAuth provider to check

        Returns:
            True if revoker is registered, False otherwise

        Example:
            >>> if OAuthRevocationRegistry.is_registered(OAuthProvider.GOOGLE):
            ...     revoker = OAuthRevocationRegistry.get_revoker(OAuthProvider.GOOGLE)
        """
        is_registered = provider in cls._revokers

        logger.debug(
            f"Checked registration for provider: {provider.value}",
            provider=provider.value,
            is_registered=is_registered,
        )

        return is_registered

    @classmethod
    def unregister_revoker(cls, provider: OAuthProvider) -> None:
        """Unregister a token revoker for a provider.

        Useful for testing or dynamic provider management.

        Args:
            provider: The OAuth provider to unregister

        Example:
            >>> OAuthRevocationRegistry.unregister_revoker(OAuthProvider.GOOGLE)
        """
        if provider in cls._revokers:
            revoker_class = cls._revokers[provider].__class__.__name__
            del cls._revokers[provider]
            logger.info(
                f"Unregistered token revoker for provider: {provider.value}",
                provider=provider.value,
                revoker_class=revoker_class,
            )
        else:
            logger.warning(
                f"Attempted to unregister non-existent revoker: {provider.value}",
                provider=provider.value,
            )

    @classmethod
    def get_registered_providers(cls) -> list[OAuthProvider]:
        """Get list of all registered providers.

        Returns:
            List of registered OAuth providers

        Example:
            >>> providers = OAuthRevocationRegistry.get_registered_providers()
            >>> print(f"Supported providers: {[p.value for p in providers]}")
        """
        providers = list(cls._revokers.keys())

        logger.debug(
            "Retrieved registered providers",
            count=len(providers),
            providers=[p.value for p in providers],
        )

        return providers

    @classmethod
    def clear_all(cls) -> None:
        """Clear all registered revokers.

        WARNING: This should only be used in testing environments.
        Production code should never clear the registry.

        Example:
            >>> # In tests
            >>> OAuthRevocationRegistry.clear_all()
            >>> # Register test revokers
        """
        count = len(cls._revokers)
        cls._revokers.clear()

        logger.warning(
            "Cleared all registered token revokers",
            count=count,
            message="This should only be used in testing",
        )
