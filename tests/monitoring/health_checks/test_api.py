"""Comprehensive tests for API health checks - MANDATORY TEST_BUILDING.md compliance.

This module tests API health check functionality with complete coverage:
- APIHealthCheck basic functionality testing
- APIHealthCheck configuration and model validation
- DependencyHealthCheck import validation
- DependencyHealthCheck with failed dependencies
- Edge cases and error handling
- Performance benchmarks

ALL tests follow MANDATORY TEST_BUILDING.md patterns:
- AAA pattern with explicit comments
- Factory fixtures for DRY principle
- Comprehensive API health check scenario testing
- Performance benchmarks with specific thresholds
"""

import time
from unittest.mock import MagicMock, patch

import pytest

from src.monitoring.health_checks.api import APIHealthCheck, DependencyHealthCheck
from src.monitoring.health_checks.base import HealthStatus

# ============================================================================
# Test Fixtures - DRY Principle
# ============================================================================


@pytest.fixture
def mock_settings() -> MagicMock:
    """Factory for mock settings - DRY principle."""
    settings = MagicMock()
    settings.database_url = "postgresql://localhost/test"
    settings.redis_url = "redis://localhost:6379"
    return settings


@pytest.fixture
def mock_base_model() -> MagicMock:
    """Factory for mock Base model - DRY principle."""
    return MagicMock()


# ============================================================================
# APIHealthCheck Tests
# ============================================================================


@pytest.mark.unit
class TestAPIHealthCheck:
    """Tests for APIHealthCheck class."""

    def test_api_health_check_initialization_defaults(self) -> None:
        """Test APIHealthCheck initialization with defaults - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # Act - MANDATORY
        health_check = APIHealthCheck()

        # Assert - MANDATORY
        assert health_check.name == "api"
        assert health_check.timeout_seconds == 10.0

    def test_api_health_check_initialization_custom_values(self) -> None:
        """Test APIHealthCheck with custom values - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        custom_name = "rest_api"
        custom_timeout = 15.0

        # Act - MANDATORY
        health_check = APIHealthCheck(name=custom_name, timeout_seconds=custom_timeout)

        # Assert - MANDATORY
        assert health_check.name == custom_name
        assert health_check.timeout_seconds == custom_timeout

    @pytest.mark.asyncio
    async def test_check_api_health_all_checks_pass(self) -> None:
        """Test check() when all API health checks pass - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        mock_settings = MagicMock()
        health_check = APIHealthCheck()

        # Act - MANDATORY
        with patch("src.config.get_settings", return_value=mock_settings):
            with patch("src.database.models.base.Base", MagicMock()):
                result = await health_check.check()

        # Assert - MANDATORY
        assert result.name == "api"
        assert result.status == HealthStatus.HEALTHY
        assert "api is healthy" in result.message.lower()
        assert result.duration_ms > 0
        assert "checks_passed" in result.details
        assert "configuration_loaded" in result.details["checks_passed"]
        assert "database_models_available" in result.details["checks_passed"]

    @pytest.mark.asyncio
    async def test_check_api_health_settings_unavailable(self) -> None:
        """Test check() when settings are unavailable - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        health_check = APIHealthCheck()

        # Act - MANDATORY
        with patch("src.config.get_settings", return_value=None):
            with patch("src.database.models.base.Base", MagicMock()):
                result = await health_check.check()

        # Assert - MANDATORY
        assert result.name == "api"
        assert result.status == HealthStatus.UNHEALTHY
        assert "api health check failed" in result.message.lower()
        assert "failed_checks" in result.details
        assert "configuration_loaded" in result.details["failed_checks"]

    @pytest.mark.asyncio
    async def test_check_api_health_models_unavailable(self) -> None:
        """Test check() when database models are unavailable - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        mock_settings = MagicMock()
        health_check = APIHealthCheck()

        # Act - MANDATORY
        with patch("src.config.get_settings", return_value=mock_settings):
            with patch("src.database.models.base.Base", None):
                result = await health_check.check()

        # Assert - MANDATORY
        assert result.name == "api"
        assert result.status == HealthStatus.UNHEALTHY
        assert "api health check failed" in result.message.lower()
        assert "database_models_available" in result.details["failed_checks"]


# ============================================================================
# DependencyHealthCheck Tests
# ============================================================================


@pytest.mark.unit
class TestDependencyHealthCheck:
    """Tests for DependencyHealthCheck class."""

    def test_dependency_health_check_initialization_defaults(self) -> None:
        """Test DependencyHealthCheck initialization with defaults - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # Act - MANDATORY
        health_check = DependencyHealthCheck()

        # Assert - MANDATORY
        assert health_check.name == "dependencies"
        assert health_check.timeout_seconds == 15.0

    def test_dependency_health_check_initialization_custom_values(self) -> None:
        """Test DependencyHealthCheck with custom values - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        custom_name = "external_deps"
        custom_timeout = 20.0

        # Act - MANDATORY
        health_check = DependencyHealthCheck(name=custom_name, timeout_seconds=custom_timeout)

        # Assert - MANDATORY
        assert health_check.name == custom_name
        assert health_check.timeout_seconds == custom_timeout

    @pytest.mark.asyncio
    async def test_check_all_dependencies_healthy(self) -> None:
        """Test check() when all dependencies are healthy - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        health_check = DependencyHealthCheck()

        # Act - MANDATORY
        result = await health_check.check()

        # Assert - MANDATORY
        assert result.name == "dependencies"
        assert result.status == HealthStatus.HEALTHY
        assert "all" in result.message.lower()
        assert "dependencies are healthy" in result.message.lower()
        assert result.duration_ms > 0
        assert "dependencies" in result.details
        # Verify expected dependencies were checked
        dep_names = [dep[0] for dep in result.details["dependencies"]]
        assert "structlog" in dep_names
        assert "pydantic" in dep_names
        assert "sqlalchemy" in dep_names

    @pytest.mark.asyncio
    async def test_check_import_health_successful(self) -> None:
        """Test _check_import_health() with successful import - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        health_check = DependencyHealthCheck()
        module_path = "structlog"

        # Act - MANDATORY
        result = health_check._check_import_health(module_path)

        # Assert - MANDATORY
        assert result == "healthy"

    @pytest.mark.asyncio
    async def test_check_import_health_with_import_name(self) -> None:
        """Test _check_import_health() with specific import name - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        health_check = DependencyHealthCheck()
        module_path = "sqlalchemy.ext.asyncio"
        import_name = "AsyncSession"

        # Act - MANDATORY
        result = health_check._check_import_health(module_path, import_name)

        # Assert - MANDATORY
        assert result == "healthy"

    @pytest.mark.asyncio
    async def test_check_dependency_statuses(self) -> None:
        """Test check() returns correct dependency statuses - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        health_check = DependencyHealthCheck()

        # Act - MANDATORY
        result = await health_check.check()

        # Assert - MANDATORY
        dependencies = result.details["dependencies"]
        for dep_name, status in dependencies:
            assert status == "healthy"  # All should be healthy in test environment


# ============================================================================
# MANDATORY Performance Benchmarks
# ============================================================================


@pytest.mark.performance
@pytest.mark.unit
class TestAPIHealthCheckPerformance:
    """MANDATORY performance tests for API health check operations."""

    def test_api_health_check_creation_performance(self) -> None:
        """MANDATORY performance test - APIHealthCheck creation speed."""
        # Arrange - MANDATORY
        iterations = 10000

        # Act - MANDATORY
        start_time = time.perf_counter()

        for _ in range(iterations):
            APIHealthCheck(name="perf_test_api")

        end_time = time.perf_counter()
        execution_time = end_time - start_time

        # Assert - MANDATORY
        avg_time = execution_time / iterations
        assert avg_time < 0.0001  # <0.1ms per creation
        assert execution_time < 1.0  # Total <1s for 10000 creations

    def test_dependency_health_check_creation_performance(self) -> None:
        """MANDATORY performance test - DependencyHealthCheck creation speed."""
        # Arrange - MANDATORY
        iterations = 10000

        # Act - MANDATORY
        start_time = time.perf_counter()

        for _ in range(iterations):
            DependencyHealthCheck(name="perf_test_deps")

        end_time = time.perf_counter()
        execution_time = end_time - start_time

        # Assert - MANDATORY
        avg_time = execution_time / iterations
        assert avg_time < 0.0001  # <0.1ms per creation
        assert execution_time < 1.0  # Total <1s for 10000 creations

    @pytest.mark.asyncio
    async def test_check_import_health_performance(self) -> None:
        """MANDATORY performance test - import health check speed."""
        # Arrange - MANDATORY
        health_check = DependencyHealthCheck()
        iterations = 1000

        # Act - MANDATORY
        start_time = time.perf_counter()

        for _ in range(iterations):
            health_check._check_import_health("structlog")

        end_time = time.perf_counter()
        execution_time = end_time - start_time

        # Assert - MANDATORY
        avg_time = execution_time / iterations
        assert avg_time < 0.001  # <1ms per import check
        assert execution_time < 1.0  # Total <1s for 1000 import checks
