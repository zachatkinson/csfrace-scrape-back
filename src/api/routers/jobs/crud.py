"""Job CRUD operations following Single Responsibility Principle.

This module handles basic job database operations including:
- Create jobs (/)
- List jobs (/)
- Get single job (/{job_id})
- Update job (/{job_id})
- Delete job (/{job_id})
"""

from fastapi import APIRouter, Query, status
from sqlalchemy.exc import SQLAlchemyError

from src.utils.logging import get_logger

from ....common.status import JobStatus
from ...crud import JobCRUD
from ...dependencies import DBSession
from ...errors import APIErrorFactory
from ...schemas import (
    JobListResponse,
    JobResponse,
    JobUpdate,
)
from ...utils import create_response_dict

logger = get_logger(__name__)

router = APIRouter()


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
    logger.info(
        "Listing jobs", page=page, page_size=page_size, status_filter=status_filter, domain=domain
    )

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

        logger.info("Jobs listed successfully", total=total, returned=len(jobs))
        return JobListResponse(**response_data)

    except SQLAlchemyError as e:
        logger.error("Failed to list jobs", error=str(e))
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
    logger.info("Getting job", job_id=job_id)

    try:
        job = await JobCRUD.get_job(db, job_id)
        if not job:
            logger.warning("Job not found", job_id=job_id)
            raise APIErrorFactory.not_found("Job", job_id)

        logger.info("Job retrieved successfully", job_id=job_id, status=job.status)
        return JobResponse.model_validate(job)

    except SQLAlchemyError as e:
        logger.error("Failed to get job", job_id=job_id, error=str(e))
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
    logger.info("Updating job", job_id=job_id, update_data=job_data.model_dump())

    try:
        job = await JobCRUD.update_job(db, job_id, job_data)
        if not job:
            logger.warning("Job not found for update", job_id=job_id)
            raise APIErrorFactory.not_found("Job", job_id)

        logger.info("Job updated successfully", job_id=job_id, status=job.status)
        return JobResponse.model_validate(job)

    except SQLAlchemyError as e:
        logger.error("Failed to update job", job_id=job_id, error=str(e))
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
    logger.info("Deleting job", job_id=job_id)

    try:
        deleted = await JobCRUD.delete_job(db, job_id)
        if not deleted:
            logger.warning("Job not found for deletion", job_id=job_id)
            raise APIErrorFactory.not_found("Job", job_id)

        logger.info("Job deleted successfully", job_id=job_id)

    except SQLAlchemyError as e:
        logger.error("Failed to delete job", job_id=job_id, error=str(e))
        raise APIErrorFactory.from_sqlalchemy_error("delete job", e)
