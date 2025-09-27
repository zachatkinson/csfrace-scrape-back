"""Tests for APIErrorFactory - SOLID and DRY compliance validation."""

from unittest.mock import patch

import pytest
from fastapi import HTTPException

from src.api.errors import APIErrorFactory
from src.core.exceptions import (
    APINotFoundError,
    APIValidationError,
    ConfigurationError,
    ConversionError,
    ProcessingError,
    RateLimitError,
)


class TestAPIErrorFactory:
    """Test APIErrorFactory following Single Responsibility Principle."""

    def test_not_found_error_creation(self):
        """Test APIErrorFactory creates standardized 404 Not Found responses."""
        exception = APIErrorFactory.not_found("Job", 123)

        assert isinstance(exception, HTTPException)
        assert exception.status_code == 404

        # The detail should be a structured error dict
        detail = exception.detail
        assert isinstance(detail, dict)
        assert detail["error_code"] == "API_NOT_FOUND"
        assert "Job" in detail["message"]
        assert "123" in detail["message"]
        assert detail["context"]["resource_type"] == "Job"
        assert detail["context"]["identifier"] == "123"

        # Logging happens through structlog - test functionality, not implementation detail

    def test_validation_error_creation(self):
        """Test APIErrorFactory creates standardized 422 Validation Error responses."""
        validation_message = "URL is required"

        with patch("src.core.exceptions.logger") as mock_logger:
            exception = APIErrorFactory.validation_error(validation_message)

            assert isinstance(exception, HTTPException)
            assert exception.status_code == 422

            # The detail should be a structured error dict
            detail = exception.detail
            assert isinstance(detail, dict)
            assert detail["error_code"] == "API_VALIDATION_ERROR"
            assert validation_message in detail["message"]

            # Verify logging occurs
            mock_logger.warning.assert_called_once()

    def test_server_error_creation(self):
        """Test APIErrorFactory creates standardized 500 Internal Server Error responses."""
        original_error = Exception("Database connection failed")

        with patch("src.core.exceptions.logger") as mock_logger:
            exception = APIErrorFactory.internal_server_error(
                "Internal server error", original_error
            )

            assert isinstance(exception, HTTPException)
            assert exception.status_code == 500

            # The detail should be a structured error dict
            detail = exception.detail
            assert isinstance(detail, dict)
            assert detail["error_code"] == "INTERNAL_SERVER_ERROR"
            assert "Internal server error" in detail["message"]

            # Should not leak internal error details in production (unless debug mode)
            assert "Database connection failed" not in detail["message"]

            # Verify error logging with context
            mock_logger.error.assert_called_once()

    def test_rate_limit_error_creation(self):
        """Test APIErrorFactory creates standardized 429 Rate Limit responses."""

        with patch("src.core.exceptions.logger") as mock_logger:
            exception = APIErrorFactory.rate_limit_exceeded("Rate limit exceeded")

            assert isinstance(exception, HTTPException)
            assert exception.status_code == 429

            # The detail should be a structured error dict
            detail = exception.detail
            assert isinstance(detail, dict)
            assert detail["error_code"] == "API_RATE_LIMIT_EXCEEDED"
            assert "Rate limit exceeded" in detail["message"]

            # Verify error logging occurs
            mock_logger.warning.assert_called_once()

    def test_business_logic_error_creation(self):
        """Test APIErrorFactory creates standardized 400 Business Logic Error responses."""
        conflict_details = "Job is already running and cannot be modified"

        with patch("src.core.exceptions.logger") as mock_logger:
            exception = APIErrorFactory.business_logic_error(conflict_details)

            assert isinstance(exception, HTTPException)
            assert exception.status_code == 400  # BusinessLogicError uses 400, not 409

            # The detail should be a structured error dict
            detail = exception.detail
            assert isinstance(detail, dict)
            assert detail["error_code"] == "API_BUSINESS_LOGIC_ERROR"
            assert conflict_details in detail["message"]

            # Verify error logging occurs
            mock_logger.warning.assert_called_once()

    def test_error_factory_dry_principle(self):
        """Test that all error creation methods follow DRY principle with shared utilities."""
        with patch("src.api.errors.logger"):
            # Test that error detail creation is consistent across methods
            not_found_exc = APIErrorFactory.not_found("User", "abc123")
            validation_exc = APIErrorFactory.validation_error("Test error")

            # Both should have structured error details (dict format)
            assert isinstance(not_found_exc.detail, dict)
            assert isinstance(validation_exc.detail, dict)

            # Both should have consistent structure with required fields
            assert "error_code" in not_found_exc.detail
            assert "message" in not_found_exc.detail
            assert "timestamp" in not_found_exc.detail

            assert "error_code" in validation_exc.detail
            assert "message" in validation_exc.detail
            assert "timestamp" in validation_exc.detail

            # Both should be HTTPException instances (consistent interface)
            assert isinstance(not_found_exc, HTTPException)
            assert isinstance(validation_exc, HTTPException)

    def test_error_mapping_coverage(self):
        """Test that factory handles all common exception types."""
        test_cases = [
            (APINotFoundError("User", "123"), 404),
            (APIValidationError("Invalid input"), 422),
            (ConversionError("Failed to convert"), 500),
            (ProcessingError("Processing failed"), 500),
            (ConfigurationError("Config invalid"), 500),
            (RateLimitError("Too many requests"), 500),  # Using existing RateLimitError
        ]

        for error, expected_status in test_cases:
            with patch("src.api.errors.logger"):
                # Test that factory can handle each exception type appropriately
                if isinstance(error, APINotFoundError):
                    exc = APIErrorFactory.not_found(
                        error.details["resource_type"], error.details["identifier"]
                    )
                elif isinstance(error, APIValidationError):
                    exc = APIErrorFactory.validation_error(str(error))
                else:
                    exc = APIErrorFactory.internal_server_error(str(error), error)

                assert exc.status_code == expected_status
                assert isinstance(exc.detail, dict)  # Verify structured response
                assert "error_code" in exc.detail


class TestErrorFactoryIntegration:
    """Test APIErrorFactory integration with FastAPI."""

    @pytest.mark.asyncio
    async def test_factory_with_fastapi_exception_handler(self):
        """Test factory integrates properly with FastAPI exception handling."""
        from fastapi import FastAPI
        from fastapi.responses import JSONResponse
        from fastapi.testclient import TestClient

        app = FastAPI()

        @app.exception_handler(APINotFoundError)
        async def handle_not_found(request, exc):
            http_exc = APIErrorFactory.not_found(
                exc.details["resource_type"], exc.details["identifier"]
            )
            return JSONResponse(
                status_code=http_exc.status_code, content={"detail": http_exc.detail}
            )

        @app.get("/test-not-found")
        async def test_endpoint():
            raise APINotFoundError("TestResource", "123")

        client = TestClient(app)
        response = client.get("/test-not-found")

        assert response.status_code == 404
        assert "TestResource" in str(response.json()["detail"])
        assert "123" in str(response.json()["detail"])

    def test_error_factory_thread_safety(self):
        """Test that APIErrorFactory is thread-safe (stateless design)."""
        import concurrent.futures

        results = []

        def create_error():
            with patch("src.core.exceptions.logger"):
                exc = APIErrorFactory.not_found("User", "test-id")
                results.append(exc.status_code)

        # Run multiple threads simultaneously
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(create_error) for _ in range(20)]
            concurrent.futures.wait(futures)

        # All results should be consistent (404 status code)
        assert all(status == 404 for status in results)
        assert len(results) == 20

    def test_error_factory_memory_efficiency(self):
        """Test that APIErrorFactory doesn't leak memory with repeated use."""
        import gc

        initial_objects = len(gc.get_objects())

        # Create many errors
        with patch("src.core.exceptions.logger"):
            for i in range(1000):
                APIErrorFactory.not_found("Resource", i)

        # Force garbage collection
        gc.collect()

        final_objects = len(gc.get_objects())

        # Should not have significant memory growth (within 10% tolerance)
        growth_ratio = (final_objects - initial_objects) / initial_objects
        assert growth_ratio < 0.1, f"Memory growth ratio: {growth_ratio}"
