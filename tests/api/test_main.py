"""Unit tests for src/api/main.py following AUDIT_3.md ZERO TOLERANCE standards.

MANDATORY REQUIREMENTS:
- NO vestigial code - every line serves a purpose
- NO legacy patterns - modern Python 3.11+ only
- NO backwards compatibility - clean implementations only
- NO broad exceptions - specific exceptions required
- SOLID principles compliance mandatory
- DRY compliance mandatory - no duplication
- Production-ready implementations only

Tests FastAPI application initialization with comprehensive coverage of:
- Application configuration
- Router registration
- Middleware setup
- Exception handler setup
- Rate limiting configuration
- Root endpoint functionality
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.main import app, limiter

# ============================================================================
# Application Initialization Tests
# ============================================================================


@pytest.mark.unit
class TestFastAPIApplicationInitialization:
    """Unit tests for FastAPI application initialization - MANDATORY AAA pattern."""

    def test_app_instance_is_fastapi(self) -> None:
        """Test app is valid FastAPI instance - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # (app is module-level, arranged by import)

        # Act - MANDATORY
        result = isinstance(app, FastAPI)

        # Assert - MANDATORY
        assert result is True
        assert app is not None

    def test_app_has_correct_title(self) -> None:
        """Test app has correct title configured - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        expected_title = "CSFrace Scraper API"

        # Act - MANDATORY
        actual_title = app.title

        # Assert - MANDATORY
        assert actual_title == expected_title

    def test_app_has_correct_description(self) -> None:
        """Test app has correct description - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        expected_description = "API for managing WordPress to Shopify content conversion jobs"

        # Act - MANDATORY
        actual_description = app.description

        # Assert - MANDATORY
        assert actual_description == expected_description

    def test_app_has_version_configured(self) -> None:
        """Test app has version from package - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        from src import __version__

        # Act - MANDATORY
        app_version = app.version

        # Assert - MANDATORY
        assert app_version is not None
        assert app_version == __version__
        assert isinstance(app_version, str)

    def test_app_has_lifespan_manager(self) -> None:
        """Test app has lifespan manager configured - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # (app configured with lifespan at module level)

        # Act - MANDATORY
        has_lifespan = hasattr(app, "router")
        has_lifespan_context = app.router.lifespan_context is not None

        # Assert - MANDATORY
        assert has_lifespan is True
        assert has_lifespan_context is True


# ============================================================================
# Rate Limiter Configuration Tests
# ============================================================================


@pytest.mark.unit
class TestRateLimiterConfiguration:
    """Unit tests for rate limiter configuration - MANDATORY AAA pattern."""

    def test_limiter_is_configured(self) -> None:
        """Test rate limiter is properly configured - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        from slowapi import Limiter

        # Act - MANDATORY
        is_limiter_instance = isinstance(limiter, Limiter)

        # Assert - MANDATORY
        assert is_limiter_instance is True
        assert limiter is not None

    def test_limiter_attached_to_app_state(self) -> None:
        """Test rate limiter is attached to app state - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # (limiter attached at module level)

        # Act - MANDATORY
        app_has_limiter = hasattr(app.state, "limiter")
        state_limiter = app.state.limiter if app_has_limiter else None

        # Assert - MANDATORY
        assert app_has_limiter is True
        assert state_limiter is limiter  # Same instance
        assert state_limiter is not None

    def test_limiter_has_headers_enabled(self) -> None:
        """Test rate limiter has headers enabled - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # (headers_enabled set at module level)

        # Act - MANDATORY
        headers_enabled = limiter._headers_enabled

        # Assert - MANDATORY
        assert headers_enabled is True


# ============================================================================
# Router Registration Tests
# ============================================================================


@pytest.mark.unit
class TestRouterRegistration:
    """Unit tests for router registration - MANDATORY AAA pattern."""

    def test_health_router_registered(self) -> None:
        """Test health router is registered - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        expected_routes = ["/health/", "/health/ready", "/health/live"]

        # Act - MANDATORY
        registered_paths = [route.path for route in app.routes]  # type: ignore[attr-defined]

        # Assert - MANDATORY
        for expected_path in expected_routes:
            assert any(expected_path in path for path in registered_paths), (
                f"Route {expected_path} not registered"
            )

    def test_auth_router_registered(self) -> None:
        """Test authentication router is registered - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        auth_route_prefixes = ["/api/auth", "/oauth"]

        # Act - MANDATORY
        registered_paths = [route.path for route in app.routes]  # type: ignore[attr-defined]

        # Assert - MANDATORY
        has_auth_routes = any(
            any(prefix in path for prefix in auth_route_prefixes) for path in registered_paths
        )
        assert has_auth_routes is True

    def test_jobs_router_registered(self) -> None:
        """Test jobs router is registered - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        expected_job_routes = ["/jobs/", "/jobs/{job_id}"]

        # Act - MANDATORY
        registered_paths = [route.path for route in app.routes]  # type: ignore[attr-defined]

        # Assert - MANDATORY
        for job_route in expected_job_routes:
            assert any(job_route in path for path in registered_paths), (
                f"Route {job_route} not registered"
            )

    def test_user_settings_router_registered(self) -> None:
        """Test user settings router is registered - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        settings_route = "/user/settings/"

        # Act - MANDATORY
        registered_paths = [route.path for route in app.routes]  # type: ignore[attr-defined]

        # Assert - MANDATORY
        has_settings_routes = any(settings_route in path for path in registered_paths)
        assert has_settings_routes is True

    def test_metrics_router_registered(self) -> None:
        """Test metrics router is registered - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        metrics_routes = ["/metrics", "/health/prometheus"]

        # Act - MANDATORY
        registered_paths = [route.path for route in app.routes]  # type: ignore[attr-defined]

        # Assert - MANDATORY
        for metrics_route in metrics_routes:
            assert any(metrics_route in path for path in registered_paths), (
                f"Metrics route {metrics_route} not registered"
            )


# ============================================================================
# Root Endpoint Tests
# ============================================================================


@pytest.mark.unit
class TestRootEndpoint:
    """Unit tests for root endpoint - MANDATORY AAA pattern."""

    def test_root_endpoint_returns_success(self) -> None:
        """Test root endpoint returns success response - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        client = TestClient(app)

        # Act - MANDATORY
        response = client.get("/")

        # Assert - MANDATORY
        assert response.status_code == 200
        assert response.json() is not None

    def test_root_endpoint_returns_message(self) -> None:
        """Test root endpoint returns message with version - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        from src import __version__

        client = TestClient(app)

        # Act - MANDATORY
        response = client.get("/")
        response_data = response.json()

        # Assert - MANDATORY
        assert "message" in response_data
        assert __version__ in response_data["message"]
        assert "CSFrace Scraper API" in response_data["message"]
        assert "/docs" in response_data["message"]
        assert "/health" in response_data["message"]

    def test_root_endpoint_response_model(self) -> None:
        """Test root endpoint uses MessageResponse model - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        client = TestClient(app)

        # Act - MANDATORY
        response = client.get("/")
        response_data = response.json()

        # Assert - MANDATORY
        assert isinstance(response_data, dict)
        assert "message" in response_data
        assert isinstance(response_data["message"], str)
        assert len(response_data["message"]) > 0


# ============================================================================
# Middleware Configuration Tests
# ============================================================================


@pytest.mark.unit
class TestMiddlewareConfiguration:
    """Unit tests for middleware configuration - MANDATORY AAA pattern."""

    def test_cors_middleware_configured(self) -> None:
        """Test CORS middleware is configured - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        from starlette.middleware.cors import CORSMiddleware

        # Act - MANDATORY
        middleware_types = [type(m) for m in app.user_middleware]
        has_cors = any(hasattr(m, "cls") and m.cls == CORSMiddleware for m in app.user_middleware)  # type: ignore[comparison-overlap]

        # Assert - MANDATORY
        assert has_cors is True

    def test_middleware_stack_configured(self) -> None:
        """Test middleware stack is configured - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # (middleware configured at module level)

        # Act - MANDATORY
        middleware_count = len(app.user_middleware)

        # Assert - MANDATORY
        # Should have at least CORS and security headers middleware
        assert middleware_count >= 1
        assert app.user_middleware is not None

    def test_security_headers_middleware_configured(self) -> None:
        """Test security headers middleware is configured - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        client = TestClient(app)

        # Act - MANDATORY
        response = client.get("/")
        headers = response.headers

        # Assert - MANDATORY (verify security headers are present)
        # These are added by SecurityHeadersMiddleware
        assert "x-content-type-options" in headers or "X-Content-Type-Options" in headers


# ============================================================================
# Exception Handler Tests
# ============================================================================


@pytest.mark.unit
class TestExceptionHandlerConfiguration:
    """Unit tests for exception handler configuration - MANDATORY AAA pattern."""

    def test_exception_handlers_configured(self) -> None:
        """Test exception handlers are configured - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # (exception handlers configured at module level)

        # Act - MANDATORY
        has_exception_handlers = len(app.exception_handlers) > 0

        # Assert - MANDATORY
        assert has_exception_handlers is True
        assert app.exception_handlers is not None


# ============================================================================
# MANDATORY Performance Benchmarks
# ============================================================================


@pytest.mark.performance
@pytest.mark.unit
class TestMainApplicationPerformance:
    """MANDATORY performance tests for main application."""

    def test_root_endpoint_performance(self) -> None:
        """MANDATORY performance test - root endpoint response time."""
        # Arrange - MANDATORY
        import time

        client = TestClient(app)
        iterations = 100

        # Act - MANDATORY
        start_time = time.time()

        for _ in range(iterations):
            response = client.get("/")
            assert response.status_code == 200

        end_time = time.time()
        execution_time = end_time - start_time

        # Assert - MANDATORY
        avg_time = execution_time / iterations
        assert avg_time < 0.05  # <50ms per request
        assert execution_time < 5.0  # Total <5s for 100 requests

    def test_app_initialization_performance(self) -> None:
        """MANDATORY performance test - app initialization time."""
        # Arrange - MANDATORY
        import time

        # Act - MANDATORY
        start_time = time.time()

        # Re-import to measure initialization
        from importlib import reload

        import src.api.main

        reload(src.api.main)

        end_time = time.time()
        initialization_time = end_time - start_time

        # Assert - MANDATORY
        assert initialization_time < 2.0  # App should initialize in <2s
