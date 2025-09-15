"""Integration tests for the API."""

import pytest
from fastapi.testclient import TestClient
from httpx import AsyncClient


class TestAPIIntegration:
    """Integration tests for API endpoints."""

    def test_complete_job_workflow(self, client: TestClient):
        """Test complete job lifecycle workflow."""
        # 1. Create a job
        job_data = {
            "url": "https://example.com/integration-test",
            "priority": "high",
            "custom_slug": "integration-test",
            "max_retries": 3,
        }

        create_response = client.post("/jobs/", json=job_data)
        assert create_response.status_code == 201
        job = create_response.json()
        job_id = job["id"]

        # 2. Verify job was created
        get_response = client.get(f"/jobs/{job_id}")
        assert get_response.status_code == 200
        retrieved_job = get_response.json()
        assert retrieved_job["url"] == job_data["url"]
        assert retrieved_job["status"] == "pending"

        # 3. Start the job
        start_response = client.post(f"/jobs/{job_id}/start")
        assert start_response.status_code == 200
        started_job = start_response.json()
        assert started_job["status"] == "running"

        # 4. Try to start again (should fail)
        start_again_response = client.post(f"/jobs/{job_id}/start")
        assert start_again_response.status_code == 400

        # 5. Cancel the job
        cancel_response = client.post(f"/jobs/{job_id}/cancel")
        assert cancel_response.status_code == 200
        cancelled_job = cancel_response.json()
        assert cancelled_job["status"] == "cancelled"

        # 6. Update job details
        update_data = {"priority": "low", "max_retries": 5}
        update_response = client.put(f"/jobs/{job_id}", json=update_data)
        assert update_response.status_code == 200
        updated_job = update_response.json()
        assert updated_job["priority"] == "low"
        assert updated_job["max_retries"] == 5

        # 7. Delete the job
        delete_response = client.delete(f"/jobs/{job_id}")
        assert delete_response.status_code == 204

        # 8. Verify deletion
        final_get_response = client.get(f"/jobs/{job_id}")
        assert final_get_response.status_code == 404

    def test_multiple_jobs_workflow(self, client: TestClient):
        """Test creating multiple jobs with unified array endpoint."""
        # 1. Create multiple jobs using the unified array endpoint
        jobs_data = {
            "urls": [
                "https://example.com/page1",
                "https://example.com/page2",
                "https://example.com/page3",
            ],
            "priority": "normal",
        }

        create_response = client.post("/jobs/", json=jobs_data)
        assert create_response.status_code == 201
        response_data = create_response.json()

        # Verify all jobs were created and have the same batch_id
        assert len(response_data["jobs"]) == 3
        batch_id = response_data["jobs"][0]["batch_id"]
        assert batch_id is not None

        # All jobs should have the same batch_id since they were created together
        for job in response_data["jobs"]:
            assert job["batch_id"] == batch_id
            assert job["status"] == "pending"

        # 2. Test individual job operations within the batch
        job_id = response_data["jobs"][0]["id"]

        # Start one job from the batch
        start_response = client.post(f"/jobs/{job_id}/start")
        assert start_response.status_code == 200

        # 3. Verify job status was updated
        get_job_response = client.get(f"/jobs/{job_id}")
        assert get_job_response.status_code == 200
        started_job = get_job_response.json()
        assert started_job["status"] == "running"

    def test_job_filtering_and_pagination(self, client: TestClient):
        """Test job filtering and pagination together."""
        # Create jobs with different statuses and domains
        jobs_data = [
            {"url": "https://site1.com/page1", "priority": "high"},
            {"url": "https://site1.com/page2", "priority": "normal"},
            {"url": "https://site2.com/page1", "priority": "low"},
            {"url": "https://site2.com/page2", "priority": "high"},
            {"url": "https://site3.com/page1", "priority": "normal"},
        ]

        created_jobs = []
        for job_data in jobs_data:
            response = client.post("/jobs/", json=job_data)
            assert response.status_code == 201
            created_jobs.append(response.json())

        # Test domain filtering
        site1_response = client.get("/jobs/?domain=site1.com")
        assert site1_response.status_code == 200
        site1_jobs = site1_response.json()
        assert site1_jobs["total"] == 2
        assert all(job["domain"] == "site1.com" for job in site1_jobs["jobs"])

        # Test status filtering (all should be pending)
        pending_response = client.get("/jobs/?status_filter=pending")
        assert pending_response.status_code == 200
        pending_jobs = pending_response.json()
        assert pending_jobs["total"] == 5

        # Test pagination
        page1_response = client.get("/jobs/?page=1&page_size=2")
        assert page1_response.status_code == 200
        page1_data = page1_response.json()
        assert len(page1_data["jobs"]) == 2
        assert page1_data["page"] == 1
        assert page1_data["total_pages"] == 3

        page2_response = client.get("/jobs/?page=2&page_size=2")
        assert page2_response.status_code == 200
        page2_data = page2_response.json()
        assert len(page2_data["jobs"]) == 2
        assert page2_data["page"] == 2

        # Verify no overlap between pages
        page1_ids = {job["id"] for job in page1_data["jobs"]}
        page2_ids = {job["id"] for job in page2_data["jobs"]}
        assert len(page1_ids.intersection(page2_ids)) == 0

    def test_api_error_handling_consistency(self, client: TestClient):
        """Test that API error handling is consistent across endpoints."""
        # Test 404 errors
        endpoints_404 = [
            ("GET", "/jobs/nonexistent-job-id"),
            ("PUT", "/jobs/nonexistent-job-id"),
            ("DELETE", "/jobs/nonexistent-job-id"),
            ("POST", "/jobs/nonexistent-job-id/start"),
            ("POST", "/jobs/nonexistent-job-id/cancel"),
            ("POST", "/jobs/nonexistent-job-id/retry"),
        ]

        for method, endpoint in endpoints_404:
            if method == "GET":
                response = client.get(endpoint)
            elif method == "PUT":
                response = client.put(endpoint, json={"priority": "high"})
            elif method == "DELETE":
                response = client.delete(endpoint)
            elif method == "POST":
                response = client.post(endpoint)

            assert response.status_code == 404
            data = response.json()
            assert "detail" in data
            assert "not found" in data["detail"].lower()

    def test_api_data_consistency(self, client: TestClient):
        """Test data consistency across different API operations."""
        # Create a job
        job_data = {
            "url": "https://consistency.test/page",
            "priority": "normal",
            "custom_slug": "consistency-test",
            "max_retries": 2,
            # "timeout_seconds": 45,  # Not a model field
            "options": {"test": "value"},  # Use 'options' not 'converter_config'
        }

        create_response = client.post("/jobs/", json=job_data)
        job = create_response.json()
        job_id = job["id"]

        # Verify data consistency across different endpoints

        # 1. GET single job
        single_job_response = client.get(f"/jobs/{job_id}")
        single_job = single_job_response.json()

        # 2. GET from job list
        list_response = client.get("/jobs/?domain=consistency.test")
        list_job = list_response.json()["jobs"][0]

        # 3. Compare key fields
        comparison_fields = [
            "id",
            "url",
            "domain",
            "slug",
            "priority",
            "status",
            "max_retries",
            # "timeout_seconds",  # Not a model field
            "options",  # Use 'options' not 'converter_config'
        ]

        for field in comparison_fields:
            assert single_job[field] == list_job[field] == job[field]

    @pytest.mark.asyncio
    async def test_concurrent_api_operations(self, async_client: AsyncClient):
        """Test API operations with multiple requests (sequential due to test setup)."""

        # Create multiple jobs sequentially (AsyncClient shares session in tests)
        responses = []
        for i in range(3):
            job_data = {
                "url": f"https://concurrent.test/page{i}",
                "priority": "normal",
            }
            response = await async_client.post("/jobs/", json=job_data)
            responses.append(response)

        # All should succeed
        assert all(response.status_code == 201 for response in responses)

        # All should have unique IDs
        job_ids = [response.json()["id"] for response in responses]
        assert len(set(job_ids)) == 3  # All unique

        # Verify they all exist
        list_response = await async_client.get("/jobs/?domain=concurrent.test")
        list_data = list_response.json()
        assert list_data["total"] == 3

    def test_api_validation_consistency(self, client: TestClient):
        """Test that API validation is consistent across endpoints."""
        # Test invalid URL validation
        invalid_url_data = {"url": "not-a-url", "priority": "normal"}

        job_response = client.post("/jobs/", json=invalid_url_data)
        assert job_response.status_code == 422

        # Test multiple jobs with invalid URL
        jobs_response = client.post("/jobs/", json={"urls": ["not-a-url"], "priority": "normal"})
        assert jobs_response.status_code == 422

        # Test missing required fields
        incomplete_job = {"priority": "high"}  # Missing URL
        response = client.post("/jobs/", json=incomplete_job)
        assert response.status_code == 422

        incomplete_jobs = {"priority": "high"}  # Missing urls array
        response = client.post("/jobs/", json=incomplete_jobs)
        assert response.status_code == 422

    def test_api_response_format_consistency(self, client: TestClient):
        """Test that API responses follow consistent format."""
        # Create test data
        job_response = client.post(
            "/jobs/", json={"url": "https://format.test/page", "priority": "normal"}
        )
        job = job_response.json()

        jobs_response = client.post(
            "/jobs/",
            json={
                "urls": ["https://format.test/batch1", "https://format.test/batch2"],
                "priority": "normal",
            },
        )
        jobs_data = jobs_response.json()
        job_from_batch = jobs_data["jobs"][0]  # Get first job from the batch

        # Check common fields have consistent naming and types
        common_fields = ["id", "created_at"]

        for field in common_fields:
            assert field in job
            assert field in job_from_batch

            # IDs should be consistent type
            if field == "id":
                # IDs can be strings or integers depending on implementation
                assert job[field] is not None
                assert job_from_batch[field] is not None

            # Timestamps should be strings in ISO format
            if "at" in field:
                assert isinstance(job[field], str)
                assert isinstance(job_from_batch[field], str)
                assert "T" in job[field]  # ISO format
                assert "T" in job_from_batch[field]  # ISO format
