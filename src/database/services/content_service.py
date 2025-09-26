"""Content results management service following Single Responsibility Principle.

This module handles all content-related database operations including:
- Saving conversion results
- Retrieving content by job
- Managing content metadata
"""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy.exc import IntegrityError

from src.utils.logging import get_logger

from ...core.exceptions import DatabaseError, ValidationError
from ..models import ContentResult
from .base import BaseService

logger = get_logger(__name__)


class ContentService(BaseService):
    """Service for content results management."""

    def save_content_result(
        self,
        job_id: str,
        content: str,
        content_type: str = "html",
        metadata: dict[str, Any] | None = None,
    ) -> ContentResult:
        """Save conversion content result for a job.

        Args:
            job_id: Associated job identifier
            content: Converted content (HTML, JSON, etc.)
            content_type: Type of content (html, json, markdown)
            metadata: Additional metadata about the content

        Returns:
            Created content result instance

        Raises:
            DatabaseError: If save operation fails
            ValidationError: If input data is invalid
        """
        logger.info("Saving content result", job_id=job_id, content_type=content_type)

        if not job_id:
            raise ValidationError("Job ID is required", field="job_id")

        if not content:
            raise ValidationError("Content cannot be empty", field="content")

        try:
            with self.get_session() as session:
                # Check if content result already exists for this job
                existing = session.query(ContentResult).filter_by(job_id=job_id).first()

                if existing:
                    # Update existing content result
                    logger.debug("Updating existing content result", job_id=job_id)
                    # Map content to appropriate field based on content type
                    if content_type == "original":
                        existing.original_html = content
                    elif content_type == "converted":
                        existing.converted_html = content
                    elif content_type == "shopify":
                        existing.shopify_html = content
                    else:
                        existing.converted_html = content  # Default to converted

                    existing.extra_metadata = metadata or {}
                    existing.updated_at = datetime.now(UTC)
                    result = existing
                else:
                    # Create new content result
                    logger.debug("Creating new content result", job_id=job_id)
                    # Map content to appropriate field based on content type
                    html_fields = {}
                    if content_type == "original":
                        html_fields["original_html"] = content
                    elif content_type == "converted":
                        html_fields["converted_html"] = content
                    elif content_type == "shopify":
                        html_fields["shopify_html"] = content
                    else:
                        html_fields["converted_html"] = content  # Default to converted

                    result = ContentResult(
                        job_id=job_id,
                        extra_metadata=metadata or {},
                        created_at=datetime.now(UTC),
                        **html_fields,
                    )
                    session.add(result)

                session.flush()

                # Calculate content size for logging
                content_size = len(content.encode("utf-8")) if content else 0
                logger.info(
                    "Content result saved successfully",
                    job_id=job_id,
                    content_size=content_size,
                )
                return result

        except IntegrityError as e:
            logger.error("Content save failed - integrity error", job_id=job_id, error=str(e))
            raise DatabaseError("save content result", e) from e
        except Exception as e:
            logger.error("Content save failed", job_id=job_id, error=str(e))
            raise DatabaseError("save content result", e) from e

    def get_content_by_job(self, job_id: str) -> ContentResult | None:
        """Get content result for a specific job.

        Args:
            job_id: Job identifier

        Returns:
            Content result instance or None if not found
        """
        logger.debug("Getting content for job", job_id=job_id)

        try:
            with self.get_session() as session:
                result = session.query(ContentResult).filter_by(job_id=job_id).first()

                if result:
                    # Determine content type based on which field has data
                    content_type = "unknown"
                    size_bytes = 0
                    if result.original_html:
                        content_type = "original"
                        size_bytes = len(result.original_html.encode("utf-8"))
                    elif result.converted_html:
                        content_type = "converted"
                        size_bytes = len(result.converted_html.encode("utf-8"))
                    elif result.shopify_html:
                        content_type = "shopify"
                        size_bytes = len(result.shopify_html.encode("utf-8"))

                    logger.debug(
                        "Content found",
                        job_id=job_id,
                        content_type=content_type,
                        size_bytes=size_bytes,
                    )
                else:
                    logger.debug("No content found for job", job_id=job_id)

                return result

        except Exception as e:
            logger.error("Failed to get content", job_id=job_id, error=str(e))
            raise DatabaseError("get content by job", e) from e

    def get_content_metadata(self, job_id: str) -> dict[str, Any] | None:
        """Get only metadata for content without loading full content.

        Args:
            job_id: Job identifier

        Returns:
            Dictionary with content metadata or None if not found
        """
        logger.debug("Getting content metadata", job_id=job_id)

        try:
            with self.get_session() as session:
                result = session.query(ContentResult).filter_by(job_id=job_id).first()

                if result:
                    # Determine content type and size from available fields
                    content_type = "unknown"
                    content_size_bytes = 0
                    if result.original_html:
                        content_type = "original"
                        content_size_bytes = len(result.original_html.encode("utf-8"))
                    elif result.converted_html:
                        content_type = "converted"
                        content_size_bytes = len(result.converted_html.encode("utf-8"))
                    elif result.shopify_html:
                        content_type = "shopify"
                        content_size_bytes = len(result.shopify_html.encode("utf-8"))

                    metadata = {
                        "job_id": result.job_id,
                        "content_type": content_type,
                        "content_size_bytes": content_size_bytes,
                        "created_at": result.created_at.isoformat() if result.created_at else None,
                        "updated_at": result.updated_at.isoformat() if result.updated_at else None,
                        "extra_metadata": result.extra_metadata,
                        "title": result.title,
                        "author": result.author,
                        "published_date": result.published_date.isoformat()
                        if result.published_date
                        else None,
                        "word_count": result.word_count,
                        "image_count": result.image_count,
                        "link_count": result.link_count,
                    }
                    logger.debug("Content metadata retrieved", job_id=job_id, metadata=metadata)
                    return metadata
                else:
                    logger.debug("No content metadata found", job_id=job_id)
                    return None

        except Exception as e:
            logger.error("Failed to get content metadata", job_id=job_id, error=str(e))
            raise DatabaseError("get content metadata", e) from e

    def delete_content(self, job_id: str) -> bool:
        """Delete content result for a job.

        Args:
            job_id: Job identifier

        Returns:
            True if content was deleted, False if not found
        """
        logger.info("Deleting content", job_id=job_id)

        try:
            with self.get_session() as session:
                result = session.query(ContentResult).filter_by(job_id=job_id).first()

                if result:
                    session.delete(result)
                    logger.info("Content deleted successfully", job_id=job_id)
                    return True
                else:
                    logger.debug("No content to delete", job_id=job_id)
                    return False

        except Exception as e:
            logger.error("Failed to delete content", job_id=job_id, error=str(e))
            raise DatabaseError("delete content", e) from e
