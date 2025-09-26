"""Health check and monitoring API endpoints.

This module has been refactored following Single Responsibility Principle.
The original monolithic module has been split into focused components.

Import the unified router from the health package.
"""

# Import the unified router from the refactored health package
from .health import router

# Export the router for backward compatibility
__all__ = ["router"]
