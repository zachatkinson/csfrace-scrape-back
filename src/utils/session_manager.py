"""Enhanced session management with persistent cookies and authentication support.

This module implements production-ready session management following CLAUDE.md patterns
for WordPress scraping with authentication support and cookie persistence.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import aiohttp
from aiohttp import ClientSession

from src.core.logging_hierarchy import get_auth_logger

from ..constants import DEFAULT_TIMEOUT, DEFAULT_USER_AGENT, MAX_CONCURRENT
from ..core.exceptions import ConfigurationError
from .session import AuthenticationService, CookiePersistenceService, SessionFactory

logger = get_auth_logger()


@dataclass(frozen=True)
class SessionConfig:
    """Enhanced configuration for session management.

    This configuration follows CLAUDE.md standards for centralized
    configuration management with environment variable support.
    """

    # Connection settings
    max_concurrent_connections: int = MAX_CONCURRENT
    connection_timeout: float = float(DEFAULT_TIMEOUT)
    total_timeout: float = float(DEFAULT_TIMEOUT)
    read_timeout: float = 30.0

    # Keep-alive settings
    keepalive_timeout: float = 30.0
    # Note: enable_cleanup_closed removed as it's deprecated in Python 3.13+

    # Cookie and persistence settings
    cookie_jar_path: Path | None = None
    save_cookies: bool = True
    load_cookies: bool = True

    # User agent and headers
    user_agent: str = DEFAULT_USER_AGENT
    custom_headers: dict[str, str] = field(default_factory=dict)

    # Authentication settings
    username: str | None = None
    password: str | None = None
    auth_type: str = "basic"  # "basic", "bearer", "custom"
    bearer_token: str | None = None

    # Retry and resilience settings
    use_retry: bool = True
    max_redirects: int = 10

    # SSL settings
    verify_ssl: bool = True
    ssl_context: Any | None = None

    def __post_init__(self) -> None:
        """Validate configuration parameters."""
        if self.max_concurrent_connections < 1:
            raise ValueError("max_concurrent_connections must be at least 1")
        if self.connection_timeout <= 0:
            raise ValueError("connection_timeout must be positive")
        if self.total_timeout <= 0:
            raise ValueError("total_timeout must be positive")
        if self.auth_type not in ["basic", "bearer", "custom"]:
            raise ValueError("auth_type must be 'basic', 'bearer', or 'custom'")
        if (
            self.auth_type == "basic"
            and not (self.username and self.password)
            and (self.username or self.password)
        ):  # One provided but not both
            raise ValueError("Both username and password required for basic auth")
        if self.auth_type == "bearer" and not self.bearer_token:
            raise ValueError("bearer_token required for bearer auth")


class EnhancedSessionManager:
    """Enhanced session manager with persistent cookies and authentication.

    This class provides production-ready session management with comprehensive
    support for WordPress authentication patterns and persistent state.
    """

    def __init__(
        self, base_url: str, config: SessionConfig | None = None, session_name: str = "default"
    ):
        """Initialize enhanced session manager.

        Args:
            base_url: Base URL for the session
            config: Session configuration (uses defaults if None)
            session_name: Unique name for this session (for cookie storage)
        """
        self.base_url = self._validate_url(base_url)
        self.config = config or SessionConfig()
        self.session_name = session_name

        # Parse base URL for domain info
        self.parsed_url = urlparse(self.base_url)
        self.domain = self.parsed_url.netloc

        # Initialize services
        self._init_services()

        # Session state
        self._session: ClientSession | None = None

        logger.info(
            "Initialized enhanced session manager",
            domain=self.domain,
            session_name=session_name,
            persistent_cookies=self.cookie_persistence is not None,
            auth_type=self.config.auth_type if self.auth_service.has_strategy else None,
        )

    def _init_services(self) -> None:
        """Initialize service dependencies."""
        # Cookie persistence service
        self.cookie_persistence = None
        if self.config.cookie_jar_path:
            self.cookie_persistence = CookiePersistenceService(self.config.cookie_jar_path)

        # Authentication service
        self.auth_service = AuthenticationService()
        if self.config.auth_type == "basic" and self.config.username and self.config.password:
            self.auth_service.set_basic_auth(self.config.username, self.config.password)
        elif self.config.auth_type == "bearer" and self.config.bearer_token:
            self.auth_service.set_bearer_auth(self.config.bearer_token)

        # Cookie jar for session
        self.cookie_jar: aiohttp.CookieJar | None = None

    def _validate_url(self, url: str) -> str:
        """Validate and normalize URL."""
        if not url or not isinstance(url, str):
            raise ConfigurationError("URL must be a non-empty string")

        if not url.startswith(("http://", "https://")):
            url = "https://" + url

        parsed = urlparse(url)
        if not parsed.netloc or parsed.netloc in ("invalid-url", ""):
            raise ConfigurationError(f"Invalid URL: {url}")

        # Additional validation for obviously invalid URLs
        if parsed.netloc == "not-a-url" or not (
            "." in parsed.netloc or parsed.netloc in ("localhost", "127.0.0.1")
        ):
            raise ConfigurationError(f"Invalid URL: {url}")

        return url

    async def __aenter__(self) -> ClientSession:
        """Async context manager entry."""
        return await self.get_session()

    async def __aexit__(
        self, exc_type: type[BaseException] | None, exc_val: BaseException | None, exc_tb: Any
    ) -> None:
        """Async context manager exit."""
        await self.close()

    async def get_session(self) -> ClientSession:
        """Get or create HTTP session with enhanced configuration.

        Returns:
            Configured aiohttp ClientSession
        """
        if self._session and not self._session.closed:
            return self._session

        # Create cookie jar if needed
        if self.config.save_cookies or self.config.load_cookies:
            self.cookie_jar = SessionFactory.create_cookie_jar(unsafe=True)

            # Load persistent cookies if configured
            if self.config.load_cookies and self.cookie_persistence:
                self.cookie_persistence.load_cookies_into_jar(self.cookie_jar, self.domain)

        # Create session using factory
        self._session = SessionFactory.create_session(
            max_connections=self.config.max_concurrent_connections,
            connection_timeout=self.config.connection_timeout,
            total_timeout=self.config.total_timeout,
            read_timeout=self.config.read_timeout,
            keepalive_timeout=self.config.keepalive_timeout,
            verify_ssl=self.config.verify_ssl,
            ssl_context=self.config.ssl_context,
            user_agent=self.config.user_agent,
            custom_headers=self.config.custom_headers,
            cookie_jar=self.cookie_jar,
        )

        logger.info(
            "Created enhanced HTTP session",
            domain=self.domain,
            max_connections=self.config.max_concurrent_connections,
            has_cookies=self.cookie_jar is not None,
            timeout=self.config.total_timeout,
        )

        # Perform authentication if configured
        if self.auth_service.has_strategy and not self.auth_service.is_authenticated:
            await self.auth_service.authenticate(self._session, self.base_url)

        return self._session

    async def validate_authentication(self) -> bool:
        """Validate current authentication state.

        Returns:
            True if authenticated and valid, False otherwise
        """
        if not self._session:
            return False

        return await self.auth_service.validate_authentication(self._session, self.base_url)

    async def close(self) -> None:
        """Close session and save cookies if configured."""
        if self._session and not self._session.closed:
            # Save cookies before closing using service
            if self.config.save_cookies and self.cookie_persistence and self.cookie_jar:
                self.cookie_persistence.save_cookies(self.cookie_jar)

            await self._session.close()
            logger.debug("Closed enhanced session", domain=self.domain)

    async def make_request(self, method: str, url: str, **kwargs: Any) -> aiohttp.ClientResponse:
        """Make an HTTP request with the managed session.

        Args:
            method: HTTP method (GET, POST, etc.)
            url: URL to request
            **kwargs: Additional request parameters

        Returns:
            aiohttp ClientResponse
        """
        session = await self.get_session()

        # Ensure URL is absolute
        if not url.startswith(("http://", "https://")):
            url = urljoin(self.base_url, url)

        return await session.request(method, url, **kwargs)

    @property
    def is_authenticated(self) -> bool:
        """Check if session is authenticated."""
        return self.auth_service.is_authenticated

    @property
    def metrics(self) -> dict[str, Any]:
        """Get session metrics for monitoring."""
        return {
            "domain": self.domain,
            "session_name": self.session_name,
            "is_authenticated": self.auth_service.is_authenticated,
            "has_persistent_cookies": self.cookie_persistence is not None,
            "session_active": self._session is not None and not self._session.closed,
            "config": {
                "max_connections": self.config.max_concurrent_connections,
                "timeout": self.config.total_timeout,
                "auth_type": self.config.auth_type if self.auth_service.has_strategy else None,
                "save_cookies": self.config.save_cookies,
            },
        }


# Utility function for easy session creation
async def create_session(
    base_url: str, config: SessionConfig | None = None, session_name: str = "default"
) -> EnhancedSessionManager:
    """Create and return an enhanced session manager.

    Args:
        base_url: Base URL for the session
        config: Session configuration
        session_name: Unique session name

    Returns:
        Configured EnhancedSessionManager
    """
    manager = EnhancedSessionManager(base_url, config, session_name)
    await manager.get_session()  # Initialize session
    return manager
