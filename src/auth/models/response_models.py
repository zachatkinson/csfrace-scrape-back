"""Standard API response Pydantic models following FastAPI best practices."""

from pydantic import BaseModel, Field


class MessageResponse(BaseModel):
    """Standard message response model for simple operations."""

    message: str
    status: str = "success"


class StatusResponse(BaseModel):
    """Standard status response model for health checks."""

    status: str
    uptime_seconds: int | None = Field(default=None, description="Service uptime in seconds")
