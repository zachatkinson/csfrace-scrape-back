"""HTTP utilities to eliminate DRY violations in request handling."""


import aiohttp
import structlog

from ..constants import CONSTANTS

logger = structlog.get_logger(__name__)


class HTTPResponse:
    """Standardized HTTP response wrapper."""

    def __init__(self, status: int, content: str, headers: dict[str, str] | None = None):
        self.status = status
        self.content = content
        self.headers = headers or {}
        self.is_success = 200 <= status < 300


async def safe_http_get(
    session: aiohttp.ClientSession,
    url: str,
    timeout: int | None = None,
    expected_statuses: set[int] | None = None,
    log_errors: bool = True,
) -> HTTPResponse:
    """Safely perform HTTP GET request with standardized error handling.

    Args:
        session: aiohttp session
        url: URL to fetch
        timeout: Request timeout in seconds (uses default if None)
        expected_statuses: Set of acceptable status codes (default: 2xx)
        log_errors: Whether to log errors

    Returns:
        HTTPResponse object with status, content, and metadata

    Raises:
        aiohttp.ClientError: For connection/timeout errors
        Exception: For unexpected errors
    """
    timeout = timeout or CONSTANTS.DEFAULT_TIMEOUT
    expected_statuses = expected_statuses or {CONSTANTS.HTTP_STATUS_OK}

    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=timeout)) as response:
            content = await response.text()

            if response.status in expected_statuses:
                logger.debug("HTTP request successful", url=url, status=response.status)
                return HTTPResponse(
                    status=response.status, content=content, headers=dict(response.headers)
                )
            else:
                if log_errors:
                    logger.warning(
                        "HTTP request returned unexpected status",
                        url=url,
                        status=response.status,
                        expected=list(expected_statuses),
                    )
                return HTTPResponse(status=response.status, content=content)

    except TimeoutError:
        if log_errors:
            logger.error("HTTP request timeout", url=url, timeout=timeout)
        raise
    except aiohttp.ClientError as e:
        if log_errors:
            logger.error("HTTP client error", url=url, error=str(e))
        raise
    except Exception as e:
        if log_errors:
            logger.error("Unexpected HTTP error", url=url, error=str(e))
        raise


async def safe_http_get_with_raise(
    session: aiohttp.ClientSession, url: str, timeout: int | None = None
) -> str:
    """HTTP GET that raises for status and returns content directly.

    This is the most common pattern - fetch content and raise on HTTP errors.

    Args:
        session: aiohttp session
        url: URL to fetch
        timeout: Request timeout in seconds

    Returns:
        Response content as string

    Raises:
        aiohttp.HTTPError: For HTTP error status codes
        aiohttp.ClientError: For connection/timeout errors
    """
    timeout = timeout or CONSTANTS.DEFAULT_TIMEOUT

    async with session.get(url, timeout=aiohttp.ClientTimeout(total=timeout)) as response:
        response.raise_for_status()  # Raises for 4xx/5xx status codes
        return await response.text()


def check_http_status(status: int, url: str, context: str = "request") -> bool:
    """Check HTTP status and log appropriately.

    Args:
        status: HTTP status code
        url: URL that was requested
        context: Context description for logging

    Returns:
        True if status indicates success
    """
    if status == CONSTANTS.HTTP_STATUS_OK:
        logger.debug(f"{context} successful", url=url, status=status)
        return True
    elif status == CONSTANTS.HTTP_STATUS_NOT_FOUND:
        logger.info(f"{context} returned 404", url=url)
        return False
    elif status >= CONSTANTS.HTTP_STATUS_SERVER_ERROR:
        logger.error(f"{context} server error", url=url, status=status)
        return False
    else:
        logger.warning(f"{context} unexpected status", url=url, status=status)
        return False
