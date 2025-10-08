"""FastAPI middleware components following Single Responsibility Principle.

This module contains all application middleware including:
- Metrics collection middleware
- Security headers middleware
- CORS configuration
- Helper functions for middleware
"""

import contextlib
import time
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any

from fastapi import Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from src.core.logging_hierarchy import get_api_logger

if TYPE_CHECKING:
    from fastapi import FastAPI

logger = get_api_logger()


class SecurityMiddleware:
    """Security headers middleware for comprehensive protection."""

    @staticmethod
    def _is_https_request(request: Request) -> bool:
        """Check if request is over HTTPS (including reverse proxy detection)."""
        return (
            request.url.scheme == "https"
            or request.headers.get("X-Forwarded-Proto", "").lower() == "https"
            or request.headers.get("X-Forwarded-SSL", "").lower() == "on"
        )

    @staticmethod
    async def add_security_headers(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """Add comprehensive security headers to all responses."""
        try:
            response: Response = await call_next(request)
        except Exception as e:
            logger.error("Error in request processing", error=str(e))
            raise

        # X-Frame-Options: Prevent clickjacking attacks
        response.headers["X-Frame-Options"] = "DENY"

        # X-Content-Type-Options: Prevent MIME type sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"

        # X-XSS-Protection: Enable browser XSS filtering (legacy support)
        response.headers["X-XSS-Protection"] = "1; mode=block"

        # Referrer-Policy: Control referrer information sent
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # X-Permitted-Cross-Domain-Policies: Control Flash/PDF cross-domain policies
        response.headers["X-Permitted-Cross-Domain-Policies"] = "none"

        # Content-Security-Policy: API CSP with Swagger UI support
        csp_directives = [
            "default-src 'none'",  # Deny all by default
            "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net",  # Allow Swagger UI scripts
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net",  # Allow Swagger UI styles
            "img-src 'self' data: https:",  # Allow images from same origin, data URLs, HTTPS
            "font-src 'self' https: https://cdn.jsdelivr.net",  # Allow fonts including CDN
            "connect-src 'self' http://localhost:8000 http://127.0.0.1:8000",  # API calls to same origin and localhost
            "frame-ancestors 'none'",  # Prevent framing (redundant with X-Frame-Options)
            "base-uri 'none'",  # Prevent base tag injection
            "form-action 'none'",  # No form submissions (API only)
            "frame-src 'none'",  # No frames allowed
            "object-src 'none'",  # No plugins allowed
            "media-src 'none'",  # No media elements
            "manifest-src 'none'",  # No web app manifests
            "worker-src 'none'",  # No web workers
            "child-src 'none'",  # No child browsing contexts
        ]
        response.headers["Content-Security-Policy"] = "; ".join(csp_directives)

        # Strict-Transport-Security: Force HTTPS (only add if HTTPS detected)
        if SecurityMiddleware._is_https_request(request):
            # 1 year max-age, include subdomains, allow preloading
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains; preload"
            )

        # Permissions-Policy: Control browser features
        permissions_policy = [
            "accelerometer=()",
            "camera=()",
            "geolocation=()",
            "gyroscope=()",
            "magnetometer=()",
            "microphone=()",
            "payment=()",
            "usb=()",
        ]
        response.headers["Permissions-Policy"] = ", ".join(permissions_policy)

        # X-Robots-Tag: Prevent search engine indexing of API endpoints
        response.headers["X-Robots-Tag"] = "noindex, nofollow"

        return response


class MetricsMiddleware:
    """Application metrics collection middleware."""

    @staticmethod
    async def collect_metrics_middleware(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """Collect application metrics for monitoring and observability."""
        from ..monitoring.metrics import metrics_collector

        start_time = time.time()
        method = request.method
        path = request.url.path

        # Skip metrics collection for static assets and health checks
        if path.startswith(("/static/", "/favicon.ico")) or path == "/health":
            skip_response: Response = await call_next(request)
            return skip_response

        try:
            # Increment active requests and connections
            metrics_collector.increment_active_connections()
            if metrics_collector.config.application_metrics_enabled and metrics_collector.metrics:
                _increment_active_requests_safe(metrics_collector)

            response: Response = await _handle_request_with_metrics_safe(
                call_next, request, metrics_collector, method, path, start_time
            )

            # Decrement active requests and connections
            metrics_collector.decrement_active_connections()
            if metrics_collector.config.application_metrics_enabled and metrics_collector.metrics:
                _decrement_active_requests_safe(metrics_collector)

            return response
        except Exception as e:
            # Decrement on error
            metrics_collector.decrement_active_connections()
            if metrics_collector.config.application_metrics_enabled and metrics_collector.metrics:
                with contextlib.suppress(Exception):
                    metrics_collector.metrics["active_requests"].dec()
            logger.error("Error in metrics collection", error=str(e))
            raise


class CORSConfiguration:
    """CORS middleware configuration for secure cross-origin requests."""

    @staticmethod
    def configure_cors(app: "FastAPI", allowed_origins: list[str]) -> None:
        """Configure CORS middleware with secure settings."""
        logger.info("Configuring CORS middleware", allowed_origins=allowed_origins)

        app.add_middleware(
            CORSMiddleware,
            allow_origins=[origin.strip() for origin in allowed_origins],
            allow_credentials=True,
            allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],  # Specific methods only
            allow_headers=["Content-Type", "Authorization", "Accept", "Origin", "X-Requested-With"],
        )

        logger.info("CORS middleware configured successfully")


def setup_middleware(app: "FastAPI", allowed_origins: list[str]) -> None:
    """Setup all application middleware following SOLID principles.

    Args:
        app: FastAPI application instance
        allowed_origins: List of allowed CORS origins
    """
    logger.info("Setting up application middleware")

    # Configure CORS middleware
    CORSConfiguration.configure_cors(app, allowed_origins)

    # Add metrics collection middleware
    app.middleware("http")(MetricsMiddleware.collect_metrics_middleware)

    # Add security headers middleware
    app.middleware("http")(SecurityMiddleware.add_security_headers)

    logger.info("Application middleware setup completed")


def _increment_active_requests_safe(metrics_collector: Any) -> None:
    """Safely increment active requests metric."""
    try:
        metrics_collector.metrics["active_requests"].inc()
    except Exception as e:
        logger.error("Failed to increment active requests", error=str(e))


def _decrement_active_requests_safe(metrics_collector: Any) -> None:
    """Safely decrement active requests metric."""
    try:
        metrics_collector.metrics["active_requests"].dec()
    except Exception as e:
        logger.error("Failed to decrement active requests", error=str(e))


async def _handle_request_with_metrics_safe(
    call_next: Callable[[Request], Awaitable[Response]],
    request: Request,
    metrics_collector: Any,
    method: str,
    path: str,
    start_time: float,
) -> Response:
    """Safely handle request with metrics recording."""
    try:
        response = await call_next(request)
        status_code = response.status_code

        # Record successful request
        duration = time.time() - start_time
        try:
            metrics_collector.record_request(method, path, status_code, duration)
        except Exception as e:
            logger.error("Failed to record request metrics", error=str(e))

        return response

    except Exception:
        # Record failed request
        duration = time.time() - start_time
        try:
            metrics_collector.record_request(method, path, 500, duration)
        except Exception as e:
            logger.error("Failed to record failed request metrics", error=str(e))
        raise
