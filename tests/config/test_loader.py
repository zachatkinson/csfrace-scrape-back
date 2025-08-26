"""Unit tests for configuration loader module."""

import json
from pathlib import Path
from unittest.mock import mock_open, patch

import pytest
import yaml

from src.batch.processor import BatchConfig
from src.config.loader import ConfigLoader, load_config_from_file
from src.core.config import ConverterConfig


class TestConfigLoader:
    """Test configuration loading functionality."""

    @pytest.fixture
    def sample_yaml_config(self):
        """Sample YAML configuration for testing."""
        return """
converter:
  default_timeout: 30
  max_concurrent_downloads: 10
  rate_limit_delay: 0.5
  preserve_classes:
    - "center"
    - "button"

batch:
  max_concurrent: 3
  continue_on_error: true
  output_base_dir: "test_output"
  timeout_per_job: 300
        """

    @pytest.fixture
    def sample_json_config(self):
        """Sample JSON configuration for testing."""
        return {
            "converter": {
                "default_timeout": 30,
                "max_concurrent_downloads": 10,
                "rate_limit_delay": 0.5,
                "preserve_classes": ["center", "button"],
            },
            "batch": {
                "max_concurrent": 3,
                "continue_on_error": True,
                "output_base_dir": "test_output",
                "timeout_per_job": 300,
            },
        }

    def test_load_yaml_config(self, sample_yaml_config):
        """Test loading YAML configuration."""
        with patch("builtins.open", mock_open(read_data=sample_yaml_config)):
            with patch("pathlib.Path.exists", return_value=True):
                config = ConfigLoader.load_config("config.yaml")

        assert config["converter"]["default_timeout"] == 30
        assert config["batch"]["max_concurrent"] == 3
        assert config["converter"]["preserve_classes"] == ["center", "button"]

    def test_load_json_config(self, sample_json_config):
        """Test loading JSON configuration."""
        json_content = json.dumps(sample_json_config)
        with patch("builtins.open", mock_open(read_data=json_content)):
            with patch("pathlib.Path.exists", return_value=True):
                config = ConfigLoader.load_config("config.json")

        assert config["converter"]["default_timeout"] == 30
        assert config["batch"]["max_concurrent"] == 3
        assert config["converter"]["preserve_classes"] == ["center", "button"]

    def test_load_missing_file(self):
        """Test loading missing configuration file."""
        with pytest.raises(FileNotFoundError):
            ConfigLoader.load_config("missing.yaml")

    def test_load_invalid_yaml(self):
        """Test loading invalid YAML configuration."""
        invalid_yaml = "invalid: yaml: content: [unclosed"

        with patch("builtins.open", mock_open(read_data=invalid_yaml)):
            with patch("pathlib.Path.exists", return_value=True):
                with pytest.raises(ValueError, match="Invalid YAML"):
                    ConfigLoader.load_config("invalid.yaml")

    def test_load_invalid_json(self):
        """Test loading invalid JSON configuration."""
        invalid_json = '{"invalid": json, "content":}'

        with patch("builtins.open", mock_open(read_data=invalid_json)):
            with patch("pathlib.Path.exists", return_value=True):
                with pytest.raises(ValueError, match="Invalid JSON"):
                    ConfigLoader.load_config("invalid.json")

    def test_unsupported_config_format(self):
        """Test loading unsupported configuration format."""
        with patch("pathlib.Path.exists", return_value=True):
            with pytest.raises(ValueError, match="Unsupported config format"):
                ConfigLoader.load_config("config.ini")

    def test_create_converter_config(self, sample_json_config):
        """Test creating ConverterConfig from dictionary."""
        converter_config = ConfigLoader.create_converter_config(sample_json_config)

        assert isinstance(converter_config, ConverterConfig)
        assert converter_config.default_timeout == 30
        assert converter_config.max_concurrent_downloads == 10
        assert converter_config.rate_limit_delay == 0.5
        assert "center" in converter_config.preserve_classes
        assert "button" in converter_config.preserve_classes

    def test_create_batch_config(self, sample_json_config):
        """Test creating BatchConfig from dictionary."""
        batch_config = ConfigLoader.create_batch_config(sample_json_config)

        assert isinstance(batch_config, BatchConfig)
        assert batch_config.max_concurrent == 3
        assert batch_config.continue_on_error is True
        assert batch_config.output_base_dir == Path("test_output")
        assert batch_config.timeout_per_job == 300

    def test_save_example_config_yaml(self, tmp_path):
        """Test saving example configuration in YAML format."""
        output_file = tmp_path / "example.yaml"

        ConfigLoader.save_example_config(output_file, "yaml")

        assert output_file.exists()
        with open(output_file) as f:
            config = yaml.safe_load(f)

        assert "converter" in config
        assert "batch" in config
        assert config["converter"]["default_timeout"] == 30
        assert config["batch"]["max_concurrent"] == 3

    def test_save_example_config_json(self, tmp_path):
        """Test saving example configuration in JSON format."""
        output_file = tmp_path / "example.json"

        ConfigLoader.save_example_config(output_file, "json")

        assert output_file.exists()
        with open(output_file) as f:
            config = json.load(f)

        assert "converter" in config
        assert "batch" in config
        assert config["converter"]["default_timeout"] == 30
        assert config["batch"]["max_concurrent"] == 3

    def test_save_example_config_unsupported_format(self, tmp_path):
        """Test saving example config with unsupported format."""
        output_file = tmp_path / "example.ini"

        with pytest.raises(ValueError, match="Unsupported format"):
            ConfigLoader.save_example_config(output_file, "ini")

    def test_frozenset_handling_in_converter_config(self):
        """Test that preserve_classes list is converted to frozenset."""
        config_dict = {"converter": {"preserve_classes": ["class1", "class2", "class3"]}}

        converter_config = ConfigLoader.create_converter_config(config_dict)

        assert isinstance(converter_config.preserve_classes, frozenset)
        assert "class1" in converter_config.preserve_classes
        assert "class2" in converter_config.preserve_classes
        assert "class3" in converter_config.preserve_classes


class TestLoadConfigFromFile:
    """Test the convenience function for loading both configs."""

    @pytest.fixture
    def complete_config_yaml(self):
        """Complete configuration for testing."""
        return """
converter:
  default_timeout: 45
  max_concurrent_downloads: 15
  rate_limit_delay: 1.0
  preserve_classes:
    - "custom-class"
    - "special-button"

batch:
  max_concurrent: 5
  continue_on_error: false
  output_base_dir: "batch_test"
  timeout_per_job: 600
        """

    def test_load_config_from_file(self, complete_config_yaml):
        """Test loading both converter and batch configs from file."""
        with patch("builtins.open", mock_open(read_data=complete_config_yaml)):
            with patch("pathlib.Path.exists", return_value=True):
                converter_config, batch_config = load_config_from_file("complete.yaml")

        # Test converter config
        assert isinstance(converter_config, ConverterConfig)
        assert converter_config.default_timeout == 45
        assert converter_config.max_concurrent_downloads == 15
        assert converter_config.rate_limit_delay == 1.0
        assert "custom-class" in converter_config.preserve_classes
        assert "special-button" in converter_config.preserve_classes

        # Test batch config
        assert isinstance(batch_config, BatchConfig)
        assert batch_config.max_concurrent == 5
        assert batch_config.continue_on_error is False
        assert batch_config.output_base_dir == Path("batch_test")
        assert batch_config.timeout_per_job == 600
