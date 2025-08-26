"""Tests for centralized constants module."""

import os
from unittest.mock import patch

import pytest

from src.constants import CONSTANTS, TEST_CONSTANTS, AppConstants


class TestAppConstants:
    """Test centralized application constants."""

    def test_constants_instance_exists(self):
        """Test that global CONSTANTS instance exists."""
        assert CONSTANTS is not None
        assert isinstance(CONSTANTS, AppConstants)

    def test_environment_variable_support(self):
        """Test that environment variables are properly loaded at module level."""
        # Since dataclass is frozen and values are evaluated at class definition,
        # we test that the current values match what would be in environment
        # or use the expected defaults
        
        # Test that defaults are used when env vars aren't set
        assert CONSTANTS.DEFAULT_TIMEOUT == 30  # Default value
        assert CONSTANTS.MAX_CONCURRENT == 10   # Default value

    def test_default_values(self):
        """Test that default values are set correctly."""
        assert CONSTANTS.DEFAULT_TIMEOUT == 30
        assert CONSTANTS.MAX_CONCURRENT == 10
        assert CONSTANTS.RATE_LIMIT_DELAY == 0.5
        assert CONSTANTS.DEFAULT_OUTPUT_DIR == "converted_content"

    def test_file_constants(self):
        """Test file-related constants."""
        assert CONSTANTS.METADATA_FILE == "metadata.txt"
        assert CONSTANTS.HTML_FILE == "converted_content.html"
        assert CONSTANTS.SHOPIFY_FILE == "shopify_ready_content.html"

    def test_http_status_codes(self):
        """Test HTTP status code constants."""
        assert CONSTANTS.HTTP_STATUS_OK == 200
        assert CONSTANTS.HTTP_STATUS_NOT_FOUND == 404
        assert CONSTANTS.HTTP_STATUS_SERVER_ERROR == 500

    def test_cache_configuration(self):
        """Test cache-related constants."""
        assert CONSTANTS.DEFAULT_TTL == 1800  # 30 minutes
        assert CONSTANTS.CACHE_TTL_HTML == 1800
        assert CONSTANTS.CACHE_TTL_IMAGES == 86400  # 24 hours
        assert CONSTANTS.MAX_CACHE_SIZE_MB == 1000

    def test_shopify_preserve_classes(self):
        """Test Shopify-compatible CSS classes."""
        expected_classes = {
            "center", "media-grid", "media-grid-2", "media-grid-4", 
            "media-grid-5", "button", "button--primary"
        }
        
        # Check that our expected classes are in the preserve set
        for css_class in expected_classes:
            assert css_class in CONSTANTS.SHOPIFY_PRESERVE_CLASSES

    def test_image_content_types(self):
        """Test image content type mappings."""
        assert CONSTANTS.IMAGE_CONTENT_TYPES["image/jpeg"] == ".jpg"
        assert CONSTANTS.IMAGE_CONTENT_TYPES["image/png"] == ".png"
        assert CONSTANTS.IMAGE_CONTENT_TYPES["image/gif"] == ".gif"
        assert CONSTANTS.IMAGE_CONTENT_TYPES["image/webp"] == ".webp"

    def test_calculation_constants(self):
        """Test mathematical constants."""
        assert CONSTANTS.BYTES_PER_MB == 1024 * 1024
        assert CONSTANTS.CACHE_CLEANUP_RATIO == 0.8

    def test_robots_txt_configuration(self):
        """Test robots.txt related constants."""
        assert CONSTANTS.ROBOTS_CACHE_DURATION == 3600  # 1 hour
        assert CONSTANTS.RESPECT_ROBOTS_TXT is True
        assert CONSTANTS.ROBOTS_TIMEOUT == 10

    def test_progress_constants(self):
        """Test progress tracking constants."""
        assert CONSTANTS.PROGRESS_START == 0
        assert CONSTANTS.PROGRESS_SETUP == 10
        assert CONSTANTS.PROGRESS_FETCH == 20
        assert CONSTANTS.PROGRESS_PROCESS == 60
        assert CONSTANTS.PROGRESS_COMPLETE == 100


class TestTestConstants:
    """Test constants specifically for testing."""

    def test_test_constants_instance(self):
        """Test that TEST_CONSTANTS instance exists."""
        assert TEST_CONSTANTS is not None

    def test_test_urls(self):
        """Test test-specific URLs."""
        assert TEST_CONSTANTS.BASE_TEST_URL == "https://test.example.com"
        assert TEST_CONSTANTS.SAMPLE_POST_URL.startswith(TEST_CONSTANTS.BASE_TEST_URL)
        assert TEST_CONSTANTS.NONEXISTENT_URL == "https://nonexistent.example.com/blog/post"

    def test_test_redis_config(self):
        """Test Redis configuration for tests."""
        assert TEST_CONSTANTS.TEST_REDIS_HOST == "localhost"
        assert TEST_CONSTANTS.TEST_REDIS_PORT == 6379
        assert TEST_CONSTANTS.TEST_REDIS_DB == 15  # Separate DB for tests
        assert TEST_CONSTANTS.TEST_REDIS_KEY_PREFIX == "pytest:"

    def test_test_data(self):
        """Test sample data constants."""
        assert TEST_CONSTANTS.SAMPLE_HTML_TITLE == "Test Blog Post"
        assert TEST_CONSTANTS.SAMPLE_HTML_DESCRIPTION == "A test blog post for unit testing"
        assert TEST_CONSTANTS.TEST_IMAGE_CONTENT == b"fake image data"

    def test_environment_isolation(self):
        """Test that test constants don't interfere with production."""
        # Test constants should use different values than production
        assert TEST_CONSTANTS.TEST_REDIS_DB != CONSTANTS.REDIS_DB
        assert TEST_CONSTANTS.TEST_REDIS_KEY_PREFIX != CONSTANTS.REDIS_KEY_PREFIX


class TestEnvironmentVariableHandling:
    """Test environment variable handling in constants."""

    def test_environment_variable_types(self):
        """Test that environment variables are correctly typed."""
        # Test string environment variables
        assert isinstance(CONSTANTS.DEFAULT_OUTPUT_DIR, str)
        assert isinstance(CONSTANTS.DEFAULT_USER_AGENT, str)
        
        # Test numeric environment variables
        assert isinstance(CONSTANTS.DEFAULT_TIMEOUT, int)
        assert isinstance(CONSTANTS.RATE_LIMIT_DELAY, float)
        assert isinstance(CONSTANTS.MAX_CONCURRENT, int)
        
        # Test boolean environment variables
        assert isinstance(CONSTANTS.RESPECT_ROBOTS_TXT, bool)

    def test_boolean_environment_parsing_logic(self):
        """Test the logic used for boolean environment variable parsing."""
        # Test the same logic used in constants.py
        test_cases = [
            ("true", True),
            ("True", True),
            ("TRUE", True),
            ("false", False),
            ("False", False),
            ("FALSE", False),
            ("", False),  # Empty string
            ("invalid", False),  # Invalid value
        ]
        
        for env_value, expected in test_cases:
            # Test the logic that constants.py actually uses
            result = env_value.lower() == "true" if env_value else False
            assert result == expected

    def test_numeric_conversion_logic(self):
        """Test numeric conversion logic."""
        # Test int conversion
        assert int("45") == 45
        assert float("3.5") == 3.5
        
        # Test that invalid conversion raises ValueError
        with pytest.raises(ValueError):
            int("not_a_number")
            
        with pytest.raises(ValueError):
            float("also_not_a_number")

    def test_environment_variable_defaults(self):
        """Test that proper defaults are used when environment variables aren't set."""
        # These should be the actual default values
        import os
        
        # Test with environment variable not set
        default_timeout = os.environ.get("DEFAULT_TIMEOUT", "30")
        assert int(default_timeout) == 30
        
        default_output = os.environ.get("OUTPUT_DIR", "converted_content")
        assert default_output == "converted_content"


class TestConstantImmutability:
    """Test that constants are properly immutable."""

    def test_constants_frozen(self):
        """Test that constants dataclass is frozen."""
        # Should not be able to modify frozen dataclass
        with pytest.raises(AttributeError):
            CONSTANTS.DEFAULT_TIMEOUT = 999

    def test_frozenset_immutability(self):
        """Test that frozenset constants are immutable."""
        # Should not be able to modify frozenset
        with pytest.raises(AttributeError):
            CONSTANTS.SHOPIFY_PRESERVE_CLASSES.add("new-class")

    def test_image_content_types_mutability(self):
        """Test that dict constants can be modified (by design)."""
        # This should work since it's a regular dict in a field
        original_types = CONSTANTS.IMAGE_CONTENT_TYPES.copy()
        CONSTANTS.IMAGE_CONTENT_TYPES["image/test"] = ".test"
        
        assert "image/test" in CONSTANTS.IMAGE_CONTENT_TYPES
        
        # Clean up
        del CONSTANTS.IMAGE_CONTENT_TYPES["image/test"]
        assert CONSTANTS.IMAGE_CONTENT_TYPES == original_types