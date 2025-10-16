"""Job event system for real-time job status updates via SSE.

This module provides event-driven job monitoring using Redis pub/sub,
following the same pattern as health_events.py for consistency.
"""

from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, field_serializer

from src.core.decorators import monitoring_error_handler
from src.core.logging_hierarchy import get_monitoring_logger

from ..caching.manager import cache_manager

logger = get_monitoring_logger()


def _extract_title_from_url(url: str) -> str:
    """Extract a preliminary title from URL for immediate display.

    Generates a human-readable title from the URL path to show in the UI
    while the actual page title is being scraped.

    Args:
        url: Source URL to extract title from

    Returns:
        Human-readable title extracted from URL path
    """
    from urllib.parse import urlparse

    try:
        parsed_url = urlparse(url)
        path = parsed_url.path.strip("/")

        # Get last segment of path (e.g., "new-csf-jeep-wrangler")
        last_segment = path.split("/")[-1] if path else parsed_url.netloc

        # Convert hyphens/underscores to spaces and title case
        # e.g., "new-csf-jeep-wrangler" -> "New Csf Jeep Wrangler"
        title = last_segment.replace("-", " ").replace("_", " ").title()

        return title if title else "Untitled Page"
    except Exception:
        return "Untitled Page"


class JobEventType(Enum):
    """Types of job events that can be emitted."""

    CREATED = "created"
    STATUS_UPDATE = "status_update"
    PROGRESS = "progress"
    DELETED = "deleted"
    ERROR = "error"


class JobEvent(BaseModel):
    """Model for job events published to Redis."""

    job_id: str
    event_type: JobEventType
    status: str
    timestamp: datetime
    data: dict[str, Any]
    message: str | None = None

    # Pydantic V2: ConfigDict instead of class Config
    model_config = ConfigDict(
        # No need for json_encoders - using field_serializer instead
    )

    @field_serializer("timestamp")
    def serialize_timestamp(self, dt: datetime) -> str:
        """Serialize datetime to ISO format string."""
        return dt.isoformat()


class JobEventPublisher:
    """Publisher for job events using Redis pub/sub."""

    def __init__(self) -> None:
        """Initialize the job event publisher."""
        self._redis_client = None
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize Redis connection for job events."""
        if self._initialized:
            return

        await _initialize_redis_connection_safe(self)

    @monitoring_error_handler("publish job event")
    async def publish_job_event(
        self,
        job_id: str,
        event_type: JobEventType,
        status: str,
        data: dict[str, Any],
        message: str | None = None,
    ) -> bool:
        """Publish a job event to Redis.

        Args:
            job_id: Job identifier
            event_type: Type of event
            status: Job status
            data: Additional event data
            message: Optional message

        Returns:
            True if published successfully, False otherwise
        """
        if not self._initialized:
            await self.initialize()

        # Type guard: After initialization, _redis_client must be set
        if self._redis_client is None:
            raise RuntimeError("Redis client not initialized after initialization call")

        event = JobEvent(
            job_id=job_id,
            event_type=event_type,
            status=status,
            timestamp=datetime.now(UTC),
            data=data,
            message=message,
        )

        # Publish to Redis channel
        event_data = event.model_dump_json()
        await self._redis_client.publish("job_events", event_data)

        logger.debug(
            "Job event published", job_id=job_id, event_type=event_type.value, status=status
        )
        return True


@monitoring_error_handler("initialize Redis connection for job events")
async def _initialize_redis_connection_safe(publisher: JobEventPublisher) -> None:
    """Safely initialize Redis connection."""
    await cache_manager.initialize()
    publisher._redis_client = await cache_manager._ensure_backend()._get_client()  # type: ignore[attr-defined]
    publisher._initialized = True
    logger.info("Job event publisher initialized")


# Global job event publisher instance
job_event_publisher = JobEventPublisher()


async def publish_job_created(job_id: str, url: str, domain: str, status: str = "pending") -> bool:
    """Publish job created event.

    Args:
        job_id: Job identifier
        url: Source URL
        domain: Domain being scraped
        status: Initial job status

    Returns:
        True if published successfully
    """
    # Extract preliminary title from URL for immediate UI display
    title = _extract_title_from_url(url)

    return await job_event_publisher.publish_job_event(
        job_id=job_id,
        event_type=JobEventType.CREATED,
        status=status,
        data={
            "url": url,
            "domain": domain,
            "title": title,  # Include extracted title for immediate display
            "created_at": datetime.now(UTC).isoformat(),
        },
        message=f"Job created for {domain}",
    )


async def publish_job_status_update(
    job_id: str,
    old_status: str,
    new_status: str,
    url: str,
    domain: str,
    error_message: str | None = None,
    processing_time_ms: int | None = None,
    title: str | None = None,
    word_count: int | None = None,
    image_count: int | None = None,
) -> bool:
    """Publish job status update event.

    Args:
        job_id: Job identifier
        old_status: Previous status (kept as old_status for API compatibility)
        new_status: New status
        url: Source URL
        domain: Domain being scraped
        error_message: Error message if failed
        processing_time_ms: Processing time in milliseconds
        title: Actual scraped page title (if available)
        word_count: Word count from scraped content (if available)
        image_count: Image count from scraped content (if available)

    Returns:
        True if published successfully
    """
    data: dict[str, Any] = {
        "url": url,
        "domain": domain,
        "old_status": old_status,
        "new_status": new_status,
        "updated_at": datetime.now(UTC).isoformat(),
    }

    if error_message:
        data["error_message"] = error_message
    if processing_time_ms is not None:
        data["processing_time_ms"] = str(processing_time_ms)
    if title is not None:
        data["title"] = title
    if word_count is not None:
        data["word_count"] = word_count
    if image_count is not None:
        data["image_count"] = image_count

    message = f"Job status changed from {old_status} to {new_status}"
    if error_message:
        message += f": {error_message}"

    return await job_event_publisher.publish_job_event(
        job_id=job_id,
        event_type=JobEventType.STATUS_UPDATE,
        status=new_status,
        data=data,
        message=message,
    )


async def publish_job_progress(
    job_id: str, status: str, progress_percent: float, url: str, domain: str, current_step: str
) -> bool:
    """Publish job progress update event.

    Args:
        job_id: Job identifier
        status: Current status
        progress_percent: Progress percentage (0-100)
        url: Source URL
        domain: Domain being scraped
        current_step: Description of current processing step

    Returns:
        True if published successfully
    """
    return await job_event_publisher.publish_job_event(
        job_id=job_id,
        event_type=JobEventType.PROGRESS,
        status=status,
        data={
            "url": url,
            "domain": domain,
            "progress_percent": progress_percent,
            "current_step": current_step,
            "updated_at": datetime.now(UTC).isoformat(),
        },
        message=f"Job progress: {progress_percent:.1f}% - {current_step}",
    )


async def publish_job_deleted(job_id: str, url: str, domain: str) -> bool:
    """Publish job deleted event.

    Args:
        job_id: Job identifier
        url: Source URL that was being scraped
        domain: Domain that was being scraped

    Returns:
        True if published successfully
    """
    return await job_event_publisher.publish_job_event(
        job_id=job_id,
        event_type=JobEventType.DELETED,
        status="deleted",
        data={"url": url, "domain": domain, "deleted_at": datetime.now(UTC).isoformat()},
        message=f"Job deleted for {domain}",
    )


async def publish_job_error(
    job_id: str, status: str, error_message: str, error_type: str, url: str, domain: str
) -> bool:
    """Publish job error event.

    Args:
        job_id: Job identifier
        status: Current status (likely 'failed')
        error_message: Error description
        error_type: Type of error
        url: Source URL
        domain: Domain being scraped

    Returns:
        True if published successfully
    """
    return await job_event_publisher.publish_job_event(
        job_id=job_id,
        event_type=JobEventType.ERROR,
        status=status,
        data={
            "url": url,
            "domain": domain,
            "error_message": error_message,
            "error_type": error_type,
            "error_at": datetime.now(UTC).isoformat(),
        },
        message=f"Job error: {error_message}",
    )
