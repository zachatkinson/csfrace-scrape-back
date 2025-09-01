"""Pydantic schemas for API request/response models."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, HttpUrl

from ..database.models import JobPriority, JobStatus


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
    max_retries: int = Field(default=3, ge=0, le=10)
    timeout_seconds: int = Field(default=30, ge=5, le=300)
    skip_existing: bool = False
    converter_config: dict[str, Any] | None = None
    processing_options: dict[str, Any] | None = None


class JobUpdate(BaseModel):
    """Schema for updating an existing job."""

    priority: JobPriority | None = None
    max_retries: int | None = Field(None, ge=0, le=10)
    timeout_seconds: int | None = Field(None, ge=5, le=300)
    skip_existing: bool | None = None
    converter_config: dict[str, Any] | None = None
    processing_options: dict[str, Any] | None = None


class JobResponse(BaseSchema):
    """Schema for job responses."""

    id: int
    url: str
    domain: str
    slug: str | None = None
    status: JobStatus
    priority: JobPriority
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    retry_count: int
    max_retries: int
    timeout_seconds: int
    output_directory: str
    custom_slug: str | None = None
    skip_existing: bool
    error_message: str | None = None
    error_type: str | None = None
    success: bool
    duration_seconds: float | None = None
    content_size_bytes: int | None = None
    images_downloaded: int
    batch_id: int | None = None
    converter_config: dict[str, Any] | None = None
    processing_options: dict[str, Any] | None = None


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

    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    urls: list[HttpUrl] = Field(..., max_length=1000)
    max_concurrent: int = Field(default=5, ge=1, le=20)
    continue_on_error: bool = True
    output_base_directory: str | None = None
    create_archives: bool = False
    cleanup_after_archive: bool = False
    batch_config: dict[str, Any] | None = None


class BatchResponse(BaseSchema):
    """Schema for batch responses."""

    id: int
    name: str
    description: str | None = None
    status: JobStatus
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    max_concurrent: int
    continue_on_error: bool
    output_base_directory: str
    create_archives: bool
    cleanup_after_archive: bool
    total_jobs: int
    completed_jobs: int
    failed_jobs: int
    skipped_jobs: int
    success_rate: float
    batch_config: dict[str, Any] | None = None


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
