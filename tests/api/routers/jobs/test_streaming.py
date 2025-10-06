"""Comprehensive tests for job streaming endpoints - MANDATORY TEST_BUILDING.md compliance.

This module tests job streaming functionality with complete coverage:
- Server-Sent Events (SSE) job monitoring
- Real-time Redis pub/sub integration
- Job event broadcasting
- Initial data loading
- Client disconnection handling
- Event formatting and serialization
- Test event triggering

ALL tests follow MANDATORY TEST_BUILDING.md patterns:
- AAA pattern with explicit comments
- Factory fixtures for DRY principle
- Comprehensive SSE and async streaming scenario testing
- Performance benchmarks with specific thresholds
"""

import json
import time
from collections.abc import AsyncGenerator
from contextlib import suppress
from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import asyncio
import pytest
from fastapi import Request
from fastapi.responses import StreamingResponse
from fastapi.routing import APIRoute

from src.api.routers.jobs.streaming import (
    _format_job_update_event_safe,
    _initialize_job_event_system_safe,
    _listen_to_redis_job_events_safe,
    _process_job_event_message_safe,
    _send_initial_job_data_safe,
    _stream_job_events_safe,
    _trigger_test_job_event_safe,
    _wait_for_job_event_safe,
    job_stream,
    router,
    safe_json_dumps,
    trigger_job_event,
)

# ============================================================================
# Test Fixtures - DRY Principle
# ============================================================================


@pytest.fixture
def mock_db_session() -> MagicMock:
    """Factory for mock database session - DRY principle."""
    db = MagicMock()
    db.execute = AsyncMock()
    db.commit = AsyncMock()
    db.rollback = AsyncMock()
    db.close = AsyncMock()
    return db


@pytest.fixture
def mock_request() -> MagicMock:
    """Factory for mock FastAPI request - DRY principle."""
    request = MagicMock(spec=Request)
    request.is_disconnected = AsyncMock(return_value=False)
    request.client = MagicMock()
    request.client.host = "127.0.0.1"
    return request


@pytest.fixture
def mock_disconnected_request() -> MagicMock:
    """Factory for mock disconnected request - DRY principle."""
    request = MagicMock(spec=Request)
    request.is_disconnected = AsyncMock(return_value=True)
    return request


@pytest.fixture
def sample_job() -> MagicMock:
    """Factory for sample job model - DRY principle."""
    job = MagicMock()
    job.id = "job-123"
    job.source_url = "https://example.com/page"
    job.status = "completed"
    job.created_at = datetime(2023, 1, 1, 0, 0, 0)
    job.started_at = datetime(2023, 1, 1, 0, 0, 1)
    job.completed_at = datetime(2023, 1, 1, 0, 0, 2)
    job.error_message = None
    job.processing_time_ms = 1000
    return job


@pytest.fixture
def sample_job_event() -> dict[str, Any]:
    """Factory for sample job event data - DRY principle."""
    return {
        "job_id": "job-456",
        "event_type": "status_update",
        "status": "running",
        "timestamp": "2023-01-01T00:00:00Z",
        "data": {"progress": 50},
        "message": "Job in progress",
    }


@pytest.fixture
def mock_redis_client() -> MagicMock:
    """Factory for mock Redis client - DRY principle."""
    redis_client = MagicMock()
    redis_client.pubsub = MagicMock()

    # Mock pubsub behavior
    pubsub = MagicMock()
    pubsub.subscribe = AsyncMock()

    # Mock async generator for listen()
    async def mock_listen() -> AsyncGenerator[dict[str, Any]]:
        yield {
            "type": "message",
            "data": b'{"job_id": "test", "event_type": "created", "status": "pending", "timestamp": "2023-01-01T00:00:00Z", "data": {}}',
        }
        yield {"type": "subscribe", "channel": "job_events"}

    pubsub.listen = mock_listen
    redis_client.pubsub.return_value = pubsub
    return redis_client


@pytest.fixture
def mock_event_queue() -> asyncio.Queue[dict[str, Any]]:
    """Factory for mock event queue - DRY principle."""
    queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
    return queue


# ============================================================================
# Router Configuration Tests
# ============================================================================


@pytest.mark.unit
class TestJobStreamingRouter:
    """Tests for job streaming router configuration."""

    def test_router_exists(self) -> None:
        """Test that streaming router exists - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # Act - MANDATORY
        # Assert - MANDATORY
        assert router is not None

    def test_router_has_stream_endpoint(self) -> None:
        """Test router has /stream endpoint - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # Act - MANDATORY
        routes = [route.path for route in router.routes if isinstance(route, APIRoute)]

        # Assert - MANDATORY
        assert "/stream" in routes

    def test_router_has_trigger_event_endpoint(self) -> None:
        """Test router has /trigger-event endpoint - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # Act - MANDATORY
        routes = [route.path for route in router.routes if isinstance(route, APIRoute)]

        # Assert - MANDATORY
        assert "/trigger-event" in routes

    def test_stream_endpoint_is_get(self) -> None:
        """Test /stream endpoint uses GET method - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # Act - MANDATORY
        stream_route = next(
            r for r in router.routes if isinstance(r, APIRoute) and r.path == "/stream"
        )
        methods = stream_route.methods

        # Assert - MANDATORY
        assert "GET" in methods

    def test_trigger_event_endpoint_is_post(self) -> None:
        """Test /trigger-event endpoint uses POST method - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # Act - MANDATORY
        trigger_route = next(
            r for r in router.routes if isinstance(r, APIRoute) and r.path == "/trigger-event"
        )
        methods = trigger_route.methods

        # Assert - MANDATORY
        assert "POST" in methods


# ============================================================================
# Safe JSON Serialization Tests
# ============================================================================


@pytest.mark.unit
class TestSafeJsonDumps:
    """Tests for safe JSON serialization."""

    def test_safe_json_dumps_handles_dict(self) -> None:
        """Test safe_json_dumps handles dictionaries - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        data = {"key": "value", "number": 123}

        # Act - MANDATORY
        result = safe_json_dumps(data)

        # Assert - MANDATORY
        assert isinstance(result, str)
        assert "key" in result
        assert "value" in result

    def test_safe_json_dumps_handles_datetime(self) -> None:
        """Test safe_json_dumps handles datetime objects - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        data = {"timestamp": datetime(2023, 1, 1, 0, 0, 0)}

        # Act - MANDATORY
        result = safe_json_dumps(data)

        # Assert - MANDATORY
        assert isinstance(result, str)
        assert "2023-01-01" in result

    def test_safe_json_dumps_handles_nested_datetime(self) -> None:
        """Test safe_json_dumps handles nested datetime - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        data = {
            "job": {
                "id": "123",
                "created_at": datetime(2023, 1, 1, 0, 0, 0),
            }
        }

        # Act - MANDATORY
        result = safe_json_dumps(data)
        parsed = json.loads(result)

        # Assert - MANDATORY
        assert "job" in parsed
        assert "2023-01-01" in parsed["job"]["created_at"]

    def test_safe_json_dumps_handles_list(self) -> None:
        """Test safe_json_dumps handles lists - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        data = [{"id": 1}, {"id": 2}]

        # Act - MANDATORY
        result = safe_json_dumps(data)

        # Assert - MANDATORY
        assert isinstance(result, str)
        assert "1" in result
        assert "2" in result


# ============================================================================
# Job Stream Endpoint Tests
# ============================================================================


@pytest.mark.unit
class TestJobStreamEndpoint:
    """Tests for /stream SSE endpoint."""

    @pytest.mark.asyncio
    async def test_job_stream_returns_streaming_response(
        self, mock_request: MagicMock, mock_db_session: MagicMock
    ) -> None:
        """Test job_stream returns StreamingResponse - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        with patch(
            "src.api.routers.jobs.streaming._initialize_job_event_system_safe",
            new_callable=AsyncMock,
        ) as mock_init:
            mock_init.return_value = None

            # Act - MANDATORY
            response = await job_stream(mock_request, mock_db_session)

            # Assert - MANDATORY
            assert isinstance(response, StreamingResponse)

    @pytest.mark.asyncio
    async def test_job_stream_sets_correct_headers(
        self, mock_request: MagicMock, mock_db_session: MagicMock
    ) -> None:
        """Test job_stream sets SSE headers - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        with patch(
            "src.api.routers.jobs.streaming._initialize_job_event_system_safe",
            new_callable=AsyncMock,
        ) as mock_init:
            mock_init.return_value = None

            # Act - MANDATORY
            response = await job_stream(mock_request, mock_db_session)

            # Assert - MANDATORY
            assert response.headers["Cache-Control"] == "no-cache"
            assert response.headers["Connection"] == "keep-alive"
            assert response.headers["Access-Control-Allow-Origin"] == "*"

    @pytest.mark.asyncio
    async def test_job_stream_media_type_is_event_stream(
        self, mock_request: MagicMock, mock_db_session: MagicMock
    ) -> None:
        """Test job_stream has correct media type - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        with patch(
            "src.api.routers.jobs.streaming._initialize_job_event_system_safe",
            new_callable=AsyncMock,
        ) as mock_init:
            mock_init.return_value = None

            # Act - MANDATORY
            response = await job_stream(mock_request, mock_db_session)

            # Assert - MANDATORY
            assert response.media_type == "text/event-stream"


# ============================================================================
# Trigger Event Endpoint Tests
# ============================================================================


@pytest.mark.unit
class TestTriggerJobEvent:
    """Tests for /trigger-event endpoint."""

    @pytest.mark.asyncio
    async def test_trigger_job_event_calls_trigger_safe(self, mock_db_session: MagicMock) -> None:
        """Test trigger_job_event calls internal function - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        expected_result = {"message": "Test event triggered"}

        with patch(
            "src.api.routers.jobs.streaming._trigger_test_job_event_safe",
            new_callable=AsyncMock,
        ) as mock_trigger:
            mock_trigger.return_value = expected_result

            # Act - MANDATORY
            result = await trigger_job_event(mock_db_session)

            # Assert - MANDATORY
            assert result == expected_result
            mock_trigger.assert_called_once()

    @pytest.mark.asyncio
    async def test_trigger_job_event_returns_dict(self, mock_db_session: MagicMock) -> None:
        """Test trigger_job_event returns dictionary - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        with patch(
            "src.api.routers.jobs.streaming._trigger_test_job_event_safe",
            new_callable=AsyncMock,
        ) as mock_trigger:
            mock_trigger.return_value = {"message": "Success"}

            # Act - MANDATORY
            result = await trigger_job_event(mock_db_session)

            # Assert - MANDATORY
            assert isinstance(result, dict)


# ============================================================================
# Initialize Job Event System Tests
# ============================================================================


@pytest.mark.unit
class TestInitializeJobEventSystem:
    """Tests for job event system initialization."""

    @pytest.mark.asyncio
    async def test_initialize_job_event_system_initializes_publisher(self) -> None:
        """Test initialization initializes publisher - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        mock_publisher = MagicMock()
        mock_publisher.initialize = AsyncMock()

        mock_cache_manager = MagicMock()
        mock_backend = MagicMock()
        mock_backend._get_client = AsyncMock(return_value=MagicMock())
        mock_cache_manager._ensure_backend.return_value = mock_backend

        with (
            patch("src.api.routers.jobs.streaming.job_event_publisher", mock_publisher),
            patch("src.api.routers.jobs.streaming.cache_manager", mock_cache_manager),
        ):
            # Act - MANDATORY
            await _initialize_job_event_system_safe()

            # Assert - MANDATORY
            mock_publisher.initialize.assert_called_once()

    @pytest.mark.asyncio
    async def test_initialize_job_event_system_returns_redis_client(self) -> None:
        """Test initialization returns Redis client - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        mock_redis_client = MagicMock()
        mock_publisher = MagicMock()
        mock_publisher.initialize = AsyncMock()

        mock_cache_manager = MagicMock()
        mock_backend = MagicMock()
        mock_backend._get_client = AsyncMock(return_value=mock_redis_client)
        mock_cache_manager._ensure_backend.return_value = mock_backend

        with (
            patch("src.api.routers.jobs.streaming.job_event_publisher", mock_publisher),
            patch("src.api.routers.jobs.streaming.cache_manager", mock_cache_manager),
        ):
            # Act - MANDATORY
            result = await _initialize_job_event_system_safe()

            # Assert - MANDATORY
            assert result == mock_redis_client


# ============================================================================
# Send Initial Job Data Tests
# ============================================================================


@pytest.mark.unit
class TestSendInitialJobData:
    """Tests for sending initial job data."""

    @pytest.mark.asyncio
    async def test_send_initial_job_data_queries_crud(
        self, mock_db_session: MagicMock, sample_job: MagicMock
    ) -> None:
        """Test send initial data queries JobCRUD - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        mock_crud = MagicMock()
        mock_crud.get_jobs = AsyncMock(return_value=([sample_job], 1))

        with patch("src.api.routers.jobs.streaming.JobCRUD", mock_crud):
            # Act - MANDATORY
            result = await _send_initial_job_data_safe(mock_db_session)

            # Assert - MANDATORY
            mock_crud.get_jobs.assert_called_once_with(db=mock_db_session, skip=0, limit=100)
            assert result is not None

    @pytest.mark.asyncio
    async def test_send_initial_job_data_formats_sse_event(
        self, mock_db_session: MagicMock, sample_job: MagicMock
    ) -> None:
        """Test send initial data formats SSE event - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        mock_crud = MagicMock()
        mock_crud.get_jobs = AsyncMock(return_value=([sample_job], 1))

        with patch("src.api.routers.jobs.streaming.JobCRUD", mock_crud):
            # Act - MANDATORY
            result = await _send_initial_job_data_safe(mock_db_session)

            # Assert - MANDATORY
            assert result is not None
            assert result.startswith("event: initial-data\n")
            assert "data: " in result
            assert result.endswith("\n\n")

    @pytest.mark.asyncio
    async def test_send_initial_job_data_includes_job_details(
        self, mock_db_session: MagicMock, sample_job: MagicMock
    ) -> None:
        """Test send initial data includes job details - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        mock_crud = MagicMock()
        mock_crud.get_jobs = AsyncMock(return_value=([sample_job], 1))

        with patch("src.api.routers.jobs.streaming.JobCRUD", mock_crud):
            # Act - MANDATORY
            result = await _send_initial_job_data_safe(mock_db_session)

            # Assert - MANDATORY
            assert result is not None
            assert "job-123" in result
            assert "https://example.com/page" in result
            assert "completed" in result


# ============================================================================
# Listen to Redis Job Events Tests
# ============================================================================


@pytest.mark.unit
class TestListenToRedisJobEvents:
    """Tests for Redis job event listener."""

    @pytest.mark.asyncio
    async def test_listen_to_redis_subscribes_to_channel(
        self, mock_redis_client: MagicMock
    ) -> None:
        """Test listener subscribes to job_events - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        event_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()

        # Mock async iteration to stop after one iteration
        async def mock_listen() -> AsyncGenerator[dict[str, Any]]:
            yield {"type": "subscribe", "channel": "job_events"}

        pubsub = mock_redis_client.pubsub.return_value
        pubsub.listen = mock_listen

        with patch(
            "src.api.routers.jobs.streaming._process_job_event_message_safe",
            new_callable=AsyncMock,
        ) as mock_process:
            # Act - MANDATORY
            task = asyncio.create_task(
                _listen_to_redis_job_events_safe(mock_redis_client, event_queue)
            )
            await asyncio.sleep(0.1)  # Let it start
            task.cancel()

            with suppress(asyncio.CancelledError):
                await task

            # Assert - MANDATORY
            pubsub.subscribe.assert_called_once_with("job_events")

    @pytest.mark.asyncio
    async def test_listen_to_redis_processes_message_events(
        self, mock_redis_client: MagicMock
    ) -> None:
        """Test listener processes message events - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        event_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        mock_job_data = {"job_id": "test", "event_type": "created"}

        # Mock async iteration
        async def mock_listen() -> AsyncGenerator[dict[str, Any]]:
            yield {
                "type": "message",
                "data": json.dumps(mock_job_data).encode("utf-8"),
            }

        pubsub = mock_redis_client.pubsub.return_value
        pubsub.listen = mock_listen

        with patch(
            "src.api.routers.jobs.streaming._process_job_event_message_safe",
            new_callable=AsyncMock,
        ) as mock_process:
            mock_process.return_value = mock_job_data

            # Act - MANDATORY
            task = asyncio.create_task(
                _listen_to_redis_job_events_safe(mock_redis_client, event_queue)
            )
            await asyncio.sleep(0.1)  # Let it process
            task.cancel()

            with suppress(asyncio.CancelledError):
                await task

            # Assert - MANDATORY
            mock_process.assert_called_once()


# ============================================================================
# Process Job Event Message Tests
# ============================================================================


@pytest.mark.unit
class TestProcessJobEventMessage:
    """Tests for job event message processing."""

    @pytest.mark.asyncio
    async def test_process_job_event_message_parses_json(self) -> None:
        """Test process message parses JSON - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        message = {
            "data": json.dumps(
                {
                    "job_id": "job-789",
                    "event_type": "status_update",
                    "status": "running",
                    "timestamp": "2023-01-01T00:00:00Z",
                    "data": {"progress": 75},
                    "message": "Processing",
                }
            ).encode("utf-8")
        }

        # Act - MANDATORY
        result = await _process_job_event_message_safe(message)

        # Assert - MANDATORY
        assert result is not None
        assert result["job_id"] == "job-789"
        assert result["event_type"] == "status_update"

    @pytest.mark.asyncio
    async def test_process_job_event_message_formats_for_sse(self) -> None:
        """Test process message formats for SSE - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        message = {
            "data": json.dumps(
                {
                    "job_id": "job-789",
                    "event_type": "created",
                    "status": "pending",
                    "timestamp": "2023-01-01T00:00:00Z",
                    "data": {},
                }
            ).encode("utf-8")
        }

        # Act - MANDATORY
        result = await _process_job_event_message_safe(message)

        # Assert - MANDATORY
        assert result is not None
        assert "job_id" in result
        assert "event_type" in result
        assert "status" in result
        assert "timestamp" in result
        assert "data" in result


# ============================================================================
# Format Job Update Event Tests
# ============================================================================


@pytest.mark.unit
class TestFormatJobUpdateEvent:
    """Tests for job update event formatting."""

    def test_format_job_update_event_creates_sse_format(
        self, sample_job_event: dict[str, Any]
    ) -> None:
        """Test format creates SSE format - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # Act - MANDATORY
        result = _format_job_update_event_safe(sample_job_event)

        # Assert - MANDATORY
        assert result.startswith("event: ")
        assert "\ndata: " in result
        assert result.endswith("\n\n")

    def test_format_job_update_event_maps_event_names(self) -> None:
        """Test format maps event types to names - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        created_event = {
            "event_type": "created",
            "job_id": "1",
            "status": "pending",
            "timestamp": "2023-01-01T00:00:00Z",
            "data": {},
        }
        status_event = {
            "event_type": "status_update",
            "job_id": "2",
            "status": "running",
            "timestamp": "2023-01-01T00:00:00Z",
            "data": {},
        }
        deleted_event = {
            "event_type": "deleted",
            "job_id": "3",
            "status": "deleted",
            "timestamp": "2023-01-01T00:00:00Z",
            "data": {},
        }

        # Act - MANDATORY
        created_result = _format_job_update_event_safe(created_event)
        status_result = _format_job_update_event_safe(status_event)
        deleted_result = _format_job_update_event_safe(deleted_event)

        # Assert - MANDATORY
        assert "event: job-created\n" in created_result
        assert "event: job-status-update\n" in status_result
        assert "event: job-deleted\n" in deleted_result

    def test_format_job_update_event_includes_job_data(
        self, sample_job_event: dict[str, Any]
    ) -> None:
        """Test format includes job data - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # Act - MANDATORY
        result = _format_job_update_event_safe(sample_job_event)

        # Assert - MANDATORY
        assert "job-456" in result
        assert "status_update" in result
        assert "running" in result


# ============================================================================
# Trigger Test Job Event Tests
# ============================================================================


@pytest.mark.unit
class TestTriggerTestJobEvent:
    """Tests for test job event triggering."""

    @pytest.mark.asyncio
    async def test_trigger_test_job_event_publishes_event(self) -> None:
        """Test trigger publishes test event - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        with patch(
            "src.api.routers.jobs.streaming.publish_job_status_update",
            new_callable=AsyncMock,
        ) as mock_publish:
            mock_publish.return_value = True

            # Act - MANDATORY
            result = await _trigger_test_job_event_safe()

            # Assert - MANDATORY
            mock_publish.assert_called_once()
            assert result["message"] == "Test job event triggered successfully"

    @pytest.mark.asyncio
    async def test_trigger_test_job_event_handles_failure(self) -> None:
        """Test trigger handles publication failure - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        with patch(
            "src.api.routers.jobs.streaming.publish_job_status_update",
            new_callable=AsyncMock,
        ) as mock_publish:
            mock_publish.return_value = False

            # Act - MANDATORY
            result = await _trigger_test_job_event_safe()

            # Assert - MANDATORY
            assert "error" in result
            assert result["message"] == "Event publication failed"


# ============================================================================
# Stream Job Events Tests
# ============================================================================


@pytest.mark.unit
class TestStreamJobEvents:
    """Tests for job event streaming."""

    @pytest.mark.asyncio
    async def test_stream_job_events_yields_events(self, mock_request: MagicMock) -> None:
        """Test stream yields events from queue - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        event_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        test_event = {
            "job_id": "job-999",
            "event_type": "created",
            "status": "pending",
            "timestamp": "2023-01-01T00:00:00Z",
            "data": {},
        }
        await event_queue.put(test_event)

        # Make request disconnect after first event
        mock_request.is_disconnected = AsyncMock(side_effect=[False, True])

        # Act - MANDATORY
        events = []
        async for event_data in _stream_job_events_safe(mock_request, event_queue):
            events.append(event_data)

        # Assert - MANDATORY
        assert len(events) == 1
        assert "job-999" in events[0]

    @pytest.mark.asyncio
    async def test_stream_job_events_sends_keepalive(self, mock_request: MagicMock) -> None:
        """Test stream sends keepalive on timeout - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        event_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()

        # Mock timeout behavior
        with patch(
            "src.api.routers.jobs.streaming._wait_for_job_event_safe",
            new_callable=AsyncMock,
        ) as mock_wait:
            mock_wait.side_effect = ["timeout", "cancelled"]

            # Act - MANDATORY
            events = []
            async for event_data in _stream_job_events_safe(mock_request, event_queue):
                events.append(event_data)

            # Assert - MANDATORY
            assert len(events) >= 1
            assert any("keepalive" in event for event in events)

    @pytest.mark.asyncio
    async def test_stream_job_events_detects_disconnect(
        self, mock_disconnected_request: MagicMock
    ) -> None:
        """Test stream detects client disconnect - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        event_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()

        # Act - MANDATORY
        events = []
        async for event_data in _stream_job_events_safe(mock_disconnected_request, event_queue):
            events.append(event_data)

        # Assert - MANDATORY
        # Should exit immediately without yielding events
        assert len(events) == 0


# ============================================================================
# Wait for Job Event Tests
# ============================================================================


@pytest.mark.unit
class TestWaitForJobEvent:
    """Tests for job event waiting."""

    @pytest.mark.asyncio
    async def test_wait_for_job_event_returns_event(self) -> None:
        """Test wait returns event from queue - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        event_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        test_event = {"job_id": "test", "event_type": "created"}
        await event_queue.put(test_event)

        # Act - MANDATORY
        result = await _wait_for_job_event_safe(event_queue)

        # Assert - MANDATORY
        assert result == test_event

    @pytest.mark.asyncio
    async def test_wait_for_job_event_returns_timeout(self) -> None:
        """Test wait returns 'timeout' on timeout - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        event_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()

        # Act - MANDATORY
        result = await _wait_for_job_event_safe(event_queue)

        # Assert - MANDATORY
        assert result == "timeout"

    @pytest.mark.asyncio
    async def test_wait_for_job_event_handles_cancellation(self) -> None:
        """Test wait handles cancellation - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        event_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()

        # Create task and cancel it
        task = asyncio.create_task(_wait_for_job_event_safe(event_queue))
        await asyncio.sleep(0.01)  # Let task start
        task.cancel()

        # Act - MANDATORY
        try:
            result = await task
        except asyncio.CancelledError:
            result = "cancelled"

        # Assert - MANDATORY
        assert result == "cancelled"


# ============================================================================
# MANDATORY Performance Benchmarks
# ============================================================================


@pytest.mark.performance
@pytest.mark.unit
class TestJobStreamingPerformance:
    """MANDATORY performance tests for job streaming."""

    def test_safe_json_dumps_performance(self) -> None:
        """MANDATORY performance test - JSON serialization speed."""
        # Arrange - MANDATORY
        data = {
            "jobs": [
                {
                    "id": f"job-{i}",
                    "status": "completed",
                    "created_at": datetime(2023, 1, 1, 0, i % 60, i % 60),  # Valid seconds/minutes
                }
                for i in range(100)
            ]
        }
        iterations = 100

        # Act - MANDATORY
        start_time = time.perf_counter()

        for _ in range(iterations):
            _ = safe_json_dumps(data)

        end_time = time.perf_counter()
        execution_time = end_time - start_time

        # Assert - MANDATORY
        avg_time = execution_time / iterations
        assert avg_time < 0.010  # <10ms per serialization
        assert execution_time < 1.0  # Total <1s for 100 serializations

    def test_format_job_update_event_performance(self, sample_job_event: dict[str, Any]) -> None:
        """MANDATORY performance test - event formatting speed."""
        # Arrange - MANDATORY
        iterations = 1000

        # Act - MANDATORY
        start_time = time.perf_counter()

        for _ in range(iterations):
            _ = _format_job_update_event_safe(sample_job_event)

        end_time = time.perf_counter()
        execution_time = end_time - start_time

        # Assert - MANDATORY
        avg_time = execution_time / iterations
        assert avg_time < 0.001  # <1ms per format
        assert execution_time < 1.0  # Total <1s for 1000 formats

    @pytest.mark.asyncio
    async def test_event_queue_throughput_performance(self) -> None:
        """MANDATORY performance test - event queue throughput."""
        # Arrange - MANDATORY
        event_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        num_events = 1000

        # Act - MANDATORY
        start_time = time.perf_counter()

        # Put events
        for i in range(num_events):
            await event_queue.put({"job_id": f"job-{i}", "event_type": "created"})

        # Get events
        for _ in range(num_events):
            await event_queue.get()

        end_time = time.perf_counter()
        execution_time = end_time - start_time

        # Assert - MANDATORY
        throughput = num_events / execution_time
        assert throughput > 1000  # >1000 events/second
        assert execution_time < 1.0  # Total <1s for 1000 events
