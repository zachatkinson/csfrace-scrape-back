"""Integration tests for OAuth token storage and revocation lifecycle.

Tests cover the complete token lifecycle:
1. Token capture during OAuth callback
2. Token encryption during account linking
3. Token decryption during account disconnection
4. Token revocation with provider APIs
5. Graceful degradation on revocation failures

Target: 80%+ coverage for token-related code paths
"""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

import pytest

from src.auth.models import OAuthProvider, OAuthUserInfo
from src.auth.oauth_service import OAuthService
from src.auth.token_encryption_service import TokenEncryptionService
from src.database.models.auth import LinkedAccount as LinkedAccountDB, User as UserTable


class TestOAuthTokenLifecycle:
    """Integration tests for OAuth token storage and revocation lifecycle."""

    @pytest.fixture
    def mock_db_session(self) -> Mock:
        """Mock database session for testing."""
        session = Mock(spec=["query", "add", "commit", "rollback", "delete"])
        session.add = Mock()
        session.commit = Mock()
        session.rollback = Mock()
        session.delete = Mock()
        return session

    @pytest.fixture
    def encryption_service(self) -> TokenEncryptionService:
        """Create real encryption service for integration testing."""
        return TokenEncryptionService()

    @pytest.fixture
    def oauth_service(
        self, mock_db_session: Mock, encryption_service: TokenEncryptionService
    ) -> OAuthService:
        """Create OAuthService with real encryption service."""
        # Mock auth_service to avoid database dependencies
        mock_auth_service = Mock()
        mock_auth_service.create_user.return_value = Mock(
            id=str(uuid4()),
            username="testuser",
            email="test@example.com",
            full_name="Test User",
        )

        # Mock merge_service
        mock_merge_service = Mock()

        return OAuthService(
            db_session=mock_db_session,
            auth_service=mock_auth_service,
            merge_service=mock_merge_service,
            token_encryption_service=encryption_service,
        )

    @pytest.fixture
    def sample_oauth_user_info(self) -> OAuthUserInfo:
        """Sample OAuth user info with access token."""
        return OAuthUserInfo(
            provider=OAuthProvider.GOOGLE,
            provider_id="google_user_123",
            email="test@example.com",
            name="Test User",
            avatar_url="https://example.com/avatar.jpg",
            access_token="sample_access_token_1234567890",
        )

    @pytest.fixture
    def sample_user_db(self) -> UserTable:
        """Sample user database record."""
        user = Mock(spec=UserTable)
        user.id = str(uuid4())
        user.username = "testuser"
        user.email = "test@example.com"
        user.hashed_password = "hashed_password_12345"
        return user

    @pytest.fixture
    def sample_linked_account(self, sample_user_db: UserTable) -> LinkedAccountDB:
        """Sample linked account with encrypted token."""
        linked_account = Mock(spec=LinkedAccountDB)
        linked_account.id = str(uuid4())
        linked_account.user_id = sample_user_db.id
        linked_account.provider = "google"
        linked_account.provider_id = "google_user_123"
        linked_account.provider_email = "test@example.com"
        linked_account.access_token = None  # Will be set during tests
        linked_account.token_scopes = ["email", "profile"]
        return linked_account

    # ========================================================================
    # Test 1: Token Encryption During Account Linking
    # ========================================================================

    def test_link_oauth_account_encrypts_access_token(
        self,
        oauth_service: OAuthService,
        mock_db_session: Mock,
        sample_oauth_user_info: OAuthUserInfo,
        sample_user_db: UserTable,
        encryption_service: TokenEncryptionService,
    ) -> None:
        """Test that access token is encrypted during account linking."""
        # Arrange: Mock database queries
        mock_db_session.query.return_value.filter.return_value.first.return_value = None

        # Act: Link OAuth account with access token
        oauth_service._link_oauth_account(
            user_id=sample_user_db.id, oauth_user_info=sample_oauth_user_info
        )

        # Assert: Verify database add was called
        assert mock_db_session.add.called
        linked_account_arg = mock_db_session.add.call_args[0][0]

        # Verify access_token is encrypted (not plaintext)
        assert linked_account_arg.access_token is not None
        assert linked_account_arg.access_token != sample_oauth_user_info.access_token

        # Verify we can decrypt it back to original
        decrypted_token = encryption_service.decrypt_token(linked_account_arg.access_token)
        assert decrypted_token == sample_oauth_user_info.access_token

    def test_link_oauth_account_handles_missing_access_token(
        self,
        oauth_service: OAuthService,
        mock_db_session: Mock,
        sample_oauth_user_info: OAuthUserInfo,
        sample_user_db: UserTable,
    ) -> None:
        """Test that linking works even without access token."""
        # Arrange: Remove access token
        sample_oauth_user_info.access_token = None
        mock_db_session.query.return_value.filter.return_value.first.return_value = None

        # Act: Link OAuth account without access token
        oauth_service._link_oauth_account(
            user_id=sample_user_db.id, oauth_user_info=sample_oauth_user_info
        )

        # Assert: Verify database add was called
        assert mock_db_session.add.called
        linked_account_arg = mock_db_session.add.call_args[0][0]

        # Verify access_token is None
        assert linked_account_arg.access_token is None

    def test_link_oauth_account_handles_encryption_failure(
        self,
        oauth_service: OAuthService,
        mock_db_session: Mock,
        sample_oauth_user_info: OAuthUserInfo,
        sample_user_db: UserTable,
    ) -> None:
        """Test graceful degradation when encryption fails."""
        # Arrange: Mock encryption service to raise exception
        oauth_service.token_encryption_service.encrypt_token = Mock(
            side_effect=Exception("Encryption service unavailable")
        )
        mock_db_session.query.return_value.filter.return_value.first.return_value = None

        # Act: Link OAuth account (should not raise exception)
        oauth_service._link_oauth_account(
            user_id=sample_user_db.id, oauth_user_info=sample_oauth_user_info
        )

        # Assert: Verify database add was called (graceful degradation)
        assert mock_db_session.add.called
        linked_account_arg = mock_db_session.add.call_args[0][0]

        # Verify access_token is None due to encryption failure
        assert linked_account_arg.access_token is None

    # ========================================================================
    # Test 2: Token Revocation During Account Disconnection
    # ========================================================================

    @pytest.mark.asyncio
    async def test_revoke_oauth_token_success(
        self,
        oauth_service: OAuthService,
        sample_linked_account: LinkedAccountDB,
        encryption_service: TokenEncryptionService,
    ) -> None:
        """Test successful token revocation."""
        # Arrange: Set encrypted access token
        plaintext_token = "sample_access_token_1234567890"
        encrypted_token = encryption_service.encrypt_token(plaintext_token)
        sample_linked_account.access_token = encrypted_token

        # Mock the revoker
        mock_revoker = AsyncMock()
        mock_revoker.revoke_all_tokens.return_value = True

        with patch(
            "src.auth.oauth_revocation_service.OAuthRevocationRegistry.get_revoker",
            return_value=mock_revoker,
        ):
            # Act: Revoke token
            result = await oauth_service._revoke_oauth_token(
                linked_account=sample_linked_account, provider=OAuthProvider.GOOGLE
            )

        # Assert: Verify revocation succeeded
        assert result is True
        mock_revoker.revoke_all_tokens.assert_called_once()

        # Verify decrypted token was passed to revoker
        call_kwargs = mock_revoker.revoke_all_tokens.call_args[1]
        assert call_kwargs["access_token"] == plaintext_token

    @pytest.mark.asyncio
    async def test_revoke_oauth_token_no_token_stored(
        self, oauth_service: OAuthService, sample_linked_account: LinkedAccountDB
    ) -> None:
        """Test revocation when no token is stored."""
        # Arrange: No access token
        sample_linked_account.access_token = None

        # Act: Attempt revocation
        result = await oauth_service._revoke_oauth_token(
            linked_account=sample_linked_account, provider=OAuthProvider.GOOGLE
        )

        # Assert: Returns False (no token to revoke)
        assert result is False

    @pytest.mark.asyncio
    async def test_revoke_oauth_token_decryption_failure(
        self,
        oauth_service: OAuthService,
        sample_linked_account: LinkedAccountDB,
    ) -> None:
        """Test graceful handling of decryption failures."""
        # Arrange: Set invalid encrypted token
        sample_linked_account.access_token = "invalid_encrypted_token"

        # Act: Attempt revocation (should not raise exception)
        result = await oauth_service._revoke_oauth_token(
            linked_account=sample_linked_account, provider=OAuthProvider.GOOGLE
        )

        # Assert: Returns False (graceful degradation)
        assert result is False

    @pytest.mark.asyncio
    async def test_revoke_oauth_token_provider_api_failure(
        self,
        oauth_service: OAuthService,
        sample_linked_account: LinkedAccountDB,
        encryption_service: TokenEncryptionService,
    ) -> None:
        """Test graceful handling when provider API fails."""
        # Arrange: Set encrypted access token
        plaintext_token = "sample_access_token_1234567890"
        encrypted_token = encryption_service.encrypt_token(plaintext_token)
        sample_linked_account.access_token = encrypted_token

        # Mock the revoker to return False (provider API failed)
        mock_revoker = AsyncMock()
        mock_revoker.revoke_all_tokens.return_value = False

        with patch(
            "src.auth.oauth_revocation_service.OAuthRevocationRegistry.get_revoker",
            return_value=mock_revoker,
        ):
            # Act: Revoke token
            result = await oauth_service._revoke_oauth_token(
                linked_account=sample_linked_account, provider=OAuthProvider.GOOGLE
            )

        # Assert: Returns False (provider API failure)
        assert result is False

    @pytest.mark.asyncio
    async def test_revoke_oauth_token_unexpected_exception(
        self,
        oauth_service: OAuthService,
        sample_linked_account: LinkedAccountDB,
        encryption_service: TokenEncryptionService,
    ) -> None:
        """Test graceful handling of unexpected exceptions."""
        # Arrange: Set encrypted access token
        plaintext_token = "sample_access_token_1234567890"
        encrypted_token = encryption_service.encrypt_token(plaintext_token)
        sample_linked_account.access_token = encrypted_token

        # Mock the revoker to raise exception
        mock_revoker = AsyncMock()
        mock_revoker.revoke_all_tokens.side_effect = Exception("Unexpected error")

        with patch(
            "src.auth.oauth_revocation_service.OAuthRevocationRegistry.get_revoker",
            return_value=mock_revoker,
        ):
            # Act: Revoke token (should not raise exception)
            result = await oauth_service._revoke_oauth_token(
                linked_account=sample_linked_account, provider=OAuthProvider.GOOGLE
            )

        # Assert: Returns False (graceful degradation)
        assert result is False

    # ========================================================================
    # Test 3: Integration Test - Full Disconnect Flow
    # ========================================================================

    @pytest.mark.asyncio
    async def test_disconnect_oauth_account_with_token_revocation(
        self,
        oauth_service: OAuthService,
        mock_db_session: Mock,
        sample_user_db: UserTable,
        sample_linked_account: LinkedAccountDB,
        encryption_service: TokenEncryptionService,
    ) -> None:
        """Test full disconnect flow with token revocation."""
        # Arrange: Set up user with password and encrypted token
        sample_user_db.hashed_password = "hashed_password_12345"
        plaintext_token = "sample_access_token_1234567890"
        encrypted_token = encryption_service.encrypt_token(plaintext_token)
        sample_linked_account.access_token = encrypted_token

        # Mock database queries
        mock_db_session.query.return_value.filter.return_value.first.side_effect = [
            sample_user_db,  # First call: get user
            sample_linked_account,  # Third call: get linked account to disconnect
        ]
        mock_db_session.query.return_value.filter.return_value.all.return_value = [
            sample_linked_account
        ]

        # Mock the revoker
        mock_revoker = AsyncMock()
        mock_revoker.revoke_all_tokens.return_value = True

        with patch(
            "src.auth.oauth_revocation_service.OAuthRevocationRegistry.get_revoker",
            return_value=mock_revoker,
        ):
            # Act: Disconnect OAuth account
            result = await oauth_service.disconnect_oauth_account(
                user_id=sample_user_db.id, provider=OAuthProvider.GOOGLE
            )

        # Assert: Verify disconnect succeeded
        assert result is True

        # Verify token revocation was attempted
        mock_revoker.revoke_all_tokens.assert_called_once()

        # Verify account was deleted
        mock_db_session.delete.assert_called_once_with(sample_linked_account)
        mock_db_session.commit.assert_called()

    @pytest.mark.asyncio
    async def test_disconnect_oauth_account_proceeds_despite_revocation_failure(
        self,
        oauth_service: OAuthService,
        mock_db_session: Mock,
        sample_user_db: UserTable,
        sample_linked_account: LinkedAccountDB,
        encryption_service: TokenEncryptionService,
    ) -> None:
        """Test that disconnect proceeds even if revocation fails (graceful degradation)."""
        # Arrange: Set up user with password and encrypted token
        sample_user_db.hashed_password = "hashed_password_12345"
        plaintext_token = "sample_access_token_1234567890"
        encrypted_token = encryption_service.encrypt_token(plaintext_token)
        sample_linked_account.access_token = encrypted_token

        # Mock database queries
        mock_db_session.query.return_value.filter.return_value.first.side_effect = [
            sample_user_db,  # First call: get user
            sample_linked_account,  # Third call: get linked account to disconnect
        ]
        mock_db_session.query.return_value.filter.return_value.all.return_value = [
            sample_linked_account
        ]

        # Mock the revoker to fail
        mock_revoker = AsyncMock()
        mock_revoker.revoke_all_tokens.return_value = False

        with patch(
            "src.auth.oauth_revocation_service.OAuthRevocationRegistry.get_revoker",
            return_value=mock_revoker,
        ):
            # Act: Disconnect OAuth account (should not raise exception)
            result = await oauth_service.disconnect_oauth_account(
                user_id=sample_user_db.id, provider=OAuthProvider.GOOGLE
            )

        # Assert: Verify disconnect still succeeded (graceful degradation)
        assert result is True

        # Verify revocation was attempted
        mock_revoker.revoke_all_tokens.assert_called_once()

        # Verify account was still deleted
        mock_db_session.delete.assert_called_once_with(sample_linked_account)
        mock_db_session.commit.assert_called()

    # ========================================================================
    # Test 4: Edge Cases
    # ========================================================================

    def test_link_oauth_account_with_empty_access_token(
        self,
        oauth_service: OAuthService,
        mock_db_session: Mock,
        sample_oauth_user_info: OAuthUserInfo,
        sample_user_db: UserTable,
    ) -> None:
        """Test that empty access token is treated as None."""
        # Arrange: Set empty access token
        sample_oauth_user_info.access_token = ""
        mock_db_session.query.return_value.filter.return_value.first.return_value = None

        # Act: Link OAuth account
        oauth_service._link_oauth_account(
            user_id=sample_user_db.id, oauth_user_info=sample_oauth_user_info
        )

        # Assert: Verify database add was called
        assert mock_db_session.add.called
        linked_account_arg = mock_db_session.add.call_args[0][0]

        # Verify access_token is None (empty string should not be encrypted)
        assert linked_account_arg.access_token is None

    @pytest.mark.asyncio
    async def test_revoke_oauth_token_with_multiple_providers(
        self,
        oauth_service: OAuthService,
        sample_linked_account: LinkedAccountDB,
        encryption_service: TokenEncryptionService,
    ) -> None:
        """Test token revocation works for different providers."""
        providers_to_test = [
            OAuthProvider.GOOGLE,
            OAuthProvider.GITHUB,
            OAuthProvider.FACEBOOK,
            OAuthProvider.MICROSOFT,
            OAuthProvider.APPLE,
        ]

        for provider in providers_to_test:
            # Arrange: Set encrypted access token and provider
            plaintext_token = f"token_for_{provider.value}"
            encrypted_token = encryption_service.encrypt_token(plaintext_token)
            sample_linked_account.access_token = encrypted_token
            sample_linked_account.provider = provider.value

            # Mock the revoker
            mock_revoker = AsyncMock()
            mock_revoker.revoke_all_tokens.return_value = True

            with patch(
                "src.auth.oauth_revocation_service.OAuthRevocationRegistry.get_revoker",
                return_value=mock_revoker,
            ):
                # Act: Revoke token
                result = await oauth_service._revoke_oauth_token(
                    linked_account=sample_linked_account, provider=provider
                )

            # Assert: Verify revocation succeeded for each provider
            assert result is True
            mock_revoker.revoke_all_tokens.assert_called_once()
