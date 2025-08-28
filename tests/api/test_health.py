"""Tests for health and monitoring API endpoints."""

from unittest.mock import AsyncMock, patch

from fastapi import status
from fastapi.testclient import TestClient


class TestHealthEndpoints:
    """Test health and monitoring API endpoints."""

    def test_root_endpoint(self, client: TestClient):
        """Test root endpoint returns API information."""
        response = client.get("/")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["message"] == "CSFrace Scraper API"
        assert data["version"] == "1.0.0"
        assert data["docs"] == "/docs"
        assert data["health"] == "/health"

    def test_liveness_check(self, client: TestClient):
        """Test liveness check endpoint."""
        response = client.get("/health/live")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["status"] == "alive"

    def test_readiness_check_healthy(self, client: TestClient):
        """Test readiness check when database is available."""
        response = client.get("/health/ready")

        # Should be healthy with test database
        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["status"] == "ready"

    def test_readiness_check_unhealthy(self, client: TestClient, override_get_db):
        """Test readiness check when database is unavailable."""
        from unittest.mock import AsyncMock

        from src.api.dependencies import get_db_session
        from src.api.main import app

        # Create a mock session that fails
        async def mock_failing_db():
            mock_session = AsyncMock()
            mock_session.execute.side_effect = Exception("Database connection failed")
            yield mock_session

        # Override the dependency with failing mock
        app.dependency_overrides[get_db_session] = mock_failing_db

        try:
            response = client.get("/health/ready")

            assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
            data = response.json()

            assert "Service not ready" in data["detail"]
        finally:
            # Clean up override
            app.dependency_overrides.clear()

    @patch("src.monitoring.health.health_checker.get_health_summary")
    @patch("src.monitoring.observability.observability_manager.get_component_status")
    def test_health_check_healthy_system(
        self, mock_obs_status, mock_health_summary, client: TestClient
    ):
        """Test comprehensive health check with healthy system."""
        # Mock healthy responses
        mock_health_summary.return_value = {"status": "healthy"}
        mock_obs_status.return_value = {"status": "healthy"}

        response = client.get("/health/")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["status"] == "healthy"
        assert "timestamp" in data
        assert data["version"] == "1.0.0"
        assert data["database"]["status"] == "healthy"
        assert data["database"]["connected"] is True

    def test_health_check_database_failure(self, client: TestClient):
        """Test health check with database failure."""
        from src.api.dependencies import get_db_session
        from src.api.main import app

        # Create a mock session that raises an exception on execute
        async def failing_db_session():
            mock_session = AsyncMock()
            mock_session.execute.side_effect = Exception("Database connection failed")
            yield mock_session

        # Override the dependency
        app.dependency_overrides[get_db_session] = failing_db_session

        try:
            response = client.get("/health/")
            # Database failure should make overall status unhealthy
            assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        finally:
            # Clean up override
            app.dependency_overrides.pop(get_db_session, None)

    @patch("src.monitoring.health.health_checker.get_health_summary")
    def test_health_check_degraded_system(self, mock_health_summary, client: TestClient):
        """Test health check with degraded system status."""
        mock_health_summary.return_value = {"status": "degraded"}

        response = client.get("/health/")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Should report degraded status but still return 200
        assert data["status"] == "degraded"

    @patch("src.caching.manager.cache_manager")
    def test_health_check_with_cache(self, mock_cache_manager, client: TestClient):
        """Test health check with caching enabled."""
        mock_cache_manager.initialize = AsyncMock()
        mock_cache_manager.backend_type = "redis"

        response = client.get("/health/")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["cache"]["status"] == "healthy"
        assert data["cache"]["backend"] == "redis"

    @patch("src.caching.manager.cache_manager")
    def test_health_check_cache_error(self, mock_cache_manager, client: TestClient):
        """Test health check with cache error."""
        mock_cache_manager.initialize.side_effect = Exception("Redis connection failed")

        response = client.get("/health/")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Cache error should make system degraded
        assert data["status"] == "degraded"
        assert data["cache"]["status"] == "error"

    @patch("src.monitoring.metrics.metrics_collector.get_metrics_snapshot")
    def test_get_metrics_success(self, mock_metrics_snapshot, client: TestClient):
        """Test successful metrics retrieval."""
        mock_metrics_snapshot.return_value = {
            "system_metrics": {
                "cpu_usage": 25.5,
                "memory_usage": 512,
                "disk_usage": 1024,
            },
            "application_metrics": {
                "active_jobs": 5,
                "completed_jobs": 100,
                "failed_jobs": 2,
            },
            "database_metrics": {
                "active_connections": 10,
                "query_count": 1500,
            },
        }

        response = client.get("/health/metrics")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert "timestamp" in data
        assert data["system_metrics"]["cpu_usage"] == 25.5
        assert data["application_metrics"]["active_jobs"] == 5
        assert data["database_metrics"]["active_connections"] == 10

    @patch("src.monitoring.performance.performance_monitor.get_performance_summary")
    @patch("src.monitoring.metrics.metrics_collector.get_metrics_snapshot")
    def test_get_metrics_with_performance(
        self, mock_metrics_snapshot, mock_perf_summary, client: TestClient
    ):
        """Test metrics retrieval with performance data."""
        mock_metrics_snapshot.return_value = {
            "system_metrics": {"cpu_usage": 30.0},
            "application_metrics": {"active_jobs": 3},
            "database_metrics": {"active_connections": 5},
        }

        mock_perf_summary.return_value = {
            "avg_response_time": 150.5,
            "requests_per_second": 25.0,
            "error_rate": 0.01,
        }

        response = client.get("/health/metrics")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Performance metrics should be included in application_metrics
        assert data["application_metrics"]["avg_response_time"] == 150.5
        assert data["application_metrics"]["requests_per_second"] == 25.0

    @patch("src.monitoring.metrics.metrics_collector.get_metrics_snapshot")
    def test_get_metrics_failure(self, mock_metrics_snapshot, client: TestClient):
        """Test metrics retrieval failure."""
        mock_metrics_snapshot.side_effect = Exception("Metrics collection failed")

        response = client.get("/health/metrics")

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        data = response.json()

        assert "Failed to collect metrics" in data["detail"]

    @patch("src.monitoring.metrics.metrics_collector.export_prometheus_metrics")
    def test_prometheus_metrics_success(self, mock_export_prometheus, client: TestClient):
        """Test Prometheus metrics export."""
        mock_export_prometheus.return_value = b"""# HELP total_requests Total requests
# TYPE total_requests counter
total_requests 1234
# HELP active_jobs Currently active jobs
# TYPE active_jobs gauge
active_jobs 5
"""

        response = client.get("/health/prometheus")

        assert response.status_code == status.HTTP_200_OK
        assert "total_requests 1234" in response.text
        assert "active_jobs 5" in response.text

    @patch("src.monitoring.metrics.metrics_collector.export_prometheus_metrics")
    def test_prometheus_metrics_failure(self, mock_export_prometheus, client: TestClient):
        """Test Prometheus metrics export failure."""
        mock_export_prometheus.side_effect = Exception("Prometheus export failed")

        response = client.get("/health/prometheus")

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        data = response.json()

        assert "Failed to export Prometheus metrics" in data["detail"]

    def test_health_endpoints_response_format(self, client: TestClient):
        """Test that health endpoints return properly formatted responses."""
        response = client.get("/health/")

        assert response.status_code in [status.HTTP_200_OK, status.HTTP_503_SERVICE_UNAVAILABLE]
        data = response.json()

        # Verify required fields are present
        required_fields = ["status", "timestamp", "version", "database"]
        for field in required_fields:
            assert field in data

        # Verify timestamp format (ISO format)
        assert "T" in data["timestamp"]  # ISO format includes T
        assert data["timestamp"].endswith("Z") or "+" in data["timestamp"]  # UTC indicator

    def test_health_check_version_info(self, client: TestClient):
        """Test that health check includes version information."""
        response = client.get("/health/")
        data = response.json()

        assert data["version"] == "1.0.0"
        # TODO: In future, this should come from package metadata

    def test_concurrent_health_checks(self, client: TestClient):
        """Test multiple concurrent health check requests."""
        import concurrent.futures

        def make_request():
            return client.get("/health/")

        # Make 10 concurrent requests
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(make_request) for _ in range(10)]
            responses = [future.result() for future in concurrent.futures.as_completed(futures)]

        # All should succeed (or consistently fail)
        status_codes = [r.status_code for r in responses]
        assert all(
            code in [status.HTTP_200_OK, status.HTTP_503_SERVICE_UNAVAILABLE]
            for code in status_codes
        )

    def test_health_check_database_connection_details(self, client: TestClient):
        """Test that health check provides database connection details."""
        response = client.get("/health/")
        data = response.json()

        assert "database" in data
        db_status = data["database"]

        assert "status" in db_status
        assert "connected" in db_status
        assert db_status["status"] in ["healthy", "unhealthy"]
        assert isinstance(db_status["connected"], bool)
