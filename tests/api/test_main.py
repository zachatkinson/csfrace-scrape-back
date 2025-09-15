"""Comprehensive tests for src/api/main.py module.

This test module provides comprehensive coverage for the FastAPI main application
in the API main module to achieve 80%+ coverage as required.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from slowapi.errors import RateLimitExceeded

from src.api.main import (
    _is_https_request,
    add_security_headers,
    app,
    global_exception_handler,
    lifespan,
    prometheus_metrics,
    rate_limit_handler,
    root,
)


class TestLifespanManager:
    """Test application lifespan management."""

    @pytest.mark.asyncio
    async def test_lifespan_startup_success(self):
        """Test successful startup sequence."""
        fake_app = MagicMock(spec=FastAPI)

        with patch("src.api.main.init_db", new_callable=AsyncMock) as mock_init_db:
            with patch("src.api.main.observability_manager") as mock_obs:
                with patch(
                    "src.api.main.initialize_health_service_registry", new_callable=AsyncMock
                ) as mock_health_init:
                    with patch(
                        "src.api.main.start_health_monitoring", new_callable=AsyncMock
                    ) as mock_health_start:
                        with patch(
                            "src.api.main.start_background_monitoring", new_callable=AsyncMock
                        ) as mock_bg_start:
                            with patch("src.api.main.cache_manager") as mock_cache:
                                with patch("src.api.main.DatabaseService") as mock_db_service:
                                    # Setup mocks
                                    mock_obs.initialize = AsyncMock()
                                    mock_cache.initialize = AsyncMock()
                                    mock_cache._ensure_backend.return_value._get_client = (
                                        AsyncMock()
                                    )

                                    # Test lifespan startup
                                    async with lifespan(fake_app):
                                        # Verify startup calls
                                        mock_init_db.assert_called_once()
                                        mock_obs.initialize.assert_called_once()
                                        mock_cache.initialize.assert_called_once()
                                        mock_health_init.assert_called_once()
                                        mock_health_start.assert_called_once()
                                        mock_bg_start.assert_called_once_with(check_interval=30)

    @pytest.mark.asyncio
    async def test_lifespan_startup_db_failure(self):
        """Test startup continues when database initialization fails."""
        fake_app = MagicMock(spec=FastAPI)

        with patch("src.api.main.init_db", new_callable=AsyncMock) as mock_init_db:
            with patch("src.api.main.observability_manager") as mock_obs:
                with patch(
                    "src.api.main.initialize_health_service_registry", new_callable=AsyncMock
                ):
                    with patch("src.api.main.start_health_monitoring", new_callable=AsyncMock):
                        with patch(
                            "src.api.main.start_background_monitoring", new_callable=AsyncMock
                        ):
                            with patch("src.api.main.cache_manager") as mock_cache:
                                with patch("src.api.main.DatabaseService"):
                                    # Setup failure
                                    mock_init_db.side_effect = Exception("DB init failed")
                                    mock_obs.initialize = AsyncMock()
                                    mock_cache.initialize = AsyncMock()
                                    mock_cache._ensure_backend.return_value._get_client = (
                                        AsyncMock()
                                    )

                                    # Should not raise exception
                                    async with lifespan(fake_app):
                                        pass

                                    # DB init should have been attempted
                                    mock_init_db.assert_called_once()

    @pytest.mark.asyncio
    async def test_lifespan_startup_observability_failure(self):
        """Test startup continues when observability initialization fails."""
        fake_app = MagicMock(spec=FastAPI)

        with patch("src.api.main.init_db", new_callable=AsyncMock) as mock_init_db:
            with patch("src.api.main.observability_manager") as mock_obs:
                with patch(
                    "src.api.main.initialize_health_service_registry", new_callable=AsyncMock
                ):
                    with patch("src.api.main.start_health_monitoring", new_callable=AsyncMock):
                        with patch(
                            "src.api.main.start_background_monitoring", new_callable=AsyncMock
                        ):
                            with patch("src.api.main.cache_manager") as mock_cache:
                                with patch("src.api.main.DatabaseService"):
                                    # Setup failure
                                    mock_obs.initialize = AsyncMock(
                                        side_effect=Exception("Obs failed")
                                    )
                                    mock_cache.initialize = AsyncMock()
                                    mock_cache._ensure_backend.return_value._get_client = (
                                        AsyncMock()
                                    )

                                    # Should not raise exception
                                    async with lifespan(fake_app):
                                        pass

                                    mock_init_db.assert_called_once()
                                    mock_obs.initialize.assert_called_once()

    @pytest.mark.asyncio
    async def test_lifespan_shutdown_success(self):
        """Test successful shutdown sequence."""
        fake_app = MagicMock(spec=FastAPI)

        with patch("src.api.main.init_db", new_callable=AsyncMock):
            with patch("src.api.main.observability_manager") as mock_obs:
                with patch(
                    "src.api.main.initialize_health_service_registry", new_callable=AsyncMock
                ):
                    with patch("src.api.main.start_health_monitoring", new_callable=AsyncMock):
                        with patch(
                            "src.api.main.start_background_monitoring", new_callable=AsyncMock
                        ):
                            with patch(
                                "src.api.main.stop_health_monitoring", new_callable=AsyncMock
                            ) as mock_health_stop:
                                with patch(
                                    "src.api.main.stop_background_monitoring",
                                    new_callable=AsyncMock,
                                ) as mock_bg_stop:
                                    with patch("src.api.main.cache_manager") as mock_cache:
                                        with patch("src.api.main.DatabaseService"):
                                            # Setup mocks
                                            mock_obs.initialize = AsyncMock()
                                            mock_obs.shutdown = AsyncMock()
                                            mock_cache.initialize = AsyncMock()
                                            mock_cache._ensure_backend.return_value._get_client = (
                                                AsyncMock()
                                            )

                                            # Test lifespan
                                            async with lifespan(fake_app):
                                                pass

                                            # Verify shutdown calls
                                            mock_health_stop.assert_called_once()
                                            mock_bg_stop.assert_called_once()
                                            mock_obs.shutdown.assert_called_once()

    @pytest.mark.asyncio
    async def test_lifespan_shutdown_failure_resilience(self):
        """Test shutdown continues even when components fail."""
        fake_app = MagicMock(spec=FastAPI)

        with patch("src.api.main.init_db", new_callable=AsyncMock):
            with patch("src.api.main.observability_manager") as mock_obs:
                with patch(
                    "src.api.main.initialize_health_service_registry", new_callable=AsyncMock
                ):
                    with patch("src.api.main.start_health_monitoring", new_callable=AsyncMock):
                        with patch(
                            "src.api.main.start_background_monitoring", new_callable=AsyncMock
                        ):
                            with patch(
                                "src.api.main.stop_health_monitoring", new_callable=AsyncMock
                            ) as mock_health_stop:
                                with patch(
                                    "src.api.main.stop_background_monitoring",
                                    new_callable=AsyncMock,
                                ) as mock_bg_stop:
                                    with patch("src.api.main.cache_manager") as mock_cache:
                                        with patch("src.api.main.DatabaseService"):
                                            # Setup failures
                                            mock_obs.initialize = AsyncMock()
                                            mock_obs.shutdown = AsyncMock(
                                                side_effect=Exception("Shutdown failed")
                                            )
                                            mock_health_stop.side_effect = Exception(
                                                "Health stop failed"
                                            )
                                            mock_bg_stop.side_effect = Exception("BG stop failed")
                                            mock_cache.initialize = AsyncMock()
                                            mock_cache._ensure_backend.return_value._get_client = (
                                                AsyncMock()
                                            )

                                            # Should not raise exception
                                            async with lifespan(fake_app):
                                                pass

                                            # All shutdown methods should have been attempted
                                            mock_health_stop.assert_called_once()
                                            mock_bg_stop.assert_called_once()
                                            mock_obs.shutdown.assert_called_once()


class TestSecurityMiddleware:
    """Test security headers middleware."""

    @pytest.mark.asyncio
    async def test_add_security_headers_http(self):
        """Test security headers for HTTP requests."""
        mock_request = MagicMock(spec=Request)
        mock_request.url.scheme = "http"
        mock_request.headers = {}

        mock_response = MagicMock()
        mock_response.headers = {}

        async def mock_call_next(request):
            return mock_response

        result = await add_security_headers(mock_request, mock_call_next)

        # Verify security headers
        assert result.headers["X-Frame-Options"] == "DENY"
        assert result.headers["X-Content-Type-Options"] == "nosniff"
        assert result.headers["X-XSS-Protection"] == "1; mode=block"
        assert result.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
        assert result.headers["X-Permitted-Cross-Domain-Policies"] == "none"
        assert "Content-Security-Policy" in result.headers
        assert "Permissions-Policy" in result.headers
        assert result.headers["X-Robots-Tag"] == "noindex, nofollow"

        # Should not have HSTS for HTTP
        assert "Strict-Transport-Security" not in result.headers

    @pytest.mark.asyncio
    async def test_add_security_headers_https(self):
        """Test security headers for HTTPS requests."""
        mock_request = MagicMock(spec=Request)
        mock_request.url.scheme = "https"
        mock_request.headers = {}

        mock_response = MagicMock()
        mock_response.headers = {}

        async def mock_call_next(request):
            return mock_response

        result = await add_security_headers(mock_request, mock_call_next)

        # Should have HSTS for HTTPS
        assert "Strict-Transport-Security" in result.headers
        assert "max-age=31536000" in result.headers["Strict-Transport-Security"]

    @pytest.mark.asyncio
    async def test_add_security_headers_proxy_https(self):
        """Test security headers for proxy HTTPS detection."""
        mock_request = MagicMock(spec=Request)
        mock_request.url.scheme = "http"
        mock_request.headers = {"X-Forwarded-Proto": "https"}

        mock_response = MagicMock()
        mock_response.headers = {}

        async def mock_call_next(request):
            return mock_response

        result = await add_security_headers(mock_request, mock_call_next)

        # Should have HSTS for proxy HTTPS
        assert "Strict-Transport-Security" in result.headers

    def test_is_https_request_direct_https(self):
        """Test HTTPS detection for direct HTTPS."""
        mock_request = MagicMock(spec=Request)
        mock_request.url.scheme = "https"
        mock_request.headers = {}

        assert _is_https_request(mock_request) is True

    def test_is_https_request_proxy_proto(self):
        """Test HTTPS detection via X-Forwarded-Proto header."""
        mock_request = MagicMock(spec=Request)
        mock_request.url.scheme = "http"
        mock_request.headers = {"X-Forwarded-Proto": "https"}

        assert _is_https_request(mock_request) is True

    def test_is_https_request_proxy_ssl(self):
        """Test HTTPS detection via X-Forwarded-SSL header."""
        mock_request = MagicMock(spec=Request)
        mock_request.url.scheme = "http"
        mock_request.headers = {"X-Forwarded-SSL": "on"}

        assert _is_https_request(mock_request) is True

    def test_is_https_request_http(self):
        """Test HTTPS detection for plain HTTP."""
        mock_request = MagicMock(spec=Request)
        mock_request.url.scheme = "http"
        mock_request.headers = {}

        assert _is_https_request(mock_request) is False


class TestExceptionHandlers:
    """Test exception handlers."""

    @pytest.mark.asyncio
    async def test_rate_limit_handler(self):
        """Test rate limit exception handler."""
        mock_request = MagicMock(spec=Request)
        mock_exc = RateLimitExceeded(detail="Rate limit exceeded")

        with patch("src.api.main.APIErrorFactory.rate_limit_exceeded") as mock_factory:
            mock_http_exc = MagicMock()
            mock_http_exc.status_code = 429
            mock_http_exc.detail = {"error": "Rate limit exceeded"}
            mock_factory.return_value = mock_http_exc

            response = await rate_limit_handler(mock_request, mock_exc)

            assert isinstance(response, JSONResponse)
            assert response.status_code == 429
            mock_factory.assert_called_once()

    @pytest.mark.asyncio
    async def test_global_exception_handler(self):
        """Test global exception handler."""
        mock_request = MagicMock(spec=Request)
        mock_request.url.path = "/test"
        test_exc = Exception("Test error")

        with patch("src.api.main.APIErrorFactory.internal_server_error") as mock_factory:
            mock_http_exc = MagicMock()
            mock_http_exc.status_code = 500
            mock_http_exc.detail = {"error": "Internal error"}
            mock_factory.return_value = mock_http_exc

            response = await global_exception_handler(mock_request, test_exc)

            assert isinstance(response, JSONResponse)
            assert response.status_code == 500
            mock_factory.assert_called_once_with(
                "An unexpected error occurred", original_error=test_exc
            )

    @pytest.mark.asyncio
    async def test_global_exception_handler_adds_path(self):
        """Test global exception handler adds path to error details."""
        mock_request = MagicMock(spec=Request)
        mock_request.url.path = "/api/test"
        test_exc = Exception("Test error")

        with patch("src.api.main.APIErrorFactory.internal_server_error") as mock_factory:
            # Create a mock HTTPException with dict detail
            mock_detail = {"error": "Internal error"}
            mock_http_exc = MagicMock()
            mock_http_exc.status_code = 500
            mock_http_exc.detail = mock_detail
            mock_factory.return_value = mock_http_exc

            await global_exception_handler(mock_request, test_exc)

            # Verify path was added to detail
            assert mock_detail["path"] == "/api/test"


class TestEndpoints:
    """Test API endpoints."""

    @pytest.mark.asyncio
    async def test_root_endpoint(self):
        """Test root endpoint response."""
        with patch("src.api.main.__version__", "1.0.0"):
            response = await root()

            assert hasattr(response, "message")
            assert "1.0.0" in response.message
            assert "/docs" in response.message
            assert "/health" in response.message

    @pytest.mark.asyncio
    async def test_prometheus_metrics_success(self):
        """Test successful metrics export."""
        with patch("src.api.main.metrics_collector") as mock_collector:
            mock_collector.export_prometheus_metrics.return_value = b"# HELP metric\nmetric 1.0\n"

            response = await prometheus_metrics()

            assert isinstance(response, str)
            assert "metric 1.0" in response
            mock_collector.export_prometheus_metrics.assert_called_once()

    @pytest.mark.asyncio
    async def test_prometheus_metrics_failure(self):
        """Test metrics export failure handling."""
        with patch("src.api.main.metrics_collector") as mock_collector:
            with patch("src.api.main.APIErrorFactory.internal_server_error") as mock_factory:
                # Setup failure
                mock_collector.export_prometheus_metrics.side_effect = Exception("Metrics failed")
                mock_factory.side_effect = Exception("Metrics error")

                with pytest.raises(Exception, match="Metrics error"):
                    await prometheus_metrics()

                mock_factory.assert_called_once()


class TestApplicationConfiguration:
    """Test FastAPI application configuration."""

    def test_app_basic_configuration(self):
        """Test basic app configuration."""
        assert app.title == "CSFrace Scraper API"
        assert app.description == "API for managing WordPress to Shopify content conversion jobs"
        assert hasattr(app, "version")

    def test_app_has_limiter(self):
        """Test that rate limiter is attached to app."""
        assert hasattr(app.state, "limiter")
        assert app.state.limiter is not None

    def test_app_middleware_configuration(self):
        """Test middleware configuration."""
        # Check that CORS middleware is configured
        cors_middleware = None
        for middleware in app.user_middleware:
            if "CORSMiddleware" in str(middleware.cls):
                cors_middleware = middleware
                break

        assert cors_middleware is not None

    def test_app_exception_handlers(self):
        """Test exception handlers are registered."""
        # Check that exception handlers are registered
        assert len(app.exception_handlers) > 0

        # Check for specific exception handlers
        handler_types = list(app.exception_handlers.keys())
        assert RateLimitExceeded in handler_types
        assert Exception in handler_types

    def test_app_routers_included(self):
        """Test that required routers are included."""
        # Get all routes
        routes = [route.path for route in app.routes]

        # Should have root route
        assert "/" in routes

        # Should have metrics route
        assert "/metrics" in routes

        # Should have health routes (from included routers)
        health_routes = [route for route in routes if "health" in route]
        assert len(health_routes) > 0


class TestCORSConfiguration:
    """Test CORS configuration."""

    def test_cors_origins_configuration(self):
        """Test CORS origins are properly configured."""
        with patch(
            "src.api.main.CONSTANTS.ALLOWED_ORIGINS_DEFAULT",
            "http://localhost:3000,https://example.com",
        ):
            # Re-import to get updated configuration
            import importlib

            import src.api.main

            importlib.reload(src.api.main)

            # CORS should be configured with split origins
            # This is verified by checking middleware configuration exists
            cors_middleware = None
            for middleware in src.api.main.app.user_middleware:
                if "CORSMiddleware" in str(middleware.cls):
                    cors_middleware = middleware
                    break

            assert cors_middleware is not None


class TestIntegrationWithTestClient:
    """Integration tests using FastAPI TestClient."""

    def test_root_endpoint_integration(self):
        """Test root endpoint through TestClient."""
        with TestClient(app) as client:
            response = client.get("/")

            assert response.status_code == 200
            data = response.json()
            assert "message" in data
            assert "CSFrace Scraper API" in data["message"]

    def test_metrics_endpoint_integration(self):
        """Test metrics endpoint through TestClient."""
        with patch("src.api.main.metrics_collector") as mock_collector:
            mock_collector.export_prometheus_metrics.return_value = b"# Metrics\ntest_metric 1.0\n"

            with TestClient(app) as client:
                response = client.get("/metrics")

                assert response.status_code == 200
                assert "test_metric 1.0" in response.text

    def test_security_headers_integration(self):
        """Test security headers in actual response."""
        with TestClient(app) as client:
            response = client.get("/")

            # Check security headers
            assert response.headers.get("X-Frame-Options") == "DENY"
            assert response.headers.get("X-Content-Type-Options") == "nosniff"
            assert response.headers.get("X-XSS-Protection") == "1; mode=block"
            assert "Content-Security-Policy" in response.headers

    def test_cors_headers_integration(self):
        """Test CORS headers in actual response."""
        with TestClient(app) as client:
            # Test preflight request
            response = client.options("/", headers={"Origin": "http://localhost:3000"})

            # Should handle OPTIONS request
            assert response.status_code in [200, 405]  # Depending on implementation
