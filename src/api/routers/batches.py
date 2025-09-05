"""Batch management API endpoints."""

from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Request, status
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.exc import SQLAlchemyError

from ...batch.processor import BatchConfig, BatchProcessor
from ...database.models import JobStatus
from ..crud import BatchCRUD, JobCRUD
from ..dependencies import DBSession, async_session
from ..schemas import BatchCreate, BatchListResponse, BatchResponse, BatchWithJobsResponse
from ..utils import create_response_dict

router = APIRouter(prefix="/batches", tags=["Batches"])
limiter = Limiter(key_func=get_remote_address)


async def execute_batch_processing(batch_id: int, output_base_dir: str, max_concurrent: int = 5):
    """Background task to execute batch processing.

    Args:
        batch_id: Database batch ID
        output_base_dir: Base output directory for batch
        max_concurrent: Maximum concurrent jobs
    """
    async with async_session() as db:
        try:
            # Get the batch and its jobs
            batch = await BatchCRUD.get_batch(db, batch_id)
            if not batch:
                return

            # Update batch status to running
            batch.status = JobStatus.RUNNING
            await db.commit()

            # Configure batch processor
            batch_config = BatchConfig(
                max_concurrent=max_concurrent,
                output_base_dir=Path(output_base_dir),
                create_summary=True,
                continue_on_error=batch.continue_on_error,
            )

            processor = BatchProcessor(batch_config)

            # Add all jobs to the processor
            for job in batch.jobs:
                processor.add_job(job.url, output_dir=Path(job.output_directory))
                # Update individual job status
                await JobCRUD.update_job_status(db, job.id, JobStatus.RUNNING)

            # Process the batch
            await processor.process_all()

            # Update batch and job statuses based on results
            completed_jobs = 0
            failed_jobs = 0

            for job in batch.jobs:
                # Check if job output exists to determine success
                job_output = Path(job.output_directory)
                if job_output.exists() and any(job_output.iterdir()):
                    await JobCRUD.update_job_status(db, job.id, JobStatus.COMPLETED)
                    completed_jobs += 1
                else:
                    await JobCRUD.update_job_status(
                        db,
                        job.id,
                        JobStatus.FAILED,
                        error_message="No output generated",
                        error_type="ProcessingError",
                    )
                    failed_jobs += 1

            # Update batch statistics
            batch.completed_jobs = completed_jobs
            batch.failed_jobs = failed_jobs
            batch.status = JobStatus.COMPLETED

            await db.commit()

        except Exception:
            # Mark batch as failed
            batch = await BatchCRUD.get_batch(db, batch_id)
            if batch:
                batch.status = JobStatus.FAILED
                await db.commit()
            raise


@router.post("/", response_model=BatchResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit(
    "10/hour"
)  # Allow 10 batch creations per hour per IP (more restrictive than single jobs)
async def create_batch(
    request: Request,  # Required for rate limiting  # pylint: disable=unused-argument
    batch_data: BatchCreate,
    background_tasks: BackgroundTasks,
    db: DBSession,
) -> BatchResponse:
    """Create a new batch with multiple jobs and start background processing.

    Args:
        batch_data: Batch creation data
        background_tasks: FastAPI background tasks
        db: Database session

    Returns:
        Created batch details

    Raises:
        HTTPException: If batch creation fails
    """
    try:
        # Create the batch record first
        batch = await BatchCRUD.create_batch(db, batch_data)

        # Add background task to execute the batch processing
        background_tasks.add_task(
            execute_batch_processing, batch.id, batch.output_base_directory, batch.max_concurrent
        )

        return BatchResponse.model_validate(batch)
    except SQLAlchemyError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create batch: {str(e)}",
        ) from e


@router.get("/", response_model=BatchListResponse)
async def list_batches(
    db: DBSession,
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=200, description="Items per page"),
) -> BatchListResponse:
    """Get paginated list of batches.

    Args:
        db: Database session
        page: Page number (1-based)
        page_size: Number of items per page

    Returns:
        Paginated batch list
    """
    try:
        skip = (page - 1) * page_size
        batches, total = await BatchCRUD.get_batches(db, skip=skip, limit=page_size)

        response_data = create_response_dict(
            response_class=BatchListResponse,
            items_key="batches",
            items=[BatchResponse.model_validate(batch) for batch in batches],
            total=total,
            page=page,
            page_size=page_size,
        )

        return BatchListResponse(**response_data)
    except SQLAlchemyError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve batches: {str(e)}",
        ) from e


@router.get("/{batch_id}", response_model=BatchWithJobsResponse)
async def get_batch(batch_id: int, db: DBSession) -> BatchWithJobsResponse:
    """Get a specific batch by ID.

    Args:
        batch_id: Batch ID
        db: Database session

    Returns:
        Batch details with jobs

    Raises:
        HTTPException: If batch not found
    """
    try:
        batch = await BatchCRUD.get_batch(db, batch_id)
        if not batch:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=f"Batch {batch_id} not found"
            )
        return BatchWithJobsResponse.model_validate(batch)
    except SQLAlchemyError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve batch: {str(e)}",
        ) from e
