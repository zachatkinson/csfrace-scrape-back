"""Tests for health stream router endpoints following testing best practices."""

import json
from decimal import Decimal

import pytest
from fastapi import status
from fastapi.testclient import TestClient


class TestHealthStreamEndpoints:
    """Test health streaming endpoints using real dependencies where possible."""

    def test_health_stream_sse_headers(self, client: TestClient):
        """Test SSE endpoint returns proper streaming headers."""
        response = client.get("/health/stream")

        # Check SSE headers are properly set
        assert response.headers["content-type"] == "text/event-stream; charset=utf-8"
        assert response.headers["cache-control"] == "no-cache"
        assert response.headers["connection"] == "keep-alive"
        assert response.headers["access-control-allow-origin"] == "*"
        assert response.headers["access-control-allow-headers"] == "Cache-Control"

    def test_trigger_health_check_endpoint(self, client: TestClient):
        """Test manual health check trigger endpoint."""
        response = client.post("/health/trigger-check")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Should have either success message or error
        assert "message" in data
        assert "health" in data or "error" in data

        if "health" in data:
            # If health data is present, verify basic structure
            health_data = data["health"]
            assert "status" in health_data
            assert "timestamp" in health_data

    def test_trigger_health_check_response_format(self, client: TestClient):
        """Test trigger health check response format consistency."""
        response = client.post("/health/trigger-check")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Response should have consistent structure
        assert isinstance(data, dict)
        assert "message" in data
        assert isinstance(data["message"], str)

        if "timestamp" in data:
            assert isinstance(data["timestamp"], str)


class TestJSONSerialization:
    """Test safe JSON serialization utilities."""

    def test_safe_json_dumps_basic_types(self):
        """Test JSON serialization with basic types."""
        from src.api.routers.health_stream import safe_json_dumps

        data = {
            "string": "test",
            "number": 42,
            "boolean": True,
            "null": None,
            "array": [1, 2, 3],
            "object": {"nested": "value"},
        }

        result = safe_json_dumps(data)
        assert isinstance(result, str)

        # Should be valid JSON
        parsed = json.loads(result)
        assert parsed == data

    def test_safe_json_dumps_with_decimal(self):
        """Test JSON serialization with Decimal objects."""
        from src.api.routers.health_stream import safe_json_dumps

        data = {"cpu_usage": Decimal("45.67"), "memory_usage": Decimal("78.90"), "message": "test"}

        result = safe_json_dumps(data)
        assert isinstance(result, str)

        parsed = json.loads(result)
        assert parsed["cpu_usage"] == 45.67
        assert parsed["memory_usage"] == 78.90
        assert parsed["message"] == "test"

    def test_safe_json_dumps_with_datetime(self):
        """Test JSON serialization with datetime objects."""
        from datetime import UTC, datetime

        from src.api.routers.health_stream import safe_json_dumps

        now = datetime.now(UTC)
        data = {"timestamp": now, "status": "healthy"}

        result = safe_json_dumps(data)
        assert isinstance(result, str)

        parsed = json.loads(result)
        assert "T" in parsed["timestamp"]  # ISO format contains T
        assert parsed["status"] == "healthy"

    def test_safe_json_dumps_mixed_types(self):
        """Test JSON serialization with mixed serializable types."""
        from datetime import UTC, datetime

        from src.api.routers.health_stream import safe_json_dumps

        data = {
            "decimal_value": Decimal("123.45"),
            "datetime_value": datetime.now(UTC),
            "string_value": "test",
            "number_value": 42,
            "nested_object": {"nested_decimal": Decimal("67.89")},
        }

        result = safe_json_dumps(data)
        assert isinstance(result, str)

        parsed = json.loads(result)
        assert parsed["decimal_value"] == 123.45
        assert parsed["nested_object"]["nested_decimal"] == 67.89

    def test_safe_json_dumps_non_serializable_raises_error(self):
        """Test JSON serialization with non-serializable objects raises appropriate error."""
        from src.api.routers.health_stream import safe_json_dumps

        class NonSerializable:
            pass

        data = {"object": NonSerializable(), "message": "test"}

        with pytest.raises(TypeError, match="not JSON serializable"):
            safe_json_dumps(data)


class TestHealthStreamErrorHandling:
    """Test error handling in health stream endpoints."""

    def test_invalid_http_method_on_stream(self, client: TestClient):
        """Test invalid HTTP method on stream endpoint."""
        response = client.post("/health/stream")

        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

    def test_invalid_http_method_on_trigger(self, client: TestClient):
        """Test invalid HTTP method on trigger endpoint."""
        response = client.get("/health/trigger-check")

        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

    def test_nonexistent_health_stream_endpoint(self, client: TestClient):
        """Test accessing non-existent health stream endpoint."""
        response = client.get("/health/nonexistent-stream")

        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestHealthStreamResponseFormat:
    """Test response format consistency for health stream endpoints."""

    def test_trigger_response_structure(self, client: TestClient):
        """Test trigger response has consistent structure."""
        response = client.post("/health/trigger-check")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Should always have message field
        assert "message" in data
        assert isinstance(data["message"], str)

        # Should have either health data or error
        has_health = "health" in data
        has_error = "error" in data
        assert has_health or has_error

        if has_health:
            health_data = data["health"]
            assert isinstance(health_data, dict)
            assert "status" in health_data

    def test_stream_response_headers(self, client: TestClient):
        """Test stream response headers are consistent."""
        response = client.get("/health/stream")

        # Should have proper SSE headers
        required_headers = {
            "content-type": "text/event-stream; charset=utf-8",
            "cache-control": "no-cache",
            "connection": "keep-alive",
            "access-control-allow-origin": "*",
        }

        for header, expected_value in required_headers.items():
            assert header in response.headers
            assert response.headers[header] == expected_value


class TestHealthStreamIntegration:
    """Test integration scenarios for health streaming."""

    def test_trigger_and_stream_consistency(self, client: TestClient):
        """Test trigger and stream endpoints are consistent."""
        # Trigger health check
        trigger_response = client.post("/health/trigger-check")
        assert trigger_response.status_code == status.HTTP_200_OK

        # Stream should be available
        stream_response = client.get("/health/stream")
        assert stream_response.headers["content-type"] == "text/event-stream; charset=utf-8"

        # Both should be operational
        trigger_data = trigger_response.json()
        assert "message" in trigger_data

    def test_stream_starts_without_errors(self, client: TestClient):
        """Test stream starts without immediate errors."""
        response = client.get("/health/stream")

        # Should start streaming (returns 200 with proper headers)
        assert response.status_code == status.HTTP_200_OK
        assert "text/event-stream" in response.headers["content-type"]

    def test_multiple_trigger_calls(self, client: TestClient):
        """Test multiple trigger calls work consistently."""
        responses = []

        for _ in range(3):
            response = client.post("/health/trigger-check")
            responses.append(response)

        # All should succeed
        for response in responses:
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert "message" in data

        # Responses should have consistent structure
        structures = [set(resp.json().keys()) for resp in responses]
        assert all(struct == structures[0] for struct in structures)
