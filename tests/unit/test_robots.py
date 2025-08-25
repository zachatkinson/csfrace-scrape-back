"""Unit tests for robots.txt handling."""

from unittest.mock import AsyncMock, patch
from urllib.robotparser import RobotFileParser

import pytest

from src.core.config import config
from src.core.exceptions import RateLimitError
from src.utils.robots import RobotsChecker


class TestRobotsChecker:
    """Test cases for robots.txt functionality."""

    @pytest.fixture
    def robots_checker_instance(self):
        """Fresh robots checker instance for each test."""
        return RobotsChecker()

    @pytest.mark.unit
    async def test_robots_parser_caching(
        self, robots_checker_instance: RobotsChecker, mock_session: AsyncMock
    ):
        """Test that robots.txt is cached after first request."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.text.return_value = "User-agent: *\nDisallow: /admin/"
        mock_session.get.return_value.__aenter__.return_value = mock_response

        url = "https://example.com/page"

        # First call should fetch robots.txt
        parser1 = await robots_checker_instance.get_robots_parser(url, mock_session)
        assert mock_session.get.call_count == 1
        assert parser1 is not None

        # Second call should use cache
        parser2 = await robots_checker_instance.get_robots_parser(url, mock_session)
        assert mock_session.get.call_count == 1  # No additional calls
        assert parser2 is parser1  # Same object from cache

    @pytest.mark.unit
    async def test_robots_not_found(
        self, robots_checker_instance: RobotsChecker, mock_session: AsyncMock
    ):
        """Test handling of 404 for robots.txt."""
        mock_response = AsyncMock()
        mock_response.status = 404
        mock_session.get.return_value.__aenter__.return_value = mock_response

        url = "https://example.com/page"

        parser = await robots_checker_instance.get_robots_parser(url, mock_session)
        assert parser is None

        # Should cache the None result
        parser2 = await robots_checker_instance.get_robots_parser(url, mock_session)
        assert mock_session.get.call_count == 1
        assert parser2 is None

    @pytest.mark.unit
    async def test_can_fetch_allowed(
        self, robots_checker_instance: RobotsChecker, mock_session: AsyncMock
    ):
        """Test can_fetch for allowed URLs."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.text.return_value = "User-agent: *\nDisallow: /admin/\nAllow: /public/"
        mock_session.get.return_value.__aenter__.return_value = mock_response

        # Test allowed URL
        can_fetch = await robots_checker_instance.can_fetch(
            "https://example.com/public/page", "*", mock_session
        )
        assert can_fetch is True

        # Test general allowed URL
        can_fetch = await robots_checker_instance.can_fetch(
            "https://example.com/blog/post", "*", mock_session
        )
        assert can_fetch is True

    @pytest.mark.unit
    async def test_can_fetch_disallowed(
        self, robots_checker_instance: RobotsChecker, mock_session: AsyncMock
    ):
        """Test can_fetch for disallowed URLs."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.text.return_value = "User-agent: *\nDisallow: /admin/"
        mock_session.get.return_value.__aenter__.return_value = mock_response

        # Test disallowed URL
        can_fetch = await robots_checker_instance.can_fetch(
            "https://example.com/admin/panel", "*", mock_session
        )
        assert can_fetch is False

    @pytest.mark.unit
    async def test_can_fetch_no_robots(
        self, robots_checker_instance: RobotsChecker, mock_session: AsyncMock
    ):
        """Test can_fetch when no robots.txt exists."""
        mock_response = AsyncMock()
        mock_response.status = 404
        mock_session.get.return_value.__aenter__.return_value = mock_response

        # Should allow everything when no robots.txt
        can_fetch = await robots_checker_instance.can_fetch(
            "https://example.com/anything", "*", mock_session
        )
        assert can_fetch is True

    @pytest.mark.unit
    async def test_get_crawl_delay_specified(
        self, robots_checker_instance: RobotsChecker, mock_session: AsyncMock
    ):
        """Test getting crawl delay when specified in robots.txt."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.text.return_value = "User-agent: *\nCrawl-delay: 5\nDisallow: /admin/"
        mock_session.get.return_value.__aenter__.return_value = mock_response

        delay = await robots_checker_instance.get_crawl_delay(
            "https://example.com/page", "*", mock_session
        )
        assert delay == 5.0

    @pytest.mark.unit
    async def test_get_crawl_delay_default(
        self, robots_checker_instance: RobotsChecker, mock_session: AsyncMock
    ):
        """Test getting default crawl delay when not specified."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.text.return_value = "User-agent: *\nDisallow: /admin/"
        mock_session.get.return_value.__aenter__.return_value = mock_response

        delay = await robots_checker_instance.get_crawl_delay(
            "https://example.com/page", "*", mock_session
        )
        # Should return config default
        assert delay == config.rate_limit_delay

    @pytest.mark.unit
    async def test_get_crawl_delay_no_robots(
        self, robots_checker_instance: RobotsChecker, mock_session: AsyncMock
    ):
        """Test getting crawl delay when no robots.txt exists."""
        mock_response = AsyncMock()
        mock_response.status = 404
        mock_session.get.return_value.__aenter__.return_value = mock_response

        delay = await robots_checker_instance.get_crawl_delay(
            "https://example.com/page", "*", mock_session
        )
        # Should return config default
        assert delay == config.rate_limit_delay

    @pytest.mark.unit
    async def test_enforce_crawl_delay_timing(
        self, robots_checker_instance: RobotsChecker, mock_session: AsyncMock
    ):
        """Test that crawl delay enforcement actually waits."""
        import asyncio

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.text.return_value = "User-agent: *\nCrawl-delay: 1"  # 1 second delay
        mock_session.get.return_value.__aenter__.return_value = mock_response

        url = "https://example.com/page"

        # First request should not wait
        start_time = asyncio.get_event_loop().time()
        await robots_checker_instance.enforce_crawl_delay(url, "*", mock_session)
        first_duration = asyncio.get_event_loop().time() - start_time

        # Should be very quick (no delay for first request)
        assert first_duration < 0.1

        # Second request should wait
        start_time = asyncio.get_event_loop().time()
        await robots_checker_instance.enforce_crawl_delay(url, "*", mock_session)
        second_duration = asyncio.get_event_loop().time() - start_time

        # Should wait approximately 1 second (allow some tolerance)
        assert second_duration >= 0.9
        assert second_duration <= 1.1

    @pytest.mark.unit
    async def test_check_and_delay_blocked(
        self, robots_checker_instance: RobotsChecker, mock_session: AsyncMock
    ):
        """Test that check_and_delay raises exception for blocked URLs."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.text.return_value = "User-agent: *\nDisallow: /blocked/"
        mock_session.get.return_value.__aenter__.return_value = mock_response

        with pytest.raises(RateLimitError, match="blocked by robots.txt"):
            await robots_checker_instance.check_and_delay(
                "https://example.com/blocked/page", "*", mock_session
            )

    @pytest.mark.unit
    async def test_check_and_delay_allowed(
        self, robots_checker_instance: RobotsChecker, mock_session: AsyncMock
    ):
        """Test that check_and_delay succeeds for allowed URLs."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.text.return_value = "User-agent: *\nDisallow: /blocked/"
        mock_session.get.return_value.__aenter__.return_value = mock_response

        # Should not raise an exception
        await robots_checker_instance.check_and_delay(
            "https://example.com/allowed/page", "*", mock_session
        )

    @pytest.mark.unit
    def test_clear_cache(self, robots_checker_instance: RobotsChecker):
        """Test cache clearing functionality."""
        # Add some data to cache
        robots_checker_instance._cache["example.com"] = RobotFileParser()
        robots_checker_instance._last_request["example.com"] = 123456789.0

        robots_checker_instance.clear_cache()

        assert len(robots_checker_instance._cache) == 0
        assert len(robots_checker_instance._last_request) == 0

    @pytest.mark.unit
    async def test_robots_fetch_retry_logic(
        self, robots_checker_instance: RobotsChecker, mock_session: AsyncMock
    ):
        """Test that robots.txt is eventually cached even if network is temporarily unavailable."""
        # Set up a successful response
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.text.return_value = "User-agent: *\nDisallow: /admin/"
        mock_session.get.return_value.__aenter__.return_value = mock_response

        # This should work and cache the result
        parser1 = await robots_checker_instance.get_robots_parser(
            "https://example.com", mock_session
        )
        assert parser1 is not None

        # Reset the session to simulate network failure
        mock_session.reset_mock()
        mock_session.get.side_effect = Exception("Network down")

        # Should still work from cache
        parser2 = await robots_checker_instance.get_robots_parser(
            "https://example.com", mock_session
        )
        assert parser2 is not None
        assert parser2 is parser1  # Same cached instance

        # Should not have called the network again
        assert mock_session.get.call_count == 0

    @pytest.mark.unit
    async def test_user_agent_specific_rules(
        self, robots_checker_instance: RobotsChecker, mock_session: AsyncMock
    ):
        """Test user agent specific robots.txt rules."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.text.return_value = """
User-agent: *
Disallow: /general/
Crawl-delay: 2

User-agent: Googlebot
Disallow: /google-blocked/
Crawl-delay: 1

User-agent: BadBot
Disallow: /
        """
        mock_session.get.return_value.__aenter__.return_value = mock_response

        url = "https://example.com"

        # Test general user agent
        can_fetch_general = await robots_checker_instance.can_fetch(
            f"{url}/general/page", "*", mock_session
        )
        assert can_fetch_general is False

        delay_general = await robots_checker_instance.get_crawl_delay(url, "*", mock_session)
        assert delay_general == 2.0

        # Test Googlebot specific rules
        can_fetch_google = await robots_checker_instance.can_fetch(
            f"{url}/general/page", "Googlebot", mock_session
        )
        assert can_fetch_google is True  # Not blocked for Googlebot

        can_fetch_google_blocked = await robots_checker_instance.can_fetch(
            f"{url}/google-blocked/page", "Googlebot", mock_session
        )
        assert can_fetch_google_blocked is False

        delay_google = await robots_checker_instance.get_crawl_delay(url, "Googlebot", mock_session)
        assert delay_google == 1.0

        # Test completely blocked bot
        can_fetch_badbot = await robots_checker_instance.can_fetch(
            f"{url}/anything", "BadBot", mock_session
        )
        assert can_fetch_badbot is False

    @pytest.mark.unit
    async def test_robots_disabled(
        self, robots_checker_instance: RobotsChecker, mock_session: AsyncMock
    ):
        """Test that robots.txt checking is bypassed when disabled in config."""
        # Mock the config attribute at the module level where it's used
        with patch("src.utils.robots.config") as mock_config:
            mock_config.respect_robots_txt = False
            mock_config.rate_limit_delay = 0.5

            # Should not even attempt to fetch robots.txt
            can_fetch = await robots_checker_instance.can_fetch(
                "https://example.com/anything", "*", mock_session
            )
            assert can_fetch is True
            assert mock_session.get.call_count == 0

            # Should return default delay
            delay = await robots_checker_instance.get_crawl_delay(
                "https://example.com", "*", mock_session
            )
            assert delay == 0.5
            assert mock_session.get.call_count == 0
