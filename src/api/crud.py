"""CRUD operations for API endpoints using async SQLAlchemy 2.0."""

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..common.status import JobStatus
from ..constants import API_DEFAULT_LIMIT
from ..database.models.jobs import ContentResult, ScrapingJob
from ..monitoring.job_events import (
    publish_job_created,
    publish_job_deleted,
    publish_job_status_update,
)
from .schemas import JobCreate, JobUpdate


class JobCRUD:
    """CRUD operations for scraping jobs."""

    @staticmethod
    async def create_job(db: AsyncSession, job_data: JobCreate) -> ScrapingJob:
        """Create a new scraping job.

        Args:
            db: Database session
            job_data: Job creation data

        Returns:
            Created job instance
        """
        from urllib.parse import urlparse

        # Parse URL to extract domain
        parsed_url = urlparse(str(job_data.url))
        domain = parsed_url.netloc

        # Generate slug: use custom_slug if provided, otherwise auto-generate from URL
        if job_data.custom_slug:
            slug = job_data.custom_slug
        else:
            path = parsed_url.path.strip("/")
            slug = path.split("/")[-1] if path else "index"

        # Generate output directory if not provided
        output_directory = job_data.output_directory
        if not output_directory:
            output_directory = f"converted_content/{domain}_{slug}"

        # priority removed - YAGNI (not used for filtering, ordering, or queue processing)

        # Store output_directory in options for deletion cleanup
        job_options = job_data.options or {}
        job_options["output_directory"] = output_directory

        job = ScrapingJob(
            source_url=str(job_data.url),  # Required field
            target_format="html",  # Default target format
            max_retries=job_data.max_retries,
            options=job_options,
        )

        db.add(job)
        # Session dependency handles commit - just refresh to get ID
        await db.flush()

        # Publish job created event
        await publish_job_created(
            job_id=job.id, url=str(job_data.url), domain=domain, status=job.status
        )

        return job

    @staticmethod
    async def get_job(db: AsyncSession, job_id: str) -> ScrapingJob | None:
        """Get a job by ID.

        Args:
            db: Database session
            job_id: Job ID

        Returns:
            Job instance or None
        """
        result = await db.execute(
            select(ScrapingJob)
            .options(selectinload(ScrapingJob.content_results))
            .where(ScrapingJob.id == job_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_jobs(
        db: AsyncSession,
        skip: int = 0,
        limit: int = API_DEFAULT_LIMIT,
        status: JobStatus | None = None,
        domain: str | None = None,
        user_id: str | None = None,
    ) -> tuple[list[ScrapingJob], int]:
        """Get paginated list of jobs with optional filters.

        Args:
            db: Database session
            skip: Number of records to skip
            limit: Maximum number of records to return
            status: Filter by job status
            domain: Filter by domain
            user_id: Filter by user ID

        Returns:
            Tuple of (jobs list, total count)
        """
        # Build query with filters - IMPORTANT: Eager load content_results
        query = select(ScrapingJob).options(selectinload(ScrapingJob.content_results))
        count_query = select(func.count(ScrapingJob.id))

        if user_id:
            query = query.where(ScrapingJob.user_id == user_id)
            count_query = count_query.where(ScrapingJob.user_id == user_id)

        if status:
            query = query.where(ScrapingJob.status == status)
            count_query = count_query.where(ScrapingJob.status == status)

        if domain:
            # Filter by domain extracted from source_url
            query = query.where(ScrapingJob.source_url.like(f"%{domain}%"))
            count_query = count_query.where(ScrapingJob.source_url.like(f"%{domain}%"))

        # Apply ordering and pagination
        query = query.order_by(ScrapingJob.created_at.desc()).offset(skip).limit(limit)

        # Execute queries
        jobs_result = await db.execute(query)
        count_result = await db.execute(count_query)

        jobs = jobs_result.scalars().all()
        total = count_result.scalar() or 0

        return list(jobs), total

    @staticmethod
    async def update_job(db: AsyncSession, job_id: str, job_data: JobUpdate) -> ScrapingJob | None:
        """Update a job.

        Args:
            db: Database session
            job_id: Job ID to update
            job_data: Update data

        Returns:
            Updated job or None if not found
        """
        job = await JobCRUD.get_job(db, job_id)
        if not job:
            return None

        # Update fields
        update_data = job_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            # priority removed - no need for enum conversion
            setattr(job, field, value)

        await db.flush()
        await db.refresh(job)
        return job

    @staticmethod
    async def delete_job(db: AsyncSession, job_id: str) -> bool:
        """Delete a job and its associated output files.

        Args:
            db: Database session
            job_id: Job ID to delete

        Returns:
            True if deleted, False if not found
        """
        import shutil
        from pathlib import Path
        from urllib.parse import urlparse

        from src.core.logging_hierarchy import get_api_logger

        logger = get_api_logger()

        job = await JobCRUD.get_job(db, job_id)
        if not job:
            return False

        # Store job data for event publishing before deletion
        job_url = job.source_url
        parsed_url = urlparse(job.source_url)
        job_domain = parsed_url.netloc

        # Clean up output files if output_directory is stored in options
        if job.options and "output_directory" in job.options:
            output_dir_str = job.options["output_directory"]
            try:
                output_path = Path(output_dir_str)

                # CRITICAL: Only delete if path is relative or under /app/converted_content
                # Security check to prevent accidental deletion of system directories
                if output_path.is_absolute():
                    # Allow only paths starting with /app/converted_content
                    if not str(output_path).startswith("/app/converted_content"):
                        logger.warning(
                            "Refusing to delete absolute path outside converted_content",
                            job_id=job_id,
                            output_dir=output_dir_str,
                        )
                    else:
                        if output_path.exists():
                            shutil.rmtree(output_path)
                            logger.info(
                                "Deleted job output directory",
                                job_id=job_id,
                                output_dir=output_dir_str,
                            )
                else:
                    # Relative paths are resolved relative to /app/converted_content
                    full_path = Path("/app/converted_content") / output_path
                    if full_path.exists():
                        shutil.rmtree(full_path)
                        logger.info(
                            "Deleted job output directory",
                            job_id=job_id,
                            output_dir=str(full_path),
                        )
            except Exception as e:
                # Log error but don't fail the job deletion
                logger.error(
                    "Failed to delete job output directory",
                    job_id=job_id,
                    output_dir=output_dir_str,
                    error=str(e),
                )

        # Delete job from database (cascade deletes content_results and job_logs)
        await db.delete(job)

        # Publish job deleted event
        await publish_job_deleted(job_id=job_id, url=job_url, domain=job_domain)

        return True

    @staticmethod
    async def update_job_status(
        db: AsyncSession,
        job_id: str,
        status: JobStatus,
        error_message: str | None = None,
    ) -> ScrapingJob | None:
        """Update job status and error information.

        Args:
            db: Database session
            job_id: Job ID
            status: New status
            error_message: Error message if failed

        Returns:
            Updated job or None if not found
        """
        job = await JobCRUD.get_job(db, job_id)
        if not job:
            return None

        # Store previous status for event publishing
        previous_status = job.status
        new_status = status.value if hasattr(status, "value") else str(status)

        # Extract domain from source_url for event publishing
        from urllib.parse import urlparse

        parsed_url = urlparse(job.source_url)
        job_domain = parsed_url.netloc

        job.status = new_status
        if error_message:
            job.error_message = error_message
        # Note: error_type field doesn't exist on ScrapingJob model
        # Error details are stored in error_message only

        # Set timestamps based on status
        now = datetime.now(UTC)
        if status == JobStatus.RUNNING and not job.started_at:
            job.started_at = now
        elif (
            status in {JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED}
            and not job.completed_at
        ):
            job.completed_at = now
            # Note: success field doesn't exist on ScrapingJob model
            # Success is determined by status == JobStatus.COMPLETED

        await db.flush()
        await db.refresh(job)

        # Publish status update event (only if status actually changed)
        if previous_status != new_status:
            await publish_job_status_update(
                job_id=job.id,
                old_status=previous_status,
                new_status=new_status,
                url=job.source_url,
                domain=job_domain,
                error_message=error_message,
                processing_time_ms=job.processing_time_ms,
            )

        return job


class ContentResultCRUD:
    """CRUD operations for content results."""

    @staticmethod
    async def get_content_result(db: AsyncSession, result_id: int) -> ContentResult | None:
        """Get a content result by ID.

        Args:
            db: Database session
            result_id: Content result ID

        Returns:
            Content result or None
        """
        result = await db.execute(select(ContentResult).where(ContentResult.id == result_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def get_content_results_by_job(db: AsyncSession, job_id: str) -> list[ContentResult]:
        """Get all content results for a job.

        Args:
            db: Database session
            job_id: Job ID

        Returns:
            List of content results
        """
        result = await db.execute(
            select(ContentResult)
            .where(ContentResult.job_id == job_id)
            .order_by(ContentResult.created_at.desc())
        )
        return list(result.scalars().all())
