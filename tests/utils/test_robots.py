"""Tests for robots.txt utilities following DRY/SOLID principles."""

from unittest.mock import AsyncMock, Mock, patch
from urllib.robotparser import RobotFileParser

import aiohttp
import pytest

from src.core.exceptions import RateLimitError
from src.utils.robots import RobotsChecker, robots_checker


class TestRobotsChecker:
    """Test RobotsChecker functionality following SOLID principles."""

    def setup_method(self):
        """Set up test fixtures."""
        self.checker = RobotsChecker()
        self.mock_session = AsyncMock(spec=aiohttp.ClientSession)

    def test_robots_checker_initialization(self):
        """Test robots checker initialization."""
        checker = RobotsChecker()

        assert isinstance(checker._cache, dict)
        assert isinstance(checker._last_request, dict)
        assert len(checker._cache) == 0
        assert len(checker._last_request) == 0

    @pytest.mark.asyncio
    async def test_get_robots_parser_no_session(self):
        """Test robots parser retrieval without session."""
        result = await self.checker.get_robots_parser("https://example.com", None)

        assert result is None

    @pytest.mark.asyncio
    async def test_get_robots_parser_successful_fetch(self):
        """Test successful robots.txt fetching and parsing."""
        robots_content = b"""User-agent: *
Disallow: /private/
Crawl-delay: 1

User-agent: Googlebot
Disallow: /admin/
"""

        # Mock the HTTP response
        mock_response = Mock()
        mock_response.status = 200
        mock_response.content = robots_content

        with patch("src.utils.robots.safe_http_get", return_value=mock_response):
            result = await self.checker.get_robots_parser("https://example.com", self.mock_session)

        assert isinstance(result, RobotFileParser)
        assert result is not None

        # Test that the parser was configured correctly
        assert result.can_fetch("*", "https://example.com/public/") is True
        assert result.can_fetch("*", "https://example.com/private/") is False

    @pytest.mark.asyncio
    async def test_get_robots_parser_not_found(self):
        """Test robots.txt not found scenario."""
        mock_response = Mock()
        mock_response.status = 404

        with patch("src.utils.robots.safe_http_get", return_value=mock_response):
            result = await self.checker.get_robots_parser("https://example.com", self.mock_session)

        assert result is None

    @pytest.mark.asyncio
    async def test_get_robots_parser_caching(self):
        """Test that robots.txt responses are cached."""
        robots_content = b"User-agent: *\nDisallow: /test/"

        mock_response = Mock()
        mock_response.status = 200
        mock_response.content = robots_content

        with patch("src.utils.robots.safe_http_get", return_value=mock_response) as mock_get:
            # First call
            result1 = await self.checker.get_robots_parser("https://example.com", self.mock_session)
            # Second call
            result2 = await self.checker.get_robots_parser("https://example.com", self.mock_session)

            # Should only make one HTTP request due to caching
            assert mock_get.call_count == 1
            assert result1 is result2

    @pytest.mark.asyncio
    async def test_get_robots_parser_http_error(self):
        """Test robots.txt fetching with HTTP error."""
        with patch(
            "src.utils.robots.safe_http_get", side_effect=aiohttp.ClientError("Connection failed")
        ):
            result = await self.checker.get_robots_parser("https://example.com", self.mock_session)

        assert result is None

    @pytest.mark.asyncio
    async def test_get_robots_parser_timeout_error(self):
        """Test robots.txt fetching with timeout error."""
        with patch("src.utils.robots.safe_http_get", side_effect=TimeoutError("Request timed out")):
            result = await self.checker.get_robots_parser("https://example.com", self.mock_session)

        assert result is None

    @pytest.mark.asyncio
    async def test_get_robots_parser_cache_failure(self):
        """Test that failed robots.txt fetches are also cached."""
        with patch(
            "src.utils.robots.safe_http_get", side_effect=aiohttp.ClientError("Error")
        ) as mock_get:
            # First call - should make HTTP request
            result1 = await self.checker.get_robots_parser("https://example.com", self.mock_session)
            # Second call - should use cached None result
            result2 = await self.checker.get_robots_parser("https://example.com", self.mock_session)

            # Should make 3 HTTP requests due to retry logic (stop_after_attempt(3))
            assert mock_get.call_count == 3
            assert result1 is None
            assert result2 is None

    @pytest.mark.asyncio
    async def test_can_fetch_robots_disabled(self):
        """Test can_fetch when robots.txt respect is disabled."""
        with patch("src.utils.robots.config") as mock_config:
            mock_config.robots.respect_robots_txt = False
            result = await self.checker.can_fetch("https://example.com/any/path")

        assert result is True

    @pytest.mark.asyncio
    async def test_can_fetch_no_robots_file(self):
        """Test can_fetch when no robots.txt exists."""
        with patch.object(self.checker, "get_robots_parser", return_value=None):
            result = await self.checker.can_fetch(
                "https://example.com/path", session=self.mock_session
            )

        assert result is True

    @pytest.mark.asyncio
    async def test_can_fetch_allowed_by_robots(self):
        """Test can_fetch when URL is allowed by robots.txt."""
        mock_parser = Mock(spec=RobotFileParser)
        mock_parser.can_fetch.return_value = True

        with patch.object(self.checker, "get_robots_parser", return_value=mock_parser):
            result = await self.checker.can_fetch(
                "https://example.com/allowed", session=self.mock_session
            )

        assert result is True
        mock_parser.can_fetch.assert_called_once_with("*", "https://example.com/allowed")

    @pytest.mark.asyncio
    async def test_can_fetch_blocked_by_robots(self):
        """Test can_fetch when URL is blocked by robots.txt."""
        mock_parser = Mock(spec=RobotFileParser)
        mock_parser.can_fetch.return_value = False

        with patch.object(self.checker, "get_robots_parser", return_value=mock_parser):
            result = await self.checker.can_fetch(
                "https://example.com/blocked", session=self.mock_session
            )

        assert result is False

    @pytest.mark.asyncio
    async def test_can_fetch_custom_user_agent(self):
        """Test can_fetch with custom user agent."""
        mock_parser = Mock(spec=RobotFileParser)
        mock_parser.can_fetch.return_value = True

        with patch.object(self.checker, "get_robots_parser", return_value=mock_parser):
            result = await self.checker.can_fetch(
                "https://example.com/path", user_agent="CustomBot/1.0", session=self.mock_session
            )

        assert result is True
        mock_parser.can_fetch.assert_called_once_with("CustomBot/1.0", "https://example.com/path")

    @pytest.mark.asyncio
    async def test_can_fetch_error_handling(self):
        """Test can_fetch error handling defaults to allowing."""
        with patch.object(self.checker, "get_robots_parser", side_effect=ValueError("Parse error")):
            result = await self.checker.can_fetch(
                "https://example.com/path", session=self.mock_session
            )

        assert result is True

    @pytest.mark.asyncio
    async def test_get_crawl_delay_robots_disabled(self):
        """Test get_crawl_delay when robots.txt respect is disabled."""
        with patch("src.utils.robots.config") as mock_config:
            mock_config.robots.respect_robots_txt = False
            mock_config.http.rate_limit_delay = 2.0
            delay = await self.checker.get_crawl_delay("https://example.com")

        assert delay == 2.0

    @pytest.mark.asyncio
    async def test_get_crawl_delay_no_robots_file(self):
        """Test get_crawl_delay when no robots.txt exists."""
        with patch.object(self.checker, "get_robots_parser", return_value=None):
            with patch("src.utils.robots.config") as mock_config:
                mock_config.http.rate_limit_delay = 1.5
                delay = await self.checker.get_crawl_delay(
                    "https://example.com", session=self.mock_session
                )

        assert delay == 1.5

    @pytest.mark.asyncio
    async def test_get_crawl_delay_from_robots(self):
        """Test get_crawl_delay when specified in robots.txt."""
        mock_parser = Mock(spec=RobotFileParser)
        mock_parser.crawl_delay.return_value = 3.0

        with patch.object(self.checker, "get_robots_parser", return_value=mock_parser):
            delay = await self.checker.get_crawl_delay(
                "https://example.com", session=self.mock_session
            )

        assert delay == 3.0
        mock_parser.crawl_delay.assert_called_once_with("*")

    @pytest.mark.asyncio
    async def test_get_crawl_delay_none_in_robots(self):
        """Test get_crawl_delay when not specified in robots.txt."""
        mock_parser = Mock(spec=RobotFileParser)
        mock_parser.crawl_delay.return_value = None

        with patch.object(self.checker, "get_robots_parser", return_value=mock_parser):
            with patch("src.utils.robots.config") as mock_config:
                mock_config.http.rate_limit_delay = 1.0
                delay = await self.checker.get_crawl_delay(
                    "https://example.com", session=self.mock_session
                )

        assert delay == 1.0

    @pytest.mark.asyncio
    async def test_get_crawl_delay_custom_user_agent(self):
        """Test get_crawl_delay with custom user agent."""
        mock_parser = Mock(spec=RobotFileParser)
        mock_parser.crawl_delay.return_value = 5.0

        with patch.object(self.checker, "get_robots_parser", return_value=mock_parser):
            delay = await self.checker.get_crawl_delay(
                "https://example.com", user_agent="MyBot/2.0", session=self.mock_session
            )

        assert delay == 5.0
        mock_parser.crawl_delay.assert_called_once_with("MyBot/2.0")

    @pytest.mark.asyncio
    async def test_get_crawl_delay_error_handling(self):
        """Test get_crawl_delay error handling returns default."""
        with patch.object(
            self.checker, "get_robots_parser", side_effect=aiohttp.ClientError("Error")
        ):
            with patch("src.utils.robots.config") as mock_config:
                mock_config.http.rate_limit_delay = 2.5
                delay = await self.checker.get_crawl_delay(
                    "https://example.com", session=self.mock_session
                )

        assert delay == 2.5


class TestCheckAndDelay:
    """Test combined check and delay functionality following DRY principles."""

    def setup_method(self):
        """Set up test fixtures."""
        self.checker = RobotsChecker()
        self.mock_session = AsyncMock(spec=aiohttp.ClientSession)

    @pytest.mark.asyncio
    async def test_check_and_delay_allowed_url(self):
        """Test check_and_delay with allowed URL."""
        with patch.object(self.checker, "can_fetch", return_value=True):
            with patch.object(self.checker, "enforce_crawl_delay") as mock_delay:
                await self.checker.check_and_delay(
                    "https://example.com/allowed", session=self.mock_session
                )

        mock_delay.assert_called_once_with("https://example.com/allowed", "*", self.mock_session)

    @pytest.mark.asyncio
    async def test_check_and_delay_blocked_url(self):
        """Test check_and_delay with blocked URL."""
        with patch.object(self.checker, "can_fetch", return_value=False):
            with pytest.raises(RateLimitError, match="Access to .* blocked by robots.txt"):
                await self.checker.check_and_delay(
                    "https://example.com/blocked", session=self.mock_session
                )

    @pytest.mark.asyncio
    async def test_check_and_delay_custom_user_agent(self):
        """Test check_and_delay with custom user agent."""
        with patch.object(self.checker, "can_fetch", return_value=True) as mock_can_fetch:
            with patch.object(self.checker, "enforce_crawl_delay") as mock_delay:
                await self.checker.check_and_delay(
                    "https://example.com/path", user_agent="TestBot/1.0", session=self.mock_session
                )

        mock_can_fetch.assert_called_once_with(
            "https://example.com/path", "TestBot/1.0", self.mock_session
        )
        mock_delay.assert_called_once_with(
            "https://example.com/path", "TestBot/1.0", self.mock_session
        )

    def test_clear_cache(self):
        """Test clearing robots cache."""
        # Add some test data to cache
        self.checker._cache["https://example.com"] = Mock()
        self.checker._last_request["https://example.com"] = 1000.0

        assert len(self.checker._cache) > 0
        assert len(self.checker._last_request) > 0

        self.checker.clear_cache()

        assert len(self.checker._cache) == 0
        assert len(self.checker._last_request) == 0


class TestGlobalRobotsInstance:
    """Test the global robots_checker instance following DRY principles."""

    def test_global_robots_checker_exists(self):
        """Test that global robots_checker instance exists."""
        assert robots_checker is not None
        assert isinstance(robots_checker, RobotsChecker)

    def test_global_robots_checker_is_singleton(self):
        """Test that the global instance behaves like a singleton."""
        # Import should return the same instance
        from src.utils.robots import robots_checker as imported_checker

        assert imported_checker is robots_checker

    @pytest.mark.asyncio
    async def test_global_robots_checker_functionality(self):
        """Test that global instance functions correctly."""
        # Should be able to use the global instance
        with patch("src.utils.robots.config") as mock_config:
            mock_config.robots.respect_robots_txt = False
            result = await robots_checker.can_fetch("https://example.com/test")

        assert result is True


class TestRobotsEdgeCases:
    """Test edge cases and error conditions following modern testing practices."""

    def setup_method(self):
        """Set up test fixtures."""
        self.checker = RobotsChecker()
        self.mock_session = AsyncMock(spec=aiohttp.ClientSession)

    @pytest.mark.asyncio
    async def test_robots_empty_content(self):
        """Test handling of empty robots.txt content."""
        mock_response = Mock()
        mock_response.status = 200
        mock_response.content = b""

        with patch("src.utils.robots.safe_http_get", return_value=mock_response):
            result = await self.checker.get_robots_parser("https://example.com", self.mock_session)

        # Should return a valid parser even for empty content
        assert isinstance(result, RobotFileParser)

    @pytest.mark.asyncio
    async def test_robots_very_large_content(self):
        """Test handling of very large robots.txt content."""
        # Create large robots.txt content
        large_content = b"User-agent: *\n" + b"Disallow: /path" + b"x" * 10000 + b"/\n"

        mock_response = Mock()
        mock_response.status = 200
        mock_response.content = large_content

        with patch("src.utils.robots.safe_http_get", return_value=mock_response):
            result = await self.checker.get_robots_parser("https://example.com", self.mock_session)

        # Should handle large content without issues
        assert isinstance(result, RobotFileParser)

    @pytest.mark.asyncio
    async def test_robots_url_with_port(self):
        """Test robots.txt handling for URLs with non-standard ports."""
        robots_content = b"User-agent: *\nDisallow: /admin/"

        mock_response = Mock()
        mock_response.status = 200
        mock_response.content = robots_content

        with patch("src.utils.robots.safe_http_get", return_value=mock_response):
            result = await self.checker.get_robots_parser(
                "https://example.com:8080", self.mock_session
            )

        assert isinstance(result, RobotFileParser)

        # Cache should be separate for different ports
        expected_url = "https://example.com:8080"
        cache_keys = list(self.checker._cache.keys())
        assert expected_url in cache_keys

    @pytest.mark.asyncio
    async def test_robots_international_domain(self):
        """Test robots.txt handling for international domain names."""
        robots_content = b"User-agent: *\nDisallow: /test/"

        mock_response = Mock()
        mock_response.status = 200
        mock_response.content = robots_content

        with patch("src.utils.robots.safe_http_get", return_value=mock_response):
            # Test with international domain
            result = await self.checker.get_robots_parser(
                "https://тест.example.com", self.mock_session
            )

        assert isinstance(result, RobotFileParser)
