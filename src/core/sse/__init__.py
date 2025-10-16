"""SSE (Server-Sent Events) core module following DRY/SOLID principles.

This module provides reusable abstractions for all SSE endpoints, eliminating
code duplication and establishing unified patterns for event-driven real-time updates.
"""

from .base import BaseSSEService
from .events import SSEEvent, format_sse_event, safe_json_dumps
from .redis_publisher import RedisEventPublisher

__all__ = [
    "BaseSSEService",
    "SSEEvent",
    "format_sse_event",
    "safe_json_dumps",
    "RedisEventPublisher",
]
