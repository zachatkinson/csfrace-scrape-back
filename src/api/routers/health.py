"""Health check and monitoring API endpoints.

This module has been refactored following Single Responsibility Principle.
The original monolithic module has been split into focused components.

Import the unified router from the health package.
"""

# Import the unified router from the refactored health package
# Import metrics collector for test compatibility
# Import cache manager for test compatibility
from ...caching.manager import cache_manager
from ...monitoring.metrics import metrics_collector
from .health import router

# Export the router and metrics collector for module interface
__all__ = ["router", "metrics_collector", "cache_manager"]
