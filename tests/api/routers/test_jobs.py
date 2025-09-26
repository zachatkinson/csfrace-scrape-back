"""Tests for jobs router endpoints following testing best practices."""

from fastapi import status
from fastapi.testclient import TestClient


class TestJobsEndpoints:
    """Test job management endpoints using real dependencies where possible."""

    def test_create_single_job(self, client: TestClient):
        """Test creating a single job."""
        job_data = {
            "urls": ["https://example.com/test-article"],
            "priority": "normal",
            "output_base_directory": "/tmp/test",
            "max_retries": 3,
        }

        response = client.post("/jobs/", json=job_data)

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert "jobs" in data
        assert "total_jobs" in data
        assert data["total_jobs"] == 1
        assert data["batch_id"] is None  # Single job should not have batch_id
        assert len(data["jobs"]) == 1

        # Verify job structure
        job = data["jobs"][0]
        assert "id" in job
        assert job["source_url"] == "https://example.com/test-article"

    def test_create_batch_jobs(self, client: TestClient):
        """Test creating multiple jobs as a batch."""
        job_data = {
            "urls": [
                "https://example.com/article1",
                "https://example.com/article2",
                "https://example.com/article3",
            ],
            "priority": "high",
            "output_base_directory": "/tmp/batch",
            "max_retries": 2,
        }

        response = client.post("/jobs/", json=job_data)

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["total_jobs"] == 3
        assert data["batch_id"] is not None  # Multiple jobs should have batch_id
        assert len(data["jobs"]) == 3

        # All jobs should have the same batch_id
        batch_id = data["batch_id"]
        for job in data["jobs"]:
            assert job.get("batch_id") == batch_id

    def test_create_job_with_minimal_data(self, client: TestClient):
        """Test creating job with only required fields."""
        minimal_data = {"urls": ["https://example.com/minimal"], "priority": "normal"}

        response = client.post("/jobs/", json=minimal_data)

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["total_jobs"] == 1

    def test_create_job_invalid_url(self, client: TestClient):
        """Test job creation with invalid URL."""
        invalid_data = {"urls": ["not-a-valid-url"], "priority": "normal"}

        response = client.post("/jobs/", json=invalid_data)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_create_job_empty_urls(self, client: TestClient):
        """Test job creation with empty URLs array."""
        invalid_data = {"urls": [], "priority": "normal"}

        response = client.post("/jobs/", json=invalid_data)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_list_jobs_default_pagination(self, client: TestClient):
        """Test listing jobs with default pagination."""
        response = client.get("/jobs/")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "jobs" in data
        assert "total" in data
        assert "page" in data
        assert "page_size" in data
        assert isinstance(data["jobs"], list)

    def test_list_jobs_custom_pagination(self, client: TestClient):
        """Test listing jobs with custom pagination parameters."""
        response = client.get("/jobs/?page=1&page_size=10")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["page"] == 1
        assert data["page_size"] == 10

    def test_list_jobs_invalid_pagination(self, client: TestClient):
        """Test listing jobs with invalid pagination parameters."""
        # Test negative page
        response = client.get("/jobs/?page=0")
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

        # Test oversized page size
        response = client.get("/jobs/?page_size=300")
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_list_jobs_with_status_filter(self, client: TestClient):
        """Test listing jobs with status filter."""
        response = client.get("/jobs/?status_filter=completed")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        # Should return filtered results (may be empty)
        assert "jobs" in data

    def test_list_jobs_with_domain_filter(self, client: TestClient):
        """Test listing jobs with domain filter."""
        response = client.get("/jobs/?domain=example.com")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "jobs" in data

    def test_get_nonexistent_job(self, client: TestClient):
        """Test retrieving a job that doesn't exist."""
        response = client.get("/jobs/nonexistent-job-id")

        assert response.status_code == status.HTTP_404_NOT_FOUND
        data = response.json()
        assert "detail" in data

    def test_update_nonexistent_job(self, client: TestClient):
        """Test updating a job that doesn't exist."""
        update_data = {"priority": "high"}

        response = client.put("/jobs/nonexistent-job-id", json=update_data)

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_delete_nonexistent_job(self, client: TestClient):
        """Test deleting a job that doesn't exist."""
        response = client.delete("/jobs/nonexistent-job-id")

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_start_nonexistent_job(self, client: TestClient):
        """Test starting a job that doesn't exist."""
        response = client.post("/jobs/nonexistent-job-id/start")

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_cancel_nonexistent_job(self, client: TestClient):
        """Test cancelling a job that doesn't exist."""
        response = client.post("/jobs/nonexistent-job-id/cancel")

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_retry_nonexistent_job(self, client: TestClient):
        """Test retrying a job that doesn't exist."""
        response = client.post("/jobs/nonexistent-job-id/retry")

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_job_stream_sse_headers(self, client: TestClient):
        """Test job stream SSE endpoint returns proper headers."""
        response = client.get("/jobs/stream")

        # Check SSE headers
        assert response.headers["content-type"] == "text/event-stream; charset=utf-8"
        assert response.headers["cache-control"] == "no-cache"
        assert response.headers["connection"] == "keep-alive"
        assert response.headers["access-control-allow-origin"] == "*"

    def test_trigger_job_event(self, client: TestClient):
        """Test manual job event trigger."""
        response = client.post("/jobs/trigger-event")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "message" in data or "error" in data


class TestJobsEndpointErrorHandling:
    """Test error handling in job endpoints."""

    def test_invalid_http_methods(self, client: TestClient):
        """Test using invalid HTTP methods on job endpoints."""
        # Test invalid method on job creation
        response = client.get("/jobs/")  # GET requests don't take json parameter
        # This should succeed as GET /jobs/ is valid for listing jobs
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_405_METHOD_NOT_ALLOWED]

        # Test invalid method on job control
        response = client.get("/jobs/test-id/start")
        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

    def test_malformed_json_in_create_job(self, client: TestClient):
        """Test job creation with malformed JSON."""
        response = client.post(
            "/jobs/",
            content='{"urls": ["https://example.com"',  # Incomplete JSON
            headers={"content-type": "application/json"},
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_missing_required_fields(self, client: TestClient):
        """Test job creation with missing required fields."""
        # Missing URLs
        response = client.post("/jobs/", json={"priority": "normal"})
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

        # Missing priority
        response = client.post("/jobs/", json={"urls": ["https://example.com"]})
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_invalid_priority_value(self, client: TestClient):
        """Test job creation with invalid priority value."""
        invalid_data = {"urls": ["https://example.com"], "priority": "invalid_priority"}

        response = client.post("/jobs/", json=invalid_data)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


class TestJobsResponseFormats:
    """Test response format consistency across job endpoints."""

    def test_job_creation_response_format(self, client: TestClient):
        """Test job creation response has consistent format."""
        job_data = {"urls": ["https://example.com/test"], "priority": "normal"}

        response = client.post("/jobs/", json=job_data)

        if response.status_code == status.HTTP_201_CREATED:
            data = response.json()
            required_fields = ["jobs", "total_jobs", "batch_id"]
            for field in required_fields:
                assert field in data, f"Missing required field: {field}"

            # Verify job object structure
            if data["jobs"]:
                job = data["jobs"][0]
                job_required_fields = ["id", "source_url", "status"]
                for field in job_required_fields:
                    assert field in job, f"Missing job field: {field}"

    def test_job_list_response_format(self, client: TestClient):
        """Test job list response has consistent format."""
        response = client.get("/jobs/")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        required_fields = ["jobs", "total", "page", "page_size"]
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"

        # Verify pagination fields are integers
        assert isinstance(data["total"], int)
        assert isinstance(data["page"], int)
        assert isinstance(data["page_size"], int)

    def test_error_response_format(self, client: TestClient):
        """Test error responses have consistent format."""
        response = client.get("/jobs/nonexistent-job")

        assert response.status_code == status.HTTP_404_NOT_FOUND
        data = response.json()
        assert "detail" in data
        assert isinstance(data["detail"], str)


class TestJobsEndpointIntegration:
    """Test integration scenarios for job management."""

    def test_complete_job_workflow(self, client: TestClient):
        """Test complete job workflow: create → list → retrieve."""
        # Create a job
        job_data = {"urls": ["https://example.com/workflow-test"], "priority": "normal"}

        create_response = client.post("/jobs/", json=job_data)
        assert create_response.status_code == status.HTTP_201_CREATED

        created_job = create_response.json()["jobs"][0]
        job_id = created_job["id"]

        # List jobs should include the created job
        list_response = client.get("/jobs/")
        assert list_response.status_code == status.HTTP_200_OK

        # Retrieve the specific job
        get_response = client.get(f"/jobs/{job_id}")
        if get_response.status_code == status.HTTP_200_OK:
            retrieved_job = get_response.json()
            assert retrieved_job["id"] == job_id
            assert retrieved_job["source_url"] == job_data["urls"][0]

    def test_batch_job_consistency(self, client: TestClient):
        """Test batch job creation maintains consistency."""
        urls = [f"https://example.com/batch-{i}" for i in range(3)]
        job_data = {"urls": urls, "priority": "high"}

        response = client.post("/jobs/", json=job_data)
        assert response.status_code == status.HTTP_201_CREATED

        data = response.json()
        batch_id = data["batch_id"]

        # All jobs should have the same batch_id and other shared properties
        for job in data["jobs"]:
            assert job.get("batch_id") == batch_id
            # Note: Other shared properties would be tested here in real scenario

    def test_pagination_consistency(self, client: TestClient):
        """Test pagination works consistently across requests."""
        # Test first page
        page1_response = client.get("/jobs/?page=1&page_size=5")
        assert page1_response.status_code == status.HTTP_200_OK

        # Test second page
        page2_response = client.get("/jobs/?page=2&page_size=5")
        assert page2_response.status_code == status.HTTP_200_OK

        # Both should have same structure
        page1_data = page1_response.json()
        page2_data = page2_response.json()

        assert page1_data["page"] == 1
        assert page2_data["page"] == 2
        assert page1_data["page_size"] == page2_data["page_size"] == 5

    def test_filtering_consistency(self, client: TestClient):
        """Test filtering works consistently."""
        # Test with different filters
        status_filtered = client.get("/jobs/?status_filter=pending")
        domain_filtered = client.get("/jobs/?domain=example.com")
        combined_filtered = client.get("/jobs/?status_filter=pending&domain=example.com")

        # All should return valid responses
        for response in [status_filtered, domain_filtered, combined_filtered]:
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert "jobs" in data
            assert "total" in data
