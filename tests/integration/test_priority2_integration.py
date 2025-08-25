"""Integration tests for Priority 2 features working together."""

from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from src.batch.processor import BatchConfig, BatchProcessor
from src.caching.base import CacheBackend, CacheConfig
from src.caching.manager import CacheManager
from src.config.loader import ConfigLoader
from src.plugins.manager import PluginManager
from src.plugins.registry import PluginRegistry


class TestPriority2Integration:
    """Test Priority 2 features working together."""

    @pytest.fixture
    def temp_dir(self):
        """Provide temporary directory for tests."""
        with TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)

    @pytest.mark.asyncio
    async def test_batch_with_config_and_caching(self, temp_dir):
        """Test batch processing with configuration files and caching."""

        # Create configuration file
        config_data = {
            "converter": {
                "default_timeout": 60,
                "max_concurrent_downloads": 5,
                "rate_limit_delay": 0.1,
            },
            "batch": {
                "max_concurrent": 2,
                "create_archives": True,
                "cleanup_after_archive": False,
                "output_base_dir": str(temp_dir / "batch_output"),
            },
        }

        config_file = temp_dir / "test_config.yaml"
        import yaml

        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        # Load configuration
        converter_config, batch_config = ConfigLoader.create_converter_config(
            config_data
        ), ConfigLoader.create_batch_config(config_data)

        # Verify config loaded correctly
        assert converter_config.default_timeout == 60
        assert converter_config.max_concurrent_downloads == 5
        assert batch_config.max_concurrent == 2
        assert batch_config.create_archives is True
        assert str(batch_config.output_base_dir) == str(temp_dir / "batch_output")

        # Set up caching
        cache_config = CacheConfig(
            backend=CacheBackend.FILE, cache_dir=temp_dir / "cache", ttl_html=1800
        )
        cache_manager = CacheManager(cache_config)
        await cache_manager.initialize()

        # Test caching works
        test_url = "https://example.com/test-post"
        test_html = "<html><body><h1>Test Post</h1></body></html>"

        await cache_manager.set_html(test_url, test_html)
        cached_html = await cache_manager.get_html(test_url)
        assert cached_html == test_html

        # Set up batch processor
        processor = BatchProcessor(batch_config)

        # Add jobs
        job1 = processor.add_job("https://example.com/post1", custom_slug="first-post")
        job2 = processor.add_job("https://example.com/post2", custom_slug="second-post")

        assert len(processor.jobs) == 2
        assert "first-post" in str(job1.output_dir)
        assert "second-post" in str(job2.output_dir)

        await cache_manager.shutdown()

    def test_config_generation_and_loading_cycle(self, temp_dir):
        """Test generating config, modifying it, and loading it back."""

        # Generate example config
        yaml_config = temp_dir / "example.yaml"
        json_config = temp_dir / "example.json"

        ConfigLoader.save_example_config(yaml_config, format="yaml")
        ConfigLoader.save_example_config(json_config, format="json")

        # Verify files were created
        assert yaml_config.exists()
        assert json_config.exists()

        # Load YAML config
        yaml_data = ConfigLoader.load_config(yaml_config)
        assert "converter" in yaml_data
        assert "batch" in yaml_data

        # Load JSON config
        json_data = ConfigLoader.load_config(json_config)
        assert "converter" in json_data
        assert "batch" in json_data

        # Both should have same structure (different formatting)
        assert yaml_data.keys() == json_data.keys()
        assert (
            yaml_data["converter"]["default_timeout"] == json_data["converter"]["default_timeout"]
        )

        # Modify config and reload
        yaml_data["converter"]["default_timeout"] = 120
        yaml_data["batch"]["max_concurrent"] = 8

        import yaml

        with open(yaml_config, "w") as f:
            yaml.dump(yaml_data, f)

        # Create configs from modified data
        converter_config = ConfigLoader.create_converter_config(yaml_data)
        batch_config = ConfigLoader.create_batch_config(yaml_data)

        assert converter_config.default_timeout == 120
        assert batch_config.max_concurrent == 8

    @pytest.mark.asyncio
    async def test_cache_and_plugin_integration(self, temp_dir):
        """Test caching system with plugin system."""

        # Set up caching
        cache_config = CacheConfig(backend=CacheBackend.FILE, cache_dir=temp_dir / "cache")
        cache = CacheManager(cache_config)
        await cache.initialize()

        # Set up plugin registry
        registry = PluginRegistry()
        manager = PluginManager(registry)

        # Test that both systems can coexist
        test_url = "https://example.com/plugin-test"
        test_html = "<html><body>Plugin test content</body></html>"
        test_metadata = {"title": "Plugin Test", "extracted_by": "test_plugin"}

        # Cache content that would be processed by plugins
        await cache.set_html(test_url, test_html)
        await cache.set_metadata(test_url, test_metadata)

        # Verify cached content
        cached_html = await cache.get_html(test_url)
        cached_metadata = await cache.get_metadata(test_url)

        assert cached_html == test_html
        assert cached_metadata == test_metadata
        assert cached_metadata["extracted_by"] == "test_plugin"

        await cache.shutdown()
        await manager.shutdown()

    def test_batch_csv_with_custom_config(self, temp_dir):
        """Test batch processing with CSV input and custom configuration."""

        # Create CSV file with structured data
        csv_file = temp_dir / "batch_jobs.csv"
        csv_content = """url,slug,output_dir,priority
https://example.com/blog/first-post,custom-first,custom/first,1
https://example.com/blog/second-post,custom-second,,2
https://example.com/blog/third-post,,,3
"""

        with open(csv_file, "w") as f:
            f.write(csv_content)

        # Custom batch config
        batch_config = BatchConfig(
            max_concurrent=3,
            output_base_dir=temp_dir / "csv_batch",
            create_archives=False,
            continue_on_error=True,
        )

        # Set up processor
        processor = BatchProcessor(batch_config)

        # Load jobs from CSV
        jobs_added = processor.add_jobs_from_file(csv_file)
        assert jobs_added == 3
        assert len(processor.jobs) == 3

        # Verify job configurations
        job1 = processor.jobs[0]
        assert job1.url == "https://example.com/blog/first-post"
        assert str(job1.output_dir) == "custom/first"

        job2 = processor.jobs[1]
        assert job2.url == "https://example.com/blog/second-post"
        assert "custom-second" in str(job2.output_dir)

        job3 = processor.jobs[2]
        assert job3.url == "https://example.com/blog/third-post"
        assert "third-post" in str(job3.output_dir)

    @pytest.mark.asyncio
    async def test_full_pipeline_simulation(self, temp_dir):
        """Test a full pipeline with all Priority 2 features."""

        # 1. Load configuration
        config_data = {
            "converter": {
                "default_timeout": 30,
                "rate_limit_delay": 0.1,
                "respect_robots_txt": True,
            },
            "batch": {
                "max_concurrent": 2,
                "create_summary": True,
                "output_base_dir": str(temp_dir / "full_pipeline"),
                "create_archives": False,  # Skip archiving for speed
            },
        }

        converter_config = ConfigLoader.create_converter_config(config_data)
        batch_config = ConfigLoader.create_batch_config(config_data)

        # 2. Set up caching
        cache_config = CacheConfig(
            backend=CacheBackend.FILE, cache_dir=temp_dir / "pipeline_cache", ttl_html=3600
        )
        cache = CacheManager(cache_config)
        await cache.initialize()

        # 3. Pre-populate cache with some content
        urls_to_process = [
            "https://example.com/blog/cached-post",
            "https://example.com/blog/fresh-post",
        ]

        # Cache one URL (simulating previous run)
        cached_html = (
            "<html><body><h1>Cached Content</h1><p>This was cached before.</p></body></html>"
        )
        await cache.set_html(urls_to_process[0], cached_html)

        # 4. Set up batch processing
        processor = BatchProcessor(batch_config)

        # Add jobs
        for url in urls_to_process:
            processor.add_job(url)

        assert len(processor.jobs) == 2

        # 5. Check cache hits/misses before processing
        cache_stats_before = await cache.get_cache_stats()

        # Verify cached content exists
        cached_content = await cache.get_html(urls_to_process[0])
        assert cached_content == cached_html

        # Verify fresh content doesn't exist in cache
        fresh_content = await cache.get_html(urls_to_process[1])
        assert fresh_content is None

        # 6. Get final cache stats
        cache_stats_after = await cache.get_cache_stats()

        # Should have at least one cached entry
        assert cache_stats_after["total_entries"] >= 1

        # 7. Verify batch job results compilation would work
        # Simulate some job results
        processor.jobs[0].status = processor.jobs[0].status.__class__.COMPLETED
        processor.jobs[0].start_time = 1000.0
        processor.jobs[0].end_time = 1005.0

        processor.jobs[1].status = processor.jobs[1].status.__class__.COMPLETED
        processor.jobs[1].start_time = 1100.0
        processor.jobs[1].end_time = 1108.0

        summary = processor._compile_results(processor.jobs)
        assert summary["total"] == 2
        assert summary["successful"] == 2
        assert summary["failed"] == 0
        assert summary["total_duration"] == 13.0  # 5.0 + 8.0

        await cache.shutdown()

    def test_priority2_feature_compatibility(self):
        """Test that all Priority 2 features can be configured together."""

        # Test comprehensive configuration
        full_config = {
            "converter": {
                "default_timeout": 45,
                "max_concurrent_downloads": 8,
                "rate_limit_delay": 0.5,
                "max_retries": 5,
                "backoff_factor": 1.5,
                "user_agent": "WordPress-Shopify-Converter/2.0",
                "respect_robots_txt": True,
                "preserve_classes": ["wp-block", "custom-class", "shopify-compatible"],
            },
            "batch": {
                "max_concurrent": 4,
                "continue_on_error": True,
                "output_base_dir": "/custom/batch/output",
                "create_summary": True,
                "skip_existing": True,
                "timeout_per_job": 600,
                "retry_failed": True,
                "max_retries": 3,
                "create_archives": True,
                "archive_format": "zip",
                "cleanup_after_archive": False,
            },
        }

        # Create both configs
        converter_config = ConfigLoader.create_converter_config(full_config)
        batch_config = ConfigLoader.create_batch_config(full_config)

        # Verify converter config
        assert converter_config.default_timeout == 45
        assert converter_config.max_concurrent_downloads == 8
        assert converter_config.rate_limit_delay == 0.5
        assert converter_config.max_retries == 5
        assert "wp-block" in converter_config.preserve_classes
        assert "shopify-compatible" in converter_config.preserve_classes

        # Verify batch config
        assert batch_config.max_concurrent == 4
        assert batch_config.continue_on_error is True
        assert str(batch_config.output_base_dir) == "/custom/batch/output"
        assert batch_config.timeout_per_job == 600
        assert batch_config.create_archives is True
        assert batch_config.archive_format == "zip"
        assert batch_config.cleanup_after_archive is False

        # Test cache config compatibility
        cache_config = CacheConfig(
            backend=CacheBackend.FILE,
            ttl_html=converter_config.default_timeout * 2,  # 90 seconds
            ttl_images=86400,
            compress=True,
            max_cache_size_mb=2000,
        )

        assert cache_config.ttl_html == 90
        assert cache_config.compress is True
        assert cache_config.max_cache_size_mb == 2000
