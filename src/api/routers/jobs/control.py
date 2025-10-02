"""Job control operations following Single Responsibility Principle.

This module handles job state management including:
- Start job (/{job_id}/start)
- Cancel job (/{job_id}/cancel)
- Retry job (/{job_id}/retry)
- Job state transitions and validation
"""

from fastapi import APIRouter

from src.core.decorators import api_error_handler
from src.core.logging_hierarchy import get_api_logger

from ....common.status import JobStatus
from ...crud import JobCRUD
from ...dependencies import DBSession
from ...errors import APIErrorFactory
from ...schemas import JobResponse

logger = get_api_logger()

router = APIRouter()


@router.post("/{job_id}/start", response_model=JobResponse)
@api_error_handler("start job")
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
    logger.info("Starting job", job_id=job_id)

    job = await JobCRUD.get_job(db, job_id)
    if not job:
        logger.warning("Job not found for start", job_id=job_id)
        raise APIErrorFactory.not_found("Job", job_id)

    # Validate state transition
    if job.status != JobStatus.PENDING.value:
        logger.warning(
            "Invalid job state transition",
            job_id=job_id,
            current_status=job.status,
            requested_action="start",
        )
        raise APIErrorFactory.business_logic_error(
            f"Job {job_id} cannot be started (current status: {job.status})",
            "INVALID_STATUS_TRANSITION",
        )

    updated_job = await JobCRUD.update_job_status(db, job_id, JobStatus.RUNNING)
    logger.info("Job started successfully", job_id=job_id, new_status=JobStatus.RUNNING.value)

    return JobResponse.model_validate(updated_job)
    # Enhanced decorator handles SQLAlchemyError and API error responses


@router.post("/{job_id}/cancel", response_model=JobResponse)
@api_error_handler("cancel job")
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
    logger.info("Cancelling job", job_id=job_id)

    job = await JobCRUD.get_job(db, job_id)
    if not job:
        logger.warning("Job not found for cancel", job_id=job_id)
        raise APIErrorFactory.not_found("Job", job_id)

    # Validate state transition - can't cancel completed/failed/already cancelled jobs
    final_states = {
        JobStatus.COMPLETED.value,
        JobStatus.FAILED.value,
        JobStatus.CANCELLED.value,
    }

    if job.status in final_states:
        logger.warning(
            "Invalid job state transition",
            job_id=job_id,
            current_status=job.status,
            requested_action="cancel",
        )
        raise APIErrorFactory.business_logic_error(
            f"Job {job_id} cannot be cancelled (current status: {job.status})",
            "INVALID_STATUS_TRANSITION",
        )

    updated_job = await JobCRUD.update_job_status(db, job_id, JobStatus.CANCELLED)
    logger.info("Job cancelled successfully", job_id=job_id, new_status=JobStatus.CANCELLED.value)

    return JobResponse.model_validate(updated_job)
    # Enhanced decorator handles SQLAlchemyError and API error responses


@router.post("/{job_id}/retry", response_model=JobResponse)
@api_error_handler("retry job")
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
    logger.info("Retrying job", job_id=job_id)

    job = await JobCRUD.get_job(db, job_id)
    if not job:
        logger.warning("Job not found for retry", job_id=job_id)
        raise APIErrorFactory.not_found("Job", job_id)

    # Check if job can be retried (business logic validation)
    if not job.can_retry:
        logger.warning(
            "Job retry limit exceeded",
            job_id=job_id,
            status=job.status,
            retry_count=job.retry_count,
            max_retries=job.max_retries,
        )
        raise APIErrorFactory.business_logic_error(
            f"Job {job_id} cannot be retried (status: {job.status}, "
            f"retries: {job.retry_count}/{job.max_retries})",
            "RETRY_LIMIT_EXCEEDED",
        )

    # Reset job for retry
    logger.debug("Resetting job for retry", job_id=job_id, current_retry_count=job.retry_count)

    job.status = JobStatus.PENDING.value
    job.retry_count += 1
    job.error_message = None
    job.started_at = None
    job.completed_at = None

    await db.flush()
    await db.refresh(job)

    logger.info(
        "Job reset for retry successfully",
        job_id=job_id,
        new_retry_count=job.retry_count,
        new_status=job.status,
    )

    return JobResponse.model_validate(job)
    # Enhanced decorator handles SQLAlchemyError and API error responses
