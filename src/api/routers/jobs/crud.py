"""Job CRUD operations following Single Responsibility Principle.

This module handles basic job database operations including:
- Create jobs (/)
- List jobs (/)
- Get single job (/{job_id})
- Update job (/{job_id})
- Delete job (/{job_id})
"""

from typing import Any

from fastapi import APIRouter, Depends, Query, status

from src.auth.dependencies import get_current_user_from_cookie
from src.auth.models import User
from src.core.decorators import api_error_handler
from src.core.logging_hierarchy import get_api_logger

from ....common.status import JobStatus
from ....database.models.jobs import ScrapingJob
from ...crud import JobCRUD
from ...dependencies import DBSession
from ...errors import APIErrorFactory
from ...schemas import (
    JobListResponse,
    JobResponse,
    JobUpdate,
)
from ...utils import create_response_dict

logger = get_api_logger()

router = APIRouter()


def _enrich_job_response(job: ScrapingJob) -> dict[str, Any]:
    """Enrich job data with content_results metadata.

    Extracts content_results metadata and merges it with job data
    for a complete JobResponse with word_count, image_count, etc.

    Args:
        job: ScrapingJob instance with content_results relationship loaded

    Returns:
        Dictionary with job data + content_results metadata
    """
    # Start with job data
    job_dict = {
        "id": job.id,
        "source_url": job.source_url,
        "target_format": job.target_format,
        "status": job.status,
        "created_at": job.created_at,
        "started_at": job.started_at,
        "completed_at": job.completed_at,
        "retry_count": job.retry_count,
        "max_retries": job.max_retries,
        "error_message": job.error_message,
        "processing_time_ms": job.processing_time_ms,
        "output_size_bytes": job.output_size_bytes,
        "batch_id": job.batch_id,
        "options": job.options,
        "progress": job.progress,
    }

    # Merge content_results metadata if available
    if job.content_results and len(job.content_results) > 0:
        content_result = job.content_results[0]  # Latest content result
        job_dict.update(
            {
                "title": content_result.title,
                "meta_description": content_result.meta_description,
                "word_count": content_result.word_count,
                "image_count": content_result.image_count,
                "link_count": content_result.link_count,
                "author": content_result.author,
                "published_date": content_result.published_date,
            }
        )

    return job_dict


@router.get("/", response_model=JobListResponse)
@api_error_handler("list jobs")
async def list_jobs(
    db: DBSession,
    current_user: User = Depends(get_current_user_from_cookie),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=200, description="Items per page"),
    status_filter: JobStatus | None = Query(None, description="Filter by job status"),
    domain: str | None = Query(None, description="Filter by domain"),
) -> JobListResponse:
    """Get paginated list of jobs for the current authenticated user.

    Automatically filters jobs by the authenticated user's ID to ensure
    users only see their own conversion jobs.

    Args:
        db: Database session
        current_user: Authenticated user from cookie
        page: Page number (1-based)
        page_size: Number of items per page
        status_filter: Optional status filter
        domain: Optional domain filter

    Returns:
        Paginated job list filtered by current user with content_results metadata
    """
    logger.info(
        "Listing jobs",
        user_id=current_user.id,
        page=page,
        page_size=page_size,
        status_filter=status_filter,
        domain=domain,
    )

    skip = (page - 1) * page_size
    jobs, total = await JobCRUD.get_jobs(
        db, skip=skip, limit=page_size, status=status_filter, domain=domain, user_id=current_user.id
    )

    # Enrich job responses with content_results metadata
    enriched_jobs = [JobResponse(**_enrich_job_response(job)) for job in jobs]

    response_data = create_response_dict(
        items_key="jobs",
        items=enriched_jobs,
        total=total,
        page=page,
        page_size=page_size,
    )

    logger.info("Jobs listed successfully", total=total, returned=len(jobs))
    return JobListResponse(**response_data)
    # Enhanced decorator handles SQLAlchemyError and API error responses


@router.get("/{job_id}", response_model=JobResponse)
@api_error_handler("get job")
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

    job = await JobCRUD.get_job(db, job_id)
    if not job:
        logger.warning("Job not found", job_id=job_id)
        raise APIErrorFactory.not_found("Job", job_id)

    logger.info("Job retrieved successfully", job_id=job_id, status=job.status)
    return JobResponse.model_validate(job)
    # Enhanced decorator handles SQLAlchemyError and API error responses


@router.put("/{job_id}", response_model=JobResponse)
@api_error_handler("update job")
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

    job = await JobCRUD.update_job(db, job_id, job_data)
    if not job:
        logger.warning("Job not found for update", job_id=job_id)
        raise APIErrorFactory.not_found("Job", job_id)

    logger.info("Job updated successfully", job_id=job_id, status=job.status)
    return JobResponse.model_validate(job)
    # Enhanced decorator handles SQLAlchemyError and API error responses


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
@api_error_handler("delete job")
async def delete_job(job_id: str, db: DBSession) -> None:
    """Delete a job.

    Args:
        job_id: Job ID
        db: Database session

    Raises:
        HTTPException: If job not found or deletion fails
    """
    logger.info("Deleting job", job_id=job_id)

    deleted = await JobCRUD.delete_job(db, job_id)
    if not deleted:
        logger.warning("Job not found for deletion", job_id=job_id)
        raise APIErrorFactory.not_found("Job", job_id)

    logger.info("Job deleted successfully", job_id=job_id)
    # Enhanced decorator handles SQLAlchemyError and API error responses
