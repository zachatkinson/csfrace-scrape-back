"""Authentication models organized by domain following SOLID principles."""

# Import all models from domain-specific modules for convenient access
from .account_merge_models import (
    AccountMergeDetection,
    AccountMergeRequest,
    AccountMergeResult,
    DuplicateAccountInfo,
    MergeAuditLog,
)
from .oauth_models import (
    LinkedAccount,
    OAuthCallback,
    OAuthConnectionResponse,
    OAuthProvider,
    OAuthUserInfo,
    SSOLoginRequest,
    SSOLoginResponse,
)
from .response_models import MessageResponse, StatusResponse
from .security_models import (
    AccountLockoutStatusResponse,
    LockoutStatsResponse,
    UnlockAccountRequest,
)
from .token_models import (
    BulkTokenRevocationRequest,
    RevocationStatsResponse,
    Token,
    TokenData,
    TokenRevocationRequest,
    TokenRevocationResponse,
)
from .user_models import (
    JobIdPath,
    OAuthUserCreate,
    PasswordChange,
    PasswordReset,
    PasswordResetConfirm,
    User,
    UserCreate,
    UserIdPath,
    UserInDB,
    UserLogin,
    UserUpdate,
)
from .validation_mixins import PasswordValidatorMixin
from .webauthn_models import (
    CredentialIdPath,
    PasskeyAuthenticationRequest,
    PasskeyAuthenticationResponse,
    PasskeyCredentialRequest,
    PasskeyDevice,
    PasskeyRegistrationRequest,
    PasskeyRegistrationResponse,
    PasskeySummary,
    WebAuthnAuthenticationComplete,
    WebAuthnAuthenticationStart,
    WebAuthnChallenge,
    WebAuthnCredentialResponse,
    WebAuthnRegistrationComplete,
    WebAuthnRegistrationStart,
)

__all__ = [
    # User models
    "User",
    "UserInDB",
    "UserCreate",
    "OAuthUserCreate",
    "UserLogin",
    "PasswordReset",
    "PasswordResetConfirm",
    "UserUpdate",
    "PasswordChange",
    "UserIdPath",
    "JobIdPath",
    # Token models
    "Token",
    "TokenData",
    "TokenRevocationRequest",
    "BulkTokenRevocationRequest",
    "TokenRevocationResponse",
    "RevocationStatsResponse",
    # OAuth models
    "OAuthProvider",
    "OAuthUserInfo",
    "OAuthCallback",
    "SSOLoginRequest",
    "SSOLoginResponse",
    "LinkedAccount",
    "OAuthConnectionResponse",
    # Account merge models
    "AccountMergeDetection",
    "AccountMergeRequest",
    "AccountMergeResult",
    "DuplicateAccountInfo",
    "MergeAuditLog",
    # WebAuthn models
    "PasskeyRegistrationRequest",
    "PasskeyRegistrationResponse",
    "PasskeyAuthenticationRequest",
    "PasskeyAuthenticationResponse",
    "PasskeyCredentialRequest",
    "PasskeySummary",
    "PasskeyDevice",
    "WebAuthnRegistrationStart",
    "WebAuthnRegistrationComplete",
    "WebAuthnAuthenticationStart",
    "WebAuthnAuthenticationComplete",
    "WebAuthnCredentialResponse",
    "WebAuthnChallenge",
    "CredentialIdPath",
    # Response models
    "MessageResponse",
    "StatusResponse",
    # Security models
    "AccountLockoutStatusResponse",
    "UnlockAccountRequest",
    "LockoutStatsResponse",
    # Validation mixins
    "PasswordValidatorMixin",
]
