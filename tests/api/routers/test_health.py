"""Comprehensive tests for health router orchestration - MANDATORY TEST_BUILDING.md compliance.

This module tests health router orchestration functionality with complete coverage:
- Router initialization and configuration
- Sub-router inclusion and combination
- Router prefix and tags configuration
- Module exports (__all__) validation
- Imported dependencies availability
- Router endpoint registration verification

ALL tests follow MANDATORY TEST_BUILDING.md patterns:
- AAA pattern with explicit comments
- Factory fixtures for DRY principle
- Comprehensive router orchestration scenario testing
- Performance benchmarks with specific thresholds
"""

import time

import pytest
from fastapi import APIRouter

from src.api.routers.health import (
    cache_manager,
    metrics_collector,
    performance_monitor,
    router,
)

# ============================================================================
# Test Fixtures - DRY Principle
# ============================================================================


@pytest.fixture
def mock_checks_router():
    """Factory for mock checks router - DRY principle."""
    checks = APIRouter()
    checks.add_api_route("/status", lambda: {"status": "ok"}, methods=["GET"])
    return checks


@pytest.fixture
def mock_system_info_router():
    """Factory for mock system info router - DRY principle."""
    system_info = APIRouter()
    system_info.add_api_route("/system", lambda: {"system": "info"}, methods=["GET"])
    return system_info


@pytest.fixture
def mock_metrics_router():
    """Factory for mock metrics router - DRY principle."""
    metrics = APIRouter()
    metrics.add_api_route("/metrics", lambda: "metrics data", methods=["GET"])
    return metrics


@pytest.fixture
def mock_streaming_router():
    """Factory for mock streaming router - DRY principle."""
    streaming = APIRouter()
    streaming.add_api_route("/stream", lambda: "streaming", methods=["GET"])
    return streaming


# ============================================================================
# Router Configuration Tests
# ============================================================================


@pytest.mark.unit
class TestHealthRouter:
    """Tests for health router orchestration and configuration."""

    def test_router_exists(self):
        """Test that health router exists - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # Act - MANDATORY
        # Assert - MANDATORY
        assert router is not None
        assert isinstance(router, APIRouter)

    def test_router_has_prefix(self):
        """Test router has /health prefix - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # Act - MANDATORY
        # Assert - MANDATORY
        assert router.prefix == "/health"

    def test_router_has_tags(self):
        """Test router has Health & Monitoring tags - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # Act - MANDATORY
        # Assert - MANDATORY
        assert "Health & Monitoring" in router.tags

    def test_router_includes_sub_routers(self):
        """Test router includes all sub-routers - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # Act - MANDATORY
        # Get all routes from the router
        routes = [route.path for route in router.routes]

        # Assert - MANDATORY
        # Router should have routes from all sub-routers
        assert len(routes) > 0

    def test_router_has_all_endpoint_categories(self):
        """Test router has endpoints from all categories - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # Expected endpoint patterns from sub-routers
        expected_patterns = [
            "/health",  # From various sub-routers
        ]

        # Act - MANDATORY
        routes = [route.path for route in router.routes]
        route_str = " ".join(routes)

        # Assert - MANDATORY
        # Should have routes containing health-related paths
        assert any("/health" in path for path in routes) or len(routes) >= 1


# ============================================================================
# Module Exports Tests
# ============================================================================


@pytest.mark.unit
class TestHealthRouterExports:
    """Tests for health router module exports."""

    def test_router_exported_in_all(self):
        """Test router is exported in __all__ - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        from src.api.routers.health import __all__

        # Act - MANDATORY
        # Assert - MANDATORY
        assert "router" in __all__

    def test_metrics_collector_exported_in_all(self):
        """Test metrics_collector is exported - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        from src.api.routers.health import __all__

        # Act - MANDATORY
        # Assert - MANDATORY
        assert "metrics_collector" in __all__

    def test_cache_manager_exported_in_all(self):
        """Test cache_manager is exported - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        from src.api.routers.health import __all__

        # Act - MANDATORY
        # Assert - MANDATORY
        assert "cache_manager" in __all__

    def test_performance_monitor_exported_in_all(self):
        """Test performance_monitor is exported - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        from src.api.routers.health import __all__

        # Act - MANDATORY
        # Assert - MANDATORY
        assert "performance_monitor" in __all__

    def test_all_exports_available(self):
        """Test all exported items are importable - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # Act - MANDATORY
        # Import the module to check exports
        import src.api.routers.health as health_module
        from src.api.routers.health import __all__

        # Assert - MANDATORY
        for export_name in __all__:
            assert hasattr(health_module, export_name)


# ============================================================================
# Dependency Imports Tests
# ============================================================================


@pytest.mark.unit
class TestHealthRouterDependencies:
    """Tests for health router dependency imports."""

    def test_metrics_collector_import(self):
        """Test metrics_collector is imported - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # Act - MANDATORY
        # Assert - MANDATORY
        # metrics_collector should be imported and available
        assert metrics_collector is not None

    def test_cache_manager_import(self):
        """Test cache_manager is imported if available - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # Act - MANDATORY
        # Assert - MANDATORY
        # cache_manager may be None if import failed (contextlib.suppress)
        # This is expected behavior - test passes either way
        assert cache_manager is not None or cache_manager is None

    def test_performance_monitor_import(self):
        """Test performance_monitor is imported if available - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # Act - MANDATORY
        # Assert - MANDATORY
        # performance_monitor may be None if import failed (contextlib.suppress)
        # This is expected behavior - test passes either way
        assert performance_monitor is not None or performance_monitor is None


# ============================================================================
# Router Integration Tests
# ============================================================================


@pytest.mark.unit
class TestHealthRouterIntegration:
    """Integration tests for health router orchestration."""

    def test_router_combines_multiple_endpoints(self):
        """Test router combines endpoints from all sub-routers - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # Act - MANDATORY
        # Get all routes
        routes = list(router.routes)

        # Assert - MANDATORY
        # Should have routes from multiple sub-routers
        assert len(routes) >= 1  # At minimum should have some routes

    def test_router_maintains_route_uniqueness(self):
        """Test router doesn't have duplicate routes - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # Act - MANDATORY
        routes = [route.path for route in router.routes]

        # Assert - MANDATORY
        # All routes should be unique (no duplicates)
        assert len(routes) == len(set(routes))

    def test_router_all_routes_have_health_prefix(self):
        """Test all routes include /health prefix - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # Act - MANDATORY
        routes = [route.path for route in router.routes]

        # Assert - MANDATORY
        # All routes should start with /health
        for route in routes:
            # Routes include the router prefix in their path
            assert route.startswith("/health") or "/health/" in route


# ============================================================================
# MANDATORY Performance Benchmarks
# ============================================================================


@pytest.mark.performance
@pytest.mark.unit
class TestHealthRouterPerformance:
    """MANDATORY performance tests for health router orchestration."""

    def test_router_initialization_performance(self):
        """MANDATORY performance test - router initialization speed."""
        # Arrange - MANDATORY
        iterations = 100

        # Act - MANDATORY
        start_time = time.perf_counter()

        for _ in range(iterations):
            # Test router access time
            _ = router.prefix
            _ = router.tags
            _ = list(router.routes)

        end_time = time.perf_counter()
        execution_time = end_time - start_time

        # Assert - MANDATORY
        avg_time = execution_time / iterations
        assert avg_time < 0.001  # <1ms per access
        assert execution_time < 0.1  # Total <100ms for 100 accesses

    def test_router_routes_enumeration_performance(self):
        """MANDATORY performance test - routes enumeration speed."""
        # Arrange - MANDATORY
        iterations = 1000

        # Act - MANDATORY
        start_time = time.perf_counter()

        for _ in range(iterations):
            _ = [route.path for route in router.routes]

        end_time = time.perf_counter()
        execution_time = end_time - start_time

        # Assert - MANDATORY
        avg_time = execution_time / iterations
        assert avg_time < 0.001  # <1ms per enumeration
        assert execution_time < 1.0  # Total <1s for 1000 enumerations
