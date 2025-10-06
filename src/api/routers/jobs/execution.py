"""Job execution operations following Single Responsibility Principle.

This module handles job creation and background execution including:
- Create jobs endpoint (/)
- Background task execution
- Job scheduling and orchestration
"""

from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Request, status
from slowapi import Limiter
from slowapi.util import get_remote_address

from src.core.decorators import api_error_handler, job_error_handler
from src.core.logging_hierarchy import get_api_logger

from ....common.status import JobStatus
from ....config.rate_limits import rate_limits

# Removed SYSTEM_USER_ID per ZERO TOLERANCE policy
from ....core.converter import AsyncWordPressConverter
from ....database.models.jobs import ScrapingJob
from ...crud import JobCRUD
from ...dependencies import DBSession, async_session
from ...schemas import (
    JobResponse,
    JobsCreateRequest,
    JobsCreateResponse,
)

logger = get_api_logger()

# Use shared limiter instance from main app (best practice)
limiter = Limiter(key_func=get_remote_address)

router = APIRouter()


@job_error_handler("execute conversion job")
async def execute_conversion_job(job_id: str, url: str, output_dir: str) -> None:
    """Background task to execute the actual WordPress to Shopify conversion.

    Args:
        job_id: Database job ID
        url: WordPress URL to convert
        output_dir: Output directory for conversion results
    """
    logger.info("Starting conversion job execution", job_id=job_id, url=url, output_dir=output_dir)

    async with async_session() as db:
        # Update job status to running
        await JobCRUD.update_job_status(db, job_id, JobStatus.RUNNING)
        logger.info("Job status updated to RUNNING", job_id=job_id)

        # Create output directory
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        logger.debug("Output directory created", path=str(output_path))

        # Initialize converter
        converter = AsyncWordPressConverter(base_url=url, output_dir=output_path)

        # Execute conversion with progress callback
        def progress_callback(progress: int) -> None:
            """Progress callback for conversion updates."""
            logger.debug("Conversion progress", job_id=job_id, progress=progress)
            # In a real implementation, you could update job progress in database
            # For now, we'll just log progress

        # Run the conversion
        logger.info("Starting conversion process", job_id=job_id)
        await converter.convert(progress_callback=progress_callback)
        logger.info("Conversion completed successfully", job_id=job_id)

        # Mark job as completed
        job = await JobCRUD.update_job_status(db, job_id, JobStatus.COMPLETED)
        if job:
            # Calculate content size if output exists
            if output_path.exists():
                total_size = sum(f.stat().st_size for f in output_path.rglob("*") if f.is_file())
                job.output_size_bytes = total_size
                logger.info(
                    "Job completed with output", job_id=job_id, output_size_bytes=total_size
                )

            await db.commit()

        # Enhanced decorator handles exceptions and marks job as failed


@router.post("/", response_model=JobsCreateResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit(rate_limits.JOB_CREATION)
@api_error_handler("create jobs")
async def create_jobs(
    request: Request,  # Required for SlowAPI rate limiting  # noqa: ARG001
    jobs_data: JobsCreateRequest,
    background_tasks: BackgroundTasks,
    db: DBSession,
) -> JobsCreateResponse:
    """Create jobs from URL array with automatic batch detection.

    Elegant approach:
    - Single URL: batch_id = None (individual job)
    - Multiple URLs: auto-generate batch_id (batch processing)

    Args:
        request: FastAPI request (required for rate limiting)
        jobs_data: Jobs creation data with URL array
        background_tasks: FastAPI background tasks
        db: Database session

    Returns:
        Created jobs details with batch info

    Raises:
        HTTPException: If job creation fails
    """
    logger.info(
        "Creating jobs", url_count=len(jobs_data.urls), output_dir=jobs_data.output_base_directory
    )

    # Auto-batch detection: multiple URLs = batch, single URL = individual
    batch_id = str(uuid4()) if len(jobs_data.urls) > 1 else None
    logger.debug("Batch detection", batch_id=batch_id, is_batch=batch_id is not None)

    jobs = []
    for url in jobs_data.urls:
        # Prepare options with output directory if provided
        job_options = jobs_data.options or {}
        if jobs_data.output_base_directory:
            job_options["output_base_directory"] = jobs_data.output_base_directory

        # Extract domain from URL for the domain field
        from urllib.parse import urlparse

        parsed_url = urlparse(str(url))
        domain = parsed_url.netloc or "unknown"

        job = ScrapingJob(
            source_url=str(url),
            domain=domain,
            user_id="anonymous",  # TODO: Replace with actual authenticated user
            batch_id=batch_id,
            priority=jobs_data.priority.value,
            max_retries=jobs_data.max_retries,
            options=job_options,
        )
        jobs.append(job)
        db.add(job)

    await db.flush()  # Get job IDs
    await db.commit()
    logger.info("Jobs created in database", job_count=len(jobs), batch_id=batch_id)

    # Add background tasks for all jobs
    for job in jobs:
        # Generate output directory path
        parsed_url = urlparse(job.source_url)
        path = parsed_url.path.strip("/")
        slug = path.split("/")[-1] if path else "index"
        output_dir = f"converted_content/{parsed_url.netloc}_{slug}"

        background_tasks.add_task(execute_conversion_job, job.id, job.source_url, output_dir)
        logger.info("Background task scheduled", job_id=job.id, url=job.source_url)

    # Prepare response
    job_responses = [JobResponse.model_validate(job) for job in jobs]
    response_batch_id = jobs[0].batch_id if jobs else None

    logger.info("Jobs creation completed", job_count=len(jobs), batch_id=response_batch_id)

    return JobsCreateResponse(jobs=job_responses, batch_id=response_batch_id, total_jobs=len(jobs))
    # Enhanced decorator handles exceptions and API error responses
