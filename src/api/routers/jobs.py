"""Job management API endpoints."""

import contextlib
import json
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any

import asyncio

try:
    import structlog
except ImportError:
    # Fallback to basic logging if structlog not available
    import logging

    structlog = logging  # type: ignore[misc]
from fastapi import APIRouter, BackgroundTasks, Query, Request, status
from fastapi.responses import StreamingResponse
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.exc import SQLAlchemyError

from ...caching.manager import cache_manager
from ...common.status import JobStatus
from ...config.rate_limits import rate_limits
from ...core.config import config as default_config
from ...core.converter import AsyncWordPressConverter
from ...database.service import DatabaseService
from ...monitoring.job_events import job_event_publisher, publish_job_status_update
from ..crud import JobCRUD
from ..dependencies import DBSession, async_session
from ..errors import APIErrorFactory
from ..schemas import (
    JobListResponse,
    JobResponse,
    JobsCreateRequest,
    JobsCreateResponse,
    JobUpdate,
)
from ..utils import create_response_dict

router = APIRouter(prefix="/jobs", tags=["Jobs"])

# Use shared limiter instance from main app (best practice)
limiter = Limiter(key_func=get_remote_address)


async def execute_conversion_job(job_id: str, url: str, output_dir: str):
    """Background task to execute the actual WordPress to Shopify conversion.

    Args:
        job_id: Database job ID
        url: WordPress URL to convert
        output_dir: Output directory for conversion results
    """

    async with async_session() as db:
        try:
            # Update job status to running
            await JobCRUD.update_job_status(db, job_id, JobStatus.RUNNING)

            # Create output directory
            output_path = Path(output_dir)
            output_path.mkdir(parents=True, exist_ok=True)

            # Initialize converter with default config
            converter = AsyncWordPressConverter(
                base_url=url, output_dir=output_path, config=default_config
            )

            # Execute conversion with progress callback
            def progress_callback(_: int):
                # In a real implementation, you could update job progress in database
                # For now, we'll just log progress
                pass

            # Run the conversion
            await converter.convert(progress_callback=progress_callback)

            # Mark job as completed
            job = await JobCRUD.update_job_status(db, job_id, JobStatus.COMPLETED)
            if job:
                job.success = True
                # Update additional completion metadata
                if output_path.exists():
                    # Calculate content size
                    total_size = sum(
                        f.stat().st_size for f in output_path.rglob("*") if f.is_file()
                    )
                    job.content_size_bytes = total_size

                    # Count images downloaded
                    images_dir = output_path / "images"
                    if images_dir.exists():
                        job.images_downloaded = len(list(images_dir.glob("*")))

                await db.commit()

        except Exception as e:
            # Mark job as failed with error details
            await JobCRUD.update_job_status(
                db, job_id, JobStatus.FAILED, error_message=str(e), error_type=type(e).__name__
            )
            # Re-raise to ensure it's logged
            raise


@router.post("/", response_model=JobsCreateResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit(rate_limits.JOB_CREATION)
async def create_jobs(
    request: Request,  # Required for SlowAPI rate limiting  # pylint: disable=unused-argument
    jobs_data: JobsCreateRequest,
    background_tasks: BackgroundTasks,
    db: DBSession,
) -> JobsCreateResponse:
    """Create jobs from URL array with automatic batch detection.

    Elegant approach:
    - Single URL: batch_id = None (individual job)
    - Multiple URLs: auto-generate batch_id (batch processing)

    Args:
        jobs_data: Jobs creation data with URL array
        background_tasks: FastAPI background tasks
        db: Database session

    Returns:
        Created jobs details with batch info

    Raises:
        HTTPException: If job creation fails
    """
    try:
        # Use database service for elegant array-based job creation
        db_service = DatabaseService()
        jobs = db_service.create_jobs(
            urls=[str(url) for url in jobs_data.urls],
            priority=jobs_data.priority.value,
            output_directory=jobs_data.output_base_directory,
            max_retries=jobs_data.max_retries,
            options=jobs_data.options,
        )

        # Add background tasks for all jobs
        for job in jobs:
            background_tasks.add_task(
                execute_conversion_job, job.id, job.source_url, job.output_directory or ""
            )

        # Prepare response
        job_responses = [JobResponse.model_validate(job) for job in jobs]
        batch_id = jobs[0].batch_id if jobs else None

        return JobsCreateResponse(jobs=job_responses, batch_id=batch_id, total_jobs=len(jobs))
    except Exception as e:
        raise APIErrorFactory.internal_server_error("create jobs", e)


@router.get("/", response_model=JobListResponse)
async def list_jobs(
    db: DBSession,
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=200, description="Items per page"),
    status_filter: JobStatus | None = Query(None, description="Filter by job status"),
    domain: str | None = Query(None, description="Filter by domain"),
) -> JobListResponse:
    """Get paginated list of jobs with optional filters.

    Args:
        db: Database session
        page: Page number (1-based)
        page_size: Number of items per page
        status_filter: Optional status filter
        domain: Optional domain filter

    Returns:
        Paginated job list
    """
    try:
        skip = (page - 1) * page_size
        jobs, total = await JobCRUD.get_jobs(
            db, skip=skip, limit=page_size, status=status_filter, domain=domain
        )

        response_data = create_response_dict(
            items_key="jobs",
            items=[JobResponse.model_validate(job) for job in jobs],
            total=total,
            page=page,
            page_size=page_size,
        )

        return JobListResponse(**response_data)
    except SQLAlchemyError as e:
        raise APIErrorFactory.from_sqlalchemy_error("retrieve jobs", e)


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(job_id: str, db: DBSession) -> JobResponse:
    """Get a specific job by ID.

    Args:
        job_id: Job ID
        db: Database session

    Returns:
        Job details

    Raises:
        HTTPException: If job not found
    """
    try:
        job = await JobCRUD.get_job(db, job_id)
        if not job:
            raise APIErrorFactory.not_found("Job", job_id)
        return JobResponse.model_validate(job)
    except SQLAlchemyError as e:
        raise APIErrorFactory.from_sqlalchemy_error("retrieve job", e)


@router.put("/{job_id}", response_model=JobResponse)
async def update_job(job_id: str, job_data: JobUpdate, db: DBSession) -> JobResponse:
    """Update a job.

    Args:
        job_id: Job ID
        job_data: Update data
        db: Database session

    Returns:
        Updated job details

    Raises:
        HTTPException: If job not found or update fails
    """
    try:
        job = await JobCRUD.update_job(db, job_id, job_data)
        if not job:
            raise APIErrorFactory.not_found("Job", job_id)
        return JobResponse.model_validate(job)
    except SQLAlchemyError as e:
        raise APIErrorFactory.from_sqlalchemy_error("update job", e)


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_job(job_id: str, db: DBSession) -> None:
    """Delete a job.

    Args:
        job_id: Job ID
        db: Database session

    Raises:
        HTTPException: If job not found or deletion fails
    """
    try:
        deleted = await JobCRUD.delete_job(db, job_id)
        if not deleted:
            raise APIErrorFactory.not_found("Job", job_id)
    except SQLAlchemyError as e:
        raise APIErrorFactory.from_sqlalchemy_error("delete job", e)


@router.post("/{job_id}/start", response_model=JobResponse)
async def start_job(job_id: str, db: DBSession) -> JobResponse:
    """Start a job (change status to RUNNING).

    Args:
        job_id: Job ID
        db: Database session

    Returns:
        Updated job details

    Raises:
        HTTPException: If job not found or cannot be started
    """
    try:
        job = await JobCRUD.get_job(db, job_id)
        if not job:
            raise APIErrorFactory.not_found("Job", job_id)

        if job.status != JobStatus.PENDING.value:
            raise APIErrorFactory.business_logic_error(
                f"Job {job_id} cannot be started (current status: {job.status})",
                "INVALID_STATUS_TRANSITION",
            )

        updated_job = await JobCRUD.update_job_status(db, job_id, JobStatus.RUNNING)
        return JobResponse.model_validate(updated_job)
    except SQLAlchemyError as e:
        raise APIErrorFactory.from_sqlalchemy_error("start job", e)


@router.post("/{job_id}/cancel", response_model=JobResponse)
async def cancel_job(job_id: str, db: DBSession) -> JobResponse:
    """Cancel a job (change status to CANCELLED).

    Args:
        job_id: Job ID
        db: Database session

    Returns:
        Updated job details

    Raises:
        HTTPException: If job not found or cannot be cancelled
    """
    try:
        job = await JobCRUD.get_job(db, job_id)
        if not job:
            raise APIErrorFactory.not_found("Job", job_id)

        if job.status in {
            JobStatus.COMPLETED.value,
            JobStatus.FAILED.value,
            JobStatus.CANCELLED.value,
        }:
            raise APIErrorFactory.business_logic_error(
                f"Job {job_id} cannot be cancelled (current status: {job.status})",
                "INVALID_STATUS_TRANSITION",
            )

        updated_job = await JobCRUD.update_job_status(db, job_id, JobStatus.CANCELLED)
        return JobResponse.model_validate(updated_job)
    except SQLAlchemyError as e:
        raise APIErrorFactory.from_sqlalchemy_error("cancel job", e)


@router.post("/{job_id}/retry", response_model=JobResponse)
async def retry_job(job_id: str, db: DBSession) -> JobResponse:
    """Retry a failed job.

    Args:
        job_id: Job ID
        db: Database session

    Returns:
        Updated job details

    Raises:
        HTTPException: If job not found or cannot be retried
    """
    try:
        job = await JobCRUD.get_job(db, job_id)
        if not job:
            raise APIErrorFactory.not_found("Job", job_id)

        if not job.can_retry:
            raise APIErrorFactory.business_logic_error(
                f"Job {job_id} cannot be retried (status: {job.status}, "
                f"retries: {job.retry_count}/{job.max_retries})",
                "RETRY_LIMIT_EXCEEDED",
            )

        # Reset job for retry
        job.status = JobStatus.PENDING.value
        job.retry_count += 1
        job.error_message = None
        job.error_type = None
        job.started_at = None
        job.completed_at = None

        await db.flush()
        await db.refresh(job)
        return JobResponse.model_validate(job)
    except SQLAlchemyError as e:
        raise APIErrorFactory.from_sqlalchemy_error("retry job", e)


# =============================================================================
# SSE STREAMING ENDPOINTS
# =============================================================================

logger = structlog.get_logger(__name__)


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

        # Send initial job list as baseline
        try:
            jobs_result, total_jobs = await JobCRUD.get_jobs(db=db, skip=0, limit=100)

            initial_data = {
                "type": "initial_data",
                "total_jobs": total_jobs,
                "jobs": [
                    {
                        "id": job.id,
                        "url": job.source_url,
                        "domain": job.domain,
                        "status": job.status,
                        "created_at": job.created_at.isoformat() if job.created_at else None,
                        "started_at": job.started_at.isoformat() if job.started_at else None,
                        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
                        "error_message": job.error_message,
                        "success": job.success,
                        "processing_time_ms": job.processing_time_ms,
                    }
                    for job in jobs_result
                ],
                "timestamp": "2023-01-01T00:00:00Z",
            }
            yield f"event: initial-data\ndata: {safe_json_dumps(initial_data)}\n\n"

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

                        except Exception as e:
                            logger.error("Failed to process job event data", error=str(e))

            except Exception as e:
                logger.error("Redis job listener failed", error=str(e))

        # Start Redis listener task
        listener_task = asyncio.create_task(redis_job_listener())

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

                except TimeoutError:
                    # Send keepalive ping every 30 seconds
                    yield f"event: keepalive\ndata: {safe_json_dumps({'timestamp': '2023-01-01T00:00:00Z'})}\n\n"
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
async def trigger_job_event(db: DBSession):
    """Manually trigger a job event for testing purposes.

    This endpoint allows testing the job event system by creating
    a test event that will be broadcast to all connected SSE clients.

    Returns:
        Confirmation of event publication
    """
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
            return {
                "message": "Test job event triggered successfully",
                "event_type": "status_update",
                "timestamp": "2023-01-01T00:00:00Z",
            }
        else:
            return {"error": "Failed to publish test event", "message": "Event publication failed"}

    except Exception as e:
        logger.error("Failed to trigger test job event", error=str(e))
        return {"error": str(e), "message": "Failed to trigger test job event"}
