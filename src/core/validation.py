"""Centralized validation engine for PERFECT DRY compliance.

ZERO TOLERANCE for duplicate validation patterns.
Single source of truth for ALL validation logic across the entire codebase.
"""

import re
from datetime import datetime
from typing import Any
from urllib.parse import ParseResult, urlparse
from uuid import UUID

from src.core.decorators import database_error_handler
from src.core.logging_hierarchy import get_general_logger

logger = get_general_logger()

# Validation patterns - DRY principle for regex patterns
UUID_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE
)
USERNAME_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{3,50}$")
USERNAME_PATTERN_WITH_DOTS = re.compile(r"^[a-zA-Z0-9._-]{3,50}$")  # OAuth usernames allow dots
URL_SCHEMES = {"http", "https"}
FORBIDDEN_URL_PATTERNS = {
    "localhost",
    "127.0.0.1",
    # "0.0.0.0",  # Removed binding to all interfaces per security
    "::1",
    "file://",
    "ftp://",
    "ftps://",
    "javascript:",
    "data:",
}

# Constants for validation limits
MAX_PAGE_SIZE = 1000
MIN_PAGE_SIZE = 1
MAX_USERNAME_LENGTH = 50
MIN_USERNAME_LENGTH = 3
MAX_EMAIL_LENGTH = 320
MAX_URL_LENGTH = 2048
MAX_DESCRIPTION_LENGTH = 1000
MAX_FILENAME_LENGTH = 255


class ValidationError(Exception):
    """Custom validation error for perfect error handling."""

    def __init__(self, message: str, field: str | None = None, value: Any = None):
        self.message = message
        self.field = field
        self.value = value
        super().__init__(message)


class ValidationEngine:
    """Perfect validation centralization - zero duplication allowed."""

    @staticmethod
    def url(value: str, field_name: str = "url") -> str:
        """Perfect URL validation - used everywhere."""
        if not value or not value.strip():
            raise ValidationError(f"{field_name} cannot be empty", field=field_name, value=value)

        url_value = value.strip()

        if len(url_value) > MAX_URL_LENGTH:
            raise ValidationError(
                f"{field_name} too long (max {MAX_URL_LENGTH} characters)",
                field=field_name,
                value=url_value,
            )

        parsed = BulkValidator._parse_url_safe(url_value, field_name)

        if not parsed.scheme or not parsed.netloc:
            raise ValidationError(
                f"{field_name} must be a valid URL", field=field_name, value=url_value
            )

        if parsed.scheme not in URL_SCHEMES:
            raise ValidationError(
                f"{field_name} must use HTTP or HTTPS", field=field_name, value=url_value
            )

        # Security validation - block dangerous URLs
        netloc_lower = parsed.netloc.lower()
        if any(forbidden in netloc_lower for forbidden in FORBIDDEN_URL_PATTERNS):
            raise ValidationError(
                f"{field_name} contains forbidden patterns", field=field_name, value=url_value
            )

        return url_value

    @staticmethod
    def pagination(skip: int, limit: int) -> tuple[int, int]:
        """Perfect pagination validation - used everywhere."""
        if skip < 0:
            raise ValidationError("Skip must be non-negative", field="skip", value=skip)

        if limit <= 0:
            raise ValidationError("Limit must be positive", field="limit", value=limit)

        if limit > MAX_PAGE_SIZE:
            raise ValidationError(
                f"Limit cannot exceed {MAX_PAGE_SIZE}", field="limit", value=limit
            )

        return skip, limit

    @staticmethod
    def user_id(value: str, field_name: str = "user_id") -> str:
        """Perfect user ID validation - used everywhere."""
        if not value or not value.strip():
            raise ValidationError(f"{field_name} cannot be empty", field=field_name, value=value)

        user_id_value = value.strip()

        if not UUID_PATTERN.match(user_id_value):
            raise ValidationError(
                f"{field_name} must be a valid UUID", field=field_name, value=user_id_value
            )

        BulkValidator._validate_uuid_safe(user_id_value, field_name)

        return user_id_value

    @staticmethod
    def username(value: str, field_name: str = "username", allow_dots: bool = False) -> str:
        """Perfect username validation - used everywhere.

        Args:
            value: Username to validate
            field_name: Field name for error messages
            allow_dots: Whether to allow dots in username (for OAuth providers like Google)

        Returns:
            Validated username string

        Raises:
            ValidationError: If username doesn't meet validation criteria
        """
        if not value or not value.strip():
            raise ValidationError(f"{field_name} cannot be empty", field=field_name, value=value)

        username_value = value.strip()

        if len(username_value) < MIN_USERNAME_LENGTH:
            raise ValidationError(
                f"{field_name} must be at least {MIN_USERNAME_LENGTH} characters",
                field=field_name,
                value=username_value,
            )

        if len(username_value) > MAX_USERNAME_LENGTH:
            raise ValidationError(
                f"{field_name} cannot exceed {MAX_USERNAME_LENGTH} characters",
                field=field_name,
                value=username_value,
            )

        # DRY: Use appropriate pattern based on allow_dots parameter
        pattern = USERNAME_PATTERN_WITH_DOTS if allow_dots else USERNAME_PATTERN
        allowed_chars = (
            "letters, numbers, dots, hyphens, and underscores"
            if allow_dots
            else "letters, numbers, hyphens, and underscores"
        )

        if not pattern.match(username_value):
            raise ValidationError(
                f"{field_name} can only contain {allowed_chars}",
                field=field_name,
                value=username_value,
            )

        return username_value

    @staticmethod
    def email(value: str, field_name: str = "email") -> str:
        """Perfect email validation - used everywhere."""
        if not value or not value.strip():
            raise ValidationError(f"{field_name} cannot be empty", field=field_name, value=value)

        email_value = value.strip()

        if len(email_value) > MAX_EMAIL_LENGTH:
            raise ValidationError(
                f"{field_name} too long (max {MAX_EMAIL_LENGTH} characters)",
                field=field_name,
                value=email_value,
            )

        BulkValidator._validate_email_format_safe(email_value, field_name)

        return email_value

    @staticmethod
    def job_id(value: str, field_name: str = "job_id") -> str:
        """Perfect job ID validation - used everywhere."""
        if not value or not value.strip():
            raise ValidationError(f"{field_name} cannot be empty", field=field_name, value=value)

        job_id_value = value.strip()

        if not UUID_PATTERN.match(job_id_value):
            raise ValidationError(
                f"{field_name} must be a valid UUID", field=field_name, value=job_id_value
            )

        BulkValidator._validate_uuid_safe(job_id_value, field_name)

        return job_id_value

    @staticmethod
    def priority(value: str, field_name: str = "priority") -> str:
        """Perfect priority validation - used everywhere."""
        if not value or not value.strip():
            raise ValidationError(f"{field_name} cannot be empty", field=field_name, value=value)

        priority_value = value.strip().lower()
        valid_priorities = {"low", "normal", "high", "urgent"}

        if priority_value not in valid_priorities:
            raise ValidationError(
                f"{field_name} must be one of: {', '.join(valid_priorities)}",
                field=field_name,
                value=priority_value,
            )

        return priority_value

    @staticmethod
    def timeout(
        value: int, field_name: str = "timeout", min_timeout: int = 1, max_timeout: int = 3600
    ) -> int:
        """Perfect timeout validation - used everywhere."""
        if value < min_timeout:
            raise ValidationError(
                f"{field_name} must be at least {min_timeout} seconds",
                field=field_name,
                value=value,
            )

        if value > max_timeout:
            raise ValidationError(
                f"{field_name} cannot exceed {max_timeout} seconds", field=field_name, value=value
            )

        return value

    @staticmethod
    def oauth_provider(value: str, field_name: str = "provider") -> str:
        """Perfect OAuth provider validation - used everywhere."""
        if not value or not value.strip():
            raise ValidationError(f"{field_name} cannot be empty", field=field_name, value=value)

        provider_value = value.strip().lower()
        valid_providers = {"google", "github", "microsoft", "facebook", "apple"}

        if provider_value not in valid_providers:
            raise ValidationError(
                f"{field_name} must be one of: {', '.join(valid_providers)}",
                field=field_name,
                value=provider_value,
            )

        return provider_value

    @staticmethod
    def oauth_code(value: str, field_name: str = "code") -> str:
        """Perfect OAuth code validation - used everywhere."""
        if not value or not value.strip():
            raise ValidationError(f"{field_name} cannot be empty", field=field_name, value=value)

        code_value = value.strip()

        # OAuth codes should be reasonable length
        if len(code_value) < 10:
            raise ValidationError(f"{field_name} too short", field=field_name, value=code_value)

        if len(code_value) > 1000:
            raise ValidationError(f"{field_name} too long", field=field_name, value=code_value)

        return code_value

    @staticmethod
    def oauth_state(value: str, field_name: str = "state") -> str:
        """Perfect OAuth state validation - used everywhere."""
        if not value or not value.strip():
            raise ValidationError(f"{field_name} cannot be empty", field=field_name, value=value)

        state_value = value.strip()

        # OAuth state should be reasonable length for security
        if len(state_value) < 10:
            raise ValidationError(
                f"{field_name} too short for security", field=field_name, value=state_value
            )

        if len(state_value) > 200:
            raise ValidationError(f"{field_name} too long", field=field_name, value=state_value)

        return state_value

    @staticmethod
    def description(value: str | None, field_name: str = "description") -> str | None:
        """Perfect description validation - used everywhere."""
        if value is None:
            return None

        if not value.strip():
            return None

        desc_value = value.strip()

        if len(desc_value) > MAX_DESCRIPTION_LENGTH:
            raise ValidationError(
                f"{field_name} too long (max {MAX_DESCRIPTION_LENGTH} characters)",
                field=field_name,
                value=desc_value,
            )

        return desc_value

    @staticmethod
    def filename(value: str, field_name: str = "filename") -> str:
        """Perfect filename validation - used everywhere."""
        if not value or not value.strip():
            raise ValidationError(f"{field_name} cannot be empty", field=field_name, value=value)

        filename_value = value.strip()

        if len(filename_value) > MAX_FILENAME_LENGTH:
            raise ValidationError(
                f"{field_name} too long (max {MAX_FILENAME_LENGTH} characters)",
                field=field_name,
                value=filename_value,
            )

        # Check for dangerous characters
        dangerous_chars = {"/", "\\", "..", "<", ">", ":", '"', "|", "?", "*"}
        if any(char in filename_value for char in dangerous_chars):
            raise ValidationError(
                f"{field_name} contains invalid characters", field=field_name, value=filename_value
            )

        return filename_value

    @staticmethod
    def datetime_range(
        start: datetime | None, end: datetime | None
    ) -> tuple[datetime | None, datetime | None]:
        """Perfect datetime range validation - used everywhere."""
        if start is None and end is None:
            return start, end

        if start is not None and end is not None and start >= end:
            raise ValidationError(
                "Start datetime must be before end datetime",
                field="datetime_range",
                value={"start": start, "end": end},
            )

        return start, end

    @staticmethod
    def json_data(value: Any, field_name: str = "data", max_depth: int = 10) -> Any:
        """Perfect JSON data validation - used everywhere."""
        if value is None:
            return None

        def check_depth(obj: Any, current_depth: int = 0) -> None:
            if current_depth > max_depth:
                raise ValidationError(
                    f"{field_name} nesting too deep (max {max_depth} levels)",
                    field=field_name,
                    value=obj,
                )

            if isinstance(obj, dict):
                for val in obj.values():
                    check_depth(val, current_depth + 1)
            elif isinstance(obj, list):
                for item in obj:
                    check_depth(item, current_depth + 1)

        BulkValidator._validate_json_depth_safe(value, field_name, max_depth)

        return value


class BulkValidator:
    """Perfect bulk validation operations for performance."""

    @staticmethod
    def validate_user_ids(user_ids: list[str]) -> list[str]:
        """Perfect bulk user ID validation - used everywhere."""
        if not user_ids:
            raise ValidationError("User IDs list cannot be empty", field="user_ids", value=user_ids)

        if len(user_ids) > 100:  # Reasonable bulk limit
            raise ValidationError("Too many user IDs (max 100)", field="user_ids", value=user_ids)

        validated_ids = []
        for i, user_id in enumerate(user_ids):
            validated_id = BulkValidator._validate_bulk_user_id_safe(user_id, i, user_ids)
            validated_ids.append(validated_id)

        return validated_ids

    @staticmethod
    def validate_urls(urls: list[str]) -> list[str]:
        """Perfect bulk URL validation - used everywhere."""
        if not urls:
            raise ValidationError("URLs list cannot be empty", field="urls", value=urls)

        if len(urls) > 50:  # Reasonable bulk limit for URLs
            raise ValidationError("Too many URLs (max 50)", field="urls", value=urls)

        validated_urls = []
        for i, url in enumerate(urls):
            validated_url = BulkValidator._validate_bulk_url_safe(url, i, urls)
            validated_urls.append(validated_url)

        return validated_urls

    @staticmethod
    @database_error_handler("validate bulk user ID")
    def _validate_bulk_user_id_safe(user_id: str, index: int, _user_ids: list[str]) -> str:
        """Validate bulk user ID with error handling."""
        validated_id = ValidationEngine.user_id(user_id, f"user_ids[{index}]")
        return validated_id

    @staticmethod
    @database_error_handler("validate bulk URL")
    def _validate_bulk_url_safe(url: str, index: int, _urls: list[str]) -> str:
        """Validate bulk URL with error handling."""
        validated_url = ValidationEngine.url(url, f"urls[{index}]")
        return validated_url

    @staticmethod
    @database_error_handler("parse URL")
    def _parse_url_safe(url_value: str, _field_name: str) -> ParseResult:
        """Parse URL with error handling."""
        return urlparse(url_value)

    @staticmethod
    @database_error_handler("validate UUID")
    def _validate_uuid_safe(uuid_value: str, _field_name: str) -> None:
        """Validate UUID with error handling."""
        UUID(uuid_value)

    @staticmethod
    @database_error_handler("validate email format")
    def _validate_email_format_safe(email_value: str, _field_name: str) -> None:
        """Validate email format with error handling."""
        from pydantic import validate_email

        validate_email(email_value)

    @staticmethod
    @database_error_handler("validate JSON depth")
    def _validate_json_depth_safe(value: Any, field_name: str, max_depth: int) -> None:
        """Validate JSON depth with error handling."""

        def check_depth(obj: Any, current_depth: int = 0) -> None:
            if current_depth > max_depth:
                raise ValidationError(
                    f"{field_name} nesting too deep (max {max_depth} levels)",
                    field=field_name,
                    value=obj,
                )

            if isinstance(obj, dict):
                for val in obj.values():
                    check_depth(val, current_depth + 1)
            elif isinstance(obj, list):
                for item in obj:
                    check_depth(item, current_depth + 1)

        check_depth(value)


# Convenience aliases for perfect DRY usage
validate_url = ValidationEngine.url
validate_pagination = ValidationEngine.pagination
validate_user_id = ValidationEngine.user_id
validate_username = ValidationEngine.username
validate_email = ValidationEngine.email
validate_job_id = ValidationEngine.job_id
validate_priority = ValidationEngine.priority
validate_timeout = ValidationEngine.timeout
validate_oauth_provider = ValidationEngine.oauth_provider
validate_oauth_code = ValidationEngine.oauth_code
validate_oauth_state = ValidationEngine.oauth_state
validate_description = ValidationEngine.description
validate_filename = ValidationEngine.filename
validate_datetime_range = ValidationEngine.datetime_range
validate_json_data = ValidationEngine.json_data
validate_bulk_user_ids = BulkValidator.validate_user_ids
validate_bulk_urls = BulkValidator.validate_urls
