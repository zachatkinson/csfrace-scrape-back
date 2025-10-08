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

import json
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


# ==================== Provider-Specific Implementations ====================


class GoogleTokenRevoker(OAuthTokenRevoker):
    """Google OAuth token revocation implementation.

    Implements token revocation for Google OAuth2 following their official API:
    https://developers.google.com/identity/protocols/oauth2/web-server#tokenrevoke

    Google's revocation endpoint accepts both access tokens and refresh tokens.
    Revoking either token revokes all access granted to the application.

    Technical Details:
    - Endpoint: POST https://oauth2.googleapis.com/revoke
    - Parameter: token (access_token or refresh_token)
    - Content-Type: application/x-www-form-urlencoded
    - Success: HTTP 200 status code
    - Revoking any token invalidates ALL tokens for the application

    Example:
        >>> revoker = GoogleTokenRevoker()
        >>> success = await revoker.revoke_access_token("ya29.a0...")
        >>> if success:
        ...     logger.info("Token revoked successfully")

    Reference:
    https://developers.google.com/identity/protocols/oauth2/web-server#tokenrevoke
    """

    def __init__(self, http_timeout: int = 30) -> None:
        """Initialize Google token revoker with httpx client.

        Args:
            http_timeout: HTTP request timeout in seconds (default: 30)
        """
        import httpx

        from src.constants.auth import GOOGLE_REVOKE_URL

        self.revoke_url = GOOGLE_REVOKE_URL
        self.http_timeout = http_timeout
        self.httpx = httpx  # Store module for testing/mocking

        logger.info(
            "Initialized GoogleTokenRevoker",
            provider="google",
            revoke_url=self.revoke_url,
            timeout=http_timeout,
        )

    async def revoke_access_token(self, access_token: str) -> bool:
        """Revoke a Google OAuth access token.

        Makes a POST request to Google's revocation endpoint with the access token.
        Returns True on success (HTTP 200), False on non-critical failures.

        Args:
            access_token: The Google OAuth access token to revoke

        Returns:
            True if revocation succeeded, False if failed non-critically

        Raises:
            TokenRevocationFailedError: If access token is empty/invalid

        Example:
            >>> revoker = GoogleTokenRevoker()
            >>> success = await revoker.revoke_access_token("ya29.a0...")

        Note:
            Revoking an access token also revokes associated refresh tokens.
        """
        if not access_token or not access_token.strip():
            logger.error(
                "Attempted to revoke empty or invalid access token",
                provider="google",
                token_length=len(access_token) if access_token else 0,
            )
            raise TokenRevocationFailedError("Access token cannot be empty")

        logger.info(
            "Attempting to revoke Google access token",
            provider="google",
            token_prefix=access_token[:10] + "..." if len(access_token) > 10 else "***",
        )

        try:
            async with self.httpx.AsyncClient(timeout=self.http_timeout) as client:
                response = await client.post(
                    self.revoke_url,
                    data={"token": access_token},
                    headers={
                        "Content-Type": "application/x-www-form-urlencoded",
                    },
                )

                if response.status_code == 200:
                    logger.info(
                        "Successfully revoked Google access token",
                        provider="google",
                        status_code=response.status_code,
                    )
                    return True
                else:
                    logger.warning(
                        "Google token revocation returned non-200 status",
                        provider="google",
                        status_code=response.status_code,
                        response_text=response.text[:200] if response.text else "No response body",
                    )
                    # Non-critical failure - token may already be invalid or expired
                    return False

        except self.httpx.TimeoutException as e:
            logger.error(
                "Timeout while revoking Google access token",
                provider="google",
                error=str(e),
                timeout=self.http_timeout,
            )
            # Non-critical - token will expire naturally
            return False

        except self.httpx.HTTPError as e:
            logger.error(
                "HTTP error while revoking Google access token",
                provider="google",
                error=str(e),
                error_type=type(e).__name__,
            )
            # Non-critical - token will expire naturally
            return False

        except Exception as e:
            logger.error(
                "Unexpected error revoking Google access token",
                provider="google",
                error=str(e),
                error_type=type(e).__name__,
            )
            # Log but don't fail critically - graceful degradation
            return False

    async def revoke_all_tokens(self, user_id: str, access_token: str) -> bool:
        """Revoke all Google OAuth tokens for a user.

        Google's API automatically revokes all tokens (including refresh tokens)
        when any token is revoked. Therefore, this method simply calls
        revoke_access_token().

        Args:
            user_id: The user ID (not used by Google's API, included for interface)
            access_token: Access token for authentication with Google

        Returns:
            True if revocation succeeded, False otherwise

        Example:
            >>> revoker = GoogleTokenRevoker()
            >>> success = await revoker.revoke_all_tokens("user123", "ya29.a0...")

        Note:
            Google automatically revokes ALL tokens when one is revoked.
        """
        logger.info(
            "Revoking all Google tokens for user",
            provider="google",
            user_id=user_id,
        )

        # Google automatically revokes all tokens when one is revoked
        result = await self.revoke_access_token(access_token)

        if result:
            logger.info(
                "Successfully revoked all Google tokens for user",
                provider="google",
                user_id=user_id,
            )
        else:
            logger.warning(
                "Failed to revoke all Google tokens for user",
                provider="google",
                user_id=user_id,
            )

        return result

    def supports_refresh_token_revocation(self) -> bool:
        """Check if Google supports refresh token revocation.

        Google supports both access token and refresh token revocation
        via the same endpoint.

        Returns:
            True - Google supports refresh token revocation
        """
        return True

    async def revoke_refresh_token(self, refresh_token: str) -> bool:
        """Revoke a Google OAuth refresh token.

        Google uses the same endpoint for both access and refresh token revocation.
        Simply pass the refresh token instead of access token.

        Args:
            refresh_token: The Google OAuth refresh token to revoke

        Returns:
            True if revocation succeeded, False otherwise

        Example:
            >>> revoker = GoogleTokenRevoker()
            >>> success = await revoker.revoke_refresh_token("1//0abc...")

        Note:
            Revoking a refresh token also revokes associated access tokens.
        """
        logger.info(
            "Revoking Google refresh token",
            provider="google",
            token_prefix=refresh_token[:10] + "..." if len(refresh_token) > 10 else "***",
        )

        # Google uses same endpoint for refresh tokens
        return await self.revoke_access_token(refresh_token)


class FacebookTokenRevoker(OAuthTokenRevoker):
    """Facebook OAuth token revoker implementation.

    Facebook uses Graph API DELETE requests to /{user-id}/permissions
    to revoke access tokens and permissions. This completely de-authorizes
    the application and invalidates all tokens for the user.

    Facebook Documentation:
    https://developers.facebook.com/docs/facebook-login/guides/permissions/request-revoke

    Implementation follows SOLID principles:
    - Single Responsibility: Only handles Facebook token revocation
    - Open/Closed: Extends OAuthTokenRevoker without modifying it
    - Liskov Substitution: Can be used anywhere OAuthTokenRevoker is expected
    - Interface Segregation: Implements minimal required interface
    - Dependency Inversion: Depends on httpx abstraction, not concrete implementation
    """

    def __init__(self, api_base: str | None = None, timeout: float = 10.0):
        """Initialize Facebook token revoker.

        Args:
            api_base: Facebook Graph API base URL (defaults to constant)
            timeout: HTTP request timeout in seconds
        """
        from src.constants.auth import FACEBOOK_GRAPH_API_BASE

        self.api_base = api_base or FACEBOOK_GRAPH_API_BASE
        self.timeout = timeout

    async def revoke_access_token(self, access_token: str) -> bool:
        """Revoke a Facebook OAuth access token.

        Makes a DELETE request to /me/permissions with the access token
        to completely de-authorize the application.

        Args:
            access_token: The Facebook access token to revoke

        Returns:
            True if successfully revoked, False if revocation failed
            but is non-critical (token will expire naturally)

        Raises:
            TokenRevocationFailedError: If revocation is critical and failed

        Example:
            >>> revoker = FacebookTokenRevoker()
            >>> success = await revoker.revoke_access_token("EAABw...")
            >>> if success:
            ...     print("Token revoked successfully")
        """
        import httpx

        url = f"{self.api_base}/me/permissions"

        logger.info(
            "Revoking Facebook access token",
            url=url,
            action="revoke_access_token",
        )

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.delete(
                    url,
                    params={"access_token": access_token},
                )

                # Facebook returns 200 with {"success": true} on success
                if response.status_code == 200:
                    try:
                        data = response.json()
                        if data.get("success") is True:
                            logger.info(
                                "Successfully revoked Facebook access token",
                                action="revoke_access_token",
                                status="success",
                            )
                            return True
                    except Exception as e:
                        logger.warning(
                            "Failed to parse Facebook revocation response",
                            error=str(e),
                            response_text=response.text,
                            action="revoke_access_token",
                        )

                # Non-200 responses or invalid JSON - log but don't fail critically
                logger.warning(
                    "Facebook token revocation returned unexpected response",
                    status_code=response.status_code,
                    response_text=response.text,
                    action="revoke_access_token",
                )
                return False

        except httpx.TimeoutException as e:
            logger.error(
                "Timeout revoking Facebook access token",
                error=str(e),
                timeout=self.timeout,
                action="revoke_access_token",
            )
            return False

        except httpx.RequestError as e:
            logger.error(
                "Network error revoking Facebook access token",
                error=str(e),
                error_type=type(e).__name__,
                action="revoke_access_token",
            )
            return False

        except Exception as e:
            logger.error(
                "Unexpected error revoking Facebook access token",
                error=str(e),
                error_type=type(e).__name__,
                action="revoke_access_token",
            )
            return False

    async def revoke_all_tokens(self, user_id: str, access_token: str) -> bool:
        """Revoke all tokens/permissions for a Facebook user.

        Makes a DELETE request to /{user-id}/permissions with an access token
        to completely de-authorize the application for the specified user.

        Args:
            user_id: The Facebook user ID
            access_token: Access token for authentication with Facebook

        Returns:
            True if successfully revoked all tokens, False otherwise

        Raises:
            TokenRevocationFailedError: If revocation is critical and failed

        Example:
            >>> revoker = FacebookTokenRevoker()
            >>> success = await revoker.revoke_all_tokens("123456", "EAABw...")
            >>> if success:
            ...     print("All tokens revoked for user")
        """
        import httpx

        url = f"{self.api_base}/{user_id}/permissions"

        logger.info(
            "Revoking all Facebook tokens for user",
            url=url,
            user_id=user_id,
            action="revoke_all_tokens",
        )

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.delete(
                    url,
                    params={"access_token": access_token},
                )

                # Facebook returns 200 with {"success": true} on success
                if response.status_code == 200:
                    try:
                        data = response.json()
                        if data.get("success") is True:
                            logger.info(
                                "Successfully revoked all Facebook tokens",
                                user_id=user_id,
                                action="revoke_all_tokens",
                                status="success",
                            )
                            return True
                    except Exception as e:
                        logger.warning(
                            "Failed to parse Facebook revocation response",
                            error=str(e),
                            response_text=response.text,
                            user_id=user_id,
                            action="revoke_all_tokens",
                        )

                # Non-200 responses or invalid JSON - log but don't fail critically
                logger.warning(
                    "Facebook token revocation returned unexpected response",
                    status_code=response.status_code,
                    response_text=response.text,
                    user_id=user_id,
                    action="revoke_all_tokens",
                )
                return False

        except httpx.TimeoutException as e:
            logger.error(
                "Timeout revoking Facebook tokens",
                error=str(e),
                timeout=self.timeout,
                user_id=user_id,
                action="revoke_all_tokens",
            )
            return False

        except httpx.RequestError as e:
            logger.error(
                "Network error revoking Facebook tokens",
                error=str(e),
                error_type=type(e).__name__,
                user_id=user_id,
                action="revoke_all_tokens",
            )
            return False

        except Exception as e:
            logger.error(
                "Unexpected error revoking Facebook tokens",
                error=str(e),
                error_type=type(e).__name__,
                user_id=user_id,
                action="revoke_all_tokens",
            )
            return False


class MicrosoftTokenRevoker(OAuthTokenRevoker):
    """Microsoft OAuth token revoker implementation.

    Microsoft has LIMITED token revocation support:
    - Access tokens CANNOT be revoked programmatically (expire naturally)
    - Only sign-in sessions (refresh tokens) can be revoked
    - Uses Microsoft Graph API /me/revokeSignInSessions endpoint

    Technical Details:
    - Endpoint: POST https://graph.microsoft.com/v1.0/me/revokeSignInSessions
    - Invalidates all refresh tokens and requires user re-authentication
    - Resets signInSessionsValidFromDateTime to current time
    - Small delay may occur before sessions are fully revoked

    Limitations:
    - Does NOT revoke access tokens (they expire naturally after ~1 hour)
    - Does NOT work for external users
    - Requires User.RevokeSessions.All permission
    - Affects all applications, not just this one

    Reference:
    https://learn.microsoft.com/en-us/graph/api/user-revokesigninsessions
    """

    def __init__(self, http_timeout: int = 10) -> None:
        """Initialize Microsoft token revoker.

        Args:
            http_timeout: HTTP request timeout in seconds (default: 10)
        """
        import httpx

        self.http_timeout = http_timeout
        self.httpx = httpx  # Store module for testing/mocking

    async def revoke_access_token(self, access_token: str) -> bool:
        """Microsoft does NOT support access token revocation.

        Microsoft access tokens cannot be revoked programmatically - they
        expire naturally after approximately 1 hour. This method logs the
        limitation and returns True with a warning.

        Args:
            access_token: The access token (will not be revoked)

        Returns:
            True (tokens expire naturally, no action taken)

        Note:
            This is a design limitation of Microsoft's OAuth implementation.
            Access tokens will expire after ~1 hour regardless.
        """
        logger.warning(
            "Microsoft does not support access token revocation - tokens expire naturally",
            provider="microsoft",
            limitation="access_tokens_cannot_be_revoked",
            expiry_info="Access tokens expire automatically after ~1 hour",
        )
        return True  # Non-critical - tokens expire naturally

    async def revoke_all_tokens(self, user_id: str, access_token: str) -> bool:
        """Revoke all sign-in sessions (refresh tokens) for a Microsoft user.

        This method calls Microsoft Graph API's revokeSignInSessions endpoint,
        which invalidates ALL refresh tokens for the user across ALL applications.
        The user will need to re-authenticate for all previously consented apps.

        Args:
            user_id: Microsoft user ID (not used - uses /me endpoint)
            access_token: Valid access token for authorization

        Returns:
            True if sessions were successfully revoked, False otherwise

        Raises:
            TokenRevocationFailedError: If revocation fails critically

        Example:
            >>> revoker = MicrosoftTokenRevoker()
            >>> success = await revoker.revoke_all_tokens(
            ...     "user123",
            ...     "EwBIA8l6BAAURSN..."
            ... )
            >>> if success:
            ...     print("All Microsoft sessions revoked")

        Note:
            - Uses /me endpoint (user_id parameter ignored)
            - Affects ALL applications, not just this one
            - Small delay may occur before sessions are fully revoked
            - Does NOT work for external users
        """
        from src.constants.auth import MICROSOFT_REVOKE_URL

        logger.info(
            "Attempting to revoke Microsoft sign-in sessions",
            provider="microsoft",
            endpoint=MICROSOFT_REVOKE_URL,
            scope="all_applications",
            note="This affects ALL applications, not just this one",
        )

        try:
            async with self.httpx.AsyncClient(timeout=self.http_timeout) as client:
                response = await client.post(
                    MICROSOFT_REVOKE_URL,
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "Content-Type": "application/json",
                    },
                )

                # Microsoft returns 200/204 on success with boolean value
                if response.status_code in (200, 204):
                    logger.info(
                        "Successfully revoked Microsoft sign-in sessions",
                        provider="microsoft",
                        status_code=response.status_code,
                        note="User must re-authenticate for all applications",
                    )
                    return True

                # Handle specific error codes
                if response.status_code == 401:
                    logger.error(
                        "Microsoft revocation failed: Invalid or expired access token",
                        provider="microsoft",
                        status_code=401,
                        error="unauthorized",
                    )
                    return False

                if response.status_code == 403:
                    logger.error(
                        "Microsoft revocation failed: Insufficient permissions",
                        provider="microsoft",
                        status_code=403,
                        error="forbidden",
                        required_permission="User.RevokeSessions.All",
                    )
                    return False

                # Other error responses
                error_body = response.text if response.text else "No error details"
                logger.error(
                    "Microsoft revocation failed with unexpected status",
                    provider="microsoft",
                    status_code=response.status_code,
                    error_body=error_body,
                )
                return False

        except self.httpx.TimeoutException:
            logger.error(
                "Microsoft revocation request timed out",
                provider="microsoft",
                timeout=self.http_timeout,
            )
            return False  # Non-critical - sessions will expire naturally

        except self.httpx.HTTPError as e:
            logger.error(
                "HTTP error during Microsoft revocation",
                provider="microsoft",
                error=str(e),
                error_type=e.__class__.__name__,
            )
            return False  # Non-critical - sessions will expire naturally

        except Exception as e:
            logger.exception(
                "Unexpected error during Microsoft revocation",
                provider="microsoft",
                error=str(e),
                error_type=e.__class__.__name__,
            )
            # Don't raise - graceful degradation (sessions expire naturally)
            return False


class GitHubTokenRevoker(OAuthTokenRevoker):
    """GitHub OAuth token revocation implementation.

    Implements token revocation for GitHub OAuth Apps following their official API:
    https://docs.github.com/en/rest/apps/oauth-applications

    GitHub's revocation endpoint deletes an app authorization, which automatically
    revokes ALL associated OAuth tokens for the user.

    Technical Details:
    - Endpoint: DELETE https://api.github.com/applications/{client_id}/grant
    - Authentication: Basic Auth (client_id:client_secret)
    - Body: {"access_token": "..."}
    - Success: HTTP 204 No Content
    - Deleting grant revokes ALL tokens for the application

    Example:
        >>> revoker = GitHubTokenRevoker()
        >>> success = await revoker.revoke_access_token("gho_...")
        >>> if success:
        ...     logger.info("Token revoked successfully")

    Reference:
    https://docs.github.com/en/rest/apps/oauth-applications#delete-an-app-authorization
    """

    def __init__(self, http_timeout: int = 30) -> None:
        """Initialize GitHub token revoker with httpx client.

        Args:
            http_timeout: HTTP request timeout in seconds (default: 30)
        """
        import httpx

        from src.constants.auth import (
            GITHUB_REVOKE_URL,
            OAUTH_GITHUB_CLIENT_ID,
            OAUTH_GITHUB_CLIENT_SECRET,
        )

        self.client_id = OAUTH_GITHUB_CLIENT_ID
        self.client_secret = OAUTH_GITHUB_CLIENT_SECRET
        self.revoke_url = GITHUB_REVOKE_URL
        self.http_timeout = http_timeout
        self.httpx = httpx  # Store module for testing/mocking

        logger.info(
            "Initialized GitHubTokenRevoker",
            provider="github",
            revoke_url=self.revoke_url,
            timeout=http_timeout,
        )

    async def revoke_access_token(self, access_token: str) -> bool:
        """Revoke a GitHub OAuth access token.

        Makes a DELETE request to GitHub's app authorization endpoint with
        Basic authentication (client_id:client_secret) and access token in body.

        Args:
            access_token: The GitHub OAuth access token to revoke

        Returns:
            True if revocation succeeded, False if failed non-critically

        Raises:
            TokenRevocationFailedError: If access token is empty/invalid

        Example:
            >>> revoker = GitHubTokenRevoker()
            >>> success = await revoker.revoke_access_token("gho_...")

        Note:
            Revoking an access token also revokes ALL tokens for the app/user.
        """
        if not access_token or not access_token.strip():
            logger.error(
                "Attempted to revoke empty or invalid access token",
                provider="github",
                token_length=len(access_token) if access_token else 0,
            )
            raise TokenRevocationFailedError("Access token cannot be empty")

        # Construct the full URL: /applications/{client_id}/grant
        full_url = f"{self.revoke_url}/{self.client_id}/grant"

        logger.info(
            "Attempting to revoke GitHub access token",
            provider="github",
            url=full_url,
            token_prefix=access_token[:10] + "..." if len(access_token) > 10 else "***",
        )

        try:
            async with self.httpx.AsyncClient(timeout=self.http_timeout) as client:
                response = await client.request(
                    method="DELETE",
                    url=full_url,
                    auth=(self.client_id, self.client_secret),  # Basic auth
                    content=json.dumps({"access_token": access_token}),
                    headers={
                        "Accept": "application/vnd.github+json",
                        "X-GitHub-Api-Version": "2022-11-28",
                        "Content-Type": "application/json",
                    },
                )

                if response.status_code == 204:
                    logger.info(
                        "Successfully revoked GitHub access token",
                        provider="github",
                        status_code=response.status_code,
                    )
                    return True
                else:
                    logger.warning(
                        "GitHub token revocation returned non-204 status",
                        provider="github",
                        status_code=response.status_code,
                        response_text=response.text[:200] if response.text else "No response body",
                    )
                    # Non-critical failure - token may already be invalid or expired
                    return False

        except self.httpx.TimeoutException as e:
            logger.error(
                "Timeout while revoking GitHub access token",
                provider="github",
                error=str(e),
                timeout=self.http_timeout,
            )
            # Non-critical - token will expire naturally
            return False

        except self.httpx.HTTPError as e:
            logger.error(
                "HTTP error while revoking GitHub access token",
                provider="github",
                error=str(e),
                error_type=type(e).__name__,
            )
            # Non-critical - token will expire naturally
            return False

        except Exception as e:
            logger.error(
                "Unexpected error revoking GitHub access token",
                provider="github",
                error=str(e),
                error_type=type(e).__name__,
            )
            # Log but don't fail critically - graceful degradation
            return False

    async def revoke_all_tokens(self, user_id: str, access_token: str) -> bool:
        """Revoke all GitHub OAuth tokens for a user.

        GitHub's API automatically revokes all tokens when the app authorization
        is deleted. Therefore, this method simply calls revoke_access_token().

        Args:
            user_id: The user ID (not used by GitHub's API, included for interface)
            access_token: Access token for authentication with GitHub

        Returns:
            True if revocation succeeded, False otherwise

        Example:
            >>> revoker = GitHubTokenRevoker()
            >>> success = await revoker.revoke_all_tokens("user123", "gho_...")

        Note:
            GitHub automatically revokes ALL tokens when app authorization is deleted.
        """
        logger.info(
            "Revoking all GitHub tokens for user",
            provider="github",
            user_id=user_id,
        )

        # GitHub automatically revokes all tokens when authorization is deleted
        result = await self.revoke_access_token(access_token)

        if result:
            logger.info(
                "Successfully revoked all GitHub tokens for user",
                provider="github",
                user_id=user_id,
            )
        else:
            logger.warning(
                "Failed to revoke all GitHub tokens for user",
                provider="github",
                user_id=user_id,
            )

        return result


class AppleTokenRevoker(OAuthTokenRevoker):
    """Apple Sign In token revocation implementation.

    Apple Sign In uses JWT-signed client secrets for token revocation.
    This implementation handles the complexity of generating the client secret
    and revoking tokens via Apple's API.

    Technical Details:
    - Endpoint: POST https://appleid.apple.com/auth/revoke
    - Authentication: Client secret (JWT signed with private key)
    - Parameters: client_id, client_secret (JWT), token, token_type_hint
    - Success: HTTP 200
    - Both access tokens and refresh tokens can be revoked

    Limitations:
    - Requires Apple Developer account with private key
    - JWT client secret must be regenerated for each request (expires after 6 months)
    - Production-only (doesn't work with localhost)

    Example:
        >>> revoker = AppleTokenRevoker()
        >>> success = await revoker.revoke_access_token("...")
        >>> if success:
        ...     logger.info("Token revoked successfully")

    Reference:
    https://developer.apple.com/documentation/sign_in_with_apple/revoke_tokens
    """

    def __init__(self, http_timeout: int = 30) -> None:
        """Initialize Apple token revoker.

        Args:
            http_timeout: HTTP request timeout in seconds (default: 30)
        """
        import httpx

        from src.constants.auth import (
            APPLE_REVOKE_URL,
            OAUTH_APPLE_CLIENT_ID,
            OAUTH_APPLE_CLIENT_SECRET,
        )

        self.client_id = OAUTH_APPLE_CLIENT_ID
        self.client_secret = OAUTH_APPLE_CLIENT_SECRET
        self.revoke_url = APPLE_REVOKE_URL
        self.http_timeout = http_timeout
        self.httpx = httpx  # Store module for testing/mocking

        logger.info(
            "Initialized AppleTokenRevoker",
            provider="apple",
            revoke_url=self.revoke_url,
            timeout=http_timeout,
            note="Production-only (requires valid SSL domain)",
        )

    async def revoke_access_token(self, access_token: str) -> bool:
        """Revoke an Apple Sign In access token.

        Makes a POST request to Apple's revocation endpoint with the access token.
        Returns True on success (HTTP 200), False on non-critical failures.

        Args:
            access_token: The Apple Sign In access token to revoke

        Returns:
            True if revocation succeeded, False if failed non-critically

        Raises:
            TokenRevocationFailedError: If access token is empty/invalid

        Example:
            >>> revoker = AppleTokenRevoker()
            >>> success = await revoker.revoke_access_token("...")

        Note:
            Apple requires JWT-signed client secret for authentication.
            This implementation uses the pre-generated client secret from env.
        """
        if not access_token or not access_token.strip():
            logger.error(
                "Attempted to revoke empty or invalid access token",
                provider="apple",
                token_length=len(access_token) if access_token else 0,
            )
            raise TokenRevocationFailedError("Access token cannot be empty")

        logger.info(
            "Attempting to revoke Apple access token",
            provider="apple",
            token_prefix=access_token[:10] + "..." if len(access_token) > 10 else "***",
        )

        try:
            async with self.httpx.AsyncClient(timeout=self.http_timeout) as client:
                response = await client.post(
                    self.revoke_url,
                    data={
                        "client_id": self.client_id,
                        "client_secret": self.client_secret,  # JWT-signed secret
                        "token": access_token,
                        "token_type_hint": "access_token",
                    },
                    headers={
                        "Content-Type": "application/x-www-form-urlencoded",
                    },
                )

                if response.status_code == 200:
                    logger.info(
                        "Successfully revoked Apple access token",
                        provider="apple",
                        status_code=response.status_code,
                    )
                    return True
                else:
                    logger.warning(
                        "Apple token revocation returned non-200 status",
                        provider="apple",
                        status_code=response.status_code,
                        response_text=response.text[:200] if response.text else "No response body",
                    )
                    # Non-critical failure - token may already be invalid or expired
                    return False

        except self.httpx.TimeoutException as e:
            logger.error(
                "Timeout while revoking Apple access token",
                provider="apple",
                error=str(e),
                timeout=self.http_timeout,
            )
            # Non-critical - token will expire naturally
            return False

        except self.httpx.HTTPError as e:
            logger.error(
                "HTTP error while revoking Apple access token",
                provider="apple",
                error=str(e),
                error_type=type(e).__name__,
            )
            # Non-critical - token will expire naturally
            return False

        except Exception as e:
            logger.error(
                "Unexpected error revoking Apple access token",
                provider="apple",
                error=str(e),
                error_type=type(e).__name__,
            )
            # Log but don't fail critically - graceful degradation
            return False

    async def revoke_all_tokens(self, user_id: str, access_token: str) -> bool:
        """Revoke all Apple Sign In tokens for a user.

        Apple's API revokes the specific token provided. To revoke all tokens,
        we need to revoke both access and refresh tokens. This method attempts
        to revoke the access token (refresh tokens are typically not stored).

        Args:
            user_id: The user ID (not used by Apple's API, included for interface)
            access_token: Access token for authentication with Apple

        Returns:
            True if revocation succeeded, False otherwise

        Example:
            >>> revoker = AppleTokenRevoker()
            >>> success = await revoker.revoke_all_tokens("user123", "...")

        Note:
            Apple revokes tokens individually (not all tokens at once).
            This method revokes the provided access token.
        """
        logger.info(
            "Revoking all Apple tokens for user",
            provider="apple",
            user_id=user_id,
            note="Apple revokes tokens individually",
        )

        # Apple revokes tokens individually, not all at once
        result = await self.revoke_access_token(access_token)

        if result:
            logger.info(
                "Successfully revoked Apple tokens for user",
                provider="apple",
                user_id=user_id,
            )
        else:
            logger.warning(
                "Failed to revoke Apple tokens for user",
                provider="apple",
                user_id=user_id,
            )

        return result

    def supports_refresh_token_revocation(self) -> bool:
        """Check if Apple supports refresh token revocation.

        Apple supports both access token and refresh token revocation
        via the same endpoint.

        Returns:
            True - Apple supports refresh token revocation
        """
        return True

    async def revoke_refresh_token(self, refresh_token: str) -> bool:
        """Revoke an Apple Sign In refresh token.

        Apple uses the same endpoint for both access and refresh token revocation.
        Simply pass the refresh token with token_type_hint="refresh_token".

        Args:
            refresh_token: The Apple Sign In refresh token to revoke

        Returns:
            True if revocation succeeded, False otherwise

        Example:
            >>> revoker = AppleTokenRevoker()
            >>> success = await revoker.revoke_refresh_token("...")

        Note:
            Uses same endpoint as access tokens, just different token_type_hint.
        """
        if not refresh_token or not refresh_token.strip():
            logger.error(
                "Attempted to revoke empty or invalid refresh token",
                provider="apple",
            )
            raise TokenRevocationFailedError("Refresh token cannot be empty")

        logger.info(
            "Revoking Apple refresh token",
            provider="apple",
            token_prefix=refresh_token[:10] + "..." if len(refresh_token) > 10 else "***",
        )

        try:
            async with self.httpx.AsyncClient(timeout=self.http_timeout) as client:
                response = await client.post(
                    self.revoke_url,
                    data={
                        "client_id": self.client_id,
                        "client_secret": self.client_secret,  # JWT-signed secret
                        "token": refresh_token,
                        "token_type_hint": "refresh_token",  # Hint for refresh token
                    },
                    headers={
                        "Content-Type": "application/x-www-form-urlencoded",
                    },
                )

                if response.status_code == 200:
                    logger.info(
                        "Successfully revoked Apple refresh token",
                        provider="apple",
                        status_code=response.status_code,
                    )
                    return True
                else:
                    logger.warning(
                        "Apple refresh token revocation returned non-200 status",
                        provider="apple",
                        status_code=response.status_code,
                    )
                    return False

        except Exception as e:
            logger.error(
                "Error revoking Apple refresh token",
                provider="apple",
                error=str(e),
                error_type=type(e).__name__,
            )
            return False


# ==================== Module-Level Registration ====================

# Register provider revokers at module import time
from .models.oauth_models import OAuthProvider  # noqa: E402

OAuthRevocationRegistry.register_revoker(
    OAuthProvider.GOOGLE,
    GoogleTokenRevoker(),
)

OAuthRevocationRegistry.register_revoker(
    OAuthProvider.FACEBOOK,
    FacebookTokenRevoker(),
)

OAuthRevocationRegistry.register_revoker(
    OAuthProvider.MICROSOFT,
    MicrosoftTokenRevoker(),
)

OAuthRevocationRegistry.register_revoker(
    OAuthProvider.GITHUB,
    GitHubTokenRevoker(),
)

OAuthRevocationRegistry.register_revoker(
    OAuthProvider.APPLE,
    AppleTokenRevoker(),
)
