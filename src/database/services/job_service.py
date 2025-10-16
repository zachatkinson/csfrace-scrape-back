"""Job management service following Single Responsibility Principle.

This module handles all job-related database operations including:
- Job creation (single and batch)
- Job retrieval and filtering
- Job status updates
- Job lifecycle management
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import and_, desc, select
from sqlalchemy.orm import Session

from src.core.decorators import database_error_handler
from src.core.logging_hierarchy import get_database_logger
from src.utils.url_utils import extract_domain

from ...common.status import JobStatus
from ...constants import API_DEFAULT_LIMIT
from ...core.exceptions import ValidationError
from ..models import ScrapingJob
from ..queries import JobQueries, QueryBuilder

logger = get_database_logger(__name__).logger


@dataclass
class JobCreateRequest:
    """Request object for creating scraping jobs."""

    url: str
    output_directory: str
    user_id: str  # MANDATORY - no default system user (ZERO TOLERANCE)
    max_retries: int = 3
    options: dict[str, Any] | None = None
    batch_id: str | None = None

    def __post_init__(self) -> None:
        """Validate and normalize job creation request."""
        if not self.url or not self.url.strip():
            raise ValidationError("URL is required", field="url")

        if not self.output_directory or not self.output_directory.strip():
            raise ValidationError("Output directory is required", field="output_directory")

        self.url = self.url.strip()
        self.output_directory = self.output_directory.strip()
        self.options = self.options or {}


class JobService:
    """Service for job management operations."""

    def __init__(self, session: Session) -> None:
        """Initialize with provided database session."""
        self.session = session

    @database_error_handler("job creation")
    def create_job(self, request: JobCreateRequest) -> ScrapingJob:
        """Create a new scraping job.

        Args:
            request: Job creation request with all required fields

        Returns:
            Created job instance

        Raises:
            DatabaseError: If job creation fails
            ValidationError: If request data is invalid
        """
        logger.info("Creating job", url=request.url)

        # Create job with auto-generated metadata
        # Note: output_directory stored in options, not as direct field
        job_options = request.options or {}
        job_options["output_directory"] = request.output_directory

        job = ScrapingJob(
            user_id=request.user_id,
            source_url=request.url,
            max_retries=request.max_retries,
            options=job_options,
            batch_id=request.batch_id,
            domain=self._extract_domain_safely(request.url),
            status=JobStatus.PENDING.value,
            created_at=datetime.now(UTC),
        )

        self.session.add(job)
        self.session.flush()  # Get the ID
        self.session.refresh(job)  # Keep job attached to session

        logger.info("Job created successfully", job_id=job.id, domain=job.domain)
        return job

    def _extract_domain_safely(self, url: str) -> str:
        """Extract domain from URL safely.

        Args:
            url: URL to extract domain from

        Returns:
            Domain string or 'unknown' if extraction fails
        """
        return extract_domain(url)

    @database_error_handler("create batch jobs")
    def create_jobs(self, urls: list[str], **job_config: Any) -> list[ScrapingJob]:
        """Create multiple jobs in batch with shared configuration.

        Args:
            urls: List of URLs to process
            **job_config: Shared job configuration (output_directory, max_retries, etc.)

        Returns:
            List of created job instances

        Raises:
            DatabaseError: If batch job creation fails
            ValidationError: If any URL is invalid
        """
        logger.info("Creating batch jobs", url_count=len(urls), config=job_config)

        if not urls:
            raise ValidationError("At least one URL is required", field="urls")

        batch_id = str(uuid4()) if len(urls) > 1 else None
        jobs = []

        for url in urls:
            request = JobCreateRequest(url=url, batch_id=batch_id, **job_config)

            # Note: output_directory stored in options, not as direct field
            job_options = request.options or {}
            job_options["output_directory"] = request.output_directory

            job = ScrapingJob(
                user_id=request.user_id,
                source_url=request.url,
                max_retries=request.max_retries,
                options=job_options,
                batch_id=batch_id,
                domain=self._extract_domain_safely(request.url),
                status=JobStatus.PENDING.value,
                created_at=datetime.now(UTC),
            )

            self.session.add(job)
            jobs.append(job)

        self.session.flush()  # Get all IDs

        # Refresh all jobs to keep them attached to session
        for job in jobs:
            self.session.refresh(job)

        logger.info("Batch jobs created successfully", job_count=len(jobs), batch_id=batch_id)
        return jobs

    @database_error_handler("get job")
    def get_job(self, job_id: str) -> ScrapingJob | None:
        """Get job by ID.

        Args:
            job_id: Job identifier

        Returns:
            Job instance or None if not found
        """
        logger.debug("Getting job", job_id=job_id)

        job: ScrapingJob | None = self.session.get(ScrapingJob, job_id)
        if job:
            logger.debug("Job found", job_id=job_id, status=job.status)
        else:
            logger.debug("Job not found", job_id=job_id)
        return job

    @database_error_handler("update job status")
    def update_job_status(
        self,
        job_id: str,
        new_status: JobStatus,
        error_message: str | None = None,
        processing_time_ms: int | None = None,
    ) -> ScrapingJob | None:
        """Update job status with metadata.

        Args:
            job_id: Job identifier
            new_status: New job status
            error_message: Error message if status is FAILED
            processing_time_ms: Processing time in milliseconds

        Returns:
            Updated job instance or None if not found

        Raises:
            DatabaseError: If update fails
        """
        logger.info("Updating job status", job_id=job_id, new_status=new_status.name)

        job: ScrapingJob | None = self.session.get(ScrapingJob, job_id)
        if not job:
            logger.warning("Job not found for status update", job_id=job_id)
            return None

        previous_status = job.status

        # Update status and metadata
        job.status = new_status.value
        job.error_message = error_message

        if processing_time_ms is not None:
            job.processing_time_ms = processing_time_ms

        # Update timestamps based on status
        now = datetime.now(UTC)
        if new_status == JobStatus.RUNNING and not job.started_at:
            job.started_at = now
        elif new_status in {JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED}:
            job.completed_at = now

        self.session.flush()

        logger.info(
            "Job status updated successfully",
            job_id=job_id,
            previous_status=previous_status,
            new_status=new_status.name,
        )
        return job

    @database_error_handler("get pending jobs")
    def get_pending_jobs(self, limit: int = API_DEFAULT_LIMIT) -> list[ScrapingJob]:
        """Get pending jobs ordered by creation time.

        Args:
            limit: Maximum number of jobs to return

        Returns:
            List of pending jobs ordered by creation time
        """
        logger.debug("Getting pending jobs", limit=limit)

        # Use centralized query pattern for DRY compliance
        stmt = JobQueries.find_pending_jobs(ScrapingJob).limit(limit)

        jobs = self.session.execute(stmt).scalars().all()

        # Eagerly load attributes to prevent DetachedInstanceError
        for job in jobs:
            # Access all attributes to load them into the session
            _ = job.source_url, job.domain, job.status
            self.session.expunge(job)  # Detach from session for safe return

        logger.debug("Pending jobs retrieved", count=len(jobs))
        return list(jobs)

    @database_error_handler("get jobs by status")
    def get_jobs_by_status(
        self,
        status: JobStatus,
        limit: int = API_DEFAULT_LIMIT,
        domain: str | None = None,
        offset: int = 0,
    ) -> list[ScrapingJob]:
        """Get jobs filtered by status and optionally by domain.

        Args:
            status: Job status to filter by
            limit: Maximum number of jobs to return
            domain: Optional domain filter
            offset: Number of records to skip for pagination

        Returns:
            List of jobs matching the criteria
        """
        logger.debug(
            "Getting jobs by status", status=status.name, limit=limit, domain=domain, offset=offset
        )

        # Use centralized query pattern for DRY compliance
        filters = {"status": status.value}
        if domain:
            filters["domain"] = domain

        stmt = QueryBuilder.find_by_multiple_fields(ScrapingJob, filters)
        stmt = stmt.order_by(desc(ScrapingJob.created_at)).limit(limit).offset(offset)

        jobs = self.session.execute(stmt).scalars().all()

        # Eagerly load attributes to prevent DetachedInstanceError
        for job in jobs:
            # Access all attributes to load them into the session
            _ = job.source_url, job.domain, job.status
            self.session.expunge(job)  # Detach from session for safe return

        logger.debug("Jobs by status retrieved", status=status.name, count=len(jobs), domain=domain)
        return list(jobs)

    @database_error_handler("get retry jobs")
    def get_retry_jobs(self, max_jobs: int = 50) -> list[ScrapingJob]:
        """Get jobs that can be retried.

        Args:
            max_jobs: Maximum number of jobs to return

        Returns:
            List of failed jobs that haven't exceeded retry limit
        """
        logger.debug("Getting retry jobs", max_jobs=max_jobs)

        stmt = (
            select(ScrapingJob)
            .where(
                and_(
                    ScrapingJob.status == JobStatus.FAILED.value,
                    ScrapingJob.retry_count < ScrapingJob.max_retries,
                    # Include jobs with NULL completed_at or those with completed_at in the past
                    (ScrapingJob.completed_at.is_(None))
                    | (ScrapingJob.completed_at <= datetime.now(UTC)),
                )
            )
            .order_by(ScrapingJob.created_at)
            .limit(max_jobs)
        )

        jobs = self.session.execute(stmt).scalars().all()

        # Eagerly load attributes to prevent DetachedInstanceError
        for job in jobs:
            # Access all attributes to load them into the session
            _ = job.source_url, job.domain, job.status
            self.session.expunge(job)  # Detach from session for safe return

        logger.debug("Retry jobs retrieved", count=len(jobs))
        return list(jobs)

    @database_error_handler("get batch jobs")
    def get_batch_jobs(self, batch_id: str) -> list[ScrapingJob]:
        """Get all jobs in a batch.

        Args:
            batch_id: Batch identifier

        Returns:
            List of jobs in the batch
        """
        logger.debug("Getting batch jobs", batch_id=batch_id)

        # Use centralized query pattern for DRY compliance
        stmt = QueryBuilder.find_by_field(ScrapingJob, ScrapingJob.batch_id, batch_id)  # type: ignore[arg-type]
        stmt = stmt.order_by(ScrapingJob.created_at)

        jobs = self.session.execute(stmt).scalars().all()

        # Eagerly load attributes to prevent DetachedInstanceError
        for job in jobs:
            # Access all attributes to load them into the session
            _ = job.source_url, job.domain, job.status
            self.session.expunge(job)  # Detach from session for safe return

        logger.debug("Batch jobs retrieved", batch_id=batch_id, count=len(jobs))
        return list(jobs)

    @database_error_handler("get batch summary")
    def get_batch_summary(self, batch_id: str) -> dict[str, Any]:
        """Get batch processing summary.

        Args:
            batch_id: Batch identifier

        Returns:
            Dictionary with batch statistics and status
        """
        logger.debug("Getting batch summary", batch_id=batch_id)

        # Query fresh job data from database (don't use get_batch_jobs which detaches)
        stmt = QueryBuilder.find_by_field(ScrapingJob, ScrapingJob.batch_id, batch_id)  # type: ignore[arg-type]
        stmt = stmt.order_by(ScrapingJob.created_at)
        jobs = self.session.execute(stmt).scalars().all()

        if not jobs:
            logger.warning("No jobs found for batch", batch_id=batch_id)
            return {
                "batch_id": batch_id,
                "total_jobs": 0,
                "status_counts": {},
                "overall_status": "empty",
            }

        # Calculate statistics
        status_counts: dict[str, int] = {}
        unique_statuses = set()
        for job in jobs:
            status_counts[job.status] = status_counts.get(job.status, 0) + 1
            unique_statuses.add(job.status)

        # Determine overall batch status with proper mixed status detection
        if all(job.status == JobStatus.COMPLETED.value for job in jobs):
            overall_status = "completed"
        elif all(job.status in {JobStatus.FAILED.value, JobStatus.CANCELLED.value} for job in jobs):
            overall_status = "failed"
        elif len(unique_statuses) > 1:
            # Mixed statuses if we have more than one distinct status
            overall_status = "mixed"
        elif any(job.status == JobStatus.RUNNING.value for job in jobs):
            overall_status = "running"
        elif any(job.status == JobStatus.PENDING.value for job in jobs):
            overall_status = "pending"
        else:
            overall_status = "mixed"

        summary = {
            "batch_id": batch_id,
            "total_jobs": len(jobs),
            "status_counts": status_counts,
            "overall_status": overall_status,
            "created_at": jobs[0].created_at.isoformat() if jobs[0].created_at else None,
        }

        logger.debug("Batch summary calculated", batch_id=batch_id, summary=summary)
        return summary
