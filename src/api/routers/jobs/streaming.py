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

from src.utils.logging import get_logger

from ....caching.manager import cache_manager
from ....monitoring.job_events import job_event_publisher, publish_job_status_update
from ...crud import JobCRUD
from ...dependencies import DBSession

logger = get_logger(__name__)

router = APIRouter()


def safe_json_dumps(data: Any) -> str:
    """JSON dumps with handling for non-serializable types."""

    def default_serializer(obj):
        if hasattr(obj, "isoformat"):
            return obj.isoformat()
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
        try:
            await job_event_publisher.initialize()
            redis_client = await cache_manager._ensure_backend()._get_client()  # type: ignore[attr-defined]
            logger.debug("Job event system initialized successfully")

        except Exception as e:
            logger.error("Failed to initialize job event system", error=str(e))
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
        try:
            jobs_result, total_jobs = await JobCRUD.get_jobs(db=db, skip=0, limit=100)
            logger.debug(
                "Retrieved initial job data", total_jobs=total_jobs, returned=len(jobs_result)
            )

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
            yield f"event: initial-data\ndata: {safe_json_dumps(initial_data)}\n\n"
            logger.debug("Sent initial job data")

        except Exception as e:
            logger.error("Failed to send initial job data", error=str(e))
            yield f"event: error\ndata: {safe_json_dumps({'error': 'Failed to get initial job data'})}\n\n"

        # Set up event listener for Redis pub/sub job events
        event_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()

        # Redis pub/sub listener for job events
        async def redis_job_listener():
            """Listen to Redis job_events channel for real-time updates."""
            try:
                pubsub = redis_client.pubsub()
                await pubsub.subscribe("job_events")
                logger.debug("Subscribed to job_events Redis channel")

                async for message in pubsub.listen():
                    if message["type"] == "message":
                        try:
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
                            await event_queue.put(job_update)
                            logger.debug(
                                "Job event queued",
                                job_id=job_update["job_id"],
                                event_type=job_update["event_type"],
                            )

                        except Exception as e:
                            logger.error("Failed to process job event data", error=str(e))

            except Exception as e:
                logger.error("Redis job listener failed", error=str(e))

        # Start Redis listener task
        listener_task = asyncio.create_task(redis_job_listener())
        logger.debug("Redis job listener task started")

        # Stream events from queue
        try:
            while True:
                # Check if client disconnected
                if await request.is_disconnected():
                    logger.info("Job SSE client disconnected")
                    break

                try:
                    # Wait for events with timeout to periodically check connection
                    job_update = await asyncio.wait_for(event_queue.get(), timeout=30.0)

                    # Map event types to SSE event names
                    event_name_map = {
                        "created": "job-created",
                        "status_update": "job-status-update",
                        "progress": "job-progress",
                        "deleted": "job-deleted",
                        "error": "job-error",
                    }

                    event_name = event_name_map.get(job_update["event_type"], "job-update")
                    yield f"event: {event_name}\ndata: {safe_json_dumps(job_update)}\n\n"
                    logger.debug(
                        "Job event sent to client",
                        event_name=event_name,
                        job_id=job_update["job_id"],
                    )

                except TimeoutError:
                    # Send keepalive ping every 30 seconds
                    yield f"event: keepalive\ndata: {safe_json_dumps({'timestamp': '2023-01-01T00:00:00Z'})}\n\n"
                    logger.debug("Keepalive sent to client")
                    continue

        except asyncio.CancelledError:
            logger.info("Job SSE stream cancelled")
        except Exception as e:
            logger.error("Job SSE stream error", error=str(e))
            yield f"event: error\ndata: {safe_json_dumps({'error': str(e)})}\n\n"
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
async def trigger_job_event(db: DBSession):  # noqa: ARG001
    """Manually trigger a job event for testing purposes.

    This endpoint allows testing the job event system by creating
    a test event that will be broadcast to all connected SSE clients.

    Args:
        db: Database session (required parameter but unused in test)

    Returns:
        Confirmation of event publication
    """
    logger.info("Triggering test job event")

    try:
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

    except Exception as e:
        logger.error("Failed to trigger test job event", error=str(e))
        return {"error": str(e), "message": "Failed to trigger test job event"}
