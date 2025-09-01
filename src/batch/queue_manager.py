"""Priority-based batch queue management system for Phase 4B."""

import asyncio
import heapq
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any

import structlog

from src.batch.enhanced_processor import Priority, ProcessingResult
from src.database.service import DatabaseService

logger = structlog.get_logger(__name__)


class QueueStatus(Enum):
    """Status of the queue manager."""

    IDLE = "idle"
    PROCESSING = "processing"
    PAUSED = "paused"
    STOPPED = "stopped"


@dataclass(order=True)
class QueueItem:
    """Priority queue item for batch processing."""

    priority: int = field(compare=True)
    timestamp: datetime = field(compare=False)
    url: str = field(compare=False)
    batch_id: int | None = field(default=None, compare=False)
    metadata: dict[str, Any] = field(default_factory=dict, compare=False)
    retry_count: int = field(default=0, compare=False)

    def __post_init__(self):
        """Initialize timestamp if not provided."""
        if self.timestamp is None:
            self.timestamp = datetime.now(UTC)


class BatchQueueManager:
    """Manages prioritized batch processing queues with intelligent scheduling."""

    def __init__(
        self,
        database_service: DatabaseService,
        max_queue_size: int = 10000,
        processing_threads: int = 3,
        requeue_failed: bool = True,
        max_retries_per_item: int = 3,
    ):
        """Initialize the batch queue manager.

        Args:
            database_service: Database service for persistence
            max_queue_size: Maximum items in queue
            processing_threads: Number of concurrent processors
            requeue_failed: Whether to requeue failed items
            max_retries_per_item: Maximum retries per queue item
        """
        self.database_service = database_service
        self.max_queue_size = max_queue_size
        self.processing_threads = processing_threads
        self.requeue_failed = requeue_failed
        self.max_retries_per_item = max_retries_per_item

        # Priority queues for different priority levels
        self.urgent_queue: list[QueueItem] = []
        self.high_queue: list[QueueItem] = []
        self.normal_queue: list[QueueItem] = []
        self.low_queue: list[QueueItem] = []
        self.deferred_queue: list[QueueItem] = []

        # Queue management
        self.processing_items: set[str] = set()
        self.failed_items: dict[str, int] = {}  # URL -> retry count
        self.status = QueueStatus.IDLE
        self.total_processed = 0
        self.total_failed = 0

        # Processing control
        self.processing_lock = asyncio.Lock()
        self.queue_condition = asyncio.Condition()
        self.shutdown_event = asyncio.Event()

        logger.info(
            "Initialized batch queue manager",
            max_queue_size=max_queue_size,
            processing_threads=processing_threads,
        )

    async def add_item(
        self,
        url: str,
        priority: Priority = Priority.NORMAL,
        batch_id: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """Add an item to the appropriate priority queue.

        Args:
            url: URL to process
            priority: Processing priority
            batch_id: Optional batch ID
            metadata: Optional metadata

        Returns:
            True if item was added, False if queue is full
        """
        if self.get_queue_size() >= self.max_queue_size:
            logger.warning("Queue is full", size=self.max_queue_size)
            return False

        item = QueueItem(
            priority=priority.value,
            timestamp=datetime.now(UTC),
            url=url,
            batch_id=batch_id,
            metadata=metadata or {},
        )

        # Add to appropriate queue based on priority
        queue = self._get_queue_for_priority(priority)
        heapq.heappush(queue, item)

        # Notify waiting processors
        async with self.queue_condition:
            self.queue_condition.notify()

        logger.debug(
            "Added item to queue", url=url, priority=priority.name, queue_size=self.get_queue_size()
        )

        return True

    async def add_batch(
        self, urls: list[str], priority: Priority = Priority.NORMAL, batch_id: int | None = None
    ) -> int:
        """Add multiple URLs to the queue.

        Args:
            urls: List of URLs to add
            priority: Processing priority for all URLs
            batch_id: Optional batch ID

        Returns:
            Number of items successfully added
        """
        added = 0
        for url in urls:
            if await self.add_item(url, priority, batch_id):
                added += 1
            else:
                logger.warning("Could not add all items to queue", total=len(urls), added=added)
                break

        return added

    async def get_next_item(self) -> QueueItem | None:
        """Get the next highest priority item from the queue.

        Returns:
            Next QueueItem or None if queues are empty
        """
        async with self.processing_lock:
            # Check queues in priority order
            for queue in [
                self.urgent_queue,
                self.high_queue,
                self.normal_queue,
                self.low_queue,
                self.deferred_queue,
            ]:
                if queue:
                    item = heapq.heappop(queue)
                    self.processing_items.add(item.url)
                    return item

        return None

    async def mark_completed(self, item: QueueItem, result: ProcessingResult):
        """Mark an item as completed.

        Args:
            item: The completed queue item
            result: Processing result
        """
        self.processing_items.discard(item.url)

        if result.success:
            self.total_processed += 1
            # Remove from failed items if it was there
            self.failed_items.pop(item.url, None)
        else:
            self.total_failed += 1

            # Handle requeue logic
            if self.requeue_failed and item.retry_count < self.max_retries_per_item:
                item.retry_count += 1
                item.priority = min(
                    item.priority + 1,  # Lower priority on retry
                    Priority.LOW.value,
                )

                # Add back to queue with delay
                await asyncio.sleep(2**item.retry_count)  # Exponential backoff
                await self.add_item(item.url, Priority(item.priority), item.batch_id, item.metadata)

                logger.info("Requeued failed item", url=item.url, retry_count=item.retry_count)
            else:
                self.failed_items[item.url] = item.retry_count

    async def process_queue(self, processor_func):
        """Process items from the queue continuously.

        Args:
            processor_func: Async function to process each item
        """
        self.status = QueueStatus.PROCESSING

        while not self.shutdown_event.is_set():
            # Wait for items if queue is empty
            if self.is_empty():
                async with self.queue_condition:
                    await self.queue_condition.wait_for(
                        lambda: not self.is_empty() or self.shutdown_event.is_set()
                    )

            if self.shutdown_event.is_set():
                break

            # Get next item
            item = await self.get_next_item()
            if item:
                try:
                    # Process the item
                    result = await processor_func(item.url, Priority(item.priority))
                    await self.mark_completed(item, result)

                except Exception as e:
                    logger.error("Error processing queue item", url=item.url, error=str(e))
                    # Mark as failed
                    result = ProcessingResult(success=False, url=item.url, error=str(e))
                    await self.mark_completed(item, result)

        self.status = QueueStatus.STOPPED

    def pause(self):
        """Pause queue processing."""
        self.status = QueueStatus.PAUSED
        logger.info("Queue processing paused")

    def resume(self):
        """Resume queue processing."""
        if self.status == QueueStatus.PAUSED:
            self.status = QueueStatus.PROCESSING
            logger.info("Queue processing resumed")

    async def shutdown(self):
        """Gracefully shutdown the queue manager."""
        logger.info("Shutting down queue manager")
        self.shutdown_event.set()

        # Notify all waiting processors
        async with self.queue_condition:
            self.queue_condition.notify_all()

        # Wait for processing items to complete
        while self.processing_items:
            await asyncio.sleep(0.1)

        self.status = QueueStatus.STOPPED
        logger.info(
            "Queue manager shutdown complete",
            total_processed=self.total_processed,
            total_failed=self.total_failed,
        )

    def get_queue_size(self) -> int:
        """Get total number of items in all queues."""
        return (
            len(self.urgent_queue)
            + len(self.high_queue)
            + len(self.normal_queue)
            + len(self.low_queue)
            + len(self.deferred_queue)
        )

    def is_empty(self) -> bool:
        """Check if all queues are empty."""
        return self.get_queue_size() == 0

    def get_statistics(self) -> dict[str, Any]:
        """Get queue statistics.

        Returns:
            Dictionary with queue statistics
        """
        return {
            "status": self.status.value,
            "queue_sizes": {
                "urgent": len(self.urgent_queue),
                "high": len(self.high_queue),
                "normal": len(self.normal_queue),
                "low": len(self.low_queue),
                "deferred": len(self.deferred_queue),
                "total": self.get_queue_size(),
            },
            "processing": len(self.processing_items),
            "total_processed": self.total_processed,
            "total_failed": self.total_failed,
            "failed_items": len(self.failed_items),
            "success_rate": (
                (self.total_processed / (self.total_processed + self.total_failed) * 100)
                if (self.total_processed + self.total_failed) > 0
                else 0
            ),
        }

    def _get_queue_for_priority(self, priority: Priority) -> list[QueueItem]:
        """Get the queue for a given priority.

        Args:
            priority: Priority level

        Returns:
            The appropriate queue list
        """
        queue_map = {
            Priority.URGENT: self.urgent_queue,
            Priority.HIGH: self.high_queue,
            Priority.NORMAL: self.normal_queue,
            Priority.LOW: self.low_queue,
            Priority.DEFERRED: self.deferred_queue,
        }
        return queue_map.get(priority, self.normal_queue)

    async def rebalance_queues(self):
        """Rebalance queues based on age and priority."""
        current_time = datetime.now(UTC)

        # Move aged items to higher priority
        for source_queue, target_queue, age_threshold in [
            (self.normal_queue, self.high_queue, timedelta(hours=1)),
            (self.low_queue, self.normal_queue, timedelta(hours=2)),
            (self.deferred_queue, self.low_queue, timedelta(hours=4)),
        ]:
            aged_items = []

            # Find aged items
            for item in source_queue:
                age = current_time - item.timestamp
                if age > age_threshold:
                    aged_items.append(item)

            # Move aged items
            for item in aged_items:
                source_queue.remove(item)
                item.priority = max(item.priority - 1, Priority.URGENT.value)
                heapq.heappush(target_queue, item)

            if aged_items:
                logger.info(
                    "Rebalanced aged items",
                    count=len(aged_items),
                    from_queue=source_queue,
                    to_queue=target_queue,
                )

    async def persist_queue_state(self, filepath: str):
        """Save current queue state to file for recovery.

        Args:
            filepath: Path to save queue state
        """
        import json
        from datetime import datetime

        state = {
            "timestamp": datetime.now(UTC).isoformat(),
            "status": self.status.value,
            "statistics": self.get_statistics(),
            "queues": {
                "urgent": [self._item_to_dict(item) for item in self.urgent_queue],
                "high": [self._item_to_dict(item) for item in self.high_queue],
                "normal": [self._item_to_dict(item) for item in self.normal_queue],
                "low": [self._item_to_dict(item) for item in self.low_queue],
                "deferred": [self._item_to_dict(item) for item in self.deferred_queue],
            },
            "processing": list(self.processing_items),
            "failed": self.failed_items,
        }

        with open(filepath, "w") as f:
            json.dump(state, f, indent=2)

        logger.info("Persisted queue state", filepath=filepath)

    async def restore_queue_state(self, filepath: str):
        """Restore queue state from file.

        Args:
            filepath: Path to load queue state from
        """
        import json

        with open(filepath) as f:
            state = json.load(f)

        # Clear current queues
        self.urgent_queue.clear()
        self.high_queue.clear()
        self.normal_queue.clear()
        self.low_queue.clear()
        self.deferred_queue.clear()

        # Restore queues
        for priority_name, items in state["queues"].items():
            queue = getattr(self, f"{priority_name}_queue")
            for item_dict in items:
                item = self._dict_to_item(item_dict)
                heapq.heappush(queue, item)

        # Restore statistics
        self.total_processed = state["statistics"]["total_processed"]
        self.total_failed = state["statistics"]["total_failed"]
        self.failed_items = state.get("failed", {})

        logger.info("Restored queue state", filepath=filepath, items_restored=self.get_queue_size())

    def _item_to_dict(self, item: QueueItem) -> dict[str, Any]:
        """Convert QueueItem to dictionary.

        Args:
            item: QueueItem to convert

        Returns:
            Dictionary representation
        """
        return {
            "priority": item.priority,
            "timestamp": item.timestamp.isoformat(),
            "url": item.url,
            "batch_id": item.batch_id,
            "metadata": item.metadata,
            "retry_count": item.retry_count,
        }

    def _dict_to_item(self, data: dict[str, Any]) -> QueueItem:
        """Convert dictionary to QueueItem.

        Args:
            data: Dictionary to convert

        Returns:
            QueueItem instance
        """
        return QueueItem(
            priority=data["priority"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            url=data["url"],
            batch_id=data.get("batch_id"),
            metadata=data.get("metadata", {}),
            retry_count=data.get("retry_count", 0),
        )
