"""Tests for health router endpoints following testing best practices."""

from fastapi import status
from fastapi.testclient import TestClient


class TestHealthEndpoints:
    """Test health monitoring endpoints using real dependencies where possible."""

    def test_liveness_check(self, client: TestClient):
        """Test liveness check endpoint."""
        response = client.get("/health/live")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "alive"

    def test_readiness_check(self, client: TestClient):
        """Test readiness check endpoint."""
        response = client.get("/health/ready")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "ready"

    def test_health_check_endpoint(self, client: TestClient):
        """Test comprehensive health check endpoint."""
        response = client.get("/health/")

        # Should return either 200 (healthy/degraded) or 503 (unhealthy)
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_503_SERVICE_UNAVAILABLE]

        data = response.json()

        if response.status_code == status.HTTP_200_OK:
            # Successful response should have health data directly
            assert "status" in data
            assert "timestamp" in data
            assert "version" in data
        else:
            # Error response has nested structure in 'detail'
            assert "detail" in data
            detail = data["detail"]
            if isinstance(detail, dict) and "details" in detail:
                # For service unavailable, health data is in details
                health_data = detail["details"]
                assert "status" in health_data
                assert "timestamp" in health_data
                assert "version" in health_data

    def test_metrics_endpoint(self, client: TestClient):
        """Test metrics collection endpoint."""
        response = client.get("/health/metrics")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "timestamp" in data
        assert "system_metrics" in data
        assert "application_metrics" in data
        assert "database_metrics" in data

    def test_prometheus_metrics_endpoint(self, client: TestClient):
        """Test Prometheus metrics export endpoint."""
        response = client.get("/health/prometheus")

        assert response.status_code == status.HTTP_200_OK
        assert response.headers["content-type"] == "text/plain; charset=utf-8"
        # Response should be valid Prometheus format (could be empty)
        assert isinstance(response.text, str)

    def test_health_stream_test_endpoint(self, client: TestClient):
        """Test SSE test endpoint."""
        response = client.get("/health/stream-test")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["message"] == "SSE endpoint test"
        assert data["status"] == "ok"

    def test_health_stream_sse_headers(self, client: TestClient):
        """Test SSE endpoint returns proper headers."""
        response = client.get("/health/stream")

        # Check SSE headers are properly set
        assert response.headers["content-type"] == "text/event-stream; charset=utf-8"
        assert response.headers["cache-control"] == "no-cache"
        assert response.headers["connection"] == "keep-alive"
        assert response.headers["access-control-allow-origin"] == "*"

    def test_trigger_health_check_endpoint(self, client: TestClient):
        """Test manual health check trigger."""
        response = client.post("/health/trigger-check")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "message" in data
        assert "health" in data or "error" in data


class TestHealthEndpointErrorCases:
    """Test error handling in health endpoints."""

    def test_nonexistent_endpoint(self, client: TestClient):
        """Test accessing non-existent health endpoint."""
        response = client.get("/health/nonexistent")

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_invalid_method_on_health_check(self, client: TestClient):
        """Test using invalid HTTP method on health endpoints."""
        response = client.delete("/health/")

        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

    def test_invalid_method_on_metrics(self, client: TestClient):
        """Test using invalid HTTP method on metrics endpoint."""
        response = client.post("/health/metrics")

        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED


class TestHealthResponseFormats:
    """Test response format consistency across health endpoints."""

    def test_health_check_response_structure(self, client: TestClient):
        """Test health check response has consistent structure."""
        response = client.get("/health/")

        if response.status_code == status.HTTP_200_OK:
            data = response.json()
            # All successful health responses should have these fields
            required_fields = ["status", "timestamp", "version"]
            for field in required_fields:
                assert field in data, f"Missing required field: {field}"
        else:
            # Error responses should have detail field
            data = response.json()
            assert "detail" in data

    def test_metrics_response_structure(self, client: TestClient):
        """Test metrics response has consistent structure."""
        response = client.get("/health/metrics")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Metrics should have consistent structure
        required_sections = ["system_metrics", "application_metrics", "database_metrics"]
        for section in required_sections:
            assert section in data, f"Missing metrics section: {section}"
            assert isinstance(data[section], dict), f"Section {section} should be a dict"

    def test_status_response_format(self, client: TestClient):
        """Test status endpoints return proper StatusResponse format."""
        endpoints = ["/health/live", "/health/ready"]

        for endpoint in endpoints:
            response = client.get(endpoint)

            if response.status_code == status.HTTP_200_OK:
                data = response.json()
                assert "status" in data
                assert isinstance(data["status"], str)


class TestHealthEndpointPerformance:
    """Test performance characteristics of health endpoints."""

    def test_liveness_check_is_fast(self, client: TestClient):
        """Test liveness check responds quickly (no heavy operations)."""
        import time

        start_time = time.time()
        response = client.get("/health/live")
        execution_time = time.time() - start_time

        assert response.status_code == status.HTTP_200_OK
        # Liveness should be very fast (under 100ms in normal conditions)
        assert execution_time < 1.0, (
            f"Liveness check took {execution_time:.3f}s, should be much faster"
        )

    def test_health_endpoints_concurrent_access(self, client: TestClient):
        """Test health endpoints handle concurrent requests."""
        import concurrent.futures

        def make_request(endpoint):
            return client.get(endpoint)

        endpoints = ["/health/live", "/health/ready", "/health/metrics"]

        # Make concurrent requests
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(make_request, endpoint) for endpoint in endpoints]
            results = [future.result() for future in concurrent.futures.as_completed(futures)]

        # All requests should succeed
        for result in results:
            assert result.status_code in [status.HTTP_200_OK, status.HTTP_503_SERVICE_UNAVAILABLE]


class TestHealthEndpointIntegration:
    """Test integration between different health monitoring components."""

    def test_health_check_integrates_with_metrics(self, client: TestClient):
        """Test health check and metrics provide consistent view."""
        health_response = client.get("/health/")
        metrics_response = client.get("/health/metrics")

        # Both should succeed or fail together in most cases
        if health_response.status_code == status.HTTP_200_OK:
            assert metrics_response.status_code == status.HTTP_200_OK

        # If health is available, metrics should contain relevant data
        if health_response.status_code == status.HTTP_200_OK:
            health_data = health_response.json()
            metrics_data = metrics_response.json()

            # Timestamps should be reasonably close (within a few seconds)
            health_ts = health_data.get("timestamp")
            metrics_ts = metrics_data.get("timestamp")

            if health_ts and metrics_ts:
                # Basic timestamp format validation
                assert isinstance(health_ts, str)
                assert isinstance(metrics_ts, str)

    def test_readiness_vs_liveness_consistency(self, client: TestClient):
        """Test readiness and liveness checks are logically consistent."""
        liveness_response = client.get("/health/live")
        readiness_response = client.get("/health/ready")

        # If service is alive, it might not be ready, but consistency checks
        assert liveness_response.status_code == status.HTTP_200_OK

        # Readiness can fail even if liveness passes (this is expected)
        assert readiness_response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_503_SERVICE_UNAVAILABLE,
        ]

        # If both succeed, verify response format consistency
        if readiness_response.status_code == status.HTTP_200_OK:
            liveness_data = liveness_response.json()
            readiness_data = readiness_response.json()

            assert "status" in liveness_data
            assert "status" in readiness_data
            assert liveness_data["status"] == "alive"
            assert readiness_data["status"] == "ready"
