"""Comprehensive tests for src/api/utils.py module.

This test module provides comprehensive coverage for all utility functions
in the API utils module to achieve 80%+ coverage as required.
"""

import asyncio
import pytest
from fastapi import HTTPException, status
from pydantic import BaseModel
from sqlalchemy.exc import SQLAlchemyError

from src.api.utils import (
    bad_request_error,
    create_paginated_response,
    create_response_dict,
    handle_api_exceptions,
    handle_database_error,
    handle_service_errors,
    internal_server_error,
    maybe_none,
    rate_limited_endpoint,
    unauthorized_error,
    validation_error,
)


class TestHandleDatabaseError:
    """Test handle_database_error function."""

    def test_creates_error_handler_function(self):
        """Test that handle_database_error returns a callable."""
        handler = handle_database_error("test operation")
        assert callable(handler)

    def test_error_handler_returns_http_exception(self):
        """Test that the error handler returns HTTPException."""
        handler = handle_database_error("create user")
        test_error = SQLAlchemyError("Database connection failed")

        result = handler(test_error)

        assert isinstance(result, HTTPException)
        assert result.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert "Failed to create user" in result.detail
        assert "Database connection failed" in result.detail

    def test_error_handler_with_different_operations(self):
        """Test error handler with different operation names."""
        operations = ["retrieve batches", "update job", "delete record"]

        for operation in operations:
            handler = handle_database_error(operation)
            test_error = SQLAlchemyError("Test error")
            result = handler(test_error)

            assert f"Failed to {operation}" in result.detail


class TestCreatePaginatedResponse:
    """Test create_paginated_response function."""

    def test_basic_pagination(self):
        """Test basic pagination response structure."""
        items = ["item1", "item2", "item3"]
        result = create_paginated_response(items, total=10, page=1, page_size=3)

        expected = {
            "items": ["item1", "item2", "item3"],
            "total": 10,
            "page": 1,
            "page_size": 3,
            "total_pages": 4,
        }
        assert result == expected

    def test_total_pages_calculation(self):
        """Test total pages calculation with various scenarios."""
        test_cases = [
            (10, 3, 4),  # 10 items, 3 per page = 4 pages
            (9, 3, 3),  # 9 items, 3 per page = 3 pages
            (8, 3, 3),  # 8 items, 3 per page = 3 pages
            (7, 3, 3),  # 7 items, 3 per page = 3 pages
            (1, 5, 1),  # 1 item, 5 per page = 1 page
            (0, 5, 0),  # 0 items, 5 per page = 0 pages
        ]

        for total, page_size, expected_pages in test_cases:
            result = create_paginated_response([], total, 1, page_size)
            assert result["total_pages"] == expected_pages

    def test_empty_items_list(self):
        """Test pagination with empty items list."""
        result = create_paginated_response([], total=0, page=1, page_size=10)

        assert result["items"] == []
        assert result["total"] == 0
        assert result["total_pages"] == 0

    def test_last_page_scenario(self):
        """Test pagination for last page with fewer items."""
        items = ["item1", "item2"]
        result = create_paginated_response(items, total=8, page=3, page_size=3)

        assert result["items"] == ["item1", "item2"]
        assert result["total"] == 8
        assert result["page"] == 3
        assert result["total_pages"] == 3


class TestCreateResponseDict:
    """Test create_response_dict function."""

    def test_basic_response_dict(self):
        """Test basic response dictionary creation."""
        items = [{"id": 1}, {"id": 2}]
        result = create_response_dict("jobs", items, total=5, page=1, page_size=2)

        expected = {
            "jobs": [{"id": 1}, {"id": 2}],
            "total": 5,
            "page": 1,
            "page_size": 2,
            "total_pages": 3,
        }
        assert result == expected

    def test_different_items_keys(self):
        """Test response dict with different items keys."""
        items = ["batch1", "batch2"]
        result = create_response_dict("batches", items, total=2, page=1, page_size=10)

        assert result["batches"] == ["batch1", "batch2"]
        assert "jobs" not in result

    def test_integrates_with_paginated_response(self):
        """Test that it properly integrates with create_paginated_response."""
        items = list(range(5))

        # Test that both functions produce consistent pagination data
        paginated = create_paginated_response(items, total=15, page=2, page_size=5)
        response_dict = create_response_dict("data", items, total=15, page=2, page_size=5)

        # All pagination fields should match
        assert response_dict["total"] == paginated["total"]
        assert response_dict["page"] == paginated["page"]
        assert response_dict["page_size"] == paginated["page_size"]
        assert response_dict["total_pages"] == paginated["total_pages"]


class TestRateLimitedEndpoint:
    """Test rate_limited_endpoint decorator."""

    def test_decorator_returns_function(self):
        """Test that decorator returns the original function."""

        @rate_limited_endpoint("10/hour")
        def test_func():
            return "test"

        assert callable(test_func)
        assert test_func() == "test"

    def test_decorator_preserves_function_metadata(self):
        """Test that decorator preserves function metadata."""

        @rate_limited_endpoint("20/minute")
        def test_function_with_docstring():
            """This is a test function."""
            return "test"

        # Function should still work normally
        assert test_function_with_docstring() == "test"
        # Metadata should be preserved (decorator is primarily for documentation)
        assert test_function_with_docstring.__doc__ == "This is a test function."

    def test_decorator_with_different_rate_limits(self):
        """Test decorator with various rate limit strings."""
        rate_limits = ["5/second", "100/hour", "1000/day"]

        for rate_limit in rate_limits:

            @rate_limited_endpoint(rate_limit)
            def decorated_func(limit=rate_limit):  # Capture rate_limit in default parameter
                return f"limited to {limit}"

            result = decorated_func()
            assert rate_limit in result


class TestHttpErrorUtilities:
    """Test HTTP error utility functions."""

    def test_unauthorized_error(self):
        """Test unauthorized_error function."""
        error = unauthorized_error("Invalid token")

        assert isinstance(error, HTTPException)
        assert error.status_code == status.HTTP_401_UNAUTHORIZED
        assert error.detail == "Invalid token"
        assert error.headers == {"WWW-Authenticate": "Bearer"}

    def test_bad_request_error(self):
        """Test bad_request_error function."""
        error = bad_request_error("Invalid input format")

        assert isinstance(error, HTTPException)
        assert error.status_code == status.HTTP_400_BAD_REQUEST
        assert error.detail == "Invalid input format"
        assert not hasattr(error, "headers") or error.headers is None

    def test_internal_server_error(self):
        """Test internal_server_error function."""
        error = internal_server_error("Database unavailable")

        assert isinstance(error, HTTPException)
        assert error.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert error.detail == "Database unavailable"

    def test_validation_error(self):
        """Test validation_error function."""
        error = validation_error("Required field missing")

        assert isinstance(error, HTTPException)
        assert error.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert error.detail == "Required field missing"


class TestMaybeNone:
    """Test maybe_none utility function."""

    def test_function_returning_value(self):
        """Test maybe_none with function that returns a value."""

        def return_value():
            return "success"

        result = maybe_none(return_value)
        assert result == "success"

    def test_function_returning_none(self):
        """Test maybe_none with function that returns None."""

        def return_none():
            return None

        result = maybe_none(return_none)
        assert result is None

    def test_function_with_args_and_kwargs(self):
        """Test maybe_none with function arguments."""

        def add_numbers(a, b, multiplier=1):
            return (a + b) * multiplier

        result = maybe_none(add_numbers, 2, 3, multiplier=2)
        assert result == 10

    def test_function_that_raises_exception(self):
        """Test maybe_none with function that raises exception."""

        def raise_error():
            raise ValueError("Test error")

        with pytest.raises(ValueError, match="Test error"):
            maybe_none(raise_error)


class TestHandleApiExceptions:
    """Test handle_api_exceptions decorator."""

    @pytest.mark.asyncio
    async def test_async_function_success(self):
        """Test decorator with successful async function."""

        @handle_api_exceptions("Test operation failed")
        async def successful_async_func():
            return "success"

        result = await successful_async_func()
        assert result == "success"

    def test_sync_function_success(self):
        """Test decorator with successful sync function."""

        @handle_api_exceptions("Test operation failed")
        def successful_sync_func():
            return "success"

        result = successful_sync_func()
        assert result == "success"

    @pytest.mark.asyncio
    async def test_async_function_http_exception_reraise(self):
        """Test that HTTPException is re-raised for async functions."""

        @handle_api_exceptions("Test operation failed")
        async def async_func_with_http_error():
            raise HTTPException(status_code=404, detail="Not found")

        with pytest.raises(HTTPException) as exc_info:
            await async_func_with_http_error()

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "Not found"

    def test_sync_function_http_exception_reraise(self):
        """Test that HTTPException is re-raised for sync functions."""

        @handle_api_exceptions("Test operation failed")
        def sync_func_with_http_error():
            raise HTTPException(status_code=400, detail="Bad request")

        with pytest.raises(HTTPException) as exc_info:
            sync_func_with_http_error()

        assert exc_info.value.status_code == 400
        assert exc_info.value.detail == "Bad request"

    @pytest.mark.asyncio
    async def test_async_function_general_exception_conversion(self):
        """Test that general exceptions are converted to HTTPException for async functions."""

        @handle_api_exceptions("Database operation failed")
        async def async_func_with_error():
            raise ValueError("Invalid value")

        with pytest.raises(HTTPException) as exc_info:
            await async_func_with_error()

        assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert "Database operation failed: Invalid value" in exc_info.value.detail

    def test_sync_function_general_exception_conversion(self):
        """Test that general exceptions are converted to HTTPException for sync functions."""

        @handle_api_exceptions("File operation failed")
        def sync_func_with_error():
            raise OSError("File not found")

        with pytest.raises(HTTPException) as exc_info:
            sync_func_with_error()

        assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert "File operation failed: File not found" in exc_info.value.detail

    def test_decorator_detects_async_function(self):
        """Test that decorator correctly detects async vs sync functions."""

        @handle_api_exceptions("Test failed")
        async def async_func():
            return "async"

        @handle_api_exceptions("Test failed")
        def sync_func():
            return "sync"

        # Async function should return a coroutine
        result = async_func()
        assert asyncio.iscoroutine(result)
        result.close()  # Clean up coroutine

        # Sync function should return value directly
        result = sync_func()
        assert result == "sync"


class TestHandleServiceErrors:
    """Test handle_service_errors decorator."""

    @pytest.mark.asyncio
    async def test_async_function_success(self):
        """Test decorator with successful async function."""

        @handle_service_errors("create batch")
        async def successful_service():
            return {"id": 1, "status": "created"}

        result = await successful_service()
        assert result == {"id": 1, "status": "created"}

    def test_sync_function_success(self):
        """Test decorator with successful sync function."""

        @handle_service_errors("update job")
        def successful_service():
            return {"id": 2, "status": "updated"}

        result = successful_service()
        assert result == {"id": 2, "status": "updated"}

    @pytest.mark.asyncio
    async def test_async_validation_error_handling(self):
        """Test ValidationError handling for async functions."""

        @handle_service_errors("create user")
        async def service_with_validation_error():
            # Mock a ValidationError by using BaseModel validation
            from pydantic import field_validator

            class TestModel(BaseModel):
                email: str

                @field_validator("email")
                def validate_email(cls, v):
                    if "@" not in v:
                        raise ValueError("Invalid email")
                    return v

            # This will raise ValidationError
            TestModel(email="invalid")

        with pytest.raises(HTTPException) as exc_info:
            await service_with_validation_error()

        assert exc_info.value.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert "Validation error in create user" in exc_info.value.detail

    def test_sync_validation_error_handling(self):
        """Test ValidationError handling for sync functions."""

        @handle_service_errors("update profile")
        def service_with_validation_error():
            # Mock a ValidationError by using BaseModel validation
            from pydantic import field_validator

            class TestModel(BaseModel):
                name: str

                @field_validator("name")
                def validate_name(cls, v):
                    if len(v) < 2:
                        raise ValueError("Name too short")
                    return v

            # This will raise ValidationError
            TestModel(name="x")

        with pytest.raises(HTTPException) as exc_info:
            service_with_validation_error()

        assert exc_info.value.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert "Validation error in update profile" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_async_sqlalchemy_error_handling(self):
        """Test SQLAlchemyError handling for async functions."""

        @handle_service_errors("delete record")
        async def service_with_db_error():
            raise SQLAlchemyError("Connection timeout")

        with pytest.raises(HTTPException) as exc_info:
            await service_with_db_error()

        assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert "Failed to delete record" in exc_info.value.detail
        assert "Connection timeout" in exc_info.value.detail

    def test_sync_sqlalchemy_error_handling(self):
        """Test SQLAlchemyError handling for sync functions."""

        @handle_service_errors("fetch data")
        def service_with_db_error():
            raise SQLAlchemyError("Table does not exist")

        with pytest.raises(HTTPException) as exc_info:
            service_with_db_error()

        assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert "Failed to fetch data" in exc_info.value.detail
        assert "Table does not exist" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_async_value_error_handling(self):
        """Test ValueError handling for async functions."""

        @handle_service_errors("process data")
        async def service_with_value_error():
            raise ValueError("Invalid data format")

        with pytest.raises(HTTPException) as exc_info:
            await service_with_value_error()

        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert "Invalid data for process data" in exc_info.value.detail
        assert "Invalid data format" in exc_info.value.detail

    def test_sync_value_error_handling(self):
        """Test ValueError handling for sync functions."""

        @handle_service_errors("validate input")
        def service_with_value_error():
            raise ValueError("Number out of range")

        with pytest.raises(HTTPException) as exc_info:
            service_with_value_error()

        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert "Invalid data for validate input" in exc_info.value.detail
        assert "Number out of range" in exc_info.value.detail

    def test_decorator_preserves_function_metadata(self):
        """Test that decorator preserves function metadata."""

        @handle_service_errors("test operation")
        def test_service():
            """This is a test service function."""
            return "test"

        assert test_service.__doc__ == "This is a test service function."
        assert test_service() == "test"

    def test_decorator_detects_async_vs_sync(self):
        """Test that decorator correctly handles both async and sync functions."""

        @handle_service_errors("async test")
        async def async_service():
            return "async result"

        @handle_service_errors("sync test")
        def sync_service():
            return "sync result"

        # Async function should return coroutine
        result = async_service()
        assert asyncio.iscoroutine(result)
        result.close()  # Clean up

        # Sync function should return result directly
        result = sync_service()
        assert result == "sync result"


class TestIntegrationScenarios:
    """Test integration scenarios combining multiple utilities."""

    def test_pagination_with_error_handling(self):
        """Test pagination utilities work with error handling decorators."""

        @handle_service_errors("retrieve items")
        def get_paginated_items(page: int, page_size: int):
            if page < 1:
                raise ValueError("Page must be positive")

            # Simulate getting items
            items = [f"item_{i}" for i in range((page - 1) * page_size, page * page_size)]
            total = 100

            return create_response_dict("items", items, total, page, page_size)

        # Test successful case
        result = get_paginated_items(2, 5)
        assert result["items"] == ["item_5", "item_6", "item_7", "item_8", "item_9"]
        assert result["page"] == 2
        assert result["total"] == 100

        # Test error case
        with pytest.raises(HTTPException) as exc_info:
            get_paginated_items(-1, 5)

        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert "Invalid data for retrieve items" in exc_info.value.detail

    def test_database_error_with_service_decorator(self):
        """Test database error handling integration."""

        @handle_service_errors("database operation")
        def database_operation():
            # Simulate database error
            raise SQLAlchemyError("Connection failed")

        with pytest.raises(HTTPException) as exc_info:
            database_operation()

        assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert "Failed to database operation" in exc_info.value.detail

    def test_complete_api_endpoint_pattern(self):
        """Test complete pattern used in API endpoints."""

        @rate_limited_endpoint("10/minute")
        @handle_service_errors("process request")
        def api_endpoint(page: int = 1, page_size: int = 10):
            # Simulate validation
            if page_size > 100:
                raise ValueError("Page size too large")

            # Simulate data retrieval
            items = [{"id": i, "name": f"item_{i}"} for i in range(page_size)]
            total = 50

            return create_response_dict("data", items, total, page, page_size)

        # Test successful case
        result = api_endpoint(1, 5)
        assert len(result["data"]) == 5
        assert result["total"] == 50
        assert result["total_pages"] == 10

        # Test validation error
        with pytest.raises(HTTPException) as exc_info:
            api_endpoint(1, 150)

        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_create_paginated_response_edge_cases(self):
        """Test edge cases for pagination."""
        # Zero total with non-zero page size
        result = create_paginated_response([], 0, 1, 10)
        assert result["total_pages"] == 0

        # Single item, single page
        result = create_paginated_response(["item"], 1, 1, 1)
        assert result["total_pages"] == 1

        # Large numbers
        result = create_paginated_response([], 1000000, 1, 1000)
        assert result["total_pages"] == 1000

    def test_error_functions_with_empty_strings(self):
        """Test error functions with empty detail strings."""
        errors = [
            unauthorized_error(""),
            bad_request_error(""),
            internal_server_error(""),
            validation_error(""),
        ]

        for error in errors:
            assert isinstance(error, HTTPException)
            assert error.detail == ""

    def test_maybe_none_with_complex_functions(self):
        """Test maybe_none with more complex function scenarios."""

        class TestClass:
            def method_returning_none(self):
                return None

            def method_with_side_effects(self):
                self.called = True
                return "result"

        obj = TestClass()

        # Test bound method returning None
        result = maybe_none(obj.method_returning_none)
        assert result is None

        # Test bound method with side effects
        result = maybe_none(obj.method_with_side_effects)
        assert result == "result"
        assert hasattr(obj, "called") and obj.called

    def test_decorators_preserve_original_exceptions(self):
        """Test that decorators properly preserve exception chaining."""

        @handle_service_errors("test")
        def func_with_chained_exception():
            try:
                raise ValueError("Original error")
            except ValueError as e:
                # ValueError is handled by the decorator, so let's use a ValueError that gets re-raised
                raise ValueError("Wrapper error") from e

        with pytest.raises(HTTPException) as exc_info:
            func_with_chained_exception()

        # The original exception should be preserved in the chain
        assert exc_info.value.__cause__ is not None
        assert isinstance(exc_info.value.__cause__, ValueError)
        assert "Wrapper error" in str(exc_info.value.__cause__)
