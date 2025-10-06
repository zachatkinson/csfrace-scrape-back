"""Comprehensive tests for URL processing utilities - MANDATORY TEST_BUILDING.md compliance.

This module tests URL processing utilities with complete coverage:
- Domain extraction and validation
- URL normalization (relative/absolute)
- Same-domain comparison
- Filename extraction from URLs
- Edge cases and error handling
- Performance benchmarks

ALL tests follow MANDATORY TEST_BUILDING.md patterns:
- AAA pattern with explicit comments
- Factory fixtures for DRY principle
- Comprehensive URL scenario testing
- Performance benchmarks with specific thresholds
"""

import time

import pytest

from src.utils.url import extract_domain, extract_filename_from_url, is_same_domain, normalize_url

# ============================================================================
# Test Fixtures - DRY Principle
# ============================================================================


@pytest.fixture
def valid_urls() -> list[str]:
    """Factory for valid URL samples - DRY principle."""
    return [
        "https://example.com",
        "http://www.example.com/path",
        "https://subdomain.example.com:8080/api",
        "https://example.com/path?query=value",
        "https://example.com/path#fragment",
    ]


@pytest.fixture
def invalid_urls() -> list[str]:
    """Factory for invalid URL samples - DRY principle."""
    return [
        "",
        "   ",
        "not-a-url",
        "://example.com",
        "http://",
        "https://",
        "//example.com",  # Protocol-relative URLs not allowed
    ]


# ============================================================================
# extract_domain Tests
# ============================================================================


@pytest.mark.unit
class TestExtractDomain:
    """Tests for extract_domain function."""

    def test_extract_domain_basic_url(self) -> None:
        """Test extract_domain with basic URL - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        url = "https://example.com"

        # Act - MANDATORY
        result = extract_domain(url)

        # Assert - MANDATORY
        assert result == "example.com"

    def test_extract_domain_with_path(self) -> None:
        """Test extract_domain with path - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        url = "https://example.com/path/to/resource"

        # Act - MANDATORY
        result = extract_domain(url)

        # Assert - MANDATORY
        assert result == "example.com"

    def test_extract_domain_with_subdomain(self) -> None:
        """Test extract_domain preserves subdomain - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        url = "https://api.example.com/v1/users"

        # Act - MANDATORY
        result = extract_domain(url)

        # Assert - MANDATORY
        assert result == "api.example.com"

    def test_extract_domain_with_port(self) -> None:
        """Test extract_domain with port number - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        url = "https://example.com:8080/api"

        # Act - MANDATORY
        result = extract_domain(url)

        # Assert - MANDATORY
        assert result == "example.com:8080"

    def test_extract_domain_with_query(self) -> None:
        """Test extract_domain ignores query - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        url = "https://example.com/path?param=value"

        # Act - MANDATORY
        result = extract_domain(url)

        # Assert - MANDATORY
        assert result == "example.com"

    def test_extract_domain_with_fragment(self) -> None:
        """Test extract_domain ignores fragment - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        url = "https://example.com/path#section"

        # Act - MANDATORY
        result = extract_domain(url)

        # Assert - MANDATORY
        assert result == "example.com"

    def test_extract_domain_invalid_url(self) -> None:
        """Test extract_domain with invalid URL - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        url = "not-a-valid-url"

        # Act - MANDATORY
        result = extract_domain(url)

        # Assert - MANDATORY
        assert result is None

    def test_extract_domain_empty_string(self) -> None:
        """Test extract_domain with empty string - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        url = ""

        # Act - MANDATORY
        result = extract_domain(url)

        # Assert - MANDATORY
        assert result is None


# ============================================================================
# is_same_domain Tests
# ============================================================================


@pytest.mark.unit
class TestIsSameDomain:
    """Tests for is_same_domain function."""

    def test_is_same_domain_exact_match(self) -> None:
        """Test is_same_domain with exact domain match - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        url1 = "https://example.com/page1"
        url2 = "https://example.com/page2"

        # Act - MANDATORY
        result = is_same_domain(url1, url2)

        # Assert - MANDATORY
        assert result is True

    def test_is_same_domain_different_schemes(self) -> None:
        """Test is_same_domain with different schemes - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        url1 = "http://example.com/page1"
        url2 = "https://example.com/page2"

        # Act - MANDATORY
        result = is_same_domain(url1, url2)

        # Assert - MANDATORY
        assert result is True  # Domain is the same, scheme doesn't matter

    def test_is_same_domain_different_domains(self) -> None:
        """Test is_same_domain with different domains - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        url1 = "https://example.com/page"
        url2 = "https://another.com/page"

        # Act - MANDATORY
        result = is_same_domain(url1, url2)

        # Assert - MANDATORY
        assert result is False

    def test_is_same_domain_subdomain_difference(self) -> None:
        """Test is_same_domain with subdomain difference - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        url1 = "https://www.example.com/page"
        url2 = "https://api.example.com/page"

        # Act - MANDATORY
        result = is_same_domain(url1, url2)

        # Assert - MANDATORY
        assert result is False  # Different subdomains

    def test_is_same_domain_with_ports(self) -> None:
        """Test is_same_domain with port numbers - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        url1 = "https://example.com:8080/page"
        url2 = "https://example.com:8080/other"

        # Act - MANDATORY
        result = is_same_domain(url1, url2)

        # Assert - MANDATORY
        assert result is True

    def test_is_same_domain_different_ports(self) -> None:
        """Test is_same_domain with different ports - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        url1 = "https://example.com:8080/page"
        url2 = "https://example.com:9090/page"

        # Act - MANDATORY
        result = is_same_domain(url1, url2)

        # Assert - MANDATORY
        assert result is False  # Different ports

    def test_is_same_domain_invalid_url(self) -> None:
        """Test is_same_domain with invalid URL - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        url1 = "https://example.com/page"
        url2 = "not-a-valid-url"

        # Act - MANDATORY
        result = is_same_domain(url1, url2)

        # Assert - MANDATORY
        assert result is False


# ============================================================================
# normalize_url Tests
# ============================================================================


@pytest.mark.unit
class TestNormalizeUrl:
    """Tests for normalize_url function."""

    def test_normalize_url_absolute_https(self) -> None:
        """Test normalize_url with absolute HTTPS URL - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        url = "https://example.com/path"

        # Act - MANDATORY
        result = normalize_url(url)

        # Assert - MANDATORY
        assert result == "https://example.com/path"

    def test_normalize_url_absolute_http(self) -> None:
        """Test normalize_url with absolute HTTP URL - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        url = "http://example.com/path"

        # Act - MANDATORY
        result = normalize_url(url)

        # Assert - MANDATORY
        assert result == "http://example.com/path"

    def test_normalize_url_strips_whitespace(self) -> None:
        """Test normalize_url strips whitespace - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        url = "  https://example.com/path  "

        # Act - MANDATORY
        result = normalize_url(url)

        # Assert - MANDATORY
        assert result == "https://example.com/path"

    def test_normalize_url_relative_with_base(self) -> None:
        """Test normalize_url with relative URL and base - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        url = "/path/to/resource"
        base_url = "https://example.com"

        # Act - MANDATORY
        result = normalize_url(url, base_url)

        # Assert - MANDATORY
        assert result == "https://example.com/path/to/resource"

    def test_normalize_url_relative_path_with_base(self) -> None:
        """Test normalize_url with relative path - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        url = "relative/path"
        base_url = "https://example.com/base/"

        # Act - MANDATORY
        result = normalize_url(url, base_url)

        # Assert - MANDATORY
        assert result == "https://example.com/base/relative/path"

    def test_normalize_url_rejects_protocol_relative(self) -> None:
        """Test normalize_url rejects protocol-relative URLs - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        url = "//example.com/path"

        # Act - MANDATORY
        result = normalize_url(url)

        # Assert - MANDATORY
        assert result is None  # Protocol-relative URLs not allowed

    def test_normalize_url_empty_string(self) -> None:
        """Test normalize_url with empty string - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        url = ""

        # Act - MANDATORY
        result = normalize_url(url)

        # Assert - MANDATORY
        assert result is None

    def test_normalize_url_whitespace_only(self) -> None:
        """Test normalize_url with whitespace only - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        url = "   "

        # Act - MANDATORY
        result = normalize_url(url)

        # Assert - MANDATORY
        assert result is None

    def test_normalize_url_invalid_domain(self) -> None:
        """Test normalize_url with invalid domain - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        url = "https://invalid-domain"

        # Act - MANDATORY
        result = normalize_url(url)

        # Assert - MANDATORY
        assert result is None  # Domain without dot is invalid

    def test_normalize_url_localhost_allowed(self) -> None:
        """Test normalize_url allows localhost - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        url = "http://localhost:8000/path"

        # Act - MANDATORY
        result = normalize_url(url)

        # Assert - MANDATORY
        assert result == "http://localhost:8000/path"

    def test_normalize_url_ip_address_allowed(self) -> None:
        """Test normalize_url allows IP addresses - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        url = "http://127.0.0.1:8000/path"

        # Act - MANDATORY
        result = normalize_url(url)

        # Assert - MANDATORY
        assert result == "http://127.0.0.1:8000/path"


# ============================================================================
# extract_filename_from_url Tests
# ============================================================================


@pytest.mark.unit
class TestExtractFilenameFromUrl:
    """Tests for extract_filename_from_url function."""

    def test_extract_filename_basic(self) -> None:
        """Test extract_filename_from_url with basic filename - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        url = "https://example.com/path/to/file.txt"

        # Act - MANDATORY
        result = extract_filename_from_url(url)

        # Assert - MANDATORY
        assert result == "file.txt"

    def test_extract_filename_with_query(self) -> None:
        """Test extract_filename_from_url handles query - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        url = "https://example.com/file.pdf?download=true"

        # Act - MANDATORY
        result = extract_filename_from_url(url)

        # Assert - MANDATORY
        # Query params removed by cleaning
        assert "file.pdf" in result

    def test_extract_filename_no_extension(self) -> None:
        """Test extract_filename_from_url with no extension - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        url = "https://example.com/path/to/file"
        default_ext = ".html"

        # Act - MANDATORY
        result = extract_filename_from_url(url, default_ext)

        # Assert - MANDATORY
        assert result == "file.html"

    def test_extract_filename_root_url(self) -> None:
        """Test extract_filename_from_url with root URL - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        url = "https://example.com/"
        default_ext = ".html"

        # Act - MANDATORY
        result = extract_filename_from_url(url, default_ext)

        # Assert - MANDATORY
        assert ".html" in result
        assert "example_com" in result or "file" in result

    def test_extract_filename_invalid_url(self) -> None:
        """Test extract_filename_from_url with invalid URL - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        url = "not-a-valid-url"
        default_ext = ".txt"

        # Act - MANDATORY
        result = extract_filename_from_url(url, default_ext)

        # Assert - MANDATORY
        assert result == "unknown.txt"

    def test_extract_filename_spaces_replaced(self) -> None:
        """Test extract_filename_from_url replaces spaces - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        url = "https://example.com/file with spaces.pdf"

        # Act - MANDATORY
        result = extract_filename_from_url(url)

        # Assert - MANDATORY
        assert " " not in result
        assert "_" in result

    def test_extract_filename_special_chars_removed(self) -> None:
        """Test extract_filename_from_url removes special chars - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        url = "https://example.com/file?query#fragment"

        # Act - MANDATORY
        result = extract_filename_from_url(url)

        # Assert - MANDATORY
        assert "?" not in result
        assert "#" not in result


# ============================================================================
# MANDATORY Performance Benchmarks
# ============================================================================


@pytest.mark.performance
@pytest.mark.unit
class TestUrlUtilsPerformance:
    """MANDATORY performance tests for URL utilities."""

    def test_normalize_url_performance(self) -> None:
        """MANDATORY performance test - URL normalization speed."""
        # Arrange - MANDATORY
        test_urls = [
            ("https://example.com/path", None),
            ("/relative/path", "https://example.com"),
            ("relative/file", "https://example.com/base/"),
        ]
        iterations = 5000

        # Act - MANDATORY
        start_time = time.perf_counter()

        for _ in range(iterations):
            for url, base in test_urls:
                normalize_url(url, base)

        end_time = time.perf_counter()
        execution_time = end_time - start_time

        # Assert - MANDATORY
        total_operations = iterations * len(test_urls)
        avg_time = execution_time / total_operations
        assert avg_time < 0.0001  # <0.1ms per normalization
        assert execution_time < 1.5  # Total <1.5s for 15000 normalizations

    def test_extract_domain_performance(self) -> None:
        """MANDATORY performance test - domain extraction speed."""
        # Arrange - MANDATORY
        test_url = "https://subdomain.example.com:8080/path/to/resource?query=value"
        iterations = 10000

        # Act - MANDATORY
        start_time = time.perf_counter()

        for _ in range(iterations):
            extract_domain(test_url)

        end_time = time.perf_counter()
        execution_time = end_time - start_time

        # Assert - MANDATORY
        avg_time = execution_time / iterations
        assert avg_time < 0.0001  # <0.1ms per extraction
        assert execution_time < 1.0  # Total <1s for 10000 extractions

    def test_extract_filename_performance(self) -> None:
        """MANDATORY performance test - filename extraction speed."""
        # Arrange - MANDATORY
        test_url = "https://example.com/path/to/file.txt?download=true"
        iterations = 10000

        # Act - MANDATORY
        start_time = time.perf_counter()

        for _ in range(iterations):
            extract_filename_from_url(test_url)

        end_time = time.perf_counter()
        execution_time = end_time - start_time

        # Assert - MANDATORY
        avg_time = execution_time / iterations
        assert avg_time < 0.0001  # <0.1ms per extraction
        assert execution_time < 1.0  # Total <1s for 10000 extractions
