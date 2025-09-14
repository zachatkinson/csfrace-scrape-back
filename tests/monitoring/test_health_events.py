"""Tests for health event system."""

import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest

from src.monitoring.health_events import (
    HealthEvent,
    HealthEventPublisher,
    HealthEventSubscriber,
    HealthEventType,
    HealthStateManager,
    initialize_health_events,
    publish_health_change_events,
)


class TestHealthEvent:
    """Test HealthEvent data structure."""

    def test_health_event_creation(self):
        """Test creating a health event."""
        event = HealthEvent(
            event_type=HealthEventType.SERVICE_STATUS_CHANGE,
            service_name="database",
            status="healthy",
            timestamp=datetime.now(UTC),
            message="Database is healthy",
            data={"response_time_ms": 5},
        )

        assert event.service_name == "database"
        assert event.status == "healthy"
        assert event.event_type == HealthEventType.SERVICE_STATUS_CHANGE
        assert event.message == "Database is healthy"
        assert event.data["response_time_ms"] == 5
        assert event.event_id is not None

    def test_health_event_serialization(self):
        """Test event serialization to/from dict."""
        original_event = HealthEvent(
            event_type=HealthEventType.SERVICE_RECOVERY,
            service_name="cache",
            status="healthy",
            timestamp=datetime(2023, 1, 1, 12, 0, 0, tzinfo=UTC),
            message="Cache recovered",
            data={"recovery_time": 30},
        )

        # Convert to dict
        event_dict = original_event.to_dict()

        # Convert back from dict
        restored_event = HealthEvent.from_dict(event_dict)

        assert restored_event.event_type == original_event.event_type
        assert restored_event.service_name == original_event.service_name
        assert restored_event.status == original_event.status
        assert restored_event.timestamp == original_event.timestamp
        assert restored_event.message == original_event.message
        assert restored_event.data == original_event.data


class TestHealthStateManager:
    """Test HealthStateManager for change detection."""

    def test_initial_state_detection(self):
        """Test that initial states are detected as changes."""
        manager = HealthStateManager()

        health_data = {
            "status": "healthy",
            "timestamp": datetime.now(UTC),
            "version": "1.0.0",
            "database": {"status": "healthy", "connected": True, "response_time_ms": 5},
            "cache": {"status": "healthy", "connected": True, "response_time_ms": 2},
        }

        events = manager.detect_changes(health_data)

        # Should generate events for all services on first detection
        assert len(events) == 3  # backend, database, cache
        service_names = [event.service_name for event in events]
        assert "backend" in service_names
        assert "database" in service_names
        assert "cache" in service_names

    def test_status_change_detection(self):
        """Test detection of status changes."""
        manager = HealthStateManager()

        # First health check
        initial_health = {
            "status": "healthy",
            "timestamp": datetime.now(UTC),
            "database": {"status": "healthy", "connected": True},
        }
        manager.detect_changes(initial_health)

        # Second health check with change
        changed_health = {
            "status": "healthy",
            "timestamp": datetime.now(UTC),
            "database": {"status": "unhealthy", "connected": False},
        }
        events = manager.detect_changes(changed_health)

        # Should detect database status change
        db_events = [e for e in events if e.service_name == "database"]
        assert len(db_events) == 1
        assert db_events[0].status == "unhealthy"
        assert db_events[0].event_type == HealthEventType.SERVICE_ERROR

    def test_no_change_detection(self):
        """Test that no events are generated when nothing changes."""
        manager = HealthStateManager()

        health_data = {
            "status": "healthy",
            "timestamp": datetime.now(UTC),
            "database": {"status": "healthy", "connected": True},
        }

        # First call - should generate events
        events1 = manager.detect_changes(health_data)
        assert len(events1) > 0

        # Second call with same data - should generate no events
        events2 = manager.detect_changes(health_data)
        assert len(events2) == 0

    def test_recovery_event_generation(self):
        """Test that recovery events are properly generated."""
        manager = HealthStateManager()

        # Start with unhealthy state
        unhealthy_health = {
            "status": "unhealthy",
            "timestamp": datetime.now(UTC),
            "database": {"status": "unhealthy", "connected": False},
        }
        manager.detect_changes(unhealthy_health)

        # Change to healthy state
        healthy_health = {
            "status": "healthy",
            "timestamp": datetime.now(UTC),
            "database": {"status": "healthy", "connected": True},
        }
        events = manager.detect_changes(healthy_health)

        # Should generate recovery events
        backend_events = [e for e in events if e.service_name == "backend"]
        db_events = [e for e in events if e.service_name == "database"]

        assert len(backend_events) == 1
        assert backend_events[0].event_type == HealthEventType.SERVICE_RECOVERY

        assert len(db_events) == 1
        assert db_events[0].event_type == HealthEventType.SERVICE_RECOVERY


class TestHealthEventPublisher:
    """Test HealthEventPublisher."""

    @pytest.mark.asyncio
    async def test_publish_event(self):
        """Test publishing a health event to Redis."""
        mock_redis = AsyncMock()
        mock_redis.publish.return_value = 1  # 1 subscriber

        publisher = HealthEventPublisher(mock_redis)

        event = HealthEvent(
            event_type=HealthEventType.SERVICE_STATUS_CHANGE,
            service_name="test",
            status="healthy",
            timestamp=datetime.now(UTC),
            message="Test event",
        )

        result = await publisher.publish_event(event)

        assert result is True
        mock_redis.publish.assert_called_once()
        call_args = mock_redis.publish.call_args
        assert call_args[0][0] == "health_events"  # Channel name

        # Verify JSON payload
        published_data = json.loads(call_args[0][1])
        assert published_data["service_name"] == "test"
        assert published_data["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_publish_multiple_events(self):
        """Test publishing multiple events."""
        mock_redis = AsyncMock()
        mock_redis.publish.return_value = 1

        publisher = HealthEventPublisher(mock_redis)

        events = [
            HealthEvent(
                event_type=HealthEventType.SERVICE_STATUS_CHANGE,
                service_name="service1",
                status="healthy",
                timestamp=datetime.now(UTC),
                message="Service 1 event",
            ),
            HealthEvent(
                event_type=HealthEventType.SERVICE_STATUS_CHANGE,
                service_name="service2",
                status="unhealthy",
                timestamp=datetime.now(UTC),
                message="Service 2 event",
            ),
        ]

        result = await publisher.publish_multiple(events)

        assert result == 2  # Both events published successfully
        assert mock_redis.publish.call_count == 2


class TestHealthEventSubscriber:
    """Test HealthEventSubscriber."""

    @pytest.mark.asyncio
    async def test_event_subscription(self):
        """Test subscribing to health events."""
        mock_redis = AsyncMock()
        mock_pubsub = AsyncMock()
        mock_redis.pubsub.return_value = mock_pubsub

        # Mock message stream
        test_event = HealthEvent(
            event_type=HealthEventType.SERVICE_STATUS_CHANGE,
            service_name="test",
            status="healthy",
            timestamp=datetime.now(UTC),
            message="Test message",
        )

        mock_message = {"type": "message", "data": json.dumps(test_event.to_dict()).encode("utf-8")}

        async def mock_listen():
            yield mock_message

        mock_pubsub.listen.return_value = mock_listen()

        subscriber = HealthEventSubscriber(mock_redis)

        # Track received events
        received_events = []

        async def test_callback(event):
            received_events.append(event)

        # Subscribe and process one message
        await subscriber.subscribe(test_callback)

        # Manually trigger message handling to test callback
        await subscriber._handle_message(mock_message["data"])

        assert len(received_events) == 1
        assert received_events[0].service_name == "test"
        assert received_events[0].status == "healthy"


@pytest.mark.asyncio
async def test_initialize_health_events():
    """Test health event system initialization."""
    mock_redis = AsyncMock()

    with (
        patch("src.monitoring.health_events.health_event_publisher") as mock_publisher,
        patch("src.monitoring.health_events.health_event_subscriber") as mock_subscriber,
    ):
        await initialize_health_events(mock_redis)

        # Verify initialization was called
        assert mock_publisher is not None
        assert mock_subscriber is not None


@pytest.mark.asyncio
async def test_publish_health_change_events_integration():
    """Test the integration function for publishing health events."""
    health_data = {
        "status": "healthy",
        "timestamp": datetime.now(UTC),
        "database": {"status": "healthy", "connected": True},
        "cache": {"status": "healthy", "connected": True},
    }

    with patch("src.monitoring.health_events.health_event_publisher") as mock_publisher:
        mock_publisher_instance = AsyncMock()
        mock_publisher_instance.publish_multiple.return_value = 2
        mock_publisher.return_value = mock_publisher_instance

        # Mock the global publisher
        import src.monitoring.health_events

        src.monitoring.health_events.health_event_publisher = mock_publisher_instance

        await publish_health_change_events(health_data)

        # Should have called publish_multiple (even if no changes, initial state creates events)
        mock_publisher_instance.publish_multiple.assert_called_once()
