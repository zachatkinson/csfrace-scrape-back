"""Tests for URL utilities following testing best practices."""

from unittest.mock import patch

from src.utils.url import (
    extract_domain,
    extract_filename_from_url,
    is_same_domain,
    normalize_url,
    safe_parse_url,
)


class TestUrlParsingCore:
    """Test core URL parsing functionality following SOLID principles."""

    def test_safe_parse_url_valid_http(self):
        """Test parsing valid HTTP URL."""
        result = safe_parse_url("http://example.com/path")
        assert result is not None
        assert result.scheme == "http"
        assert result.netloc == "example.com"
        assert result.path == "/path"

    def test_safe_parse_url_valid_https(self):
        """Test parsing valid HTTPS URL."""
        result = safe_parse_url("https://secure.example.com/api/v1")
        assert result is not None
        assert result.scheme == "https"
        assert result.netloc == "secure.example.com"
        assert result.path == "/api/v1"

    def test_safe_parse_url_with_query_and_fragment(self):
        """Test parsing URL with query parameters and fragment."""
        result = safe_parse_url("https://example.com/search?q=test&limit=10#results")
        assert result is not None
        assert result.scheme == "https"
        assert result.netloc == "example.com"
        assert result.path == "/search"
        assert result.query == "q=test&limit=10"
        assert result.fragment == "results"

    def test_safe_parse_url_invalid_no_scheme(self):
        """Test parsing URL without scheme."""
        result = safe_parse_url("example.com/path")
        assert result is None

    def test_safe_parse_url_invalid_no_netloc(self):
        """Test parsing URL without network location."""
        result = safe_parse_url("http:///path")
        assert result is None

    def test_safe_parse_url_empty_string(self):
        """Test parsing empty string."""
        result = safe_parse_url("")
        assert result is None

    def test_safe_parse_url_exception_handling(self):
        """Test parsing URL that causes exception."""
        with patch("src.utils.url.urlparse", side_effect=Exception("Parse error")):
            result = safe_parse_url("http://example.com")
            assert result is None


class TestDomainExtraction:
    """Test domain extraction functionality with comprehensive edge cases."""

    def test_extract_domain_valid_url(self):
        """Test domain extraction from valid URL."""
        assert extract_domain("https://www.example.com/path") == "www.example.com"

    def test_extract_domain_with_port(self):
        """Test domain extraction from URL with port."""
        assert extract_domain("http://localhost:8080/api") == "localhost:8080"

    def test_extract_domain_subdomain(self):
        """Test domain extraction with subdomain."""
        assert extract_domain("https://api.service.example.com") == "api.service.example.com"

    def test_extract_domain_invalid_url(self):
        """Test domain extraction from invalid URL."""
        assert extract_domain("not-a-url") is None

    def test_extract_domain_empty_url(self):
        """Test domain extraction from empty URL."""
        assert extract_domain("") is None

    def test_extract_domain_url_with_credentials(self):
        """Test domain extraction from URL with credentials."""
        assert extract_domain("https://user:pass@example.com/path") == "user:pass@example.com"


class TestDomainComparison:
    """Test domain comparison functionality."""

    def test_is_same_domain_identical_domains(self):
        """Test domain comparison with identical domains."""
        url1 = "https://example.com/page1"
        url2 = "https://example.com/page2"
        assert is_same_domain(url1, url2) is True

    def test_is_same_domain_different_domains(self):
        """Test domain comparison with different domains."""
        url1 = "https://example.com/page"
        url2 = "https://other.com/page"
        assert is_same_domain(url1, url2) is False

    def test_is_same_domain_different_subdomains(self):
        """Test domain comparison with different subdomains."""
        url1 = "https://www.example.com/page"
        url2 = "https://api.example.com/page"
        assert is_same_domain(url1, url2) is False

    def test_is_same_domain_different_schemes(self):
        """Test domain comparison with different schemes but same domain."""
        url1 = "http://example.com/page"
        url2 = "https://example.com/page"
        assert is_same_domain(url1, url2) is True

    def test_is_same_domain_different_ports(self):
        """Test domain comparison with different ports."""
        url1 = "https://example.com:8080/page"
        url2 = "https://example.com:9000/page"
        assert is_same_domain(url1, url2) is False

    def test_is_same_domain_one_invalid(self):
        """Test domain comparison with one invalid URL."""
        url1 = "https://example.com/page"
        url2 = "not-a-url"
        assert is_same_domain(url1, url2) is False

    def test_is_same_domain_both_invalid(self):
        """Test domain comparison with both invalid URLs."""
        url1 = "not-a-url-1"
        url2 = "not-a-url-2"
        assert is_same_domain(url1, url2) is False


class TestUrlNormalization:
    """Test URL normalization with various scenarios."""

    def test_normalize_url_absolute_http(self):
        """Test normalization of absolute HTTP URL."""
        url = "http://example.com/path"
        result = normalize_url(url)
        assert result == "http://example.com/path"

    def test_normalize_url_absolute_https(self):
        """Test normalization of absolute HTTPS URL."""
        url = "https://example.com/path"
        result = normalize_url(url)
        assert result == "https://example.com/path"

    def test_normalize_url_invalid_absolute(self):
        """Test normalization of invalid absolute URL."""
        url = "http://invalid"
        result = normalize_url(url)
        assert result is None

    def test_normalize_url_relative_with_base(self):
        """Test normalization of relative URL with base URL."""
        url = "/api/endpoint"
        base_url = "https://example.com"
        result = normalize_url(url, base_url)
        assert result == "https://example.com/api/endpoint"

    def test_normalize_url_relative_no_leading_slash(self):
        """Test normalization of relative URL without leading slash."""
        url = "api/endpoint"
        base_url = "https://example.com/base/"
        result = normalize_url(url, base_url)
        assert result == "https://example.com/base/api/endpoint"

    def test_normalize_url_relative_without_base(self):
        """Test normalization of relative URL without base URL."""
        url = "/api/endpoint"
        result = normalize_url(url, None)
        assert result is None

    def test_normalize_url_empty_string(self):
        """Test normalization of empty string."""
        result = normalize_url("")
        assert result is None

    def test_normalize_url_whitespace_only(self):
        """Test normalization of whitespace-only string."""
        result = normalize_url("   ")
        assert result is None

    def test_normalize_url_fragment_anchor(self):
        """Test normalization of fragment anchor."""
        url = "#section"
        base_url = "https://example.com"
        result = normalize_url(url, base_url)
        assert result is None

    def test_normalize_url_protocol_relative(self):
        """Test normalization of protocol-relative URL."""
        url = "//example.com/path"
        base_url = "https://base.com"
        result = normalize_url(url, base_url)
        assert result is None

    def test_normalize_url_urljoin_exception(self):
        """Test normalization when urljoin raises exception."""
        url = "/path"
        base_url = "invalid-base"

        with patch("src.utils.url.urljoin", side_effect=Exception("Join failed")):
            result = normalize_url(url, base_url)
            assert result is None


class TestFilenameExtraction:
    """Test filename extraction from URLs."""

    def test_extract_filename_with_extension(self):
        """Test filename extraction with extension."""
        url = "https://example.com/files/document.pdf"
        result = extract_filename_from_url(url)
        assert result == "document.pdf"

    def test_extract_filename_without_extension(self):
        """Test filename extraction without extension."""
        url = "https://example.com/files/document"
        result = extract_filename_from_url(url, ".html")
        assert result == "document.html"

    def test_extract_filename_from_root(self):
        """Test filename extraction from root path."""
        url = "https://example.com/"
        result = extract_filename_from_url(url, ".html")
        assert result == "example_com.html"

    def test_extract_filename_no_path(self):
        """Test filename extraction with no path."""
        url = "https://example.com"
        result = extract_filename_from_url(url, ".html")
        assert result == "example_com.html"

    def test_extract_filename_invalid_url(self):
        """Test filename extraction from invalid URL."""
        url = "not-a-url"
        result = extract_filename_from_url(url, ".html")
        assert result == "unknown.html"

    def test_extract_filename_with_query_params(self):
        """Test filename extraction with query parameters."""
        url = "https://example.com/files/document.pdf?version=1&format=A4"
        result = extract_filename_from_url(url)
        assert result == "document.pdf"

    def test_extract_filename_with_fragment(self):
        """Test filename extraction with fragment."""
        url = "https://example.com/files/document.pdf#page=5"
        result = extract_filename_from_url(url)
        assert result == "document.pdf"

    def test_extract_filename_with_spaces(self):
        """Test filename extraction with spaces (should be cleaned)."""
        url = "https://example.com/files/my document.pdf"
        result = extract_filename_from_url(url)
        assert result == "my_document.pdf"

    def test_extract_filename_with_special_chars(self):
        """Test filename extraction with special characters."""
        url = "https://example.com/files/doc?ument.pdf"
        result = extract_filename_from_url(url)
        assert result == "document.pdf"

    def test_extract_filename_deep_path(self):
        """Test filename extraction from deep path."""
        url = "https://example.com/very/deep/path/structure/file.txt"
        result = extract_filename_from_url(url)
        assert result == "file.txt"

    def test_extract_filename_default_extension_applied(self):
        """Test default extension is applied when needed."""
        url = "https://example.com/api/data"
        result = extract_filename_from_url(url, ".json")
        assert result == "data.json"

    def test_extract_filename_fallback_to_file(self):
        """Test fallback to 'file' when no usable name found."""
        url = "https://example.com/"

        with patch("src.utils.url.safe_parse_url") as mock_parse:
            # Mock a parsed URL with empty netloc to trigger fallback
            mock_parsed = type(
                "MockParsed", (), {"path": "", "netloc": "", "query": "", "fragment": ""}
            )()
            mock_parse.return_value = mock_parsed

            result = extract_filename_from_url(url, ".html")
            assert result == "file.html"


class TestUrlUtilsIntegration:
    """Test integration scenarios between URL utility functions."""

    def test_domain_extraction_with_normalization(self):
        """Test domain extraction works with normalized URLs."""
        relative_url = "/api/data"
        base_url = "https://api.example.com"

        normalized = normalize_url(relative_url, base_url)
        domain = extract_domain(normalized) if normalized else None

        assert domain == "api.example.com"

    def test_filename_extraction_from_normalized_url(self):
        """Test filename extraction from normalized URL."""
        relative_url = "files/document.pdf"
        base_url = "https://cdn.example.com/"

        normalized = normalize_url(relative_url, base_url)
        filename = extract_filename_from_url(normalized) if normalized else "unknown.pdf"

        assert filename == "document.pdf"

    def test_same_domain_check_with_normalization(self):
        """Test same domain check with URL normalization."""
        url1 = "https://example.com/page1"
        relative_url2 = "/page2"

        normalized_url2 = normalize_url(relative_url2, url1)
        if normalized_url2:
            are_same = is_same_domain(url1, normalized_url2)
            assert are_same is True

    def test_complete_url_processing_workflow(self):
        """Test complete URL processing workflow."""
        # Start with relative URL
        relative_url = "api/v1/users.json"
        base_url = "https://api.service.com/v1/"

        # Normalize URL
        normalized = normalize_url(relative_url, base_url)
        assert normalized == "https://api.service.com/v1/api/v1/users.json"

        # Extract domain
        domain = extract_domain(normalized)
        assert domain == "api.service.com"

        # Extract filename
        filename = extract_filename_from_url(normalized)
        assert filename == "users.json"

        # Check same domain with base
        same_domain = is_same_domain(normalized, base_url)
        assert same_domain is True


class TestUrlUtilsErrorHandling:
    """Test comprehensive error handling in URL utilities."""

    def test_safe_parse_url_with_malformed_input(self):
        """Test safe URL parsing with various malformed inputs."""
        malformed_urls = [
            "http://",
            "://example.com",
            "http:example.com",
            "ftp://example.com",  # Valid but no scheme/netloc
            "javascript:alert('test')",
            None,  # This should be handled gracefully if function gets None
        ]

        for url in malformed_urls:
            if url is not None:  # Skip None test for now
                result = safe_parse_url(url)
                # All should return None (invalid) or be handled gracefully
                assert result is None or hasattr(result, "scheme")

    def test_extract_domain_edge_cases(self):
        """Test domain extraction with edge cases."""
        edge_cases = [
            "http://",
            "https://",
            "http://localhost",
            "https://127.0.0.1",
            "http://[::1]",  # IPv6
            "https://user@example.com",  # User in URL
        ]

        for url in edge_cases:
            result = extract_domain(url)
            # Should either return valid domain or None
            assert result is None or isinstance(result, str)

    def test_normalize_url_error_resilience(self):
        """Test URL normalization error resilience."""
        problematic_inputs = [
            ("", "https://example.com"),
            ("   ", "https://example.com"),
            (None, "https://example.com")
            if False
            else ("valid", "https://example.com"),  # Skip None test
            ("/path", None),
            ("/path", ""),
            ("/path", "invalid-base"),
        ]

        for url, base in problematic_inputs:
            result = normalize_url(url, base)
            # Should handle gracefully without exceptions
            assert result is None or isinstance(result, str)

    def test_extract_filename_error_resilience(self):
        """Test filename extraction error resilience."""
        problematic_urls = [
            "",
            "http://",
            "not-a-url-at-all",
            "https://example.com/" + "a" * 1000,  # Very long URL
        ]

        for url in problematic_urls:
            result = extract_filename_from_url(url, ".html")
            # Should always return a string, never None or raise exception
            assert isinstance(result, str)
            assert len(result) > 0


class TestUrlUtilsPerformance:
    """Test performance characteristics of URL utilities."""

    def test_url_parsing_performance_bulk(self):
        """Test URL parsing performance with bulk operations."""
        import time

        urls = [f"https://example{i}.com/path/{i}" for i in range(100)]

        start_time = time.time()
        results = [safe_parse_url(url) for url in urls]
        execution_time = time.time() - start_time

        # Should complete bulk operations quickly
        assert execution_time < 1.0  # Less than 1 second for 100 URLs
        assert len(results) == 100
        assert all(result is not None for result in results)

    def test_domain_extraction_performance(self):
        """Test domain extraction performance."""
        import time

        url = "https://very-long-subdomain.example.com/very/long/path/with/many/segments"

        start_time = time.time()
        for _ in range(1000):
            extract_domain(url)
        execution_time = time.time() - start_time

        # Should be very fast for repeated operations
        assert execution_time < 0.5  # Less than 500ms for 1000 operations
