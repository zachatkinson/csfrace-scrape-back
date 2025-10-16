"""Unit tests for AuthService following TEST_BUILDING.md MANDATORY standards.

MANDATORY COMPLIANCE:
- AAA Pattern (Arrange-Act-Assert) - NON-NEGOTIABLE
- SOLID principles testing
- Factory Pattern for test data
- 85%+ coverage target
- PostgreSQL ONLY for database tests

Tests AuthService database operations.
"""

from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from src.auth.models import OAuthUserCreate, UserCreate, UserUpdate
from src.auth.service import AuthService
from src.database.models.auth import User as UserTable

# ============================================================================
# MANDATORY Fixtures Following TEST_BUILDING.md Factory Pattern
# ============================================================================


@pytest.fixture
def user_create_password() -> UserCreate:
    """Factory for password-based user creation - DRY principle."""
    return UserCreate(
        username="testuser",
        email="test@example.com",
        password="SecurePass123!",
        full_name="Test User",
    )


@pytest.fixture
def user_create_oauth() -> OAuthUserCreate:
    """Factory for OAuth user creation - DRY principle."""
    return OAuthUserCreate(
        username="oauth_user",
        email="oauth@example.com",
        full_name="OAuth User",
    )


@pytest.fixture
def user_update_partial() -> UserUpdate:
    """Factory for partial user update."""
    return UserUpdate(full_name="Updated Name")


@pytest.fixture
def user_update_full() -> UserUpdate:
    """Factory for full user update."""
    return UserUpdate(
        email="updated@example.com",
        full_name="Updated Full Name",
        is_active=True,
    )


# ============================================================================
# Test Suite 1: Initialization (1 test)
# ============================================================================


class TestAuthServiceInit:
    """Test AuthService initialization."""

    @pytest.mark.unit
    def test_auth_service_init(self, test_session: Session) -> None:
        """Test AuthService initializes with database session."""
        # Arrange & Act
        service = AuthService(db=test_session)

        # Assert
        assert service.db == test_session


# ============================================================================
# Test Suite 2: get_user_by_username (3 tests) - Lines 27-44
# ============================================================================


class TestGetUserByUsername:
    """Test get user by username lookup - Lines 27-44."""

    @pytest.mark.integration
    def test_get_user_by_username_exists(
        self, test_session: Session, user_create_password: UserCreate
    ) -> None:
        """Test get_user_by_username returns user when exists."""
        # Arrange
        service = AuthService(db=test_session)
        created_user = service.create_user(user_create_password)

        # Act
        result = service.get_user_by_username(user_create_password.username)

        # Assert
        assert result is not None
        assert result.id == created_user.id
        assert result.username == user_create_password.username
        assert result.email == user_create_password.email

    @pytest.mark.unit
    def test_get_user_by_username_not_exists(self, test_session: Session) -> None:
        """Test get_user_by_username returns None when user not found."""
        # Arrange
        service = AuthService(db=test_session)

        # Act
        result = service.get_user_by_username("nonexistent_user")

        # Assert
        assert result is None

    @pytest.mark.integration
    def test_get_user_by_username_case_sensitive(
        self, test_session: Session, user_create_password: UserCreate
    ) -> None:
        """Test get_user_by_username is case-sensitive."""
        # Arrange
        service = AuthService(db=test_session)
        service.create_user(user_create_password)

        # Act - Try with different case
        result = service.get_user_by_username(user_create_password.username.upper())

        # Assert - Should not find user (case-sensitive)
        assert result is None


# ============================================================================
# Test Suite 3: get_user_by_email (3 tests) - Lines 46-63
# ============================================================================


class TestGetUserByEmail:
    """Test get user by email lookup - Lines 46-63."""

    @pytest.mark.integration
    def test_get_user_by_email_exists(
        self, test_session: Session, user_create_password: UserCreate
    ) -> None:
        """Test get_user_by_email returns user when exists."""
        # Arrange
        service = AuthService(db=test_session)
        created_user = service.create_user(user_create_password)

        # Act
        result = service.get_user_by_email(user_create_password.email)

        # Assert
        assert result is not None
        assert result.id == created_user.id
        assert result.email == user_create_password.email

    @pytest.mark.unit
    def test_get_user_by_email_not_exists(self, test_session: Session) -> None:
        """Test get_user_by_email returns None when user not found."""
        # Arrange
        service = AuthService(db=test_session)

        # Act
        result = service.get_user_by_email("nonexistent@example.com")

        # Assert
        assert result is None

    @pytest.mark.integration
    def test_get_user_by_email_case_sensitive(
        self, test_session: Session, user_create_password: UserCreate
    ) -> None:
        """Test get_user_by_email is case-sensitive."""
        # Arrange
        service = AuthService(db=test_session)
        service.create_user(user_create_password)

        # Act - Try with different case
        result = service.get_user_by_email(user_create_password.email.upper())

        # Assert - Should not find user (case-sensitive)
        assert result is None


# ============================================================================
# Test Suite 4: get_user_by_id (2 tests) - Lines 65-82
# ============================================================================


class TestGetUserById:
    """Test get user by ID lookup - Lines 65-82."""

    @pytest.mark.integration
    def test_get_user_by_id_exists(
        self, test_session: Session, user_create_password: UserCreate
    ) -> None:
        """Test get_user_by_id returns user when exists."""
        # Arrange
        service = AuthService(db=test_session)
        created_user = service.create_user(user_create_password)

        # Act
        result = service.get_user_by_id(created_user.id)

        # Assert
        assert result is not None
        assert result.id == created_user.id
        assert result.username == user_create_password.username

    @pytest.mark.unit
    def test_get_user_by_id_not_exists(self, test_session: Session) -> None:
        """Test get_user_by_id returns None when user not found."""
        # Arrange
        service = AuthService(db=test_session)
        non_existent_id = str(uuid4())

        # Act
        result = service.get_user_by_id(non_existent_id)

        # Assert
        assert result is None


# ============================================================================
# Test Suite 5: create_user (8 tests) - Lines 84-145
# ============================================================================


class TestCreateUser:
    """Test user creation for both password and OAuth users."""

    @pytest.mark.integration
    def test_create_user_password_success(
        self, test_session: Session, user_create_password: UserCreate
    ) -> None:
        """Test create_user successfully creates password-based user."""
        # Arrange
        service = AuthService(db=test_session)

        # Act
        result = service.create_user(user_create_password)

        # Assert
        assert result is not None
        assert result.username == user_create_password.username
        assert result.email == user_create_password.email
        assert result.full_name == user_create_password.full_name
        assert result.is_active is True
        assert result.is_superuser is False
        assert result.created_at is not None

    @pytest.mark.integration
    def test_create_user_oauth_success(
        self, test_session: Session, user_create_oauth: OAuthUserCreate
    ) -> None:
        """Test create_user successfully creates OAuth user."""
        # Arrange
        service = AuthService(db=test_session)

        # Act
        result = service.create_user(user_create_oauth)

        # Assert
        assert result is not None
        assert result.username == user_create_oauth.username
        assert result.email == user_create_oauth.email
        assert result.full_name == user_create_oauth.full_name

    @pytest.mark.integration
    def test_create_user_duplicate_email(
        self, test_session: Session, user_create_password: UserCreate
    ) -> None:
        """Test create_user fails with duplicate email."""
        # Arrange
        service = AuthService(db=test_session)
        service.create_user(user_create_password)

        # Create duplicate with same email but different username
        duplicate = UserCreate(
            username="different_user",
            email=user_create_password.email,  # Same email
            password="SecurePass456!",
            full_name="Different User",
        )

        # Act & Assert
        with pytest.raises(ValueError, match="already exists"):
            service.create_user(duplicate)

    @pytest.mark.integration
    def test_create_user_duplicate_username(
        self, test_session: Session, user_create_password: UserCreate
    ) -> None:
        """Test create_user fails with duplicate username."""
        # Arrange
        service = AuthService(db=test_session)
        service.create_user(user_create_password)

        # Create duplicate with same username but different email
        duplicate = UserCreate(
            username=user_create_password.username,  # Same username
            email="different@example.com",
            password="SecurePass456!",
            full_name="Different User",
        )

        # Act & Assert
        with pytest.raises(ValueError, match="already taken"):
            service.create_user(duplicate)

    @pytest.mark.integration
    def test_create_user_password_hashed(
        self, test_session: Session, user_create_password: UserCreate
    ) -> None:
        """Test create_user hashes password for password-based users."""
        # Arrange
        service = AuthService(db=test_session)

        # Act
        created_user = service.create_user(user_create_password)

        # Assert - Password should be hashed in database
        user_row = test_session.query(UserTable).filter(UserTable.id == created_user.id).first()
        assert user_row is not None
        assert user_row.hashed_password is not None
        assert user_row.hashed_password != user_create_password.password

    @pytest.mark.integration
    def test_create_user_oauth_no_password(
        self, test_session: Session, user_create_oauth: OAuthUserCreate
    ) -> None:
        """Test create_user does not store password for OAuth users."""
        # Arrange
        service = AuthService(db=test_session)

        # Act
        created_user = service.create_user(user_create_oauth)

        # Assert - OAuth user should have no password
        user_row = test_session.query(UserTable).filter(UserTable.id == created_user.id).first()
        assert user_row is not None
        assert user_row.hashed_password is None

    @pytest.mark.integration
    def test_create_user_sets_defaults(
        self, test_session: Session, user_create_password: UserCreate
    ) -> None:
        """Test create_user sets proper default values."""
        # Arrange
        service = AuthService(db=test_session)

        # Act
        result = service.create_user(user_create_password)

        # Assert defaults
        assert result.is_active is True
        assert result.is_superuser is False
        assert result.created_at is not None

    @pytest.mark.integration
    def test_create_user_generates_unique_id(
        self, test_session: Session, user_create_password: UserCreate
    ) -> None:
        """Test create_user generates unique UUID for each user."""
        # Arrange
        service = AuthService(db=test_session)

        # Act - Create first user
        user1 = service.create_user(user_create_password)

        # Create second user with different credentials
        user2_data = UserCreate(
            username="testuser2",
            email="test2@example.com",
            password="SecurePass456!",
            full_name="Test User 2",
        )
        user2 = service.create_user(user2_data)

        # Assert - IDs should be different
        assert user1.id != user2.id


# ============================================================================
# Test Suite 6: update_user (5 tests) - Lines 147-183
# ============================================================================


class TestUpdateUser:
    """Test user update operations - Lines 147-183."""

    @pytest.mark.integration
    def test_update_user_partial(
        self,
        test_session: Session,
        user_create_password: UserCreate,
        user_update_partial: UserUpdate,
    ) -> None:
        """Test update_user with partial update."""
        # Arrange
        service = AuthService(db=test_session)
        created_user = service.create_user(user_create_password)

        # Act
        result = service.update_user(created_user.id, user_update_partial)

        # Assert
        assert result is not None
        assert result.full_name == user_update_partial.full_name
        assert result.username == user_create_password.username  # Unchanged
        assert result.email == user_create_password.email  # Unchanged

    @pytest.mark.integration
    def test_update_user_full(
        self, test_session: Session, user_create_password: UserCreate, user_update_full: UserUpdate
    ) -> None:
        """Test update_user with full update."""
        # Arrange
        service = AuthService(db=test_session)
        created_user = service.create_user(user_create_password)

        # Act
        result = service.update_user(created_user.id, user_update_full)

        # Assert
        assert result is not None
        assert result.username == user_create_password.username  # Username not updatable
        assert result.email == user_update_full.email
        assert result.full_name == user_update_full.full_name
        assert result.is_active == user_update_full.is_active

    @pytest.mark.integration
    def test_update_user_not_found(
        self, test_session: Session, user_update_partial: UserUpdate
    ) -> None:
        """Test update_user returns None for non-existent user."""
        # Arrange
        service = AuthService(db=test_session)
        non_existent_id = str(uuid4())

        # Act
        result = service.update_user(non_existent_id, user_update_partial)

        # Assert
        assert result is None

    @pytest.mark.integration
    def test_update_user_updates_timestamp(
        self,
        test_session: Session,
        user_create_password: UserCreate,
        user_update_partial: UserUpdate,
    ) -> None:
        """Test update_user updates the updated_at timestamp."""
        # Arrange
        service = AuthService(db=test_session)
        created_user = service.create_user(user_create_password)
        original_row = test_session.query(UserTable).filter(UserTable.id == created_user.id).first()
        assert original_row is not None
        original_updated_at = original_row.updated_at

        # Act
        result = service.update_user(created_user.id, user_update_partial)

        # Assert
        assert result is not None
        updated_row = test_session.query(UserTable).filter(UserTable.id == result.id).first()
        assert updated_row is not None
        assert updated_row.updated_at > original_updated_at

    @pytest.mark.integration
    def test_update_user_excludes_unset_fields(
        self, test_session: Session, user_create_password: UserCreate
    ) -> None:
        """Test update_user only updates fields that are explicitly set."""
        # Arrange
        service = AuthService(db=test_session)
        created_user = service.create_user(user_create_password)

        # Create update with only full_name set (exclude_unset behavior)
        partial_update = UserUpdate(full_name="New Name")

        # Act
        result = service.update_user(created_user.id, partial_update)

        # Assert - Only full_name changed
        assert result is not None
        assert result.full_name == "New Name"
        assert result.username == user_create_password.username
        assert result.email == user_create_password.email


# ============================================================================
# Test Suite 7: update_last_login (3 tests) - Lines 185-203
# ============================================================================


class TestUpdateLastLogin:
    """Test last login timestamp updates - Lines 185-203."""

    @pytest.mark.integration
    def test_update_last_login_success(
        self, test_session: Session, user_create_password: UserCreate
    ) -> None:
        """Test update_last_login successfully updates timestamp."""
        # Arrange
        service = AuthService(db=test_session)
        created_user = service.create_user(user_create_password)

        # Act
        result = service.update_last_login(created_user.id)

        # Assert
        assert result is True
        user_row = test_session.query(UserTable).filter(UserTable.id == created_user.id).first()
        assert user_row is not None
        assert user_row.last_login is not None

    @pytest.mark.unit
    def test_update_last_login_not_found(self, test_session: Session) -> None:
        """Test update_last_login returns False for non-existent user."""
        # Arrange
        service = AuthService(db=test_session)
        non_existent_id = str(uuid4())

        # Act
        result = service.update_last_login(non_existent_id)

        # Assert
        assert result is False

    @pytest.mark.integration
    def test_update_last_login_updates_updated_at(
        self, test_session: Session, user_create_password: UserCreate
    ) -> None:
        """Test update_last_login also updates updated_at timestamp."""
        # Arrange
        service = AuthService(db=test_session)
        created_user = service.create_user(user_create_password)

        # Act
        service.update_last_login(created_user.id)

        # Assert
        user_row = test_session.query(UserTable).filter(UserTable.id == created_user.id).first()
        assert user_row is not None
        assert user_row.updated_at is not None
        assert user_row.last_login is not None


# ============================================================================
# Test Suite 8: list_users (4 tests) - Lines 205-227
# ============================================================================


class TestListUsers:
    """Test user listing with pagination - Lines 205-227."""

    @pytest.mark.integration
    def test_list_users_default_pagination(
        self, test_session: Session, user_create_password: UserCreate
    ) -> None:
        """Test list_users with default pagination."""
        # Arrange
        service = AuthService(db=test_session)
        service.create_user(user_create_password)

        # Act
        result = service.list_users()

        # Assert
        assert len(result) == 1
        assert result[0].username == user_create_password.username

    @pytest.mark.integration
    def test_list_users_with_skip_limit(self, test_session: Session) -> None:
        """Test list_users with skip and limit parameters."""
        # Arrange
        service = AuthService(db=test_session)

        # Create 5 users
        for i in range(5):
            user_data = UserCreate(
                username=f"user{i}",
                email=f"user{i}@example.com",
                password="SecurePass123!",
                full_name=f"User {i}",
            )
            service.create_user(user_data)

        # Act - Skip 2, limit 2
        result = service.list_users(skip=2, limit=2)

        # Assert
        assert len(result) == 2

    @pytest.mark.integration
    def test_list_users_ordered_by_created_at_desc(self, test_session: Session) -> None:
        """Test list_users returns users ordered by created_at descending."""
        # Arrange
        service = AuthService(db=test_session)

        # Create users in sequence
        user1_data = UserCreate(
            username="user1",
            email="user1@example.com",
            password="SecurePass123!",
            full_name="User 1",
        )
        user1 = service.create_user(user1_data)

        user2_data = UserCreate(
            username="user2",
            email="user2@example.com",
            password="SecurePass123!",
            full_name="User 2",
        )
        user2 = service.create_user(user2_data)

        # Act
        result = service.list_users()

        # Assert - Most recent first
        assert result[0].id == user2.id
        assert result[1].id == user1.id

    @pytest.mark.integration
    def test_list_users_includes_last_login(
        self, test_session: Session, user_create_password: UserCreate
    ) -> None:
        """Test list_users includes last_login field."""
        # Arrange
        service = AuthService(db=test_session)
        created_user = service.create_user(user_create_password)
        service.update_last_login(created_user.id)

        # Act
        result = service.list_users()

        # Assert
        assert result[0].last_login is not None


# ============================================================================
# Test Suite 9: deactivate_user (4 tests) - Lines 229-251
# ============================================================================


class TestDeactivateUser:
    """Test user deactivation - Lines 229-251."""

    @pytest.mark.integration
    def test_deactivate_user_success(
        self, test_session: Session, user_create_password: UserCreate
    ) -> None:
        """Test deactivate_user successfully deactivates active user."""
        # Arrange
        service = AuthService(db=test_session)
        created_user = service.create_user(user_create_password)

        # Act
        result = service.deactivate_user(created_user.id)

        # Assert
        assert result is True
        user_row = test_session.query(UserTable).filter(UserTable.id == created_user.id).first()
        assert user_row is not None
        assert user_row.is_active is False

    @pytest.mark.unit
    def test_deactivate_user_not_found(self, test_session: Session) -> None:
        """Test deactivate_user returns False for non-existent user."""
        # Arrange
        service = AuthService(db=test_session)
        non_existent_id = str(uuid4())

        # Act
        result = service.deactivate_user(non_existent_id)

        # Assert
        assert result is False

    @pytest.mark.integration
    def test_deactivate_user_already_deactivated(
        self, test_session: Session, user_create_password: UserCreate
    ) -> None:
        """Test deactivate_user returns True for already deactivated user."""
        # Arrange
        service = AuthService(db=test_session)
        created_user = service.create_user(user_create_password)
        service.deactivate_user(created_user.id)

        # Act - Try to deactivate again
        result = service.deactivate_user(created_user.id)

        # Assert
        assert result is True

    @pytest.mark.integration
    def test_deactivate_user_updates_timestamp(
        self, test_session: Session, user_create_password: UserCreate
    ) -> None:
        """Test deactivate_user updates updated_at timestamp."""
        # Arrange
        service = AuthService(db=test_session)
        created_user = service.create_user(user_create_password)
        original_row = test_session.query(UserTable).filter(UserTable.id == created_user.id).first()
        assert original_row is not None
        original_updated_at = original_row.updated_at

        # Act
        service.deactivate_user(created_user.id)

        # Assert
        user_row = test_session.query(UserTable).filter(UserTable.id == created_user.id).first()
        assert user_row is not None
        assert user_row.updated_at > original_updated_at


# ============================================================================
# Test Suite 10: delete_user_account (3 tests) - Lines 253-297
# ============================================================================


class TestDeleteUserAccount:
    """Test permanent user deletion - Lines 253-297."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_delete_user_account_success(
        self, test_session: Session, user_create_password: UserCreate
    ) -> None:
        """Test delete_user_account successfully deletes user."""
        # Arrange
        service = AuthService(db=test_session)
        created_user = service.create_user(user_create_password)

        # Act
        result = await service.delete_user_account(created_user.id)

        # Assert
        assert result is True
        user_row = test_session.query(UserTable).filter(UserTable.id == created_user.id).first()
        assert user_row is None

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_delete_user_account_not_found(self, test_session: Session) -> None:
        """Test delete_user_account returns False for non-existent user."""
        # Arrange
        service = AuthService(db=test_session)
        non_existent_id = str(uuid4())

        # Act
        result = await service.delete_user_account(non_existent_id)

        # Assert
        assert result is False

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_delete_user_account_removes_from_database(
        self, test_session: Session, user_create_password: UserCreate
    ) -> None:
        """Test delete_user_account completely removes user from database."""
        # Arrange
        service = AuthService(db=test_session)
        created_user = service.create_user(user_create_password)
        user_id = created_user.id

        # Act
        await service.delete_user_account(user_id)

        # Assert - User should not be found
        result = service.get_user_by_id(user_id)
        assert result is None


# ============================================================================
# Test Suite 11: authenticate_user (6 tests) - Lines 299-340
# ============================================================================


class TestAuthenticateUser:
    """Test user authentication - Lines 299-340."""

    @pytest.mark.integration
    def test_authenticate_user_success_with_username(
        self, test_session: Session, user_create_password: UserCreate
    ) -> None:
        """Test authenticate_user succeeds with valid username and password."""
        # Arrange
        service = AuthService(db=test_session)
        service.create_user(user_create_password)

        # Act
        result = service.authenticate_user(
            user_create_password.username, user_create_password.password
        )

        # Assert
        assert result is not None
        assert result.username == user_create_password.username

    @pytest.mark.integration
    def test_authenticate_user_success_with_email(
        self, test_session: Session, user_create_password: UserCreate
    ) -> None:
        """Test authenticate_user succeeds with valid email and password."""
        # Arrange
        service = AuthService(db=test_session)
        service.create_user(user_create_password)

        # Act - Use email instead of username
        result = service.authenticate_user(
            user_create_password.email, user_create_password.password
        )

        # Assert
        assert result is not None
        assert result.email == user_create_password.email

    @pytest.mark.integration
    def test_authenticate_user_invalid_password(
        self, test_session: Session, user_create_password: UserCreate
    ) -> None:
        """Test authenticate_user fails with invalid password."""
        # Arrange
        service = AuthService(db=test_session)
        service.create_user(user_create_password)

        # Act
        result = service.authenticate_user(user_create_password.username, "WrongPassword123!")

        # Assert
        assert result is None

    @pytest.mark.unit
    def test_authenticate_user_user_not_found(self, test_session: Session) -> None:
        """Test authenticate_user returns None for non-existent user."""
        # Arrange
        service = AuthService(db=test_session)

        # Act
        result = service.authenticate_user("nonexistent_user", "SomePassword123!")

        # Assert
        assert result is None

    @pytest.mark.integration
    def test_authenticate_user_inactive_user(
        self, test_session: Session, user_create_password: UserCreate
    ) -> None:
        """Test authenticate_user fails for inactive user."""
        # Arrange
        service = AuthService(db=test_session)
        created_user = service.create_user(user_create_password)
        service.deactivate_user(created_user.id)

        # Act
        result = service.authenticate_user(
            user_create_password.username, user_create_password.password
        )

        # Assert
        assert result is None

    @pytest.mark.integration
    def test_authenticate_user_oauth_user_no_password(
        self, test_session: Session, user_create_oauth: OAuthUserCreate
    ) -> None:
        """Test authenticate_user fails for OAuth user (no password)."""
        # Arrange
        service = AuthService(db=test_session)
        service.create_user(user_create_oauth)

        # Act - Try to authenticate OAuth user with password
        result = service.authenticate_user(user_create_oauth.username, "AnyPassword123!")

        # Assert
        assert result is None


# ============================================================================
# Test Suite 12: change_password (5 tests) - Lines 342-382
# ============================================================================


class TestChangePassword:
    """Test password change operations - Lines 342-382."""

    @pytest.mark.integration
    def test_change_password_success(
        self, test_session: Session, user_create_password: UserCreate
    ) -> None:
        """Test change_password successfully changes password."""
        # Arrange
        service = AuthService(db=test_session)
        created_user = service.create_user(user_create_password)
        new_password = "NewSecurePass456!"

        # Act
        result = service.change_password(
            created_user.id, user_create_password.password, new_password
        )

        # Assert
        assert result is True

        # Verify new password works
        auth_result = service.authenticate_user(user_create_password.username, new_password)
        assert auth_result is not None

    @pytest.mark.unit
    def test_change_password_user_not_found(self, test_session: Session) -> None:
        """Test change_password returns False for non-existent user."""
        # Arrange
        service = AuthService(db=test_session)
        non_existent_id = str(uuid4())

        # Act
        result = service.change_password(non_existent_id, "OldPass123!", "NewPass456!")

        # Assert
        assert result is False

    @pytest.mark.integration
    def test_change_password_invalid_old_password(
        self, test_session: Session, user_create_password: UserCreate
    ) -> None:
        """Test change_password fails with invalid old password."""
        # Arrange
        service = AuthService(db=test_session)
        created_user = service.create_user(user_create_password)

        # Act - Wrong old password
        result = service.change_password(created_user.id, "WrongOldPass123!", "NewSecurePass456!")

        # Assert
        assert result is False

    @pytest.mark.integration
    def test_change_password_updates_hash(
        self, test_session: Session, user_create_password: UserCreate
    ) -> None:
        """Test change_password updates password hash in database."""
        # Arrange
        service = AuthService(db=test_session)
        created_user = service.create_user(user_create_password)
        original_row = test_session.query(UserTable).filter(UserTable.id == created_user.id).first()
        assert original_row is not None
        original_hash = original_row.hashed_password
        new_password = "NewSecurePass456!"

        # Act
        service.change_password(created_user.id, user_create_password.password, new_password)

        # Assert - Hash should be different
        new_row = test_session.query(UserTable).filter(UserTable.id == created_user.id).first()
        assert new_row is not None
        new_hash = new_row.hashed_password
        assert new_hash != original_hash

    @pytest.mark.integration
    def test_change_password_updates_timestamp(
        self, test_session: Session, user_create_password: UserCreate
    ) -> None:
        """Test change_password updates updated_at timestamp."""
        # Arrange
        service = AuthService(db=test_session)
        created_user = service.create_user(user_create_password)
        original_row = test_session.query(UserTable).filter(UserTable.id == created_user.id).first()
        assert original_row is not None
        original_updated_at = original_row.updated_at

        # Act
        service.change_password(created_user.id, user_create_password.password, "NewSecurePass456!")

        # Assert
        user_row = test_session.query(UserTable).filter(UserTable.id == created_user.id).first()
        assert user_row is not None
        assert user_row.updated_at > original_updated_at
