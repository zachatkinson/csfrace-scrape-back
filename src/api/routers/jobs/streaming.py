"""Job streaming operations following Single Responsibility Principle.

This module handles real-time job monitoring including:
- SSE job streaming (/stream)
- Job event testing (/trigger-event)
- Redis pub/sub integration for real-time updates
"""

import contextlib
import json
from collections.abc import AsyncGenerator
from typing import Any
from urllib.parse import urlparse

import asyncio
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from redis.asyncio import Redis

from src.core.decorators import api_error_handler
from src.core.logging_hierarchy import get_api_logger

from ....caching.manager import cache_manager
from ....monitoring.job_events import job_event_publisher, publish_job_status_update
from ...crud import JobCRUD
from ...dependencies import DBSession

logger = get_api_logger()

router = APIRouter()


def safe_json_dumps(data: Any) -> str:
    """JSON dumps with handling for non-serializable types."""

    def default_serializer(obj: Any) -> str:
        if hasattr(obj, "isoformat"):
            result: str = obj.isoformat()
            return result
        raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

    return json.dumps(data, default=default_serializer)


@router.get("/stream")
async def job_stream(request: Request, db: DBSession) -> StreamingResponse:
    """Server-Sent Events endpoint for real-time job monitoring.

    This endpoint provides event-driven job monitoring using Redis pub/sub.
    Streams job status changes, creation, deletion, and progress updates in real-time.

    Args:
        request: FastAPI request object for disconnect detection
        db: Database session for job queries

    Returns:
        StreamingResponse: SSE stream of job events
    """
    logger.info("Job SSE stream connection established")

    async def event_generator() -> AsyncGenerator[str]:
        """Generate SSE events from Redis job event stream."""

        # Initialize Redis connection for job events
        redis_client = await _initialize_job_event_system_safe()
        if redis_client is None:
            yield f"event: error\ndata: {safe_json_dumps({'error': 'Failed to initialize event system'})}\n\n"
            return

        # Send initial connection message
        connection_data = {
            "type": "connection",
            "message": "Real-time job monitoring connected",
            "timestamp": "2023-01-01T00:00:00Z",
        }
        yield f"event: connection\ndata: {safe_json_dumps(connection_data)}\n\n"
        logger.debug("Sent connection event")

        # Send initial job list as baseline
        initial_data_event = await _send_initial_job_data_safe(db)
        if initial_data_event:
            yield initial_data_event
        else:
            yield f"event: error\ndata: {safe_json_dumps({'error': 'Failed to get initial job data'})}\n\n"

        # Set up event listener for Redis pub/sub job events
        event_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()

        # Redis pub/sub listener for job events
        async def redis_job_listener() -> None:
            """Listen to Redis job_events channel for real-time updates."""
            await _listen_to_redis_job_events_safe(redis_client, event_queue)

        # Start Redis listener task
        listener_task = asyncio.create_task(redis_job_listener())
        logger.debug("Redis job listener task started")

        # Stream events from queue
        try:
            async for event_data in _stream_job_events_safe(request, event_queue):
                yield event_data
        finally:
            # Cleanup Redis listener task
            if "listener_task" in locals():
                listener_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await listener_task
                logger.debug("Redis listener task cancelled")

            logger.info("Job SSE stream cleanup completed")

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Cache-Control",
        },
    )


@router.post("/trigger-event")
async def trigger_job_event(db: DBSession) -> dict[str, Any]:  # noqa: ARG001
    """Manually trigger a job event for testing purposes.

    This endpoint allows testing the job event system by creating
    a test event that will be broadcast to all connected SSE clients.

    Args:
        db: Database session (required parameter but unused in test)

    Returns:
        Confirmation of event publication
    """
    logger.info("Triggering test job event")

    return await _trigger_test_job_event_safe()


@api_error_handler("initialize job event system")
async def _initialize_job_event_system_safe() -> Redis | None:
    """Safely initialize job event system."""
    await job_event_publisher.initialize()
    redis_client: Redis = await cache_manager._ensure_backend()._get_client()  # type: ignore[attr-defined]
    logger.debug("Job event system initialized successfully")
    return redis_client


@api_error_handler("send initial job data")
async def _send_initial_job_data_safe(db: DBSession) -> str | None:
    """Safely send initial job data."""
    jobs_result, total_jobs = await JobCRUD.get_jobs(db=db, skip=0, limit=100)
    logger.debug("Retrieved initial job data", total_jobs=total_jobs, returned=len(jobs_result))

    initial_data = {
        "type": "initial_data",
        "total_jobs": total_jobs,
        "jobs": [
            {
                "id": job.id,
                "url": job.source_url,
                "domain": urlparse(job.source_url).netloc,
                "status": job.status,
                "created_at": job.created_at.isoformat() if job.created_at else None,
                "started_at": job.started_at.isoformat() if job.started_at else None,
                "completed_at": job.completed_at.isoformat() if job.completed_at else None,
                "error_message": job.error_message,
                "success": job.status == "completed",
                "processing_time_ms": job.processing_time_ms,
            }
            for job in jobs_result
        ],
        "timestamp": "2023-01-01T00:00:00Z",
    }
    event_data = f"event: initial-data\ndata: {safe_json_dumps(initial_data)}\n\n"
    logger.debug("Sent initial job data")
    return event_data


@api_error_handler("listen to Redis job events")
async def _listen_to_redis_job_events_safe(
    redis_client: Redis, event_queue: asyncio.Queue[dict[str, Any]]
) -> None:
    """Safely listen to Redis job events."""
    pubsub = redis_client.pubsub()
    await pubsub.subscribe("job_events")
    logger.debug("Subscribed to job_events Redis channel")

    async for message in pubsub.listen():
        if message["type"] == "message":
            job_event_data = await _process_job_event_message_safe(message)
            if job_event_data:
                await event_queue.put(job_event_data)


@api_error_handler("process job event message")
async def _process_job_event_message_safe(message: dict[str, Any]) -> dict[str, Any] | None:
    """Safely process job event message."""
    # Parse job event data
    job_event_data = json.loads(message["data"].decode("utf-8"))

    # Format for SSE client
    job_update = {
        "job_id": job_event_data["job_id"],
        "event_type": job_event_data["event_type"],
        "status": job_event_data["status"],
        "timestamp": job_event_data["timestamp"],
        "data": job_event_data["data"],
        "message": job_event_data.get("message"),
    }

    logger.debug(
        "Job event queued",
        job_id=job_update["job_id"],
        event_type=job_update["event_type"],
    )
    return job_update


def _format_job_update_event_safe(job_update: dict[str, Any]) -> str:
    """Safely format job update event for SSE."""
    # Map event types to SSE event names
    event_name_map = {
        "created": "job-created",
        "status_update": "job-status-update",
        "progress": "job-progress",
        "deleted": "job-deleted",
        "error": "job-error",
    }

    event_name = event_name_map.get(job_update["event_type"], "job-update")
    event_data = f"event: {event_name}\ndata: {safe_json_dumps(job_update)}\n\n"

    logger.debug(
        "Job event sent to client",
        event_name=event_name,
        job_id=job_update["job_id"],
    )
    return event_data


@api_error_handler("trigger test job event")
async def _trigger_test_job_event_safe() -> dict[str, Any]:
    """Safely trigger test job event."""
    # Create a test job status update event
    success = await publish_job_status_update(
        job_id="test-job-123",
        old_status="pending",
        new_status="running",
        url="https://example.com",
        domain="example.com",
        error_message=None,
        processing_time_ms=None,
    )

    if success:
        logger.info("Test job event triggered successfully")
        return {
            "message": "Test job event triggered successfully",
            "event_type": "status_update",
            "timestamp": "2023-01-01T00:00:00Z",
        }
    else:
        logger.warning("Failed to publish test event")
        return {"error": "Failed to publish test event", "message": "Event publication failed"}


async def _stream_job_events_safe(
    request: Request, event_queue: asyncio.Queue[dict[str, Any]]
) -> AsyncGenerator[str]:
    """Safely stream job events from queue."""
    while True:
        # Check if client disconnected
        if await request.is_disconnected():
            logger.info("Job SSE client disconnected")
            break

        # Wait for events with timeout handling
        event_result = await _wait_for_job_event_safe(event_queue)

        if event_result == "timeout":
            # Send keepalive ping every 30 seconds
            yield f"event: keepalive\ndata: {safe_json_dumps({'timestamp': '2023-01-01T00:00:00Z'})}\n\n"
            logger.debug("Keepalive sent to client")
            continue
        elif event_result == "cancelled":
            logger.info("Job SSE stream cancelled")
            break
        elif event_result is None:
            # General error case handled by decorator
            yield f"event: error\ndata: {safe_json_dumps({'error': 'Job monitoring temporarily unavailable'})}\n\n"
            break
        else:
            # Valid job update received
            if isinstance(event_result, dict):
                event_data = _format_job_update_event_safe(event_result)
                yield event_data
            else:
                # Unexpected data type, send error event
                yield f"event: error\ndata: {safe_json_dumps({'error': 'Invalid event data received'})}\n\n"


async def _wait_for_job_event_safe(
    event_queue: asyncio.Queue[dict[str, Any]],
) -> dict[str, Any] | str | None:
    """Safely wait for job event with timeout handling."""
    # Handle timeout and cancellation as specific control flow, not general exceptions
    try:
        job_update = await asyncio.wait_for(event_queue.get(), timeout=30.0)
        return job_update
    except TimeoutError:
        return "timeout"
    except asyncio.CancelledError:
        return "cancelled"
