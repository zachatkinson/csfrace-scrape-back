"""Comprehensive tests for src/api/schemas.py module.

This test module provides comprehensive coverage for all Pydantic schemas
in the API schemas module to achieve 80%+ coverage as required.
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from src.api.schemas import (
    BaseSchema,
    ContentResultResponse,
    ErrorResponse,
    HealthCheckResponse,
    JobCreate,
    JobListResponse,
    JobResponse,
    JobsCreateRequest,
    JobsCreateResponse,
    JobUpdate,
    MetricsResponse,
)
from src.common.status import JobPriority


class TestBaseSchema:
    """Test BaseSchema configuration."""

    def test_base_schema_configuration(self):
        """Test BaseSchema has correct configuration."""
        schema = BaseSchema()

        # Verify model configuration
        assert hasattr(BaseSchema.model_config, "__getitem__")
        assert BaseSchema.model_config["from_attributes"] is True


class TestJobCreate:
    """Test JobCreate schema."""

    def test_job_create_minimal_valid(self):
        """Test JobCreate with minimal required fields."""
        data = {"url": "https://example.com/test"}

        job = JobCreate(**data)

        assert str(job.url) == "https://example.com/test"
        assert job.slug is None
        assert job.custom_slug is None
        assert job.priority == JobPriority.NORMAL
        assert job.output_directory is None
        assert job.max_retries == 3
        assert job.options is None
        assert job.processing_options is None

    def test_job_create_all_fields(self):
        """Test JobCreate with all fields provided."""
        data = {
            "url": "https://example.com/test-page",
            "slug": "test-slug",
            "custom_slug": "custom-test-slug",
            "priority": JobPriority.HIGH,
            "output_directory": "/custom/output",
            "max_retries": 5,
            "options": {"format": "html", "include_images": True},
            "processing_options": {"timeout": 30},
        }

        job = JobCreate(**data)

        assert str(job.url) == "https://example.com/test-page"
        assert job.slug == "test-slug"
        assert job.custom_slug == "custom-test-slug"
        assert job.priority == JobPriority.HIGH
        assert job.output_directory == "/custom/output"
        assert job.max_retries == 5
        assert job.options == {"format": "html", "include_images": True}
        assert job.processing_options == {"timeout": 30}

    def test_job_create_invalid_url(self):
        """Test JobCreate with invalid URL."""
        data = {"url": "not-a-valid-url"}

        with pytest.raises(ValidationError) as exc_info:
            JobCreate(**data)

        assert "url" in str(exc_info.value)

    def test_job_create_max_retries_validation(self):
        """Test JobCreate max_retries field validation."""
        # Test negative retries
        with pytest.raises(ValidationError):
            JobCreate(url="https://example.com", max_retries=-1)

        # Test retries exceeding limit (assuming API_MAX_RETRIES_LIMIT = 10)
        with pytest.raises(ValidationError):
            JobCreate(url="https://example.com", max_retries=999)

        # Test valid boundaries
        job1 = JobCreate(url="https://example.com", max_retries=0)
        assert job1.max_retries == 0

        job2 = JobCreate(url="https://example.com", max_retries=10)
        assert job2.max_retries == 10

    def test_job_create_priority_validation(self):
        """Test JobCreate priority field validation."""
        # Test valid priorities
        for priority in JobPriority:
            job = JobCreate(url="https://example.com", priority=priority)
            assert job.priority == priority

        # Test invalid priority
        with pytest.raises(ValidationError):
            JobCreate(url="https://example.com", priority="INVALID_PRIORITY")


class TestJobUpdate:
    """Test JobUpdate schema."""

    def test_job_update_empty(self):
        """Test JobUpdate with no fields (all optional)."""
        job_update = JobUpdate()

        assert job_update.priority is None
        assert job_update.max_retries is None
        assert job_update.options is None
        assert job_update.processing_options is None

    def test_job_update_partial_fields(self):
        """Test JobUpdate with some fields."""
        data = {"priority": JobPriority.LOW, "max_retries": 1}

        job_update = JobUpdate(**data)

        assert job_update.priority == JobPriority.LOW
        assert job_update.max_retries == 1
        assert job_update.options is None
        assert job_update.processing_options is None

    def test_job_update_all_fields(self):
        """Test JobUpdate with all fields."""
        data = {
            "priority": JobPriority.URGENT,
            "max_retries": 2,
            "options": {"new_option": "value"},
            "processing_options": {"timeout": 60},
        }

        job_update = JobUpdate(**data)

        assert job_update.priority == JobPriority.URGENT
        assert job_update.max_retries == 2
        assert job_update.options == {"new_option": "value"}
        assert job_update.processing_options == {"timeout": 60}

    def test_job_update_max_retries_validation(self):
        """Test JobUpdate max_retries validation."""
        # Test negative retries
        with pytest.raises(ValidationError):
            JobUpdate(max_retries=-1)

        # Test retries exceeding limit
        with pytest.raises(ValidationError):
            JobUpdate(max_retries=999)


class TestJobResponse:
    """Test JobResponse schema."""

    def test_job_response_creation(self):
        """Test JobResponse creation with all fields."""
        now = datetime.now(UTC)
        job_id = str(uuid4())

        data = {
            "id": job_id,
            "source_url": "https://example.com/test",
            "domain": "example.com",
            "slug": "test",
            "status": "pending",
            "priority": "normal",
            "created_at": now,
            "started_at": now,
            "completed_at": now,
            "retry_count": 0,
            "max_retries": 3,
            "output_directory": "/output",
            "error_message": None,
            "error_type": None,
            "duration_seconds": 10.5,
            "content_size_bytes": 1024,
            "batch_id": str(uuid4()),
            "options": {"format": "html"},
        }

        job_response = JobResponse(**data)

        assert job_response.id == job_id
        assert job_response.source_url == "https://example.com/test"
        assert job_response.url == "https://example.com/test"  # Alias field
        assert job_response.domain == "example.com"
        assert job_response.slug == "test"
        assert job_response.status == "pending"
        assert job_response.priority == "normal"
        assert job_response.created_at == now
        assert job_response.retry_count == 0
        assert job_response.options == {"format": "html"}

    def test_job_response_minimal_fields(self):
        """Test JobResponse with minimal required fields."""
        now = datetime.now(UTC)
        job_id = str(uuid4())

        data = {
            "id": job_id,
            "source_url": "https://example.com/test",
            "status": "pending",
            "priority": "normal",
            "created_at": now,
            "retry_count": 0,
            "max_retries": 3,
        }

        job_response = JobResponse(**data)

        assert job_response.id == job_id
        assert job_response.source_url == "https://example.com/test"
        assert job_response.url == "https://example.com/test"
        assert job_response.domain is None
        assert job_response.slug is None
        assert job_response.started_at is None
        assert job_response.completed_at is None

    def test_job_response_alias_field(self):
        """Test that url field is an alias for source_url."""
        data = {
            "id": str(uuid4()),
            "source_url": "https://example.com/test",
            "status": "pending",
            "priority": "normal",
            "created_at": datetime.now(UTC),
            "retry_count": 0,
            "max_retries": 3,
        }

        job_response = JobResponse(**data)

        # Both should have the same value
        assert job_response.source_url == job_response.url
        assert job_response.url == "https://example.com/test"


class TestJobListResponse:
    """Test JobListResponse schema."""

    def test_job_list_response_creation(self):
        """Test JobListResponse creation."""
        job_data = {
            "id": str(uuid4()),
            "source_url": "https://example.com/test",
            "status": "pending",
            "priority": "normal",
            "created_at": datetime.now(UTC),
            "retry_count": 0,
            "max_retries": 3,
        }

        job = JobResponse(**job_data)

        data = {"jobs": [job], "total": 1, "page": 1, "page_size": 20, "total_pages": 1}

        job_list = JobListResponse(**data)

        assert len(job_list.jobs) == 1
        assert job_list.total == 1
        assert job_list.page == 1
        assert job_list.page_size == 20
        assert job_list.total_pages == 1

    def test_job_list_response_empty(self):
        """Test JobListResponse with empty jobs list."""
        data = {"jobs": [], "total": 0, "page": 1, "page_size": 20, "total_pages": 0}

        job_list = JobListResponse(**data)

        assert len(job_list.jobs) == 0
        assert job_list.total == 0


class TestJobsCreateRequest:
    """Test JobsCreateRequest schema."""

    def test_jobs_create_request_single_url(self):
        """Test JobsCreateRequest with single URL."""
        data = {"urls": ["https://example.com/page1"]}

        request = JobsCreateRequest(**data)

        assert len(request.urls) == 1
        assert str(request.urls[0]) == "https://example.com/page1"
        assert request.priority == JobPriority.NORMAL
        assert request.output_base_directory is None
        assert request.max_retries == 3
        assert request.options is None

    def test_jobs_create_request_multiple_urls(self):
        """Test JobsCreateRequest with multiple URLs."""
        urls = [
            "https://example.com/page1",
            "https://example.com/page2",
            "https://example.com/page3",
        ]

        data = {
            "urls": urls,
            "priority": JobPriority.HIGH,
            "output_base_directory": "/batch/output",
            "max_retries": 5,
            "options": {"batch_mode": True},
        }

        request = JobsCreateRequest(**data)

        assert len(request.urls) == 3
        assert all(str(url) in [str(u) for u in request.urls] for url in urls)
        assert request.priority == JobPriority.HIGH
        assert request.output_base_directory == "/batch/output"
        assert request.max_retries == 5
        assert request.options == {"batch_mode": True}

    def test_jobs_create_request_validation_empty_urls(self):
        """Test JobsCreateRequest validation with empty URLs."""
        with pytest.raises(ValidationError) as exc_info:
            JobsCreateRequest(urls=[])

        assert "min_length" in str(exc_info.value) or "at least 1" in str(exc_info.value)

    def test_jobs_create_request_validation_too_many_urls(self):
        """Test JobsCreateRequest validation with too many URLs."""
        # Create more URLs than API_MAX_URLS_PER_BATCH (assuming it's 100)
        too_many_urls = [f"https://example.com/page{i}" for i in range(101)]

        with pytest.raises(ValidationError) as exc_info:
            JobsCreateRequest(urls=too_many_urls)

        assert "max_length" in str(exc_info.value) or "at most" in str(exc_info.value)

    def test_jobs_create_request_invalid_urls(self):
        """Test JobsCreateRequest with invalid URLs."""
        data = {"urls": ["not-a-url", "also-not-a-url"]}

        with pytest.raises(ValidationError):
            JobsCreateRequest(**data)


class TestJobsCreateResponse:
    """Test JobsCreateResponse schema."""

    def test_jobs_create_response_single_job(self):
        """Test JobsCreateResponse for single job creation."""
        job_data = {
            "id": str(uuid4()),
            "source_url": "https://example.com/test",
            "status": "pending",
            "priority": "normal",
            "created_at": datetime.now(UTC),
            "retry_count": 0,
            "max_retries": 3,
        }

        job = JobResponse(**job_data)

        data = {
            "jobs": [job],
            "batch_id": None,  # None for single job
            "total_jobs": 1,
        }

        response = JobsCreateResponse(**data)

        assert len(response.jobs) == 1
        assert response.batch_id is None
        assert response.total_jobs == 1

    def test_jobs_create_response_batch_jobs(self):
        """Test JobsCreateResponse for batch job creation."""
        jobs = []
        for i in range(3):
            job_data = {
                "id": str(uuid4()),
                "source_url": f"https://example.com/page{i}",
                "status": "pending",
                "priority": "normal",
                "created_at": datetime.now(UTC),
                "retry_count": 0,
                "max_retries": 3,
            }
            jobs.append(JobResponse(**job_data))

        batch_id = str(uuid4())
        data = {"jobs": jobs, "batch_id": batch_id, "total_jobs": 3}

        response = JobsCreateResponse(**data)

        assert len(response.jobs) == 3
        assert response.batch_id == batch_id
        assert response.total_jobs == 3


class TestContentResultResponse:
    """Test ContentResultResponse schema."""

    def test_content_result_response_creation(self):
        """Test ContentResultResponse creation."""
        now = datetime.now(UTC)
        job_id = str(uuid4())

        data = {
            "id": 1,
            "job_id": job_id,
            "title": "Test Article",
            "meta_description": "Test description",
            "published_date": now,
            "author": "Test Author",
            "tags": ["tag1", "tag2"],
            "categories": ["category1"],
            "word_count": 500,
            "image_count": 3,
            "link_count": 10,
            "processing_time_seconds": 2.5,
            "created_at": now,
            "updated_at": now,
        }

        result = ContentResultResponse(**data)

        assert result.id == 1
        assert result.job_id == job_id
        assert result.title == "Test Article"
        assert result.meta_description == "Test description"
        assert result.author == "Test Author"
        assert result.tags == ["tag1", "tag2"]
        assert result.categories == ["category1"]
        assert result.word_count == 500
        assert result.image_count == 3
        assert result.link_count == 10
        assert result.processing_time_seconds == 2.5

    def test_content_result_response_minimal(self):
        """Test ContentResultResponse with minimal required fields."""
        now = datetime.now(UTC)
        job_id = str(uuid4())

        data = {"id": 1, "job_id": job_id, "created_at": now, "updated_at": now}

        result = ContentResultResponse(**data)

        assert result.id == 1
        assert result.job_id == job_id
        assert result.title is None
        assert result.meta_description is None
        assert result.tags is None
        assert result.categories is None


class TestHealthCheckResponse:
    """Test HealthCheckResponse schema."""

    def test_health_check_response_creation(self):
        """Test HealthCheckResponse creation."""
        now = datetime.now(UTC)

        data = {
            "status": "healthy",
            "timestamp": now,
            "version": "1.0.0",
            "database": {"status": "connected", "latency_ms": 5},
            "cache": {"status": "connected", "hit_rate": 0.95},
            "monitoring": {"status": "active", "alerts": 0},
        }

        health = HealthCheckResponse(**data)

        assert health.status == "healthy"
        assert health.timestamp == now
        assert health.version == "1.0.0"
        assert health.database["status"] == "connected"
        assert health.cache["hit_rate"] == 0.95
        assert health.monitoring["alerts"] == 0


class TestMetricsResponse:
    """Test MetricsResponse schema."""

    def test_metrics_response_creation(self):
        """Test MetricsResponse creation."""
        now = datetime.now(UTC)

        data = {
            "timestamp": now,
            "system_metrics": {"cpu_usage": 45.2, "memory_usage": 67.8},
            "application_metrics": {"requests_per_second": 100, "error_rate": 0.01},
            "database_metrics": {"active_connections": 5, "query_latency_ms": 12},
        }

        metrics = MetricsResponse(**data)

        assert metrics.timestamp == now
        assert metrics.system_metrics["cpu_usage"] == 45.2
        assert metrics.application_metrics["requests_per_second"] == 100
        assert metrics.database_metrics["active_connections"] == 5


class TestErrorResponse:
    """Test ErrorResponse schema."""

    def test_error_response_creation(self):
        """Test ErrorResponse creation."""
        now = datetime.now(UTC)

        data = {
            "detail": "Resource not found",
            "error_code": "RESOURCE_NOT_FOUND",
            "timestamp": now,
        }

        error = ErrorResponse(**data)

        assert error.detail == "Resource not found"
        assert error.error_code == "RESOURCE_NOT_FOUND"
        assert error.timestamp == now

    def test_error_response_minimal(self):
        """Test ErrorResponse with minimal fields."""
        now = datetime.now(UTC)

        data = {"detail": "An error occurred", "timestamp": now}

        error = ErrorResponse(**data)

        assert error.detail == "An error occurred"
        assert error.error_code is None
        assert error.timestamp == now


class TestSchemaIntegration:
    """Integration tests for schema interactions."""

    def test_job_create_to_response_workflow(self):
        """Test workflow from JobCreate to JobResponse."""
        # Create a job request
        create_data = {
            "url": "https://example.com/test",
            "priority": JobPriority.HIGH,
            "max_retries": 5,
            "options": {"format": "html"},
        }

        job_create = JobCreate(**create_data)

        # Simulate job creation response
        now = datetime.now(UTC)
        response_data = {
            "id": str(uuid4()),
            "source_url": str(job_create.url),
            "status": "pending",
            "priority": job_create.priority.value,
            "created_at": now,
            "retry_count": 0,
            "max_retries": job_create.max_retries,
            "options": job_create.options,
        }

        job_response = JobResponse(**response_data)

        assert job_response.source_url == str(job_create.url)
        assert job_response.priority == job_create.priority.value
        assert job_response.max_retries == job_create.max_retries
        assert job_response.options == job_create.options

    def test_jobs_create_request_to_response_workflow(self):
        """Test workflow from JobsCreateRequest to JobsCreateResponse."""
        # Create batch request
        request_data = {
            "urls": ["https://example.com/page1", "https://example.com/page2"],
            "priority": JobPriority.NORMAL,
            "max_retries": 3,
        }

        batch_request = JobsCreateRequest(**request_data)

        # Simulate batch creation response
        now = datetime.now(UTC)
        jobs = []
        for i, url in enumerate(batch_request.urls):
            job_data = {
                "id": str(uuid4()),
                "source_url": str(url),
                "status": "pending",
                "priority": batch_request.priority.value,
                "created_at": now,
                "retry_count": 0,
                "max_retries": batch_request.max_retries,
            }
            jobs.append(JobResponse(**job_data))

        batch_response = JobsCreateResponse(jobs=jobs, batch_id=str(uuid4()), total_jobs=len(jobs))

        assert len(batch_response.jobs) == len(batch_request.urls)
        assert batch_response.total_jobs == len(batch_request.urls)
        assert batch_response.batch_id is not None

    def test_schema_from_attributes_configuration(self):
        """Test that schemas work with from_attributes configuration."""

        # Simulate database model object
        class MockJob:
            def __init__(self):
                self.id = str(uuid4())
                self.source_url = "https://example.com/test"
                self.status = "pending"
                self.priority = "normal"
                self.created_at = datetime.now(UTC)
                self.retry_count = 0
                self.max_retries = 3

        mock_job = MockJob()

        # Should be able to create response from object attributes
        job_response = JobResponse.model_validate(mock_job)

        assert job_response.id == mock_job.id
        assert job_response.source_url == mock_job.source_url
        assert job_response.status == mock_job.status
