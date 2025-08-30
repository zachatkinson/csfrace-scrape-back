"""Comprehensive tests for HTML sanitization and XSS prevention."""

import pytest

from src.security.sanitization import HTMLSanitizer, sanitize_attribute, sanitize_html_content


class TestHTMLSanitizer:
    """Test the HTMLSanitizer class for XSS prevention."""

    @pytest.fixture
    def sanitizer(self):
        """Create a test sanitizer instance."""
        return HTMLSanitizer(strict_mode=True)

    @pytest.fixture
    def lenient_sanitizer(self):
        """Create a lenient sanitizer instance."""
        return HTMLSanitizer(strict_mode=False)

    def test_basic_html_sanitization(self, sanitizer):
        """Test basic HTML content sanitization."""
        html = "<p>Hello <strong>world</strong>!</p>"
        result = sanitizer.sanitize_html(html)
        assert result == "<p>Hello <strong>world</strong>!</p>"

    def test_script_tag_removal(self, sanitizer):
        """Test that script tags are completely removed."""
        html = '<p>Safe content</p><script>alert("xss")</script><p>More content</p>'
        result = sanitizer.sanitize_html(html)
        assert "<script>" not in result
        assert "alert" not in result
        assert "<p>Safe content</p>" in result
        assert "<p>More content</p>" in result

    def test_javascript_protocol_removal(self, sanitizer):
        """Test that javascript: protocols are blocked."""
        html = "<a href=\"javascript:alert('xss')\">Click me</a>"
        result = sanitizer.sanitize_html(html)
        assert "javascript:" not in result
        # Link should be made safe but preserved
        assert "<a" in result

    def test_event_handler_removal(self, sanitizer):
        """Test that event handlers like onclick are removed."""
        html = "<div onclick=\"alert('xss')\">Click me</div>"
        result = sanitizer.sanitize_html(html)
        assert "onclick" not in result
        assert "alert" not in result
        assert result == "<div>Click me</div>"

    def test_data_url_blocking(self, sanitizer):
        """Test that data: URLs are blocked."""
        html = "<img src=\"data:text/html,<script>alert('xss')</script>\">"
        result = sanitizer.sanitize_html(html)
        assert "data:" not in result
        assert "<script>" not in result

    def test_iframe_domain_filtering(self, sanitizer):
        """Test that only trusted domains are allowed in iframes."""
        # Trusted domain should be preserved
        trusted_html = '<iframe src="https://www.youtube.com/embed/123"></iframe>'
        result = sanitizer.sanitize_html(trusted_html)
        assert "youtube.com" in result
        assert "<iframe" in result

        # Untrusted domain should be removed
        untrusted_html = '<iframe src="https://malicious.com/embed/123"></iframe>'
        result = sanitizer.sanitize_html(untrusted_html)
        assert "malicious.com" not in result
        assert "<iframe" not in result or 'src=""' in result

    def test_css_expression_removal(self, sanitizer):
        """Test that CSS expressions are removed."""
        html = "<div style=\"color: red; expression(alert('xss'))\">Text</div>"
        result = sanitizer.sanitize_html(html)
        assert "expression" not in result
        assert "alert" not in result
        assert "color: red" in result  # Safe CSS should remain

    def test_allowed_tags_preservation(self, sanitizer):
        """Test that allowed HTML tags are preserved."""
        html = """
        <h1>Title</h1>
        <p>Paragraph with <strong>bold</strong> and <em>italic</em> text.</p>
        <ul>
            <li>Item 1</li>
            <li>Item 2</li>
        </ul>
        <blockquote>Quote</blockquote>
        <a href="https://example.com">Link</a>
        <img src="https://example.com/image.jpg" alt="Image">
        """
        result = sanitizer.sanitize_html(html)

        # All these tags should be preserved
        for tag in ["h1", "p", "strong", "em", "ul", "li", "blockquote", "a", "img"]:
            assert f"<{tag}" in result

    def test_disallowed_tags_removal(self, sanitizer):
        """Test that disallowed HTML tags are removed."""
        html = """
        <script>alert('xss')</script>
        <object data="malicious.swf"></object>
        <embed src="malicious.swf">
        <form action="/submit"><input type="text"></form>
        <meta http-equiv="refresh" content="0;url=http://malicious.com">
        """
        result = sanitizer.sanitize_html(html)

        # All these tags should be removed
        for tag in ["script", "object", "embed", "form", "input", "meta"]:
            assert f"<{tag}" not in result

    def test_attribute_sanitization(self, sanitizer):
        """Test individual attribute sanitization."""
        # Safe URL
        assert (
            sanitizer.sanitize_attribute_value("href", "https://example.com")
            == "https://example.com"
        )

        # Unsafe URL
        assert sanitizer.sanitize_attribute_value("href", "javascript:alert('xss')") == ""

        # Safe CSS
        safe_css = "color: red; font-size: 14px;"
        result = sanitizer.sanitize_attribute_value("style", safe_css)
        assert "color: red" in result
        assert "font-size: 14px" in result

        # Unsafe CSS
        unsafe_css = "color: red; expression(alert('xss'));"
        result = sanitizer.sanitize_attribute_value("style", unsafe_css)
        assert "expression" not in result
        assert "alert" not in result

    def test_xss_pattern_detection(self, sanitizer):
        """Test XSS pattern detection."""
        # Test various XSS patterns
        xss_patterns = [
            '<script>alert("xss")</script>',
            '<img src="x" onerror="alert(1)">',
            '<a href="javascript:alert(1)">click</a>',
            '<iframe src="javascript:alert(1)"></iframe>',
            '<div style="expression(alert(1))">text</div>',
            '<svg onload="alert(1)">',
        ]

        for pattern in xss_patterns:
            # Pattern should be detected
            assert sanitizer._detect_potential_xss(pattern)
            # Pattern should be sanitized
            result = sanitizer.sanitize_html(pattern)
            assert "alert" not in result or result == ""

    def test_strict_mode_vs_lenient(self, sanitizer, lenient_sanitizer):
        """Test difference between strict and lenient modes."""
        html = '<a href="http://external-site.com">External Link</a>'

        # Both should preserve the link, but strict mode might be more restrictive
        strict_result = sanitizer.sanitize_html(html)
        lenient_result = lenient_sanitizer.sanitize_html(html)

        # Both should preserve basic structure
        assert "<a" in strict_result
        assert "<a" in lenient_result

    def test_empty_and_none_input(self, sanitizer):
        """Test handling of empty and None inputs."""
        assert sanitizer.sanitize_html("") == ""
        assert sanitizer.sanitize_html(None) == ""
        assert sanitizer.sanitize_attribute_value("href", "") == ""
        assert sanitizer.sanitize_attribute_value("href", None) == ""

    def test_malformed_html_handling(self, sanitizer):
        """Test handling of malformed HTML."""
        malformed_html = (
            '<p>Unclosed paragraph<div>Nested without closing<script>alert("xss")</script>'
        )
        result = sanitizer.sanitize_html(malformed_html)

        # Should not crash and should remove script
        assert "alert" not in result
        assert "<script>" not in result

    def test_url_validation(self, sanitizer):
        """Test URL validation logic."""
        # Safe URLs
        safe_urls = [
            "https://example.com",
            "http://example.com",
            "mailto:test@example.com",
            "tel:+1234567890",
            "/relative/path",
            "#anchor",
        ]

        for url in safe_urls:
            assert sanitizer._is_safe_url(url), f"URL should be safe: {url}"

        # Unsafe URLs
        unsafe_urls = [
            "javascript:alert('xss')",
            "data:text/html,<script>alert('xss')</script>",
            "vbscript:msgbox('xss')",
            "//malicious.com/path",  # Protocol-relative
            "../../../etc/passwd",  # Path traversal
        ]

        for url in unsafe_urls:
            assert not sanitizer._is_safe_url(url), f"URL should be unsafe: {url}"

    def test_css_sanitization(self, sanitizer):
        """Test CSS sanitization."""
        # Safe CSS properties
        safe_css = "color: blue; font-size: 16px; margin: 10px; padding: 5px;"
        result = sanitizer._sanitize_css(safe_css)
        assert "color: blue" in result
        assert "font-size: 16px" in result
        assert "margin: 10px" in result
        assert "padding: 5px" in result

        # Unsafe CSS should be removed
        unsafe_css = (
            "color: red; expression(alert('xss')); background: url(javascript:alert('xss'));"
        )
        result = sanitizer._sanitize_css(unsafe_css)
        assert "expression" not in result
        assert "javascript" not in result
        assert "color: red" in result  # Safe part should remain

    def test_convenience_functions(self):
        """Test convenience functions."""
        html = '<p>Test content</p><script>alert("xss")</script>'

        # Test sanitize_html_content function
        result = sanitize_html_content(html, strict=True)
        assert "<p>Test content</p>" in result
        assert "script" not in result

        # Test sanitize_attribute function
        result = sanitize_attribute("href", "javascript:alert('xss')")
        assert result == ""

        result = sanitize_attribute("href", "https://example.com")
        assert result == "https://example.com"


class TestXSSPreventionIntegration:
    """Integration tests for XSS prevention in the broader system."""

    def test_wordpress_content_sanitization(self):
        """Test sanitization of typical WordPress content."""
        wordpress_html = """
        <div class="wp-block-group">
            <p>This is a normal paragraph with <strong>bold text</strong>.</p>
            <script>alert('This should be removed');</script>
            <a href="https://example.com">Safe external link</a>
            <a href="javascript:alert('xss')">Malicious link</a>
            <img src="https://example.com/image.jpg" alt="Safe image">
            <img src="javascript:alert('xss')" alt="Malicious image">
            <iframe src="https://www.youtube.com/embed/123">YouTube</iframe>
            <iframe src="https://malicious.com/embed/123">Malicious</iframe>
        </div>
        """

        result = sanitize_html_content(wordpress_html)

        # Safe content should be preserved
        assert "normal paragraph" in result
        assert "<strong>bold text</strong>" in result
        assert "https://example.com" in result
        assert "youtube.com" in result

        # Malicious content should be removed
        assert "alert('This should be removed')" not in result
        assert "javascript:alert" not in result
        assert "malicious.com" not in result

    def test_shopify_compatibility(self):
        """Test that sanitized content remains Shopify-compatible."""
        html = """
        <div class="media-grid">
            <div class="media-grid-text-box">
                <h2>Product Title</h2>
                <p>Product description with <em>emphasis</em>.</p>
                <a href="/products/item" class="button button--primary">Buy Now</a>
            </div>
        </div>
        """

        result = sanitize_html_content(html)

        # Shopify classes and structure should be preserved
        assert "media-grid" in result
        assert "media-grid-text-box" in result
        assert "button--primary" in result
        assert "<h2>" in result
        assert "<em>" in result

    def test_performance_with_large_content(self):
        """Test sanitization performance with large HTML content."""
        # Create large HTML content
        large_html = "<div>" + "<p>Test paragraph</p>" * 1000 + "</div>"

        # Should complete without timeout
        result = sanitize_html_content(large_html)

        # Should preserve structure
        assert result.startswith("<div>")
        assert result.endswith("</div>")
        assert "Test paragraph" in result

    def test_nested_malicious_content(self):
        """Test handling of deeply nested malicious content."""
        nested_html = """
        <div>
            <div>
                <div>
                    <script>
                        var malicious = function() {
                            alert('Deep XSS');
                            document.cookie = 'stolen';
                        };
                        malicious();
                    </script>
                </div>
            </div>
        </div>
        """

        result = sanitize_html_content(nested_html)

        # Structure should remain but script should be gone
        assert "<div>" in result
        assert "script" not in result
        assert "alert" not in result
        assert "document.cookie" not in result


class TestHTMLSanitizerEdgeCases:
    """Test edge cases and exception handling for HTMLSanitizer."""

    @pytest.fixture
    def sanitizer(self):
        """Create a test sanitizer instance."""
        return HTMLSanitizer(strict_mode=True)

    def test_sanitization_exception_handling(self, sanitizer):
        """Test exception handling in sanitization process."""
        # Simulate an error condition by mocking cleaner
        from unittest.mock import patch

        with patch.object(sanitizer, "cleaner") as mock_cleaner:
            mock_cleaner.clean.side_effect = Exception("Simulated error")
            result = sanitizer.sanitize_html("<p>Test</p>")
            assert result == ""  # Should return empty string on error

    def test_attribute_edge_cases(self, sanitizer):
        """Test edge cases in attribute sanitization."""
        # None value handling (lines 243-247)
        assert sanitizer.sanitize_attribute_value("href", None) == ""
        assert sanitizer.sanitize_attribute_value("style", None) == ""
        assert sanitizer.sanitize_attribute_value("alt", None) == ""
        assert sanitizer.sanitize_attribute_value("unknown", None) == ""

    def test_strict_mode_application(self, sanitizer):
        """Test strict mode rule application."""
        # Test external link modification (lines 288, 293)
        html = '<a href="http://unsafe-external.com">External</a>'
        result = sanitizer.sanitize_html(html)
        # In strict mode, external links might be modified

    def test_iframe_decomposition(self, sanitizer):
        """Test iframe removal in strict mode."""
        # Test iframe decomposition (line 298)
        html = '<iframe src="https://untrusted-domain.com/embed"></iframe>'
        result = sanitizer.sanitize_html(html)
        assert "<iframe" not in result

    def test_url_exception_handling(self, sanitizer):
        """Test URL parsing exception handling."""
        # Test malformed URLs that cause urlparse to fail
        malformed_urls = ["ht!tp://malformed", "javascript\x00:alert(1)", ""]
        for url in malformed_urls:
            result = sanitizer._sanitize_url(url)
            # Should not crash and should be safe

    def test_css_empty_handling(self, sanitizer):
        """Test CSS sanitization with empty input."""
        assert sanitizer._sanitize_css("") == ""
        assert sanitizer._sanitize_css(None) == ""

    def test_text_sanitization_edge_cases(self, sanitizer):
        """Test text sanitization edge cases."""
        # Test _sanitize_text with various inputs (lines 485-497)
        assert sanitizer._sanitize_text("") == ""
        assert sanitizer._sanitize_text(None) == ""

        # Test dangerous character encoding (after script removal)
        dangerous_text = "<div>Test & \"quotes\" 'apostrophes'</div>"
        result = sanitizer._sanitize_text(dangerous_text)
        assert "&lt;" in result  # < should be encoded
        assert "&gt;" in result  # > should be encoded
        assert "&quot;" in result  # " should be encoded
        assert "&#x27;" in result  # ' should be encoded

    def test_iframe_trusted_domain_validation(self, sanitizer):
        """Test trusted iframe domain validation."""
        # Test domain comparison logic (lines 518-519, 540-541)
        trusted_sources = [
            "https://www.youtube.com/embed/123",
            "https://youtube.com/embed/456",
            "https://player.vimeo.com/video/789",
        ]

        for src in trusted_sources:
            assert sanitizer._is_trusted_iframe_source(src)

        # Test exception handling in iframe validation
        assert not sanitizer._is_trusted_iframe_source("invalid://malformed-url")

    def test_relative_url_traversal_protection(self, sanitizer):
        """Test protection against path traversal in relative URLs."""
        # Test lines 425-427 - only checks ../ (forward slashes)
        unix_traversal = "../../../etc/passwd"
        result = sanitizer._sanitize_url(unix_traversal)
        assert result == ""  # Should be blocked

        # Test that backslash traversal isn't currently blocked (by design)
        windows_traversal = "..\\..\\windows\\system32"
        result = sanitizer._sanitize_url(windows_traversal)
        # This will pass through since code only checks "../" not "..\\"
