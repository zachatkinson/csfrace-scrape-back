"""OAuth callback validation service following SOLID principles."""

from fastapi import HTTPException, status

from src.core.logging_hierarchy import get_auth_logger

from ..enum_utils import get_oauth_provider_value
from ..models import OAuthCallback, OAuthProvider

logger = get_auth_logger()


class OAuthValidationService:
    """Service for OAuth callback parameter validation - SOLID Single Responsibility."""

    @staticmethod
    def validate_callback_parameters(
        provider: OAuthProvider, oauth_callback: OAuthCallback
    ) -> None:
        """Validate OAuth callback parameters and handle errors.

        Args:
            provider: Expected OAuth provider
            oauth_callback: OAuth callback data

        Raises:
            HTTPException: If validation fails
        """
        OAuthValidationService._validate_oauth_errors(provider, oauth_callback)
        OAuthValidationService._validate_provider_consistency(provider, oauth_callback)
        OAuthValidationService._validate_required_parameters(provider, oauth_callback)

    @staticmethod
    def _validate_oauth_errors(provider: OAuthProvider, oauth_callback: OAuthCallback) -> None:
        """Validate OAuth error responses.

        Args:
            provider: OAuth provider
            oauth_callback: OAuth callback data

        Raises:
            HTTPException: If OAuth error is present
        """
        if oauth_callback.error:
            error_detail = oauth_callback.error_description or oauth_callback.error
            logger.warning(
                "OAuth callback received error",
                provider=get_oauth_provider_value(provider),
                error=oauth_callback.error,
                error_description=oauth_callback.error_description,
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"OAuth authorization failed: {error_detail}",
            )

    @staticmethod
    def _validate_provider_consistency(
        provider: OAuthProvider, oauth_callback: OAuthCallback
    ) -> None:
        """Validate provider consistency (CSRF protection).

        Args:
            provider: Expected OAuth provider
            oauth_callback: OAuth callback data

        Raises:
            HTTPException: If provider mismatch detected
        """
        if provider != oauth_callback.provider:
            logger.warning(
                "OAuth callback provider mismatch",
                url_provider=get_oauth_provider_value(provider),
                callback_provider=get_oauth_provider_value(oauth_callback.provider),
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="OAuth provider mismatch - possible CSRF attack",
            )

    @staticmethod
    def _validate_required_parameters(
        provider: OAuthProvider, oauth_callback: OAuthCallback
    ) -> None:
        """Validate required OAuth callback parameters.

        Args:
            provider: OAuth provider
            oauth_callback: OAuth callback data

        Raises:
            HTTPException: If required parameters are missing
        """
        if not oauth_callback.code:
            logger.warning(
                "OAuth callback missing authorization code",
                provider=get_oauth_provider_value(provider),
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing authorization code in OAuth callback",
            )

        if not oauth_callback.state:
            logger.warning(
                "OAuth callback missing state parameter",
                provider=get_oauth_provider_value(provider),
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing state parameter in OAuth callback",
            )
