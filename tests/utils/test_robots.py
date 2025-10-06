"""Comprehensive tests for robots.txt parsing - MANDATORY TEST_BUILDING.md compliance.

This module tests robots.txt compliance with complete coverage:
- RobotFileParser integration
- URL permission checking
- Crawl delay enforcement
- Domain caching mechanisms
- Error handling and fallbacks
- Performance benchmarks

ALL tests follow MANDATORY TEST_BUILDING.md patterns:
- AAA pattern with explicit comments
- Factory fixtures for DRY principle
- Comprehensive robots.txt scenario testing
- Performance benchmarks with specific thresholds
"""

import time
from unittest.mock import AsyncMock, MagicMock, patch
from urllib.robotparser import RobotFileParser

import aiohttp
import pytest

from src.core.exceptions import RateLimitError
from src.utils.http import HTTPResponse
from src.utils.robots import RobotsChecker, robots_checker

# ============================================================================
# Test Fixtures - DRY Principle
# ============================================================================


@pytest.fixture
def robots_checker_instance() -> RobotsChecker:
    """Factory for fresh RobotsChecker instance - DRY principle."""
    return RobotsChecker()


@pytest.fixture
def mock_session() -> AsyncMock:
    """Factory for mock aiohttp ClientSession - DRY principle."""
    return AsyncMock(spec=aiohttp.ClientSession)


@pytest.fixture
def test_url() -> str:
    """Factory for test URL - DRY principle."""
    return "https://example.com/page"


@pytest.fixture
def robots_txt_content_allow_all() -> str:
    """Factory for permissive robots.txt - DRY principle."""
    return """User-agent: *
Allow: /
"""


@pytest.fixture
def robots_txt_content_disallow_all() -> str:
    """Factory for restrictive robots.txt - DRY principle."""
    return """User-agent: *
Disallow: /
"""


@pytest.fixture
def robots_txt_content_with_crawl_delay() -> str:
    """Factory for robots.txt with crawl delay - DRY principle."""
    return """User-agent: *
Crawl-delay: 5
Allow: /
"""


@pytest.fixture
def robots_txt_content_selective() -> str:
    """Factory for selective robots.txt - DRY principle."""
    return """User-agent: *
Allow: /public/
Disallow: /private/
Crawl-delay: 2
"""


# ============================================================================
# RobotsChecker Initialization Tests
# ============================================================================


@pytest.mark.unit
class TestRobotsCheckerInit:
    """Tests for RobotsChecker initialization."""

    def test_robots_checker_initialization(self, robots_checker_instance: RobotsChecker) -> None:
        """Test RobotsChecker initializes with empty caches - MANDATORY AAA pattern."""
        # Arrange - MANDATORY (done by fixture)

        # Act - MANDATORY (initialization happens in fixture)

        # Assert - MANDATORY
        assert robots_checker_instance._cache == {}
        assert robots_checker_instance._last_request == {}


# ============================================================================
# get_robots_parser Tests
# ============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
class TestGetRobotsParser:
    """Tests for get_robots_parser method."""

    async def test_get_robots_parser_successful_fetch(
        self,
        robots_checker_instance: RobotsChecker,
        mock_session: AsyncMock,
        test_url: str,
        robots_txt_content_allow_all: str,
    ) -> None:
        """Test get_robots_parser with successful fetch - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        mock_response = HTTPResponse(status=200, content=robots_txt_content_allow_all)
        with patch("src.utils.robots.safe_http_get", return_value=mock_response):
            # Act - MANDATORY
            result = await robots_checker_instance.get_robots_parser(test_url, mock_session)

            # Assert - MANDATORY
            assert result is not None
            assert isinstance(result, RobotFileParser)
            assert "https://example.com" in robots_checker_instance._cache

    async def test_get_robots_parser_404_not_found(
        self, robots_checker_instance: RobotsChecker, mock_session: AsyncMock, test_url: str
    ) -> None:
        """Test get_robots_parser with 404 Not Found - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        mock_response = HTTPResponse(status=404, content="")
        with patch("src.utils.robots.safe_http_get", return_value=mock_response):
            # Act - MANDATORY
            result = await robots_checker_instance.get_robots_parser(test_url, mock_session)

            # Assert - MANDATORY
            assert result is None
            assert "https://example.com" in robots_checker_instance._cache
            assert robots_checker_instance._cache["https://example.com"] is None

    async def test_get_robots_parser_caching(
        self,
        robots_checker_instance: RobotsChecker,
        mock_session: AsyncMock,
        test_url: str,
        robots_txt_content_allow_all: str,
    ) -> None:
        """Test get_robots_parser uses cache - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        mock_response = HTTPResponse(status=200, content=robots_txt_content_allow_all)
        with patch("src.utils.robots.safe_http_get", return_value=mock_response) as mock_get:
            # Act - MANDATORY
            # First call
            result1 = await robots_checker_instance.get_robots_parser(test_url, mock_session)
            # Second call should use cache
            result2 = await robots_checker_instance.get_robots_parser(test_url, mock_session)

            # Assert - MANDATORY
            assert result1 is not None
            assert result2 is not None
            assert result1 is result2  # Same cached instance
            assert mock_get.call_count == 1  # Only called once

    async def test_get_robots_parser_no_session(
        self, robots_checker_instance: RobotsChecker, test_url: str
    ) -> None:
        """Test get_robots_parser with no session - MANDATORY AAA pattern."""
        # Arrange - MANDATORY (no session provided)

        # Act - MANDATORY
        result = await robots_checker_instance.get_robots_parser(test_url, None)

        # Assert - MANDATORY
        assert result is None

    async def test_get_robots_parser_handles_exception(
        self, robots_checker_instance: RobotsChecker, mock_session: AsyncMock, test_url: str
    ) -> None:
        """Test get_robots_parser handles fetch exception - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        with patch("src.utils.robots.safe_http_get", side_effect=Exception("Network error")):
            # Act - MANDATORY
            result = await robots_checker_instance.get_robots_parser(test_url, mock_session)

            # Assert - MANDATORY
            assert result is None
            assert "https://example.com" in robots_checker_instance._cache


# ============================================================================
# can_fetch Tests
# ============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
class TestCanFetch:
    """Tests for can_fetch method."""

    async def test_can_fetch_allowed_url(
        self,
        robots_checker_instance: RobotsChecker,
        mock_session: AsyncMock,
        robots_txt_content_allow_all: str,
    ) -> None:
        """Test can_fetch with allowed URL - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        test_url = "https://example.com/allowed"
        mock_response = HTTPResponse(status=200, content=robots_txt_content_allow_all)
        with patch("src.utils.robots.safe_http_get", return_value=mock_response):
            # Act - MANDATORY
            result = await robots_checker_instance.can_fetch(test_url, "*", mock_session)

            # Assert - MANDATORY
            assert result is True

    async def test_can_fetch_disallowed_url(
        self,
        robots_checker_instance: RobotsChecker,
        mock_session: AsyncMock,
        robots_txt_content_disallow_all: str,
    ) -> None:
        """Test can_fetch with disallowed URL - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        test_url = "https://example.com/blocked"
        mock_response = HTTPResponse(status=200, content=robots_txt_content_disallow_all)
        with patch("src.utils.robots.safe_http_get", return_value=mock_response):
            # Act - MANDATORY
            result = await robots_checker_instance.can_fetch(test_url, "*", mock_session)

            # Assert - MANDATORY
            assert result is False

    async def test_can_fetch_selective_permissions(
        self,
        robots_checker_instance: RobotsChecker,
        mock_session: AsyncMock,
        robots_txt_content_selective: str,
    ) -> None:
        """Test can_fetch with selective permissions - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        mock_response = HTTPResponse(status=200, content=robots_txt_content_selective)
        with patch("src.utils.robots.safe_http_get", return_value=mock_response):
            # Act & Assert - MANDATORY
            public_url = "https://example.com/public/page"
            private_url = "https://example.com/private/page"

            public_result = await robots_checker_instance.can_fetch(public_url, "*", mock_session)
            private_result = await robots_checker_instance.can_fetch(private_url, "*", mock_session)

            assert public_result is True
            assert private_result is False

    async def test_can_fetch_no_robots_txt(
        self, robots_checker_instance: RobotsChecker, mock_session: AsyncMock
    ) -> None:
        """Test can_fetch with no robots.txt - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        test_url = "https://example.com/page"
        mock_response = HTTPResponse(status=404, content="")
        with patch("src.utils.robots.safe_http_get", return_value=mock_response):
            # Act - MANDATORY
            result = await robots_checker_instance.can_fetch(test_url, "*", mock_session)

            # Assert - MANDATORY
            assert result is True  # No robots.txt means allow all

    @patch("src.utils.robots.RESPECT_ROBOTS_TXT", False)
    async def test_can_fetch_respect_disabled(
        self, robots_checker_instance: RobotsChecker, mock_session: AsyncMock
    ) -> None:
        """Test can_fetch with respect disabled - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        test_url = "https://example.com/page"

        # Act - MANDATORY
        result = await robots_checker_instance.can_fetch(test_url, "*", mock_session)

        # Assert - MANDATORY
        assert result is True  # Should allow all when respect is disabled


# ============================================================================
# get_crawl_delay Tests
# ============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
class TestGetCrawlDelay:
    """Tests for get_crawl_delay method."""

    async def test_get_crawl_delay_from_robots_txt(
        self,
        robots_checker_instance: RobotsChecker,
        mock_session: AsyncMock,
        robots_txt_content_with_crawl_delay: str,
    ) -> None:
        """Test get_crawl_delay from robots.txt - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        test_url = "https://example.com/page"
        mock_response = HTTPResponse(status=200, content=robots_txt_content_with_crawl_delay)
        with patch("src.utils.robots.safe_http_get", return_value=mock_response):
            # Act - MANDATORY
            result = await robots_checker_instance.get_crawl_delay(test_url, "*", mock_session)

            # Assert - MANDATORY
            assert result == 5.0

    async def test_get_crawl_delay_default_when_not_specified(
        self,
        robots_checker_instance: RobotsChecker,
        mock_session: AsyncMock,
        robots_txt_content_allow_all: str,
    ) -> None:
        """Test get_crawl_delay returns default when not specified - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        test_url = "https://example.com/page"
        mock_response = HTTPResponse(status=200, content=robots_txt_content_allow_all)
        with patch("src.utils.robots.safe_http_get", return_value=mock_response):
            with patch("src.utils.robots.RATE_LIMIT_DELAY", 1.0):
                # Act - MANDATORY
                result = await robots_checker_instance.get_crawl_delay(test_url, "*", mock_session)

                # Assert - MANDATORY
                assert result == 1.0

    async def test_get_crawl_delay_no_robots_txt(
        self, robots_checker_instance: RobotsChecker, mock_session: AsyncMock
    ) -> None:
        """Test get_crawl_delay with no robots.txt - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        test_url = "https://example.com/page"
        mock_response = HTTPResponse(status=404, content="")
        with patch("src.utils.robots.safe_http_get", return_value=mock_response):
            with patch("src.utils.robots.RATE_LIMIT_DELAY", 1.0):
                # Act - MANDATORY
                result = await robots_checker_instance.get_crawl_delay(test_url, "*", mock_session)

                # Assert - MANDATORY
                assert result == 1.0

    @patch("src.utils.robots.RESPECT_ROBOTS_TXT", False)
    async def test_get_crawl_delay_respect_disabled(
        self, robots_checker_instance: RobotsChecker, mock_session: AsyncMock
    ) -> None:
        """Test get_crawl_delay with respect disabled - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        test_url = "https://example.com/page"
        with patch("src.utils.robots.RATE_LIMIT_DELAY", 1.0):
            # Act - MANDATORY
            result = await robots_checker_instance.get_crawl_delay(test_url, "*", mock_session)

            # Assert - MANDATORY
            assert result == 1.0


# ============================================================================
# enforce_crawl_delay Tests
# ============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
class TestEnforceCrawlDelay:
    """Tests for enforce_crawl_delay method."""

    async def test_enforce_crawl_delay_first_request(
        self, robots_checker_instance: RobotsChecker, mock_session: AsyncMock
    ) -> None:
        """Test enforce_crawl_delay for first request - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        test_url = "https://example.com/page"
        with patch.object(
            robots_checker_instance, "get_crawl_delay", return_value=1.0
        ) as mock_delay:
            # Act - MANDATORY
            start_time = time.time()
            await robots_checker_instance.enforce_crawl_delay(test_url, "*", mock_session)
            elapsed = time.time() - start_time

            # Assert - MANDATORY
            assert elapsed < 0.1  # Should not sleep for first request
            assert "https://example.com" in robots_checker_instance._last_request

    async def test_enforce_crawl_delay_enforces_delay(
        self, robots_checker_instance: RobotsChecker, mock_session: AsyncMock
    ) -> None:
        """Test enforce_crawl_delay enforces delay - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        test_url = "https://example.com/page"
        crawl_delay = 0.2
        with patch.object(
            robots_checker_instance, "get_crawl_delay", return_value=crawl_delay
        ) as mock_delay:
            # Act - MANDATORY
            # First request
            await robots_checker_instance.enforce_crawl_delay(test_url, "*", mock_session)

            # Second request immediately after
            start_time = time.time()
            await robots_checker_instance.enforce_crawl_delay(test_url, "*", mock_session)
            elapsed = time.time() - start_time

            # Assert - MANDATORY
            assert elapsed >= crawl_delay * 0.9  # Allow 10% margin

    async def test_enforce_crawl_delay_multiple_domains(
        self, robots_checker_instance: RobotsChecker, mock_session: AsyncMock
    ) -> None:
        """Test enforce_crawl_delay tracks multiple domains - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        url1 = "https://example.com/page"
        url2 = "https://different.com/page"
        with patch.object(robots_checker_instance, "get_crawl_delay", return_value=0.1):
            # Act - MANDATORY
            await robots_checker_instance.enforce_crawl_delay(url1, "*", mock_session)
            await robots_checker_instance.enforce_crawl_delay(url2, "*", mock_session)

            # Assert - MANDATORY
            assert "https://example.com" in robots_checker_instance._last_request
            assert "https://different.com" in robots_checker_instance._last_request


# ============================================================================
# check_and_delay Tests
# ============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
class TestCheckAndDelay:
    """Tests for check_and_delay method."""

    async def test_check_and_delay_allowed_url(
        self, robots_checker_instance: RobotsChecker, mock_session: AsyncMock
    ) -> None:
        """Test check_and_delay with allowed URL - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        test_url = "https://example.com/page"
        with patch.object(
            robots_checker_instance, "can_fetch", return_value=True
        ) as mock_can_fetch:
            with patch.object(robots_checker_instance, "enforce_crawl_delay") as mock_enforce:
                # Act - MANDATORY
                await robots_checker_instance.check_and_delay(test_url, "*", mock_session)

                # Assert - MANDATORY
                mock_can_fetch.assert_called_once()
                mock_enforce.assert_called_once()

    async def test_check_and_delay_disallowed_url(
        self, robots_checker_instance: RobotsChecker, mock_session: AsyncMock
    ) -> None:
        """Test check_and_delay with disallowed URL - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        test_url = "https://example.com/blocked"
        with patch.object(robots_checker_instance, "can_fetch", return_value=False):
            # Act & Assert - MANDATORY
            with pytest.raises(RateLimitError, match="blocked by robots.txt"):
                await robots_checker_instance.check_and_delay(test_url, "*", mock_session)


# ============================================================================
# clear_cache Tests
# ============================================================================


@pytest.mark.unit
class TestClearCache:
    """Tests for clear_cache method."""

    def test_clear_cache_empties_all_caches(self, robots_checker_instance: RobotsChecker) -> None:
        """Test clear_cache empties all caches - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        robots_checker_instance._cache["https://example.com"] = MagicMock()
        robots_checker_instance._last_request["https://example.com"] = 12345.0

        # Act - MANDATORY
        robots_checker_instance.clear_cache()

        # Assert - MANDATORY
        assert robots_checker_instance._cache == {}
        assert robots_checker_instance._last_request == {}


# ============================================================================
# Global Instance Tests
# ============================================================================


@pytest.mark.unit
class TestGlobalInstance:
    """Tests for global robots_checker instance."""

    def test_global_robots_checker_exists(self) -> None:
        """Test global robots_checker instance exists - MANDATORY AAA pattern."""
        # Arrange - MANDATORY (global import)

        # Act - MANDATORY
        instance = robots_checker

        # Assert - MANDATORY
        assert instance is not None
        assert isinstance(instance, RobotsChecker)


# ============================================================================
# MANDATORY Performance Benchmarks
# ============================================================================


@pytest.mark.performance
@pytest.mark.unit
class TestRobotsPerformance:
    """MANDATORY performance tests for robots.txt utilities."""

    def test_robots_checker_initialization_performance(self) -> None:
        """MANDATORY performance test - RobotsChecker initialization speed."""
        # Arrange - MANDATORY
        iterations = 10000

        # Act - MANDATORY
        start_time = time.perf_counter()

        for _ in range(iterations):
            RobotsChecker()

        end_time = time.perf_counter()
        execution_time = end_time - start_time

        # Assert - MANDATORY
        avg_time = execution_time / iterations
        assert avg_time < 0.0001  # <0.1ms per initialization
        assert execution_time < 1.0  # Total <1s for 10000 initializations

    @pytest.mark.asyncio
    async def test_can_fetch_cache_hit_performance(self, mock_session: AsyncMock) -> None:
        """MANDATORY performance test - can_fetch cache performance."""
        # Arrange - MANDATORY
        checker = RobotsChecker()
        test_url = "https://example.com/page"
        mock_response = HTTPResponse(status=200, content="User-agent: *\nAllow: /\n")

        with patch("src.utils.robots.safe_http_get", return_value=mock_response):
            # Prime the cache
            await checker.can_fetch(test_url, "*", mock_session)

            iterations = 1000

            # Act - MANDATORY
            start_time = time.perf_counter()

            for _ in range(iterations):
                await checker.can_fetch(test_url, "*", mock_session)

            end_time = time.perf_counter()
            execution_time = end_time - start_time

            # Assert - MANDATORY
            avg_time = execution_time / iterations
            assert avg_time < 0.001  # <1ms per cached check
            assert execution_time < 1.0  # Total <1s for 1000 checks

    def test_clear_cache_performance(self) -> None:
        """MANDATORY performance test - cache clearing speed."""
        # Arrange - MANDATORY
        checker = RobotsChecker()
        # Add many cache entries
        for i in range(100):
            checker._cache[f"https://example{i}.com"] = MagicMock()
            checker._last_request[f"https://example{i}.com"] = float(i)

        iterations = 1000

        # Act - MANDATORY
        start_time = time.perf_counter()

        for _ in range(iterations):
            # Repopulate before each clear
            for i in range(100):
                checker._cache[f"https://example{i}.com"] = MagicMock()
                checker._last_request[f"https://example{i}.com"] = float(i)
            checker.clear_cache()

        end_time = time.perf_counter()
        execution_time = end_time - start_time

        # Assert - MANDATORY
        avg_time = execution_time / iterations
        assert (
            avg_time < 0.02
        )  # <20ms per clear operation (relaxed for CI variability with logging overhead)
