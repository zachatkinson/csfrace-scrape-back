"""URL processing utilities following Single Responsibility Principle.

This module handles URL parsing, domain extraction, and validation operations
with proper error handling and logging.
"""

from urllib.parse import urlparse

from src.utils.logging import get_logger

logger = get_logger(__name__)


class URLError(ValueError):
    """Custom exception for URL processing errors."""

    pass


def extract_domain(url: str) -> str:
    """Extract domain from URL with comprehensive validation and error handling.

    This function extracts the domain from a URL, handling various edge cases
    and providing consistent domain normalization.

    Args:
        url: The URL to extract domain from (e.g., "https://www.example.com/path")

    Returns:
        The normalized domain name (e.g., "example.com")

    Raises:
        URLError: If URL is invalid, malformed, or has no domain
        TypeError: If url is not a string

    Examples:
        >>> extract_domain("https://www.example.com/path")
        "example.com"
        >>> extract_domain("http://subdomain.example.com:8080/api")
        "subdomain.example.com"
        >>> extract_domain("ftp://files.example.org")
        "files.example.org"
    """
    if not isinstance(url, str):
        raise TypeError(f"URL must be a string, got {type(url).__name__}")

    if not url.strip():
        raise URLError("URL cannot be empty")

    try:
        # Parse URL using urllib.parse for RFC-compliant parsing
        parsed = urlparse(url.strip())

        # Validate that URL has a netloc (domain) component
        if not parsed.netloc:
            raise URLError(f"No domain found in URL: {url}")

        # Extract domain, handling port numbers and userinfo
        domain = parsed.netloc.lower()

        # Remove userinfo (user:pass@domain) if present
        if "@" in domain:
            domain = domain.split("@")[-1]

        # Remove port number if present
        if ":" in domain:
            domain = domain.split(":")[0]

        # Remove leading 'www.' subdomain for normalization
        # This is a common practice for domain analytics
        if domain.startswith("www."):
            domain = domain[4:]

        # Final validation - ensure domain is not empty after processing
        if not domain:
            raise URLError(f"Domain extraction resulted in empty string for URL: {url}")

        # Basic domain format validation (contains at least one dot for TLD)
        if "." not in domain:
            logger.warning(f"Domain '{domain}' appears to be missing TLD, but proceeding")

        logger.debug(f"Extracted domain '{domain}' from URL '{url}'")
        return domain

    except Exception as e:
        # Re-raise URLError as-is, wrap other exceptions
        if isinstance(e, URLError):
            raise

        logger.error(f"Failed to extract domain from URL '{url}': {e}")
        raise URLError(f"Invalid URL format: {url}") from e


def validate_url(url: str) -> bool:
    """Validate if a URL is properly formatted and has a domain.

    Args:
        url: The URL to validate

    Returns:
        True if URL is valid and has a domain, False otherwise
    """
    try:
        extract_domain(url)
        return True
    except (URLError, TypeError):
        return False


def normalize_url(url: str) -> str:
    """Normalize URL for consistent processing.

    Args:
        url: The URL to normalize

    Returns:
        Normalized URL with consistent scheme and format

    Raises:
        URLError: If URL cannot be normalized
    """
    if not isinstance(url, str):
        raise TypeError(f"URL must be a string, got {type(url).__name__}")

    url = url.strip()
    if not url:
        raise URLError("URL cannot be empty")

    # Add https:// if no scheme is present
    if not url.startswith(("http://", "https://", "ftp://")):
        url = f"https://{url}"

    # Validate the normalized URL
    try:
        parsed = urlparse(url)
        if not parsed.netloc:
            raise URLError(f"No domain found in normalized URL: {url}")
        return url
    except Exception as e:
        raise URLError(f"Failed to normalize URL '{url}': {e}") from e
