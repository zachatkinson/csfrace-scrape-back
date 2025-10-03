"""URL processing utilities following Single Responsibility Principle.

This module handles URL parsing, domain extraction, and validation operations
with proper error handling and logging.
"""

from urllib.parse import urlparse

from src.core.decorators import content_processing_error_handler
from src.core.logging_hierarchy import get_scraping_logger

logger = get_scraping_logger()


class URLError(ValueError):
    """Custom exception for URL processing errors."""

    pass


@content_processing_error_handler("extract domain from URL")
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


@content_processing_error_handler("validate URL format")
def validate_url(url: str) -> bool:
    """Validate if a URL is properly formatted and has a domain.

    Args:
        url: The URL to validate

    Returns:
        True if URL is valid and has a domain, False otherwise
    """
    extract_domain(url)
    return True


@content_processing_error_handler("normalize URL format")
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
    parsed = urlparse(url)
    if not parsed.netloc:
        raise URLError(f"No domain found in normalized URL: {url}")
    return url
