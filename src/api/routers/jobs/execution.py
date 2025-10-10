"""Job execution operations following Single Responsibility Principle.

This module handles job creation and background execution including:
- Create jobs endpoint (/)
- Background task execution
- Job scheduling and orchestration
"""

from pathlib import Path
from urllib.parse import urlparse
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, Request, status
from slowapi import Limiter
from slowapi.util import get_remote_address

from src.auth.dependencies import get_current_user_from_cookie
from src.auth.models import User
from src.core.decorators import api_error_handler, job_error_handler
from src.core.logging_hierarchy import get_api_logger
from src.monitoring.job_events import (
    publish_job_created,
    publish_job_progress,
    publish_job_status_update,
)

from ....common.status import JobStatus
from ....config.rate_limits import rate_limits

# Removed SYSTEM_USER_ID per ZERO TOLERANCE policy
from ....core.converter import AsyncWordPressConverter
from ....core.metadata_extractor import MetadataExtractorService
from ....database.models.jobs import ContentResult, ScrapingJob
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

    # Extract domain from URL for event publishing
    parsed_url = urlparse(url)
    domain = parsed_url.netloc or "unknown"

    async with async_session() as db:
        # Update job status to running and publish SSE event
        await JobCRUD.update_job_status(db, job_id, JobStatus.RUNNING)
        logger.info("Job status updated to RUNNING", job_id=job_id)

        # Publish status update event
        await publish_job_status_update(
            job_id=job_id,
            old_status=JobStatus.PENDING.value,
            new_status=JobStatus.RUNNING.value,
            url=url,
            domain=domain,
        )

        # Create output directory
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        logger.debug("Output directory created", path=str(output_path))

        # Initialize converter
        converter = AsyncWordPressConverter(base_url=url, output_dir=output_path)

        # Execute conversion with progress callback
        async def progress_callback(progress: int) -> None:
            """Progress callback for conversion updates with SSE publishing."""
            logger.debug("Conversion progress", job_id=job_id, progress=progress)

            # Publish progress update via SSE
            await publish_job_progress(
                job_id=job_id,
                status=JobStatus.RUNNING.value,
                progress_percent=float(progress),
                url=url,
                domain=domain,
                current_step=f"Processing: {progress}% complete",
            )

        # Run the conversion
        logger.info("Starting conversion process", job_id=job_id)
        await converter.convert(progress_callback=progress_callback)
        logger.info("Conversion completed successfully", job_id=job_id)

        # Extract metadata from generated files
        logger.info(
            "Extracting metadata from output files", job_id=job_id, output_dir=str(output_path)
        )

        # Variables to store metadata for SSE event (may not be available if extraction fails)
        scraped_title = None
        scraped_word_count = None
        scraped_image_count = None

        try:
            metadata_extractor = MetadataExtractorService(output_path)
            content_data = metadata_extractor.extract_all()
            logger.info(
                "Metadata extracted successfully",
                job_id=job_id,
                title=content_data.title,
                word_count=content_data.word_count,
                image_count=content_data.image_count,
            )

            # Store metadata for SSE event
            scraped_title = content_data.title
            scraped_word_count = content_data.word_count
            scraped_image_count = content_data.image_count

            # Create ContentResult record
            content_result = ContentResult(
                job_id=job_id,
                # File paths
                html_file_path=content_data.html_file_path,
                metadata_file_path=content_data.metadata_file_path,
                images_directory=content_data.images_directory,
                # Metadata
                title=content_data.title,
                meta_description=content_data.meta_description,
                published_date=content_data.published_date,
                author=content_data.author,
                # Statistics
                word_count=content_data.word_count,
                image_count=content_data.image_count,
                link_count=content_data.link_count,
                # HTML content (optional - can be large)
                original_html=content_data.original_html,
                converted_html=content_data.converted_html,
                shopify_html=content_data.shopify_html,
            )
            db.add(content_result)
            logger.info("ContentResult record created", job_id=job_id)

        except Exception as e:
            logger.error(
                "Failed to extract metadata or create ContentResult",
                job_id=job_id,
                error=str(e),
                exc_info=True,
            )
            # Continue with job completion even if metadata extraction fails

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

            # Publish completion event with scraped metadata (title, word_count, image_count)
            await publish_job_status_update(
                job_id=job_id,
                old_status=JobStatus.RUNNING.value,
                new_status=JobStatus.COMPLETED.value,
                url=url,
                domain=domain,
                processing_time_ms=job.processing_time_ms if job.processing_time_ms else None,
                title=scraped_title,  # Actual scraped title
                word_count=scraped_word_count,  # Actual word count
                image_count=scraped_image_count,  # Actual image count
            )

        # Enhanced decorator handles exceptions and marks job as failed


@router.post("/", response_model=JobsCreateResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit(rate_limits.JOB_CREATION)
@api_error_handler("create jobs")
async def create_jobs(
    request: Request,  # Required for SlowAPI rate limiting  # noqa: ARG001
    jobs_data: JobsCreateRequest,
    background_tasks: BackgroundTasks,
    db: DBSession,
    current_user: User = Depends(get_current_user_from_cookie),
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
            user_id=current_user.id,  # Secure: Use authenticated user's ID
            batch_id=batch_id,
            # priority removed - YAGNI (not used for filtering, ordering, or queue processing)
            max_retries=jobs_data.max_retries,
            options=job_options,
        )
        jobs.append(job)
        db.add(job)

    await db.flush()  # Get job IDs
    await db.commit()
    logger.info("Jobs created in database", job_count=len(jobs), batch_id=batch_id)

    # Publish job created events
    for job in jobs:
        await publish_job_created(
            job_id=job.id,
            url=job.source_url,
            domain=job.domain,
            status=JobStatus.PENDING.value,
        )

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
