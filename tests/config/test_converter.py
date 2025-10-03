"""Comprehensive tests for src/config/converter.py.

Test coverage: 96 statements, 54% → 80%+
Following TEST_BUILDING.md MANDATORY standards with ZERO TOLERANCE.
"""

from pathlib import Path
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from src.config.converter import (
    ConverterConfig,
    HttpConfig,
    OutputConfig,
    RobotsConfig,
    ShopifyConfig,
)


@pytest.fixture(autouse=True)
def clear_converter_env_vars(monkeypatch):
    """Clear converter-related environment variables for consistent tests."""
    env_vars = [
        "USER_AGENT",
        "LOG_LEVEL",
        "DEFAULT_DIR",
        "IMAGES_SUBDIR",
    ]
    for var in env_vars:
        monkeypatch.delenv(var, raising=False)


# =============================================================================
# TEST HttpConfig - Initialization
# =============================================================================


@pytest.mark.unit
class TestHttpConfigInitialization:
    """Test HttpConfig initialization and defaults."""

    def test_initialization_with_default_values(self):
        """Test initialization with default values."""
        # Arrange & Act
        config = HttpConfig()

        # Assert
        assert config.timeout == 30
        assert config.max_concurrent == 10
        assert config.rate_limit_delay == 0.5
        assert config.max_retries == 3
        assert config.backoff_factor == 2.0
        assert config.pool_size == 20
        assert config.pool_timeout == 30

    def test_initialization_with_custom_values(self):
        """Test initialization with custom values."""
        # Arrange & Act
        config = HttpConfig(
            timeout=60,
            max_concurrent=20,
            rate_limit_delay=2.0,
            max_retries=5,
            backoff_factor=3.0,
            pool_size=50,
            pool_timeout=60,
        )

        # Assert
        assert config.timeout == 60
        assert config.max_concurrent == 20
        assert config.rate_limit_delay == 2.0
        assert config.max_retries == 5
        assert config.backoff_factor == 3.0
        assert config.pool_size == 50
        assert config.pool_timeout == 60

    def test_user_agent_default_value(self):
        """Test User-Agent has valid default."""
        # Arrange & Act
        config = HttpConfig()

        # Assert
        assert len(config.user_agent) >= 10
        assert "Python" in config.user_agent or "Mozilla" in config.user_agent


# =============================================================================
# TEST HttpConfig - User-Agent Validation
# =============================================================================


@pytest.mark.unit
class TestHttpConfigUserAgent:
    """Test HttpConfig.validate_user_agent() validation."""

    def test_validate_user_agent_accepts_valid_agent(self):
        """Test accepts valid User-Agent string."""
        # Arrange & Act
        config = HttpConfig(user_agent="Mozilla/5.0 Custom Agent")

        # Assert
        assert config.user_agent == "Mozilla/5.0 Custom Agent"

    def test_validate_user_agent_rejects_short_agent(self):
        """Test rejects User-Agent shorter than 10 characters."""
        # Arrange & Act & Assert
        with pytest.raises(ValueError, match="User-Agent must be at least 10 characters"):
            HttpConfig(user_agent="short")

    def test_validate_user_agent_rejects_empty_agent(self):
        """Test rejects empty User-Agent."""
        # Arrange & Act & Assert
        with pytest.raises(ValueError, match="User-Agent must be at least 10 characters"):
            HttpConfig(user_agent="")

    def test_validate_user_agent_strips_whitespace(self):
        """Test strips whitespace from User-Agent."""
        # Arrange & Act
        config = HttpConfig(user_agent="  Mozilla/5.0 Agent  ")

        # Assert
        assert config.user_agent == "Mozilla/5.0 Agent"
        assert not config.user_agent.startswith(" ")
        assert not config.user_agent.endswith(" ")


# =============================================================================
# TEST HttpConfig - Field Constraints
# =============================================================================


@pytest.mark.unit
class TestHttpConfigFieldConstraints:
    """Test Pydantic field constraints are enforced."""

    def test_timeout_enforces_minimum(self):
        """Test timeout enforces minimum value of 1."""
        # Arrange & Act & Assert
        with pytest.raises(ValidationError):
            HttpConfig(timeout=0)

    def test_timeout_enforces_maximum(self):
        """Test timeout enforces maximum value of 300."""
        # Arrange & Act & Assert
        with pytest.raises(ValidationError):
            HttpConfig(timeout=301)

    def test_max_retries_enforces_range(self):
        """Test max_retries enforces range 0-10."""
        # Arrange & Act & Assert - Too low
        with pytest.raises(ValidationError):
            HttpConfig(max_retries=-1)

        # Too high
        with pytest.raises(ValidationError):
            HttpConfig(max_retries=11)

    def test_backoff_factor_enforces_range(self):
        """Test backoff_factor enforces range 1.0-10.0."""
        # Arrange & Act & Assert - Too low
        with pytest.raises(ValidationError):
            HttpConfig(backoff_factor=0.5)

        # Too high
        with pytest.raises(ValidationError):
            HttpConfig(backoff_factor=11.0)


# =============================================================================
# TEST OutputConfig - Initialization
# =============================================================================


@pytest.mark.unit
class TestOutputConfigInitialization:
    """Test OutputConfig initialization and defaults."""

    def test_initialization_with_default_values(self):
        """Test initialization with default values."""
        # Arrange & Act
        config = OutputConfig()

        # Assert
        assert config.default_dir == "converted_content"
        assert config.images_subdir == "images"
        assert config.metadata_file == "metadata.txt"
        assert config.html_file == "converted_content.html"
        assert config.shopify_file == "shopify_ready_content.html"
        assert config.create_directories is True
        assert config.overwrite_existing is False
        assert config.max_file_size_mb == 100

    def test_initialization_with_custom_values(self):
        """Test initialization with custom values."""
        # Arrange & Act
        config = OutputConfig(
            default_dir="custom_output",
            images_subdir="imgs",
            metadata_file="meta.json",
            html_file="output.html",
            shopify_file="shopify.html",
            create_directories=False,
            overwrite_existing=True,
            max_file_size_mb=200,
        )

        # Assert
        assert config.default_dir == "custom_output"
        assert config.images_subdir == "imgs"
        assert config.metadata_file == "meta.json"
        assert config.html_file == "output.html"
        assert config.shopify_file == "shopify.html"
        assert config.create_directories is False
        assert config.overwrite_existing is True
        assert config.max_file_size_mb == 200


# =============================================================================
# TEST OutputConfig - Directory Name Validation
# =============================================================================


@pytest.mark.unit
class TestOutputConfigDirectoryValidation:
    """Test OutputConfig.validate_directory_names() validation."""

    def test_validate_directory_names_accepts_valid_names(self):
        """Test accepts valid directory names."""
        # Arrange & Act
        config = OutputConfig(default_dir="output", images_subdir="images")

        # Assert
        assert config.default_dir == "output"
        assert config.images_subdir == "images"

    def test_validate_directory_names_rejects_empty_name(self):
        """Test rejects empty directory name."""
        # Arrange & Act & Assert
        with pytest.raises(ValueError, match="Directory name cannot be empty"):
            OutputConfig(default_dir="")

    def test_validate_directory_names_rejects_parent_traversal(self):
        """Test rejects directory names with '..' (path traversal)."""
        # Arrange & Act & Assert
        with pytest.raises(ValueError, match="Directory cannot contain"):
            OutputConfig(default_dir="../output")

    def test_validate_directory_names_rejects_absolute_path(self):
        """Test rejects directory names starting with '/'."""
        # Arrange & Act & Assert
        with pytest.raises(ValueError, match="Directory cannot contain"):
            OutputConfig(default_dir="/absolute/path")

    def test_validate_directory_names_strips_whitespace(self):
        """Test strips whitespace from directory names."""
        # Arrange & Act
        config = OutputConfig(default_dir="  output  ", images_subdir="  images  ")

        # Assert
        assert config.default_dir == "output"
        assert config.images_subdir == "images"


# =============================================================================
# TEST OutputConfig - Path Properties
# =============================================================================


@pytest.mark.unit
class TestOutputConfigPathProperties:
    """Test OutputConfig path property methods."""

    def test_output_path_returns_path_object(self):
        """Test output_path returns Path object."""
        # Arrange
        config = OutputConfig(default_dir="custom_output")

        # Act
        path = config.output_path

        # Assert
        assert isinstance(path, Path)
        assert str(path) == "custom_output"

    def test_images_path_combines_output_and_images(self):
        """Test images_path combines output_path and images_subdir."""
        # Arrange
        config = OutputConfig(default_dir="output", images_subdir="imgs")

        # Act
        path = config.images_path

        # Assert
        assert isinstance(path, Path)
        assert str(path) == str(Path("output") / "imgs")


# =============================================================================
# TEST RobotsConfig - Initialization
# =============================================================================


@pytest.mark.unit
class TestRobotsConfigInitialization:
    """Test RobotsConfig initialization and defaults."""

    def test_initialization_with_default_values(self):
        """Test initialization with default values."""
        # Arrange & Act
        config = RobotsConfig()

        # Assert
        assert config.respect_robots_txt is True
        assert config.cache_duration == 3600
        assert config.crawl_delay == 1.0
        assert config.user_agent_for_robots == "*"

    def test_initialization_with_custom_values(self):
        """Test initialization with custom values."""
        # Arrange & Act
        config = RobotsConfig(
            respect_robots_txt=False,
            cache_duration=7200,
            crawl_delay=2.0,
            user_agent_for_robots="CustomBot",
        )

        # Assert
        assert config.respect_robots_txt is False
        assert config.cache_duration == 7200
        assert config.crawl_delay == 2.0
        assert config.user_agent_for_robots == "CustomBot"

    def test_cache_duration_enforces_range(self):
        """Test cache_duration enforces range 300-86400."""
        # Arrange & Act & Assert - Too low
        with pytest.raises(ValidationError):
            RobotsConfig(cache_duration=299)

        # Too high
        with pytest.raises(ValidationError):
            RobotsConfig(cache_duration=86401)


# =============================================================================
# TEST ShopifyConfig - Initialization
# =============================================================================


@pytest.mark.unit
class TestShopifyConfigInitialization:
    """Test ShopifyConfig initialization and defaults."""

    def test_initialization_with_default_values(self):
        """Test initialization with default values."""
        # Arrange & Act
        config = ShopifyConfig()

        # Assert
        assert isinstance(config.preserve_classes, set)
        assert isinstance(config.content_type_extensions, dict)
        assert config.minify_html is False
        assert config.preserve_comments is False
        assert config.convert_relative_urls is True

    def test_initialization_with_custom_values(self):
        """Test initialization with custom values."""
        # Arrange & Act
        config = ShopifyConfig(
            preserve_classes={"class1", "class2"},
            content_type_extensions={"image/png": ".png"},
            minify_html=True,
            preserve_comments=True,
            convert_relative_urls=False,
        )

        # Assert
        assert config.preserve_classes == {"class1", "class2"}
        assert config.content_type_extensions == {"image/png": ".png"}
        assert config.minify_html is True
        assert config.preserve_comments is True
        assert config.convert_relative_urls is False


# =============================================================================
# TEST ShopifyConfig - Preserve Classes Validation
# =============================================================================


@pytest.mark.unit
class TestShopifyConfigPreserveClasses:
    """Test ShopifyConfig.validate_preserve_classes() validation."""

    def test_validate_preserve_classes_accepts_set(self):
        """Test accepts set of class names."""
        # Arrange & Act
        config = ShopifyConfig(preserve_classes={"class1", "class2"})

        # Assert
        assert config.preserve_classes == {"class1", "class2"}

    def test_validate_preserve_classes_converts_string(self):
        """Test converts comma-separated string to set."""
        # Arrange & Act
        config = ShopifyConfig(preserve_classes="class1,class2,class3")

        # Assert
        assert isinstance(config.preserve_classes, set)
        assert config.preserve_classes == {"class1", "class2", "class3"}

    def test_validate_preserve_classes_converts_list(self):
        """Test converts list to set."""
        # Arrange & Act
        config = ShopifyConfig(preserve_classes=["class1", "class2"])

        # Assert
        assert isinstance(config.preserve_classes, set)
        assert config.preserve_classes == {"class1", "class2"}

    def test_validate_preserve_classes_strips_whitespace_from_string(self):
        """Test strips whitespace when converting from string."""
        # Arrange & Act
        config = ShopifyConfig(preserve_classes="  class1  ,  class2  ,  class3  ")

        # Assert
        assert config.preserve_classes == {"class1", "class2", "class3"}

    def test_validate_preserve_classes_rejects_invalid_type(self):
        """Test rejects invalid types."""
        # Arrange & Act & Assert
        with pytest.raises(ValueError, match="preserve_classes must be"):
            ShopifyConfig(preserve_classes=123)  # type: ignore[arg-type]


# =============================================================================
# TEST ConverterConfig - Initialization
# =============================================================================


@pytest.mark.unit
class TestConverterConfigInitialization:
    """Test ConverterConfig initialization and nested configs."""

    def test_initialization_with_default_values(self):
        """Test initialization with default values."""
        # Arrange & Act
        config = ConverterConfig()

        # Assert
        assert isinstance(config.http, HttpConfig)
        assert isinstance(config.output, OutputConfig)
        assert isinstance(config.robots, RobotsConfig)
        assert isinstance(config.shopify, ShopifyConfig)
        assert config.debug_mode is False
        assert config.log_level == "INFO"
        assert config.enable_metrics is True

    def test_initialization_creates_nested_configs(self):
        """Test nested config objects are properly initialized."""
        # Arrange & Act
        config = ConverterConfig()

        # Assert - verify nested configs have correct default values
        assert config.http.timeout == 30
        assert config.output.default_dir == "converted_content"
        assert config.robots.respect_robots_txt is True
        assert isinstance(config.shopify.preserve_classes, set)

    def test_initialization_with_custom_nested_values(self):
        """Test initialization with custom nested config values."""
        # Arrange & Act
        config = ConverterConfig(
            http=HttpConfig(timeout=60, max_concurrent=20),
            output=OutputConfig(default_dir="custom"),
            robots=RobotsConfig(crawl_delay=2.0),
            shopify=ShopifyConfig(minify_html=True),
        )

        # Assert
        assert config.http.timeout == 60
        assert config.http.max_concurrent == 20
        assert config.output.default_dir == "custom"
        assert config.robots.crawl_delay == 2.0
        assert config.shopify.minify_html is True


# =============================================================================
# TEST ConverterConfig - Log Level Validation
# =============================================================================


@pytest.mark.unit
class TestConverterConfigLogLevel:
    """Test ConverterConfig.validate_log_level() validation."""

    @pytest.mark.parametrize("level", ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])
    def test_validate_log_level_accepts_valid_levels(self, level):
        """Test accepts all valid log levels."""
        # Arrange & Act
        config = ConverterConfig(log_level=level)

        # Assert
        assert config.log_level == level

    @pytest.mark.parametrize("level", ["debug", "info", "warning", "error", "critical"])
    def test_validate_log_level_normalizes_case(self, level):
        """Test normalizes log level to uppercase."""
        # Arrange & Act
        config = ConverterConfig(log_level=level)

        # Assert
        assert config.log_level == level.upper()

    def test_validate_log_level_rejects_invalid_level(self):
        """Test rejects invalid log level."""
        # Arrange & Act & Assert
        with pytest.raises(ValueError, match="log_level must be one of"):
            ConverterConfig(log_level="INVALID")


# =============================================================================
# TEST ConverterConfig - get_http_headers Method
# =============================================================================


@pytest.mark.unit
class TestConverterConfigGetHttpHeaders:
    """Test ConverterConfig.get_http_headers() method."""

    def test_get_http_headers_returns_correct_structure(self):
        """Test returns dictionary with all required headers."""
        # Arrange
        config = ConverterConfig()

        # Act
        headers = config.get_http_headers()

        # Assert
        assert isinstance(headers, dict)
        assert "User-Agent" in headers
        assert "Accept" in headers
        assert "Accept-Language" in headers
        assert "Accept-Encoding" in headers
        assert "Connection" in headers

    def test_get_http_headers_includes_custom_user_agent(self):
        """Test includes custom User-Agent from http config."""
        # Arrange
        custom_agent = "CustomBot/1.0"
        config = ConverterConfig(http=HttpConfig(user_agent=custom_agent))

        # Act
        headers = config.get_http_headers()

        # Assert
        assert headers["User-Agent"] == custom_agent

    def test_get_http_headers_has_correct_values(self):
        """Test headers have correct standard values."""
        # Arrange
        config = ConverterConfig()

        # Act
        headers = config.get_http_headers()

        # Assert
        assert "text/html" in headers["Accept"]
        assert "en-US" in headers["Accept-Language"]
        assert "gzip" in headers["Accept-Encoding"]
        assert headers["Connection"] == "keep-alive"


# =============================================================================
# TEST ConverterConfig - validate_output_directory Method
# =============================================================================


@pytest.mark.unit
class TestConverterConfigValidateOutputDirectory:
    """Test ConverterConfig.validate_output_directory() method."""

    def test_validate_output_directory_creates_directories_when_enabled(
        self, tmp_path, monkeypatch
    ):
        """Test creates output directories when create_directories is True."""
        # Arrange - use relative path and chdir to tmp_path to avoid absolute path validation
        monkeypatch.chdir(tmp_path)
        output_dir = "test_output"
        config = ConverterConfig(
            output=OutputConfig(default_dir=output_dir, create_directories=True)
        )

        # Act
        config.validate_output_directory()

        # Assert
        assert Path(output_dir).exists()
        assert (Path(output_dir) / "images").exists()

    def test_validate_output_directory_does_not_create_when_disabled(self, tmp_path, monkeypatch):
        """Test does not create directories when create_directories is False."""
        # Arrange - use relative path
        monkeypatch.chdir(tmp_path)
        output_dir = "existing_output"
        Path(output_dir).mkdir()  # Create directory manually
        config = ConverterConfig(
            output=OutputConfig(default_dir=output_dir, create_directories=False)
        )

        # Act - should not raise since directory exists
        config.validate_output_directory()

        # Assert - only parent should exist, images subdir should not be auto-created
        assert Path(output_dir).exists()

    def test_validate_output_directory_raises_when_disabled_and_missing(
        self, tmp_path, monkeypatch
    ):
        """Test raises error when create_directories is False and directory missing."""
        # Arrange - use relative path
        monkeypatch.chdir(tmp_path)
        output_dir = "nonexistent"
        config = ConverterConfig(
            output=OutputConfig(default_dir=output_dir, create_directories=False)
        )

        # Act & Assert
        with pytest.raises(ValueError, match="Output directory .* does not exist"):
            config.validate_output_directory()

    def test_validate_output_directory_handles_creation_error(self, tmp_path, monkeypatch):
        """Test handles OSError when directory creation fails."""
        # Arrange - use relative path
        monkeypatch.chdir(tmp_path)
        output_dir = "test_output"
        config = ConverterConfig(
            output=OutputConfig(default_dir=output_dir, create_directories=True)
        )

        # Act & Assert - mock mkdir to raise OSError
        with patch.object(Path, "mkdir", side_effect=OSError("Permission denied")):
            with pytest.raises(ValueError, match="Cannot create output directory"):
                config.validate_output_directory()
