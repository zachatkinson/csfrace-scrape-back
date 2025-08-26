"""Enhanced session management with persistent cookies and authentication support.

This module implements production-ready session management following CLAUDE.md patterns
for WordPress scraping with authentication support and cookie persistence.
"""

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse

import aiohttp
import structlog
from aiohttp import BasicAuth, ClientSession, TCPConnector

from ..constants import CONSTANTS
from ..core.exceptions import ConfigurationError, FetchError

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class SessionConfig:
    """Enhanced configuration for session management.

    This configuration follows CLAUDE.md standards for centralized
    configuration management with environment variable support.
    """

    # Connection settings
    max_concurrent_connections: int = CONSTANTS.MAX_CONCURRENT
    connection_timeout: float = float(CONSTANTS.DEFAULT_TIMEOUT)
    total_timeout: float = float(CONSTANTS.DEFAULT_TIMEOUT)
    read_timeout: float = 30.0

    # Keep-alive settings
    keepalive_timeout: float = 30.0
    enable_cleanup_closed: bool = True

    # Cookie and persistence settings
    cookie_jar_path: Optional[Path] = None
    save_cookies: bool = True
    load_cookies: bool = True

    # User agent and headers
    user_agent: str = CONSTANTS.DEFAULT_USER_AGENT
    custom_headers: dict[str, str] = field(default_factory=dict)

    # Authentication settings
    username: Optional[str] = None
    password: Optional[str] = None
    auth_type: str = "basic"  # "basic", "bearer", "custom"
    bearer_token: Optional[str] = None

    # Retry and resilience settings
    use_retry: bool = True
    max_redirects: int = 10

    # SSL settings
    verify_ssl: bool = True
    ssl_context: Optional[Any] = None

    def __post_init__(self):
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


class PersistentCookieJar:
    """Persistent cookie jar with file-based storage.

    This class handles cookie persistence across sessions for maintaining
    authentication state and session continuity.
    """

    def __init__(self, file_path: Path):
        """Initialize persistent cookie jar.

        Args:
            file_path: Path to store cookie data
        """
        self.file_path = file_path
        self.cookies: dict[str, dict[str, Any]] = {}
        self._ensure_directory()

        logger.debug("Initialized persistent cookie jar", path=str(file_path))

    def _ensure_directory(self):
        """Ensure cookie storage directory exists."""
        self.file_path.parent.mkdir(parents=True, exist_ok=True)

    def load_cookies(self) -> dict[str, dict[str, Any]]:
        """Load cookies from persistent storage.

        Returns:
            Dictionary of cookie data
        """
        if not self.file_path.exists():
            logger.debug("No existing cookie file found")
            return {}

        try:
            with open(self.file_path, encoding="utf-8") as f:
                cookie_data = json.load(f)

            # Filter out expired cookies
            current_time = time.time()
            valid_cookies = {}

            for domain, cookies in cookie_data.items():
                valid_domain_cookies = {}
                for name, cookie in cookies.items():
                    expires = cookie.get("expires")
                    if expires is None or expires > current_time:
                        valid_domain_cookies[name] = cookie

                if valid_domain_cookies:
                    valid_cookies[domain] = valid_domain_cookies

            self.cookies = valid_cookies

            logger.info(
                "Loaded persistent cookies",
                domains=len(valid_cookies),
                total_cookies=sum(len(cookies) for cookies in valid_cookies.values()),
            )

            return valid_cookies

        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Failed to load cookies, starting fresh", error=str(e))
            return {}

    def save_cookies(self, cookie_jar: aiohttp.CookieJar):
        """Save cookies to persistent storage.

        Args:
            cookie_jar: aiohttp cookie jar to save
        """
        if not cookie_jar:
            logger.debug("No cookies to save")
            return

        cookie_data: dict[str, dict[str, Any]] = {}

        for cookie in cookie_jar:
            domain = cookie.get("domain", "")
            name = cookie.get("name", "")

            if not domain or not name:
                continue

            if domain not in cookie_data:
                cookie_data[domain] = {}

            cookie_data[domain][name] = {
                "name": name,
                "value": cookie.get("value", ""),
                "domain": domain,
                "path": cookie.get("path", "/"),
                "expires": cookie.get("expires", None),
                "secure": cookie.get("secure", False),
                "httponly": cookie.get("httponly", False),
            }

        try:
            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump(cookie_data, f, indent=2, default=str)

            logger.info(
                "Saved persistent cookies",
                domains=len(cookie_data),
                total_cookies=sum(len(cookies) for cookies in cookie_data.values()),
                path=str(self.file_path),
            )

        except OSError as e:
            logger.error("Failed to save cookies", error=str(e), path=str(self.file_path))


class EnhancedSessionManager:
    """Enhanced session manager with persistent cookies and authentication.

    This class provides production-ready session management with comprehensive
    support for WordPress authentication patterns and persistent state.
    """

    def __init__(
        self, base_url: str, config: Optional[SessionConfig] = None, session_name: str = "default"
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

        # Initialize cookie persistence
        self.cookie_jar: Optional[aiohttp.CookieJar] = None
        self.persistent_jar = None
        if self.config.cookie_jar_path:
            self.persistent_jar = PersistentCookieJar(self.config.cookie_jar_path)

        # Session state
        self._session: Optional[ClientSession] = None
        self._is_authenticated = False
        self._auth_validated = False

        logger.info(
            "Initialized enhanced session manager",
            domain=self.domain,
            session_name=session_name,
            persistent_cookies=self.persistent_jar is not None,
            auth_type=self.config.auth_type if self._has_auth_config() else None,
        )

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

    def _has_auth_config(self) -> bool:
        """Check if authentication is configured."""
        if self.config.auth_type == "basic":
            return bool(self.config.username and self.config.password)
        elif self.config.auth_type == "bearer":
            return bool(self.config.bearer_token)
        return False

    async def __aenter__(self) -> ClientSession:
        """Async context manager entry."""
        return await self.get_session()

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()

    async def get_session(self) -> ClientSession:
        """Get or create HTTP session with enhanced configuration.

        Returns:
            Configured aiohttp ClientSession
        """
        if self._session and not self._session.closed:
            return self._session

        # Create cookie jar
        if self.config.save_cookies or self.config.load_cookies:
            self.cookie_jar = aiohttp.CookieJar(unsafe=True)

            # Load persistent cookies if configured
            if self.config.load_cookies and self.persistent_jar:
                await self._load_persistent_cookies()

        # Create connector with enhanced configuration
        connector = TCPConnector(
            limit=self.config.max_concurrent_connections,
            limit_per_host=min(self.config.max_concurrent_connections, 30),
            ttl_dns_cache=300,  # Cache DNS for 5 minutes
            use_dns_cache=True,
            keepalive_timeout=self.config.keepalive_timeout,
            enable_cleanup_closed=self.config.enable_cleanup_closed,
            verify_ssl=self.config.verify_ssl,
            ssl_context=self.config.ssl_context,
        )

        # Create timeout configuration
        timeout = aiohttp.ClientTimeout(
            total=self.config.total_timeout,
            connect=self.config.connection_timeout,
            sock_read=self.config.read_timeout,
        )

        # Prepare headers
        headers = {
            "User-Agent": self.config.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }
        headers.update(self.config.custom_headers)

        # Create session
        self._session = ClientSession(
            connector=connector,
            timeout=timeout,
            headers=headers,
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
        if self._has_auth_config() and not self._is_authenticated:
            await self._authenticate()

        return self._session

    async def _load_persistent_cookies(self):
        """Load persistent cookies into the session."""
        if not self.persistent_jar or not self.cookie_jar:
            return

        cookie_data = self.persistent_jar.load_cookies()

        # Add cookies to the jar for our domain and parent domains
        for domain, cookies in cookie_data.items():
            if self.domain.endswith(domain) or domain.endswith(self.domain):
                for cookie_info in cookies.values():
                    self.cookie_jar.update_cookies({cookie_info["name"]: cookie_info["value"]})

        logger.debug("Loaded persistent cookies into session")

    async def _authenticate(self):
        """Perform authentication based on configuration."""
        if not self._session:
            raise RuntimeError("Session not initialized")

        try:
            if self.config.auth_type == "basic":
                await self._perform_basic_auth()
            elif self.config.auth_type == "bearer":
                await self._perform_bearer_auth()
            elif self.config.auth_type == "custom":
                await self._perform_custom_auth()

            self._is_authenticated = True
            logger.info("Authentication successful", auth_type=self.config.auth_type)

        except Exception as e:
            logger.error("Authentication failed", auth_type=self.config.auth_type, error=str(e))
            raise FetchError(f"Authentication failed: {e}")

    async def _perform_basic_auth(self):
        """Perform HTTP Basic Authentication."""
        # For WordPress, we might need to authenticate against wp-login.php
        login_url = f"{self.base_url.rstrip('/')}/wp-login.php"

        # Try WordPress login form authentication
        try:
            # Get login page first
            async with self._session.get(login_url) as response:
                login_page = await response.text()

            # Parse login form and submit credentials
            from bs4 import BeautifulSoup

            soup = BeautifulSoup(login_page, "html.parser")

            # Look for WordPress login form
            login_form = soup.find("form", {"id": "loginform"})
            if login_form:
                # Extract form action and hidden fields
                action = login_form.get("action", login_url)

                form_data = {
                    "log": self.config.username,
                    "pwd": self.config.password,
                    "wp-submit": "Log In",
                    "redirect_to": self.base_url,
                    "testcookie": "1",
                }

                # Add any hidden fields
                for hidden_input in login_form.find_all("input", {"type": "hidden"}):
                    name = hidden_input.get("name")
                    value = hidden_input.get("value")
                    if name:
                        form_data[name] = value or ""

                # Submit login form
                async with self._session.post(action, data=form_data) as response:
                    if response.status == 200 and "wp-admin" in str(response.url):
                        logger.info("WordPress form login successful")
                        return

            # Fallback to HTTP Basic Auth
            auth = BasicAuth(self.config.username, self.config.password)
            async with self._session.get(self.base_url, auth=auth) as response:
                if response.status == 200:
                    logger.info("HTTP Basic Auth successful")
                    return

            raise FetchError("Basic authentication failed")

        except Exception as e:
            logger.error("Basic authentication error", error=str(e))
            raise

    async def _perform_bearer_auth(self):
        """Perform Bearer Token Authentication."""
        if not self._session:
            raise RuntimeError("Session not initialized")

        # Add bearer token to session headers
        self._session.headers["Authorization"] = f"Bearer {self.config.bearer_token}"

        # Validate token by making a test request
        try:
            async with self._session.get(self.base_url) as response:
                if response.status == 401:
                    raise FetchError("Bearer token authentication failed - unauthorized")
                elif response.status >= 400:
                    raise FetchError(f"Bearer token validation failed - status {response.status}")

            logger.info("Bearer token authentication validated")

        except aiohttp.ClientError as e:
            raise FetchError(f"Bearer token validation error: {e}")

    async def _perform_custom_auth(self):
        """Perform custom authentication (placeholder for extensibility)."""
        logger.warning("Custom authentication requested but not implemented")
        # This would be implemented based on specific site requirements

    async def validate_authentication(self) -> bool:
        """Validate current authentication state.

        Returns:
            True if authenticated and valid, False otherwise
        """
        if not self._is_authenticated or not self._session:
            return False

        if self._auth_validated:
            return True

        try:
            # Make a test request to a protected area
            protected_urls = [
                f"{self.base_url.rstrip('/')}/wp-admin/",
                f"{self.base_url.rstrip('/')}/wp-admin/index.php",
                self.base_url,
            ]

            for url in protected_urls:
                try:
                    async with self._session.get(url, allow_redirects=False) as response:
                        # Check for authentication indicators
                        if response.status == 200:
                            # Check if we're getting login page content
                            if response.content_type and "text/html" in response.content_type:
                                content = await response.text()
                                if "wp-login" not in content.lower():
                                    self._auth_validated = True
                                    return True
                        elif response.status in (301, 302):
                            # Check redirect location
                            location = response.headers.get("Location", "")
                            if "wp-login" not in location:
                                self._auth_validated = True
                                return True

                except aiohttp.ClientError:
                    continue

            return False

        except Exception as e:
            logger.warning("Authentication validation failed", error=str(e))
            return False

    async def close(self):
        """Close session and save cookies if configured."""
        if self._session and not self._session.closed:
            # Save cookies before closing
            if self.config.save_cookies and self.persistent_jar and self.cookie_jar:
                self.persistent_jar.save_cookies(self.cookie_jar)

            await self._session.close()
            logger.debug("Closed enhanced session", domain=self.domain)

    async def make_request(self, method: str, url: str, **kwargs) -> aiohttp.ClientResponse:
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
            from urllib.parse import urljoin

            url = urljoin(self.base_url, url)

        return await session.request(method, url, **kwargs)

    @property
    def is_authenticated(self) -> bool:
        """Check if session is authenticated."""
        return self._is_authenticated

    @property
    def metrics(self) -> dict[str, Any]:
        """Get session metrics for monitoring."""
        return {
            "domain": self.domain,
            "session_name": self.session_name,
            "is_authenticated": self._is_authenticated,
            "auth_validated": self._auth_validated,
            "has_persistent_cookies": self.persistent_jar is not None,
            "session_active": self._session is not None and not self._session.closed,
            "config": {
                "max_connections": self.config.max_concurrent_connections,
                "timeout": self.config.total_timeout,
                "auth_type": self.config.auth_type if self._has_auth_config() else None,
                "save_cookies": self.config.save_cookies,
            },
        }


# Utility function for backward compatibility and ease of use
async def create_session(
    base_url: str, config: Optional[SessionConfig] = None, session_name: str = "default"
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
