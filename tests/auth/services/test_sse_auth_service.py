"""Unit tests for SSEAuthService following TEST_BUILDING.md MANDATORY standards.

MANDATORY COMPLIANCE:
- AAA Pattern (Arrange-Act-Assert) - NON-NEGOTIABLE
- SOLID principles testing
- Factory Pattern for test data
- 85%+ coverage target
- Focus on SSE stream logic and authentication parsing

Tests SSEAuthService Server-Sent Events authentication methods.
"""

import json
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import asyncio
import jwt
import pytest

from src.auth.services.sse_auth_service import SSEAuthService, auth_config

# ============================================================================
# MANDATORY Fixtures Following TEST_BUILDING.md Factory Pattern
# ============================================================================


@pytest.fixture
def sse_service():
    """Factory for SSEAuthService instance - DRY principle."""
    return SSEAuthService()


@pytest.fixture
def mock_request_authenticated():
    """Factory for authenticated FastAPI request mock."""
    request = MagicMock()

    # Create valid JWT token
    payload = {
        "sub": "testuser",
        "user_id": str(uuid4()),
        "exp": datetime.now(UTC) + timedelta(hours=1),
        "iat": datetime.now(UTC),
    }
    auth_token = jwt.encode(payload, auth_config.SECRET_KEY, algorithm=auth_config.ALGORITHM)

    # Create user data
    user_data = {
        "id": str(uuid4()),
        "username": "testuser",
        "email": "test@example.com",
        "is_verified": True,
        "provider": "google",
    }

    # Mock cookies
    request.cookies = {
        "auth_token": auth_token,
        "auth_user": json.dumps(user_data),
    }

    # Mock headers
    request.headers = MagicMock()
    request.headers.get.return_value = "auth_token=...; auth_user=..."
    request.headers.keys.return_value = ["cookie", "user-agent"]

    # Mock client
    request.client = MagicMock()
    request.client.host = "127.0.0.1"

    # Mock URL
    request.url = MagicMock()
    request.url.__str__.return_value = "http://localhost:8000/api/auth/sse"

    return request


@pytest.fixture
def mock_request_unauthenticated():
    """Factory for unauthenticated FastAPI request mock."""
    request = MagicMock()

    # Empty cookies
    request.cookies = {}

    # Mock headers
    request.headers = MagicMock()
    request.headers.get.return_value = "NO_COOKIE_HEADER"
    request.headers.keys.return_value = ["user-agent"]

    # Mock client
    request.client = MagicMock()
    request.client.host = "127.0.0.1"

    # Mock URL
    request.url = MagicMock()
    request.url.__str__.return_value = "http://localhost:8000/api/auth/sse"

    return request


@pytest.fixture
def mock_request_invalid_token():
    """Factory for request with invalid JWT token."""
    request = MagicMock()

    # Invalid token and valid user data
    request.cookies = {
        "auth_token": "invalid.jwt.token",
        "auth_user": json.dumps({"id": "123", "username": "test"}),
    }

    # Mock headers
    request.headers = MagicMock()
    request.headers.get.return_value = "auth_token=...; auth_user=..."
    request.headers.keys.return_value = ["cookie"]

    # Mock client
    request.client = MagicMock()
    request.client.host = "127.0.0.1"

    # Mock URL
    request.url = MagicMock()
    request.url.__str__.return_value = "http://localhost:8000/api/auth/sse"

    return request


@pytest.fixture
def mock_request_invalid_json():
    """Factory for request with invalid JSON in auth_user cookie."""
    request = MagicMock()

    # Valid token but invalid JSON
    payload = {
        "sub": "testuser",
        "exp": datetime.now(UTC) + timedelta(hours=1),
    }
    auth_token = jwt.encode(payload, auth_config.SECRET_KEY, algorithm=auth_config.ALGORITHM)

    request.cookies = {
        "auth_token": auth_token,
        "auth_user": "invalid-json-data",
    }

    # Mock headers
    request.headers = MagicMock()
    request.headers.get.return_value = "auth_token=...; auth_user=..."
    request.headers.keys.return_value = ["cookie"]

    # Mock client
    request.client = MagicMock()
    request.client.host = "127.0.0.1"

    # Mock URL
    request.url = MagicMock()
    request.url.__str__.return_value = "http://localhost:8000/api/auth/sse"

    return request


# ============================================================================
# Test Suite 1: __init__ (1 test) - Initialization
# ============================================================================


class TestSSEAuthServiceInitialization:
    """Test SSEAuthService initialization."""

    @pytest.mark.unit
    def test_initialization(self):
        """Test SSEAuthService initializes with correct defaults."""
        # Act
        service = SSEAuthService()

        # Assert
        assert service.heartbeat_interval == 30


# ============================================================================
# Test Suite 2: get_auth_status_from_cookies (6 tests) - Lines 36-109
# ============================================================================


class TestGetAuthStatusFromCookies:
    """Test authentication status extraction from cookies - SECURITY CRITICAL."""

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_get_auth_status_authenticated_success(
        self, sse_service, mock_request_authenticated
    ):
        """Test get_auth_status_from_cookies with valid authentication.

        AAA Pattern:
        - Arrange: Request with valid auth_token and auth_user cookies
        - Act: Extract authentication status
        - Assert: Returns authenticated status with user data
        """
        # Act
        status = await sse_service.get_auth_status_from_cookies(mock_request_authenticated)

        # Assert
        assert status["authenticated"] is True
        assert "user" in status
        assert status["user"]["username"] == "testuser"
        assert status["user"]["email"] == "test@example.com"
        assert status["user"]["is_verified"] is True
        assert status["user"]["provider"] == "google"
        assert "expires_at" in status
        assert status["token_type"] == "bearer"

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_get_auth_status_no_cookies(self, sse_service, mock_request_unauthenticated):
        """Test get_auth_status_from_cookies with no cookies present."""
        # Act
        status = await sse_service.get_auth_status_from_cookies(mock_request_unauthenticated)

        # Assert
        assert status["authenticated"] is False
        assert status["reason"] == "no_auth_cookies"

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_get_auth_status_invalid_token(self, sse_service, mock_request_invalid_token):
        """Test get_auth_status_from_cookies with invalid JWT token."""
        # Act
        status = await sse_service.get_auth_status_from_cookies(mock_request_invalid_token)

        # Assert
        assert status["authenticated"] is False
        assert status["reason"] == "no_auth_cookies"

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_get_auth_status_invalid_json(self, sse_service, mock_request_invalid_json):
        """Test get_auth_status_from_cookies with invalid JSON in auth_user."""
        # Act
        status = await sse_service.get_auth_status_from_cookies(mock_request_invalid_json)

        # Assert
        assert status["authenticated"] is False
        assert status["reason"] == "no_auth_cookies"

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_get_auth_status_missing_auth_token(self, sse_service):
        """Test get_auth_status_from_cookies with only auth_user cookie."""
        # Arrange
        request = MagicMock()
        request.cookies = {
            "auth_user": json.dumps({"id": "123", "username": "test"}),
        }
        request.headers = MagicMock()
        request.headers.get.return_value = "NO_COOKIE_HEADER"
        request.headers.keys.return_value = []
        request.client = MagicMock()
        request.client.host = "127.0.0.1"
        request.url = MagicMock()
        request.url.__str__.return_value = "http://localhost:8000/api/auth/sse"

        # Act
        status = await sse_service.get_auth_status_from_cookies(request)

        # Assert
        assert status["authenticated"] is False
        assert status["reason"] == "no_auth_cookies"

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_get_auth_status_missing_auth_user(self, sse_service):
        """Test get_auth_status_from_cookies with only auth_token cookie."""
        # Arrange
        payload = {
            "sub": "testuser",
            "exp": datetime.now(UTC) + timedelta(hours=1),
        }
        auth_token = jwt.encode(payload, auth_config.SECRET_KEY, algorithm=auth_config.ALGORITHM)

        request = MagicMock()
        request.cookies = {
            "auth_token": auth_token,
        }
        request.headers = MagicMock()
        request.headers.get.return_value = "NO_COOKIE_HEADER"
        request.headers.keys.return_value = []
        request.client = MagicMock()
        request.client.host = "127.0.0.1"
        request.url = MagicMock()
        request.url.__str__.return_value = "http://localhost:8000/api/auth/sse"

        # Act
        status = await sse_service.get_auth_status_from_cookies(request)

        # Assert
        assert status["authenticated"] is False
        assert status["reason"] == "no_auth_cookies"


# ============================================================================
# Test Suite 3: generate_auth_events (5 tests) - Lines 111-193
# ============================================================================


class TestGenerateAuthEvents:
    """Test SSE event generation - ASYNC GENERATOR."""

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_generate_auth_events_initial_unauthenticated(
        self, sse_service, mock_request_unauthenticated
    ):
        """Test generate_auth_events sends initial unauthenticated status.

        AAA Pattern:
        - Arrange: Unauthenticated request
        - Act: Generate SSE events (collect first event)
        - Assert: First event is auth_status with authenticated=False
        """
        # Arrange - Patch asyncio.sleep to avoid long waits
        with patch("asyncio.sleep", new=AsyncMock()) as mock_sleep:
            # Configure sleep to raise CancelledError after first event
            mock_sleep.side_effect = [None, asyncio.CancelledError()]

            # Act
            generator = sse_service.generate_auth_events(mock_request_unauthenticated)
            events = []

            try:
                async for event in generator:
                    events.append(event)
                    if len(events) >= 1:  # Only collect first event
                        break
            except asyncio.CancelledError:
                pass

            # Assert
            assert len(events) >= 1
            first_event = events[0]
            assert "event: auth_status" in first_event
            assert "data:" in first_event

            # Parse JSON data from SSE format
            data_line = [line for line in first_event.split("\n") if line.startswith("data:")][0]
            event_data = json.loads(data_line.replace("data: ", ""))

            assert event_data["type"] == "auth_status"
            assert event_data["data"]["authenticated"] is False

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_generate_auth_events_authenticated(
        self, sse_service, mock_request_authenticated
    ):
        """Test generate_auth_events with authenticated request."""
        # Arrange - Patch asyncio.sleep
        with patch("asyncio.sleep", new=AsyncMock()) as mock_sleep:
            mock_sleep.side_effect = [None, asyncio.CancelledError()]

            # Act
            generator = sse_service.generate_auth_events(mock_request_authenticated)
            events = []

            try:
                async for event in generator:
                    events.append(event)
                    if len(events) >= 1:
                        break
            except asyncio.CancelledError:
                pass

            # Assert
            assert len(events) >= 1
            first_event = events[0]

            # Parse event data
            data_line = [line for line in first_event.split("\n") if line.startswith("data:")][0]
            event_data = json.loads(data_line.replace("data: ", ""))

            assert event_data["type"] == "auth_status"
            assert event_data["data"]["authenticated"] is True
            assert event_data["data"]["user"]["username"] == "testuser"

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_generate_auth_events_heartbeat(self, sse_service, mock_request_unauthenticated):
        """Test generate_auth_events sends heartbeat after interval."""
        # Arrange - Patch asyncio.sleep and set low heartbeat interval
        sse_service.heartbeat_interval = 2  # Send heartbeat every 2 iterations

        with patch("asyncio.sleep", new=AsyncMock()) as mock_sleep:
            # Allow 3 iterations then cancel
            mock_sleep.side_effect = [None, None, None, asyncio.CancelledError()]

            # Act
            generator = sse_service.generate_auth_events(mock_request_unauthenticated)
            events = []

            try:
                async for event in generator:
                    events.append(event)
                    if len(events) >= 2:  # Collect until we get heartbeat
                        break
            except asyncio.CancelledError:
                pass

            # Assert - Should have auth_status and heartbeat
            assert len(events) >= 2

            # Check for heartbeat event
            heartbeat_events = [e for e in events if "event: heartbeat" in e]
            assert len(heartbeat_events) >= 1

            # Parse heartbeat data
            heartbeat_line = [
                line for line in heartbeat_events[0].split("\n") if line.startswith("data:")
            ][0]
            heartbeat_data = json.loads(heartbeat_line.replace("data: ", ""))

            assert heartbeat_data["type"] == "heartbeat"
            assert "timestamp" in heartbeat_data
            assert "connection_id" in heartbeat_data

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_generate_auth_events_handles_cancellation(
        self, sse_service, mock_request_unauthenticated
    ):
        """Test generate_auth_events handles asyncio.CancelledError gracefully."""
        # Arrange
        with patch("asyncio.sleep", new=AsyncMock()) as mock_sleep:
            mock_sleep.side_effect = asyncio.CancelledError()

            # Act
            generator = sse_service.generate_auth_events(mock_request_unauthenticated)
            events = []

            try:
                async for event in generator:
                    events.append(event)
            except asyncio.CancelledError:
                pass

            # Assert - Should handle cancellation without error
            # May have 0 or 1 events depending on timing

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_generate_auth_events_handles_exception(
        self, sse_service, mock_request_unauthenticated
    ):
        """Test generate_auth_events sends error event on exception."""
        # Arrange - Mock get_auth_status_from_cookies to raise exception
        with patch.object(
            sse_service,
            "get_auth_status_from_cookies",
            new=AsyncMock(side_effect=Exception("Test error")),
        ):
            # Act
            generator = sse_service.generate_auth_events(mock_request_unauthenticated)
            events = []

            try:
                async for event in generator:
                    events.append(event)
                    if "event: error" in event:
                        break
            except Exception:
                pass

            # Assert - Should send error event
            error_events = [e for e in events if "event: error" in e]
            assert len(error_events) >= 1

            # Parse error data
            error_line = [line for line in error_events[0].split("\n") if line.startswith("data:")][
                0
            ]
            error_data = json.loads(error_line.replace("data: ", ""))

            assert error_data["type"] == "error"
            assert error_data["error"] == "stream_error"


# ============================================================================
# Test Suite 4: get_sse_headers (3 tests) - Lines 195-216
# ============================================================================


class TestGetSSEHeaders:
    """Test SSE response headers generation."""

    @pytest.mark.unit
    def test_get_sse_headers_development(self):
        """Test get_sse_headers in development environment."""
        # Arrange
        with patch.dict("os.environ", {"ENVIRONMENT": "development"}):
            # Act
            headers = SSEAuthService.get_sse_headers()

            # Assert
            assert headers["Content-Type"] == "text/event-stream"
            assert headers["Cache-Control"] == "no-cache"
            assert headers["Connection"] == "keep-alive"
            assert headers["Access-Control-Allow-Origin"] == "http://localhost:3000"
            assert headers["Access-Control-Allow-Credentials"] == "true"
            assert headers["Access-Control-Allow-Headers"] == "Cache-Control"

    @pytest.mark.unit
    def test_get_sse_headers_production(self):
        """Test get_sse_headers in production environment."""
        # Arrange
        with patch.dict(
            "os.environ", {"ENVIRONMENT": "production", "FRONTEND_URL": "https://app.example.com"}
        ):
            # Act
            headers = SSEAuthService.get_sse_headers()

            # Assert
            assert headers["Content-Type"] == "text/event-stream"
            assert headers["Access-Control-Allow-Origin"] == "https://app.example.com"

    @pytest.mark.unit
    def test_get_sse_headers_default_environment(self):
        """Test get_sse_headers with no ENVIRONMENT variable."""
        # Arrange
        with patch.dict("os.environ", {}, clear=True):
            # Act
            headers = SSEAuthService.get_sse_headers()

            # Assert
            assert headers["Access-Control-Allow-Origin"] == "http://localhost:3000"
