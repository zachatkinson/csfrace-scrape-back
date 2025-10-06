"""Configuration file loading for YAML and JSON formats."""

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any, TypedDict, cast

import yaml

from src.core.decorators import content_processing_error_handler
from src.core.logging_hierarchy import get_core_logger

from ..batch.processor import BatchConfig
from ..constants import (
    DEFAULT_IMAGES_DIR,
    DEFAULT_OUTPUT_DIR,
    HTML_FILE,
    METADATA_FILE,
    SHOPIFY_FILE,
)
from .converter import ConverterConfig

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


logger = get_core_logger()


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
    @content_processing_error_handler("load YAML config")
    def _load_yaml(config_path: Path) -> ConfigDict:
        """Load YAML configuration file."""
        with open(config_path, encoding="utf-8") as f:
            loaded_config = yaml.safe_load(f) or {}
            logger.info(
                "Loaded YAML config", path=str(config_path), keys=list(loaded_config.keys())
            )
            return loaded_config

    @staticmethod
    @content_processing_error_handler("load JSON config")
    def _load_json(config_path: Path) -> ConfigDict:
        """Load JSON configuration file."""
        with open(config_path, encoding="utf-8") as f:
            loaded_config_raw = json.load(f)
            loaded_config: ConfigDict = (
                loaded_config_raw if isinstance(loaded_config_raw, dict) else {}
            )
            logger.info(
                "Loaded JSON config", path=str(config_path), keys=list(loaded_config.keys())
            )
            return loaded_config

    @staticmethod
    def create_converter_config(
        config_dict: ConfigDict, base_config: ConverterConfig | None = None
    ) -> ConverterConfig:
        """Create ConverterConfig from dictionary.

        Args:
            config_dict: Configuration dictionary
            base_config: Base config to extend

        Returns:
            ConverterConfig instance
        """
        base = base_config or ConverterConfig(
            debug_mode=False, log_level="INFO", enable_metrics=True
        )

        # Get converter-specific settings
        converter_settings = config_dict.get("converter", {})

        # Create a merged dictionary from base config
        merged = {}
        if base:
            # Extract current values from base config
            merged.update(
                {
                    "default_timeout": base.http.timeout,
                    "max_concurrent": base.http.max_concurrent,
                    "rate_limit_delay": base.http.rate_limit_delay,
                    "max_retries": base.http.max_retries,
                    "backoff_factor": base.http.backoff_factor,
                    "user_agent": base.http.user_agent,
                    "default_dir": base.output.default_dir,
                    "images_subdir": base.output.images_subdir,
                    "metadata_file": base.output.metadata_file,
                    "html_file": base.output.html_file,
                    "shopify_file": base.output.shopify_file,
                    "respect_robots_txt": base.robots.respect_robots_txt,
                    "robots_cache_duration": base.robots.cache_duration,
                }
            )

        # Merge with new settings (but handle preserve_classes specially)
        converter_settings_copy = converter_settings.copy()
        preserve_classes_override = converter_settings_copy.pop("preserve_classes", None)
        merged.update(converter_settings_copy)

        # Create ConverterConfig with values from merged dict
        converter_config = ConverterConfig(debug_mode=False, log_level="INFO", enable_metrics=True)

        # Update HTTP settings
        converter_config.http.timeout = cast(
            "int", merged.get("default_timeout", merged.get("timeout", 30))
        )
        converter_config.http.max_concurrent = cast(
            "int", merged.get("max_concurrent_downloads", merged.get("max_concurrent", 5))
        )
        converter_config.http.rate_limit_delay = cast("float", merged.get("rate_limit_delay", 0.5))
        converter_config.http.max_retries = cast("int", merged.get("max_retries", 3))
        converter_config.http.backoff_factor = cast("float", merged.get("backoff_factor", 2.0))
        converter_config.http.user_agent = cast(
            "str", merged.get("user_agent", "CSFrace-Scraper/1.0")
        )

        # Update Output settings
        converter_config.output.default_dir = cast(
            "str", merged.get("default_dir", DEFAULT_OUTPUT_DIR)
        )
        converter_config.output.images_subdir = cast(
            "str", merged.get("images_subdir", DEFAULT_IMAGES_DIR)
        )
        converter_config.output.metadata_file = cast(
            "str", merged.get("metadata_file", METADATA_FILE)
        )
        converter_config.output.html_file = cast("str", merged.get("html_file", HTML_FILE))
        converter_config.output.shopify_file = cast("str", merged.get("shopify_file", SHOPIFY_FILE))

        # Update Robots settings
        converter_config.robots.respect_robots_txt = cast(
            "bool", merged.get("respect_robots_txt", True)
        )
        converter_config.robots.cache_duration = cast(
            "int", merged.get("robots_cache_duration", 3600)
        )

        # Handle preserve_classes specially
        if preserve_classes_override is not None and isinstance(preserve_classes_override, list):
            converter_config.shopify.preserve_classes = preserve_classes_override

        # Update content type extensions if provided
        content_type_extensions = merged.get("content_type_extensions")
        if content_type_extensions and isinstance(content_type_extensions, dict):
            converter_config.shopify.content_type_extensions = dict(content_type_extensions)

        logger.debug("Created converter config", settings=list(converter_settings.keys()))
        return converter_config

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
