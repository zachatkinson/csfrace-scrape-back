"""Cookie persistence service following SOLID principles."""

import json
import time
from pathlib import Path
from typing import Any

import aiohttp

from src.core.logging_hierarchy import get_auth_logger

logger = get_auth_logger()


class CookiePersistenceService:
    """Service for persistent cookie storage - SOLID Single Responsibility."""

    def __init__(self, file_path: Path):
        """Initialize cookie persistence service.

        Args:
            file_path: Path to store cookie data
        """
        self.file_path = file_path
        self.cookies: dict[str, dict[str, Any]] = {}
        self._ensure_directory()

        logger.debug("Initialized cookie persistence service", path=str(file_path))

    def _ensure_directory(self) -> None:
        """Ensure cookie storage directory exists."""
        self.file_path.parent.mkdir(parents=True, exist_ok=True)

    def load_cookies(self) -> dict[str, dict[str, Any]]:
        """Load cookies from persistent storage.

        Returns:
            Dictionary of valid cookie data
        """
        if not self.file_path.exists():
            logger.debug("No existing cookie file found")
            return {}

        return self._load_cookies_safe()

    def _load_cookies_safe(self) -> dict[str, dict[str, Any]]:
        """Load and filter expired cookies with error handling."""
        try:
            with open(self.file_path, encoding="utf-8") as f:
                cookie_data = json.load(f)

            # Filter out expired cookies
            valid_cookies = self._filter_expired_cookies(cookie_data)
            self.cookies = valid_cookies

            logger.info(
                "Loaded persistent cookies",
                domains=len(valid_cookies),
                total_cookies=sum(len(cookies) for cookies in valid_cookies.values()),
            )

            return valid_cookies
        except Exception as e:
            logger.error("Failed to load persistent cookies", error=str(e))
            return {}

    def _filter_expired_cookies(
        self, cookie_data: dict[str, dict[str, Any]]
    ) -> dict[str, dict[str, Any]]:
        """Filter out expired cookies.

        Args:
            cookie_data: Raw cookie data from storage

        Returns:
            Filtered valid cookies
        """
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

        return valid_cookies

    def save_cookies(self, cookie_jar: aiohttp.CookieJar) -> None:
        """Save cookies to persistent storage.

        Args:
            cookie_jar: aiohttp cookie jar to save
        """
        if not cookie_jar:
            logger.debug("No cookies to save")
            return

        cookie_data = self._extract_cookie_data(cookie_jar)
        if not cookie_data:
            logger.debug("No cookie data to save")
            return
        self._save_cookies_safe(cookie_data)

    def _extract_cookie_data(self, cookie_jar: aiohttp.CookieJar) -> dict[str, dict[str, Any]]:
        """Extract cookie data from aiohttp cookie jar.

        Args:
            cookie_jar: aiohttp cookie jar

        Returns:
            Structured cookie data
        """
        cookie_data: dict[str, dict[str, Any]] = {}

        # Iterate over cookies in the jar - cookies are http.cookies.Morsel objects
        for cookie in cookie_jar:
            # Morsel objects have key, value, and coded_value attributes
            # Domain is in the cookie dict
            domain = cookie.get("domain", "")
            name = cookie.key if hasattr(cookie, "key") else ""
            value = cookie.value if hasattr(cookie, "value") else cookie.get("value", "")

            if not domain or not name:
                logger.debug(
                    "Skipping cookie with missing domain or name", domain=domain, name=name
                )
                continue

            if domain not in cookie_data:
                cookie_data[domain] = {}

            cookie_data[domain][name] = {
                "name": name,
                "value": value,
                "domain": domain,
                "path": cookie.get("path", "/"),
                "expires": cookie.get("expires", None),
                "secure": cookie.get("secure", False),
                "httponly": cookie.get("httponly", False),
            }

        logger.debug(
            "Extracted cookie data",
            domains=len(cookie_data),
            total_cookies=sum(len(c) for c in cookie_data.values()),
        )
        return cookie_data

    def _save_cookies_safe(self, cookie_data: dict[str, dict[str, Any]]) -> None:
        """Save cookies to file with error handling.

        Args:
            cookie_data: Cookie data to save
        """
        try:
            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump(cookie_data, f, indent=2, default=str)
        except Exception as e:
            logger.error("Failed to save persistent cookies", error=str(e))

        logger.info(
            "Saved persistent cookies",
            domains=len(cookie_data),
            total_cookies=sum(len(cookies) for cookies in cookie_data.values()),
            path=str(self.file_path),
        )

    def load_cookies_into_jar(self, cookie_jar: aiohttp.CookieJar, domain: str) -> None:
        """Load persistent cookies into an aiohttp cookie jar.

        Args:
            cookie_jar: Target cookie jar
            domain: Domain to match against stored cookies
        """
        cookie_data = self.load_cookies()

        # Add cookies to the jar for our domain and parent domains
        for stored_domain, cookies in cookie_data.items():
            if domain.endswith(stored_domain) or stored_domain.endswith(domain):
                for cookie_info in cookies.values():
                    cookie_jar.update_cookies({cookie_info["name"]: cookie_info["value"]})

        logger.debug("Loaded persistent cookies into jar", domain=domain)
