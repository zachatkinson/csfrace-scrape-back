"""SSE event formatting utilities following DRY principles.

Extracted from jobs/streaming.py to eliminate code duplication across all SSE endpoints.
"""

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any


def safe_json_dumps(data: Any) -> str:
    """JSON dumps with handling for non-serializable types.

    DRY: Extracted from jobs/streaming.py to be reused by all SSE endpoints.
    Handles datetime serialization and provides clear error messages.

    Args:
        data: Any Python object to serialize to JSON

    Returns:
        JSON string representation

    Raises:
        TypeError: If object type is not JSON serializable
    """

    def default_serializer(obj: Any) -> str:
        if hasattr(obj, "isoformat"):
            result: str = obj.isoformat()
            return result
        raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

    return json.dumps(data, default=default_serializer)


@dataclass(frozen=True)
class SSEEvent:
    """Immutable SSE event structure following SOLID principles.

    Single Responsibility: Represents one SSE event with its data and metadata.
    Open/Closed: Extend via subclassing, don't modify this base class.
    """

    event_name: str
    data: dict[str, Any]
    event_id: str | None = None
    retry: int | None = None

    def format(self) -> str:
        """Format as SSE protocol string.

        Returns:
            SSE-formatted string ready to send to client
        """
        return format_sse_event(
            event_name=self.event_name,
            data=self.data,
            event_id=self.event_id,
            retry=self.retry,
        )


def format_sse_event(
    event_name: str,
    data: dict[str, Any],
    event_id: str | None = None,
    retry: int | None = None,
) -> str:
    """Format data as SSE protocol string.

    SSE Protocol Format:
        event: event_name
        data: {"key": "value"}
        id: optional_event_id
        retry: optional_retry_ms

        (blank line to signal end of event)

    Args:
        event_name: Name of the SSE event (e.g., "job-status-update", "health-update")
        data: Event payload as dictionary
        event_id: Optional event ID for client reconnection
        retry: Optional retry delay in milliseconds

    Returns:
        SSE-formatted string ready to send to client

    Examples:
        >>> format_sse_event("connection", {"status": "connected"})
        'event: connection\\ndata: {"status": "connected"}\\n\\n'
    """
    lines = []

    # Event name (required)
    lines.append(f"event: {event_name}")

    # Event data (required, must be JSON)
    lines.append(f"data: {safe_json_dumps(data)}")

    # Optional event ID (for client reconnection)
    if event_id is not None:
        lines.append(f"id: {event_id}")

    # Optional retry delay
    if retry is not None:
        lines.append(f"retry: {retry}")

    # SSE protocol requires blank line to signal end of event
    return "\n".join(lines) + "\n\n"


def format_connection_event(message: str = "Real-time connection established") -> str:
    """Format standard connection event.

    DRY: All SSE endpoints send connection events, so extract to utility.

    Args:
        message: Connection message to send to client

    Returns:
        SSE-formatted connection event
    """
    return format_sse_event(
        event_name="connection",
        data={
            "type": "connection",
            "message": message,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        },
    )


def format_keepalive_event() -> str:
    """Format standard keepalive/ping event.

    DRY: All SSE endpoints send keepalive pings, so extract to utility.

    Returns:
        SSE-formatted keepalive event
    """
    return format_sse_event(
        event_name="keepalive",
        data={
            "timestamp": datetime.utcnow().isoformat() + "Z",
        },
    )


def format_error_event(error_message: str, error_code: str | None = None) -> str:
    """Format standard error event.

    DRY: All SSE endpoints send errors, so extract to utility.

    Args:
        error_message: Human-readable error message
        error_code: Optional machine-readable error code

    Returns:
        SSE-formatted error event
    """
    data = {
        "error": error_message,
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }

    if error_code is not None:
        data["error_code"] = error_code

    return format_sse_event(event_name="error", data=data)
