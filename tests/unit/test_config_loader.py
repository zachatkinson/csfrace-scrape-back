"""Tests for configuration loading functionality."""

import json
import yaml
import pytest
from pathlib import Path
from tempfile import TemporaryDirectory
from dataclasses import asdict

from src.config.loader import ConfigLoader, load_config_from_file
from src.core.config import ConverterConfig
from src.batch.processor import BatchConfig


class TestConfigLoader:
    """Test ConfigLoader functionality."""
    
    @pytest.fixture
    def temp_dir(self):
        """Provide temporary directory for tests."""
        with TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)
    
    @pytest.fixture
    def sample_config_data(self):
        """Provide sample configuration data."""
        return {
            'converter': {
                'default_timeout': 45,
                'max_concurrent_downloads': 15,
                'rate_limit_delay': 1.0,
                'user_agent': 'Test-Agent/1.0',
                'preserve_classes': ['test-class', 'another-class']
            },
            'batch': {
                'max_concurrent': 5,
                'continue_on_error': False,
                'output_base_dir': 'test_output',
                'create_archives': True,
                'cleanup_after_archive': True
            }
        }
    
    def test_load_yaml_config(self, temp_dir, sample_config_data):
        """Test loading YAML configuration file."""
        config_file = temp_dir / "test_config.yaml"
        
        with open(config_file, 'w') as f:
            yaml.dump(sample_config_data, f)
        
        loaded_config = ConfigLoader.load_config(config_file)
        
        assert loaded_config == sample_config_data
        assert loaded_config['converter']['default_timeout'] == 45
        assert loaded_config['batch']['max_concurrent'] == 5
    
    def test_load_json_config(self, temp_dir, sample_config_data):
        """Test loading JSON configuration file."""
        config_file = temp_dir / "test_config.json"
        
        with open(config_file, 'w') as f:
            json.dump(sample_config_data, f)
        
        loaded_config = ConfigLoader.load_config(config_file)
        
        assert loaded_config == sample_config_data
        assert loaded_config['converter']['user_agent'] == 'Test-Agent/1.0'
        assert loaded_config['batch']['create_archives'] is True
    
    def test_load_config_with_type_override(self, temp_dir, sample_config_data):
        """Test loading config with explicit type override."""
        # Save as .txt but specify as YAML
        config_file = temp_dir / "config.txt"
        
        with open(config_file, 'w') as f:
            yaml.dump(sample_config_data, f)
        
        loaded_config = ConfigLoader.load_config(config_file, config_type='yaml')
        
        assert loaded_config == sample_config_data
    
    def test_load_nonexistent_file(self, temp_dir):
        """Test error handling for nonexistent config file."""
        config_file = temp_dir / "nonexistent.yaml"
        
        with pytest.raises(FileNotFoundError):
            ConfigLoader.load_config(config_file)
    
    def test_load_invalid_yaml(self, temp_dir):
        """Test error handling for invalid YAML."""
        config_file = temp_dir / "invalid.yaml"
        
        with open(config_file, 'w') as f:
            f.write("invalid: yaml: content: [unclosed")
        
        with pytest.raises(ValueError, match="Invalid YAML"):
            ConfigLoader.load_config(config_file)
    
    def test_load_invalid_json(self, temp_dir):
        """Test error handling for invalid JSON."""
        config_file = temp_dir / "invalid.json"
        
        with open(config_file, 'w') as f:
            f.write('{"invalid": json, "unclosed": }')
        
        with pytest.raises(ValueError, match="Invalid JSON"):
            ConfigLoader.load_config(config_file)
    
    def test_unsupported_format(self, temp_dir):
        """Test error handling for unsupported config format."""
        config_file = temp_dir / "config.xml"
        config_file.touch()
        
        with pytest.raises(ValueError, match="Unsupported config format"):
            ConfigLoader.load_config(config_file)
    
    def test_create_converter_config_default(self):
        """Test creating ConverterConfig with default base."""
        config_dict = {
            'converter': {
                'default_timeout': 60,
                'max_retries': 5,
                'user_agent': 'Custom-Agent/2.0'
            }
        }
        
        converter_config = ConfigLoader.create_converter_config(config_dict)
        
        assert isinstance(converter_config, ConverterConfig)
        assert converter_config.default_timeout == 60
        assert converter_config.max_retries == 5
        assert converter_config.user_agent == 'Custom-Agent/2.0'
        # Should preserve other defaults
        assert converter_config.max_concurrent_downloads == 10  # default
    
    def test_create_converter_config_with_preserve_classes(self):
        """Test creating ConverterConfig with preserve_classes as list."""
        config_dict = {
            'converter': {
                'preserve_classes': ['class1', 'class2', 'class3']
            }
        }
        
        converter_config = ConfigLoader.create_converter_config(config_dict)
        
        assert isinstance(converter_config.preserve_classes, frozenset)
        assert 'class1' in converter_config.preserve_classes
        assert 'class2' in converter_config.preserve_classes
        assert 'class3' in converter_config.preserve_classes
    
    def test_create_converter_config_with_base(self):
        """Test creating ConverterConfig with custom base config."""
        base_config = ConverterConfig(
            default_timeout=30,
            max_retries=2,
            user_agent='Base-Agent/1.0'
        )
        
        config_dict = {
            'converter': {
                'default_timeout': 45,  # Override
                'max_concurrent_downloads': 20  # Override
                # max_retries should come from base
            }
        }
        
        converter_config = ConfigLoader.create_converter_config(config_dict, base_config)
        
        assert converter_config.default_timeout == 45  # Overridden
        assert converter_config.max_concurrent_downloads == 20  # Overridden
        assert converter_config.max_retries == 2  # From base
        assert converter_config.user_agent == 'Base-Agent/1.0'  # From base
    
    def test_create_batch_config_default(self):
        """Test creating BatchConfig with default base."""
        config_dict = {
            'batch': {
                'max_concurrent': 8,
                'timeout_per_job': 600,
                'create_archives': True
            }
        }
        
        batch_config = ConfigLoader.create_batch_config(config_dict)
        
        assert isinstance(batch_config, BatchConfig)
        assert batch_config.max_concurrent == 8
        assert batch_config.timeout_per_job == 600
        assert batch_config.create_archives is True
        # Should preserve other defaults
        assert batch_config.continue_on_error is True  # default
    
    def test_create_batch_config_with_path_conversion(self):
        """Test creating BatchConfig with string path conversion."""
        config_dict = {
            'batch': {
                'output_base_dir': '/custom/output/path'
            }
        }
        
        batch_config = ConfigLoader.create_batch_config(config_dict)
        
        assert isinstance(batch_config.output_base_dir, Path)
        assert batch_config.output_base_dir == Path('/custom/output/path')
    
    def test_save_example_yaml_config(self, temp_dir):
        """Test saving example YAML configuration."""
        config_file = temp_dir / "example.yaml"
        
        ConfigLoader.save_example_config(config_file, format='yaml')
        
        assert config_file.exists()
        
        # Load and verify content
        with open(config_file, 'r') as f:
            loaded_config = yaml.safe_load(f)
        
        assert 'converter' in loaded_config
        assert 'batch' in loaded_config
        assert loaded_config['converter']['default_timeout'] == 30
        assert loaded_config['batch']['max_concurrent'] == 3
        assert isinstance(loaded_config['converter']['preserve_classes'], list)
    
    def test_save_example_json_config(self, temp_dir):
        """Test saving example JSON configuration."""
        config_file = temp_dir / "example.json"
        
        ConfigLoader.save_example_config(config_file, format='json')
        
        assert config_file.exists()
        
        # Load and verify content
        with open(config_file, 'r') as f:
            loaded_config = json.load(f)
        
        assert 'converter' in loaded_config
        assert 'batch' in loaded_config
        assert loaded_config['converter']['default_timeout'] == 30
        assert loaded_config['batch']['max_concurrent'] == 3
    
    def test_save_example_config_unsupported_format(self, temp_dir):
        """Test error handling for unsupported save format."""
        config_file = temp_dir / "example.xml"
        
        with pytest.raises(ValueError, match="Unsupported format"):
            ConfigLoader.save_example_config(config_file, format='xml')
    
    def test_load_config_from_file_convenience(self, temp_dir, sample_config_data):
        """Test convenience function for loading both configs."""
        config_file = temp_dir / "test.yaml"
        
        with open(config_file, 'w') as f:
            yaml.dump(sample_config_data, f)
        
        converter_config, batch_config = load_config_from_file(config_file)
        
        assert isinstance(converter_config, ConverterConfig)
        assert isinstance(batch_config, BatchConfig)
        
        assert converter_config.default_timeout == 45
        assert batch_config.max_concurrent == 5
        assert batch_config.create_archives is True
    
    def test_empty_config_sections(self):
        """Test handling of missing or empty config sections."""
        config_dict = {
            'converter': {},
            'batch': {}
        }
        
        converter_config = ConfigLoader.create_converter_config(config_dict)
        batch_config = ConfigLoader.create_batch_config(config_dict)
        
        # Should use all defaults
        assert converter_config.default_timeout == 30  # default
        assert batch_config.max_concurrent == 3  # default
    
    def test_missing_config_sections(self):
        """Test handling of completely missing config sections."""
        config_dict = {}
        
        converter_config = ConfigLoader.create_converter_config(config_dict)
        batch_config = ConfigLoader.create_batch_config(config_dict)
        
        # Should use all defaults
        assert converter_config.default_timeout == 30  # default
        assert batch_config.max_concurrent == 3  # default
    
    def test_yml_extension_recognition(self, temp_dir, sample_config_data):
        """Test that .yml extension is recognized as YAML."""
        config_file = temp_dir / "config.yml"
        
        with open(config_file, 'w') as f:
            yaml.dump(sample_config_data, f)
        
        loaded_config = ConfigLoader.load_config(config_file)
        
        assert loaded_config == sample_config_data