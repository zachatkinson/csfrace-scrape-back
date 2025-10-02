"""Authentication service layer for database operations."""

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core.decorators import auth_error_handler
from src.core.logging_hierarchy import get_auth_logger

from ..constants import API_DEFAULT_LIMIT
from ..database.models.auth import User as UserTable
from .decorators import with_transaction_rollback
from .models import OAuthUserCreate, User, UserCreate, UserUpdate
from .security import security_manager

logger = get_auth_logger()


class AuthService:
    """Authentication service for user management."""

    def __init__(self, db: Session):
        self.db = db

    @auth_error_handler("get user by username")
    def get_user_by_username(self, username: str) -> User | None:
        """Get user by username."""
        stmt = select(UserTable).where(UserTable.username == username)
        result = self.db.execute(stmt)
        user_row = result.scalar_one_or_none()

        if user_row:
            return User(
                id=user_row.id,
                username=user_row.username,
                email=user_row.email,
                full_name=user_row.full_name,
                is_active=user_row.is_active,
                is_superuser=user_row.is_superuser,
                created_at=user_row.created_at,
            )
        return None

    @auth_error_handler("get user by email")
    def get_user_by_email(self, email: str) -> User | None:
        """Get user by email."""
        stmt = select(UserTable).where(UserTable.email == email)
        result = self.db.execute(stmt)
        user_row = result.scalar_one_or_none()

        if user_row:
            return User(
                id=user_row.id,
                username=user_row.username,
                email=user_row.email,
                full_name=user_row.full_name,
                is_active=user_row.is_active,
                is_superuser=user_row.is_superuser,
                created_at=user_row.created_at,
            )
        return None

    @auth_error_handler("get user by id")
    def get_user_by_id(self, user_id: str) -> User | None:
        """Get user by ID."""
        stmt = select(UserTable).where(UserTable.id == user_id)
        result = self.db.execute(stmt)
        user_row = result.scalar_one_or_none()

        if user_row:
            return User(
                id=user_row.id,
                username=user_row.username,
                email=user_row.email,
                full_name=user_row.full_name,
                is_active=user_row.is_active,
                is_superuser=user_row.is_superuser,
                created_at=user_row.created_at,
            )
        return None

    def create_user(self, user_create: UserCreate | OAuthUserCreate) -> User:
        """Create new user (supports both password and OAuth users)."""
        # Check if user already exists
        existing = self.get_user_by_email(user_create.email)
        if existing:
            logger.warning("Attempt to create user with existing email", email=user_create.email)
            raise ValueError(f"User with email {user_create.email} already exists")

        # Check username uniqueness
        existing = self.get_user_by_username(user_create.username)
        if existing:
            logger.warning(
                "Attempt to create user with existing username", username=user_create.username
            )
            raise ValueError(f"Username {user_create.username} already taken")

        # The database operations are handled by the helper method
        return self._create_user_in_database_safe(user_create)

    @with_transaction_rollback
    @auth_error_handler("create user in database")
    def _create_user_in_database_safe(self, user_create: UserCreate | OAuthUserCreate) -> User:
        """Create user in database with error handling."""
        # Generate user ID
        user_id = str(uuid4())

        # Hash password (only for regular users, not OAuth)
        if isinstance(user_create, UserCreate):
            hashed_password = security_manager.get_password_hash(user_create.password)
        else:
            # OAuth users don't have passwords
            hashed_password = None

        # Create user in database
        user_data = UserTable(
            id=user_id,
            username=user_create.username,
            email=user_create.email,
            full_name=user_create.full_name,
            hashed_password=hashed_password,
            is_active=True,
            is_superuser=False,
            is_verified=True,  # OAuth users are auto-verified
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        self.db.add(user_data)
        self.db.commit()
        self.db.refresh(user_data)

        logger.info("User created successfully", user_id=user_id, username=user_create.username)

        return User(
            id=user_data.id,
            username=user_data.username,
            email=user_data.email,
            full_name=user_data.full_name,
            is_active=user_data.is_active,
            is_superuser=user_data.is_superuser,
            created_at=user_data.created_at,
        )

    @with_transaction_rollback
    @auth_error_handler("update user")
    def update_user(self, user_id: str, user_update: UserUpdate) -> User | None:
        """Update user information with complete database integration."""
        stmt = select(UserTable).where(UserTable.id == user_id)
        result = self.db.execute(stmt)
        user_row = result.scalar_one_or_none()

        if not user_row:
            logger.warning("User not found for update", user_id=user_id)
            return None

        # Apply updates from UserUpdate model
        update_data = user_update.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            if hasattr(user_row, field):
                setattr(user_row, field, value)

        # Update timestamp
        user_row.updated_at = datetime.now(UTC)

        self.db.commit()
        self.db.refresh(user_row)

        logger.info(
            "User updated successfully", user_id=user_id, updated_fields=list(update_data.keys())
        )

        return User(
            id=user_row.id,
            username=user_row.username,
            email=user_row.email,
            full_name=user_row.full_name,
            is_active=user_row.is_active,
            is_superuser=user_row.is_superuser,
            created_at=user_row.created_at,
        )

    @with_transaction_rollback
    @auth_error_handler("update last login")
    def update_last_login(self, user_id: str) -> bool:
        """Update user's last login timestamp for OAuth authentication."""
        stmt = select(UserTable).where(UserTable.id == user_id)
        result = self.db.execute(stmt)
        user_row = result.scalar_one_or_none()

        if not user_row:
            logger.warning("User not found for login update", user_id=user_id)
            return False

        user_row.last_login = datetime.now(UTC)
        user_row.updated_at = datetime.now(UTC)

        self.db.commit()

        logger.info("Last login updated successfully", user_id=user_id)
        return True

    @auth_error_handler("list users")
    def list_users(self, skip: int = 0, limit: int = API_DEFAULT_LIMIT) -> list[User]:
        """List users with pagination for OAuth/SSO management."""
        stmt = select(UserTable).offset(skip).limit(limit).order_by(UserTable.created_at.desc())
        result = self.db.execute(stmt)
        user_rows = result.scalars().all()

        users = [
            User(
                id=user_row.id,
                username=user_row.username,
                email=user_row.email,
                full_name=user_row.full_name,
                is_active=user_row.is_active,
                is_superuser=user_row.is_superuser,
                created_at=user_row.created_at,
                last_login=user_row.last_login,
            )
            for user_row in user_rows
        ]

        logger.info("Users listed successfully", count=len(users), skip=skip, limit=limit)
        return users

    @with_transaction_rollback
    @auth_error_handler("deactivate user")
    def deactivate_user(self, user_id: str) -> bool:
        """Deactivate user account for OAuth/SSO users."""
        stmt = select(UserTable).where(UserTable.id == user_id)
        result = self.db.execute(stmt)
        user_row = result.scalar_one_or_none()

        if not user_row:
            logger.warning("User not found for deactivation", user_id=user_id)
            return False

        if not user_row.is_active:
            logger.warning("User already deactivated", user_id=user_id)
            return True

        user_row.is_active = False
        user_row.updated_at = datetime.now(UTC)

        self.db.commit()

        logger.info("User deactivated successfully", user_id=user_id, username=user_row.username)
        return True

    @with_transaction_rollback
    @auth_error_handler("delete user account")
    def delete_user_account(self, user_id: str) -> bool:
        """Permanently delete user account and all associated data.

        This method performs a complete account deletion including:
        - User record
        - Linked OAuth accounts (cascade delete)
        - WebAuthn credentials (cascade delete)
        - User settings (cascade delete)
        - Preserves scraping jobs (for audit/historical purposes)

        Args:
            user_id: The ID of the user to delete

        Returns:
            bool: True if user was deleted successfully, False if user not found

        Raises:
            Exception: If database operation fails
        """
        # Find the user first
        stmt = select(UserTable).where(UserTable.id == user_id)
        result = self.db.execute(stmt)
        user_row = result.scalar_one_or_none()

        if not user_row:
            logger.warning("User not found for deletion", user_id=user_id)
            return False

        # Log the deletion for audit purposes
        logger.info(
            "Deleting user account",
            user_id=user_id,
            username=user_row.username,
            email=user_row.email,
        )

        # Delete the user - cascades will handle related records
        # Note: scraping_jobs relationship has no cascade, so jobs are preserved
        self.db.delete(user_row)
        self.db.commit()

        logger.info("User account deleted successfully", user_id=user_id)
        return True

    @auth_error_handler("authenticate user")
    def authenticate_user(self, username: str, password: str) -> User | None:
        """Authenticate user with username/email and password.

        Args:
            username: Username or email address
            password: Plain text password

        Returns:
            User: Authenticated user if credentials are valid, None otherwise
        """
        # Try to find user by username or email
        user = self.get_user_by_username(username)
        if not user:
            user = self.get_user_by_email(username)

        if not user:
            logger.warning("Authentication failed: user not found", username=username)
            return None

        # Check if user is active
        if not user.is_active:
            logger.warning("Authentication failed: user is inactive", username=username)
            return None

        # Verify password using security manager
        from .security import security_manager

        # Get password hash from database model using user.id
        user_row = self.db.execute(
            select(UserTable).where(UserTable.id == user.id)
        ).scalar_one_or_none()
        if not user_row:
            logger.warning("Authentication failed: user not found in database", username=username)
            return None

        if not security_manager.verify_password(password, user_row.hashed_password):  # type: ignore[arg-type]
            logger.warning("Authentication failed: invalid password", username=username)
            return None

        logger.info("User authenticated successfully", user_id=user.id, username=user.username)
        return user

    @with_transaction_rollback
    @auth_error_handler("change user password")
    def change_password(self, user_id: str, old_password: str, new_password: str) -> bool:
        """Change user password after verifying old password.

        Args:
            user_id: User ID
            old_password: Current password
            new_password: New password

        Returns:
            bool: True if password was changed successfully
        """
        # Find user
        user = self.get_user_by_id(user_id)
        if not user:
            logger.warning("Password change failed: user not found", user_id=user_id)
            return False

        # Verify old password using database model
        from .security import security_manager

        user_row = self.db.execute(
            select(UserTable).where(UserTable.id == user_id)
        ).scalar_one_or_none()
        if not user_row:
            logger.warning("Password change failed: user not found in database", user_id=user_id)
            return False

        if not security_manager.verify_password(old_password, user_row.hashed_password):  # type: ignore[arg-type]
            logger.warning("Password change failed: invalid old password", user_id=user_id)
            return False

        # Hash new password and update (reuse existing user_row)
        new_password_hash = security_manager.get_password_hash(new_password)

        user_row.hashed_password = new_password_hash  # type: ignore[attr-defined]
        user_row.updated_at = datetime.now(UTC)
        self.db.commit()
        logger.info("Password changed successfully", user_id=user_id)
        return True
