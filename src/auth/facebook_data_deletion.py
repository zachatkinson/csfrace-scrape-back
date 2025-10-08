"""Facebook Data Deletion Callback Implementation.

This module handles Facebook's data deletion requests as required by Facebook's
Platform Policy for apps in Live mode.

Facebook sends a signed_request parameter containing the user's Facebook ID.
We verify the signature and delete all user data associated with that Facebook account.

@see https://developers.facebook.com/docs/development/create-an-app/app-dashboard/data-deletion-callback
"""

import base64
import hashlib
import hmac
import json
import secrets
from typing import Any, cast

from src.constants.auth import OAUTH_FACEBOOK_CLIENT_SECRET
from src.core.logging_hierarchy import get_auth_logger

logger = get_auth_logger(__name__)


class FacebookDataDeletionRequest:
    """Handle Facebook data deletion requests with signature verification."""

    def __init__(self, app_secret: str):
        """
        Initialize Facebook data deletion handler.

        Args:
            app_secret: Facebook app secret for signature verification
        """
        self.app_secret = app_secret

    def parse_signed_request(self, signed_request: str) -> dict[str, Any] | None:
        """
        Parse and verify Facebook's signed_request parameter.

        Facebook signs requests using HMAC-SHA256 to prevent spoofing.
        Format: <base64-signature>.<base64-payload>

        Args:
            signed_request: The signed request from Facebook

        Returns:
            Parsed payload dict if valid, None if invalid signature

        Raises:
            ValueError: If signed_request format is invalid
        """
        try:
            # Split signature and payload
            encoded_sig, payload = signed_request.split(".", 2)

            # Decode signature (add padding if needed)
            sig = self._base64_url_decode(encoded_sig)

            # Decode payload
            data = json.loads(self._base64_url_decode(payload))

            # Verify signature
            if data.get("algorithm", "").upper() != "HMAC-SHA256":
                logger.warning(
                    "Invalid algorithm in signed_request", algorithm=data.get("algorithm")
                )
                return None

            # Compute expected signature
            expected_sig = hmac.new(
                self.app_secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256
            ).digest()

            # Compare signatures (constant-time comparison to prevent timing attacks)
            if not hmac.compare_digest(sig, expected_sig):
                logger.warning("Signature verification failed for signed_request")
                return None

            logger.info(
                "Successfully verified Facebook signed_request", user_id=data.get("user_id")
            )
            return cast("dict[str, Any]", data)

        except (ValueError, KeyError) as e:
            logger.error("Failed to parse signed_request", error=str(e))
            raise ValueError(f"Invalid signed_request format: {e}")

    def _base64_url_decode(self, inp: str) -> bytes:
        """
        Decode base64-encoded string with URL-safe alphabet.

        Facebook uses URL-safe base64 encoding without padding.

        Args:
            inp: Base64-encoded string

        Returns:
            Decoded bytes
        """
        # Add padding if needed (base64 requires length to be multiple of 4)
        padding_factor = (4 - len(inp) % 4) % 4
        inp += "=" * padding_factor

        # Replace URL-safe characters with standard base64 characters
        inp = inp.replace("-", "+").replace("_", "/")

        return base64.b64decode(inp)

    def generate_confirmation_code(self, user_id: str) -> str:
        """
        Generate a unique confirmation code for the deletion request.

        This code can be used to track the deletion request status.

        Args:
            user_id: Facebook user ID

        Returns:
            Unique confirmation code (32 characters)
        """
        # Generate cryptographically secure random code
        random_suffix = secrets.token_hex(12)  # 24 hex characters
        code = f"fb_{user_id[:8]}_{random_suffix}"
        return code


# Singleton instance
facebook_data_deletion_handler = FacebookDataDeletionRequest(
    app_secret=OAUTH_FACEBOOK_CLIENT_SECRET
)
