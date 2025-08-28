"""Tests for batch API endpoints."""

from fastapi import status
from fastapi.testclient import TestClient

from src.database.models import Batch


class TestBatchEndpoints:
    """Test batch API endpoints."""

    def test_create_batch_success(self, client: TestClient, batch_create_data: dict):
        """Test successful batch creation."""
        response = client.post("/batches/", json=batch_create_data)

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

    def test_create_batch_with_jobs(self, client: TestClient, batch_create_data: dict):
        """Test that batch creation also creates associated jobs."""
        response = client.post("/batches/", json=batch_create_data)

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        batch_id = data["id"]

        # Get the batch to verify jobs were created
        batch_response = client.get(f"/batches/{batch_id}")
        batch_data = batch_response.json()

        assert len(batch_data["jobs"]) == len(batch_create_data["urls"])

        # Verify each job has correct properties
        for job in batch_data["jobs"]:
            assert job["batch_id"] == batch_id
            assert job["status"] == "pending"
            assert job["url"] in batch_create_data["urls"]

    def test_create_batch_empty_urls(self, client: TestClient):
        """Test batch creation with empty URL list."""
        batch_data = {
            "name": "Empty Batch",
            "description": "A batch with no URLs",
            "urls": [],
            "max_concurrent": 5,
        }

        response = client.post("/batches/", json=batch_data)

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["total_jobs"] == 0

    def test_create_batch_invalid_data(self, client: TestClient):
        """Test batch creation with invalid data."""
        invalid_data = {
            "name": "",  # Empty name should be invalid
            "urls": ["not-a-valid-url"],
        }

        response = client.post("/batches/", json=invalid_data)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_get_batch_success(self, client: TestClient, sample_batch: Batch):
        """Test successful batch retrieval."""
        response = client.get(f"/batches/{sample_batch.id}")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["id"] == sample_batch.id
        assert data["name"] == sample_batch.name
        assert data["description"] == sample_batch.description
        assert data["total_jobs"] == sample_batch.total_jobs
        assert data["status"] == sample_batch.status.value
        assert "jobs" in data

    def test_get_batch_not_found(self, client: TestClient):
        """Test batch retrieval with non-existent ID."""
        response = client.get("/batches/99999")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_list_batches_empty(self, client: TestClient):
        """Test listing batches when none exist."""
        response = client.get("/batches/")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["batches"] == []
        assert data["total"] == 0
        assert data["page"] == 1
        assert data["page_size"] == 50
        assert data["total_pages"] == 0

    def test_list_batches_with_data(self, client: TestClient, sample_batch: Batch):
        """Test listing batches with existing data."""
        response = client.get("/batches/")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert len(data["batches"]) == 1
        assert data["total"] == 1
        assert data["page"] == 1
        assert data["page_size"] == 50
        assert data["total_pages"] == 1
        assert data["batches"][0]["id"] == sample_batch.id

    def test_list_batches_pagination(self, client: TestClient):
        """Test batch listing pagination."""
        # Create multiple batches
        for i in range(5):
            batch_data = {
                "name": f"Test Batch {i}",
                "description": f"Test batch number {i}",
                "urls": [f"https://example.com/page{i}"],
                "max_concurrent": 5,
            }
            client.post("/batches/", json=batch_data)

        # Test first page with page_size=2
        response = client.get("/batches/?page=1&page_size=2")
        data = response.json()

        assert len(data["batches"]) == 2
        assert data["total"] == 5
        assert data["page"] == 1
        assert data["page_size"] == 2
        assert data["total_pages"] == 3

    def test_list_batches_pagination_bounds(self, client: TestClient):
        """Test batch listing pagination edge cases."""
        # Test with page_size exceeding maximum
        response = client.get("/batches/?page_size=500")
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

        # Test with invalid page number
        response = client.get("/batches/?page=0")
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

        # Test with negative page_size
        response = client.get("/batches/?page_size=-1")
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_batch_directory_generation(self, client: TestClient):
        """Test batch output directory generation."""
        batch_data = {
            "name": "Directory Test Batch",
            "description": "Testing directory generation",
            "urls": ["https://example.com/test"],
            "max_concurrent": 5,
            # No output_base_directory specified
        }

        response = client.post("/batches/", json=batch_data)

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()

        # Should generate directory based on batch name
        expected_dir = "batch_output/Directory Test Batch"
        assert data["output_base_directory"] == expected_dir

    def test_batch_with_custom_directory(self, client: TestClient):
        """Test batch creation with custom output directory."""
        batch_data = {
            "name": "Custom Dir Batch",
            "description": "Testing custom directory",
            "urls": ["https://example.com/test"],
            "max_concurrent": 5,
            "output_base_directory": "/custom/output/path",
        }

        response = client.post("/batches/", json=batch_data)

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()

        assert data["output_base_directory"] == "/custom/output/path"

    def test_batch_job_output_directories(self, client: TestClient):
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

        response = client.post("/batches/", json=batch_data)
        batch_id = response.json()["id"]

        # Get the batch with jobs
        batch_response = client.get(f"/batches/{batch_id}")
        batch_data_result = batch_response.json()

        # Check that jobs have proper output directories
        for i, job in enumerate(batch_data_result["jobs"], 1):
            expected_dir = f"batch_output/Job Dir Test/job_{i}"
            assert job["output_directory"] == expected_dir

    def test_batch_default_settings(self, client: TestClient):
        """Test batch creation with default settings."""
        minimal_data = {
            "name": "Minimal Batch",
            "urls": ["https://example.com/test"],
        }

        response = client.post("/batches/", json=minimal_data)

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()

        # Check default values
        assert data["max_concurrent"] == 5  # Default from schema
        assert data["continue_on_error"] is True  # Default from schema
        assert data["create_archives"] is False  # Default from schema
        assert data["cleanup_after_archive"] is False  # Default from schema

    def test_batch_endpoints_require_valid_ids(self, client: TestClient):
        """Test that batch endpoints validate ID parameters."""
        invalid_id = "not-an-integer"

        response = client.get(f"/batches/{invalid_id}")
        assert response.status_code in [
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            status.HTTP_404_NOT_FOUND,
        ]

    def test_batch_config_preservation(self, client: TestClient):
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

        response = client.post("/batches/", json=batch_data)

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()

        assert data["batch_config"] == batch_data["batch_config"]

    def test_large_batch_creation(self, client: TestClient):
        """Test creating batch with many URLs."""
        urls = [f"https://example.com/page{i}" for i in range(100)]

        batch_data = {
            "name": "Large Batch",
            "description": "Testing large batch creation",
            "urls": urls,
            "max_concurrent": 20,
        }

        response = client.post("/batches/", json=batch_data)

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()

        assert data["total_jobs"] == 100

        # Verify all jobs were created
        batch_response = client.get(f"/batches/{data['id']}")
        batch_with_jobs = batch_response.json()

        assert len(batch_with_jobs["jobs"]) == 100
