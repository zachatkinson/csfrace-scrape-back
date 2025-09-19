"""Authentication service layer for database operations."""

from datetime import UTC, datetime
from uuid import uuid4

import structlog
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..constants import API_DEFAULT_LIMIT
from ..database.models import User as UserTable
from .models import OAuthUserCreate, User, UserCreate, UserInDB, UserUpdate
from .security import security_manager

logger = structlog.get_logger(__name__)


class AuthService:
    """Authentication service for user management."""

    def __init__(self, db: Session):
        self.db = db

    def get_user_by_username(self, username: str) -> User | None:
        """Get user by username."""
        try:
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
        except Exception as e:
            logger.error("Error fetching user by username", username=username, error=str(e))
            return None

    def get_user_by_email(self, email: str) -> User | None:
        """Get user by email."""
        try:
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
        except Exception as e:
            logger.error("Error fetching user by email", email=email, error=str(e))
            return None

    def get_user_by_id(self, user_id: str) -> User | None:
        """Get user by ID."""
        try:
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
        except Exception as e:
            logger.error("Error fetching user by id", user_id=user_id, error=str(e))
            return None

    def create_user(self, user_create: UserCreate | OAuthUserCreate) -> User:
        """Create new user (supports both password and OAuth users)."""
        try:
            # Check if user already exists
            existing = self.get_user_by_email(user_create.email)
            if existing:
                logger.warning(
                    "Attempt to create user with existing email", email=user_create.email
                )
                raise ValueError(f"User with email {user_create.email} already exists")

            # Check username uniqueness
            existing = self.get_user_by_username(user_create.username)
            if existing:
                logger.warning(
                    "Attempt to create user with existing username", username=user_create.username
                )
                raise ValueError(f"Username {user_create.username} already taken")

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

        except ValueError:
            raise
        except Exception as e:
            logger.error("Error creating user", username=user_create.username, error=str(e))
            self.db.rollback()
            raise RuntimeError(f"Failed to create user: {str(e)}") from e

    def update_user(self, _user_id: str, _user_update: UserUpdate) -> User | None:
        """Update user information."""
        # Placeholder implementation - database integration pending
        # Production implementation will update User table:
        # stmt = select(UserTable).where(UserTable.id == user_id)
        # result = self.db.execute(stmt)
        # user_row = result.scalar_one_or_none()
        #
        # if not user_row:
        #     return None
        #
        # update_data = user_update.dict(exclude_unset=True)
        # for field, value in update_data.items():
        #     setattr(user_row, field, value)
        #
        # self.db.commit()
        # self.db.refresh(user_row)
        # return User.from_orm(user_row)
        return None

    def authenticate_user(self, _username: str, _password: str) -> UserInDB | None:
        """Authenticate user with username and password."""
        # Placeholder implementation - database integration pending
        # Production implementation will query User table and verify password:
        # stmt = select(UserTable).where(UserTable.username == username)
        # result = self.db.execute(stmt)
        # user_row = result.scalar_one_or_none()
        #
        # if not user_row:
        #     return None
        #
        # user_in_db = UserInDB.from_orm(user_row)
        #
        # # Verify password
        # if not security_manager.verify_password(password, user_in_db.hashed_password):
        #     return None
        #
        # # Update last login
        # user_row.last_login = datetime.now(timezone.utc)
        # self.db.commit()
        #
        # return user_in_db
        return None

    def change_password(self, _user_id: str, _new_password: str) -> bool:
        """Change user password."""
        # Placeholder implementation - database integration pending
        # Production implementation will update User password:
        # stmt = select(UserTable).where(UserTable.id == user_id)
        # result = self.db.execute(stmt)
        # user_row = result.scalar_one_or_none()
        #
        # if not user_row:
        #     return False
        #
        # user_row.hashed_password = security_manager.get_password_hash(new_password)
        # self.db.commit()
        # return True
        return False

    def list_users(self, _skip: int = 0, _limit: int = API_DEFAULT_LIMIT) -> list[User]:
        """List users with pagination."""
        # Placeholder implementation - database integration pending
        # Production implementation will query User table with pagination:
        # stmt = select(UserTable).offset(skip).limit(limit)
        # result = self.db.execute(stmt)
        # user_rows = result.scalars().all()
        # return [User.from_orm(user_row) for user_row in user_rows]
        return []

    def deactivate_user(self, _user_id: str) -> bool:
        """Deactivate user account."""
        # Placeholder implementation - database integration pending
        # Production implementation will deactivate User:
        # stmt = select(UserTable).where(UserTable.id == user_id)
        # result = self.db.execute(stmt)
        # user_row = result.scalar_one_or_none()
        #
        # if not user_row:
        #     return False
        #
        # user_row.is_active = False
        # self.db.commit()
        # return True
        return False
