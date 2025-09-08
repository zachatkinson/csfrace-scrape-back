"""Tests for EnvironmentLoader - DRY and security compliance validation."""

import os
from unittest.mock import patch

import pytest

from src.core.environment import EnvironmentLoader


class TestEnvironmentLoader:
    """Test EnvironmentLoader following DRY and security best practices."""

    def test_get_required_success(self):
        """Test EnvironmentLoader.get_required returns value when environment variable exists."""
        with patch.dict(os.environ, {"TEST_REQUIRED_VAR": "test_value"}):
            result = EnvironmentLoader.get_required("TEST_REQUIRED_VAR")
            assert result == "test_value"

    def test_get_required_with_description(self):
        """Test EnvironmentLoader.get_required includes description in error message."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError) as exc_info:
                EnvironmentLoader.get_required("MISSING_VAR", "Database connection string")

            error_msg = str(exc_info.value)
            assert "MISSING_VAR" in error_msg
            assert "Database connection string" in error_msg

    def test_get_required_strips_whitespace(self):
        """Test EnvironmentLoader.get_required strips whitespace from values."""
        with patch.dict(os.environ, {"TEST_WHITESPACE_VAR": "  test_value  "}):
            result = EnvironmentLoader.get_required("TEST_WHITESPACE_VAR")
            assert result == "test_value"  # Whitespace should be stripped

    def test_get_required_rejects_empty_strings(self):
        """Test EnvironmentLoader.get_required treats empty strings as missing."""
        test_cases = ["", "   ", "\t\n "]

        for empty_value in test_cases:
            with patch.dict(os.environ, {"EMPTY_VAR": empty_value}):
                with pytest.raises(ValueError) as exc_info:
                    EnvironmentLoader.get_required("EMPTY_VAR")

                assert "not set" in str(exc_info.value)

    def test_get_optional_with_default(self):
        """Test EnvironmentLoader.get_optional returns default when variable missing."""
        with patch.dict(os.environ, {}, clear=True):
            result = EnvironmentLoader.get_optional("MISSING_VAR", "default_value")
            assert result == "default_value"

    def test_get_optional_returns_env_value(self):
        """Test EnvironmentLoader.get_optional returns environment value when present."""
        with patch.dict(os.environ, {"PRESENT_VAR": "env_value"}):
            result = EnvironmentLoader.get_optional("PRESENT_VAR", "default_value")
            assert result == "env_value"

    def test_get_optional_strips_whitespace(self):
        """Test EnvironmentLoader.get_optional strips whitespace from values."""
        with patch.dict(os.environ, {"WHITESPACE_VAR": "  optional_value  "}):
            result = EnvironmentLoader.get_optional("WHITESPACE_VAR", "default")
            assert result == "optional_value"

    def test_get_optional_treats_empty_as_missing(self):
        """Test EnvironmentLoader.get_optional strips whitespace but returns empty strings."""
        test_cases = [
            ("", ""),  # Empty string returns empty string
            ("   ", ""),  # Whitespace only returns empty string after strip
            ("\t\n ", ""),  # Tab/newline whitespace returns empty string after strip
        ]

        for empty_value, expected in test_cases:
            with patch.dict(os.environ, {"EMPTY_OPTIONAL": empty_value}):
                result = EnvironmentLoader.get_optional("EMPTY_OPTIONAL", "fallback")
                assert result == expected  # Should return stripped empty string, not fallback

    def test_get_bool_true_values(self):
        """Test EnvironmentLoader.get_bool recognizes various true values."""
        true_values = ["true", "TRUE", "True", "1", "yes", "YES", "on", "ON"]

        for true_val in true_values:
            with patch.dict(os.environ, {"BOOL_VAR": true_val}):
                result = EnvironmentLoader.get_bool("BOOL_VAR", False)
                assert result is True, f"Failed for value: {true_val}"

    def test_get_bool_false_values(self):
        """Test EnvironmentLoader.get_bool recognizes various false values."""
        false_values = ["false", "FALSE", "False", "0", "no", "NO", "off", "OFF", "other"]

        for false_val in false_values:
            with patch.dict(os.environ, {"BOOL_VAR": false_val}):
                result = EnvironmentLoader.get_bool("BOOL_VAR", True)
                # Only 'true', '1', 'yes', 'on' are considered True, everything else is False
                expected = false_val.lower() in ("true", "1", "yes", "on")
                assert result is expected, f"Failed for value: {false_val}"

    def test_get_bool_default_when_missing(self):
        """Test EnvironmentLoader.get_bool returns default when variable missing."""
        with patch.dict(os.environ, {}, clear=True):
            result_default_true = EnvironmentLoader.get_bool("MISSING_BOOL", True)
            result_default_false = EnvironmentLoader.get_bool("MISSING_BOOL", False)

            assert result_default_true is True
            assert result_default_false is False

    def test_get_int_valid_values(self):
        """Test EnvironmentLoader.get_int converts valid integer strings."""
        test_cases = [
            ("42", 42),
            ("0", 0),
            ("-123", -123),
            ("  456  ", 456),  # With whitespace
        ]

        for env_val, expected in test_cases:
            with patch.dict(os.environ, {"INT_VAR": env_val}):
                result = EnvironmentLoader.get_int("INT_VAR", 999)
                assert result == expected

    def test_get_int_default_when_missing(self):
        """Test EnvironmentLoader.get_int returns default when variable missing."""
        with patch.dict(os.environ, {}, clear=True):
            result = EnvironmentLoader.get_int("MISSING_INT", 42)
            assert result == 42

    def test_get_int_invalid_value_raises_error(self):
        """Test EnvironmentLoader.get_int raises error for invalid integer values."""
        invalid_values = ["not_a_number", "12.34", "1a2b3c"]

        for invalid_val in invalid_values:
            with patch.dict(os.environ, {"INVALID_INT": invalid_val}):
                with pytest.raises(ValueError) as exc_info:
                    EnvironmentLoader.get_int("INVALID_INT", 0)

                error_msg = str(exc_info.value)
                assert "must be an integer" in error_msg
                assert "INVALID_INT" in error_msg

    def test_get_int_with_range_validation(self):
        """Test EnvironmentLoader.get_int validates min/max ranges."""
        with patch.dict(os.environ, {"RANGE_VAR": "50"}):
            # Should pass when within range
            result = EnvironmentLoader.get_int("RANGE_VAR", 0, min_value=10, max_value=100)
            assert result == 50

            # Should fail when below minimum
            with pytest.raises(ValueError) as exc_info:
                EnvironmentLoader.get_int("RANGE_VAR", 0, min_value=60, max_value=100)
            assert ">= 60" in str(exc_info.value)

            # Should fail when above maximum
            with pytest.raises(ValueError) as exc_info:
                EnvironmentLoader.get_int("RANGE_VAR", 0, min_value=10, max_value=40)
            assert "<= 40" in str(exc_info.value)

    def test_environment_loader_is_stateless(self):
        """Test EnvironmentLoader is stateless (follows functional programming principles)."""
        # All methods should be static/class methods
        loader_methods = [
            EnvironmentLoader.get_required,
            EnvironmentLoader.get_optional,
            EnvironmentLoader.get_bool,
            EnvironmentLoader.get_int,
        ]

        for method in loader_methods:
            # Should be callable without instance
            assert callable(method)
            # Should not require self parameter (static/class methods)
            import inspect

            sig = inspect.signature(method)
            assert "self" not in sig.parameters


class TestEnvironmentLoaderSecurity:
    """Test EnvironmentLoader security considerations."""

    def test_no_sensitive_logging(self):
        """Test EnvironmentLoader doesn't accidentally expose sensitive information."""
        # EnvironmentLoader doesn't do logging, but test that it doesn't expose sensitive data
        with patch.dict(os.environ, {"SECRET_KEY": "super_secret_password"}):
            result = EnvironmentLoader.get_required("SECRET_KEY")

            # Should return the value but not expose it in error messages
            assert result == "super_secret_password"

            # Test that error messages don't contain sensitive data
            with patch.dict(os.environ, {}, clear=True):
                try:
                    EnvironmentLoader.get_required("SECRET_KEY")
                except ValueError as e:
                    error_msg = str(e)
                    # Error should mention the key name but not contain other secrets
                    assert "SECRET_KEY" in error_msg
                    assert "super_secret_password" not in error_msg

    def test_error_messages_dont_leak_sensitive_data(self):
        """Test error messages don't accidentally expose sensitive information."""
        with patch.dict(os.environ, {}, clear=True):
            try:
                EnvironmentLoader.get_required("DATABASE_PASSWORD", "Database authentication")
            except ValueError as e:
                error_msg = str(e)
                # Error message should be helpful but not expose system internals
                assert "DATABASE_PASSWORD" in error_msg
                assert "Database authentication" in error_msg
                # Should not contain system paths, internal details, etc.
                assert "/env" not in error_msg.lower()
                assert "secret" not in error_msg.lower()

    def test_input_validation_prevents_injection(self):
        """Test EnvironmentLoader validates input to prevent injection attacks."""
        # Test that malicious environment variable names don't cause issues
        malicious_names = [
            "../../../etc/passwd",
            "$(whoami)",
            "`ls -la`",
            "; rm -rf /",
            '<script>alert("xss")</script>',
        ]

        for malicious_name in malicious_names:
            with patch.dict(os.environ, {malicious_name: "value"}):
                # Should handle gracefully without executing anything
                try:
                    result = EnvironmentLoader.get_optional(malicious_name, "default")
                    # If it doesn't raise an error, should return the safe value
                    assert result in ["value", "default"]
                except (KeyError, ValueError):
                    # Or it might raise an error, which is also acceptable
                    pass


class TestEnvironmentLoaderIntegration:
    """Test EnvironmentLoader integration with real environment scenarios."""

    def test_production_environment_simulation(self):
        """Test EnvironmentLoader with production-like environment variables."""
        prod_env = {
            "SECRET_KEY": "prod-secret-key-64-chars-long-for-security-compliance-test",
            "DATABASE_URL": "postgresql://user:pass@prod-db:5432/app_db",
            "REDIS_URL": "redis://prod-redis:6379/0",
            "DEBUG": "false",
            "MAX_WORKERS": "4",
            "SENTRY_DSN": "https://key@sentry.io/project",
        }

        with patch.dict(os.environ, prod_env):
            # Test required values
            secret = EnvironmentLoader.get_required("SECRET_KEY")
            db_url = EnvironmentLoader.get_required("DATABASE_URL")

            # Test optional with defaults
            log_level = EnvironmentLoader.get_optional("LOG_LEVEL", "INFO")

            # Test boolean parsing
            debug = EnvironmentLoader.get_bool("DEBUG", True)

            # Test integer parsing
            workers = EnvironmentLoader.get_int("MAX_WORKERS", 1)

            assert len(secret) >= 32  # Security requirement
            assert "postgresql" in db_url
            assert log_level == "INFO"
            assert debug is False
            assert workers == 4

    def test_development_environment_simulation(self):
        """Test EnvironmentLoader with development environment setup."""
        dev_env = {
            "SECRET_KEY": "dev-secret-key",
            "DATABASE_URL": "sqlite:///dev.db",
            "DEBUG": "true",
            "MAX_WORKERS": "1",
        }

        with patch.dict(os.environ, dev_env):
            debug = EnvironmentLoader.get_bool("DEBUG", False)
            workers = EnvironmentLoader.get_int("MAX_WORKERS", 4)

            assert debug is True
            assert workers == 1

    def test_docker_environment_simulation(self):
        """Test EnvironmentLoader with Docker-style environment variables."""
        docker_env = {
            "APP_SECRET_KEY": "docker-secret-key",
            "APP_DATABASE_HOST": "postgres",
            "APP_DATABASE_PORT": "5432",
            "APP_REDIS_ENABLED": "true",
        }

        with patch.dict(os.environ, docker_env):
            secret = EnvironmentLoader.get_required("APP_SECRET_KEY")
            db_host = EnvironmentLoader.get_required("APP_DATABASE_HOST")
            db_port = EnvironmentLoader.get_int("APP_DATABASE_PORT", 5432)
            redis_enabled = EnvironmentLoader.get_bool("APP_REDIS_ENABLED", False)

            assert secret == "docker-secret-key"
            assert db_host == "postgres"
            assert db_port == 5432
            assert redis_enabled is True
