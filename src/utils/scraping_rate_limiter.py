"""Scraping-specific rate limiter using token bucket algorithm.

Integrates with robots.txt compliance and provides burst-friendly
rate limiting for external website scraping.
"""

import asyncio

from src.core.decorators import network_error_handler
from src.core.logging_hierarchy import get_scraping_logger

from .rate_limiting.token_bucket import TokenBucket, TokenBucketConfig, TokenBucketPool
from .robots import RobotsChecker

# Type for domain statistics - much better than Any
DomainStats = dict[str, str | int | float | bool]

logger = get_scraping_logger()


class ScrapingRateLimiter:
    """Rate limiter specifically designed for web scraping.

    Combines token bucket algorithm with robots.txt compliance
    to provide respectful and efficient scraping rate limiting.

    Features:
    - Per-domain rate limiting
    - Robots.txt crawl-delay integration
    - Burst traffic handling
    - Adaptive rate adjustment

    Example:
        limiter = ScrapingRateLimiter()

        if await limiter.can_request("example.com"):
            response = await fetch_url("https://example.com/page")
            await limiter.record_request("example.com")
        else:
            wait_time = await limiter.get_wait_time("example.com")
            await asyncio.sleep(wait_time)
    """

    def __init__(
        self,
        default_requests_per_second: float = 1.0,
        default_burst_capacity: int = 5,
        robots_checker: RobotsChecker | None = None,
    ) -> None:
        """Initialize scraping rate limiter.

        Args:
            default_requests_per_second: Default rate when no robots.txt crawl-delay
            default_burst_capacity: Default burst capacity for token bucket
            robots_checker: Optional robots.txt checker (creates if None)
        """
        self.default_requests_per_second = default_requests_per_second
        self.default_burst_capacity = default_burst_capacity
        self.robots_checker = robots_checker or RobotsChecker()

        # Domain-specific configurations
        self._domain_configs: dict[str, TokenBucketConfig] = {}

        # Token bucket pool for all domains
        default_config = TokenBucketConfig(
            capacity=default_burst_capacity,
            refill_rate=default_requests_per_second,
        )
        self._bucket_pool = TokenBucketPool(default_config, max_buckets=1000)

        logger.info(
            "Scraping rate limiter initialized",
            default_rate=default_requests_per_second,
            default_burst=default_burst_capacity,
        )

    async def can_request(self, domain: str, user_agent: str = "*") -> bool:
        """Check if a request can be made to the domain.

        Args:
            domain: Target domain (e.g., "example.com")
            user_agent: User agent for robots.txt checking

        Returns:
            True if request is allowed, False if rate limited
        """
        # First check robots.txt compliance
        if not await self._check_robots_compliance(domain, user_agent):
            logger.debug("Request blocked by robots.txt", domain=domain)
            return False

        # Then check rate limiting
        bucket = await self._get_domain_bucket(domain)
        return await bucket.consume(1)

    async def get_wait_time(self, domain: str, user_agent: str = "*") -> float:
        """Get time to wait before next request to domain.

        Args:
            domain: Target domain
            user_agent: User agent for robots.txt checking

        Returns:
            Seconds to wait before next request
        """
        # Check robots.txt crawl delay
        crawl_delay = await self._get_crawl_delay(domain, user_agent)

        # Check token bucket wait time
        bucket = await self._get_domain_bucket(domain)
        bucket_wait = await bucket.get_wait_time(1)

        # Return the maximum of both constraints
        return max(crawl_delay, bucket_wait)

    async def record_request(self, domain: str) -> None:
        """Record that a request was made to the domain.

        This is mainly for logging and monitoring purposes.
        The actual rate limiting happens in can_request().
        """
        logger.debug("Request recorded", domain=domain)

    async def _get_domain_bucket(self, domain: str) -> TokenBucket:
        """Get or create token bucket for domain."""
        # Use domain-specific config if available, otherwise default
        if domain not in self._domain_configs:
            await self._configure_domain(domain)

        return await self._bucket_pool.get_bucket(domain)

    @network_error_handler("configure domain rate limiting")
    async def _configure_domain(self, domain: str) -> None:
        """Configure rate limiting for a specific domain based on robots.txt."""
        # Get crawl delay from robots.txt
        crawl_delay = await self._get_crawl_delay(domain)

        if crawl_delay > 0:
            # Convert crawl delay to requests per second
            requests_per_second = 1.0 / crawl_delay

            # Adjust burst capacity based on crawl delay
            # Slower sites get smaller burst capacity
            burst_capacity = max(2, min(10, int(self.default_burst_capacity / crawl_delay)))
        else:
            requests_per_second = self.default_requests_per_second
            burst_capacity = self.default_burst_capacity

        config = TokenBucketConfig(
            capacity=burst_capacity,
            refill_rate=requests_per_second,
        )

        self._domain_configs[domain] = config

        logger.info(
            "Configured domain rate limiting",
            domain=domain,
            requests_per_second=requests_per_second,
            burst_capacity=burst_capacity,
            crawl_delay=crawl_delay,
        )

    @network_error_handler("check robots.txt compliance")
    async def _check_robots_compliance(self, domain: str, user_agent: str = "*") -> bool:
        """Check if request complies with robots.txt."""
        return await self.robots_checker.can_fetch(domain, "/", None)

    @network_error_handler("get crawl delay from robots.txt")
    async def _get_crawl_delay(self, domain: str, user_agent: str = "*") -> float:
        """Get crawl delay from robots.txt."""
        return await self.robots_checker.get_crawl_delay(domain, user_agent)

    async def get_domain_stats(self, domain: str) -> DomainStats | None:
        """Get rate limiting statistics for a domain."""
        if domain not in self._domain_configs:
            return None

        config = self._domain_configs[domain]
        bucket = await self._bucket_pool.get_bucket(domain)
        available_tokens = await bucket.get_available_tokens()

        return {
            "domain": domain,
            "capacity": config.capacity,
            "refill_rate": config.refill_rate,
            "available_tokens": available_tokens,
            "requests_per_second": config.refill_rate,
            "burst_capacity": config.capacity,
        }

    async def reset_domain_limits(self, domain: str) -> None:
        """Reset rate limits for a specific domain."""
        await self._bucket_pool.reset_bucket(domain)
        logger.info("Reset rate limits", domain=domain)

    async def get_all_domain_stats(self) -> dict[str, DomainStats]:
        """Get statistics for all configured domains."""
        stats = {}

        for domain in self._domain_configs:
            domain_stats = await self.get_domain_stats(domain)
            if domain_stats:
                stats[domain] = domain_stats

        return stats


# Global instance for convenient access
_scraping_rate_limiter: ScrapingRateLimiter | None = None


def get_scraping_rate_limiter() -> ScrapingRateLimiter:
    """Get global scraping rate limiter instance."""
    global _scraping_rate_limiter

    if _scraping_rate_limiter is None:
        _scraping_rate_limiter = ScrapingRateLimiter()

    return _scraping_rate_limiter


async def wait_for_rate_limit(domain: str, user_agent: str = "*") -> None:
    """Convenience function to wait for rate limit compliance.

    Args:
        domain: Target domain
        user_agent: User agent string
    """
    limiter = get_scraping_rate_limiter()
    wait_time = await limiter.get_wait_time(domain, user_agent)

    if wait_time > 0:
        logger.debug("Waiting for rate limit", domain=domain, wait_time=wait_time)
        await asyncio.sleep(wait_time)
