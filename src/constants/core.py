"""Core application constants for PERFECT SRP compliance.

ZERO TOLERANCE for mixing domains - only core application constants here.
Single source of truth for ALL core application configuration.
"""

from enum import Enum

from src.core.environment import EnvironmentLoader

# Paths - configurable via environment
DEFAULT_OUTPUT_DIR: str = EnvironmentLoader.get_optional("OUTPUT_DIR", "converted_content")
DEFAULT_IMAGES_DIR: str = "images"  # Sub-directory name is a constant (part of app logic)

# File Names - centralized file naming (constants, not configurable)
METADATA_FILE: str = "metadata.txt"
HTML_FILE: str = "converted_content.html"
SHOPIFY_FILE: str = "shopify_ready_content.html"

# Removed system-user pattern per ZERO TOLERANCE policy

# Shopify-compatible CSS classes to preserve
SHOPIFY_PRESERVE_CLASSES: frozenset[str] = frozenset(
    [
        "center",
        "media-grid",
        "media-grid-2",
        "media-grid-4",
        "media-grid-5",
        "media-grid-text-box",
        "testimonial-quote",
        "group",
        "quote-container",
        "button",
        "button--full-width",
        "button--primary",
        "press-release-button",
    ]
)

# Content type mappings for images - immutable mapping
IMAGE_CONTENT_TYPES: dict[str, str] = {
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/gif": ".gif",
    "image/webp": ".webp",
    "image/svg+xml": ".svg",
}

# Default image extension when content type is unknown
DEFAULT_IMAGE_EXTENSION: str = ".jpg"


# Progress tracking as proper Enum
class ProgressStage(Enum):
    """Progress stages for conversion operations."""

    START = 0
    SETUP = 10
    FETCH = 20
    PROCESS = 60
    COMPLETE = 100


# Authentication types as Enum
class AuthTokenType(Enum):
    """Authentication token types."""

    BEARER = "bearer"


# Exit codes as Enum
class ExitCode(Enum):
    """Application exit codes."""

    SUCCESS = 0
    KEYBOARD_INTERRUPT = 130
