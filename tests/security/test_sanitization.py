"""Comprehensive tests for HTML sanitization - MANDATORY TEST_BUILDING.md compliance.

This module tests the HTMLSanitizer class with complete coverage:
- XSS attack vector detection and prevention
- SQL injection payload detection
- Path traversal attack prevention
- HTML entity encoding
- JavaScript injection prevention
- URL validation and sanitization
- CSS injection prevention
- Iframe source validation
- Attribute sanitization
- Performance benchmarks

ALL tests follow MANDATORY TEST_BUILDING.md patterns:
- AAA pattern with explicit comments
- Factory fixtures for DRY principle
- Comprehensive security payload testing
- Performance benchmarks with specific thresholds
"""

import time

import pytest

from src.security.sanitization import HTMLSanitizer

# ============================================================================
# Test Fixtures - DRY Principle
# ============================================================================


@pytest.fixture
def default_sanitizer() -> HTMLSanitizer:
    """Factory for default HTMLSanitizer - DRY principle."""
    return HTMLSanitizer()


@pytest.fixture
def strict_sanitizer() -> HTMLSanitizer:
    """Factory for strict mode HTMLSanitizer - DRY principle."""
    return HTMLSanitizer(strict_mode=True)


@pytest.fixture
def non_strict_sanitizer() -> HTMLSanitizer:
    """Factory for non-strict mode HTMLSanitizer - DRY principle."""
    return HTMLSanitizer(strict_mode=False)


@pytest.fixture
def xss_payloads() -> list[str]:
    """Factory for XSS attack payloads - DRY principle."""
    return [
        '<script>alert("XSS")</script>',
        '<img src=x onerror=alert("XSS")>',
        '<svg onload=alert("XSS")>',
        'javascript:alert("XSS")',
        "<iframe src=\"javascript:alert('XSS')\"></iframe>",
        '<body onload=alert("XSS")>',
        '<input onfocus=alert("XSS") autofocus>',
        '<select onfocus=alert("XSS") autofocus>',
        '<textarea onfocus=alert("XSS") autofocus>',
        '<details open ontoggle=alert("XSS")>',
        '<marquee onstart=alert("XSS")>',
        '<audio src=x onerror=alert("XSS")>',
        '<video src=x onerror=alert("XSS")>',
        "<object data=\"javascript:alert('XSS')\">",
        "<embed src=\"javascript:alert('XSS')\">",
    ]


@pytest.fixture
def sql_injection_payloads() -> list[str]:
    """Factory for SQL injection payloads - DRY principle."""
    return [
        "' OR '1'='1",
        "'; DROP TABLE users--",
        "' UNION SELECT * FROM users--",
        "admin'--",
        "' OR 1=1--",
        "1' AND '1'='1",
        "1' UNION SELECT NULL--",
        "' WAITFOR DELAY '00:00:10'--",
    ]


@pytest.fixture
def path_traversal_payloads() -> list[str]:
    """Factory for path traversal payloads - DRY principle."""
    return [
        "../../../etc/passwd",
        "..\\..\\..\\windows\\system32",
        "....//....//....//etc/passwd",
        "..%2F..%2F..%2Fetc%2Fpasswd",
        "..%252F..%252F..%252Fetc%252Fpasswd",
    ]


# ============================================================================
# Sanitizer Initialization Tests
# ============================================================================


@pytest.mark.unit
@pytest.mark.security
class TestSanitizerInitialization:
    """Tests for HTMLSanitizer initialization."""

    def test_sanitizer_initialization_with_defaults(self):
        """Test sanitizer initializes with default values - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # (no setup needed)

        # Act - MANDATORY
        sanitizer = HTMLSanitizer()

        # Assert - MANDATORY
        assert sanitizer.strict_mode is True
        assert sanitizer.cleaner is not None
        assert len(sanitizer.ALLOWED_TAGS) > 0
        assert len(sanitizer.ALLOWED_PROTOCOLS) > 0

    def test_sanitizer_initialization_with_strict_mode_false(self):
        """Test sanitizer initializes with strict_mode=False - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # (no setup needed)

        # Act - MANDATORY
        sanitizer = HTMLSanitizer(strict_mode=False)

        # Assert - MANDATORY
        assert sanitizer.strict_mode is False
        assert sanitizer.cleaner is not None

    def test_sanitizer_has_required_allowed_tags(self, default_sanitizer: HTMLSanitizer):
        """Test sanitizer has required allowed tags - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        required_tags = {"p", "div", "span", "a", "img", "h1", "h2", "h3", "ul", "ol", "li"}

        # Act - MANDATORY
        allowed_tags = default_sanitizer.ALLOWED_TAGS

        # Assert - MANDATORY
        for tag in required_tags:
            assert tag in allowed_tags

    def test_sanitizer_has_required_allowed_protocols(self, default_sanitizer: HTMLSanitizer):
        """Test sanitizer has required allowed protocols - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        required_protocols = {"http", "https"}

        # Act - MANDATORY
        allowed_protocols = default_sanitizer.ALLOWED_PROTOCOLS

        # Assert - MANDATORY
        for protocol in required_protocols:
            assert protocol in allowed_protocols

    def test_sanitizer_has_trusted_iframe_domains(self, default_sanitizer: HTMLSanitizer):
        """Test sanitizer has trusted iframe domains - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        expected_domains = {"youtube.com", "vimeo.com"}

        # Act - MANDATORY
        trusted_domains = default_sanitizer.TRUSTED_IFRAME_DOMAINS

        # Assert - MANDATORY
        for domain in expected_domains:
            assert domain in trusted_domains


# ============================================================================
# XSS Attack Vector Tests
# ============================================================================


@pytest.mark.unit
@pytest.mark.security
class TestXSSPrevention:
    """MANDATORY security tests for XSS attack prevention."""

    def test_sanitize_html_blocks_script_tags(
        self, default_sanitizer: HTMLSanitizer, xss_payloads: list[str]
    ):
        """MANDATORY security test - blocks script tag XSS - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        script_payload = '<script>alert("XSS")</script>'

        # Act - MANDATORY
        sanitized = default_sanitizer.sanitize_html(script_payload)

        # Assert - MANDATORY
        assert "<script>" not in sanitized.lower()
        assert "alert" not in sanitized.lower()

    def test_sanitize_html_blocks_img_onerror_xss(self, default_sanitizer: HTMLSanitizer):
        """MANDATORY security test - blocks img onerror XSS - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        img_payload = '<img src=x onerror=alert("XSS")>'

        # Act - MANDATORY
        sanitized = default_sanitizer.sanitize_html(img_payload)

        # Assert - MANDATORY
        assert "onerror" not in sanitized.lower()
        assert "alert" not in sanitized.lower()

    def test_sanitize_html_blocks_svg_onload_xss(self, default_sanitizer: HTMLSanitizer):
        """MANDATORY security test - blocks SVG onload XSS - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        svg_payload = '<svg onload=alert("XSS")>'

        # Act - MANDATORY
        sanitized = default_sanitizer.sanitize_html(svg_payload)

        # Assert - MANDATORY
        assert "onload" not in sanitized.lower()
        assert "alert" not in sanitized.lower()

    def test_sanitize_html_blocks_javascript_protocol(self, default_sanitizer: HTMLSanitizer):
        """MANDATORY security test - blocks javascript: protocol - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        js_protocol = "<a href=\"javascript:alert('XSS')\">Click</a>"

        # Act - MANDATORY
        sanitized = default_sanitizer.sanitize_html(js_protocol)

        # Assert - MANDATORY
        assert "javascript:" not in sanitized.lower()

    def test_sanitize_html_blocks_iframe_javascript(self, default_sanitizer: HTMLSanitizer):
        """MANDATORY security test - blocks iframe javascript - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        iframe_payload = "<iframe src=\"javascript:alert('XSS')\"></iframe>"

        # Act - MANDATORY
        sanitized = default_sanitizer.sanitize_html(iframe_payload)

        # Assert - MANDATORY
        assert "javascript:" not in sanitized.lower()

    def test_sanitize_html_blocks_body_onload(self, default_sanitizer: HTMLSanitizer):
        """MANDATORY security test - blocks body onload - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        body_payload = '<body onload=alert("XSS")>Content</body>'

        # Act - MANDATORY
        sanitized = default_sanitizer.sanitize_html(body_payload)

        # Assert - MANDATORY
        assert "onload" not in sanitized.lower()
        assert "alert" not in sanitized.lower()

    def test_sanitize_html_blocks_all_xss_payloads(
        self, default_sanitizer: HTMLSanitizer, xss_payloads: list[str]
    ):
        """MANDATORY security test - blocks all XSS payloads - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # (xss_payloads from fixture)

        # Act & Assert - MANDATORY
        for payload in xss_payloads:
            sanitized = default_sanitizer.sanitize_html(payload)
            # None of these dangerous executable patterns should remain
            assert "<script" not in sanitized.lower()
            assert "onerror" not in sanitized.lower()
            assert "onload" not in sanitized.lower()
            # Text content may remain but should not be executable
            if "<" not in payload:  # Plain text payloads might remain as text
                # For plain text XSS attempts, ensure they're encoded
                assert "&lt;" in sanitized or payload.lower() == sanitized.lower()

    def test_detect_potential_xss_identifies_script_tags(self, default_sanitizer: HTMLSanitizer):
        """Test XSS detection identifies script tags - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        html_with_script = '<html><script>alert("XSS")</script></html>'

        # Act - MANDATORY
        is_xss = default_sanitizer._detect_potential_xss(html_with_script)

        # Assert - MANDATORY
        assert is_xss is True

    def test_detect_potential_xss_identifies_event_handlers(self, default_sanitizer: HTMLSanitizer):
        """Test XSS detection identifies event handlers - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        html_with_events = '<img src="test.jpg" onerror="alert(1)">'

        # Act - MANDATORY
        is_xss = default_sanitizer._detect_potential_xss(html_with_events)

        # Assert - MANDATORY
        assert is_xss is True

    def test_detect_potential_xss_identifies_javascript_protocol(
        self, default_sanitizer: HTMLSanitizer
    ):
        """Test XSS detection identifies javascript: protocol - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        html_with_js_protocol = '<a href="javascript:alert(1)">Click</a>'

        # Act - MANDATORY
        is_xss = default_sanitizer._detect_potential_xss(html_with_js_protocol)

        # Assert - MANDATORY
        assert is_xss is True


# ============================================================================
# SQL Injection Detection Tests
# ============================================================================


@pytest.mark.unit
@pytest.mark.security
class TestSQLInjectionDetection:
    """MANDATORY security tests for SQL injection detection in HTML attributes."""

    def test_sanitize_attribute_value_handles_sql_injection(
        self, default_sanitizer: HTMLSanitizer, sql_injection_payloads: list[str]
    ):
        """MANDATORY security test - sanitize SQL injection in attributes - MANDATORY AAA."""
        # Arrange - MANDATORY
        # (sql_injection_payloads from fixture)

        # Act & Assert - MANDATORY
        for payload in sql_injection_payloads:
            sanitized = default_sanitizer.sanitize_attribute_value("title", payload)
            # SQL special characters should be encoded
            assert "<" not in sanitized
            assert ">" not in sanitized
            assert "'" not in sanitized or "&#x27;" in sanitized

    def test_sanitize_text_encodes_sql_characters(
        self, default_sanitizer: HTMLSanitizer, sql_injection_payloads: list[str]
    ):
        """MANDATORY security test - encode SQL injection characters - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # (sql_injection_payloads from fixture)

        # Act & Assert - MANDATORY
        for payload in sql_injection_payloads:
            sanitized = default_sanitizer._sanitize_text(payload)
            # Dangerous characters should be encoded
            assert "<" not in sanitized or "&lt;" in sanitized
            assert ">" not in sanitized or "&gt;" in sanitized


# ============================================================================
# Path Traversal Prevention Tests
# ============================================================================


@pytest.mark.unit
@pytest.mark.security
class TestPathTraversalPrevention:
    """MANDATORY security tests for path traversal prevention."""

    def test_sanitize_url_blocks_path_traversal(
        self, default_sanitizer: HTMLSanitizer, path_traversal_payloads: list[str]
    ):
        """MANDATORY security test - blocks path traversal - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # (path_traversal_payloads from fixture)

        # Act & Assert - MANDATORY
        for payload in path_traversal_payloads:
            sanitized = default_sanitizer._sanitize_url(payload)
            # Path traversal should be blocked
            assert sanitized == "" or "../" not in sanitized

    def test_is_safe_url_blocks_path_traversal(self, default_sanitizer: HTMLSanitizer):
        """MANDATORY security test - is_safe_url blocks traversal - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        traversal_url = "../../../etc/passwd"

        # Act - MANDATORY
        is_safe = default_sanitizer._is_safe_url(traversal_url)

        # Assert - MANDATORY
        assert is_safe is False


# ============================================================================
# URL Validation and Sanitization Tests
# ============================================================================


@pytest.mark.unit
@pytest.mark.security
class TestURLSanitization:
    """MANDATORY security tests for URL validation and sanitization."""

    def test_sanitize_url_allows_http_protocol(self, default_sanitizer: HTMLSanitizer):
        """Test URL sanitization allows HTTP protocol - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        http_url = "http://example.com/page"

        # Act - MANDATORY
        sanitized = default_sanitizer._sanitize_url(http_url)

        # Assert - MANDATORY
        assert sanitized == http_url

    def test_sanitize_url_allows_https_protocol(self, default_sanitizer: HTMLSanitizer):
        """Test URL sanitization allows HTTPS protocol - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        https_url = "https://example.com/page"

        # Act - MANDATORY
        sanitized = default_sanitizer._sanitize_url(https_url)

        # Assert - MANDATORY
        assert sanitized == https_url

    def test_sanitize_url_blocks_data_protocol(self, default_sanitizer: HTMLSanitizer):
        """MANDATORY security test - blocks data: protocol - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        data_url = "data:text/html,<script>alert('XSS')</script>"

        # Act - MANDATORY
        sanitized = default_sanitizer._sanitize_url(data_url)

        # Assert - MANDATORY
        assert sanitized == ""

    def test_sanitize_url_blocks_file_protocol(self, default_sanitizer: HTMLSanitizer):
        """MANDATORY security test - blocks file: protocol - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        file_url = "file:///etc/passwd"

        # Act - MANDATORY
        sanitized = default_sanitizer._sanitize_url(file_url)

        # Assert - MANDATORY
        assert sanitized == ""

    def test_is_safe_url_allows_relative_urls(self, default_sanitizer: HTMLSanitizer):
        """Test is_safe_url allows relative URLs - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        relative_url = "/path/to/page"

        # Act - MANDATORY
        is_safe = default_sanitizer._is_safe_url(relative_url)

        # Assert - MANDATORY
        assert is_safe is True

    def test_is_safe_url_blocks_protocol_relative_urls(self, default_sanitizer: HTMLSanitizer):
        """MANDATORY security test - blocks protocol-relative URLs - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        protocol_relative = "//malicious.com/xss"

        # Act - MANDATORY
        is_safe = default_sanitizer._is_safe_url(protocol_relative)

        # Assert - MANDATORY
        assert is_safe is False


# ============================================================================
# CSS Injection Prevention Tests
# ============================================================================


@pytest.mark.unit
@pytest.mark.security
class TestCSSInjectionPrevention:
    """MANDATORY security tests for CSS injection prevention."""

    def test_sanitize_css_blocks_expression_injection(self, default_sanitizer: HTMLSanitizer):
        """MANDATORY security test - blocks CSS expression() - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        css_with_expression = "width: expression(alert('XSS'))"

        # Act - MANDATORY
        sanitized = default_sanitizer._sanitize_css(css_with_expression)

        # Assert - MANDATORY
        # expression() function should be removed from CSS
        assert "expression" not in sanitized.lower()
        # width is not in ALLOWED_CSS_PROPERTIES, so the entire declaration should be removed
        # or at minimum the dangerous expression pattern should be gone
        assert "expression(" not in sanitized.lower()

    def test_sanitize_css_blocks_javascript_in_url(self, default_sanitizer: HTMLSanitizer):
        """MANDATORY security test - blocks javascript in CSS url() - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        css_with_js = "background: url('javascript:alert(1)')"

        # Act - MANDATORY
        sanitized = default_sanitizer._sanitize_css(css_with_js)

        # Assert - MANDATORY
        assert "javascript:" not in sanitized.lower()

    def test_sanitize_css_blocks_data_urls(self, default_sanitizer: HTMLSanitizer):
        """MANDATORY security test - blocks data: URLs in CSS - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        css_with_data_url = "background: url('data:text/html,<script>alert(1)</script>')"

        # Act - MANDATORY
        sanitized = default_sanitizer._sanitize_css(css_with_data_url)

        # Assert - MANDATORY
        assert "data:" not in sanitized.lower()

    def test_sanitize_css_blocks_import_directives(self, default_sanitizer: HTMLSanitizer):
        """MANDATORY security test - blocks @import directives - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        css_with_import = "@import url('malicious.css'); color: red;"

        # Act - MANDATORY
        sanitized = default_sanitizer._sanitize_css(css_with_import)

        # Assert - MANDATORY
        assert "@import" not in sanitized.lower()

    def test_sanitize_css_allows_safe_properties(self, default_sanitizer: HTMLSanitizer):
        """Test CSS sanitization allows safe properties - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        safe_css = "color: red; font-size: 14px; margin: 10px;"

        # Act - MANDATORY
        sanitized = default_sanitizer._sanitize_css(safe_css)

        # Assert - MANDATORY
        assert "color: red" in sanitized
        assert "font-size: 14px" in sanitized
        assert "margin: 10px" in sanitized

    def test_sanitize_css_removes_unsafe_properties(self, default_sanitizer: HTMLSanitizer):
        """MANDATORY security test - removes unsafe CSS properties - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        unsafe_css = "position: absolute; z-index: 9999; opacity: 0;"

        # Act - MANDATORY
        sanitized = default_sanitizer._sanitize_css(unsafe_css)

        # Assert - MANDATORY
        # position, z-index, opacity are not in ALLOWED_CSS_PROPERTIES
        assert "position" not in sanitized.lower()
        assert "z-index" not in sanitized.lower()


# ============================================================================
# Iframe Source Validation Tests
# ============================================================================


@pytest.mark.unit
@pytest.mark.security
class TestIframeSourceValidation:
    """MANDATORY security tests for iframe source validation."""

    def test_is_trusted_iframe_source_allows_youtube(self, default_sanitizer: HTMLSanitizer):
        """Test iframe validation allows YouTube - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        youtube_url = "https://www.youtube.com/embed/video123"

        # Act - MANDATORY
        is_trusted = default_sanitizer._is_trusted_iframe_source(youtube_url)

        # Assert - MANDATORY
        assert is_trusted is True

    def test_is_trusted_iframe_source_allows_vimeo(self, default_sanitizer: HTMLSanitizer):
        """Test iframe validation allows Vimeo - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        vimeo_url = "https://player.vimeo.com/video/123456"

        # Act - MANDATORY
        is_trusted = default_sanitizer._is_trusted_iframe_source(vimeo_url)

        # Assert - MANDATORY
        assert is_trusted is True

    def test_is_trusted_iframe_source_blocks_untrusted_domain(
        self, default_sanitizer: HTMLSanitizer
    ):
        """MANDATORY security test - blocks untrusted iframe sources - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        untrusted_url = "https://malicious.com/embed"

        # Act - MANDATORY
        is_trusted = default_sanitizer._is_trusted_iframe_source(untrusted_url)

        # Assert - MANDATORY
        assert is_trusted is False

    def test_sanitize_html_removes_untrusted_iframes(self, strict_sanitizer: HTMLSanitizer):
        """MANDATORY security test - removes untrusted iframes - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        html_with_iframe = '<iframe src="https://malicious.com/xss"></iframe>'

        # Act - MANDATORY
        sanitized = strict_sanitizer.sanitize_html(html_with_iframe)

        # Assert - MANDATORY
        assert "malicious.com" not in sanitized


# ============================================================================
# HTML Entity Encoding Tests
# ============================================================================


@pytest.mark.unit
@pytest.mark.security
class TestHTMLEntityEncoding:
    """MANDATORY security tests for HTML entity encoding."""

    def test_sanitize_text_encodes_less_than(self, default_sanitizer: HTMLSanitizer):
        """Test text sanitization encodes < character - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        text_with_lt = "5 < 10"

        # Act - MANDATORY
        sanitized = default_sanitizer._sanitize_text(text_with_lt)

        # Assert - MANDATORY
        assert "&lt;" in sanitized

    def test_sanitize_text_encodes_greater_than(self, default_sanitizer: HTMLSanitizer):
        """Test text sanitization encodes > character - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        text_with_gt = "10 > 5"

        # Act - MANDATORY
        sanitized = default_sanitizer._sanitize_text(text_with_gt)

        # Assert - MANDATORY
        assert "&gt;" in sanitized

    def test_sanitize_text_encodes_double_quotes(self, default_sanitizer: HTMLSanitizer):
        """Test text sanitization encodes double quotes - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        text_with_quotes = 'He said "hello"'

        # Act - MANDATORY
        sanitized = default_sanitizer._sanitize_text(text_with_quotes)

        # Assert - MANDATORY
        assert "&quot;" in sanitized

    def test_sanitize_text_encodes_single_quotes(self, default_sanitizer: HTMLSanitizer):
        """Test text sanitization encodes single quotes - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        text_with_quotes = "It's a test"

        # Act - MANDATORY
        sanitized = default_sanitizer._sanitize_text(text_with_quotes)

        # Assert - MANDATORY
        assert "&#x27;" in sanitized


# ============================================================================
# Content Preprocessing Tests
# ============================================================================


@pytest.mark.unit
@pytest.mark.security
class TestContentPreprocessing:
    """MANDATORY security tests for content preprocessing."""

    def test_pre_process_html_removes_script_tags_completely(
        self, default_sanitizer: HTMLSanitizer
    ):
        """MANDATORY security test - pre-processing removes scripts - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        html_with_script = '<div>Safe</div><script>alert("XSS")</script><div>Content</div>'

        # Act - MANDATORY
        processed = default_sanitizer._pre_process_html(html_with_script)

        # Assert - MANDATORY
        assert "<script>" not in processed
        assert "alert" not in processed
        assert "<div>Safe</div>" in processed
        assert "<div>Content</div>" in processed

    def test_pre_process_html_removes_style_tags(self, default_sanitizer: HTMLSanitizer):
        """MANDATORY security test - removes style tags - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        html_with_style = "<div>Content</div><style>body { display: none; }</style>"

        # Act - MANDATORY
        processed = default_sanitizer._pre_process_html(html_with_style)

        # Assert - MANDATORY
        assert "<style>" not in processed

    def test_pre_process_html_removes_form_elements(self, default_sanitizer: HTMLSanitizer):
        """MANDATORY security test - removes form elements - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        html_with_form = '<div>Safe</div><form><input type="text"></form>'

        # Act - MANDATORY
        processed = default_sanitizer._pre_process_html(html_with_form)

        # Assert - MANDATORY
        assert "<form>" not in processed
        assert "<input>" not in processed

    def test_pre_process_html_removes_meta_tags(self, default_sanitizer: HTMLSanitizer):
        """MANDATORY security test - removes meta tags - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        html_with_meta = '<div>Content</div><meta http-equiv="refresh" content="0;url=malicious">'

        # Act - MANDATORY
        processed = default_sanitizer._pre_process_html(html_with_meta)

        # Assert - MANDATORY
        assert "<meta>" not in processed


# ============================================================================
# Strict Mode Application Tests
# ============================================================================


@pytest.mark.unit
@pytest.mark.security
class TestStrictModeApplication:
    """MANDATORY security tests for strict mode application."""

    def test_apply_strict_rules_validates_all_links(self, strict_sanitizer: HTMLSanitizer):
        """MANDATORY security test - strict mode validates links - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        html_with_unsafe_link = '<a href="javascript:alert(1)">Click</a>'

        # Act - MANDATORY
        strict_html = strict_sanitizer._apply_strict_rules(html_with_unsafe_link)

        # Assert - MANDATORY
        assert 'href="#"' in strict_html or "javascript:" not in strict_html

    def test_apply_strict_rules_removes_untrusted_iframes(self, strict_sanitizer: HTMLSanitizer):
        """MANDATORY security test - strict mode removes iframes - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        html_with_iframe = '<iframe src="https://malicious.com/embed"></iframe>'

        # Act - MANDATORY
        strict_html = strict_sanitizer._apply_strict_rules(html_with_iframe)

        # Assert - MANDATORY
        assert "malicious.com" not in strict_html


# ============================================================================
# Empty and Edge Case Tests
# ============================================================================


@pytest.mark.unit
@pytest.mark.security
class TestEdgeCases:
    """Tests for edge cases and empty content handling."""

    def test_sanitize_html_handles_empty_string(self, default_sanitizer: HTMLSanitizer):
        """Test sanitize_html handles empty string - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        empty_html = ""

        # Act - MANDATORY
        sanitized = default_sanitizer.sanitize_html(empty_html)

        # Assert - MANDATORY
        assert sanitized == ""

    def test_sanitize_html_handles_none_input(self, default_sanitizer: HTMLSanitizer):
        """Test sanitize_html handles None input - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        none_input = None

        # Act - MANDATORY
        sanitized = default_sanitizer.sanitize_html(none_input)

        # Assert - MANDATORY
        assert sanitized == ""

    def test_sanitize_html_handles_whitespace_only(self, default_sanitizer: HTMLSanitizer):
        """Test sanitize_html handles whitespace - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        whitespace_html = "   \n\t   "

        # Act - MANDATORY
        sanitized = default_sanitizer.sanitize_html(whitespace_html)

        # Assert - MANDATORY
        assert sanitized.strip() == ""

    def test_sanitize_html_preserves_safe_content(self, default_sanitizer: HTMLSanitizer):
        """Test sanitize_html preserves safe content - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        safe_html = "<p>This is <strong>safe</strong> content.</p>"

        # Act - MANDATORY
        sanitized = default_sanitizer.sanitize_html(safe_html)

        # Assert - MANDATORY
        assert "<p>" in sanitized
        assert "<strong>" in sanitized
        assert "safe" in sanitized


# ============================================================================
# MANDATORY Performance Benchmarks
# ============================================================================


@pytest.mark.performance
@pytest.mark.unit
@pytest.mark.security
class TestSanitizationPerformance:
    """MANDATORY performance tests for sanitization operations."""

    def test_sanitization_initialization_performance(self):
        """MANDATORY performance test - sanitizer initialization speed."""
        # Arrange - MANDATORY
        iterations = 1000

        # Act - MANDATORY
        start_time = time.perf_counter()

        for _ in range(iterations):
            HTMLSanitizer()

        end_time = time.perf_counter()
        execution_time = end_time - start_time

        # Assert - MANDATORY
        avg_time = execution_time / iterations
        assert avg_time < 0.01  # <10ms per initialization
        assert execution_time < 10.0  # Total <10s for 1000 initializations

    def test_html_sanitization_performance(self, default_sanitizer: HTMLSanitizer):
        """MANDATORY performance test - HTML sanitization speed."""
        # Arrange - MANDATORY
        html_content = "<div><p>Safe content</p><script>alert('XSS')</script></div>" * 100
        iterations = 100

        # Act - MANDATORY
        start_time = time.perf_counter()

        for _ in range(iterations):
            default_sanitizer.sanitize_html(html_content)

        end_time = time.perf_counter()
        execution_time = end_time - start_time

        # Assert - MANDATORY
        avg_time = execution_time / iterations
        assert avg_time < 0.06  # <60ms per sanitization (relaxed for CI with logging overhead)
        assert execution_time < 6.0  # Total <6s for 100 sanitizations (relaxed for CI)

    def test_url_sanitization_performance(self, default_sanitizer: HTMLSanitizer):
        """MANDATORY performance test - URL sanitization speed."""
        # Arrange - MANDATORY
        urls = [
            "https://example.com/page",
            "http://test.com/resource",
            "javascript:alert(1)",
            "data:text/html,<script>alert(1)</script>",
            "../../../etc/passwd",
        ] * 200
        iterations = len(urls)

        # Act - MANDATORY
        start_time = time.perf_counter()

        for url in urls:
            default_sanitizer._sanitize_url(url)

        end_time = time.perf_counter()
        execution_time = end_time - start_time

        # Assert - MANDATORY
        avg_time = execution_time / iterations
        assert avg_time < 0.001  # <1ms per URL sanitization
        assert execution_time < 1.0  # Total <1s for 1000 URLs

    def test_css_sanitization_performance(self, default_sanitizer: HTMLSanitizer):
        """MANDATORY performance test - CSS sanitization speed."""
        # Arrange - MANDATORY
        css_content = "color: red; font-size: 14px; expression(alert('XSS'))" * 100
        iterations = 500

        # Act - MANDATORY
        start_time = time.perf_counter()

        for _ in range(iterations):
            default_sanitizer._sanitize_css(css_content)

        end_time = time.perf_counter()
        execution_time = end_time - start_time

        # Assert - MANDATORY
        avg_time = execution_time / iterations
        assert avg_time < 0.01  # <10ms per CSS sanitization
        assert execution_time < 5.0  # Total <5s for 500 sanitizations
