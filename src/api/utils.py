"""Common utilities for API endpoints."""

from typing import Any, Dict, List, Type, TypeVar
from fastapi import HTTPException, status
from sqlalchemy.exc import SQLAlchemyError
from pydantic import BaseModel

T = TypeVar('T', bound=BaseModel)


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


def create_response_dict(
    response_class: Type[T],
    items_key: str, 
    items: List[Any], 
    total: int, 
    page: int, 
    page_size: int
) -> Dict[str, Any]:
    """Create a complete response dictionary for paginated endpoints.
    
    Args:
        response_class: The response model class
        items_key: The key name for items in response (e.g., 'jobs', 'batches') 
        items: List of items for current page
        total: Total number of items
        page: Current page number
        page_size: Number of items per page
    
    Returns:
        Dictionary ready for response model validation
    """
    pagination = create_paginated_response(items, total, page, page_size)
    
    return {
        items_key: pagination["items"],
        "total": pagination["total"],
        "page": pagination["page"],
        "page_size": pagination["page_size"],
        "total_pages": pagination["total_pages"],
    }