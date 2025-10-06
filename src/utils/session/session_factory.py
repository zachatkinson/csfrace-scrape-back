"""Session factory for creating configured HTTP sessions following SOLID principles."""

from typing import Any

import aiohttp
from aiohttp import ClientSession, TCPConnector

from src.core.logging_hierarchy import get_auth_logger

logger = get_auth_logger()


class SessionFactory:
    """Factory for creating configured HTTP sessions - SOLID Single Responsibility."""

    @staticmethod
    def create_session(
        max_connections: int = 10,
        connection_timeout: float = 30.0,
        total_timeout: float = 30.0,
        read_timeout: float = 30.0,
        keepalive_timeout: float = 30.0,
        verify_ssl: bool = True,
        ssl_context: Any = None,
        user_agent: str = "Enhanced Session Manager/1.0",
        custom_headers: dict[str, str] | None = None,
        cookie_jar: aiohttp.CookieJar | None = None,
    ) -> ClientSession:
        """Create a configured HTTP session.

        Args:
            max_connections: Maximum concurrent connections
            connection_timeout: Connection timeout in seconds
            total_timeout: Total request timeout in seconds
            read_timeout: Socket read timeout in seconds
            keepalive_timeout: Keep-alive timeout in seconds
            verify_ssl: Whether to verify SSL certificates
            ssl_context: Custom SSL context
            user_agent: User-Agent header value
            custom_headers: Additional headers to include
            cookie_jar: Cookie jar for session

        Returns:
            Configured ClientSession
        """
        # Create connector with configuration
        connector = TCPConnector(
            limit=max_connections,
            limit_per_host=min(max_connections, 30),
            ttl_dns_cache=300,  # Cache DNS for 5 minutes
            use_dns_cache=True,
            keepalive_timeout=keepalive_timeout,
            verify_ssl=verify_ssl,
            ssl_context=ssl_context,
        )

        # Create timeout configuration
        timeout = aiohttp.ClientTimeout(
            total=total_timeout,
            connect=connection_timeout,
            sock_read=read_timeout,
        )

        # Prepare headers
        headers = SessionFactory._build_default_headers(user_agent)
        if custom_headers:
            headers.update(custom_headers)

        # Create and return session
        session = ClientSession(
            connector=connector,
            timeout=timeout,
            headers=headers,
            cookie_jar=cookie_jar,
        )

        logger.info(
            "Created HTTP session",
            max_connections=max_connections,
            timeout=total_timeout,
            has_cookies=cookie_jar is not None,
        )

        return session

    @staticmethod
    def _build_default_headers(user_agent: str) -> dict[str, str]:
        """Build default HTTP headers.

        Args:
            user_agent: User-Agent header value

        Returns:
            Dictionary of default headers
        """
        return {
            "User-Agent": user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }

    @staticmethod
    def create_cookie_jar(unsafe: bool = True) -> aiohttp.CookieJar:
        """Create a cookie jar with specified safety settings.

        Args:
            unsafe: Whether to allow unsafe cookies

        Returns:
            Configured CookieJar
        """
        return aiohttp.CookieJar(unsafe=unsafe)
