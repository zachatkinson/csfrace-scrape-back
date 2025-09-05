"""Common utilities for API endpoints."""

from fastapi import HTTPException, status
from sqlalchemy.exc import SQLAlchemyError


def handle_database_error(operation: str) -> HTTPException:
    """Create a standardized HTTPException for database errors.
    
    Args:
        operation: The operation that failed (e.g., 'create job', 'retrieve batches')
    
    Returns:
        Standardized HTTPException for database errors
    """
    def error_handler(e: SQLAlchemyError) -> HTTPException:
        return HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to {operation}: {str(e)}",
        )
    return error_handler


def create_paginated_response(items: list, total: int, page: int, page_size: int) -> dict:
    """Create a standardized paginated response structure.
    
    Args:
        items: List of items for current page
        total: Total number of items
        page: Current page number
        page_size: Number of items per page
    
    Returns:
        Dictionary with pagination structure
    """
    total_pages = (total + page_size - 1) // page_size
    
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
    }