"""Configuration file loading for YAML and JSON formats."""

import json
import yaml
from pathlib import Path
from typing import Dict, Any, Optional, Union
from dataclasses import asdict

import structlog

from ..core.config import ConverterConfig
from ..batch.processor import BatchConfig

logger = structlog.get_logger(__name__)


class ConfigLoader:
    """Load and merge configuration from YAML/JSON files."""
    
    @staticmethod
    def load_config(
        config_path: Union[str, Path],
        config_type: Optional[str] = None
    ) -> Dict[str, Any]:
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
        if config_type:
            file_type = config_type.lower()
        else:
            file_type = config_path.suffix.lower().lstrip('.')
        
        # Load based on format
        if file_type in ('yaml', 'yml'):
            return ConfigLoader._load_yaml(config_path)
        elif file_type == 'json':
            return ConfigLoader._load_json(config_path)
        else:
            raise ValueError(f"Unsupported config format: {file_type}")
    
    @staticmethod
    def _load_yaml(config_path: Path) -> Dict[str, Any]:
        """Load YAML configuration file."""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f) or {}
                logger.info("Loaded YAML config", path=str(config_path), keys=list(config.keys()))
                return config
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML in {config_path}: {e}")
    
    @staticmethod
    def _load_json(config_path: Path) -> Dict[str, Any]:
        """Load JSON configuration file."""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                logger.info("Loaded JSON config", path=str(config_path), keys=list(config.keys()))
                return config
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in {config_path}: {e}")
    
    @staticmethod
    def create_converter_config(
        config_dict: Dict[str, Any],
        base_config: Optional[ConverterConfig] = None
    ) -> ConverterConfig:
        """Create ConverterConfig from dictionary.
        
        Args:
            config_dict: Configuration dictionary
            base_config: Base config to extend (defaults to global config)
            
        Returns:
            ConverterConfig instance
        """
        from ..core.config import config as default_config
        
        base = base_config or default_config
        base_dict = asdict(base)
        
        # Merge converter-specific settings
        converter_settings = config_dict.get('converter', {})
        merged = {**base_dict, **converter_settings}
        
        # Handle frozenset fields
        if 'preserve_classes' in merged and isinstance(merged['preserve_classes'], list):
            merged['preserve_classes'] = frozenset(merged['preserve_classes'])
        
        logger.debug("Created converter config", settings=list(converter_settings.keys()))
        return ConverterConfig(**merged)
    
    @staticmethod
    def create_batch_config(
        config_dict: Dict[str, Any],
        base_config: Optional[BatchConfig] = None
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
        batch_settings = config_dict.get('batch', {})
        merged = {**base_dict, **batch_settings}
        
        # Handle Path fields
        if 'output_base_dir' in merged and isinstance(merged['output_base_dir'], str):
            merged['output_base_dir'] = Path(merged['output_base_dir'])
        
        logger.debug("Created batch config", settings=list(batch_settings.keys()))
        return BatchConfig(**merged)
    
    @staticmethod
    def save_example_config(output_path: Union[str, Path], format: str = 'yaml') -> None:
        """Save an example configuration file.
        
        Args:
            output_path: Path to save example config
            format: Format to save ('yaml' or 'json')
        """
        output_path = Path(output_path)
        
        # Create example configuration
        example_config = {
            'converter': {
                'default_timeout': 30,
                'max_concurrent_downloads': 10,
                'rate_limit_delay': 0.5,
                'max_retries': 3,
                'backoff_factor': 2.0,
                'user_agent': 'WordPress-Shopify-Converter/1.0',
                'default_output_dir': 'converted_content',
                'images_subdir': 'images',
                'respect_robots_txt': True,
                'robots_cache_duration': 3600,
                'preserve_classes': [
                    'center', 'media-grid', 'media-grid-2', 'media-grid-4',
                    'button', 'button--primary', 'testimonial-quote'
                ]
            },
            'batch': {
                'max_concurrent': 3,
                'continue_on_error': True,
                'output_base_dir': 'batch_output',
                'create_summary': True,
                'skip_existing': False,
                'timeout_per_job': 300,
                'retry_failed': True,
                'max_retries': 2,
                'create_archives': False,
                'archive_format': 'zip',
                'cleanup_after_archive': False
            }
        }
        
        # Save in requested format
        if format.lower() == 'yaml':
            with open(output_path, 'w', encoding='utf-8') as f:
                yaml.dump(
                    example_config,
                    f,
                    default_flow_style=False,
                    sort_keys=False,
                    indent=2,
                    width=80
                )
        elif format.lower() == 'json':
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(example_config, f, indent=2, sort_keys=True)
        else:
            raise ValueError(f"Unsupported format: {format}")
        
        logger.info("Saved example config", path=str(output_path), format=format)


def load_config_from_file(
    config_path: Union[str, Path]
) -> tuple[ConverterConfig, BatchConfig]:
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