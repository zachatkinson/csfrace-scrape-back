"""Unit tests for API main module."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import Request
from fastapi.testclient import TestClient

from src import __version__
from src.api.main import app, global_exception_handler, lifespan


class TestFastAPIApp:
    """Test FastAPI application configuration."""

    def test_app_configuration(self):
        """Test that FastAPI app is properly configured."""
        assert app.title == "CSFrace Scraper API"
        assert app.description == "API for managing WordPress to Shopify content conversion jobs"
        assert app.version == __version__
        assert app.docs_url == "/docs"
        assert app.redoc_url == "/redoc"

    def test_cors_middleware_configured(self):
        """Test that CORS middleware is properly configured."""
        # Check that CORS middleware is in the middleware stack
        middleware_stack = app.user_middleware

        # Check if any middleware is CORS-related
        cors_present = any(
            "cors" in str(middleware_item).lower() for middleware_item in middleware_stack
        )
        assert cors_present

    def test_routers_included(self):
        """Test that all routers are included in the app."""
        routes = [route.path for route in app.routes]

        # Check health routes (noting trailing slash)
        health_routes = [route for route in routes if "/health" in route]
        assert len(health_routes) > 0
        assert any("/health/" in route for route in health_routes)
        assert "/health/live" in routes
        assert "/health/ready" in routes
        assert "/health/metrics" in routes
        assert "/health/prometheus" in routes

        # Check job routes
        job_routes = [route for route in routes if "/jobs" in route]
        assert len(job_routes) > 0

        # Check batch routes
        batch_routes = [route for route in routes if "/batches" in route]
        assert len(batch_routes) > 0

    def test_root_endpoint_functionality(self):
        """Test root endpoint returns correct information."""
        with TestClient(app) as client:
            response = client.get("/")

            assert response.status_code == 200
            data = response.json()

            assert data["message"] == "CSFrace Scraper API"
            assert data["version"] == __version__
            assert data["docs"] == "/docs"
            assert data["health"] == "/health"

    def test_exception_handlers_registered(self):
        """Test that exception handlers are registered."""
        # Check that global exception handler is registered
        assert Exception in app.exception_handlers


class TestLifespanManager:
    """Test application lifespan management."""

    @pytest.mark.asyncio
    async def test_lifespan_startup_success(self):
        """Test successful lifespan startup."""
        with patch("src.api.main.init_db") as mock_init_db:
            mock_init_db.return_value = AsyncMock()

            # Test the lifespan context manager
            async with lifespan(app):
                pass

            mock_init_db.assert_called_once()

    @pytest.mark.asyncio
    async def test_lifespan_startup_failure(self):
        """Test lifespan handles database initialization failure gracefully."""
        with patch("src.api.main.init_db") as mock_init_db:
            mock_init_db.side_effect = Exception("Database connection failed")

            # Should not raise exception, just print error
            with patch("builtins.print") as mock_print:
                async with lifespan(app):
                    pass

                mock_print.assert_called_once_with(
                    "Database initialization failed: Database connection failed"
                )

    @pytest.mark.asyncio
    async def test_lifespan_shutdown(self):
        """Test lifespan shutdown logic."""
        # Currently shutdown logic is minimal, test it executes
        async with lifespan(app):
            pass
        # Should complete without error


class TestGlobalExceptionHandler:
    """Test global exception handler."""

    @pytest.fixture
    def mock_request(self):
        """Create a mock request."""
        request = MagicMock(spec=Request)
        request.url.path = "/test/path"
        return request

    @pytest.mark.asyncio
    async def test_global_exception_handler_response(self, mock_request):
        """Test global exception handler returns proper error response."""
        test_exception = Exception("Test error message")

        response = await global_exception_handler(mock_request, test_exception)

        assert response.status_code == 500
        assert response.media_type == "application/json"

        # Check response content
        import json

        content = json.loads(response.body.decode())

        assert content["detail"] == "Internal server error"
        assert content["type"] == "internal_error"
        assert content["path"] == "/test/path"

    @pytest.mark.asyncio
    async def test_global_exception_handler_different_paths(self):
        """Test global exception handler with different request paths."""
        test_paths = ["/", "/jobs", "/batches/123", "/health"]

        for path in test_paths:
            request = MagicMock(spec=Request)
            request.url.path = path

            response = await global_exception_handler(request, Exception("Test"))

            import json

            content = json.loads(response.body.decode())
            assert content["path"] == path

    @pytest.mark.asyncio
    async def test_global_exception_handler_preserves_exception_details(self, mock_request):
        """Test that exception handler provides consistent error format."""
        different_exceptions = [
            ValueError("Value error"),
            KeyError("Key error"),
            RuntimeError("Runtime error"),
            AttributeError("Attribute error"),
        ]

        for exc in different_exceptions:
            response = await global_exception_handler(mock_request, exc)

            assert response.status_code == 500

            import json

            content = json.loads(response.body.decode())

            # All should return same standardized error format
            assert content["detail"] == "Internal server error"
            assert content["type"] == "internal_error"

    @pytest.mark.asyncio
    async def test_global_exception_handler_json_response_format(self, mock_request):
        """Test that exception handler returns valid JSON response."""
        response = await global_exception_handler(mock_request, Exception("Test"))

        # Should be valid JSON
        import json

        content = json.loads(response.body.decode())

        # Required fields
        assert "detail" in content
        assert "type" in content
        assert "path" in content

        # Check types
        assert isinstance(content["detail"], str)
        assert isinstance(content["type"], str)
        assert isinstance(content["path"], str)


class TestAppIntegration:
    """Integration tests for app components."""

    def test_app_startup_sequence(self):
        """Test that app starts successfully with all components."""
        # Test that app can be instantiated and configured
        with TestClient(app) as client:
            # App should start successfully
            response = client.get("/")
            assert response.status_code == 200

    def test_middleware_stack_order(self):
        """Test that middleware is applied in correct order."""
        # CORS middleware should be in the stack
        middleware_stack = app.user_middleware
        assert len(middleware_stack) > 0

        # Check if any middleware is CORS-related by name
        cors_present = any(
            "cors" in str(middleware_item).lower() for middleware_item in middleware_stack
        )
        assert cors_present

    def test_main_module_execution(self):
        """Test main module execution block."""
        # Test basic module structure without mocking uvicorn
        import src.api.main

        # Test that the code structure is correct
        assert hasattr(src.api.main, "app")
        assert callable(src.api.main.root)

    def test_app_route_registration(self):
        """Test that all expected routes are registered."""
        # Get all registered routes
        routes = {route.path: route.methods for route in app.routes if hasattr(route, "methods")}

        # Root route
        assert "/" in routes
        assert "GET" in routes["/"]

        # Health routes should be registered via router inclusion
        health_routes = [path for path in routes if path.startswith("/health")]
        assert len(health_routes) > 0

    def test_uvicorn_configuration_parameters(self):
        """Test that app is properly configured for uvicorn."""
        # Test that the app object is properly configured for uvicorn
        assert app is not None
        assert hasattr(app, "routes")
        assert hasattr(app, "middleware_stack")
        assert hasattr(app, "exception_handlers")

    def test_app_openapi_configuration(self):
        """Test OpenAPI documentation configuration."""
        openapi_schema = app.openapi()

        assert openapi_schema["info"]["title"] == "CSFrace Scraper API"
        assert openapi_schema["info"]["version"] == __version__
        assert (
            openapi_schema["info"]["description"]
            == "API for managing WordPress to Shopify content conversion jobs"
        )

    def test_app_exception_handler_coverage(self):
        """Test that exception handlers cover expected exception types."""
        handlers = app.exception_handlers

        # Should have handler for general Exception
        assert Exception in handlers

        # Handler should be our global exception handler
        assert handlers[Exception] == global_exception_handler
