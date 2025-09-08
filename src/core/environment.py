"""Centralized environment variable loading with validation."""

import os


class EnvironmentLoader:
    """Centralized, secure environment variable loader.

    Eliminates DRY violations and provides consistent validation
    for environment variable access across the application.
    """

    @staticmethod
    def get_required(key: str, description: str = "") -> str:
        """Get a required environment variable.

        Args:
            key: Environment variable name
            description: Human-readable description for error messages

        Returns:
            Environment variable value

        Raises:
            ValueError: If environment variable is not set or empty
        """
        value = os.environ.get(key, "").strip()
        if not value:
            error_msg = f"Required environment variable '{key}' not set"
            if description:
                error_msg += f" ({description})"
            raise ValueError(error_msg)
        return value

    @staticmethod
    def get_optional(key: str, default: str = "", description: str = "") -> str:  # noqa: ARG004
        """Get an optional environment variable with default.

        Args:
            key: Environment variable name
            default: Default value if not set
            description: Human-readable description for logging

        Returns:
            Environment variable value or default
        """
        return os.environ.get(key, default).strip()

    @staticmethod
    def get_int(
        key: str, default: int, min_value: int | None = None, max_value: int | None = None
    ) -> int:
        """Get an integer environment variable with validation.

        Args:
            key: Environment variable name
            default: Default value if not set
            min_value: Minimum allowed value
            max_value: Maximum allowed value

        Returns:
            Integer value

        Raises:
            ValueError: If value cannot be converted to int or is out of range
        """
        value_str = os.environ.get(key, str(default)).strip()

        try:
            value = int(value_str)
        except ValueError:
            raise ValueError(f"Environment variable '{key}' must be an integer, got: {value_str}")

        if min_value is not None and value < min_value:
            raise ValueError(f"Environment variable '{key}' must be >= {min_value}, got: {value}")

        if max_value is not None and value > max_value:
            raise ValueError(f"Environment variable '{key}' must be <= {max_value}, got: {value}")

        return value

    @staticmethod
    def get_bool(key: str, default: bool = False) -> bool:
        """Get a boolean environment variable.

        Args:
            key: Environment variable name
            default: Default value if not set

        Returns:
            Boolean value (True for 'true', '1', 'yes', 'on')
        """
        value_str = os.environ.get(key, str(default)).strip().lower()
        return value_str in ("true", "1", "yes", "on")

    @staticmethod
    def get_url(key: str, default: str = "", required: bool = False) -> str:
        """Get a URL environment variable with basic validation.

        Args:
            key: Environment variable name
            default: Default URL if not set
            required: Whether URL is required

        Returns:
            Valid URL string

        Raises:
            ValueError: If URL is required but not provided or invalid
        """
        value = os.environ.get(key, default).strip()

        if required and not value:
            raise ValueError(f"Required URL environment variable '{key}' not set")

        if value and not (value.startswith("http://") or value.startswith("https://")):
            raise ValueError(f"Environment variable '{key}' must be a valid URL, got: {value}")

        return value

    @staticmethod
    def get_list(key: str, default: list[str] | None = None, separator: str = ",") -> list[str]:
        """Get a comma-separated list from environment variable.

        Args:
            key: Environment variable name
            default: Default list if not set
            separator: Character to split on

        Returns:
            List of strings
        """
        if default is None:
            default = []

        value = os.environ.get(key, "").strip()
        if not value:
            return default

        return [item.strip() for item in value.split(separator) if item.strip()]


class EnvironmentValidator:
    """Validates environment configuration at startup."""

    @staticmethod
    def validate_required_vars(required_vars: dict[str, str]) -> list[str]:
        """Validate that all required environment variables are set.

        Args:
            required_vars: Dict of {var_name: description}

        Returns:
            List of missing variables
        """
        missing = []

        for var_name, description in required_vars.items():
            value = os.environ.get(var_name, "").strip()
            if not value:
                missing.append(f"{var_name} ({description})")

        return missing

    @staticmethod
    def validate_startup_environment() -> None:
        """Validate critical environment variables at application startup.

        Raises:
            RuntimeError: If critical environment variables are missing
        """
        required_vars = {
            "SECRET_KEY": "Application secret key for security",
            "DATABASE_URL": "Database connection URL",
        }

        missing = EnvironmentValidator.validate_required_vars(required_vars)

        if missing:
            error_msg = "Missing required environment variables:\n" + "\n".join(
                f"  - {var}" for var in missing
            )
            raise RuntimeError(error_msg)
