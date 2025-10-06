"""Comprehensive tests for system info endpoints - MANDATORY TEST_BUILDING.md compliance.

This module tests system information functionality with complete coverage:
- Router configuration
- System info endpoint
- Version detection
- Uptime tracking
- Platform information gathering
- Error handling scenarios

ALL tests follow MANDATORY TEST_BUILDING.md patterns:
- AAA pattern with explicit comments
- Factory fixtures for DRY principle
- Comprehensive system info scenario testing
- Performance benchmarks with specific thresholds
"""

import platform
import sys
import time
from datetime import datetime
from typing import Any
from unittest.mock import patch

import asyncio
import pytest
from fastapi import APIRouter
from fastapi.routing import APIRoute

from src.api.routers.health.system_info import (
    SystemInfoResponse,
    _get_application_version,
    router,
    system_info,
)

# ============================================================================
# Test Fixtures - DRY Principle
# ============================================================================


@pytest.fixture
def sample_system_info() -> dict[str, Any]:
    """Factory for sample system info - DRY principle."""
    return {
        "platform": "Darwin",
        "platform_release": "25.0.0",
        "platform_version": "Darwin Kernel Version 25.0.0",
        "architecture": "arm64",
        "processor": "arm",
        "python_version": "3.13.7",
        "python_implementation": "CPython",
        "app_version": "1.0.0",
        "uptime_seconds": 3600,
        "startup_time": datetime.now(),
    }


# ============================================================================
# Router Configuration Tests
# ============================================================================


@pytest.mark.unit
class TestSystemInfoRouter:
    """Tests for system info router configuration."""

    def test_router_exists(self) -> None:
        """Test that system info router exists - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # Act - MANDATORY
        # Assert - MANDATORY
        assert router is not None
        assert isinstance(router, APIRouter)

    def test_router_has_system_endpoint(self) -> None:
        """Test router has /system endpoint - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # Act - MANDATORY
        routes = [route.path for route in router.routes if isinstance(route, APIRoute)]

        # Assert - MANDATORY
        assert "/system" in routes

    def test_system_endpoint_uses_get_method(self) -> None:
        """Test system endpoint uses GET method - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # Act - MANDATORY
        system_route = next(
            route
            for route in router.routes
            if isinstance(route, APIRoute) and route.path == "/system"
        )

        # Assert - MANDATORY
        assert "GET" in system_route.methods


# ============================================================================
# System Info Response Model Tests
# ============================================================================


@pytest.mark.unit
class TestSystemInfoResponseModel:
    """Tests for SystemInfoResponse model."""

    def test_system_info_response_model_exists(self) -> None:
        """Test SystemInfoResponse model exists - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # Act - MANDATORY
        # Assert - MANDATORY
        assert SystemInfoResponse is not None

    def test_system_info_response_has_required_fields(
        self, sample_system_info: dict[str, Any]
    ) -> None:
        """Test SystemInfoResponse has all required fields - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # Act - MANDATORY
        response = SystemInfoResponse(**sample_system_info)

        # Assert - MANDATORY
        assert hasattr(response, "platform")
        assert hasattr(response, "platform_release")
        assert hasattr(response, "platform_version")
        assert hasattr(response, "architecture")
        assert hasattr(response, "processor")
        assert hasattr(response, "python_version")
        assert hasattr(response, "python_implementation")
        assert hasattr(response, "app_version")
        assert hasattr(response, "uptime_seconds")
        assert hasattr(response, "startup_time")

    def test_system_info_response_validates_types(self, sample_system_info: dict[str, Any]) -> None:
        """Test SystemInfoResponse validates field types - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # Act - MANDATORY
        response = SystemInfoResponse(**sample_system_info)

        # Assert - MANDATORY
        assert isinstance(response.platform, str)
        assert isinstance(response.platform_release, str)
        assert isinstance(response.platform_version, str)
        assert isinstance(response.architecture, str)
        assert isinstance(response.processor, str)
        assert isinstance(response.python_version, str)
        assert isinstance(response.python_implementation, str)
        assert isinstance(response.app_version, str)
        assert isinstance(response.uptime_seconds, int)
        assert isinstance(response.startup_time, datetime)


# ============================================================================
# Application Version Tests
# ============================================================================


@pytest.mark.unit
class TestApplicationVersion:
    """Tests for application version detection."""

    def test_get_application_version_exists(self) -> None:
        """Test _get_application_version function exists - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # Act - MANDATORY
        # Assert - MANDATORY
        assert callable(_get_application_version)

    def test_get_application_version_returns_string(self) -> None:
        """Test _get_application_version returns string - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # Act - MANDATORY
        result = _get_application_version()

        # Assert - MANDATORY
        assert isinstance(result, str)
        assert len(result) > 0

    def test_get_application_version_handles_exception(self) -> None:
        """Test _get_application_version returns fallback on exception - MANDATORY AAA pattern."""
        # Arrange - MANDATORY

        # Act - MANDATORY
        with patch("importlib.metadata.version", side_effect=Exception("Package not found")):
            result = _get_application_version()

        # Assert - MANDATORY
        assert result == "1.0.0"  # Fallback version


# ============================================================================
# System Info Endpoint Tests
# ============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
class TestSystemInfoEndpoint:
    """Tests for GET /system endpoint."""

    async def test_system_info_returns_system_info_response(self) -> None:
        """Test system_info returns SystemInfoResponse - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # Act - MANDATORY
        result = await system_info()

        # Assert - MANDATORY
        assert isinstance(result, SystemInfoResponse)

    async def test_system_info_includes_platform(self) -> None:
        """Test system_info includes platform - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # Act - MANDATORY
        result = await system_info()

        # Assert - MANDATORY
        assert result.platform is not None
        assert isinstance(result.platform, str)
        assert len(result.platform) > 0

    async def test_system_info_includes_python_version(self) -> None:
        """Test system_info includes python version - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # Act - MANDATORY
        result = await system_info()

        # Assert - MANDATORY
        assert result.python_version is not None
        assert isinstance(result.python_version, str)
        assert len(result.python_version) > 0

    async def test_system_info_includes_app_version(self) -> None:
        """Test system_info includes app version - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # Act - MANDATORY
        result = await system_info()

        # Assert - MANDATORY
        assert result.app_version is not None
        assert isinstance(result.app_version, str)
        # Should be either detected version or fallback "1.0.0"
        assert len(result.app_version) > 0

    async def test_system_info_includes_uptime(self) -> None:
        """Test system_info includes uptime - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # Act - MANDATORY
        result = await system_info()

        # Assert - MANDATORY
        assert result.uptime_seconds is not None
        assert isinstance(result.uptime_seconds, int)
        assert result.uptime_seconds >= 0

    async def test_system_info_includes_startup_time(self) -> None:
        """Test system_info includes startup time - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # Act - MANDATORY
        result = await system_info()

        # Assert - MANDATORY
        assert result.startup_time is not None
        assert isinstance(result.startup_time, datetime)

    async def test_system_info_platform_matches_system(self) -> None:
        """Test system_info platform matches platform.system() - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        expected_platform = platform.system()

        # Act - MANDATORY
        result = await system_info()

        # Assert - MANDATORY
        assert result.platform == expected_platform

    async def test_system_info_python_version_matches_sys(self) -> None:
        """Test system_info python version matches sys.version - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        expected_version = sys.version

        # Act - MANDATORY
        result = await system_info()

        # Assert - MANDATORY
        assert result.python_version == expected_version

    async def test_system_info_architecture_is_valid(self) -> None:
        """Test system_info architecture is valid - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # Act - MANDATORY
        result = await system_info()

        # Assert - MANDATORY
        assert result.architecture is not None
        assert isinstance(result.architecture, str)
        # Common architectures
        valid_architectures = ["x86_64", "arm64", "aarch64", "i386", "AMD64"]
        # Architecture should be in valid list or be a non-empty string
        assert result.architecture in valid_architectures or len(result.architecture) > 0


# ============================================================================
# Uptime Tracking Tests
# ============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
class TestUptimeTracking:
    """Tests for uptime tracking functionality."""

    async def test_uptime_increases_over_time(self) -> None:
        """Test uptime increases between calls - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # Act - MANDATORY
        result1 = await system_info()
        uptime1 = result1.uptime_seconds

        # Wait a small amount of time
        await asyncio.sleep(0.1)

        result2 = await system_info()
        uptime2 = result2.uptime_seconds

        # Assert - MANDATORY
        # Uptime should be the same or slightly higher (within 1 second tolerance)
        assert uptime2 >= uptime1

    async def test_startup_time_is_consistent(self) -> None:
        """Test startup time remains consistent - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # Act - MANDATORY
        result1 = await system_info()
        startup1 = result1.startup_time

        result2 = await system_info()
        startup2 = result2.startup_time

        # Assert - MANDATORY
        # Startup time should be the same between calls
        assert startup1 == startup2


# ============================================================================
# Integration Tests
# ============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
class TestSystemInfoIntegration:
    """Integration tests for system info endpoints."""

    async def test_system_info_endpoint_accessible(self) -> None:
        """Test system info endpoint is accessible - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # Act - MANDATORY
        result = await system_info()

        # Assert - MANDATORY
        assert result is not None
        assert isinstance(result, SystemInfoResponse)

    async def test_system_info_provides_complete_data(self) -> None:
        """Test system info provides all required data - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # Act - MANDATORY
        result = await system_info()

        # Assert - MANDATORY
        # All fields should be non-None
        assert result.platform is not None
        assert result.platform_release is not None
        assert result.platform_version is not None
        assert result.architecture is not None
        assert result.processor is not None
        assert result.python_version is not None
        assert result.python_implementation is not None
        assert result.app_version is not None
        assert result.uptime_seconds is not None
        assert result.startup_time is not None


# ============================================================================
# MANDATORY Performance Benchmarks
# ============================================================================


@pytest.mark.performance
@pytest.mark.unit
@pytest.mark.asyncio
class TestSystemInfoPerformance:
    """MANDATORY performance tests for system info endpoints."""

    async def test_system_info_endpoint_performance(self) -> None:
        """MANDATORY performance test - system info endpoint speed."""
        # Arrange - MANDATORY
        iterations = 100

        # Act - MANDATORY
        start_time = time.perf_counter()

        for _ in range(iterations):
            await system_info()

        end_time = time.perf_counter()
        execution_time = end_time - start_time

        # Assert - MANDATORY
        avg_time = execution_time / iterations
        assert avg_time < 0.01  # <10ms per call
        assert execution_time < 1.0  # Total <1s for 100 calls

    async def test_system_info_data_collection_performance(self) -> None:
        """MANDATORY performance test - system data collection speed."""
        # Arrange - MANDATORY
        iterations = 100

        # Act - MANDATORY
        start_time = time.perf_counter()

        for _ in range(iterations):
            # Simulate the data collection operations
            _ = platform.system()
            _ = platform.release()
            _ = platform.version()
            _ = platform.machine()
            _ = platform.processor()
            _ = sys.version
            _ = platform.python_implementation()

        end_time = time.perf_counter()
        execution_time = end_time - start_time

        # Assert - MANDATORY
        avg_time = execution_time / iterations
        assert avg_time < 0.005  # <5ms per collection
        assert execution_time < 0.5  # Total <500ms for 100 collections
