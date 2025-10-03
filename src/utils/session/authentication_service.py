"""Authentication service for session management following SOLID principles."""

from abc import ABC, abstractmethod

import aiohttp
from aiohttp import BasicAuth
from bs4 import BeautifulSoup

from src.core.decorators import network_error_handler
from src.core.logging_hierarchy import get_auth_logger

from ...core.exceptions import FetchError

logger = get_auth_logger()


class AuthenticationStrategy(ABC):
    """Abstract base class for authentication strategies - SOLID Open/Closed Principle."""

    @abstractmethod
    async def authenticate(self, session: aiohttp.ClientSession, base_url: str) -> bool:
        """Authenticate using this strategy.

        Args:
            session: HTTP session to authenticate
            base_url: Base URL for authentication

        Returns:
            True if authentication successful
        """


class BasicAuthStrategy(AuthenticationStrategy):
    """HTTP Basic Authentication strategy."""

    def __init__(self, username: str, password: str):
        """Initialize basic auth strategy.

        Args:
            username: Authentication username
            password: Authentication password
        """
        self.username = username
        self.password = password

    @network_error_handler("perform basic authentication")
    async def authenticate(self, session: aiohttp.ClientSession, base_url: str) -> bool:
        """Perform HTTP Basic Authentication with WordPress form fallback."""
        # Try WordPress form login first
        if await self._try_wordpress_form_login(session, base_url):
            return True

        # Fallback to HTTP Basic Auth
        return await self._try_http_basic_auth(session, base_url)

    async def _try_wordpress_form_login(
        self, session: aiohttp.ClientSession, base_url: str
    ) -> bool:
        """Try WordPress form-based login.

        Args:
            session: HTTP session
            base_url: Base URL

        Returns:
            True if successful
        """
        login_url = f"{base_url.rstrip('/')}/wp-login.php"

        try:
            # Get login page
            async with session.get(login_url) as response:
                if response.status != 200:
                    return False
                login_page = await response.text()

            # Parse and submit login form
            form_data = self._extract_login_form_data(login_page, base_url)
            if not form_data:
                return False

            # Submit login form
            async with session.post(login_url, data=form_data) as response:
                return response.status == 200 and "wp-admin" in str(response.url)

        except aiohttp.ClientError:
            return False

    def _extract_login_form_data(self, login_page: str, base_url: str) -> dict[str, str] | None:
        """Extract WordPress login form data.

        Args:
            login_page: HTML content of login page
            base_url: Base URL for redirect

        Returns:
            Form data dictionary or None if not found
        """
        soup = BeautifulSoup(login_page, "html.parser")
        login_form = soup.find("form", {"id": "loginform"})

        if not login_form or not hasattr(login_form, "get"):
            return None

        form_data = {
            "log": self.username,
            "pwd": self.password,
            "wp-submit": "Log In",
            "redirect_to": base_url,
            "testcookie": "1",
        }

        # Add hidden fields
        if hasattr(login_form, "find_all"):
            for hidden_input in login_form.find_all("input", {"type": "hidden"}):
                if hasattr(hidden_input, "get"):
                    name = hidden_input.get("name")
                    value = hidden_input.get("value")
                    if name:
                        form_data[name] = value or ""

        return form_data

    async def _try_http_basic_auth(self, session: aiohttp.ClientSession, base_url: str) -> bool:
        """Try HTTP Basic Authentication.

        Args:
            session: HTTP session
            base_url: Base URL

        Returns:
            True if successful
        """
        try:
            auth = BasicAuth(self.username, self.password)
            async with session.get(base_url, auth=auth) as response:
                return response.status == 200
        except aiohttp.ClientError:
            return False


class BearerTokenStrategy(AuthenticationStrategy):
    """Bearer token authentication strategy."""

    def __init__(self, token: str):
        """Initialize bearer token strategy.

        Args:
            token: Bearer token
        """
        self.token = token

    @network_error_handler("perform bearer authentication")
    async def authenticate(self, session: aiohttp.ClientSession, base_url: str) -> bool:
        """Perform Bearer Token Authentication."""
        # Add bearer token to session headers
        session.headers["Authorization"] = f"Bearer {self.token}"

        # Validate token by making a test request
        # Network errors (ClientError, etc.) are handled by @network_error_handler decorator
        async with session.get(base_url) as response:
            if response.status == 401:
                raise FetchError("Bearer token authentication failed - unauthorized")
            if response.status >= 400:
                raise FetchError(f"Bearer token validation failed - status {response.status}")

            logger.info("Bearer token authentication validated")
            return True


class AuthenticationService:
    """Service for managing authentication strategies - SOLID Single Responsibility."""

    def __init__(self) -> None:
        """Initialize authentication service."""
        self._strategy: AuthenticationStrategy | None = None
        self._is_authenticated = False
        self._auth_validated = False

    def set_basic_auth(self, username: str, password: str) -> None:
        """Set basic authentication strategy.

        Args:
            username: Authentication username
            password: Authentication password
        """
        self._strategy = BasicAuthStrategy(username, password)
        self._reset_auth_state()

    def set_bearer_auth(self, token: str) -> None:
        """Set bearer token authentication strategy.

        Args:
            token: Bearer token
        """
        self._strategy = BearerTokenStrategy(token)
        self._reset_auth_state()

    def _reset_auth_state(self) -> None:
        """Reset authentication state when strategy changes."""
        self._is_authenticated = False
        self._auth_validated = False

    async def authenticate(self, session: aiohttp.ClientSession, base_url: str) -> bool:
        """Perform authentication using configured strategy.

        Args:
            session: HTTP session
            base_url: Base URL

        Returns:
            True if authentication successful

        Raises:
            RuntimeError: If no authentication strategy is configured
        """
        if not self._strategy:
            raise RuntimeError("No authentication strategy configured")

        success = await self._strategy.authenticate(session, base_url)
        self._is_authenticated = success

        if success:
            logger.info("Authentication successful", strategy=type(self._strategy).__name__)
        else:
            logger.warning("Authentication failed", strategy=type(self._strategy).__name__)

        return success

    async def validate_authentication(self, session: aiohttp.ClientSession, base_url: str) -> bool:
        """Validate current authentication state.

        Args:
            session: HTTP session
            base_url: Base URL

        Returns:
            True if authenticated and valid
        """
        if not self._is_authenticated:
            return False

        if self._auth_validated:
            return True

        return await self._validate_authentication_safe(session, base_url)

    @network_error_handler("validate authentication")
    async def _validate_authentication_safe(
        self, session: aiohttp.ClientSession, base_url: str
    ) -> bool:
        """Validate authentication with error handling."""
        protected_urls = [
            f"{base_url.rstrip('/')}/wp-admin/",
            f"{base_url.rstrip('/')}/wp-admin/index.php",
            base_url,
        ]

        for url in protected_urls:
            if await self._test_protected_url(session, url):
                self._auth_validated = True
                return True

        return False

    async def _test_protected_url(self, session: aiohttp.ClientSession, url: str) -> bool:
        """Test if a URL indicates successful authentication.

        Args:
            session: HTTP session
            url: URL to test

        Returns:
            True if authentication is indicated
        """
        try:
            async with session.get(url, allow_redirects=False) as response:
                # Check for authentication indicators
                if response.status == 200:
                    return await self._check_response_content(response)
                elif response.status in (301, 302):
                    # Check redirect location
                    location = response.headers.get("Location", "")
                    return "wp-login" not in location

        except aiohttp.ClientError:
            pass

        return False

    async def _check_response_content(self, response: aiohttp.ClientResponse) -> bool:
        """Check response content for authentication indicators.

        Args:
            response: HTTP response

        Returns:
            True if authenticated content detected
        """
        if response.content_type and "text/html" in response.content_type:
            content = await response.text()
            return "wp-login" not in content.lower()
        return True

    @property
    def is_authenticated(self) -> bool:
        """Check if authentication has been performed."""
        return self._is_authenticated

    @property
    def has_strategy(self) -> bool:
        """Check if authentication strategy is configured."""
        return self._strategy is not None
