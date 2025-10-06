"""Unit tests for OAuthValidationService following TEST_BUILDING.md MANDATORY standards.

MANDATORY COMPLIANCE:
- AAA Pattern (Arrange-Act-Assert) - NON-NEGOTIABLE
- SOLID principles testing
- Factory Pattern for test data
- 85%+ coverage target
- Focus on validation logic and error handling

Tests OAuthValidationService validation methods.
"""

from uuid import uuid4

import pytest
from fastapi import HTTPException

from src.auth.models import OAuthCallback, OAuthProvider
from src.auth.services.oauth_validation_service import OAuthValidationService

# ============================================================================
# MANDATORY Fixtures Following TEST_BUILDING.md Factory Pattern
# ============================================================================


@pytest.fixture
def valid_google_callback() -> OAuthCallback:
    """Factory for valid Google OAuth callback data - DRY principle."""
    return OAuthCallback(
        provider=OAuthProvider.GOOGLE,
        code="auth_code_123",
        state=str(uuid4()),
        error=None,
        error_description=None,
    )


@pytest.fixture
def valid_github_callback() -> OAuthCallback:
    """Factory for valid GitHub OAuth callback data."""
    return OAuthCallback(
        provider=OAuthProvider.GITHUB,
        code="github_code_456",
        state=str(uuid4()),
        error=None,
        error_description=None,
    )


@pytest.fixture
def callback_with_error() -> OAuthCallback:
    """Factory for OAuth callback with error."""
    # When OAuth error occurs, code/state might not be sent, but Pydantic requires them
    # Provide dummy values - validation service checks error field first anyway
    return OAuthCallback(
        provider=OAuthProvider.GOOGLE,
        code="dummy_code",  # Not used when error present
        state="dummy_state",  # Not used when error present
        error="access_denied",
        error_description="User denied access",
    )


@pytest.fixture
def callback_missing_code() -> OAuthCallback:
    """Factory for OAuth callback missing authorization code."""
    # Use empty string to represent missing code (Pydantic requires string type)
    return OAuthCallback(
        provider=OAuthProvider.GOOGLE,
        code="",  # Empty string represents missing code
        state=str(uuid4()),
        error=None,
        error_description=None,
    )


@pytest.fixture
def callback_missing_state() -> OAuthCallback:
    """Factory for OAuth callback missing state parameter."""
    # Use empty string to represent missing state (Pydantic requires string type)
    return OAuthCallback(
        provider=OAuthProvider.GOOGLE,
        code="auth_code_123",
        state="",  # Empty string represents missing state
        error=None,
        error_description=None,
    )


# ============================================================================
# Test Suite 1: validate_callback_parameters (3 tests) - Main entry point
# ============================================================================


class TestValidateCallbackParameters:
    """Test main validation entry point - Lines 17-31."""

    @pytest.mark.unit
    def test_validate_callback_parameters_success(
        self, valid_google_callback: OAuthCallback
    ) -> None:
        """Test validate_callback_parameters succeeds with valid data.

        AAA Pattern:
        - Arrange: Valid Google OAuth callback
        - Act: Validate callback parameters
        - Assert: No exception raised
        """
        # Arrange - Using fixture

        # Act & Assert - Should not raise exception
        try:
            OAuthValidationService.validate_callback_parameters(
                provider=OAuthProvider.GOOGLE, oauth_callback=valid_google_callback
            )
        except HTTPException:
            pytest.fail("validate_callback_parameters raised HTTPException unexpectedly")

    @pytest.mark.unit
    def test_validate_callback_parameters_with_error(
        self, callback_with_error: OAuthCallback
    ) -> None:
        """Test validate_callback_parameters fails when callback has error."""
        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            OAuthValidationService.validate_callback_parameters(
                provider=OAuthProvider.GOOGLE, oauth_callback=callback_with_error
            )

        # Assert error details
        assert exc_info.value.status_code == 400
        assert "OAuth authorization failed" in exc_info.value.detail
        assert "User denied access" in exc_info.value.detail

    @pytest.mark.unit
    def test_validate_callback_parameters_provider_mismatch(
        self, valid_google_callback: OAuthCallback
    ) -> None:
        """Test validate_callback_parameters fails on provider mismatch."""
        # Act & Assert - Expect GitHub but callback has Google
        with pytest.raises(HTTPException) as exc_info:
            OAuthValidationService.validate_callback_parameters(
                provider=OAuthProvider.GITHUB,  # Mismatch
                oauth_callback=valid_google_callback,
            )

        # Assert error details
        assert exc_info.value.status_code == 400
        assert "provider mismatch" in exc_info.value.detail
        assert "CSRF" in exc_info.value.detail


# ============================================================================
# Test Suite 2: _validate_oauth_errors (5 tests) - Lines 34-55
# ============================================================================


class TestValidateOAuthErrors:
    """Test OAuth error validation - SECURITY REQUIREMENT."""

    @pytest.mark.unit
    def test_validate_oauth_errors_no_error(self, valid_google_callback: OAuthCallback) -> None:
        """Test _validate_oauth_errors succeeds when no error present."""
        # Act & Assert - Should not raise exception
        try:
            OAuthValidationService._validate_oauth_errors(
                provider=OAuthProvider.GOOGLE, oauth_callback=valid_google_callback
            )
        except HTTPException:
            pytest.fail("_validate_oauth_errors raised HTTPException unexpectedly")

    @pytest.mark.unit
    def test_validate_oauth_errors_with_error_and_description(self) -> None:
        """Test _validate_oauth_errors fails with error and description."""
        # Arrange - Provide dummy code/state since Pydantic requires them
        callback = OAuthCallback(
            provider=OAuthProvider.GOOGLE,
            code="dummy",
            state="dummy",
            error="access_denied",
            error_description="User cancelled authorization",
        )

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            OAuthValidationService._validate_oauth_errors(
                provider=OAuthProvider.GOOGLE, oauth_callback=callback
            )

        assert exc_info.value.status_code == 400
        assert "OAuth authorization failed" in exc_info.value.detail
        assert "User cancelled authorization" in exc_info.value.detail

    @pytest.mark.unit
    def test_validate_oauth_errors_with_error_no_description(self) -> None:
        """Test _validate_oauth_errors uses error when description missing."""
        # Arrange - Provide dummy code/state since Pydantic requires them
        callback = OAuthCallback(
            provider=OAuthProvider.GOOGLE,
            code="dummy",
            state="dummy",
            error="server_error",
            error_description=None,
        )

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            OAuthValidationService._validate_oauth_errors(
                provider=OAuthProvider.GOOGLE, oauth_callback=callback
            )

        assert exc_info.value.status_code == 400
        assert "OAuth authorization failed" in exc_info.value.detail
        assert "server_error" in exc_info.value.detail

    @pytest.mark.unit
    def test_validate_oauth_errors_invalid_grant(self) -> None:
        """Test _validate_oauth_errors handles invalid_grant error."""
        # Arrange - Provide dummy code/state since Pydantic requires them
        callback = OAuthCallback(
            provider=OAuthProvider.GITHUB,
            code="dummy",
            state="dummy",
            error="invalid_grant",
            error_description="The provided authorization grant is invalid",
        )

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            OAuthValidationService._validate_oauth_errors(
                provider=OAuthProvider.GITHUB, oauth_callback=callback
            )

        assert exc_info.value.status_code == 400
        assert "invalid_grant" not in exc_info.value.detail  # Uses description
        assert "authorization grant is invalid" in exc_info.value.detail

    @pytest.mark.unit
    def test_validate_oauth_errors_empty_error_string(self) -> None:
        """Test _validate_oauth_errors treats empty string as no error (Python falsy behavior)."""
        # Arrange - Empty string is falsy in Python, treated as no error
        callback = OAuthCallback(
            provider=OAuthProvider.GOOGLE,
            code="valid_code",
            state="valid_state",
            error="",  # Empty string treated as falsy
            error_description=None,
        )

        # Act & Assert - Should NOT raise exception (empty string is falsy)
        try:
            OAuthValidationService._validate_oauth_errors(
                provider=OAuthProvider.GOOGLE, oauth_callback=callback
            )
        except HTTPException:
            pytest.fail("_validate_oauth_errors raised HTTPException for empty error string")


# ============================================================================
# Test Suite 3: _validate_provider_consistency (4 tests) - Lines 58-79
# ============================================================================


class TestValidateProviderConsistency:
    """Test provider consistency validation - CSRF PROTECTION."""

    @pytest.mark.unit
    def test_validate_provider_consistency_match(
        self, valid_google_callback: OAuthCallback
    ) -> None:
        """Test _validate_provider_consistency succeeds with matching providers."""
        # Act & Assert - Should not raise exception
        try:
            OAuthValidationService._validate_provider_consistency(
                provider=OAuthProvider.GOOGLE, oauth_callback=valid_google_callback
            )
        except HTTPException:
            pytest.fail("_validate_provider_consistency raised HTTPException unexpectedly")

    @pytest.mark.unit
    def test_validate_provider_consistency_google_github_mismatch(
        self, valid_google_callback: OAuthCallback
    ) -> None:
        """Test _validate_provider_consistency fails on Google vs GitHub mismatch."""
        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            OAuthValidationService._validate_provider_consistency(
                provider=OAuthProvider.GITHUB,  # Expecting GitHub
                oauth_callback=valid_google_callback,  # But got Google
            )

        assert exc_info.value.status_code == 400
        assert "provider mismatch" in exc_info.value.detail
        assert "CSRF" in exc_info.value.detail

    @pytest.mark.unit
    def test_validate_provider_consistency_github_google_mismatch(
        self, valid_github_callback: OAuthCallback
    ) -> None:
        """Test _validate_provider_consistency fails on GitHub vs Google mismatch."""
        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            OAuthValidationService._validate_provider_consistency(
                provider=OAuthProvider.GOOGLE,  # Expecting Google
                oauth_callback=valid_github_callback,  # But got GitHub
            )

        assert exc_info.value.status_code == 400
        assert "provider mismatch" in exc_info.value.detail
        assert "CSRF" in exc_info.value.detail

    @pytest.mark.unit
    def test_validate_provider_consistency_github_match(
        self, valid_github_callback: OAuthCallback
    ) -> None:
        """Test _validate_provider_consistency succeeds with GitHub match."""
        # Act & Assert - Should not raise exception
        try:
            OAuthValidationService._validate_provider_consistency(
                provider=OAuthProvider.GITHUB, oauth_callback=valid_github_callback
            )
        except HTTPException:
            pytest.fail("_validate_provider_consistency raised HTTPException unexpectedly")


# ============================================================================
# Test Suite 4: _validate_required_parameters (4 tests) - Lines 82-112
# ============================================================================


class TestValidateRequiredParameters:
    """Test required parameter validation - SECURITY REQUIREMENT."""

    @pytest.mark.unit
    def test_validate_required_parameters_success(
        self, valid_google_callback: OAuthCallback
    ) -> None:
        """Test _validate_required_parameters succeeds with all required params."""
        # Act & Assert - Should not raise exception
        try:
            OAuthValidationService._validate_required_parameters(
                provider=OAuthProvider.GOOGLE, oauth_callback=valid_google_callback
            )
        except HTTPException:
            pytest.fail("_validate_required_parameters raised HTTPException unexpectedly")

    @pytest.mark.unit
    def test_validate_required_parameters_missing_code(
        self, callback_missing_code: OAuthCallback
    ) -> None:
        """Test _validate_required_parameters fails when code missing."""
        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            OAuthValidationService._validate_required_parameters(
                provider=OAuthProvider.GOOGLE, oauth_callback=callback_missing_code
            )

        assert exc_info.value.status_code == 400
        assert "Missing authorization code" in exc_info.value.detail

    @pytest.mark.unit
    def test_validate_required_parameters_missing_state(
        self, callback_missing_state: OAuthCallback
    ) -> None:
        """Test _validate_required_parameters fails when state missing."""
        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            OAuthValidationService._validate_required_parameters(
                provider=OAuthProvider.GOOGLE, oauth_callback=callback_missing_state
            )

        assert exc_info.value.status_code == 400
        assert "Missing state parameter" in exc_info.value.detail

    @pytest.mark.unit
    def test_validate_required_parameters_empty_code(self) -> None:
        """Test _validate_required_parameters fails when code is empty string."""
        # Arrange
        callback = OAuthCallback(
            provider=OAuthProvider.GOOGLE,
            code="",  # Empty string
            state=str(uuid4()),
            error=None,
            error_description=None,
        )

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            OAuthValidationService._validate_required_parameters(
                provider=OAuthProvider.GOOGLE, oauth_callback=callback
            )

        assert exc_info.value.status_code == 400
        assert "Missing authorization code" in exc_info.value.detail


# ============================================================================
# Test Suite 5: Integration Tests (2 tests) - Full validation flow
# ============================================================================


class TestOAuthValidationIntegration:
    """Test complete validation flow - INTEGRATION."""

    @pytest.mark.unit
    def test_full_validation_flow_success(self, valid_google_callback: OAuthCallback) -> None:
        """Test complete validation flow with valid callback.

        AAA Pattern:
        - Arrange: Valid OAuth callback with all required fields
        - Act: Run full validation
        - Assert: No exceptions, validation passes
        """
        # Act & Assert - Should complete without exception
        try:
            OAuthValidationService.validate_callback_parameters(
                provider=OAuthProvider.GOOGLE, oauth_callback=valid_google_callback
            )
        except HTTPException:
            pytest.fail("Full validation failed unexpectedly")

    @pytest.mark.unit
    def test_full_validation_flow_multiple_errors(self) -> None:
        """Test validation stops at first error in chain.

        Validation order:
        1. Check for OAuth errors (should fail here)
        2. Check provider consistency (not reached)
        3. Check required parameters (not reached)
        """
        # Arrange - Callback with error AND provider mismatch AND missing code
        # Provide dummy code/state since Pydantic requires them
        callback = OAuthCallback(
            provider=OAuthProvider.GITHUB,  # Will cause mismatch
            code="dummy",  # Would cause missing code error if we got there
            state="dummy",  # Would cause missing state error if we got there
            error="access_denied",  # Should fail at this first check
            error_description="User denied",
        )

        # Act & Assert - Should fail at first validation (OAuth error)
        with pytest.raises(HTTPException) as exc_info:
            OAuthValidationService.validate_callback_parameters(
                provider=OAuthProvider.GOOGLE,  # Mismatch
                oauth_callback=callback,
            )

        # Assert - Failed at OAuth error check (first validation)
        assert "OAuth authorization failed" in exc_info.value.detail
        assert "User denied" in exc_info.value.detail
