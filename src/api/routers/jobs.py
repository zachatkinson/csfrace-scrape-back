"""Job management API endpoints.

This module has been refactored following Single Responsibility Principle.
The original monolithic module has been split into focused components.

Import the unified router from the jobs package.
"""

# Import the unified router from the refactored jobs package
from .jobs import router

# Export the router for module interface
__all__ = ["router"]
