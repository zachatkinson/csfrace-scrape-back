"""Authentication-related constants for PERFECT SRP compliance.

ZERO TOLERANCE for mixing domains - only authentication constants here.
Single source of truth for ALL authentication-related configuration.
"""

from src.core.environment import EnvironmentLoader

# Authentication constants
BEARER_TOKEN_TYPE: str = "bearer"  # noqa: S105
PASSWORD_CONTEXT_DEPRECATED: str = "auto"  # noqa: S105

# OAuth2 Client Credentials - SECURE Environment Variable Configuration
OAUTH_GOOGLE_CLIENT_ID: str = EnvironmentLoader.get_optional("OAUTH_GOOGLE_CLIENT_ID", "")
OAUTH_GOOGLE_CLIENT_SECRET: str = EnvironmentLoader.get_optional("OAUTH_GOOGLE_CLIENT_SECRET", "")

OAUTH_GITHUB_CLIENT_ID: str = EnvironmentLoader.get_optional("OAUTH_GITHUB_CLIENT_ID", "")
OAUTH_GITHUB_CLIENT_SECRET: str = EnvironmentLoader.get_optional("OAUTH_GITHUB_CLIENT_SECRET", "")

OAUTH_MICROSOFT_CLIENT_ID: str = EnvironmentLoader.get_optional("OAUTH_MICROSOFT_CLIENT_ID", "")
OAUTH_MICROSOFT_CLIENT_SECRET: str = EnvironmentLoader.get_optional(
    "OAUTH_MICROSOFT_CLIENT_SECRET", ""
)
OAUTH_FACEBOOK_CLIENT_ID: str = EnvironmentLoader.get_optional("OAUTH_FACEBOOK_CLIENT_ID", "")
OAUTH_FACEBOOK_CLIENT_SECRET: str = EnvironmentLoader.get_optional(
    "OAUTH_FACEBOOK_CLIENT_SECRET", ""
)
OAUTH_APPLE_CLIENT_ID: str = EnvironmentLoader.get_optional("OAUTH_APPLE_CLIENT_ID", "")
OAUTH_APPLE_CLIENT_SECRET: str = EnvironmentLoader.get_optional("OAUTH_APPLE_CLIENT_SECRET", "")

# OAuth Token Encryption - SECURE Environment Variable Configuration
# Default test key for CI/testing environments (should be overridden in production)
OAUTH_TOKEN_ENCRYPTION_KEY: str = EnvironmentLoader.get_optional(
    "OAUTH_TOKEN_ENCRYPTION_KEY",
    "TKwaDTMfz6H89IfmbJKUCACZ2BeJN3YIgFGlkIHx6T8=",  # Valid Fernet key for testing only
)

# OAuth Token Revocation URLs - DRY principle for provider endpoints
GOOGLE_REVOKE_URL: str = "https://oauth2.googleapis.com/revoke"
FACEBOOK_GRAPH_API_BASE: str = "https://graph.facebook.com/v18.0"
GITHUB_REVOKE_URL: str = "https://api.github.com/applications"  # Append /{client_id}/grant
MICROSOFT_REVOKE_URL: str = "https://graph.microsoft.com/v1.0/me/revokeSignInSessions"
APPLE_REVOKE_URL: str = "https://appleid.apple.com/auth/revoke"  # For future production use

# OAuth2 Redirect URIs - Centralized Configuration
OAUTH_REDIRECT_URI_BASE: str = EnvironmentLoader.get_url(
    "OAUTH_REDIRECT_URI_BASE", "http://localhost:8000"
)

# Google OAuth2 Configuration
GOOGLE_AUTHORIZATION_URL: str = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL: str = "https://oauth2.googleapis.com/token"  # noqa: S105
GOOGLE_USER_INFO_URL: str = "https://www.googleapis.com/oauth2/v2/userinfo"
GOOGLE_SCOPES: list[str] = ["openid", "email", "profile"]

# GitHub OAuth2 Configuration
GITHUB_AUTHORIZATION_URL: str = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN_URL: str = "https://github.com/login/oauth/access_token"  # noqa: S105
GITHUB_USER_INFO_URL: str = "https://api.github.com/user"
GITHUB_USER_EMAILS_URL: str = "https://api.github.com/user/emails"
GITHUB_SCOPES: list[str] = ["user:email"]

# Microsoft OAuth2 Configuration
MICROSOFT_AUTHORIZATION_URL: str = "https://login.microsoftonline.com/common/oauth2/v2.0/authorize"
MICROSOFT_TOKEN_URL: str = "https://login.microsoftonline.com/common/oauth2/v2.0/token"  # noqa: S105
MICROSOFT_USER_INFO_URL: str = "https://graph.microsoft.com/v1.0/me"
MICROSOFT_SCOPES: list[str] = ["openid", "profile", "email", "User.Read"]

# Apple OAuth2 Configuration
APPLE_AUTHORIZATION_URL: str = "https://appleid.apple.com/auth/authorize"
APPLE_TOKEN_URL: str = "https://appleid.apple.com/auth/token"  # noqa: S105
APPLE_SCOPES: list[str] = ["name", "email"]

# OAuth2 Security Settings
STATE_TOKEN_LENGTH: int = 32  # Length for OAuth2 state parameter
OAUTH_TIMEOUT: int = EnvironmentLoader.get_int(
    "OAUTH_TIMEOUT", 30, min_value=5, max_value=120
)  # OAuth request timeout
OAUTH_MAX_RETRIES: int = EnvironmentLoader.get_int(
    "OAUTH_MAX_RETRIES", 3, min_value=0, max_value=10
)  # OAuth retry attempts

# WebAuthn/Passkeys configuration constants
WEBAUTHN_RP_ID: str = EnvironmentLoader.get_optional("WEBAUTHN_RP_ID", "localhost")
WEBAUTHN_RP_NAME: str = EnvironmentLoader.get_optional("WEBAUTHN_RP_NAME", "CSFrace Backend")
WEBAUTHN_ORIGIN: str = EnvironmentLoader.get_url("WEBAUTHN_ORIGIN", "http://localhost:8000")

# Challenge Configuration - Security Settings
CHALLENGE_LENGTH_BYTES: int = 32  # 256-bit challenge (FIDO2 standard)
CHALLENGE_TIMEOUT_MS: int = EnvironmentLoader.get_int(
    "WEBAUTHN_CHALLENGE_TIMEOUT_MS", 60000, min_value=30000, max_value=300000
)  # 1 minute
CHALLENGE_MAX_AGE_MINUTES: int = EnvironmentLoader.get_int(
    "WEBAUTHN_CHALLENGE_MAX_AGE", 10, min_value=1, max_value=60
)  # 10 minutes

# Credential Configuration
MAX_CREDENTIALS_PER_USER: int = EnvironmentLoader.get_int(
    "WEBAUTHN_MAX_CREDENTIALS", 10, min_value=1, max_value=50
)
DEVICE_NAME_MAX_LENGTH: int = 100
CREDENTIAL_ID_LENGTH: int = 64  # Base64URL encoded length

# Authenticator Selection Preferences - FIDO2 Standards
USER_VERIFICATION_REQUIREMENT: str = "preferred"  # preferred, required, discouraged
AUTHENTICATOR_ATTACHMENT: str = "platform"  # platform, cross-platform, or None
REQUIRE_RESIDENT_KEY: bool = False  # For discoverable credentials

# Attestation Configuration
ATTESTATION_CONVEYANCE: str = "none"  # none, indirect, direct, enterprise

# Timeout Configuration
REGISTRATION_TIMEOUT_MS: int = EnvironmentLoader.get_int(
    "WEBAUTHN_REG_TIMEOUT_MS", 60000, min_value=30000, max_value=300000
)
AUTHENTICATION_TIMEOUT_MS: int = EnvironmentLoader.get_int(
    "WEBAUTHN_AUTH_TIMEOUT_MS", 60000, min_value=30000, max_value=300000
)

# Security Settings
ALLOWED_ORIGINS: list[str] = [
    EnvironmentLoader.get_url("WEBAUTHN_ORIGIN", "http://localhost:8000"),
    EnvironmentLoader.get_url("WEBAUTHN_PRODUCTION_ORIGIN", "https://api.csfrace.com"),
]

# Cache keys for authentication
CHALLENGE_CACHE_PREFIX: str = "webauthn_challenge:"

# Error Messages - DRY Principle
ERROR_INVALID_CHALLENGE: str = "Invalid or expired challenge"
ERROR_VERIFICATION_FAILED: str = "WebAuthn verification failed"
ERROR_CREDENTIAL_NOT_FOUND: str = "Credential not found or inactive"
ERROR_USER_NOT_FOUND: str = "User not found or inactive"
ERROR_CHALLENGE_TYPE_MISMATCH: str = "Challenge type mismatch"
ERROR_MAX_CREDENTIALS_EXCEEDED: str = "Maximum number of credentials exceeded"

# Success Messages
SUCCESS_CREDENTIAL_REGISTERED: str = "Passkey registered successfully"
SUCCESS_AUTHENTICATION: str = "Authentication successful"
SUCCESS_CREDENTIAL_REVOKED: str = "Passkey revoked successfully"
