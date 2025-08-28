"""Job management API endpoints."""

from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy.exc import SQLAlchemyError

from ...database.models import JobStatus
from ..crud import JobCRUD
from ..dependencies import DBSession
from ..schemas import JobCreate, JobListResponse, JobResponse, JobUpdate

router = APIRouter(prefix="/jobs", tags=["Jobs"])


@router.post("/", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
async def create_job(job_data: JobCreate, db: DBSession) -> JobResponse:
    """Create a new scraping job.

    Args:
        job_data: Job creation data
        db: Database session

    Returns:
        Created job details

    Raises:
        HTTPException: If job creation fails
    """
    try:
        job = await JobCRUD.create_job(db, job_data)
        return JobResponse.model_validate(job)
    except SQLAlchemyError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create job: {str(e)}",
        )


@router.get("/", response_model=JobListResponse)
async def list_jobs(
    db: DBSession,
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=200, description="Items per page"),
    status_filter: Optional[JobStatus] = Query(None, description="Filter by job status"),
    domain: Optional[str] = Query(None, description="Filter by domain"),
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

        total_pages = (total + page_size - 1) // page_size

        return JobListResponse(
            jobs=[JobResponse.model_validate(job) for job in jobs],
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )
    except SQLAlchemyError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve jobs: {str(e)}",
        )


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(job_id: int, db: DBSession) -> JobResponse:
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
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=f"Job {job_id} not found"
            )
        return JobResponse.model_validate(job)
    except SQLAlchemyError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve job: {str(e)}",
        )


@router.put("/{job_id}", response_model=JobResponse)
async def update_job(job_id: int, job_data: JobUpdate, db: DBSession) -> JobResponse:
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
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=f"Job {job_id} not found"
            )
        return JobResponse.model_validate(job)
    except SQLAlchemyError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update job: {str(e)}",
        )


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_job(job_id: int, db: DBSession) -> None:
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
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=f"Job {job_id} not found"
            )
    except SQLAlchemyError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete job: {str(e)}",
        )


@router.post("/{job_id}/start", response_model=JobResponse)
async def start_job(job_id: int, db: DBSession) -> JobResponse:
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
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=f"Job {job_id} not found"
            )

        if job.status != JobStatus.PENDING:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Job {job_id} cannot be started (current status: {job.status.value})",
            )

        updated_job = await JobCRUD.update_job_status(db, job_id, JobStatus.RUNNING)
        return JobResponse.model_validate(updated_job)
    except SQLAlchemyError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start job: {str(e)}",
        )


@router.post("/{job_id}/cancel", response_model=JobResponse)
async def cancel_job(job_id: int, db: DBSession) -> JobResponse:
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
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=f"Job {job_id} not found"
            )

        if job.status in {JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED}:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Job {job_id} cannot be cancelled (current status: {job.status.value})",
            )

        updated_job = await JobCRUD.update_job_status(db, job_id, JobStatus.CANCELLED)
        return JobResponse.model_validate(updated_job)
    except SQLAlchemyError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to cancel job: {str(e)}",
        )


@router.post("/{job_id}/retry", response_model=JobResponse)
async def retry_job(job_id: int, db: DBSession) -> JobResponse:
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
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=f"Job {job_id} not found"
            )

        if not job.can_retry:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Job {job_id} cannot be retried (status: {job.status.value}, "
                f"retries: {job.retry_count}/{job.max_retries})",
            )

        # Reset job for retry
        job.status = JobStatus.PENDING
        job.retry_count += 1
        job.error_message = None
        job.error_type = None
        job.started_at = None
        job.completed_at = None

        await db.flush()
        await db.refresh(job)
        return JobResponse.model_validate(job)
    except SQLAlchemyError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retry job: {str(e)}",
        )
