"""Account Merge Service following SOLID principles - Single Responsibility.

This service handles detection, validation, and execution of account merging when
a user attempts to link an OAuth provider that's already associated with a different account.

SOLID Principles Applied:
- Single Responsibility: Only handles account merging logic
- Open/Closed: Extensible for different merge strategies
- Liskov Substitution: Clear interfaces for merge operations
- Interface Segregation: Separate detector, validator, executor
- Dependency Inversion: Depends on abstractions, injects dependencies
"""

import secrets
from abc import ABC, abstractmethod
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from sqlalchemy.orm import Session

from src.core.decorators import auth_error_handler
from src.core.logging_hierarchy import get_auth_logger
from src.database.models.auth import LinkedAccount as LinkedAccountDB, User as UserTable

from .models import (
    AccountMergeDetection,
    AccountMergeRequest,
    AccountMergeResult,
    DuplicateAccountInfo,
    MergeAuditLog,
    OAuthProvider,
    OAuthUserInfo,
)
from .service import AuthService

logger = get_auth_logger()

# Merge token configuration
MERGE_TOKEN_SECRET = secrets.token_urlsafe(32)  # In production, load from environment
MERGE_TOKEN_EXPIRY_MINUTES = 15  # Merge must be confirmed within 15 minutes


class IMergeDetector(ABC):
    """Interface Segregation: Separate interface for merge detection."""

    @abstractmethod
    def detect_duplicate_account(
        self, current_user_id: str, oauth_user_info: OAuthUserInfo
    ) -> UserTable | None:
        """Detect if OAuth account belongs to a different user."""


class IMergeValidator(ABC):
    """Interface Segregation: Separate interface for merge validation."""

    @abstractmethod
    def validate_merge_token(self, merge_token: str) -> dict[str, Any]:
        """Validate and decode merge token."""

    @abstractmethod
    def can_merge_accounts(self, source_user_id: str, target_user_id: str) -> tuple[bool, str]:
        """Validate if accounts can be merged."""


class IMergeExecutor(ABC):
    """Interface Segregation: Separate interface for merge execution."""

    @abstractmethod
    def execute_merge(
        self, source_user: UserTable, target_user: UserTable, trigger_provider: OAuthProvider
    ) -> AccountMergeResult:
        """Execute account merge operation."""


class MergeTokenGenerator:
    """Single Responsibility: Generate and validate merge tokens using JWT."""

    @staticmethod
    def generate_merge_token(
        current_user_id: str,
        duplicate_user_id: str,
        provider: OAuthProvider,
        provider_id: str,
    ) -> str:
        """Generate secure JWT token for merge confirmation."""
        payload = {
            "current_user_id": current_user_id,
            "duplicate_user_id": duplicate_user_id,
            "provider": provider.value,
            "provider_id": provider_id,
            "exp": datetime.now(UTC) + timedelta(minutes=MERGE_TOKEN_EXPIRY_MINUTES),
            "iat": datetime.now(UTC),
            "jti": secrets.token_urlsafe(16),  # Unique token ID
        }

        token = jwt.encode(payload, MERGE_TOKEN_SECRET, algorithm="HS256")
        logger.info(
            "Merge token generated",
            current_user_id=current_user_id,
            duplicate_user_id=duplicate_user_id,
            provider=provider.value,
        )
        return token

    @staticmethod
    def validate_merge_token(merge_token: str) -> dict[str, Any]:
        """Validate and decode merge token."""
        try:
            payload: dict[str, Any] = jwt.decode(
                merge_token, MERGE_TOKEN_SECRET, algorithms=["HS256"]
            )
            logger.debug("Merge token validated successfully", jti=payload.get("jti"))
            return payload
        except jwt.ExpiredSignatureError:
            logger.warning("Merge token expired")
            raise ValueError("Merge token has expired. Please restart the linking process.")
        except jwt.InvalidTokenError as e:
            logger.warning("Invalid merge token", error=str(e))
            raise ValueError("Invalid merge token")


class MergeDetector(IMergeDetector):
    """Single Responsibility: Detect duplicate accounts for merging."""

    def __init__(self, db_session: Session):
        self.db_session = db_session

    @auth_error_handler("detect duplicate account")
    def detect_duplicate_account(
        self, current_user_id: str, oauth_user_info: OAuthUserInfo
    ) -> UserTable | None:
        """Detect if this OAuth account is already linked to a different user.

        Args:
            current_user_id: ID of the currently logged-in user
            oauth_user_info: OAuth user information from provider

        Returns:
            UserTable if duplicate found, None otherwise
        """
        # Query for linked account with this provider_id belonging to a DIFFERENT user
        duplicate_link = (
            self.db_session.query(LinkedAccountDB)
            .filter(
                LinkedAccountDB.provider == oauth_user_info.provider.value.lower(),
                LinkedAccountDB.provider_account_id == oauth_user_info.provider_id,
                LinkedAccountDB.user_id != current_user_id,  # Different user!
            )
            .first()
        )

        if duplicate_link:
            # Get the full user record
            duplicate_user = (
                self.db_session.query(UserTable)
                .filter(UserTable.id == duplicate_link.user_id)
                .first()
            )

            if duplicate_user:
                logger.info(
                    "Duplicate account detected for merge",
                    current_user_id=current_user_id,
                    duplicate_user_id=duplicate_user.id,
                    provider=oauth_user_info.provider.value,
                )
                return duplicate_user

        return None


class MergeValidator(IMergeValidator):
    """Single Responsibility: Validate merge operations."""

    def __init__(self, db_session: Session):
        self.db_session = db_session

    def validate_merge_token(self, merge_token: str) -> dict[str, Any]:
        """Delegate to token generator for validation."""
        return MergeTokenGenerator.validate_merge_token(merge_token)

    @auth_error_handler("validate merge compatibility")
    def can_merge_accounts(self, source_user_id: str, target_user_id: str) -> tuple[bool, str]:
        """Validate if accounts can be safely merged.

        Args:
            source_user_id: User account to be merged (will be deleted)
            target_user_id: User account to keep (will receive all data)

        Returns:
            Tuple of (can_merge: bool, reason: str)
        """
        # Check both users exist
        source_user = (
            self.db_session.query(UserTable).filter(UserTable.id == source_user_id).first()
        )
        target_user = (
            self.db_session.query(UserTable).filter(UserTable.id == target_user_id).first()
        )

        if not source_user:
            return False, "Source user not found"
        if not target_user:
            return False, "Target user not found"

        # Check if users are the same (shouldn't happen)
        if source_user_id == target_user_id:
            return False, "Cannot merge account with itself"

        # Additional validation could be added here:
        # - Check for conflicting data
        # - Verify no circular dependencies
        # - Check business rules

        logger.debug(
            "Merge validation passed",
            source_user_id=source_user_id,
            target_user_id=target_user_id,
        )
        return True, "Accounts can be merged"


class MergeExecutor(IMergeExecutor):
    """Single Responsibility: Execute account merge operations."""

    def __init__(self, db_session: Session):
        self.db_session = db_session

    @auth_error_handler("execute account merge")
    def execute_merge(
        self, source_user: UserTable, target_user: UserTable, trigger_provider: OAuthProvider
    ) -> AccountMergeResult:
        """Execute account merge - Transfer all data from source to target, delete source.

        SOLID: Single Transaction Pattern - All or nothing operation.

        Args:
            source_user: User account to be deleted
            target_user: User account to keep
            trigger_provider: OAuth provider that triggered the merge

        Returns:
            AccountMergeResult with merge details
        """
        logger.info(
            "Starting account merge execution",
            source_user_id=source_user.id,
            target_user_id=target_user.id,
            trigger_provider=trigger_provider.value,
        )

        transferred_providers = []

        try:
            # Step 1: Transfer all linked OAuth accounts from source to target
            linked_accounts = (
                self.db_session.query(LinkedAccountDB)
                .filter(LinkedAccountDB.user_id == source_user.id)
                .all()
            )

            for linked_account in linked_accounts:
                # Check if target already has this provider linked
                existing_link = (
                    self.db_session.query(LinkedAccountDB)
                    .filter(
                        LinkedAccountDB.user_id == target_user.id,
                        LinkedAccountDB.provider == linked_account.provider,
                    )
                    .first()
                )

                if existing_link:
                    # Target already has this provider, skip (shouldn't happen often)
                    logger.warning(
                        "Skipping duplicate provider during merge",
                        provider=linked_account.provider,
                        target_user_id=target_user.id,
                    )
                    # Delete the source's duplicate link
                    self.db_session.delete(linked_account)
                else:
                    # Transfer the linked account to target user
                    linked_account.user_id = target_user.id
                    linked_account.updated_at = datetime.now(UTC)
                    transferred_providers.append(OAuthProvider(linked_account.provider))

                    logger.info(
                        "Transferred OAuth link to target user",
                        provider=linked_account.provider,
                        from_user=source_user.id,
                        to_user=target_user.id,
                    )

            # Step 2: Delete the source user account
            self.db_session.delete(source_user)

            # Step 3: Commit transaction - all or nothing
            self.db_session.commit()

            logger.info(
                "Account merge completed successfully",
                source_user_id=source_user.id,
                target_user_id=target_user.id,
                transferred_providers=[p.value for p in transferred_providers],
            )

            # Step 4: Return result
            return AccountMergeResult(
                success=True,
                message=f"Successfully merged accounts. {len(transferred_providers)} OAuth provider(s) transferred.",
                merged_user_id=target_user.id,
                deleted_user_id=source_user.id,
                transferred_providers=transferred_providers,
                merge_timestamp=datetime.now(UTC),
            )

        except Exception as e:
            # Rollback on any error
            self.db_session.rollback()
            logger.error(
                "Account merge failed, transaction rolled back",
                source_user_id=source_user.id,
                target_user_id=target_user.id,
                error=str(e),
            )
            raise


class AccountMergeService:
    """Dependency Inversion: Main service coordinates merge operations via injected components.

    This service follows the Facade pattern to provide a simple interface for complex
    account merging operations while maintaining SOLID principles.
    """

    def __init__(
        self,
        db_session: Session,
        auth_service: AuthService,
        detector: IMergeDetector | None = None,
        validator: IMergeValidator | None = None,
        executor: IMergeExecutor | None = None,
    ):
        """Dependency Injection: Components can be overridden for testing."""
        self.db_session = db_session
        self.auth_service = auth_service

        # Default implementations (Dependency Inversion)
        self.detector = detector or MergeDetector(db_session)
        self.validator = validator or MergeValidator(db_session)
        self.executor = executor or MergeExecutor(db_session)

    @auth_error_handler("check for account merge")
    def check_merge_required(
        self, current_user_id: str, oauth_user_info: OAuthUserInfo
    ) -> AccountMergeDetection | None:
        """Check if account merge is required when linking OAuth provider.

        Returns:
            AccountMergeDetection if duplicate found, None otherwise
        """
        # Detect duplicate account
        duplicate_user = self.detector.detect_duplicate_account(current_user_id, oauth_user_info)

        if not duplicate_user:
            return None

        # Get current user info
        current_user = self.auth_service.get_user_by_id(current_user_id)
        if not current_user:
            raise ValueError("Current user not found")

        # Get linked providers for both accounts
        current_providers = self._get_linked_providers(current_user_id)
        duplicate_providers = self._get_linked_providers(duplicate_user.id)

        # Generate merge token
        merge_token = MergeTokenGenerator.generate_merge_token(
            current_user_id=current_user_id,
            duplicate_user_id=duplicate_user.id,
            provider=oauth_user_info.provider,
            provider_id=oauth_user_info.provider_id,
        )

        # Build response
        return AccountMergeDetection(
            merge_required=True,
            message=f"This {oauth_user_info.provider.value} account is already linked to another account ({duplicate_user.email}). "
            f"Would you like to merge these accounts?",
            current_account=DuplicateAccountInfo(
                user_id=current_user.id,
                username=current_user.username,
                email=current_user.email,
                created_at=datetime.fromisoformat(str(current_user.created_at)),
                linked_providers=current_providers,
            ),
            duplicate_account=DuplicateAccountInfo(
                user_id=duplicate_user.id,
                username=duplicate_user.username,
                email=duplicate_user.email,
                created_at=duplicate_user.created_at,
                linked_providers=duplicate_providers,
            ),
            provider_to_link=oauth_user_info.provider,
            merge_token=merge_token,
        )

    @auth_error_handler("execute account merge")
    def merge_accounts(
        self, merge_request: AccountMergeRequest, initiated_by_user_id: str
    ) -> AccountMergeResult:
        """Execute account merge after user confirmation.

        Args:
            merge_request: Validated merge request with token
            initiated_by_user_id: ID of user who initiated the merge

        Returns:
            AccountMergeResult with merge details
        """
        # Validate merge token
        token_data = self.validator.validate_merge_token(merge_request.merge_token)

        # Extract user IDs from token
        target_user_id = token_data["current_user_id"]  # User to keep
        source_user_id = token_data["duplicate_user_id"]  # User to delete
        trigger_provider = OAuthProvider(token_data["provider"])

        # Validate user confirmation
        if not merge_request.confirm_merge:
            raise ValueError("User must confirm merge operation")

        # Validate initiated by correct user
        if initiated_by_user_id != target_user_id:
            raise ValueError("Merge can only be initiated by the target user")

        # Validate accounts can be merged
        can_merge, reason = self.validator.can_merge_accounts(source_user_id, target_user_id)
        if not can_merge:
            raise ValueError(f"Cannot merge accounts: {reason}")

        # Get user records
        source_user = (
            self.db_session.query(UserTable).filter(UserTable.id == source_user_id).first()
        )
        target_user = (
            self.db_session.query(UserTable).filter(UserTable.id == target_user_id).first()
        )

        if not source_user or not target_user:
            raise ValueError("User records not found")

        # Execute merge
        result = self.executor.execute_merge(source_user, target_user, trigger_provider)

        # Create audit log
        audit_log = MergeAuditLog(
            target_user_id=target_user_id,
            source_user_id=source_user_id,
            initiated_by_user_id=initiated_by_user_id,
            trigger_provider=trigger_provider,
            transferred_providers=result.transferred_providers,
            merge_timestamp=result.merge_timestamp,
            client_ip=None,
            user_agent=None,
        )

        logger.info(
            "Account merge audit log created",
            audit_log=audit_log.model_dump(),
        )

        return result

    def _get_linked_providers(self, user_id: str) -> list[OAuthProvider]:
        """Helper: Get list of OAuth providers linked to user."""
        linked_accounts = (
            self.db_session.query(LinkedAccountDB).filter(LinkedAccountDB.user_id == user_id).all()
        )

        return [OAuthProvider(account.provider) for account in linked_accounts]
