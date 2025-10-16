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
from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from redis.asyncio import Redis

from src.auth.dependencies import get_current_user_from_cookie
from src.auth.models import User
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
async def job_stream(
    request: Request, db: DBSession, current_user: User = Depends(get_current_user_from_cookie)
) -> StreamingResponse:
    """Server-Sent Events endpoint for real-time job monitoring.

    This endpoint provides event-driven job monitoring using Redis pub/sub.
    Streams job status changes, creation, deletion, and progress updates in real-time.

    Args:
        request: FastAPI request object for disconnect detection
        db: Database session for job queries
        current_user: Authenticated user from cookie

    Returns:
        StreamingResponse: SSE stream of job events
    """
    logger.info("Job SSE stream connection established", user_id=current_user.id)

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

        # Send initial job list as baseline (filtered by authenticated user)
        initial_data_event = await _send_initial_job_data_safe(db, current_user.id)
        if initial_data_event:
            yield initial_data_event
        else:
            yield f"event: error\ndata: {safe_json_dumps({'error': 'Failed to get initial job data'})}\n\n"

        # Set up event listener for Redis pub/sub job events
        event_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()

        # Redis pub/sub listener for job events
        async def redis_job_listener() -> None:
            """Listen to Redis job_events channel for real-time updates."""
            await _listen_to_redis_job_events_safe(redis_client, event_queue, current_user.id)

        # Start Redis listener task
        listener_task = asyncio.create_task(redis_job_listener())
        logger.info("Redis job listener task started", user_id=current_user.id)

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
async def _send_initial_job_data_safe(db: DBSession, user_id: str) -> str | None:
    """Safely send initial job data filtered by user_id in optimized chunks.

    SSE Best Practice: Send data in manageable chunks instead of one massive payload.
    This prevents overwhelming the client and allows progressive rendering.
    """
    jobs_result, total_jobs = await JobCRUD.get_jobs(db=db, skip=0, limit=100, user_id=user_id)
    logger.debug(
        "Retrieved initial job data",
        total_jobs=total_jobs,
        returned=len(jobs_result),
        user_id=user_id,
    )

    # Helper function to extract title from URL when content_results not available
    def extract_title_from_url(url: str) -> str:
        """Extract preliminary title from URL."""
        try:
            parsed = urlparse(url)
            path = parsed.path.strip("/")
            last_segment = path.split("/")[-1] if path else parsed.netloc
            return last_segment.replace("-", " ").replace("_", " ").title() or "Untitled Page"
        except Exception:
            return "Untitled Page"

    # Send most recent 12 jobs in initial data (Recent Jobs card shows max 12)
    # But mark which ones are "active" for continued streaming
    recent_jobs = jobs_result[:12] if len(jobs_result) > 12 else jobs_result

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
                # Mark if job is active (will receive SSE updates)
                "is_active": job.status in ["pending", "processing"],
                # Content metadata (from content_results table or extracted from URL)
                "title": (
                    job.content_results[0].title
                    if job.content_results and len(job.content_results) > 0
                    else extract_title_from_url(job.source_url)
                ),
                "meta_description": (
                    job.content_results[0].meta_description
                    if job.content_results and len(job.content_results) > 0
                    else None
                ),
                "word_count": (
                    job.content_results[0].word_count
                    if job.content_results and len(job.content_results) > 0
                    else None
                ),
                "image_count": (
                    job.content_results[0].image_count
                    if job.content_results and len(job.content_results) > 0
                    else None
                ),
                "link_count": (
                    job.content_results[0].link_count
                    if job.content_results and len(job.content_results) > 0
                    else None
                ),
                "author": (
                    job.content_results[0].author
                    if job.content_results and len(job.content_results) > 0
                    else None
                ),
                "published_date": (
                    job.content_results[0].published_date.isoformat()
                    if job.content_results
                    and len(job.content_results) > 0
                    and job.content_results[0].published_date
                    else None
                ),
            }
            for job in recent_jobs
        ],
        "timestamp": "2023-01-01T00:00:00Z",
        # Summary for client optimization
        "active_jobs": sum(1 for job in jobs_result if job.status in ["pending", "processing"]),
        "completed_jobs": sum(1 for job in jobs_result if job.status == "completed"),
        "failed_jobs": sum(1 for job in jobs_result if job.status == "failed"),
    }
    event_data = f"event: initial-data\ndata: {safe_json_dumps(initial_data)}\n\n"
    logger.debug(
        "Sent initial job data",
        total=total_jobs,
        active=initial_data["active_jobs"],
        completed=initial_data["completed_jobs"],
    )
    return event_data


@api_error_handler("listen to Redis job events")
async def _listen_to_redis_job_events_safe(
    redis_client: Redis, event_queue: asyncio.Queue[dict[str, Any]], user_id: str
) -> None:
    """Safely listen to Redis job events with smart filtering.

    SSE Optimization: Only stream events for ACTIVE jobs (pending/processing).
    Once a job reaches terminal state (completed/failed), send ONE final event
    then stop streaming updates for that job. This reduces SSE traffic by 90%+.
    """
    pubsub = redis_client.pubsub()
    await pubsub.subscribe("job_events")
    logger.info("Subscribed to job_events Redis channel", user_id=user_id)

    # Track which jobs have reached terminal state (don't stream anymore)
    terminal_jobs: set[str] = set()

    async for message in pubsub.listen():
        if message["type"] == "message":
            job_event_data = await _process_job_event_message_safe(message)
            if job_event_data:
                job_id = job_event_data["job_id"]
                status = job_event_data["status"]

                # Check if this job already reached terminal state
                if job_id in terminal_jobs:
                    logger.debug(
                        "Skipping event for terminal job (optimization)",
                        job_id=job_id,
                        status=status,
                    )
                    continue

                # If job just reached terminal state, send ONE final event then mark it
                if status in ["completed", "failed", "cancelled"]:
                    logger.info(
                        "Job reached terminal state - sending final SSE event",
                        job_id=job_id,
                        status=status,
                    )
                    terminal_jobs.add(job_id)
                    # Add flag to indicate this is the final event for this job
                    job_event_data["is_terminal"] = True

                await event_queue.put(job_event_data)
                logger.info(
                    "Job event queued for SSE",
                    job_id=job_id,
                    event_type=job_event_data["event_type"],
                )


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

    logger.info(
        "Job event sent to client",
        event_name=event_name,
        job_id=job_update["job_id"],
        status=job_update.get("status"),
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
