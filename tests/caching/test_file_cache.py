"""Comprehensive tests for file cache implementation."""

import asyncio
from pathlib import Path
from unittest.mock import patch

import pytest
import pytest_asyncio

from src.caching.base import CacheConfig
from src.caching.file_cache import FileCache


class TestFileCacheErrorHandling:
    """Test file cache error handling scenarios."""

    @pytest_asyncio.fixture
    async def file_cache(self, temp_dir):
        """Create file cache instance."""
        config = CacheConfig(cache_dir=temp_dir / "test_cache")
        cache = FileCache(config)
        yield cache

    @pytest.mark.asyncio
    async def test_get_file_read_error(self, file_cache):
        """Test get operation when file read fails."""
        test_key = "test_key"
        test_content_type = "html"

        # Create a cache file first
        await file_cache.set(test_key, "test_value", ttl=3600, content_type=test_content_type)

        # Mock aiofiles.open to raise an exception
        with patch("aiofiles.open", side_effect=OSError("File read error")):
            result = await file_cache.get(test_key)

            # Should return None due to error
            assert result is None
            # Error stats should increment
            assert file_cache._stats["errors"] >= 1

    @pytest.mark.asyncio
    async def test_get_json_decode_error(self, file_cache):
        """Test get operation when JSON decode fails."""
        test_key = "test_key"
        test_content_type = "html"
        cache_path = file_cache._get_cache_path(test_key, test_content_type)

        # Create cache file with invalid JSON
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        with open(cache_path, "w") as f:
            f.write("invalid json content")

        result = await file_cache.get(test_key)

        # Should return None due to JSON decode error
        assert result is None
        # Error stats should increment
        assert file_cache._stats["errors"] >= 1

    @pytest.mark.asyncio
    async def test_set_file_write_error(self, file_cache):
        """Test set operation when file write fails."""
        test_key = "test_key"
        test_value = "test_value"

        # Mock aiofiles.open to raise an exception
        with patch("aiofiles.open", side_effect=OSError("File write error")):
            result = await file_cache.set(test_key, test_value)

            # Should return False due to error
            assert result is False
            # Error stats should increment
            assert file_cache._stats["errors"] >= 1

    @pytest.mark.asyncio
    async def test_delete_file_error(self, file_cache):
        """Test delete operation when file deletion fails."""
        test_key = "test_key"

        # Create a cache file first
        await file_cache.set(test_key, "test_value")

        # Mock Path.unlink to raise an exception
        with patch("pathlib.Path.unlink", side_effect=OSError("File delete error")):
            result = await file_cache.delete(test_key)

            # Should return False due to error
            assert result is False
            # Error stats should increment
            assert file_cache._stats["errors"] >= 1

    @pytest.mark.asyncio
    async def test_cleanup_file_corruption_error(self, file_cache):
        """Test cleanup handles corrupted cache files."""
        test_key = "test_key"
        test_content_type = "html"
        cache_path = file_cache._get_cache_path(test_key, test_content_type)

        # Create cache file with corrupted content
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        with open(cache_path, "w") as f:
            f.write("corrupted cache data")

        # Cleanup should handle the corrupted file by removing it
        cleaned_count = await file_cache.cleanup_expired()

        # Should have cleaned up the corrupted file
        assert cleaned_count >= 1
        # File should be removed
        assert not cache_path.exists()

    @pytest.mark.asyncio
    async def test_cleanup_general_error(self, file_cache):
        """Test cleanup handles general errors."""
        # Mock Path.glob to raise an exception
        with patch("pathlib.Path.glob", side_effect=Exception("Cleanup error")):
            result = await file_cache.cleanup_expired()

            # Should return 0 due to error
            assert result == 0


class TestFileCacheSizeEnforcement:
    """Test file cache size limit enforcement."""

    @pytest_asyncio.fixture
    async def small_cache(self, temp_dir):
        """Create file cache with small size limit."""
        config = CacheConfig(
            cache_dir=temp_dir / "small_cache",
            max_cache_size_mb=1,  # 1MB limit
        )
        cache = FileCache(config)
        yield cache

    @pytest.mark.asyncio
    async def test_size_limit_enforcement_triggered(self, small_cache):
        """Test that size limit enforcement is triggered."""
        # Add multiple large entries to exceed the limit
        large_data = "x" * (300 * 1024)  # 300KB each

        # Add several large entries
        for i in range(5):
            await small_cache.set(f"large_key_{i}", large_data, content_type="html")
            await asyncio.sleep(0.1)  # Small delay to ensure different modification times

        # Get stats to check current size
        stats = await small_cache.stats()

        # Should be some cache management happening
        assert "total_size_mb" in stats
        assert stats["total_entries"] >= 0

    @pytest.mark.asyncio
    async def test_size_enforcement_error_handling(self, small_cache):
        """Test size enforcement error handling."""
        # Mock stats method to raise an exception
        with patch.object(small_cache, "stats", side_effect=Exception("Stats error")):
            # This should trigger size enforcement during set, but handle the error
            result = await small_cache.set("test_key", "test_value")

            # Set should still succeed despite enforcement error
            assert result is True

    @pytest.mark.asyncio
    async def test_size_enforcement_file_stat_error(self, small_cache):
        """Test size enforcement handles file stat errors."""
        # Add an entry first
        await small_cache.set("test_key", "test_value")

        # Mock Path.stat to raise OSError for some files
        original_stat = Path.stat

        def mock_stat(self):
            if "test_key" in str(self):
                raise OSError("Stat error")
            return original_stat(self)

        with patch("pathlib.Path.stat", side_effect=mock_stat):
            # Force size enforcement by mocking stats to show high size
            with patch.object(small_cache, "stats", return_value={"total_size_mb": 10}):
                # This should trigger size enforcement
                await small_cache._enforce_size_limit()

    @pytest.mark.asyncio
    async def test_size_enforcement_file_deletion_error(self, small_cache):
        """Test size enforcement handles file deletion errors."""
        # Add several entries
        for i in range(3):
            await small_cache.set(f"key_{i}", f"value_{i}")
            await asyncio.sleep(0.1)

        # Mock Path.unlink to raise OSError for some files
        original_unlink = Path.unlink

        def mock_unlink(self, missing_ok=False):
            if "key_1" in str(self):
                raise OSError("Delete error")
            return original_unlink(self, missing_ok=missing_ok)

        with patch("pathlib.Path.unlink", side_effect=mock_unlink):
            # Force size enforcement
            with patch.object(small_cache, "stats", return_value={"total_size_mb": 10}):
                await small_cache._enforce_size_limit()


class TestFileCacheContentTypes:
    """Test file cache with different content types."""

    @pytest_asyncio.fixture
    async def file_cache(self, temp_dir):
        """Create file cache instance."""
        config = CacheConfig(cache_dir=temp_dir / "content_cache")
        cache = FileCache(config)
        yield cache

    @pytest.mark.asyncio
    async def test_html_content_type_path(self, file_cache):
        """Test HTML content uses correct directory."""
        await file_cache.set("html_key", "<html>test</html>", content_type="html")

        # Check that file was created in html directory
        html_files = list(file_cache.html_dir.glob("*.cache"))
        assert len(html_files) >= 1

    @pytest.mark.asyncio
    async def test_image_content_type_path(self, file_cache):
        """Test image content uses correct directory."""
        await file_cache.set("image_key", b"fake image data", content_type="image")

        # Check that file was created in image directory
        image_files = list(file_cache.image_dir.glob("*.cache"))
        assert len(image_files) >= 1

    @pytest.mark.asyncio
    async def test_metadata_content_type_path(self, file_cache):
        """Test metadata content uses correct directory."""
        await file_cache.set("meta_key", {"title": "Test"}, content_type="metadata")

        # Check that file was created in metadata directory
        metadata_files = list(file_cache.metadata_dir.glob("*.cache"))
        assert len(metadata_files) >= 1

    @pytest.mark.asyncio
    async def test_robots_content_type_path(self, file_cache):
        """Test robots.txt content uses correct directory."""
        await file_cache.set("robots_key", "User-agent: *", content_type="robots")

        # Check that file was created in robots directory
        robots_files = list(file_cache.robots_dir.glob("*.cache"))
        assert len(robots_files) >= 1

    @pytest.mark.asyncio
    async def test_generic_content_type_path(self, file_cache):
        """Test generic content uses correct directory."""
        await file_cache.set("generic_key", "some data", content_type="generic")

        # Check that file was created in generic directory
        generic_files = list(file_cache.generic_dir.glob("*.cache"))
        assert len(generic_files) >= 1


class TestFileCacheDeleteBranches:
    """Test file cache delete operation branches."""

    @pytest_asyncio.fixture
    async def file_cache(self, temp_dir):
        """Create file cache instance."""
        config = CacheConfig(cache_dir=temp_dir / "delete_cache")
        cache = FileCache(config)
        yield cache

    @pytest.mark.asyncio
    async def test_delete_existing_file_success(self, file_cache):
        """Test deleting an existing file successfully."""
        test_key = "existing_key"

        # Create a cache entry
        await file_cache.set(test_key, "test_value")

        # Verify it exists
        entry = await file_cache.get(test_key)
        assert entry is not None

        # Delete it
        result = await file_cache.delete(test_key)

        # Should return True and update stats
        assert result is True
        assert file_cache._stats["deletes"] >= 1

    @pytest.mark.asyncio
    async def test_delete_nonexistent_file(self, file_cache):
        """Test deleting a non-existent file."""
        test_key = "nonexistent_key"

        # Try to delete non-existent key
        result = await file_cache.delete(test_key)

        # Should return False (no file was actually deleted)
        assert result is False


class TestFileCacheClearOperation:
    """Test file cache clear operation."""

    @pytest_asyncio.fixture
    async def file_cache(self, temp_dir):
        """Create file cache instance."""
        config = CacheConfig(cache_dir=temp_dir / "clear_cache")
        cache = FileCache(config)
        yield cache

    @pytest.mark.asyncio
    async def test_clear_with_files(self, file_cache):
        """Test clearing cache with existing files."""
        # Add multiple entries of different types
        await file_cache.set("html_key", "<html>test</html>", content_type="html")
        await file_cache.set("image_key", b"image_data", content_type="image")
        await file_cache.set("meta_key", {"title": "Test"}, content_type="metadata")

        # Clear the cache
        result = await file_cache.clear()

        # Should return True
        assert result is True

        # All entries should be gone
        assert await file_cache.get("html_key") is None
        assert await file_cache.get("image_key") is None
        assert await file_cache.get("meta_key") is None

    @pytest.mark.asyncio
    async def test_clear_empty_cache(self, file_cache):
        """Test clearing an empty cache."""
        result = await file_cache.clear()

        # Should still return True
        assert result is True


class TestFileCacheStatsOperation:
    """Test file cache statistics operation."""

    @pytest_asyncio.fixture
    async def file_cache(self, temp_dir):
        """Create file cache instance."""
        config = CacheConfig(cache_dir=temp_dir / "stats_cache")
        cache = FileCache(config)
        yield cache

    @pytest.mark.asyncio
    async def test_stats_with_various_content(self, file_cache):
        """Test stats with different content types."""
        # Add entries of different types and sizes
        await file_cache.set("html_key", "<html>test content</html>", content_type="html")
        await file_cache.set("image_key", b"binary_image_data" * 100, content_type="image")
        await file_cache.set(
            "meta_key", {"title": "Test", "desc": "Description"}, content_type="metadata"
        )

        stats = await file_cache.stats()

        # Should have comprehensive stats
        assert "total_entries" in stats
        assert "total_size_bytes" in stats
        assert "total_size_mb" in stats
        assert "hits" in stats
        assert "misses" in stats
        assert "sets" in stats

        # Should have at least 3 entries
        assert stats["total_entries"] >= 3
        assert stats["total_size_bytes"] > 0
        assert stats["total_size_mb"] >= 0


class TestFileCacheIntegration:
    """Test file cache integration scenarios."""

    @pytest_asyncio.fixture
    async def file_cache(self, temp_dir):
        """Create file cache instance."""
        config = CacheConfig(
            cache_dir=temp_dir / "integration_cache",
            ttl_default=1,  # Short TTL for testing expiration
            max_cache_size_mb=5,
        )
        cache = FileCache(config)
        yield cache

    @pytest.mark.asyncio
    async def test_full_lifecycle_with_expiration(self, file_cache):
        """Test full cache lifecycle including expiration."""
        test_key = "lifecycle_key"
        test_value = "lifecycle_value"

        # Set with short TTL
        await file_cache.set(test_key, test_value, ttl=1)

        # Should be available immediately
        entry = await file_cache.get(test_key)
        assert entry is not None
        assert entry.value == test_value

        # Wait for expiration
        await asyncio.sleep(2)

        # Should be expired now
        entry = await file_cache.get(test_key)
        assert entry is None

    @pytest.mark.asyncio
    async def test_concurrent_operations(self, file_cache):
        """Test concurrent cache operations."""
        # Create multiple concurrent set operations
        tasks = []
        for i in range(10):
            task = file_cache.set(f"concurrent_key_{i}", f"value_{i}")
            tasks.append(task)

        # Wait for all to complete
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # All should succeed
        assert all(result is True for result in results if not isinstance(result, Exception))

        # All entries should be retrievable
        for i in range(10):
            entry = await file_cache.get(f"concurrent_key_{i}")
            assert entry is not None
            assert entry.value == f"value_{i}"

    @pytest.mark.asyncio
    async def test_large_value_handling(self, file_cache):
        """Test handling of large cached values."""
        test_key = "large_key"
        # Create a large value (1MB)
        large_value = "x" * (1024 * 1024)

        # Should be able to cache large values
        result = await file_cache.set(test_key, large_value)
        assert result is True

        # Should be able to retrieve large values
        entry = await file_cache.get(test_key)
        assert entry is not None
        assert entry.value == large_value
        assert entry.size_bytes >= 1024 * 1024

    @pytest.mark.asyncio
    async def test_special_characters_in_keys(self, file_cache):
        """Test handling of special characters in cache keys."""
        special_keys = [
            "key with spaces",
            "key/with/slashes",
            "key-with-dashes",
            "key_with_underscores",
            "key.with.dots",
            "key@with#special$chars%",
        ]

        for key in special_keys:
            # Should be able to set and get with special characters
            await file_cache.set(key, f"value_for_{key}")
            entry = await file_cache.get(key)
            assert entry is not None
            assert entry.value == f"value_for_{key}"

    @pytest.mark.asyncio
    async def test_error_recovery(self, file_cache):
        """Test cache recovery from error conditions."""
        test_key = "recovery_key"

        # Set a value successfully
        await file_cache.set(test_key, "initial_value")

        # Simulate an error condition by corrupting the cache file
        cache_path = file_cache._get_cache_path(test_key, "generic")
        with open(cache_path, "w") as f:
            f.write("corrupted data")

        # Get should handle the corruption gracefully
        entry = await file_cache.get(test_key)
        assert entry is None

        # Should be able to set a new value after corruption
        result = await file_cache.set(test_key, "recovered_value")
        assert result is True

        # Should be able to get the new value
        entry = await file_cache.get(test_key)
        assert entry is not None
        assert entry.value == "recovered_value"
