"""Configuration file loading for YAML and JSON formats."""

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any, TypedDict

import structlog
import yaml

from ..batch.processor import BatchConfig
from ..constants import CONSTANTS
from ..core.config import (
    ConverterConfig,
    HttpConfig,
    OutputConfig,
    RobotsConfig,
    ShopifyConfig,
    config,
)

# Configuration types - using Any is acceptable here for JSON/YAML flexibility
# Best practice: Use TypedDict to document expected structure while allowing Any for values
ConfigDict = dict[str, Any]


class ConverterConfigDict(TypedDict, total=False):
    """Expected structure for converter configuration dictionary.

    Using TypedDict documents the expected keys while total=False allows partial configs.
    This is the best practice for configuration - strict structure, flexible values.
    """
    # HTTP settings
    default_timeout: int
    timeout: int
    max_concurrent: int
    rate_limit_delay: float
    max_retries: int
    backoff_factor: float
    user_agent: str

    # Output settings
    default_dir: str
    images_subdir: str
    metadata_file: str
    html_file: str
    shopify_file: str

    # Behavior settings
    respect_robots_txt: bool
    preserve_classes: list[str]
    preserve_ids: list[str]


logger = structlog.get_logger(__name__)


class ConfigLoader:
    """Load and merge configuration from YAML/JSON files."""

    @staticmethod
    def load_config(config_path: str | Path, config_type: str | None = None) -> ConfigDict:
        """Load configuration from file.

        Args:
            config_path: Path to configuration file
            config_type: Optional type override ('yaml', 'json')

        Returns:
            Configuration dictionary

        Raises:
            FileNotFoundError: If config file doesn't exist
            ValueError: If config format is unsupported
        """
        config_path = Path(config_path)

        if not config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")

        # Determine file format
        file_type = config_type.lower() if config_type else config_path.suffix.lower().lstrip(".")

        # Load based on format
        if file_type in ("yaml", "yml"):
            return ConfigLoader._load_yaml(config_path)
        if file_type == "json":
            return ConfigLoader._load_json(config_path)
        raise ValueError(f"Unsupported config format: {file_type}")

    @staticmethod
    def _load_yaml(config_path: Path) -> ConfigDict:
        """Load YAML configuration file."""
        try:
            with open(config_path, encoding="utf-8") as f:
                loaded_config = yaml.safe_load(f) or {}
                logger.info(
                    "Loaded YAML config", path=str(config_path), keys=list(loaded_config.keys())
                )
                return loaded_config
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML in {config_path}: {e}") from e

    @staticmethod
    def _load_json(config_path: Path) -> ConfigDict:
        """Load JSON configuration file."""
        try:
            with open(config_path, encoding="utf-8") as f:
                loaded_config = json.load(f)
                logger.info(
                    "Loaded JSON config", path=str(config_path), keys=list(loaded_config.keys())
                )
                return loaded_config
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in {config_path}: {e}") from e

    @staticmethod
    def create_converter_config(
        config_dict: ConfigDict, base_config: ConverterConfig | None = None
    ) -> ConverterConfig:
        """Create ConverterConfig from dictionary.

        Args:
            config_dict: Configuration dictionary
            base_config: Base config to extend (defaults to global config)

        Returns:
            ConverterConfig instance
        """
        base = base_config or config

        # Get converter-specific settings
        converter_settings = config_dict.get("converter", {})

        # Create a merged flat dictionary for backwards compatibility
        merged = {}
        if base:
            # Extract current values from nested structure
            if hasattr(base, 'http'):
                merged.update(asdict(base.http))
            if hasattr(base, 'output'):
                merged.update(asdict(base.output))
            if hasattr(base, 'robots'):
                merged.update(asdict(base.robots))
            if hasattr(base, 'shopify'):
                merged.update(asdict(base.shopify))

        # Merge with new settings
        merged.update(converter_settings)

        # Map old flat structure to new nested structure
        http_config = HttpConfig(
            timeout=merged.get("default_timeout", merged.get("timeout", 30)),
            max_concurrent=merged.get("max_concurrent_downloads", merged.get("max_concurrent", 5)),
            rate_limit_delay=merged.get("rate_limit_delay", 0.5),
            max_retries=merged.get("max_retries", 3),
            backoff_factor=merged.get("backoff_factor", 2.0),
            user_agent=merged.get("user_agent", "CSFrace-Scraper/1.0")
        )

        output_config = OutputConfig(
            default_dir=merged.get("default_dir", CONSTANTS.DEFAULT_OUTPUT_DIR),
            images_subdir=merged.get("images_subdir", CONSTANTS.DEFAULT_IMAGES_DIR),
            metadata_file=merged.get("metadata_file", CONSTANTS.METADATA_FILE),
            html_file=merged.get("html_file", CONSTANTS.HTML_FILE),
            shopify_file=merged.get("shopify_file", CONSTANTS.SHOPIFY_FILE)
        )

        robots_config = RobotsConfig(
            respect_robots_txt=merged.get("respect_robots_txt", True),
            cache_duration=merged.get("robots_cache_duration", 3600)
        )

        # Handle frozenset conversion for preserve_classes
        preserve_classes = merged.get("preserve_classes", frozenset())
        if isinstance(preserve_classes, list):
            preserve_classes = frozenset(preserve_classes)

        shopify_config = ShopifyConfig(
            preserve_classes=preserve_classes,
            content_type_extensions=merged.get(
                "content_type_extensions", CONSTANTS.IMAGE_CONTENT_TYPES
            )
        )

        logger.debug("Created converter config", settings=list(converter_settings.keys()))
        return ConverterConfig(
            http=http_config,
            output=output_config,
            robots=robots_config,
            shopify=shopify_config
        )

    @staticmethod
    def create_batch_config(
        config_dict: ConfigDict, base_config: BatchConfig | None = None
    ) -> BatchConfig:
        """Create BatchConfig from dictionary.

        Args:
            config_dict: Configuration dictionary
            base_config: Base config to extend

        Returns:
            BatchConfig instance
        """
        base = base_config or BatchConfig()
        base_dict = asdict(base)

        # Merge batch-specific settings
        batch_settings = config_dict.get("batch", {})
        merged = {**base_dict, **batch_settings}

        # Handle Path fields
        if "output_base_dir" in merged and isinstance(merged["output_base_dir"], str):
            merged["output_base_dir"] = Path(merged["output_base_dir"])

        logger.debug("Created batch config", settings=list(batch_settings.keys()))
        return BatchConfig(**merged)

    @staticmethod
    def save_example_config(output_path: str | Path, file_format: str = "yaml") -> None:
        """Save an example configuration file.

        Args:
            output_path: Path to save example config
            file_format: Format to save ('yaml' or 'json')
        """
        output_path = Path(output_path)

        # Create example configuration
        example_config = {
            "converter": {
                "default_timeout": 30,
                "max_concurrent_downloads": 10,
                "rate_limit_delay": 0.5,
                "max_retries": 3,
                "backoff_factor": 2.0,
                "user_agent": "WordPress-Shopify-Converter/1.0",
                "default_output_dir": "converted_content",
                "images_subdir": "images",
                "respect_robots_txt": True,
                "robots_cache_duration": 3600,
                "preserve_classes": [
                    "center",
                    "media-grid",
                    "media-grid-2",
                    "media-grid-4",
                    "button",
                    "button--primary",
                    "testimonial-quote",
                ],
            },
            "batch": {
                "max_concurrent": 3,
                "continue_on_error": True,
                "output_base_dir": "batch_output",
                "create_summary": True,
                "skip_existing": False,
                "timeout_per_job": 300,
                "retry_failed": True,
                "max_retries": 2,
                "create_archives": False,
                "archive_format": "zip",
                "cleanup_after_archive": False,
            },
        }

        # Save in requested format
        if file_format.lower() == "yaml":
            with open(output_path, "w", encoding="utf-8") as f:
                yaml.dump(
                    example_config, f, default_flow_style=False, sort_keys=False, indent=2, width=80
                )
        elif file_format.lower() == "json":
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(example_config, f, indent=2, sort_keys=True)
        else:
            raise ValueError(f"Unsupported format: {file_format}")

        logger.info("Saved example config", path=str(output_path), format=file_format)


def load_config_from_file(config_path: str | Path) -> tuple[ConverterConfig, BatchConfig]:
    """Convenience function to load both configs from file.

    Args:
        config_path: Path to configuration file

    Returns:
        Tuple of (converter_config, batch_config)
    """
    config_dict = ConfigLoader.load_config(config_path)
    converter_config = ConfigLoader.create_converter_config(config_dict)
    batch_config = ConfigLoader.create_batch_config(config_dict)

    return converter_config, batch_config
