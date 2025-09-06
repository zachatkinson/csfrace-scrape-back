"""WebAuthn/Passkeys service implementation - following SOLID principles and FIDO2 standards."""

import secrets
from dataclasses import dataclass
from datetime import UTC, datetime

import structlog
from sqlalchemy.orm import Session
from webauthn import (
    generate_authentication_options,
    generate_registration_options,
    verify_authentication_response,
    verify_registration_response,
)
from webauthn.helpers import base64url_to_bytes, bytes_to_base64url
from webauthn.helpers.structs import (
    AttestationConveyancePreference,
    AuthenticationCredential,
    AuthenticatorSelectionCriteria,
    PublicKeyCredentialDescriptor,
    PublicKeyCredentialType,
    RegistrationCredential,
    UserVerificationRequirement,
)

from ..constants import WEBAUTHN_CONSTANTS
from ..database.models import WebAuthnCredential as WebAuthnCredentialModel
from .models import User
from .service import AuthService

logger = structlog.get_logger(__name__)


@dataclass
class WebAuthnConfig:
    """Configuration for WebAuthn service - Best practice for too-many-arguments."""

    rp_id: str = WEBAUTHN_CONSTANTS.WEBAUTHN_RP_ID
    rp_name: str = WEBAUTHN_CONSTANTS.WEBAUTHN_RP_NAME
    origin: str = WEBAUTHN_CONSTANTS.WEBAUTHN_ORIGIN


@dataclass
class CredentialMetadata:
    """Credential metadata - grouped attributes for better organization."""

    created_at: datetime
    last_used_at: datetime | None = None
    device_name: str | None = None
    is_active: bool = True


@dataclass
class WebAuthnCredential:
    """WebAuthn credential model - SOLID principles with composition."""

    credential_id: str
    public_key: str
    sign_count: int
    user_id: str
    metadata: CredentialMetadata


@dataclass
class RelyingPartyInfo:
    """Relying party information - grouped for better organization."""

    rp: dict[str, str | None]
    rp_id: str


@dataclass
class RegistrationCredentialOptions:
    """Credential options for registration - grouped related options."""

    pub_key_cred_params: list[dict]
    exclude_credentials: list[dict]
    authenticator_selection: dict[str, str]
    attestation: str


@dataclass
class WebAuthnRegistrationOptions:
    """WebAuthn registration options - SOLID principles with composition."""

    challenge: str
    relying_party: RelyingPartyInfo
    user: dict[str, str]
    credential_options: RegistrationCredentialOptions
    timeout: int


@dataclass
class WebAuthnAuthenticationOptions:
    """WebAuthn authentication options - Interface Segregation."""

    challenge: str
    timeout: int
    rp_id: str
    allow_credentials: list[dict]
    user_verification: str


class WebAuthnService:
    """WebAuthn service for passwordless authentication - SOLID Dependency Inversion."""

    def __init__(
        self,
        db_session: Session,
        config: WebAuthnConfig | None = None,
        auth_service: AuthService | None = None,
    ):
        """Initialize WebAuthn service with dependency injection - Best practice."""
        self.db_session = db_session
        self.config = config or WebAuthnConfig()
        self.auth_service = auth_service or AuthService(db_session)

        # Challenge storage for registration/authentication flows
        # In production, this should be stored in Redis or similar
        self._pending_challenges: dict[str, dict] = {}

    def generate_registration_options(self, user: User) -> tuple[WebAuthnRegistrationOptions, str]:
        """Generate WebAuthn registration options - Following FIDO2 standards."""
        # Generate secure challenge using DRY constant
        challenge_bytes = secrets.token_bytes(WEBAUTHN_CONSTANTS.CHALLENGE_LENGTH_BYTES)
        challenge = bytes_to_base64url(challenge_bytes)

        # Get existing credentials to exclude
        existing_credentials = self._get_user_credentials(user.id)
        exclude_credentials = [
            {"id": cred.credential_id, "type": "public-key"} for cred in existing_credentials
        ]

        # Generate registration options using webauthn library
        registration_options = generate_registration_options(
            rp_id=self.config.rp_id,
            rp_name=self.config.rp_name,
            user_id=user.id.encode("utf-8"),
            user_name=user.username,
            user_display_name=user.full_name or user.username,
            exclude_credentials=[
                PublicKeyCredentialDescriptor(
                    id=base64url_to_bytes(cred["id"]), type=PublicKeyCredentialType.PUBLIC_KEY
                )
                for cred in exclude_credentials
            ],
            authenticator_selection=AuthenticatorSelectionCriteria(
                user_verification=UserVerificationRequirement.PREFERRED
            ),
            attestation=AttestationConveyancePreference.NONE,
        )

        # Store challenge for verification
        challenge_key = f"reg_{user.id}_{challenge}"
        self._pending_challenges[challenge_key] = {
            "challenge": challenge,
            "user_id": user.id,
            "type": "registration",
            "created_at": datetime.now(UTC),
        }

        # Convert to our model format
        rp_info = RelyingPartyInfo(
            rp={"id": registration_options.rp.id, "name": registration_options.rp.name},
            rp_id=registration_options.rp.id or self.config.rp_id,
        )

        credential_opts = RegistrationCredentialOptions(
            pub_key_cred_params=[
                {"type": param.type, "alg": param.alg}
                for param in registration_options.pub_key_cred_params
            ],
            exclude_credentials=exclude_credentials,
            authenticator_selection={
                "userVerification": str(
                    registration_options.authenticator_selection.user_verification
                    if registration_options.authenticator_selection
                    else "preferred"
                )
            },
            attestation=registration_options.attestation,
        )

        options = WebAuthnRegistrationOptions(
            challenge=bytes_to_base64url(registration_options.challenge),
            relying_party=rp_info,
            user={
                "id": bytes_to_base64url(registration_options.user.id),
                "name": registration_options.user.name,
                "displayName": registration_options.user.display_name,
            },
            credential_options=credential_opts,
            timeout=registration_options.timeout or 60000,
        )

        return options, challenge_key

    def verify_registration_response(
        self,
        credential: RegistrationCredential,
        challenge_key: str,
        device_name: str | None = None,
    ) -> WebAuthnCredential:
        """Verify WebAuthn registration response and store credential."""
        # Retrieve and validate challenge
        if challenge_key not in self._pending_challenges:
            raise ValueError("Invalid or expired challenge")

        challenge_data = self._pending_challenges[challenge_key]
        if challenge_data["type"] != "registration":
            raise ValueError("Challenge type mismatch")

        # Verify registration response
        verification = verify_registration_response(
            credential=credential,
            expected_challenge=base64url_to_bytes(challenge_data["challenge"]),
            expected_origin=self.config.origin,
            expected_rp_id=self.config.rp_id,
        )

        # verification is VerifiedRegistration object, no need for boolean check
        # Create and store credential
        metadata = CredentialMetadata(
            created_at=datetime.now(UTC),
            device_name=device_name,
        )

        webauthn_credential = WebAuthnCredential(
            credential_id=bytes_to_base64url(verification.credential_id),
            public_key=bytes_to_base64url(verification.credential_public_key),
            sign_count=verification.sign_count,
            user_id=challenge_data["user_id"],
            metadata=metadata,
        )

        # Store credential in database
        self._store_credential(webauthn_credential)

        # Clean up challenge
        del self._pending_challenges[challenge_key]

        return webauthn_credential

    def generate_authentication_options(
        self, user: User | None = None
    ) -> tuple[WebAuthnAuthenticationOptions, str]:
        """Generate WebAuthn authentication options - supports usernameless login."""
        # Generate secure challenge using DRY constant
        challenge_bytes = secrets.token_bytes(WEBAUTHN_CONSTANTS.CHALLENGE_LENGTH_BYTES)
        challenge = bytes_to_base64url(challenge_bytes)

        # Get allowed credentials
        if user:
            # User-specific authentication
            credentials = self._get_user_credentials(user.id)
            challenge_key = f"auth_{user.id}_{challenge}"
        else:
            # Usernameless/discoverable authentication
            credentials = []  # Empty list allows any registered credential
            challenge_key = f"auth_any_{challenge}"

        allow_credentials = [
            {"id": cred.credential_id, "type": "public-key"} for cred in credentials
        ]

        # Generate authentication options
        authentication_options = generate_authentication_options(
            rp_id=self.config.rp_id,
            allow_credentials=[
                PublicKeyCredentialDescriptor(
                    id=base64url_to_bytes(cred["id"]), type=PublicKeyCredentialType.PUBLIC_KEY
                )
                for cred in allow_credentials
            ]
            if allow_credentials
            else None,
            user_verification=UserVerificationRequirement.PREFERRED,
        )

        # Store challenge for verification
        self._pending_challenges[challenge_key] = {
            "challenge": challenge,
            "user_id": user.id if user else None,
            "type": "authentication",
            "created_at": datetime.now(UTC),
        }

        # Convert to our model format
        options = WebAuthnAuthenticationOptions(
            challenge=bytes_to_base64url(authentication_options.challenge),
            timeout=authentication_options.timeout or 60000,
            rp_id=authentication_options.rp_id or self.config.rp_id,
            allow_credentials=allow_credentials,
            user_verification=str(authentication_options.user_verification or "preferred"),
        )

        return options, challenge_key

    def verify_authentication_response(
        self, credential: AuthenticationCredential, challenge_key: str
    ) -> tuple[User, WebAuthnCredential]:
        """Verify WebAuthn authentication response and return user."""
        # Retrieve and validate challenge
        if challenge_key not in self._pending_challenges:
            raise ValueError("Invalid or expired challenge")

        challenge_data = self._pending_challenges[challenge_key]
        if challenge_data["type"] != "authentication":
            raise ValueError("Challenge type mismatch")

        # Find credential by ID
        credential_id = bytes_to_base64url(credential.raw_id)
        stored_credential = self._get_credential_by_id(credential_id)

        if not stored_credential or not stored_credential.metadata.is_active:
            raise ValueError("Credential not found or inactive")

        # Verify authentication response
        verification = verify_authentication_response(
            credential=credential,
            expected_challenge=base64url_to_bytes(challenge_data["challenge"]),
            expected_origin=self.config.origin,
            expected_rp_id=self.config.rp_id,
            credential_public_key=base64url_to_bytes(stored_credential.public_key),
            credential_current_sign_count=stored_credential.sign_count,
        )

        # verification is VerifiedAuthentication object, no need for boolean check

        # Update credential usage
        stored_credential.sign_count = verification.new_sign_count
        stored_credential.metadata.last_used_at = datetime.now(UTC)
        self._update_credential(stored_credential)

        # Get authenticated user
        user = self.auth_service.get_user_by_id(stored_credential.user_id)
        if not user or not user.is_active:
            raise ValueError("User not found or inactive")

        # Clean up challenge
        del self._pending_challenges[challenge_key]

        return user, stored_credential

    def get_user_credentials(self, user: User) -> list[WebAuthnCredential]:
        """Get all WebAuthn credentials for a user - Read-only operation."""
        return self._get_user_credentials(user.id)

    def revoke_credential(self, user: User, credential_id: str) -> bool:
        """Revoke a WebAuthn credential - Security operation."""
        credential = self._get_credential_by_id(credential_id)

        if not credential or credential.user_id != user.id:
            return False

        credential.metadata.is_active = False
        self._update_credential(credential)
        return True

    def cleanup_expired_challenges(self, max_age_minutes: int = 10) -> int:
        """Cleanup expired challenges - Maintenance operation."""
        current_time = datetime.now(UTC)
        expired_keys = []

        for key, challenge_data in self._pending_challenges.items():
            age = (current_time - challenge_data["created_at"]).total_seconds() / 60
            if age > max_age_minutes:
                expired_keys.append(key)

        for key in expired_keys:
            del self._pending_challenges[key]

        return len(expired_keys)

    # Private helper methods - Implementation details

    def _get_user_credentials(self, user_id: str) -> list[WebAuthnCredential]:
        """Get user credentials from database - Private implementation."""
        db_credentials = (
            self.db_session.query(WebAuthnCredentialModel)
            .filter(WebAuthnCredentialModel.user_id == user_id)
            .filter(WebAuthnCredentialModel.is_active)
            .order_by(WebAuthnCredentialModel.created_at.desc())
            .all()
        )

        # Convert database models to service models
        return [
            WebAuthnCredential(
                credential_id=db_cred.credential_id,
                public_key=db_cred.public_key,
                sign_count=db_cred.sign_count,
                user_id=db_cred.user_id,
                metadata=CredentialMetadata(
                    created_at=db_cred.created_at,
                    last_used_at=db_cred.last_used_at,
                    device_name=db_cred.device_name,
                    is_active=db_cred.is_active,
                ),
            )
            for db_cred in db_credentials
        ]

    def _get_credential_by_id(self, credential_id: str) -> WebAuthnCredential | None:
        """Get credential by ID from database - Private implementation."""
        db_credential = (
            self.db_session.query(WebAuthnCredentialModel)
            .filter(WebAuthnCredentialModel.credential_id == credential_id)
            .filter(WebAuthnCredentialModel.is_active)
            .first()
        )

        if not db_credential:
            return None

        # Convert database model to service model
        return WebAuthnCredential(
            credential_id=db_credential.credential_id,
            public_key=db_credential.public_key,
            sign_count=db_credential.sign_count,
            user_id=db_credential.user_id,
            metadata=CredentialMetadata(
                created_at=db_credential.created_at,
                last_used_at=db_credential.last_used_at,
                device_name=db_credential.device_name,
                is_active=db_credential.is_active,
            ),
        )

    def _store_credential(self, credential: WebAuthnCredential) -> None:
        """Store credential in database - Private implementation."""

        # Create database model
        db_credential = WebAuthnCredentialModel(
            credential_id=credential.credential_id,
            user_id=credential.user_id,
            public_key=credential.public_key,
            sign_count=credential.sign_count,
            device_name=credential.metadata.device_name,
            is_active=credential.metadata.is_active,
            created_at=credential.metadata.created_at,
            last_used_at=credential.metadata.last_used_at,
        )

        # Store in database
        self.db_session.add(db_credential)
        self.db_session.commit()

    def _update_credential(self, credential: WebAuthnCredential) -> None:
        """Update credential in database - Private implementation."""

        # Find existing credential
        db_credential = (
            self.db_session.query(WebAuthnCredentialModel)
            .filter(WebAuthnCredentialModel.credential_id == credential.credential_id)
            .first()
        )

        if db_credential:
            # Update fields
            db_credential.sign_count = credential.sign_count
            db_credential.last_used_at = credential.metadata.last_used_at
            db_credential.is_active = credential.metadata.is_active
            db_credential.usage_count = db_credential.usage_count + 1

            # Commit changes
            self.db_session.commit()


class PasskeyManager:
    """High-level passkey management service - Facade pattern."""

    def __init__(self, webauthn_service: WebAuthnService):
        """Initialize with WebAuthn service dependency."""
        self.webauthn_service = webauthn_service

    def start_passkey_registration(self, user: User, device_name: str = "Default Device") -> dict:
        """Start passkey registration flow - User-friendly interface."""
        options, challenge_key = self.webauthn_service.generate_registration_options(user)

        return {
            "publicKey": {
                "challenge": options.challenge,
                "rp": options.relying_party.rp,
                "user": options.user,
                "pubKeyCredParams": options.credential_options.pub_key_cred_params,
                "timeout": options.timeout,
                "attestation": options.credential_options.attestation,
                "excludeCredentials": options.credential_options.exclude_credentials,
                "authenticatorSelection": options.credential_options.authenticator_selection,
            },
            "challengeKey": challenge_key,
            "deviceName": device_name,
        }

    def start_passkey_authentication(self, user: User | None = None) -> dict:
        """Start passkey authentication flow - Supports usernameless login."""
        options, challenge_key = self.webauthn_service.generate_authentication_options(user)

        return {
            "publicKey": {
                "challenge": options.challenge,
                "timeout": options.timeout,
                "rpId": options.rp_id,
                "allowCredentials": options.allow_credentials,
                "userVerification": options.user_verification,
            },
            "challengeKey": challenge_key,
        }

    def get_passkey_summary(self, user: User) -> dict:
        """Get user's passkey summary - Dashboard information."""
        credentials = self.webauthn_service.get_user_credentials(user)

        return {
            "total_passkeys": len(credentials),
            "active_passkeys": len([c for c in credentials if c.metadata.is_active]),
            "last_used": max(
                (c.metadata.last_used_at for c in credentials if c.metadata.last_used_at),
                default=None,
            ),
            "devices": [
                {
                    "id": c.credential_id,
                    "name": c.metadata.device_name or "Unknown Device",
                    "created_at": c.metadata.created_at,
                    "last_used_at": c.metadata.last_used_at,
                    "is_active": c.metadata.is_active,
                }
                for c in credentials
            ],
        }
