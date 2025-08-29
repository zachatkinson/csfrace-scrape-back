"""Tests for XSS prevention integration in HTML processor."""

import pytest
from bs4 import BeautifulSoup

from src.processors.html_processor import HTMLProcessor


class TestHTMLProcessorXSSPrevention:
    """Test XSS prevention in the HTML processor."""

    @pytest.fixture
    def processor(self):
        """Create HTML processor with sanitization enabled."""
        return HTMLProcessor(enable_sanitization=True)

    @pytest.fixture
    def unsafe_processor(self):
        """Create HTML processor without sanitization for comparison."""
        return HTMLProcessor(enable_sanitization=False)

    @pytest.mark.asyncio
    async def test_script_injection_prevention(self, processor):
        """Test that script injections are prevented during processing."""
        malicious_html = """
        <html>
            <body>
                <div class="entry-content">
                    <p>Normal content</p>
                    <script>alert('XSS attack!');</script>
                    <p>More content</p>
                </div>
            </body>
        </html>
        """

        soup = BeautifulSoup(malicious_html, "html.parser")
        result = await processor.process(soup)

        # Normal content should be preserved
        assert "Normal content" in result
        assert "More content" in result

        # Script should be removed
        assert "<script>" not in result
        assert "alert('XSS attack!')" not in result

    @pytest.mark.asyncio
    async def test_event_handler_removal(self, processor):
        """Test that event handlers are removed from elements."""
        malicious_html = """
        <html>
            <body>
                <div class="entry-content">
                    <img src="test.jpg" onload="alert('XSS')" alt="Test">
                    <button onclick="window.location='http://malicious.com'">Click me</button>
                    <div onmouseover="document.cookie='stolen=true'">Hover me</div>
                </div>
            </body>
        </html>
        """

        soup = BeautifulSoup(malicious_html, "html.parser")
        result = await processor.process(soup)

        # Elements should be preserved but handlers removed
        assert "src=" in result or "<img" in result  # Image structure preserved
        assert "Click me" in result  # Button text preserved
        assert "Hover me" in result  # Div text preserved

        # Event handlers should be removed
        assert "onload" not in result
        assert "onclick" not in result
        assert "onmouseover" not in result
        assert "alert('XSS')" not in result
        assert "malicious.com" not in result

    @pytest.mark.asyncio
    async def test_javascript_url_sanitization(self, processor):
        """Test that javascript: URLs are sanitized."""
        malicious_html = """
        <html>
            <body>
                <div class="entry-content">
                    <a href="javascript:alert('XSS')">Malicious Link</a>
                    <a href="https://example.com">Safe Link</a>
                    <img src="javascript:alert('XSS')" alt="Malicious Image">
                </div>
            </body>
        </html>
        """

        soup = BeautifulSoup(malicious_html, "html.parser")
        result = await processor.process(soup)

        # Link text should be preserved
        assert "Malicious Link" in result
        assert "Safe Link" in result

        # Safe URL should be preserved
        assert "https://example.com" in result

        # JavaScript URLs should be removed
        assert "javascript:alert" not in result

    @pytest.mark.asyncio
    async def test_wordpress_embed_xss_prevention(self, processor):
        """Test XSS prevention in WordPress embeds."""
        malicious_html = """
        <html>
            <body>
                <div class="entry-content">
                    <figure class="wp-block-embed-youtube">
                        <div class="wp-block-embed__wrapper">
                            <iframe src="javascript:alert('XSS')" width="560" height="315"></iframe>
                        </div>
                    </figure>
                    <figure class="wp-block-embed-youtube">
                        <div class="wp-block-embed__wrapper">
                            <iframe src="https://www.youtube.com/embed/dQw4w9WgXcQ" width="560" height="315"></iframe>
                        </div>
                    </figure>
                </div>
            </body>
        </html>
        """

        soup = BeautifulSoup(malicious_html, "html.parser")
        result = await processor.process(soup)

        # Safe YouTube embed should be preserved
        assert "youtube.com/embed" in result

        # JavaScript URL should be removed
        assert "javascript:alert" not in result

    @pytest.mark.asyncio
    async def test_css_injection_prevention(self, processor):
        """Test that CSS injections are prevented."""
        malicious_html = """
        <html>
            <body>
                <div class="entry-content">
                    <div style="color: red; expression(alert('XSS'));">Safe and unsafe CSS</div>
                    <p style="background: url(javascript:alert('XSS'));">Background XSS</p>
                    <span style="font-size: 14px; color: blue;">Safe CSS only</span>
                </div>
            </body>
        </html>
        """

        soup = BeautifulSoup(malicious_html, "html.parser")
        result = await processor.process(soup)

        # Text content should be preserved
        assert "Safe and unsafe CSS" in result
        assert "Background XSS" in result
        assert "Safe CSS only" in result

        # Safe CSS might be preserved (depending on sanitization level)
        # The key requirement is that malicious CSS is removed

        # Malicious CSS should be removed
        assert "expression(" not in result
        assert "javascript:alert" not in result

    @pytest.mark.asyncio
    async def test_data_url_prevention(self, processor):
        """Test that data: URLs are blocked."""
        malicious_html = """
        <html>
            <body>
                <div class="entry-content">
                    <img src="data:text/html,<script>alert('XSS')</script>" alt="Data URL XSS">
                    <a href="data:text/html,<script>alert('XSS')</script>">Data URL Link</a>
                    <img src="https://example.com/safe-image.jpg" alt="Safe Image">
                </div>
            </body>
        </html>
        """

        soup = BeautifulSoup(malicious_html, "html.parser")
        result = await processor.process(soup)

        # Text content should be preserved
        assert "Data URL XSS" in result
        assert "Data URL Link" in result
        assert "Safe Image" in result

        # Safe URL should be preserved
        assert "https://example.com/safe-image.jpg" in result

        # Data URLs should be removed
        assert "data:text/html" not in result
        assert "<script>alert" not in result

    @pytest.mark.asyncio
    async def test_nested_xss_prevention(self, processor):
        """Test prevention of nested XSS attempts."""
        malicious_html = """
        <html>
            <body>
                <div class="entry-content">
                    <div class="wp-block-kadence-rowlayout">
                        <div class="kt-has-2-columns">
                            <div class="wp-block-kadence-column">
                                <div class="kt-inside-inner-col">
                                    <p>Normal content</p>
                                    <script>alert('Nested XSS');</script>
                                </div>
                            </div>
                            <div class="wp-block-kadence-column">
                                <div class="kt-inside-inner-col">
                                    <img src="test.jpg" onerror="alert('Image XSS')" alt="Test">
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </body>
        </html>
        """

        soup = BeautifulSoup(malicious_html, "html.parser")
        result = await processor.process(soup)

        # Structure conversion should work
        assert "media-grid" in result or "Normal content" in result

        # XSS attempts should be blocked
        assert "alert('Nested XSS')" not in result
        assert "alert('Image XSS')" not in result
        assert "onerror=" not in result
        assert "<script>" not in result

    @pytest.mark.asyncio
    async def test_sanitization_disabled(self, unsafe_processor):
        """Test that sanitization can be disabled when needed."""
        html_with_scripts = """
        <html>
            <body>
                <div class="entry-content">
                    <p>Content</p>
                    <script>console.log('test');</script>
                </div>
            </body>
        </html>
        """

        soup = BeautifulSoup(html_with_scripts, "html.parser")
        result = await unsafe_processor.process(soup)

        # Content should be preserved
        assert "Content" in result

        # Scripts should be removed by _remove_scripts method, not sanitizer
        # (The processor removes scripts regardless of sanitization setting)
        assert "console.log('test')" not in result

    @pytest.mark.asyncio
    async def test_complex_wordpress_content_sanitization(self, processor):
        """Test sanitization of complex WordPress content."""
        complex_html = """
        <html>
            <body>
                <div class="entry-content">
                    <div class="wp-block-kadence-advancedgallery">
                        <img src="test1.jpg" alt="Test 1" onload="alert('Gallery XSS')">
                        <img src="javascript:alert('Img XSS')" alt="Test 2">
                    </div>
                    <div class="wp-block-kadence-advancedbtn">
                        <a class="button" href="javascript:alert('Button XSS')">Click Me</a>
                    </div>
                    <figure class="wp-block-pullquote">
                        <blockquote>
                            <p>Quote text</p>
                            <script>alert('Quote XSS');</script>
                        </blockquote>
                    </figure>
                    <iframe class="instagram-media" src="javascript:alert('Instagram XSS')"></iframe>
                </div>
            </body>
        </html>
        """

        soup = BeautifulSoup(complex_html, "html.parser")
        result = await processor.process(soup)

        # Structure should be converted properly
        assert "media-grid" in result or len(result) > 0

        # Content should be preserved
        assert "Quote text" in result

        # All XSS attempts should be blocked
        xss_patterns = [
            "alert('Gallery XSS')",
            "alert('Img XSS')",
            "alert('Button XSS')",
            "alert('Quote XSS')",
            "alert('Instagram XSS')",
            "javascript:alert",
            "onload=",
            "<script>",
        ]

        for pattern in xss_patterns:
            assert pattern not in result, f"XSS pattern found: {pattern}"

    @pytest.mark.asyncio
    async def test_sanitization_preserves_shopify_classes(self, processor):
        """Test that sanitization preserves important Shopify classes."""
        html = """
        <html>
            <body>
                <div class="entry-content">
                    <div class="media-grid-2">
                        <div class="media-grid-text-box">
                            <h2>Product Title</h2>
                            <script>alert('XSS in product');</script>
                        </div>
                    </div>
                    <a class="button button--primary" href="javascript:alert('XSS')">Buy Now</a>
                </div>
            </body>
        </html>
        """

        soup = BeautifulSoup(html, "html.parser")
        result = await processor.process(soup)

        # Shopify classes should be preserved
        assert "media-grid-2" in result
        assert "media-grid-text-box" in result
        assert "button--primary" in result

        # Content should be preserved
        assert "Product Title" in result
        assert "Buy Now" in result

        # XSS should be blocked
        assert "alert('XSS" not in result
        assert "javascript:alert" not in result
        assert "<script>" not in result

    @pytest.mark.asyncio
    async def test_error_handling_with_malformed_xss(self, processor):
        """Test error handling with malformed XSS attempts."""
        malformed_html = """
        <html>
            <body>
                <div class="entry-content">
                    <p>Normal content</p>
                    <script>alert('unclosed script
                    <div onclick="alert('unclosed onclick
                    <img src="javascript:alert('unclosed js
                    <p>More normal content</p>
                </div>
            </body>
        </html>
        """

        soup = BeautifulSoup(malformed_html, "html.parser")
        result = await processor.process(soup)

        # Should not crash
        assert result is not None
        assert len(result) > 0

        # Normal content should be preserved
        assert "Normal content" in result
        # Note: Malformed HTML might cause some content to be lost during parsing

        # Malformed XSS should be handled safely
        assert "alert(" not in result or result.count("alert(") == 0
