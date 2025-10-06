"""Robots.txt parsing and rate limiting compliance."""

from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import aiohttp
import asyncio
from tenacity import AsyncRetrying, stop_after_attempt, wait_fixed

from src.core.decorators import network_error_handler
from src.core.logging_hierarchy import get_scraping_logger

from ..constants.api import (
    HTTP_STATUS_NOT_FOUND,
    HTTP_STATUS_OK,
    RATE_LIMIT_DELAY,
    ROBOTS_TIMEOUT,
)
from ..constants.caching import RESPECT_ROBOTS_TXT
from ..core.exceptions import RateLimitError
from ..utils.http import safe_http_get

logger = get_scraping_logger()


class RobotsChecker:
    """Handles robots.txt compliance and crawl delay enforcement."""

    def __init__(self) -> None:
        """Initialize robots checker with cache."""
        self._cache: dict[str, RobotFileParser | None] = {}
        self._last_request: dict[str, float] = {}

    @network_error_handler("fetch robots.txt parser")
    async def get_robots_parser(
        self, base_url: str, session: aiohttp.ClientSession | None
    ) -> RobotFileParser | None:
        """Get robots.txt parser for a domain with caching.

        Args:
            base_url: Base URL to get robots.txt for
            session: aiohttp session for making requests

        Returns:
            RobotFileParser instance or None if not available
        """
        if session is None:
            logger.warning("No session provided for robots.txt fetch", url=base_url)
            return None

        parsed_url = urlparse(base_url)
        domain = f"{parsed_url.scheme}://{parsed_url.netloc}"

        # Check cache first
        if domain in self._cache:
            logger.debug("Using cached robots.txt", domain=domain)
            return self._cache[domain]

        robots_url = urljoin(domain, "/robots.txt")
        result = None

        try:
            logger.debug("Fetching robots.txt", url=robots_url)

            # Use tenacity for retry logic
            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(3), wait=wait_fixed(1), reraise=True
            ):
                with attempt:
                    http_response = await safe_http_get(
                        session,
                        robots_url,
                        timeout=ROBOTS_TIMEOUT,
                        expected_statuses={
                            HTTP_STATUS_OK,
                            HTTP_STATUS_NOT_FOUND,
                        },
                    )

                    if http_response.status == HTTP_STATUS_OK:
                        robots_content = http_response.content

                        # Parse robots.txt content directly
                        rp = RobotFileParser()
                        rp.set_url(robots_url)

                        # Parse the content line by line - decode bytes to string if needed
                        if isinstance(robots_content, bytes):
                            text_content = robots_content.decode("utf-8", errors="ignore")
                        else:
                            text_content = str(robots_content)
                        lines = text_content.splitlines()
                        rp.parse(lines)

                        result = rp
                        logger.info("Successfully loaded robots.txt", domain=domain, url=robots_url)
                    elif http_response.status == HTTP_STATUS_NOT_FOUND:
                        logger.info("No robots.txt found", domain=domain)
                        result = None
                    else:
                        logger.warning(
                            "Unexpected robots.txt response",
                            domain=domain,
                            status=http_response.status,
                        )
                        result = None

        except Exception as e:
            logger.error("Failed to fetch robots.txt", domain=domain, error=str(e))
            result = None

        # Cache the result (success or failure) to avoid repeated requests
        self._cache[domain] = result
        return result

    @network_error_handler("check robots.txt permissions")
    async def can_fetch(
        self, url: str, user_agent: str = "*", session: aiohttp.ClientSession | None = None
    ) -> bool:
        """Check if we're allowed to fetch the given URL according to robots.txt.

        Args:
            url: URL to check
            user_agent: User agent string to check for
            session: aiohttp session (required if not cached)

        Returns:
            True if allowed to fetch, False otherwise
        """
        if not RESPECT_ROBOTS_TXT:
            return True

        rp = await self.get_robots_parser(url, session)
        if rp is None:
            # No robots.txt means everything is allowed
            return True

        can_fetch = rp.can_fetch(user_agent, url)
        logger.debug("Robots.txt check", url=url, allowed=can_fetch)
        return can_fetch

    @network_error_handler("get robots.txt crawl delay")
    async def get_crawl_delay(
        self, url: str, user_agent: str = "*", session: aiohttp.ClientSession | None = None
    ) -> float:
        """Get the crawl delay specified in robots.txt.

        Args:
            url: URL to check
            user_agent: User agent string
            session: aiohttp session

        Returns:
            Crawl delay in seconds (returns config default if not specified)
        """
        if not RESPECT_ROBOTS_TXT:
            return RATE_LIMIT_DELAY

        rp = await self.get_robots_parser(url, session)
        if rp is None:
            return RATE_LIMIT_DELAY

        # Get crawl delay for specific user agent
        crawl_delay = rp.crawl_delay(user_agent)
        if crawl_delay is not None:
            logger.debug("Using robots.txt crawl delay", url=url, delay=crawl_delay)
            return float(crawl_delay)

        # Fallback to default
        return RATE_LIMIT_DELAY

    async def enforce_crawl_delay(
        self, url: str, user_agent: str = "*", session: aiohttp.ClientSession | None = None
    ) -> None:
        """Enforce crawl delay by sleeping if necessary.

        Args:
            url: URL being accessed
            user_agent: User agent string
            session: aiohttp session
        """
        parsed_url = urlparse(url)
        domain = f"{parsed_url.scheme}://{parsed_url.netloc}"

        # Get required crawl delay
        crawl_delay = await self.get_crawl_delay(url, user_agent, session)

        # Check when we last accessed this domain
        current_time = asyncio.get_event_loop().time()

        if domain in self._last_request:
            time_since_last = current_time - self._last_request[domain]

            if time_since_last < crawl_delay:
                sleep_time = crawl_delay - time_since_last
                logger.debug(
                    "Enforcing crawl delay", domain=domain, delay=crawl_delay, sleep_time=sleep_time
                )
                await asyncio.sleep(sleep_time)

        # Update last request time
        self._last_request[domain] = asyncio.get_event_loop().time()

    async def check_and_delay(
        self, url: str, user_agent: str = "*", session: aiohttp.ClientSession | None = None
    ) -> None:
        """Check robots.txt permissions and enforce crawl delay.

        Args:
            url: URL to check and delay for
            user_agent: User agent string
            session: aiohttp session

        Raises:
            RateLimitError: If URL is not allowed by robots.txt
        """
        if not await self.can_fetch(url, user_agent, session):
            raise RateLimitError(f"Access to {url} blocked by robots.txt")

        await self.enforce_crawl_delay(url, user_agent, session)

    def clear_cache(self) -> None:
        """Clear the robots.txt cache."""
        self._cache.clear()
        self._last_request.clear()
        logger.info("Cleared robots.txt cache")


# Global instance for reuse
robots_checker = RobotsChecker()
