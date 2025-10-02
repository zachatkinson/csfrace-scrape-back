"""URL processing utilities to eliminate DRY violations."""

from urllib.parse import ParseResult, urljoin, urlparse

from src.core.logging_hierarchy import get_general_logger

logger = get_general_logger()


def _is_valid_domain(domain: str) -> bool:
    """Check if domain looks valid.

    Args:
        domain: Domain string to validate

    Returns:
        True if domain appears valid, False otherwise
    """
    if not domain:
        return False
    # Allow localhost, IP addresses, and IPv6
    if domain in ("localhost", "127.0.0.1") or domain.startswith("[") or ":" in domain:
        return True
    # Domain should have at least one dot for proper domains
    return "." in domain


def _join_urls_safe(base_url: str, url: str) -> str:
    """Join URLs safely - urlparse is a stdlib function, no network operation."""
    return urljoin(base_url, url)


def _parse_url_safe(url: str) -> ParseResult:
    """Parse URL safely - urlparse is a stdlib function, no network operation."""
    return urlparse(url)


def safe_parse_url(url: str) -> ParseResult | None:
    """Safely parse URL with error handling.

    Args:
        url: URL string to parse

    Returns:
        ParseResult object or None if parsing fails
    """
    parsed = _parse_url_safe(url)
    if not parsed or not parsed.scheme or not parsed.netloc:
        logger.logger.warning("Invalid URL structure", url=url)
        return None
    return parsed


def extract_domain(url: str) -> str | None:
    """Extract domain from URL.

    Args:
        url: URL string

    Returns:
        Domain name or None if extraction fails
    """
    parsed = safe_parse_url(url)
    return parsed.netloc if parsed else None


def is_same_domain(url1: str, url2: str) -> bool:
    """Check if two URLs are from the same domain.

    Args:
        url1: First URL
        url2: Second URL

    Returns:
        True if same domain, False otherwise
    """
    domain1 = extract_domain(url1)
    domain2 = extract_domain(url2)
    return domain1 is not None and domain1 == domain2


def normalize_url(url: str, base_url: str | None = None) -> str | None:
    """Normalize URL by resolving relative URLs and cleaning up.

    Args:
        url: URL to normalize (can be relative)
        base_url: Base URL for resolving relative URLs

    Returns:
        Normalized absolute URL or None if invalid
    """
    if not url or not url.strip():
        return None

    url = url.strip()

    # Reject protocol-relative URLs (//example.com/path)
    if url.startswith("//"):
        return None

    # If already absolute, validate domain and return
    if url.startswith(("http://", "https://")):
        parsed = safe_parse_url(url)
        if parsed and _is_valid_domain(parsed.netloc):
            return url
        return None

    # If relative and we have base_url, resolve it
    if base_url and url.startswith("/"):
        result = _join_urls_safe(base_url, url)
        return result if result else None

    # If it looks like a relative URL without leading slash
    if base_url and not url.startswith(("http", "#")):
        result = _join_urls_safe(base_url, url)
        return result if result else None

    logger.logger.warning("Cannot normalize URL", url=url, base_url=base_url)
    return None


def extract_filename_from_url(url: str, default_extension: str = "") -> str:
    """Extract filename from URL path.

    Args:
        url: URL string
        default_extension: Extension to add if none found

    Returns:
        Filename extracted from URL path
    """
    parsed = safe_parse_url(url)
    if not parsed:
        return f"unknown{default_extension}"

    # Extract filename from path
    path = parsed.path
    filename = path.split("/")[-1] if "/" in path else path

    # If query looks like it could be part of filename (contains extension), combine them
    if parsed.query and "." in parsed.query:
        filename = filename + parsed.query

    # Clean up filename for filesystem safety - remove query/fragment separators
    filename = filename.replace("?", "").replace("#", "").replace(" ", "_")

    # If no filename or extension after cleaning, generate one
    if not filename or "." not in filename:
        # Use last path segment or domain as base
        base = filename or parsed.netloc.replace(".", "_") or "file"
        filename = f"{base}{default_extension}"

    return filename or f"file{default_extension}"
