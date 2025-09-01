"""URL processing utilities to eliminate DRY violations."""

from urllib.parse import ParseResult, urljoin, urlparse

import structlog

logger = structlog.get_logger(__name__)


def safe_parse_url(url: str) -> ParseResult | None:
    """Safely parse URL with error handling.

    Args:
        url: URL string to parse

    Returns:
        ParseResult object or None if parsing fails
    """
    try:
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            logger.warning("Invalid URL structure", url=url)
            return None
        return parsed
    except Exception as e:
        logger.error("URL parsing failed", url=url, error=str(e))
        return None


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

    # If already absolute, validate and return
    if url.startswith(("http://", "https://")):
        return url if safe_parse_url(url) else None

    # If relative and we have base_url, resolve it
    if base_url and url.startswith("/"):
        try:
            return urljoin(base_url, url)
        except Exception as e:
            logger.warning("URL join failed", url=url, base_url=base_url, error=str(e))
            return None

    # If it looks like a relative URL without leading slash
    if base_url and not url.startswith(("http", "//", "#")):
        try:
            return urljoin(base_url, url)
        except Exception as e:
            logger.warning("URL join failed", url=url, base_url=base_url, error=str(e))
            return None

    logger.warning("Cannot normalize URL", url=url, base_url=base_url)
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

    # If no filename or extension, generate one
    if not filename or "." not in filename:
        # Use last path segment or domain as base
        base = filename or parsed.netloc.replace(".", "_")
        filename = f"{base}{default_extension}"

    # Clean up filename for filesystem safety
    filename = filename.replace(" ", "_").replace("?", "").replace("#", "")

    return filename or f"file{default_extension}"
