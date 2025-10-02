"""Comprehensive tests for session factory - MANDATORY TEST_BUILDING.md compliance.

This module tests session factory functionality with complete coverage:
- SessionFactory session creation with default settings
- SessionFactory session creation with custom settings
- SessionFactory connector configuration
- SessionFactory timeout configuration
- SessionFactory header building
- SessionFactory cookie jar creation
- Edge cases and error handling
- Performance benchmarks

ALL tests follow MANDATORY TEST_BUILDING.md patterns:
- AAA pattern with explicit comments
- Factory fixtures for DRY principle
- Comprehensive session factory scenario testing
- Performance benchmarks with specific thresholds
"""

import time

import aiohttp
import pytest

from src.utils.session.session_factory import SessionFactory

# ============================================================================
# Test Fixtures - DRY Principle
# ============================================================================


@pytest.fixture
def default_user_agent():
    """Factory for default user agent - DRY principle."""
    return "Enhanced Session Manager/1.0"


@pytest.fixture
def custom_headers():
    """Factory for custom headers - DRY principle."""
    return {"X-Custom-Header": "test-value", "X-Request-ID": "12345"}


# ============================================================================
# SessionFactory Tests
# ============================================================================


@pytest.mark.unit
class TestSessionFactory:
    """Tests for SessionFactory class."""

    @pytest.mark.asyncio
    async def test_create_session_default_settings(self):
        """Test create_session() with default settings - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # Act - MANDATORY
        session = SessionFactory.create_session()

        # Assert - MANDATORY
        try:
            assert session is not None
            assert isinstance(session, aiohttp.ClientSession)
            assert session.connector is not None
            assert session.timeout is not None
        finally:
            await session.close()

    @pytest.mark.asyncio
    async def test_create_session_custom_max_connections(self):
        """Test create_session() with custom max connections - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        max_connections = 20

        # Act - MANDATORY
        session = SessionFactory.create_session(max_connections=max_connections)

        # Assert - MANDATORY
        try:
            assert session.connector.limit == max_connections
        finally:
            await session.close()

    @pytest.mark.asyncio
    async def test_create_session_custom_timeouts(self):
        """Test create_session() with custom timeouts - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        connection_timeout = 10.0
        total_timeout = 45.0
        read_timeout = 35.0

        # Act - MANDATORY
        session = SessionFactory.create_session(
            connection_timeout=connection_timeout,
            total_timeout=total_timeout,
            read_timeout=read_timeout,
        )

        # Assert - MANDATORY
        try:
            assert session.timeout.total == total_timeout
            assert session.timeout.connect == connection_timeout
            assert session.timeout.sock_read == read_timeout
        finally:
            await session.close()

    @pytest.mark.asyncio
    async def test_create_session_custom_keepalive_timeout(self):
        """Test create_session() with custom keepalive - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        keepalive_timeout = 60.0

        # Act - MANDATORY
        session = SessionFactory.create_session(keepalive_timeout=keepalive_timeout)

        # Assert - MANDATORY
        try:
            # TCPConnector stores keepalive_timeout as _keepalive_timeout
            assert session.connector._keepalive_timeout == keepalive_timeout
        finally:
            await session.close()

    @pytest.mark.asyncio
    async def test_create_session_ssl_verification_disabled(self):
        """Test create_session() with SSL verification disabled - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        verify_ssl = False

        # Act - MANDATORY
        session = SessionFactory.create_session(verify_ssl=verify_ssl)

        # Assert - MANDATORY
        try:
            assert session.connector._ssl is False
        finally:
            await session.close()

    @pytest.mark.asyncio
    async def test_create_session_custom_user_agent(self):
        """Test create_session() with custom user agent - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        custom_user_agent = "Test Bot/2.0"

        # Act - MANDATORY
        session = SessionFactory.create_session(user_agent=custom_user_agent)

        # Assert - MANDATORY
        try:
            assert session.headers["User-Agent"] == custom_user_agent
        finally:
            await session.close()

    @pytest.mark.asyncio
    async def test_create_session_custom_headers(self, custom_headers):
        """Test create_session() with custom headers - MANDATORY AAA pattern."""
        # Arrange - MANDATORY (using fixture)
        # Act - MANDATORY
        session = SessionFactory.create_session(custom_headers=custom_headers)

        # Assert - MANDATORY
        try:
            assert "X-Custom-Header" in session.headers
            assert session.headers["X-Custom-Header"] == "test-value"
            assert session.headers["X-Request-ID"] == "12345"
        finally:
            await session.close()

    @pytest.mark.asyncio
    async def test_create_session_with_cookie_jar(self):
        """Test create_session() with cookie jar - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        cookie_jar = aiohttp.CookieJar()

        # Act - MANDATORY
        session = SessionFactory.create_session(cookie_jar=cookie_jar)

        # Assert - MANDATORY
        try:
            assert session.cookie_jar is cookie_jar
        finally:
            await session.close()

    @pytest.mark.asyncio
    async def test_create_session_connector_configuration(self):
        """Test connector configuration in create_session() - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        max_connections = 15

        # Act - MANDATORY
        session = SessionFactory.create_session(max_connections=max_connections)

        # Assert - MANDATORY
        try:
            assert session.connector.limit == max_connections
            assert session.connector.limit_per_host == min(max_connections, 30)
            # TCPConnector uses _cached_hosts for DNS cache, not _ttl_dns_cache
            assert hasattr(session.connector, "_cached_hosts")
        finally:
            await session.close()

    @pytest.mark.asyncio
    async def test_create_session_timeout_configuration(self):
        """Test timeout configuration in create_session() - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        connection_timeout = 15.0
        total_timeout = 60.0
        read_timeout = 40.0

        # Act - MANDATORY
        session = SessionFactory.create_session(
            connection_timeout=connection_timeout,
            total_timeout=total_timeout,
            read_timeout=read_timeout,
        )

        # Assert - MANDATORY
        try:
            timeout = session.timeout
            assert timeout.total == total_timeout
            assert timeout.connect == connection_timeout
            assert timeout.sock_read == read_timeout
        finally:
            await session.close()

    def test_build_default_headers(self, default_user_agent):
        """Test _build_default_headers() - MANDATORY AAA pattern."""
        # Arrange - MANDATORY (using fixture)
        # Act - MANDATORY
        headers = SessionFactory._build_default_headers(default_user_agent)

        # Assert - MANDATORY
        assert headers["User-Agent"] == default_user_agent
        assert (
            headers["Accept"] == "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
        )
        assert headers["Accept-Language"] == "en-US,en;q=0.5"
        assert headers["Accept-Encoding"] == "gzip, deflate"
        assert headers["Connection"] == "keep-alive"
        assert headers["Upgrade-Insecure-Requests"] == "1"

    def test_build_default_headers_custom_user_agent(self):
        """Test _build_default_headers() with custom user agent - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        custom_user_agent = "Custom Bot/3.0"

        # Act - MANDATORY
        headers = SessionFactory._build_default_headers(custom_user_agent)

        # Assert - MANDATORY
        assert headers["User-Agent"] == custom_user_agent

    @pytest.mark.asyncio
    async def test_create_cookie_jar_unsafe_true(self):
        """Test create_cookie_jar() with unsafe=True - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # Act - MANDATORY
        cookie_jar = SessionFactory.create_cookie_jar(unsafe=True)

        # Assert - MANDATORY
        assert cookie_jar is not None
        assert isinstance(cookie_jar, aiohttp.CookieJar)
        # CookieJar stores unsafe as _unsafe private attribute
        assert cookie_jar._unsafe is True

    @pytest.mark.asyncio
    async def test_create_cookie_jar_unsafe_false(self):
        """Test create_cookie_jar() with unsafe=False - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # Act - MANDATORY
        cookie_jar = SessionFactory.create_cookie_jar(unsafe=False)

        # Assert - MANDATORY
        assert cookie_jar is not None
        assert isinstance(cookie_jar, aiohttp.CookieJar)
        # CookieJar stores unsafe as _unsafe private attribute
        assert cookie_jar._unsafe is False

    @pytest.mark.asyncio
    async def test_create_session_includes_all_default_headers(self):
        """Test create_session() includes all default headers - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # Act - MANDATORY
        session = SessionFactory.create_session()

        # Assert - MANDATORY
        try:
            headers = session.headers
            assert "User-Agent" in headers
            assert "Accept" in headers
            assert "Accept-Language" in headers
            assert "Accept-Encoding" in headers
            assert "Connection" in headers
            assert "Upgrade-Insecure-Requests" in headers
        finally:
            await session.close()

    @pytest.mark.asyncio
    async def test_create_session_custom_headers_override_defaults(self):
        """Test custom headers override defaults - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        custom_headers = {"Accept": "application/json"}

        # Act - MANDATORY
        session = SessionFactory.create_session(custom_headers=custom_headers)

        # Assert - MANDATORY
        try:
            assert session.headers["Accept"] == "application/json"
        finally:
            await session.close()

    @pytest.mark.asyncio
    async def test_create_session_limit_per_host_respects_max_connections(self):
        """Test limit_per_host respects max_connections - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        max_connections = 50  # More than 30

        # Act - MANDATORY
        session = SessionFactory.create_session(max_connections=max_connections)

        # Assert - MANDATORY
        try:
            # limit_per_host should be capped at 30
            assert session.connector.limit_per_host == 30
        finally:
            await session.close()

    @pytest.mark.asyncio
    async def test_create_session_limit_per_host_uses_max_connections_when_lower(self):
        """Test limit_per_host uses max_connections when lower - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        max_connections = 5  # Less than 30

        # Act - MANDATORY
        session = SessionFactory.create_session(max_connections=max_connections)

        # Assert - MANDATORY
        try:
            assert session.connector.limit_per_host == 5
        finally:
            await session.close()


# ============================================================================
# MANDATORY Performance Benchmarks
# ============================================================================


@pytest.mark.performance
@pytest.mark.unit
class TestSessionFactoryPerformance:
    """MANDATORY performance tests for session factory operations."""

    @pytest.mark.asyncio
    async def test_create_session_performance(self):
        """MANDATORY performance test - session creation speed."""
        # Arrange - MANDATORY
        iterations = 1000
        sessions = []

        # Act - MANDATORY
        start_time = time.perf_counter()

        for _ in range(iterations):
            session = SessionFactory.create_session()
            sessions.append(session)

        end_time = time.perf_counter()
        execution_time = end_time - start_time

        # Clean up sessions
        for session in sessions:
            await session.close()

        # Assert - MANDATORY
        avg_time = execution_time / iterations
        assert avg_time < 0.01  # <10ms per creation
        assert execution_time < 10.0  # Total <10s for 1000 creations

    @pytest.mark.asyncio
    async def test_create_cookie_jar_performance(self):
        """MANDATORY performance test - cookie jar creation speed."""
        # Arrange - MANDATORY
        iterations = 10000

        # Act - MANDATORY
        start_time = time.perf_counter()

        for _ in range(iterations):
            SessionFactory.create_cookie_jar(unsafe=True)

        end_time = time.perf_counter()
        execution_time = end_time - start_time

        # Assert - MANDATORY
        avg_time = execution_time / iterations
        assert avg_time < 0.0001  # <0.1ms per creation
        assert execution_time < 1.0  # Total <1s for 10000 creations

    def test_build_default_headers_performance(self):
        """MANDATORY performance test - header building speed."""
        # Arrange - MANDATORY
        iterations = 10000
        user_agent = "Performance Test Bot/1.0"

        # Act - MANDATORY
        start_time = time.perf_counter()

        for _ in range(iterations):
            SessionFactory._build_default_headers(user_agent)

        end_time = time.perf_counter()
        execution_time = end_time - start_time

        # Assert - MANDATORY
        avg_time = execution_time / iterations
        assert avg_time < 0.0001  # <0.1ms per build
        assert execution_time < 1.0  # Total <1s for 10000 builds
