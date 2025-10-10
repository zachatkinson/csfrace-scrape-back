"""Pydantic schemas for API request/response models."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, HttpUrl

from src.core.decorators import api_error_handler

from ..constants import (
    API_MAX_RETRIES_LIMIT,
    API_MAX_URLS_PER_BATCH,
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
    # priority: Removed - YAGNI, not used for filtering/ordering/queue processing
    output_directory: str | None = None
    max_retries: int = Field(default=3, ge=0, le=API_MAX_RETRIES_LIMIT)
    # timeout_seconds: removed - not in database model
    # skip_existing: removed - not in database model
    options: dict[str, Any] | None = None
    # processing_options: alias for options to maintain compatibility
    processing_options: dict[str, Any] | None = None


class JobUpdate(BaseModel):
    """Schema for updating an existing job."""

    # priority: Removed - YAGNI (not used for filtering, ordering, or queue processing)
    max_retries: int | None = Field(None, ge=0, le=API_MAX_RETRIES_LIMIT)
    # timeout_seconds: removed - not in database model
    # skip_existing: removed - not in database model
    options: dict[str, Any] | None = None
    # processing_options: alias for options to maintain compatibility
    processing_options: dict[str, Any] | None = None


class JobResponse(BaseSchema):
    """Schema for job responses with embedded content_results metadata."""

    id: str  # String ID in database model
    source_url: str  # Required field in model
    target_format: str  # Actual field in model
    status: str  # String status in database model
    # priority: Removed - YAGNI (not used for filtering, ordering, or queue processing)
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    retry_count: int
    max_retries: int
    error_message: str | None = None
    processing_time_ms: int | None = None  # Actual field in model
    output_size_bytes: int | None = None  # Actual field in model
    batch_id: str | None = None  # String ID in database model
    options: dict[str, Any] | None = None
    progress: int = 0  # Progress tracking (0-100)

    # Embedded content_results metadata (from content_results table)
    title: str | None = None
    meta_description: str | None = None
    word_count: int | None = None
    image_count: int | None = None
    link_count: int | None = None
    author: str | None = None
    published_date: datetime | None = None

    # Computed fields derived from source_url
    @property
    def url(self) -> str:
        """Alias for source_url."""
        return self.source_url

    @property
    def domain(self) -> str:
        """Extract domain from source_url."""
        from urllib.parse import urlparse

        return urlparse(self.source_url).netloc


class JobListResponse(BaseModel):
    """Schema for paginated job list responses."""

    jobs: list[JobResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


# Array-based job creation schema
class JobsCreateRequest(BaseModel):
    """Schema for creating multiple jobs from URL array.

    Elegant approach: Always expect arrays, auto-detect batches vs individual jobs.
    - Single URL: batch_id = None (individual job)
    - Multiple URLs: auto-generate batch_id (batch processing)
    """

    urls: list[HttpUrl] = Field(min_length=1, max_length=API_MAX_URLS_PER_BATCH)
    # priority: Removed - YAGNI (not used for filtering, ordering, or queue processing)
    output_base_directory: str | None = None
    max_retries: int = Field(default=3, ge=0, le=API_MAX_RETRIES_LIMIT)
    options: dict[str, Any] | None = None


class JobsCreateResponse(BaseModel):
    """Schema for jobs creation response."""

    jobs: list[JobResponse]
    batch_id: str | None = None  # Present if multiple URLs (batch), None if single URL
    total_jobs: int


# Content result schemas
class ContentResultResponse(BaseSchema):
    """Schema for content result responses."""

    id: int
    job_id: str  # Fixed: Database model uses string job_id
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


# User Settings schemas
class UserSettingsResponse(BaseSchema):
    """Schema for user settings responses."""

    id: str
    user_id: str

    # Job Defaults
    default_priority: str
    max_retries: int
    job_timeout: int

    # API Configuration
    api_url: str
    api_timeout: int
    refresh_interval: int
    retry_attempts: int
    enable_caching: bool

    # Display Options
    dark_mode: bool
    show_job_ids: bool
    compact_mode: bool
    jobs_per_page: int
    timezone: str

    # Notification Settings
    completion_alerts: bool
    error_notifications: bool
    browser_notifications: bool

    # Additional settings
    custom_settings: dict[str, Any] | None = None


@api_error_handler("convert database priority to string")
def _convert_db_priority_to_string_safe(v: int) -> str:
    """Safely convert database integer priority to string."""
    from ..common.status import db_to_priority

    return db_to_priority(v).value


class UserSettingsUpdate(BaseModel):
    """Schema for updating user settings."""

    # Job Defaults
    default_priority: str | None = None
    max_retries: int | None = Field(None, ge=0, le=10)
    job_timeout: int | None = Field(None, ge=10, le=3600)

    # API Configuration
    api_url: str | None = None
    api_timeout: int | None = Field(None, ge=5, le=300)
    refresh_interval: int | None = Field(None, ge=5, le=300)
    retry_attempts: int | None = Field(None, ge=0, le=10)
    enable_caching: bool | None = None

    # Display Options
    dark_mode: bool | None = None
    show_job_ids: bool | None = None
    compact_mode: bool | None = None
    jobs_per_page: int | None = Field(None, ge=5, le=100)
    timezone: str | None = None

    # Notification Settings
    completion_alerts: bool | None = None
    error_notifications: bool | None = None
    browser_notifications: bool | None = None

    # Additional settings
    custom_settings: dict[str, Any] | None = None
