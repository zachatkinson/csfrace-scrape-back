"""Batch management API endpoints."""

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy.exc import SQLAlchemyError

from ..crud import BatchCRUD
from ..dependencies import DBSession
from ..schemas import BatchCreate, BatchListResponse, BatchResponse, BatchWithJobsResponse

router = APIRouter(prefix="/batches", tags=["Batches"])


@router.post("/", response_model=BatchResponse, status_code=status.HTTP_201_CREATED)
async def create_batch(batch_data: BatchCreate, db: DBSession) -> BatchResponse:
    """Create a new batch with multiple jobs.

    Args:
        batch_data: Batch creation data
        db: Database session

    Returns:
        Created batch details

    Raises:
        HTTPException: If batch creation fails
    """
    try:
        batch = await BatchCRUD.create_batch(db, batch_data)
        return BatchResponse.model_validate(batch)
    except SQLAlchemyError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create batch: {str(e)}",
        )


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

        total_pages = (total + page_size - 1) // page_size

        return BatchListResponse(
            batches=[BatchResponse.model_validate(batch) for batch in batches],
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )
    except SQLAlchemyError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve batches: {str(e)}",
        )


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
        )
