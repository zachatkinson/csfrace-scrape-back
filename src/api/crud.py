"""CRUD operations for API endpoints using async SQLAlchemy 2.0."""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..database.models import Batch, ContentResult, JobPriority, JobStatus, ScrapingJob
from .schemas import BatchCreate, JobCreate, JobUpdate


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

        # Generate slug from URL (always auto-generated)
        path = parsed_url.path.strip("/")
        slug = path.split("/")[-1] if path else "index"

        # Generate output directory if not provided
        output_directory = job_data.output_directory
        if not output_directory:
            output_directory = f"converted_content/{domain}_{slug}"

        job = ScrapingJob(
            url=str(job_data.url),
            domain=domain,
            slug=slug,
            priority=job_data.priority,
            custom_slug=job_data.custom_slug,
            output_directory=output_directory,
            max_retries=job_data.max_retries,
            timeout_seconds=job_data.timeout_seconds,
            skip_existing=job_data.skip_existing,
            converter_config=job_data.converter_config,
            processing_options=job_data.processing_options,
        )

        db.add(job)
        await db.flush()
        await db.refresh(job)
        return job

    @staticmethod
    async def get_job(db: AsyncSession, job_id: int) -> Optional[ScrapingJob]:
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
        limit: int = 100,
        status: Optional[JobStatus] = None,
        domain: Optional[str] = None,
    ) -> tuple[list[ScrapingJob], int]:
        """Get paginated list of jobs with optional filters.

        Args:
            db: Database session
            skip: Number of records to skip
            limit: Maximum number of records to return
            status: Filter by job status
            domain: Filter by domain

        Returns:
            Tuple of (jobs list, total count)
        """
        # Build query with filters
        query = select(ScrapingJob)
        count_query = select(func.count(ScrapingJob.id))

        if status:
            query = query.where(ScrapingJob.status == status)
            count_query = count_query.where(ScrapingJob.status == status)

        if domain:
            query = query.where(ScrapingJob.domain == domain)
            count_query = count_query.where(ScrapingJob.domain == domain)

        # Apply ordering and pagination
        query = query.order_by(ScrapingJob.created_at.desc()).offset(skip).limit(limit)

        # Execute queries
        jobs_result = await db.execute(query)
        count_result = await db.execute(count_query)

        jobs = jobs_result.scalars().all()
        total = count_result.scalar() or 0

        return list(jobs), total

    @staticmethod
    async def update_job(
        db: AsyncSession, job_id: int, job_data: JobUpdate
    ) -> Optional[ScrapingJob]:
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
            setattr(job, field, value)

        await db.flush()
        await db.refresh(job)
        return job

    @staticmethod
    async def delete_job(db: AsyncSession, job_id: int) -> bool:
        """Delete a job.

        Args:
            db: Database session
            job_id: Job ID to delete

        Returns:
            True if deleted, False if not found
        """
        job = await JobCRUD.get_job(db, job_id)
        if not job:
            return False

        await db.delete(job)
        return True

    @staticmethod
    async def update_job_status(
        db: AsyncSession,
        job_id: int,
        status: JobStatus,
        error_message: Optional[str] = None,
        error_type: Optional[str] = None,
    ) -> Optional[ScrapingJob]:
        """Update job status and error information.

        Args:
            db: Database session
            job_id: Job ID
            status: New status
            error_message: Error message if failed
            error_type: Error type if failed

        Returns:
            Updated job or None if not found
        """
        job = await JobCRUD.get_job(db, job_id)
        if not job:
            return None

        job.status = status
        if error_message:
            job.error_message = error_message
        if error_type:
            job.error_type = error_type

        # Set timestamps based on status
        now = datetime.now(timezone.utc)
        if status == JobStatus.RUNNING and not job.started_at:
            job.started_at = now
        elif status in {JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED}:
            if not job.completed_at:
                job.completed_at = now
            job.success = status == JobStatus.COMPLETED

        await db.flush()
        await db.refresh(job)
        return job


class BatchCRUD:
    """CRUD operations for batches."""

    @staticmethod
    async def create_batch(db: AsyncSession, batch_data: BatchCreate) -> Batch:
        """Create a new batch with jobs.

        Args:
            db: Database session
            batch_data: Batch creation data

        Returns:
            Created batch instance
        """
        # Create batch
        batch = Batch(
            name=batch_data.name,
            description=batch_data.description,
            max_concurrent=batch_data.max_concurrent,
            continue_on_error=batch_data.continue_on_error,
            output_base_directory=batch_data.output_base_directory
            or f"batch_output/{batch_data.name}",
            create_archives=batch_data.create_archives,
            cleanup_after_archive=batch_data.cleanup_after_archive,
            batch_config=batch_data.batch_config,
            total_jobs=len(batch_data.urls),
        )

        db.add(batch)
        await db.flush()
        await db.refresh(batch)

        # Create jobs for each URL
        for i, url in enumerate(batch_data.urls):
            job_data = JobCreate(
                url=url,
                priority=JobPriority.NORMAL,
                output_directory=f"{batch.output_base_directory}/job_{i + 1}",
            )
            job = await JobCRUD.create_job(db, job_data)
            job.batch_id = batch.id

        await db.flush()
        await db.refresh(batch)
        return batch

    @staticmethod
    async def get_batch(db: AsyncSession, batch_id: int) -> Optional[Batch]:
        """Get a batch by ID.

        Args:
            db: Database session
            batch_id: Batch ID

        Returns:
            Batch instance or None
        """
        result = await db.execute(
            select(Batch).options(selectinload(Batch.jobs)).where(Batch.id == batch_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_batches(
        db: AsyncSession, skip: int = 0, limit: int = 100
    ) -> tuple[list[Batch], int]:
        """Get paginated list of batches.

        Args:
            db: Database session
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            Tuple of (batches list, total count)
        """
        # Get batches with jobs loaded
        batches_result = await db.execute(
            select(Batch)
            .options(selectinload(Batch.jobs))
            .order_by(Batch.created_at.desc())
            .offset(skip)
            .limit(limit)
        )

        # Get total count
        count_result = await db.execute(select(func.count(Batch.id)))

        batches = batches_result.scalars().all()
        total = count_result.scalar() or 0

        return list(batches), total


class ContentResultCRUD:
    """CRUD operations for content results."""

    @staticmethod
    async def get_content_result(db: AsyncSession, result_id: int) -> Optional[ContentResult]:
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
    async def get_content_results_by_job(db: AsyncSession, job_id: int) -> list[ContentResult]:
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
