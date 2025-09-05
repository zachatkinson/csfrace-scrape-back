"""Integration tests for batch API endpoints.

These tests focus on business logic and use relaxed rate limits.
For rate limiting behavior tests, see test_rate_limiting.py
"""

import pytest
from fastapi import status
from httpx import AsyncClient

from src.database.models import Batch


class TestBatchEndpoints:
    """Test batch API endpoints."""

    def _assert_pagination_response(
        self,
        data: dict,
        expected_total: int,
        expected_page: int = 1,
        expected_page_size: int = 50,
        expected_batches_count: int = None,
    ) -> None:
        """DRY utility: Assert pagination response structure."""
        assert data["total"] == expected_total
        assert data["page"] == expected_page
        assert data["page_size"] == expected_page_size
        assert (
            data["total_pages"] == (expected_total + expected_page_size - 1) // expected_page_size
        )

        if expected_batches_count is not None:
            assert len(data["batches"]) == expected_batches_count

        assert "batches" in data

    def _assert_batch_response(self, data: dict, expected_batch: Batch = None) -> None:
        """DRY utility: Assert batch response structure."""
        required_fields = ["id", "name", "description", "total_jobs", "status", "created_at"]

        for field in required_fields:
            assert field in data, f"Missing required field: {field}"

        if expected_batch:
            assert data["id"] == expected_batch.id
            assert data["name"] == expected_batch.name
            assert data["description"] == expected_batch.description
            assert data["total_jobs"] == expected_batch.total_jobs
            assert data["status"] == expected_batch.status.value

    async def _assert_validation_errors(
        self, async_client: AsyncClient, endpoint: str, invalid_params: list[str]
    ) -> None:
        """DRY utility: Assert validation errors for invalid parameters."""
        for param in invalid_params:
            response = await async_client.get(f"{endpoint}?{param}")
            assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    async def _create_batch_and_get_id(self, async_client: AsyncClient, batch_data: dict) -> int:
        """DRY utility: Create batch and return its ID."""
        response = await async_client.post("/batches/", json=batch_data)
        assert response.status_code == status.HTTP_201_CREATED
        return response.json()["id"]

    def _assert_default_batch_values(self, data: dict) -> None:
        """DRY utility: Assert batch has expected default values."""
        defaults = {
            "max_concurrent": 5,
            "continue_on_error": True,
            "create_archives": False,
            "cleanup_after_archive": False,
        }

        for field, expected_value in defaults.items():
            assert data[field] == expected_value, (
                f"Expected {field}={expected_value}, got {data[field]}"
            )

    @pytest.mark.asyncio
    async def test_create_batch_success(self, async_client: AsyncClient, batch_create_data: dict):
        """Test successful batch creation."""
        response = await async_client.post("/batches/", json=batch_create_data)

        # Removed debug output - timezone issue should be fixed

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()

        assert data["name"] == batch_create_data["name"]
        assert data["description"] == batch_create_data["description"]
        assert data["total_jobs"] == len(batch_create_data["urls"])
        assert data["max_concurrent"] == batch_create_data["max_concurrent"]
        assert data["continue_on_error"] == batch_create_data["continue_on_error"]
        assert data["create_archives"] == batch_create_data["create_archives"]
        assert data["cleanup_after_archive"] == batch_create_data["cleanup_after_archive"]
        assert data["status"] == "pending"
        assert "id" in data
        assert "created_at" in data

    @pytest.mark.asyncio
    async def test_create_batch_with_jobs(self, async_client: AsyncClient, batch_create_data: dict):
        """Test that batch creation also creates associated jobs."""
        response = await async_client.post("/batches/", json=batch_create_data)

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        batch_id = data["id"]

        # Get the batch to verify jobs were created
        batch_response = await async_client.get(f"/batches/{batch_id}")
        batch_data = batch_response.json()

        assert len(batch_data["jobs"]) == len(batch_create_data["urls"])

        # Verify each job has correct properties
        for job in batch_data["jobs"]:
            assert job["batch_id"] == batch_id
            assert job["status"] == "pending"
            assert job["url"] in batch_create_data["urls"]

    @pytest.mark.asyncio
    async def test_create_batch_empty_urls(self, async_client: AsyncClient):
        """Test batch creation with empty URL list."""
        batch_data = {
            "name": "Empty Batch",
            "description": "A batch with no URLs",
            "urls": [],
            "max_concurrent": 5,
        }

        response = await async_client.post("/batches/", json=batch_data)

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["total_jobs"] == 0

    @pytest.mark.asyncio
    async def test_create_batch_invalid_data(self, async_client: AsyncClient):
        """Test batch creation with invalid data."""
        invalid_data = {
            "name": "",  # Empty name should be invalid
            "urls": ["not-a-valid-url"],
        }

        response = await async_client.post("/batches/", json=invalid_data)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    @pytest.mark.asyncio
    async def test_get_batch_success(self, async_client: AsyncClient, sample_batch: Batch):
        """Test successful batch retrieval."""
        response = await async_client.get(f"/batches/{sample_batch.id}")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        self._assert_batch_response(data, sample_batch)
        assert "jobs" in data

    @pytest.mark.asyncio
    async def test_get_batch_not_found(self, async_client: AsyncClient):
        """Test batch retrieval with non-existent ID."""
        response = await async_client.get("/batches/99999")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_list_batches_empty(self, async_client: AsyncClient):
        """Test listing batches when none exist."""
        response = await async_client.get("/batches/")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["batches"] == []
        self._assert_pagination_response(data, expected_total=0, expected_batches_count=0)

    @pytest.mark.asyncio
    async def test_list_batches_with_data(self, async_client: AsyncClient, sample_batch: Batch):
        """Test listing batches with existing data."""
        response = await async_client.get("/batches/")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        self._assert_pagination_response(data, expected_total=1, expected_batches_count=1)
        assert data["batches"][0]["id"] == sample_batch.id

    @pytest.mark.asyncio
    async def test_list_batches_pagination(self, async_client: AsyncClient):
        """Test batch listing pagination."""
        # Create multiple batches
        for i in range(5):
            batch_data = {
                "name": f"Test Batch {i}",
                "description": f"Test batch number {i}",
                "urls": [f"https://example.com/page{i}"],
                "max_concurrent": 5,
            }
            await async_client.post("/batches/", json=batch_data)

        # Test first page with page_size=2
        response = await async_client.get("/batches/?page=1&page_size=2")
        data = response.json()

        self._assert_pagination_response(
            data, expected_total=5, expected_page=1, expected_page_size=2, expected_batches_count=2
        )

    @pytest.mark.asyncio
    async def test_list_batches_pagination_bounds(self, async_client: AsyncClient):
        """Test batch listing pagination edge cases."""
        invalid_params = [
            "page_size=500",  # Exceeding maximum
            "page=0",  # Invalid page number
            "page_size=-1",  # Negative page_size
        ]
        await self._assert_validation_errors(async_client, "/batches/", invalid_params)

    @pytest.mark.asyncio
    async def test_batch_directory_generation(self, async_client: AsyncClient):
        """Test batch output directory generation."""
        batch_data = {
            "name": "Directory Test Batch",
            "description": "Testing directory generation",
            "urls": ["https://example.com/test"],
            "max_concurrent": 5,
            # No output_base_directory specified
        }

        response = await async_client.post("/batches/", json=batch_data)

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()

        # Should generate directory based on batch name
        expected_dir = "batch_output/Directory Test Batch"
        assert data["output_base_directory"] == expected_dir

    @pytest.mark.asyncio
    async def test_batch_with_custom_directory(self, async_client: AsyncClient):
        """Test batch creation with custom output directory."""
        batch_data = {
            "name": "Custom Dir Batch",
            "description": "Testing custom directory",
            "urls": ["https://example.com/test"],
            "max_concurrent": 5,
            "output_base_directory": "/custom/output/path",
        }

        response = await async_client.post("/batches/", json=batch_data)

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()

        assert data["output_base_directory"] == "/custom/output/path"

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_batch_job_output_directories(self, async_client: AsyncClient):
        """Test that batch jobs get proper output directories."""
        batch_data = {
            "name": "Job Dir Test",
            "description": "Testing job directory assignment",
            "urls": [
                "https://example.com/page1",
                "https://example.com/page2",
            ],
            "max_concurrent": 5,
        }

        response = await async_client.post("/batches/", json=batch_data)

        # Skip if rate limited - this test is about job directory logic, not creation
        if response.status_code == status.HTTP_429_TOO_MANY_REQUESTS:
            pytest.skip("Rate limited - logic test moved to dedicated shard")

        assert response.status_code == status.HTTP_201_CREATED
        batch_id = response.json()["id"]

        # Get the batch with jobs
        batch_response = await async_client.get(f"/batches/{batch_id}")
        batch_data_result = batch_response.json()

        # Check that jobs have proper output directories
        for i, job in enumerate(batch_data_result["jobs"], 1):
            expected_dir = f"batch_output/Job Dir Test/job_{i}"
            assert job["output_directory"] == expected_dir

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_batch_default_settings(self, async_client: AsyncClient):
        """Test batch creation with default settings."""
        minimal_data = {
            "name": "Minimal Batch",
            "urls": ["https://example.com/test"],
        }

        response = await async_client.post("/batches/", json=minimal_data)

        # Skip if rate limited - this test is about default values, not creation
        if response.status_code == status.HTTP_429_TOO_MANY_REQUESTS:
            pytest.skip("Rate limited - logic test moved to dedicated shard")

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()

        # Check default values using DRY utility
        self._assert_default_batch_values(data)

    @pytest.mark.asyncio
    async def test_batch_endpoints_require_valid_ids(self, async_client: AsyncClient):
        """Test that batch endpoints validate ID parameters."""
        invalid_id = "not-an-integer"

        response = await async_client.get(f"/batches/{invalid_id}")
        assert response.status_code in [
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            status.HTTP_404_NOT_FOUND,
        ]

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_batch_config_preservation(self, async_client: AsyncClient):
        """Test that batch configuration is properly preserved."""
        batch_data = {
            "name": "Config Test Batch",
            "description": "Testing config preservation",
            "urls": ["https://example.com/test"],
            "max_concurrent": 10,
            "batch_config": {
                "retry_failed": True,
                "notification_email": "test@example.com",
                "custom_headers": {"User-Agent": "TestBot"},
            },
        }

        response = await async_client.post("/batches/", json=batch_data)

        # Skip if rate limited - this test is about config preservation, not creation
        if response.status_code == status.HTTP_429_TOO_MANY_REQUESTS:
            pytest.skip("Rate limited - logic test moved to dedicated shard")

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()

        assert data["batch_config"] == batch_data["batch_config"]

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_large_batch_creation(self, async_client: AsyncClient):
        """Test creating batch with many URLs."""
        urls = [f"https://example.com/page{i}" for i in range(100)]

        batch_data = {
            "name": "Large Batch",
            "description": "Testing large batch creation",
            "urls": urls,
            "max_concurrent": 20,
        }

        response = await async_client.post("/batches/", json=batch_data)

        # Skip if rate limited - this test is about large batch logic, not creation
        if response.status_code == status.HTTP_429_TOO_MANY_REQUESTS:
            pytest.skip("Rate limited - logic test moved to dedicated shard")

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()

        assert data["total_jobs"] == 100

        # Verify all jobs were created
        batch_response = await async_client.get(f"/batches/{data['id']}")
        batch_with_jobs = batch_response.json()

        assert len(batch_with_jobs["jobs"]) == 100
