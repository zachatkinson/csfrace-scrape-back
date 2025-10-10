"""Server-Sent Events authentication service following SOLID principles."""

import json
import os
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import asyncio
import jwt
from fastapi import Request
from slowapi.util import get_remote_address

from src.config.settings import ConfigManager
from src.core.logging_hierarchy import get_auth_logger

if TYPE_CHECKING:
    from src.config.auth import AuthConfig


def _get_auth_config() -> "AuthConfig":
    """Get authentication configuration from centralized settings."""
    try:
        settings = ConfigManager.get_config()
        return settings.auth
    except RuntimeError:
        # Fallback for testing or early initialization
        from src.config.auth import AuthConfig

        return AuthConfig(SECRET_KEY=os.getenv("SECRET_KEY", ""))


auth_config = _get_auth_config()

logger = get_auth_logger()


class SSEAuthService:
    """Service for SSE authentication status management - SOLID Single Responsibility."""

    def __init__(self) -> None:
        """Initialize SSE auth service."""
        self.heartbeat_interval = 30  # Send heartbeat every 30 seconds

    async def get_auth_status_from_cookies(self, request: Request) -> dict[str, bool | str | None]:
        """Extract authentication status from HTTP-only cookies.

        Args:
            request: FastAPI request object

        Returns:
            Authentication status dictionary
        """
        # Log comprehensive debugging information
        logger.info(
            "Checking authentication from cookies",
            request_url=str(request.url),
            client_host=request.client.host if request.client else "unknown",
            headers_keys=list(request.headers.keys()),
            cookie_header=request.headers.get("cookie", "NO_COOKIE_HEADER"),
            has_auth_token=bool(request.cookies.get("auth_token")),
            has_auth_user=bool(request.cookies.get("auth_user")),
            all_cookie_names=list(request.cookies.keys()),
            cookie_count=len(request.cookies),
        )

        # Extract cookies
        auth_token = request.cookies.get("auth_token")
        auth_user = request.cookies.get("auth_user")

        # Log detailed cookie debugging
        logger.info(
            "Cookie extraction results",
            auth_token_present=bool(auth_token),
            auth_token_length=len(auth_token) if auth_token else 0,
            auth_user_present=bool(auth_user),
            auth_user_length=len(auth_user) if auth_user else 0,
            auth_token_prefix=auth_token[:20] + "..."
            if auth_token and len(auth_token) > 20
            else auth_token,
            auth_user_preview=auth_user[:50] + "..."
            if auth_user and len(auth_user) > 50
            else auth_user,
        )

        if auth_token and auth_user:
            try:
                # Validate the JWT token
                payload = jwt.decode(
                    auth_token, auth_config.SECRET_KEY, algorithms=[auth_config.ALGORITHM]
                )

                # Parse user data from cookie
                user_data = json.loads(auth_user)

                return {
                    "authenticated": True,
                    "user": {
                        "id": user_data.get("id"),
                        "username": user_data.get("username"),
                        "email": user_data.get("email"),
                        "is_verified": user_data.get("is_verified", True),
                        "provider": user_data.get("provider", "local"),
                    },
                    "expires_at": payload.get("exp"),
                    "token_type": "bearer",
                }
            except (jwt.InvalidTokenError, json.JSONDecodeError) as e:
                logger.warning("Invalid authentication cookies", error=str(e))

        logger.info(
            "No valid authentication cookies found",
            auth_token_missing=not bool(auth_token),
            auth_user_missing=not bool(auth_user),
            available_cookies=list(request.cookies.keys()),
            cookie_header_raw=request.headers.get("cookie", "NO_COOKIE_HEADER"),
        )
        return {"authenticated": False, "reason": "no_auth_cookies"}

    async def generate_auth_events(self, request: Request) -> AsyncGenerator[str]:
        """Generate Server-Sent Events for authentication status updates.

        Args:
            request: FastAPI request object

        Yields:
            SSE formatted authentication events
        """
        client_ip = get_remote_address(request)
        connection_id = f"auth_{client_ip}_{datetime.now().timestamp()}"

        logger.info(
            "SSE auth stream connection established",
            connection_id=connection_id,
            client_ip=client_ip,
        )

        try:
            last_auth_status = None
            heartbeat_counter = 0

            while True:
                # Check current authentication status
                current_auth_status = await self.get_auth_status_from_cookies(request)

                # Send auth status update if it changed
                if current_auth_status != last_auth_status:
                    auth_event = {
                        "type": "auth_status",
                        "data": current_auth_status,
                        "timestamp": datetime.now(UTC).isoformat(),
                        "connection_id": connection_id,
                    }

                    yield f"event: auth_status\ndata: {json.dumps(auth_event)}\n\n"

                    logger.debug(
                        "Auth status change detected",
                        connection_id=connection_id,
                        authenticated=current_auth_status.get("authenticated", False),
                        reason=current_auth_status.get("reason"),
                    )

                    last_auth_status = current_auth_status

                # Send periodic heartbeat to keep connection alive
                heartbeat_counter += 1
                if heartbeat_counter % self.heartbeat_interval == 0:
                    heartbeat_event = {
                        "type": "heartbeat",
                        "timestamp": datetime.now(UTC).isoformat(),
                        "connection_id": connection_id,
                        "authenticated": current_auth_status.get("authenticated", False),
                    }

                    yield f"event: heartbeat\ndata: {json.dumps(heartbeat_event)}\n\n"
                    logger.debug("SSE heartbeat sent", connection_id=connection_id)

                # Check every second for auth changes, heartbeat every 30 seconds
                await asyncio.sleep(1)

        except asyncio.CancelledError:
            logger.info(
                "SSE auth stream cancelled", connection_id=connection_id, client_ip=client_ip
            )
        except Exception as e:
            logger.error("Error in SSE auth stream", connection_id=connection_id, error=str(e))
            # Send error event
            error_event = {
                "type": "error",
                "error": "stream_error",
                "message": "Authentication stream error",
                "timestamp": datetime.now(UTC).isoformat(),
                "connection_id": connection_id,
            }
            yield f"event: error\ndata: {json.dumps(error_event)}\n\n"
        finally:
            logger.info(
                "SSE auth stream connection closed",
                connection_id=connection_id,
                client_ip=client_ip,
            )

    @staticmethod
    def get_sse_headers() -> dict[str, str]:
        """Get SSE response headers with environment-aware CORS.

        Returns:
            Dictionary of SSE headers
        """
        environment = os.getenv("ENVIRONMENT", "development").lower()
        frontend_origin = (
            "http://localhost:3000"
            if environment == "development"
            else os.getenv("FRONTEND_URL", "https://your-domain.com")
        )

        return {
            "Content-Type": "text/event-stream",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": frontend_origin,
            "Access-Control-Allow-Credentials": "true",
            "Access-Control-Allow-Headers": "Cache-Control",
        }
