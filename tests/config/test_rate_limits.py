"""Comprehensive tests for src/config/rate_limits.py.

Test coverage: 26 statements, 0% → 100%
Following TEST_BUILDING.md MANDATORY standards with ZERO TOLERANCE.
"""

from collections.abc import Generator

import pytest

from src.config.rate_limits import RateLimits, get_rate_limits, get_rate_limits_instance


@pytest.fixture(autouse=True)
def clear_rate_limits_env_vars(monkeypatch: pytest.MonkeyPatch) -> None:
    """Clear rate limits environment variables for consistent tests."""
    monkeypatch.delenv("TESTING", raising=False)
    monkeypatch.delenv("ENVIRONMENT", raising=False)


@pytest.fixture(autouse=True)
def reset_rate_limits_singleton() -> Generator[None]:
    """Reset rate limits singleton state before each test."""
    import src.config.rate_limits as rate_limits_module

    rate_limits_module._rate_limits_instance = None
    yield
    # Cleanup after test
    rate_limits_module._rate_limits_instance = None


# =============================================================================
# TEST RateLimits - Dataclass Defaults
# =============================================================================


@pytest.mark.unit
class TestRateLimitsDataclass:
    """Test RateLimits dataclass and default values."""

    def test_rate_limits_is_frozen(self) -> None:
        """Test RateLimits is immutable (frozen=True)."""
        # Arrange
        rate_limits = RateLimits()

        # Act & Assert - should not allow modification
        with pytest.raises(
            Exception
        ):  # Frozen dataclass raises FrozenInstanceError or AttributeError
            rate_limits.AUTH_LOGIN = "10/minute"  # type: ignore[misc]

    def test_rate_limits_default_values(self) -> None:
        """Test RateLimits default production values."""
        # Arrange & Act
        rate_limits = RateLimits()

        # Assert - Production defaults
        assert rate_limits.AUTH_LOGIN == "5/minute"
        assert rate_limits.AUTH_REGISTER == "3/minute"
        assert rate_limits.AUTH_PASSWORD_RESET == "2/minute"
        assert rate_limits.AUTH_OAUTH == "10/minute"
        assert rate_limits.AUTH_PASSKEY == "10/minute"
        assert rate_limits.AUTH_SENSITIVE_OPERATION == "3/minute"
        assert rate_limits.JOB_CREATION == "20/hour"
        assert rate_limits.BATCH_CREATION == "10/hour"
        assert rate_limits.ADMIN_OPERATIONS == "100/hour"
        assert rate_limits.DEVELOPMENT == "1000/hour"

    def test_rate_limits_custom_values(self) -> None:
        """Test RateLimits accepts custom values."""
        # Arrange & Act
        rate_limits = RateLimits(
            AUTH_LOGIN="100/minute",
            AUTH_REGISTER="50/minute",
            JOB_CREATION="1000/hour",
        )

        # Assert
        assert rate_limits.AUTH_LOGIN == "100/minute"
        assert rate_limits.AUTH_REGISTER == "50/minute"
        assert rate_limits.JOB_CREATION == "1000/hour"
        # Other values use defaults
        assert rate_limits.AUTH_PASSWORD_RESET == "2/minute"


# =============================================================================
# TEST get_rate_limits - Environment-Based Configuration
# =============================================================================


@pytest.mark.unit
class TestGetRateLimits:
    """Test get_rate_limits() environment-based configuration."""

    def test_get_rate_limits_returns_production_defaults(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test returns production defaults when no environment set."""
        # Arrange - clear environment variables
        monkeypatch.delenv("TESTING", raising=False)
        monkeypatch.delenv("ENVIRONMENT", raising=False)

        # Act
        rate_limits = get_rate_limits()

        # Assert - Production defaults
        assert rate_limits.AUTH_LOGIN == "5/minute"
        assert rate_limits.AUTH_REGISTER == "3/minute"
        assert rate_limits.JOB_CREATION == "20/hour"
        assert rate_limits.BATCH_CREATION == "10/hour"

    def test_get_rate_limits_returns_testing_values(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test returns test-friendly values when TESTING=true."""
        # Arrange
        monkeypatch.setenv("TESTING", "true")

        # Act
        rate_limits = get_rate_limits()

        # Assert - Test-friendly high limits
        assert rate_limits.AUTH_LOGIN == "1000/minute"
        assert rate_limits.AUTH_REGISTER == "1000/minute"
        assert rate_limits.AUTH_PASSWORD_RESET == "1000/minute"
        assert rate_limits.AUTH_OAUTH == "1000/minute"
        assert rate_limits.AUTH_PASSKEY == "1000/minute"
        assert rate_limits.AUTH_SENSITIVE_OPERATION == "1000/minute"
        assert rate_limits.JOB_CREATION == "1000/hour"
        assert rate_limits.BATCH_CREATION == "1000/hour"
        assert rate_limits.ADMIN_OPERATIONS == "1000/hour"
        assert rate_limits.DEVELOPMENT == "1000/hour"

    def test_get_rate_limits_returns_development_values(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test returns development-friendly values when ENVIRONMENT=development."""
        # Arrange
        monkeypatch.setenv("ENVIRONMENT", "development")

        # Act
        rate_limits = get_rate_limits()

        # Assert - Development-friendly higher limits
        assert rate_limits.AUTH_LOGIN == "30/minute"
        assert rate_limits.AUTH_REGISTER == "15/minute"
        assert rate_limits.AUTH_PASSWORD_RESET == "10/minute"
        assert rate_limits.AUTH_OAUTH == "50/minute"
        assert rate_limits.AUTH_PASSKEY == "50/minute"
        assert rate_limits.AUTH_SENSITIVE_OPERATION == "20/minute"
        assert rate_limits.JOB_CREATION == "100/hour"
        assert rate_limits.BATCH_CREATION == "50/hour"
        assert rate_limits.ADMIN_OPERATIONS == "200/hour"
        assert rate_limits.DEVELOPMENT == "500/hour"

    def test_get_rate_limits_testing_takes_precedence_over_development(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test TESTING environment takes precedence over ENVIRONMENT."""
        # Arrange - Both testing and development set
        monkeypatch.setenv("TESTING", "true")
        monkeypatch.setenv("ENVIRONMENT", "development")

        # Act
        rate_limits = get_rate_limits()

        # Assert - Should use testing values, not development
        assert rate_limits.AUTH_LOGIN == "1000/minute"
        assert rate_limits.JOB_CREATION == "1000/hour"


# =============================================================================
# TEST get_rate_limits_instance - Singleton Pattern
# =============================================================================


@pytest.mark.unit
class TestGetRateLimitsInstance:
    """Test get_rate_limits_instance() singleton pattern."""

    def test_get_rate_limits_instance_creates_singleton(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test creates singleton instance on first call."""
        # Arrange
        monkeypatch.delenv("TESTING", raising=False)
        monkeypatch.delenv("ENVIRONMENT", raising=False)

        # Act
        instance = get_rate_limits_instance()

        # Assert
        assert instance is not None
        assert isinstance(instance, RateLimits)

    def test_get_rate_limits_instance_returns_same_instance(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test returns same instance on multiple calls."""
        # Arrange
        monkeypatch.delenv("TESTING", raising=False)
        monkeypatch.delenv("ENVIRONMENT", raising=False)

        # Act
        instance1 = get_rate_limits_instance()
        instance2 = get_rate_limits_instance()

        # Assert - Same instance
        assert instance1 is instance2

    def test_get_rate_limits_instance_uses_environment(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test singleton uses environment configuration."""
        # Arrange
        monkeypatch.setenv("TESTING", "true")

        # Act
        instance = get_rate_limits_instance()

        # Assert - Should have testing values
        assert instance.AUTH_LOGIN == "1000/minute"
        assert instance.JOB_CREATION == "1000/hour"


# =============================================================================
# TEST Module-Level rate_limits Variable
# =============================================================================


@pytest.mark.unit
class TestModuleLevelRateLimits:
    """Test module-level rate_limits variable."""

    def test_module_rate_limits_is_initialized(self) -> None:
        """Test module-level rate_limits is initialized on import."""
        # Arrange & Act
        from src.config.rate_limits import rate_limits

        # Assert
        assert rate_limits is not None
        assert isinstance(rate_limits, RateLimits)

    def test_module_rate_limits_has_same_values_as_singleton(self) -> None:
        """Test module-level rate_limits has same values as singleton."""
        # Arrange & Act
        from src.config.rate_limits import rate_limits

        instance = get_rate_limits_instance()

        # Assert - Should have same values (both production defaults)
        assert rate_limits.AUTH_LOGIN == instance.AUTH_LOGIN
        assert rate_limits.AUTH_REGISTER == instance.AUTH_REGISTER
        assert rate_limits.JOB_CREATION == instance.JOB_CREATION
        assert rate_limits.BATCH_CREATION == instance.BATCH_CREATION
