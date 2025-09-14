"""Pydantic schemas for API request/response models."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, HttpUrl

from ..common.status import JobPriority
from ..constants import (
    API_MAX_CONCURRENT_JOBS,
    API_MAX_NAME_LENGTH,
    API_MAX_RETRIES_LIMIT,
    API_MAX_TIMEOUT_SECONDS,
    API_MAX_URLS_PER_BATCH,
    API_MIN_TIMEOUT_SECONDS,
)


# Base schemas
class BaseSchema(BaseModel):
    """Base schema with common configuration."""

    model_config = {"from_attributes": True}


# Job-related schemas
class JobCreate(BaseModel):
    """Schema for creating a new scraping job."""

    url: HttpUrl
    slug: str | None = None
    custom_slug: str | None = None
    priority: JobPriority = JobPriority.NORMAL
    output_directory: str | None = None
    max_retries: int = Field(default=3, ge=0, le=API_MAX_RETRIES_LIMIT)
    timeout_seconds: int = Field(default=30, ge=API_MIN_TIMEOUT_SECONDS, le=API_MAX_TIMEOUT_SECONDS)
    skip_existing: bool = False
    options: dict[str, Any] | None = None
    processing_options: dict[str, Any] | None = None


class JobUpdate(BaseModel):
    """Schema for updating an existing job."""

    priority: JobPriority | None = None
    max_retries: int | None = Field(None, ge=0, le=API_MAX_RETRIES_LIMIT)
    timeout_seconds: int | None = Field(
        None, ge=API_MIN_TIMEOUT_SECONDS, le=API_MAX_TIMEOUT_SECONDS
    )
    skip_existing: bool | None = None
    options: dict[str, Any] | None = None
    processing_options: dict[str, Any] | None = None


class JobResponse(BaseSchema):
    """Schema for job responses."""

    id: str  # String ID in database model
    source_url: str  # Required field in model
    url: str
    domain: str | None = None
    slug: str | None = None
    status: str  # String status in database model
    priority: str  # String priority in database model
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    retry_count: int
    max_retries: int
    output_directory: str | None = None
    error_message: str | None = None
    error_type: str | None = None
    duration_seconds: float | None = None
    content_size_bytes: int | None = None
    batch_id: str | None = None  # String ID in database model
    options: dict[str, Any] | None = None


class JobListResponse(BaseModel):
    """Schema for paginated job list responses."""

    jobs: list[JobResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


# Batch-related schemas
class BatchCreate(BaseModel):
    """Schema for creating a new batch."""

    name: str = Field(..., min_length=1, max_length=API_MAX_NAME_LENGTH)
    description: str | None = None
    urls: list[HttpUrl] = Field(..., max_length=API_MAX_URLS_PER_BATCH)
    max_concurrent: int = Field(default=5, ge=1, le=API_MAX_CONCURRENT_JOBS)
    continue_on_error: bool = True
    output_base_directory: str | None = None


class BatchResponse(BaseSchema):
    """Schema for batch responses."""

    id: str  # String ID in database model
    name: str
    description: str | None = None
    status: str  # String status in database model
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    max_concurrent: int
    continue_on_error: bool
    output_base_directory: str | None = None
    total_jobs: int
    completed_jobs: int
    failed_jobs: int
    skipped_jobs: int
    success_rate: float  # Computed property


class BatchWithJobsResponse(BatchResponse):
    """Schema for batch responses that include jobs."""

    jobs: list[JobResponse]


class BatchListResponse(BaseModel):
    """Schema for paginated batch list responses."""

    batches: list[BatchResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


# Content result schemas
class ContentResultResponse(BaseSchema):
    """Schema for content result responses."""

    id: int
    job_id: int
    title: str | None = None
    meta_description: str | None = None
    published_date: datetime | None = None
    author: str | None = None
    tags: list[str] | None = None
    categories: list[str] | None = None
    word_count: int | None = None
    image_count: int | None = None
    link_count: int | None = None
    processing_time_seconds: float | None = None
    created_at: datetime
    updated_at: datetime


# Health check schemas
class HealthCheckResponse(BaseModel):
    """Schema for health check responses."""

    status: str
    timestamp: datetime
    version: str
    database: dict[str, Any]
    cache: dict[str, Any]
    monitoring: dict[str, Any]


# Metrics schemas
class MetricsResponse(BaseModel):
    """Schema for metrics responses."""

    timestamp: datetime
    system_metrics: dict[str, Any]
    application_metrics: dict[str, Any]
    database_metrics: dict[str, Any]


# Error schemas
class ErrorResponse(BaseModel):
    """Schema for error responses."""

    detail: str
    error_code: str | None = None
    timestamp: datetime
