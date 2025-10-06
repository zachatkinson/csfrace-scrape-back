"""Comprehensive tests for browser configuration - MANDATORY TEST_BUILDING.md compliance.

This module tests the OptimizedBrowserConfig dataclass with complete coverage:
- Configuration initialization
- Factory methods (for_ci, for_performance_tests, for_simple_tests)
- Browser arguments and context options
- Performance optimization settings
- Security validation

ALL tests follow MANDATORY TEST_BUILDING.md patterns:
- AAA pattern with explicit comments
- Factory fixtures for DRY principle
- Comprehensive configuration testing
- Performance benchmarks with specific thresholds
"""

import time

import pytest

from src.rendering.browser_config import OptimizedBrowserConfig

# ============================================================================
# Test Fixtures - DRY Principle
# ============================================================================


@pytest.fixture
def default_config() -> OptimizedBrowserConfig:
    """Factory for default OptimizedBrowserConfig - DRY principle."""
    return OptimizedBrowserConfig()


# ============================================================================
# Configuration Initialization Tests
# ============================================================================


@pytest.mark.unit
class TestBrowserConfigInitialization:
    """Tests for OptimizedBrowserConfig initialization."""

    def test_config_initialization_with_defaults(self) -> None:
        """Test config initializes with default values - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # (no setup needed)

        # Act - MANDATORY
        config = OptimizedBrowserConfig()

        # Assert - MANDATORY
        assert config.chromium_args is not None
        assert config.webkit_args is not None
        assert config.context_options is not None
        assert config.navigation_options is not None

    def test_chromium_args_include_required_flags(
        self, default_config: OptimizedBrowserConfig
    ) -> None:
        """Test chromium args include required flags - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        required_flags = [
            "--disable-blink-features=AutomationControlled",
            "--disable-dev-shm-usage",
            "--disable-gpu",
            "--no-sandbox",
        ]

        # Act - MANDATORY
        args = default_config.chromium_args

        # Assert - MANDATORY
        for flag in required_flags:
            assert flag in args

    def test_webkit_args_include_required_flags(
        self, default_config: OptimizedBrowserConfig
    ) -> None:
        """Test webkit args include required flags - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        required_flags = [
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-dev-shm-usage",
        ]

        # Act - MANDATORY
        args = default_config.webkit_args

        # Assert - MANDATORY
        for flag in required_flags:
            assert flag in args

    def test_context_options_include_viewport(self, default_config: OptimizedBrowserConfig) -> None:
        """Test context options include viewport settings - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # (default_config from fixture)

        # Act - MANDATORY
        options = default_config.context_options

        # Assert - MANDATORY
        assert "viewport" in options
        assert options["viewport"]["width"] == 1280
        assert options["viewport"]["height"] == 720

    def test_context_options_enable_javascript(
        self, default_config: OptimizedBrowserConfig
    ) -> None:
        """Test context options enable JavaScript by default - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # (default_config from fixture)

        # Act - MANDATORY
        options = default_config.context_options

        # Assert - MANDATORY
        assert options["java_script_enabled"] is True

    def test_navigation_options_use_domcontentloaded(
        self, default_config: OptimizedBrowserConfig
    ) -> None:
        """Test navigation options use domcontentloaded - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # (default_config from fixture)

        # Act - MANDATORY
        options = default_config.navigation_options

        # Assert - MANDATORY
        assert options["wait_until"] == "domcontentloaded"
        assert options["timeout"] == 10000


# ============================================================================
# Factory Methods Tests
# ============================================================================


@pytest.mark.unit
class TestFactoryMethods:
    """Tests for factory methods."""

    def test_for_ci_returns_default_config(self) -> None:
        """Test for_ci returns default configuration - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # (no setup needed)

        # Act - MANDATORY
        config = OptimizedBrowserConfig.for_ci()

        # Assert - MANDATORY
        assert isinstance(config, OptimizedBrowserConfig)
        assert config.navigation_options["wait_until"] == "domcontentloaded"

    def test_for_performance_tests_uses_networkidle(self) -> None:
        """Test for_performance_tests uses networkidle wait - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # (no setup needed)

        # Act - MANDATORY
        config = OptimizedBrowserConfig.for_performance_tests()

        # Assert - MANDATORY
        assert config.navigation_options["wait_until"] == "networkidle"

    def test_for_performance_tests_uses_larger_viewport(self) -> None:
        """Test for_performance_tests uses larger viewport - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # (no setup needed)

        # Act - MANDATORY
        config = OptimizedBrowserConfig.for_performance_tests()

        # Assert - MANDATORY
        assert config.context_options["viewport"]["width"] == 1920
        assert config.context_options["viewport"]["height"] == 1080

    def test_for_simple_tests_disables_javascript(self) -> None:
        """Test for_simple_tests disables JavaScript - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # (no setup needed)

        # Act - MANDATORY
        config = OptimizedBrowserConfig.for_simple_tests()

        # Assert - MANDATORY
        assert config.context_options["java_script_enabled"] is False

    def test_for_simple_tests_uses_shorter_timeout(self) -> None:
        """Test for_simple_tests uses shorter timeout - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # (no setup needed)

        # Act - MANDATORY
        config = OptimizedBrowserConfig.for_simple_tests()

        # Assert - MANDATORY
        assert config.navigation_options["timeout"] == 5000


# ============================================================================
# Configuration Options Tests
# ============================================================================


@pytest.mark.unit
class TestConfigurationOptions:
    """Tests for configuration options."""

    def test_context_options_ignore_https_errors(
        self, default_config: OptimizedBrowserConfig
    ) -> None:
        """Test context options ignore HTTPS errors - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # (default_config from fixture)

        # Act - MANDATORY
        options = default_config.context_options

        # Assert - MANDATORY
        assert options["ignore_https_errors"] is True

    def test_context_options_bypass_csp(self, default_config: OptimizedBrowserConfig) -> None:
        """Test context options bypass CSP - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # (default_config from fixture)

        # Act - MANDATORY
        options = default_config.context_options

        # Assert - MANDATORY
        assert options["bypass_csp"] is True

    def test_context_options_disable_downloads(
        self, default_config: OptimizedBrowserConfig
    ) -> None:
        """Test context options disable downloads - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # (default_config from fixture)

        # Act - MANDATORY
        options = default_config.context_options

        # Assert - MANDATORY
        assert options["accept_downloads"] is False

    def test_context_options_set_locale(self, default_config: OptimizedBrowserConfig) -> None:
        """Test context options set locale to en-US - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # (default_config from fixture)

        # Act - MANDATORY
        options = default_config.context_options

        # Assert - MANDATORY
        assert options["locale"] == "en-US"
        assert options["timezone_id"] == "UTC"

    def test_context_options_include_http_headers(
        self, default_config: OptimizedBrowserConfig
    ) -> None:
        """Test context options include HTTP headers - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # (default_config from fixture)

        # Act - MANDATORY
        options = default_config.context_options

        # Assert - MANDATORY
        assert "extra_http_headers" in options
        assert "Accept-Language" in options["extra_http_headers"]


# ============================================================================
# Configuration Modification Tests
# ============================================================================


@pytest.mark.unit
class TestConfigurationModification:
    """Tests for configuration modification."""

    def test_chromium_args_can_be_modified(self) -> None:
        """Test chromium args can be modified after initialization - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        config = OptimizedBrowserConfig()
        original_count = len(config.chromium_args)

        # Act - MANDATORY
        config.chromium_args.append("--custom-flag")

        # Assert - MANDATORY
        assert len(config.chromium_args) == original_count + 1
        assert "--custom-flag" in config.chromium_args

    def test_context_options_can_be_modified(self) -> None:
        """Test context options can be modified after initialization - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        config = OptimizedBrowserConfig()

        # Act - MANDATORY
        config.context_options["custom_option"] = "custom_value"

        # Assert - MANDATORY
        assert config.context_options["custom_option"] == "custom_value"

    def test_navigation_options_can_be_modified(self) -> None:
        """Test navigation options can be modified after initialization - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        config = OptimizedBrowserConfig()

        # Act - MANDATORY
        config.navigation_options["timeout"] = 15000

        # Assert - MANDATORY
        assert config.navigation_options["timeout"] == 15000


# ============================================================================
# MANDATORY Security Tests
# ============================================================================


@pytest.mark.security
@pytest.mark.unit
class TestBrowserConfigSecurity:
    """MANDATORY security tests for browser configuration."""

    def test_sandbox_disabled_for_performance(self, default_config: OptimizedBrowserConfig) -> None:
        """MANDATORY security test - sandbox disabled for CI performance."""
        # Arrange - MANDATORY
        # Note: Disabling sandbox is intentional for CI/Docker performance
        # Production deployments should enable sandbox

        # Act - MANDATORY
        args = default_config.chromium_args

        # Assert - MANDATORY
        assert "--no-sandbox" in args
        # This is documented as intentional for containers

    def test_web_security_disabled_for_testing(
        self, default_config: OptimizedBrowserConfig
    ) -> None:
        """MANDATORY security test - web security disabled for testing."""
        # Arrange - MANDATORY
        # Note: Disabling web security is intentional for testing environments
        # Production scraping should NOT disable web security

        # Act - MANDATORY
        args = default_config.chromium_args

        # Assert - MANDATORY
        assert "--disable-web-security" in args
        # This is documented as intentional for testing

    def test_csp_bypass_enabled_for_testing(self, default_config: OptimizedBrowserConfig) -> None:
        """MANDATORY security test - CSP bypass enabled for testing."""
        # Arrange - MANDATORY
        # Note: Bypassing CSP is intentional for testing environments

        # Act - MANDATORY
        options = default_config.context_options

        # Assert - MANDATORY
        assert options["bypass_csp"] is True
        # This is documented as intentional for testing

    def test_https_errors_ignored_for_testing(self, default_config: OptimizedBrowserConfig) -> None:
        """MANDATORY security test - HTTPS errors ignored for testing."""
        # Arrange - MANDATORY
        # Note: Ignoring HTTPS errors is intentional for testing environments

        # Act - MANDATORY
        options = default_config.context_options

        # Assert - MANDATORY
        assert options["ignore_https_errors"] is True
        # This is documented as intentional for testing


# ============================================================================
# MANDATORY Performance Benchmarks
# ============================================================================


@pytest.mark.performance
@pytest.mark.unit
class TestBrowserConfigPerformance:
    """MANDATORY performance tests for browser configuration."""

    def test_config_initialization_performance(self) -> None:
        """MANDATORY performance test - config initialization speed."""
        # Arrange - MANDATORY
        iterations = 1000

        # Act - MANDATORY
        start_time = time.perf_counter()

        for _ in range(iterations):
            OptimizedBrowserConfig()

        end_time = time.perf_counter()
        execution_time = end_time - start_time

        # Assert - MANDATORY
        avg_time = execution_time / iterations
        assert avg_time < 0.001  # <1ms per initialization
        assert execution_time < 1.0  # Total <1s for 1000 initializations

    def test_factory_method_performance(self) -> None:
        """MANDATORY performance test - factory method speed."""
        # Arrange - MANDATORY
        iterations = 1000

        # Act - MANDATORY
        start_time = time.perf_counter()

        for _ in range(iterations):
            OptimizedBrowserConfig.for_ci()

        end_time = time.perf_counter()
        execution_time = end_time - start_time

        # Assert - MANDATORY
        avg_time = execution_time / iterations
        assert avg_time < 0.001  # <1ms per factory call
        assert execution_time < 1.0  # Total <1s for 1000 calls

    def test_config_modification_performance(self) -> None:
        """MANDATORY performance test - config modification speed."""
        # Arrange - MANDATORY
        config = OptimizedBrowserConfig()
        iterations = 10000

        # Act - MANDATORY
        start_time = time.perf_counter()

        for i in range(iterations):
            config.context_options[f"key_{i}"] = f"value_{i}"

        end_time = time.perf_counter()
        execution_time = end_time - start_time

        # Assert - MANDATORY
        avg_time = execution_time / iterations
        assert avg_time < 0.00001  # <10μs per modification
        assert execution_time < 0.1  # Total <100ms for 10000 modifications
