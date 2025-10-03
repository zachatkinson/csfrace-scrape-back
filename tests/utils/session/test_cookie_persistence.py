"""Comprehensive tests for cookie persistence service - MANDATORY TEST_BUILDING.md compliance.

This module tests cookie persistence functionality with complete coverage:
- CookiePersistenceService initialization
- Cookie loading from persistent storage
- Cookie saving to persistent storage
- Expired cookie filtering
- Cookie extraction from aiohttp jar
- Loading cookies into jar
- Edge cases and error handling
- Performance benchmarks

ALL tests follow MANDATORY TEST_BUILDING.md patterns:
- AAA pattern with explicit comments
- Factory fixtures for DRY principle
- Comprehensive cookie persistence scenario testing
- Performance benchmarks with specific thresholds
"""

import json
import time
from unittest.mock import MagicMock

import aiohttp
import pytest

from src.utils.session.cookie_persistence import CookiePersistenceService

# ============================================================================
# Test Fixtures - DRY Principle
# ============================================================================


@pytest.fixture
def temp_cookie_file(tmp_path):
    """Factory for temporary cookie file - DRY principle."""
    return tmp_path / "cookies.json"


@pytest.fixture
def sample_cookie_data():
    """Factory for sample cookie data - DRY principle."""
    return {
        "example.com": {
            "session_id": {
                "name": "session_id",
                "value": "abc123",
                "domain": "example.com",
                "path": "/",
                "expires": time.time() + 3600,  # Expires in 1 hour
                "secure": True,
                "httponly": True,
            },
            "user_pref": {
                "name": "user_pref",
                "value": "dark_mode",
                "domain": "example.com",
                "path": "/",
                "expires": None,  # Session cookie
                "secure": False,
                "httponly": False,
            },
        }
    }


@pytest.fixture
def expired_cookie_data():
    """Factory for expired cookie data - DRY principle."""
    return {
        "example.com": {
            "expired_cookie": {
                "name": "expired_cookie",
                "value": "old_value",
                "domain": "example.com",
                "path": "/",
                "expires": time.time() - 3600,  # Expired 1 hour ago
                "secure": False,
                "httponly": False,
            }
        }
    }


@pytest.fixture
def mock_cookie_jar():
    """Factory for mock cookie jar - DRY principle."""
    jar = MagicMock(spec=aiohttp.CookieJar)
    # Create mock cookies that behave like http.cookies.Morsel objects
    cookie1 = MagicMock()
    cookie1.key = "cookie1"
    cookie1.value = "value1"
    cookie1.get.side_effect = lambda k, default=None: {
        "domain": "example.com",
        "path": "/",
        "expires": time.time() + 3600,
        "secure": True,
        "httponly": True,
    }.get(k, default)

    cookie2 = MagicMock()
    cookie2.key = "cookie2"
    cookie2.value = "value2"
    cookie2.get.side_effect = lambda k, default=None: {
        "domain": "example.com",
        "path": "/api",
        "expires": None,
        "secure": False,
        "httponly": False,
    }.get(k, default)

    jar.__iter__ = MagicMock(return_value=iter([cookie1, cookie2]))
    jar.__len__ = MagicMock(return_value=2)  # Make mock truthy via __len__
    jar.update_cookies = MagicMock()
    return jar


# ============================================================================
# CookiePersistenceService Tests
# ============================================================================


@pytest.mark.unit
class TestCookiePersistenceService:
    """Tests for CookiePersistenceService class."""

    def test_initialization(self, temp_cookie_file):
        """Test CookiePersistenceService initialization - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # Act - MANDATORY
        service = CookiePersistenceService(temp_cookie_file)

        # Assert - MANDATORY
        assert service.file_path == temp_cookie_file
        assert service.cookies == {}
        assert temp_cookie_file.parent.exists()

    def test_ensure_directory_creates_parent_directories(self, tmp_path):
        """Test _ensure_directory() creates parent dirs - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        nested_path = tmp_path / "level1" / "level2" / "cookies.json"

        # Act - MANDATORY
        service = CookiePersistenceService(nested_path)

        # Assert - MANDATORY
        assert nested_path.parent.exists()

    def test_load_cookies_no_existing_file(self, temp_cookie_file):
        """Test load_cookies() with no existing file - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        service = CookiePersistenceService(temp_cookie_file)

        # Act - MANDATORY
        cookies = service.load_cookies()

        # Assert - MANDATORY
        assert cookies == {}

    def test_load_cookies_with_valid_data(self, temp_cookie_file, sample_cookie_data):
        """Test load_cookies() with valid data - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # Write sample data to file
        with open(temp_cookie_file, "w", encoding="utf-8") as f:
            json.dump(sample_cookie_data, f)

        service = CookiePersistenceService(temp_cookie_file)

        # Act - MANDATORY
        cookies = service.load_cookies()

        # Assert - MANDATORY
        assert "example.com" in cookies
        assert "session_id" in cookies["example.com"]
        assert "user_pref" in cookies["example.com"]

    def test_filter_expired_cookies(
        self, temp_cookie_file, sample_cookie_data, expired_cookie_data
    ):
        """Test _filter_expired_cookies() removes expired - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        service = CookiePersistenceService(temp_cookie_file)
        # Combine valid and expired cookies
        mixed_data = {
            "example.com": {
                **sample_cookie_data["example.com"],
                **expired_cookie_data["example.com"],
            }
        }

        # Act - MANDATORY
        filtered = service._filter_expired_cookies(mixed_data)

        # Assert - MANDATORY
        assert "example.com" in filtered
        assert "session_id" in filtered["example.com"]  # Valid cookie kept
        assert "user_pref" in filtered["example.com"]  # Valid cookie kept
        assert "expired_cookie" not in filtered["example.com"]  # Expired removed

    def test_filter_expired_cookies_session_cookies_kept(
        self, temp_cookie_file, sample_cookie_data
    ):
        """Test session cookies (expires=None) are kept - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        service = CookiePersistenceService(temp_cookie_file)

        # Act - MANDATORY
        filtered = service._filter_expired_cookies(sample_cookie_data)

        # Assert - MANDATORY
        assert "user_pref" in filtered["example.com"]  # Session cookie kept

    def test_save_cookies_with_cookie_jar(self, temp_cookie_file, mock_cookie_jar):
        """Test save_cookies() with cookie jar - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        service = CookiePersistenceService(temp_cookie_file)

        # Act - MANDATORY
        service.save_cookies(mock_cookie_jar)

        # Assert - MANDATORY
        assert temp_cookie_file.exists()

        # Verify file contains cookie data
        with open(temp_cookie_file, encoding="utf-8") as f:
            saved_data = json.load(f)
        assert "example.com" in saved_data

    def test_save_cookies_no_cookie_jar(self, temp_cookie_file):
        """Test save_cookies() with None cookie jar - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        service = CookiePersistenceService(temp_cookie_file)

        # Act - MANDATORY
        service.save_cookies(None)

        # Assert - MANDATORY
        assert not temp_cookie_file.exists()  # No file should be created

    def test_extract_cookie_data(self, temp_cookie_file, mock_cookie_jar):
        """Test _extract_cookie_data() from cookie jar - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        service = CookiePersistenceService(temp_cookie_file)

        # Act - MANDATORY
        cookie_data = service._extract_cookie_data(mock_cookie_jar)

        # Assert - MANDATORY
        assert "example.com" in cookie_data
        assert "cookie1" in cookie_data["example.com"]
        assert "cookie2" in cookie_data["example.com"]
        assert cookie_data["example.com"]["cookie1"]["value"] == "value1"
        assert cookie_data["example.com"]["cookie2"]["value"] == "value2"

    def test_extract_cookie_data_skips_invalid_cookies(self, temp_cookie_file):
        """Test _extract_cookie_data() skips invalid cookies - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        service = CookiePersistenceService(temp_cookie_file)
        jar = MagicMock(spec=aiohttp.CookieJar)
        # Cookie with no domain or name
        invalid_cookie = {"value": "test"}
        jar.__iter__ = MagicMock(return_value=iter([invalid_cookie]))

        # Act - MANDATORY
        cookie_data = service._extract_cookie_data(jar)

        # Assert - MANDATORY
        assert cookie_data == {}  # Invalid cookie should be skipped

    def test_load_cookies_into_jar(self, temp_cookie_file, sample_cookie_data):
        """Test load_cookies_into_jar() - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # Write sample data to file
        with open(temp_cookie_file, "w", encoding="utf-8") as f:
            json.dump(sample_cookie_data, f)

        service = CookiePersistenceService(temp_cookie_file)
        jar = MagicMock(spec=aiohttp.CookieJar)
        jar.update_cookies = MagicMock()

        # Act - MANDATORY
        service.load_cookies_into_jar(jar, "example.com")

        # Assert - MANDATORY
        jar.update_cookies.assert_called()  # Cookies should be loaded

    def test_load_cookies_into_jar_domain_matching(self, temp_cookie_file):
        """Test domain matching in load_cookies_into_jar() - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        cookie_data = {
            "example.com": {
                "cookie1": {
                    "name": "cookie1",
                    "value": "value1",
                    "domain": "example.com",
                    "path": "/",
                    "expires": None,
                    "secure": False,
                    "httponly": False,
                }
            },
            "other.com": {
                "cookie2": {
                    "name": "cookie2",
                    "value": "value2",
                    "domain": "other.com",
                    "path": "/",
                    "expires": None,
                    "secure": False,
                    "httponly": False,
                }
            },
        }

        with open(temp_cookie_file, "w", encoding="utf-8") as f:
            json.dump(cookie_data, f)

        service = CookiePersistenceService(temp_cookie_file)
        jar = MagicMock(spec=aiohttp.CookieJar)
        jar.update_cookies = MagicMock()

        # Act - MANDATORY
        service.load_cookies_into_jar(jar, "example.com")

        # Assert - MANDATORY
        # Only example.com cookies should be loaded
        jar.update_cookies.assert_called()

    def test_load_cookies_into_jar_subdomain_matching(self, temp_cookie_file):
        """Test subdomain matching in load_cookies_into_jar() - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        cookie_data = {
            ".example.com": {  # Cookie for all subdomains
                "cookie1": {
                    "name": "cookie1",
                    "value": "value1",
                    "domain": ".example.com",
                    "path": "/",
                    "expires": None,
                    "secure": False,
                    "httponly": False,
                }
            }
        }

        with open(temp_cookie_file, "w", encoding="utf-8") as f:
            json.dump(cookie_data, f)

        service = CookiePersistenceService(temp_cookie_file)
        jar = MagicMock(spec=aiohttp.CookieJar)
        jar.update_cookies = MagicMock()

        # Act - MANDATORY
        service.load_cookies_into_jar(jar, "sub.example.com")

        # Assert - MANDATORY
        # Should match subdomain
        jar.update_cookies.assert_called()

    def test_save_cookies_creates_proper_structure(self, temp_cookie_file, mock_cookie_jar):
        """Test save_cookies() creates proper JSON structure - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        service = CookiePersistenceService(temp_cookie_file)

        # Act - MANDATORY
        service.save_cookies(mock_cookie_jar)

        # Assert - MANDATORY
        with open(temp_cookie_file, encoding="utf-8") as f:
            saved_data = json.load(f)

        # Verify structure
        assert isinstance(saved_data, dict)
        for domain, cookies in saved_data.items():
            assert isinstance(cookies, dict)
            for name, cookie in cookies.items():
                assert "name" in cookie
                assert "value" in cookie
                assert "domain" in cookie
                assert "path" in cookie


# ============================================================================
# MANDATORY Performance Benchmarks
# ============================================================================


@pytest.mark.performance
@pytest.mark.unit
class TestCookiePersistenceServicePerformance:
    """MANDATORY performance tests for cookie persistence operations."""

    def test_save_cookies_performance(self, temp_cookie_file, mock_cookie_jar):
        """MANDATORY performance test - cookie saving speed."""
        # Arrange - MANDATORY
        service = CookiePersistenceService(temp_cookie_file)
        iterations = 100

        # Act - MANDATORY
        start_time = time.perf_counter()

        for _ in range(iterations):
            service.save_cookies(mock_cookie_jar)

        end_time = time.perf_counter()
        execution_time = end_time - start_time

        # Assert - MANDATORY
        avg_time = execution_time / iterations
        assert avg_time < 0.1  # <100ms per save
        assert execution_time < 10.0  # Total <10s for 100 saves

    def test_load_cookies_performance(self, temp_cookie_file, sample_cookie_data):
        """MANDATORY performance test - cookie loading speed."""
        # Arrange - MANDATORY
        # Write sample data
        with open(temp_cookie_file, "w", encoding="utf-8") as f:
            json.dump(sample_cookie_data, f)

        service = CookiePersistenceService(temp_cookie_file)
        iterations = 100

        # Act - MANDATORY
        start_time = time.perf_counter()

        for _ in range(iterations):
            service.load_cookies()

        end_time = time.perf_counter()
        execution_time = end_time - start_time

        # Assert - MANDATORY
        avg_time = execution_time / iterations
        assert avg_time < 0.01  # <10ms per load
        assert execution_time < 1.0  # Total <1s for 100 loads

    def test_filter_expired_cookies_performance(self, temp_cookie_file):
        """MANDATORY performance test - cookie filtering speed."""
        # Arrange - MANDATORY
        service = CookiePersistenceService(temp_cookie_file)
        # Create large cookie dataset
        large_cookie_data = {
            f"domain{i}.com": {
                f"cookie{j}": {
                    "name": f"cookie{j}",
                    "value": f"value{j}",
                    "domain": f"domain{i}.com",
                    "path": "/",
                    "expires": time.time() + 3600 if j % 2 == 0 else time.time() - 3600,
                    "secure": False,
                    "httponly": False,
                }
                for j in range(10)
            }
            for i in range(10)
        }

        # Act - MANDATORY
        start_time = time.perf_counter()

        filtered = service._filter_expired_cookies(large_cookie_data)

        end_time = time.perf_counter()
        execution_time = end_time - start_time

        # Assert - MANDATORY
        assert execution_time < 0.1  # Should complete in <100ms
        assert len(filtered) > 0  # Should have filtered some cookies
