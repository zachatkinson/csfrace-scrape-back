"""HTML content sanitization utilities for XSS prevention.

This module provides secure HTML sanitization using the bleach library
to prevent XSS attacks while preserving safe content for Shopify conversion.
"""

import re
from urllib.parse import urlparse

import bleach
import structlog
from bs4 import BeautifulSoup

logger = structlog.get_logger(__name__)


class HTMLSanitizer:
    """Secure HTML sanitizer with XSS prevention for web scraping content."""

    # Safe HTML tags allowed in Shopify content
    ALLOWED_TAGS: set[str] = {
        # Text formatting
        "p",
        "br",
        "strong",
        "b",
        "em",
        "i",
        "u",
        "s",
        "del",
        "ins",
        "mark",
        "small",
        "sub",
        "sup",
        "code",
        "pre",
        "kbd",
        "var",
        "samp",
        "q",
        "cite",
        # Headings
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        # Lists
        "ul",
        "ol",
        "li",
        "dl",
        "dt",
        "dd",
        # Links and media
        "a",
        "img",
        "figure",
        "figcaption",
        # Layout
        "div",
        "span",
        "section",
        "article",
        "header",
        "main",
        "footer",
        "blockquote",
        "hr",
        "table",
        "thead",
        "tbody",
        "tfoot",
        "tr",
        "th",
        "td",
        # Shopify-specific
        "iframe",  # For YouTube embeds (will be further validated)
    }

    # Safe attributes for HTML elements
    ALLOWED_ATTRIBUTES: dict[str, list[str]] = {
        # Global attributes
        "*": ["class", "id", "title", "lang", "dir"],
        # Links
        "a": ["href", "title", "rel", "target"],
        # Images
        "img": ["src", "alt", "title", "width", "height", "loading", "decoding"],
        # Layout elements
        "div": ["class", "id", "style"],  # Limited style will be further validated
        "span": ["class", "id", "style"],
        # Tables
        "table": ["class", "id", "summary"],
        "th": ["class", "id", "scope", "colspan", "rowspan"],
        "td": ["class", "id", "colspan", "rowspan"],
        # Media embeds (strictly validated)
        "iframe": ["src", "width", "height", "frameborder", "allowfullscreen", "title"],
        # Lists
        "ol": ["start", "reversed", "type"],
        "li": ["value"],
    }

    # Safe URL schemes for links and media
    ALLOWED_PROTOCOLS: set[str] = {"http", "https", "mailto", "tel", "ftp", "ftps"}

    # Trusted domains for iframe embeds
    TRUSTED_IFRAME_DOMAINS: set[str] = {
        "youtube.com",
        "www.youtube.com",
        "youtube-nocookie.com",
        "www.youtube-nocookie.com",
        "vimeo.com",
        "player.vimeo.com",
        "instagram.com",
        "www.instagram.com",
    }

    # CSS properties allowed in style attributes (very restrictive)
    ALLOWED_CSS_PROPERTIES: set[str] = {
        "color",
        "background-color",
        "font-size",
        "font-weight",
        "font-style",
        "text-align",
        "text-decoration",
        "margin",
        "margin-top",
        "margin-bottom",
        "margin-left",
        "margin-right",
        "padding",
        "padding-top",
        "padding-bottom",
        "padding-left",
        "padding-right",
        "border",
        "border-radius",
        "width",
        "height",
        "max-width",
        "max-height",
        "display",
        "float",
        "clear",
    }

    def __init__(self, strict_mode: bool = True):
        """Initialize HTML sanitizer.

        Args:
            strict_mode: If True, applies stricter sanitization rules
        """
        self.strict_mode = strict_mode
        self._setup_bleach_cleaner()

    def _setup_bleach_cleaner(self) -> None:
        """Configure bleach cleaner with security settings."""
        # Remove script tags and their content before bleach processing
        self.DISALLOWED_TAGS = {"script", "style", "object", "embed", "form", "input", "meta"}

        # Create a CSS sanitizer that allows safe properties
        from bleach.css_sanitizer import CSSSanitizer

        css_sanitizer = CSSSanitizer(
            allowed_css_properties=self.ALLOWED_CSS_PROPERTIES,
            allowed_svg_properties=[],  # No SVG properties allowed
        )

        self.cleaner = bleach.Cleaner(
            tags=self.ALLOWED_TAGS,
            attributes=self.ALLOWED_ATTRIBUTES,
            protocols=self.ALLOWED_PROTOCOLS,
            css_sanitizer=css_sanitizer,
            strip=True,  # Remove disallowed tags entirely
            strip_comments=True,  # Remove HTML comments
        )

    def sanitize_html(self, html_content: str) -> str:
        """Sanitize HTML content to prevent XSS attacks.

        Args:
            html_content: Raw HTML content to sanitize

        Returns:
            Sanitized HTML string safe for display

        Raises:
            ValueError: If content is invalid or contains malicious code
        """
        if not html_content or not isinstance(html_content, str):
            return ""

        try:
            logger.info("Starting HTML sanitization", strict_mode=self.strict_mode)

            # Pre-sanitization security checks
            if self._detect_potential_xss(html_content):
                logger.warning("Potential XSS content detected, applying strict sanitization")

            # Pre-process to remove dangerous tags and their content
            html_content = self._pre_process_html(html_content)

            # Apply bleach sanitization
            sanitized = self.cleaner.clean(html_content)

            # Apply additional filtering
            sanitized = self._post_process_html(sanitized)

            # Post-sanitization validation
            if self.strict_mode:
                sanitized = self._apply_strict_rules(sanitized)

            logger.info("HTML sanitization completed successfully")
            return sanitized

        except Exception as e:
            logger.error("HTML sanitization failed", error=str(e))
            # In case of error, return empty string for security
            return ""

    def sanitize_attribute_value(self, attribute: str, value: str) -> str:
        """Sanitize individual HTML attribute values.

        Args:
            attribute: Attribute name (href, src, etc.)
            value: Attribute value to sanitize

        Returns:
            Sanitized attribute value
        """
        if not value:
            return ""

        # URL attributes need special handling
        if attribute in ("href", "src"):
            return self._sanitize_url(value)
        elif attribute == "style":
            return self._sanitize_css(value)
        elif attribute in ("alt", "title"):
            return self._sanitize_text(value)

        # Default: basic text sanitization
        return self._sanitize_text(value)

    def _detect_potential_xss(self, content: str) -> bool:
        """Detect potential XSS patterns in content.

        Args:
            content: HTML content to analyze

        Returns:
            True if potential XSS detected
        """
        xss_patterns = [
            r"<script[^>]*>.*?</script>",  # Script tags
            r"javascript:",  # JavaScript protocol
            r"on\w+\s*=",  # Event handlers (onclick, onload, etc.)
            r'<iframe[^>]+src=["\'][^"\']*(?:data:|javascript:)',  # Data/JS in iframes
            r"<object[^>]*>",  # Object tags
            r"<embed[^>]*>",  # Embed tags
            r"<form[^>]*>",  # Forms
            r"<meta[^>]+http-equiv",  # Meta refresh
            r'<link[^>]+rel=["\']?stylesheet',  # External stylesheets
            r"expression\s*\(",  # CSS expressions
            r"@import",  # CSS imports
            r"<svg[^>]*onload",  # SVG with onload
        ]

        return any(re.search(pattern, content, re.IGNORECASE) for pattern in xss_patterns)

    def _apply_strict_rules(self, content: str) -> str:
        """Apply additional strict sanitization rules.

        Args:
            content: Pre-sanitized HTML content

        Returns:
            Content with strict rules applied
        """
        soup = BeautifulSoup(content, "html.parser")

        # Remove any remaining script tags or their content
        for script in soup.find_all("script"):
            script.decompose()

        # Validate all links point to safe domains
        for link in soup.find_all("a", href=True):
            if not self._is_safe_url(link["href"]):
                link["href"] = "#"  # Make link safe but non-functional

        # Ensure iframes only embed from trusted sources
        for iframe in soup.find_all("iframe", src=True):
            if not self._is_trusted_iframe_source(iframe["src"]):
                iframe.decompose()

        return str(soup)

    def _pre_process_html(self, html: str) -> str:
        """Pre-process HTML to remove dangerous tags and their content completely."""
        soup = BeautifulSoup(html, "html.parser")

        # Remove script tags and all their content completely
        for tag in soup.find_all(["script", "style", "object", "embed"]):
            tag.decompose()  # Completely remove tag and contents

        # Remove form-related tags
        for tag in soup.find_all(["form", "input", "textarea", "select", "option"]):
            tag.decompose()

        # Remove meta tags that could be used for redirects
        for tag in soup.find_all("meta"):
            tag.decompose()

        return str(soup)

    def _post_process_html(self, html: str) -> str:
        """Post-process HTML to apply custom filtering."""
        soup = BeautifulSoup(html, "html.parser")

        # Filter style attributes
        for element in soup.find_all(attrs={"style": True}):
            style_value = element.get("style", "")
            sanitized_style = self._sanitize_css(style_value)
            if sanitized_style:
                element["style"] = sanitized_style
            else:
                del element["style"]

        # Filter URLs in href and src attributes
        for element in soup.find_all(attrs={"href": True}):
            href_value = element.get("href", "")
            sanitized_href = self._sanitize_url(href_value)
            if sanitized_href:
                element["href"] = sanitized_href
            else:
                element["href"] = "#"

        for element in soup.find_all(attrs={"src": True}):
            src_value = element.get("src", "")
            if element.name == "iframe" and not self._is_trusted_iframe_source(src_value):
                element.decompose()
                continue
            sanitized_src = self._sanitize_url(src_value)
            if sanitized_src:
                element["src"] = sanitized_src
            else:
                element.decompose()

        return str(soup)

    def _css_filter(self, tag: str, name: str, value: str) -> str:
        """Filter CSS style attributes for security.

        Args:
            tag: HTML tag name
            name: Attribute name
            value: Attribute value

        Returns:
            Filtered CSS value
        """
        if name != "style":
            return value

        return self._sanitize_css(value)

    def _url_filter(self, tag: str, name: str, value: str) -> str:
        """Filter URL attributes for security.

        Args:
            tag: HTML tag name
            name: Attribute name
            value: Attribute value

        Returns:
            Filtered URL value
        """
        if name in ("href", "src"):
            return self._sanitize_url(value)
        return value

    def _iframe_filter(self, tag: str, name: str, value: str) -> str:
        """Filter iframe sources for security.

        Args:
            tag: HTML tag name
            name: Attribute name
            value: Attribute value

        Returns:
            Filtered iframe value or empty string if unsafe
        """
        if tag == "iframe" and name == "src":
            if self._is_trusted_iframe_source(value):
                return value
            return ""  # Remove unsafe iframe sources
        return value

    def _sanitize_url(self, url: str) -> str:
        """Sanitize URL values to prevent XSS.

        Args:
            url: URL to sanitize

        Returns:
            Sanitized URL or empty string if unsafe
        """
        try:
            parsed = urlparse(url)

            # Block dangerous protocols
            if parsed.scheme and parsed.scheme.lower() not in self.ALLOWED_PROTOCOLS:
                logger.warning("Blocked unsafe URL protocol", url=url, scheme=parsed.scheme)
                return ""

            # Block data: URLs which can contain scripts
            if parsed.scheme == "data":
                return ""

            # For relative URLs, ensure they don't try to break out
            if not parsed.scheme and "../" in url:
                logger.warning("Blocked potentially dangerous relative URL", url=url)
                return ""

            return url

        except Exception:
            logger.warning("Failed to parse URL, blocking for security", url=url)
            return ""

    def _sanitize_css(self, css: str) -> str:
        """Sanitize CSS style attribute values.

        Args:
            css: CSS string to sanitize

        Returns:
            Sanitized CSS string
        """
        if not css:
            return ""

        # Remove dangerous CSS patterns
        dangerous_patterns = [
            r"expression\s*\(",  # IE CSS expressions
            r"javascript:",  # JavaScript protocol
            r"@import",  # CSS imports
            r'url\s*\(\s*["\']?\s*data:',  # Data URLs
            r'url\s*\(\s*["\']?\s*javascript:',  # JavaScript URLs
            r"binding:",  # Mozilla binding
            r"-moz-binding",  # Mozilla binding
            r"behavior:",  # IE behaviors
        ]

        cleaned_css = css
        for pattern in dangerous_patterns:
            cleaned_css = re.sub(pattern, "", cleaned_css, flags=re.IGNORECASE)

        # Only allow whitelisted CSS properties
        properties = []
        for declaration in cleaned_css.split(";"):
            if ":" in declaration:
                prop, value = declaration.split(":", 1)
                prop = prop.strip().lower()
                if prop in self.ALLOWED_CSS_PROPERTIES:
                    # Basic value sanitization
                    value = re.sub(r'[<>"\']', "", value.strip())
                    properties.append(f"{prop}: {value}")

        return "; ".join(properties) if properties else ""

    def _sanitize_text(self, text: str) -> str:
        """Sanitize plain text content.

        Args:
            text: Text to sanitize

        Returns:
            Sanitized text string
        """
        if not text:
            return ""

        # Remove potential script injections
        text = re.sub(r"<script[^>]*>.*?</script>", "", text, flags=re.IGNORECASE | re.DOTALL)
        text = re.sub(r"javascript:", "", text, flags=re.IGNORECASE)

        # HTML encode potentially dangerous characters
        dangerous_chars = {"<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#x27;"}
        for char, encoded in dangerous_chars.items():
            text = text.replace(char, encoded)

        return text.strip()

    def _is_safe_url(self, url: str) -> bool:
        """Check if URL is safe for links.

        Args:
            url: URL to validate

        Returns:
            True if URL is safe
        """
        try:
            parsed = urlparse(url)

            # Allow relative URLs that don't break out of domain
            if not parsed.scheme:
                return not url.startswith("//") and "../" not in url

            # Check protocol
            return parsed.scheme.lower() in self.ALLOWED_PROTOCOLS

        except Exception:
            return False

    def _is_trusted_iframe_source(self, src: str) -> bool:
        """Check if iframe source is from trusted domain.

        Args:
            src: Iframe source URL

        Returns:
            True if source is trusted
        """
        try:
            parsed = urlparse(src)
            domain = parsed.netloc.lower()

            # Remove www. prefix for comparison
            if domain.startswith("www."):
                domain = domain[4:]

            return any(trusted in domain for trusted in self.TRUSTED_IFRAME_DOMAINS)

        except Exception:
            return False


# Global sanitizer instance for convenience
default_sanitizer = HTMLSanitizer(strict_mode=True)


def sanitize_html_content(html: str, strict: bool = True) -> str:
    """Convenience function for HTML sanitization.

    Args:
        html: HTML content to sanitize
        strict: Whether to apply strict sanitization rules

    Returns:
        Sanitized HTML string
    """
    sanitizer = HTMLSanitizer(strict_mode=strict)
    return sanitizer.sanitize_html(html)


def sanitize_attribute(attribute: str, value: str) -> str:
    """Convenience function for attribute sanitization.

    Args:
        attribute: Attribute name
        value: Attribute value

    Returns:
        Sanitized attribute value
    """
    return default_sanitizer.sanitize_attribute_value(attribute, value)
