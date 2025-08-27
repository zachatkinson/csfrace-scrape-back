"""Tests for batch queue management system."""

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.batch.enhanced_processor import Priority, ProcessingResult
from src.batch.queue_manager import BatchQueueManager, QueueItem, QueueStatus
from src.database.service import DatabaseService


@pytest.fixture
def mock_database_service():
    """Create mock database service."""
    return MagicMock(spec=DatabaseService)


@pytest.fixture
def queue_manager(mock_database_service):
    """Create queue manager instance."""
    return BatchQueueManager(
        database_service=mock_database_service, max_queue_size=100, processing_threads=2
    )


@pytest.fixture
def sample_queue_item():
    """Create sample queue item."""
    return QueueItem(
        priority=Priority.NORMAL.value,
        timestamp=datetime.now(timezone.utc),
        url="https://example.com/test",
        batch_id=1,
        metadata={"test": "data"},
    )


class TestQueueItem:
    """Test QueueItem data class functionality."""

    def test_queue_item_creation(self):
        """Test creating a queue item."""
        item = QueueItem(
            priority=Priority.HIGH.value,
            timestamp=datetime.now(timezone.utc),
            url="https://example.com",
            batch_id=123,
            metadata={"key": "value"},
        )

        assert item.priority == Priority.HIGH.value
        assert item.url == "https://example.com"
        assert item.batch_id == 123
        assert item.metadata == {"key": "value"}
        assert item.retry_count == 0

    def test_queue_item_auto_timestamp(self):
        """Test that timestamp is set automatically if None."""
        item = QueueItem(
            priority=Priority.NORMAL.value,
            timestamp=None,  # Will be auto-set in __post_init__
            url="https://example.com",
        )

        assert item.timestamp is not None
        assert isinstance(item.timestamp, datetime)

    def test_queue_item_ordering(self):
        """Test that queue items are ordered by priority."""
        low_item = QueueItem(Priority.LOW.value, datetime.now(timezone.utc), "url1")
        high_item = QueueItem(Priority.HIGH.value, datetime.now(timezone.utc), "url2")

        # Lower numeric value = higher priority
        assert high_item < low_item


class TestBatchQueueManager:
    """Test BatchQueueManager functionality."""

    def test_initialization(self, mock_database_service):
        """Test queue manager initialization."""
        manager = BatchQueueManager(
            database_service=mock_database_service, max_queue_size=500, processing_threads=5
        )

        assert manager.max_queue_size == 500
        assert manager.processing_threads == 5
        assert manager.status == QueueStatus.IDLE
        assert manager.total_processed == 0
        assert manager.total_failed == 0
        assert len(manager.urgent_queue) == 0

    @pytest.mark.asyncio
    async def test_add_item_success(self, queue_manager):
        """Test successfully adding an item to the queue."""
        result = await queue_manager.add_item(
            url="https://example.com/test",
            priority=Priority.HIGH,
            batch_id=1,
            metadata={"test": "data"},
        )

        assert result is True
        assert queue_manager.get_queue_size() == 1
        assert len(queue_manager.high_queue) == 1

    @pytest.mark.asyncio
    async def test_add_item_queue_full(self, queue_manager):
        """Test adding item when queue is full."""
        queue_manager.max_queue_size = 1

        # Add first item (should succeed)
        result1 = await queue_manager.add_item("https://example.com/1")
        assert result1 is True

        # Add second item (should fail - queue full)
        result2 = await queue_manager.add_item("https://example.com/2")
        assert result2 is False

    @pytest.mark.asyncio
    async def test_add_batch(self, queue_manager):
        """Test adding multiple URLs to the queue."""
        urls = ["https://example.com/1", "https://example.com/2", "https://example.com/3"]

        added = await queue_manager.add_batch(urls, Priority.NORMAL, batch_id=1)

        assert added == 3
        assert queue_manager.get_queue_size() == 3

    @pytest.mark.asyncio
    async def test_add_batch_partial_success(self, queue_manager):
        """Test adding batch when queue becomes full partway through."""
        queue_manager.max_queue_size = 2
        urls = ["url1", "url2", "url3", "url4"]

        added = await queue_manager.add_batch(urls)

        assert added == 2  # Only first 2 could be added
        assert queue_manager.get_queue_size() == 2

    @pytest.mark.asyncio
    async def test_get_next_item_priority_order(self, queue_manager):
        """Test that items are retrieved in priority order."""
        # Add items in reverse priority order
        await queue_manager.add_item("low", Priority.LOW)
        await queue_manager.add_item("normal", Priority.NORMAL)
        await queue_manager.add_item("urgent", Priority.URGENT)
        await queue_manager.add_item("high", Priority.HIGH)

        # Should get urgent first
        item1 = await queue_manager.get_next_item()
        assert item1.url == "urgent"
        assert item1.priority == Priority.URGENT.value

        # Then high
        item2 = await queue_manager.get_next_item()
        assert item2.url == "high"

        # Then normal
        item3 = await queue_manager.get_next_item()
        assert item3.url == "normal"

        # Finally low
        item4 = await queue_manager.get_next_item()
        assert item4.url == "low"

    @pytest.mark.asyncio
    async def test_get_next_item_empty_queue(self, queue_manager):
        """Test getting item from empty queue."""
        item = await queue_manager.get_next_item()
        assert item is None

    @pytest.mark.asyncio
    async def test_mark_completed_success(self, queue_manager, sample_queue_item):
        """Test marking an item as successfully completed."""
        # Add item to processing set
        queue_manager.processing_items.add(sample_queue_item.url)

        result = ProcessingResult(success=True, url=sample_queue_item.url, data={"status": "ok"})

        await queue_manager.mark_completed(sample_queue_item, result)

        assert queue_manager.total_processed == 1
        assert queue_manager.total_failed == 0
        assert sample_queue_item.url not in queue_manager.processing_items

    @pytest.mark.asyncio
    async def test_mark_completed_failure_no_requeue(self, queue_manager, sample_queue_item):
        """Test marking item as failed without requeuing."""
        queue_manager.requeue_failed = False
        queue_manager.processing_items.add(sample_queue_item.url)

        result = ProcessingResult(success=False, url=sample_queue_item.url, error="Test error")

        await queue_manager.mark_completed(sample_queue_item, result)

        assert queue_manager.total_processed == 0
        assert queue_manager.total_failed == 1
        assert sample_queue_item.url in queue_manager.failed_items

    @pytest.mark.asyncio
    async def test_mark_completed_failure_with_requeue(self, queue_manager, sample_queue_item):
        """Test marking item as failed with requeuing."""
        queue_manager.requeue_failed = True
        queue_manager.max_retries_per_item = 3
        sample_queue_item.retry_count = 1  # Still under max retries

        queue_manager.processing_items.add(sample_queue_item.url)

        result = ProcessingResult(success=False, url=sample_queue_item.url, error="Test error")

        with patch("asyncio.sleep", new_callable=AsyncMock):
            await queue_manager.mark_completed(sample_queue_item, result)

        assert queue_manager.total_failed == 1
        # Item should be requeued (queue size should be 1)
        assert queue_manager.get_queue_size() == 1

    @pytest.mark.asyncio
    async def test_mark_completed_failure_max_retries_exceeded(
        self, queue_manager, sample_queue_item
    ):
        """Test marking item as failed when max retries exceeded."""
        queue_manager.requeue_failed = True
        queue_manager.max_retries_per_item = 2
        sample_queue_item.retry_count = 3  # Exceeds max retries

        queue_manager.processing_items.add(sample_queue_item.url)

        result = ProcessingResult(success=False, url=sample_queue_item.url, error="Test error")

        await queue_manager.mark_completed(sample_queue_item, result)

        assert queue_manager.total_failed == 1
        assert sample_queue_item.url in queue_manager.failed_items
        assert queue_manager.get_queue_size() == 0  # Not requeued

    @pytest.mark.asyncio
    async def test_process_queue_with_items(self, queue_manager):
        """Test processing queue with items."""
        # Add some items
        await queue_manager.add_item("url1", Priority.NORMAL)
        await queue_manager.add_item("url2", Priority.HIGH)

        processed_urls = []

        async def mock_processor(url, priority):
            processed_urls.append(url)
            return ProcessingResult(success=True, url=url)

        # Start processing task
        process_task = asyncio.create_task(queue_manager.process_queue(mock_processor))

        # Wait a bit for processing
        await asyncio.sleep(0.1)

        # Shutdown
        await queue_manager.shutdown()

        # Wait for task completion
        await process_task

        # Should have processed both URLs (high priority first)
        assert len(processed_urls) == 2
        assert "url2" in processed_urls  # High priority item
        assert "url1" in processed_urls  # Normal priority item

    @pytest.mark.asyncio
    async def test_process_queue_error_handling(self, queue_manager):
        """Test error handling during queue processing."""
        await queue_manager.add_item("error_url", Priority.NORMAL)

        async def failing_processor(url, priority):
            raise Exception("Processing error")

        process_task = asyncio.create_task(queue_manager.process_queue(failing_processor))

        # Wait a bit for processing
        await asyncio.sleep(0.1)

        await queue_manager.shutdown()
        await process_task

        # Should have recorded failure
        assert queue_manager.total_failed == 1

    def test_pause_resume(self, queue_manager):
        """Test pausing and resuming queue processing."""
        assert queue_manager.status == QueueStatus.IDLE

        queue_manager.pause()
        assert queue_manager.status == QueueStatus.PAUSED

        queue_manager.resume()
        assert queue_manager.status == QueueStatus.PROCESSING

        # Pausing already paused queue should remain paused
        queue_manager.pause()
        queue_manager.pause()
        assert queue_manager.status == QueueStatus.PAUSED

    @pytest.mark.asyncio
    async def test_shutdown(self, queue_manager):
        """Test graceful shutdown."""
        await queue_manager.add_item("test_url")

        await queue_manager.shutdown()

        assert queue_manager.status == QueueStatus.STOPPED
        assert queue_manager.shutdown_event.is_set()

    def test_get_queue_size(self, queue_manager):
        """Test getting total queue size."""
        assert queue_manager.get_queue_size() == 0
        assert queue_manager.is_empty() is True

        # Add items to different priority queues
        queue_manager.urgent_queue.append(QueueItem(1, datetime.now(timezone.utc), "url1"))
        queue_manager.normal_queue.append(QueueItem(3, datetime.now(timezone.utc), "url2"))
        queue_manager.low_queue.append(QueueItem(4, datetime.now(timezone.utc), "url3"))

        assert queue_manager.get_queue_size() == 3
        assert queue_manager.is_empty() is False

    def test_get_statistics(self, queue_manager):
        """Test getting queue statistics."""
        queue_manager.total_processed = 10
        queue_manager.total_failed = 2
        queue_manager.processing_items.add("processing_url")

        # Add some items to queues
        queue_manager.urgent_queue.append(QueueItem(1, datetime.now(timezone.utc), "url1"))
        queue_manager.high_queue.append(QueueItem(2, datetime.now(timezone.utc), "url2"))

        stats = queue_manager.get_statistics()

        assert stats["status"] == QueueStatus.IDLE.value
        assert stats["queue_sizes"]["urgent"] == 1
        assert stats["queue_sizes"]["high"] == 1
        assert stats["queue_sizes"]["total"] == 2
        assert stats["processing"] == 1
        assert stats["total_processed"] == 10
        assert stats["total_failed"] == 2
        assert stats["success_rate"] == 10 / 12 * 100  # 10/(10+2) * 100

    def test_get_statistics_no_processed_jobs(self, queue_manager):
        """Test statistics when no jobs processed."""
        stats = queue_manager.get_statistics()
        assert stats["success_rate"] == 0

    @pytest.mark.asyncio
    async def test_rebalance_queues(self, queue_manager):
        """Test queue rebalancing based on age."""
        from datetime import timedelta

        # Add old items to low priority queues
        old_time = datetime.now(timezone.utc) - timedelta(hours=3)
        old_item = QueueItem(priority=Priority.LOW.value, timestamp=old_time, url="old_url")
        queue_manager.low_queue.append(old_item)

        # Add recent item
        recent_item = QueueItem(
            priority=Priority.LOW.value, timestamp=datetime.now(timezone.utc), url="recent_url"
        )
        queue_manager.low_queue.append(recent_item)

        await queue_manager.rebalance_queues()

        # Old item should be moved to higher priority queue
        assert len(queue_manager.low_queue) == 1
        assert len(queue_manager.normal_queue) == 1

        # Verify the old item was moved and priority updated
        moved_item = queue_manager.normal_queue[0]
        assert moved_item.url == "old_url"
        assert moved_item.priority < Priority.LOW.value  # Higher priority (lower number)

    @pytest.mark.asyncio
    async def test_persist_and_restore_queue_state(self, queue_manager, tmp_path):
        """Test persisting and restoring queue state."""
        # Add items to queues
        await queue_manager.add_item("urgent_url", Priority.URGENT, batch_id=1)
        await queue_manager.add_item("normal_url", Priority.NORMAL, batch_id=2)

        queue_manager.total_processed = 5
        queue_manager.total_failed = 1
        queue_manager.failed_items = {"failed_url": 2}

        # Persist state
        state_file = tmp_path / "queue_state.json"
        await queue_manager.persist_queue_state(str(state_file))

        assert state_file.exists()

        # Create new queue manager and restore state
        new_queue_manager = BatchQueueManager(database_service=MagicMock(spec=DatabaseService))

        await new_queue_manager.restore_queue_state(str(state_file))

        # Verify state was restored
        assert new_queue_manager.get_queue_size() == 2
        assert new_queue_manager.total_processed == 5
        assert new_queue_manager.total_failed == 1
        assert new_queue_manager.failed_items == {"failed_url": 2}

        # Verify items were restored to correct queues
        assert len(new_queue_manager.urgent_queue) == 1
        assert len(new_queue_manager.normal_queue) == 1

    def test_get_queue_for_priority(self, queue_manager):
        """Test getting the correct queue for each priority level."""
        assert queue_manager._get_queue_for_priority(Priority.URGENT) is queue_manager.urgent_queue
        assert queue_manager._get_queue_for_priority(Priority.HIGH) is queue_manager.high_queue
        assert queue_manager._get_queue_for_priority(Priority.NORMAL) is queue_manager.normal_queue
        assert queue_manager._get_queue_for_priority(Priority.LOW) is queue_manager.low_queue
        assert (
            queue_manager._get_queue_for_priority(Priority.DEFERRED) is queue_manager.deferred_queue
        )

    def test_item_to_dict_and_dict_to_item(self, queue_manager, sample_queue_item):
        """Test serialization and deserialization of queue items."""
        # Convert to dict
        item_dict = queue_manager._item_to_dict(sample_queue_item)

        assert item_dict["url"] == sample_queue_item.url
        assert item_dict["priority"] == sample_queue_item.priority
        assert item_dict["batch_id"] == sample_queue_item.batch_id
        assert item_dict["metadata"] == sample_queue_item.metadata
        assert item_dict["retry_count"] == sample_queue_item.retry_count

        # Convert back to item
        restored_item = queue_manager._dict_to_item(item_dict)

        assert restored_item.url == sample_queue_item.url
        assert restored_item.priority == sample_queue_item.priority
        assert restored_item.batch_id == sample_queue_item.batch_id
        assert restored_item.metadata == sample_queue_item.metadata
        assert restored_item.retry_count == sample_queue_item.retry_count


@pytest.mark.asyncio
async def test_queue_manager_integration(mock_database_service):
    """Integration test for complete queue manager workflow."""
    manager = BatchQueueManager(
        database_service=mock_database_service, max_queue_size=10, processing_threads=2
    )

    # Add items with different priorities
    urls = [
        ("urgent_task", Priority.URGENT),
        ("normal_task1", Priority.NORMAL),
        ("high_task", Priority.HIGH),
        ("normal_task2", Priority.NORMAL),
        ("low_task", Priority.LOW),
    ]

    for url, priority in urls:
        await manager.add_item(url, priority)

    assert manager.get_queue_size() == 5

    # Process items and verify priority order
    processed_order = []

    async def processor(url, priority):
        processed_order.append(url)
        return ProcessingResult(success=True, url=url)

    # Process a few items manually to test order
    for _ in range(3):
        item = await manager.get_next_item()
        if item:
            result = await processor(item.url, Priority(item.priority))
            await manager.mark_completed(item, result)

    # Verify processing order (urgent, high, normal)
    expected_start = ["urgent_task", "high_task"]
    assert processed_order[:2] == expected_start

    # Verify statistics
    stats = manager.get_statistics()
    assert stats["total_processed"] == 3
    assert stats["total_failed"] == 0
    assert stats["queue_sizes"]["total"] == 2  # 2 items remaining
