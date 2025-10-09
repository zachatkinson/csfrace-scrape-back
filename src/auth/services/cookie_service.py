"""Cookie management service for secure authentication following OWASP best practices."""

import os
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Literal

from fastapi import Response

from src.core.logging_hierarchy import get_auth_logger

from ..models import Token

if TYPE_CHECKING:
    from fastapi import Request

logger = get_auth_logger()


class CookieService:
    """Service for secure HTTP-only cookie management - SOLID Single Responsibility."""

    def __init__(self) -> None:
        """Initialize cookie service with environment-aware settings."""
        self.environment = os.getenv("ENVIRONMENT", "development").lower()
        self.is_production = self.environment == "production"
        # Allow forcing secure cookies in development (for HTTPS development environments)
        self.force_secure_cookies = os.getenv("FORCE_SECURE_COOKIES", "false").lower() == "true"

    def set_auth_cookies(
        self, response: Response, token: Token, request: "Request | None" = None
    ) -> None:
        """Set HTTP-only cookies for secure token storage.

        Args:
            response: FastAPI response object
            token: JWT token object with access and refresh tokens
            request: Optional FastAPI request to detect HTTPS via X-Forwarded-Proto
        """
        # Check if request came through HTTPS proxy (nginx sets X-Forwarded-Proto)
        is_https_request = False
        if request:
            forwarded_proto = request.headers.get("X-Forwarded-Proto", "").lower()
            is_https_request = forwarded_proto == "https"

        # Environment-aware security settings
        # CRITICAL: Disable Secure flag for localhost (even with HTTPS) due to self-signed certs
        # Browsers reject Secure cookies on localhost with self-signed certificates
        # Use Secure flag if: production OR explicitly forced (not just HTTPS detection)
        secure_cookies = self.is_production or self.force_secure_cookies
        cookie_domain = self._get_cookie_domain()
        samesite_policy = self._get_samesite_policy()

        # Access token cookie - short lived
        response.set_cookie(
            key="auth_token",
            value=token.access_token,
            max_age=token.expires_in,  # Seconds until expiration
            httponly=True,  # Prevents XSS attacks
            secure=secure_cookies,  # HTTPS only in production
            samesite=samesite_policy,  # Environment-aware CSRF protection
            path="/",  # Available to entire application
            domain=cookie_domain,  # Cross-port support in development
        )

        # Refresh token cookie - longer lived
        if token.refresh_token:
            response.set_cookie(
                key="refresh_token",
                value=token.refresh_token,
                max_age=60 * 60 * 24 * 30,  # 30 days
                httponly=True,
                secure=secure_cookies,
                samesite=samesite_policy,
                path="/",
                domain=cookie_domain,
            )

        # User info cookie for frontend (non-sensitive data only)
        response.set_cookie(
            key="auth_user",
            value=f'{{"isAuthenticated":true,"isNewUser":{str(token.is_new_user).lower()}}}',
            max_age=token.expires_in,
            httponly=False,  # Frontend needs to read this
            secure=secure_cookies,
            samesite=samesite_policy,
            path="/",
            domain=cookie_domain,
        )

        logger.info(
            "Secure authentication cookies set",
            access_token_expires=token.expires_in,
            has_refresh_token=bool(token.refresh_token),
            is_new_user=token.is_new_user,
            environment=self.environment,
            secure_cookies=secure_cookies,
            cookie_domain=cookie_domain,
            samesite_policy=samesite_policy,
            is_https_request=is_https_request,
            x_forwarded_proto=request.headers.get("X-Forwarded-Proto") if request else None,
        )

    def clear_auth_cookies(self, response: Response) -> None:
        """Clear authentication cookies for logout.

        Args:
            response: FastAPI response object
        """
        # Safari-compatible cookie clearing patterns
        secure_cookies = self.is_production
        cookie_domain = self._get_cookie_domain()
        samesite_policy = self._get_samesite_policy()

        # Safari-compatible cookie clearing: Set to empty value with past expiration
        past_date = datetime.now(UTC) - timedelta(days=1)

        # Clear auth_token cookie
        response.set_cookie(
            key="auth_token",
            value="",
            expires=past_date,
            httponly=True,
            secure=secure_cookies,
            samesite=samesite_policy,
            path="/",
            domain=cookie_domain,
        )

        # Clear refresh_token cookie
        response.set_cookie(
            key="refresh_token",
            value="",
            expires=past_date,
            httponly=True,
            secure=secure_cookies,
            samesite=samesite_policy,
            path="/",
            domain=cookie_domain,
        )

        # Clear auth_user cookie
        response.set_cookie(
            key="auth_user",
            value="",
            expires=past_date,
            httponly=False,
            secure=secure_cookies,
            samesite=samesite_policy,
            path="/",
            domain=cookie_domain,
        )

        logger.info(
            "Authentication cookies cleared for logout",
            environment=self.environment,
            is_production=self.is_production,
            cookie_domain=cookie_domain,
            samesite_policy=samesite_policy,
            secure_cookies=secure_cookies,
        )

    def _get_cookie_domain(self) -> str | None:
        """Get appropriate cookie domain for environment.

        Returns:
            None - let browser use default domain (exact host match)
        """
        # CRITICAL: Return None to let browser use default domain behavior
        # Setting domain="localhost" causes browsers to add a leading dot (.localhost)
        # which prevents cookies from being sent back to localhost
        # With None, cookies work correctly for both localhost and production domains
        return None

    def _get_samesite_policy(self) -> Literal["strict", "lax"]:
        """Get appropriate SameSite policy for environment.

        Returns:
            SameSite policy based on environment
        """
        # SameSite policy for development vs production
        # Use "lax" in development to allow cross-origin SSE proxy requests
        return "strict" if self.is_production else "lax"
