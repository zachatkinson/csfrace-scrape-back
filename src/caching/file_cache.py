"""File-based cache backend implementation."""

import hashlib
import time
from pathlib import Path
from typing import Any, Optional

import aiofiles

from .base import BaseCacheBackend, CacheConfig, CacheEntry


class FileCache(BaseCacheBackend):
    """File-based cache backend using local filesystem."""

    def __init__(self, config: CacheConfig):
        """Initialize file cache.

        Args:
            config: Cache configuration
        """
        super().__init__(config)
        self.cache_dir = Path(config.cache_dir).resolve()
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Create subdirectories for different content types
        self.html_dir = self.cache_dir / "html"
        self.image_dir = self.cache_dir / "images"
        self.metadata_dir = self.cache_dir / "metadata"
        self.robots_dir = self.cache_dir / "robots"
        self.generic_dir = self.cache_dir / "generic"

        for directory in [
            self.html_dir,
            self.image_dir,
            self.metadata_dir,
            self.robots_dir,
            self.generic_dir,
        ]:
            directory.mkdir(exist_ok=True)

        self._stats = {"hits": 0, "misses": 0, "sets": 0, "deletes": 0, "errors": 0}

    def _get_cache_path(self, key: str, content_type: str) -> Path:
        """Get the file path for a cache key.

        Args:
            key: Cache key
            content_type: Content type

        Returns:
            Path to cache file
        """
        # Choose directory based on content type
        type_dirs = {
            "html": self.html_dir,
            "image": self.image_dir,
            "metadata": self.metadata_dir,
            "robots": self.robots_dir,
        }

        base_dir = type_dirs.get(content_type, self.generic_dir)

        # Create safe filename from key
        safe_key = hashlib.sha256(key.encode()).hexdigest()
        return base_dir / f"{safe_key}.cache"

    async def get(self, key: str) -> Optional[CacheEntry]:
        """Get a cache entry by key."""
        try:
            # We need to check all possible content type directories
            # since we don't know the content type from just the key
            possible_paths = []
            for content_type in ["html", "image", "metadata", "robots", "generic"]:
                possible_paths.append(self._get_cache_path(key, content_type))

            cache_path = None
            for path in possible_paths:
                if path.exists():
                    cache_path = path
                    break

            if not cache_path:
                self._stats["misses"] += 1
                return None

            # Read cache entry
            async with aiofiles.open(cache_path, "rb") as f:
                data = await f.read()

            # Deserialize entry
            entry_data = self._decompress_data(data, compressed=True)
            entry = CacheEntry.from_dict(entry_data)

            # Check if expired
            if entry.is_expired:
                await self.delete(key)
                self._stats["misses"] += 1
                return None

            self._stats["hits"] += 1
            self.logger.debug("Cache hit", key=key, age_seconds=entry.age_seconds)
            return entry

        except Exception as e:
            self._stats["errors"] += 1
            self.logger.warning("Cache get failed", key=key, error=str(e))
            return None

    async def set(
        self, key: str, value: Any, ttl: Optional[int] = None, content_type: str = "generic"
    ) -> bool:
        """Set a cache entry."""
        try:
            if ttl is None:
                ttl = self.get_ttl_for_content_type(content_type)

            # Create cache entry
            entry = CacheEntry(
                key=key,
                value=value,
                created_at=time.time(),
                ttl=ttl,
                content_type=content_type,
                size_bytes=self._calculate_size(value),
                compressed=self.config.compress,
            )

            # Get cache file path
            cache_path = self._get_cache_path(key, content_type)

            # Serialize and compress entry
            entry_data = self._compress_data(entry.to_dict())

            # Write to file atomically
            temp_path = cache_path.with_suffix(".tmp")
            async with aiofiles.open(temp_path, "wb") as f:
                await f.write(entry_data)

            # Atomic move
            temp_path.rename(cache_path)

            self._stats["sets"] += 1
            self.logger.debug("Cache set", key=key, size_bytes=entry.size_bytes, ttl=ttl)

            # Check if cache size is getting too large
            await self._enforce_size_limit()

            return True

        except Exception as e:
            self._stats["errors"] += 1
            self.logger.error("Cache set failed", key=key, error=str(e))
            return False

    async def delete(self, key: str) -> bool:
        """Delete a cache entry."""
        try:
            deleted = False

            # Check all possible content type directories
            for content_type in ["html", "image", "metadata", "robots", "generic"]:
                cache_path = self._get_cache_path(key, content_type)
                if cache_path.exists():
                    cache_path.unlink()
                    deleted = True

            if deleted:
                self._stats["deletes"] += 1
                self.logger.debug("Cache delete", key=key)

            return deleted

        except Exception as e:
            self._stats["errors"] += 1
            self.logger.error("Cache delete failed", key=key, error=str(e))
            return False

    async def clear(self) -> bool:
        """Clear all cache entries."""
        try:
            # Remove all files in cache directories
            for directory in [
                self.html_dir,
                self.image_dir,
                self.metadata_dir,
                self.robots_dir,
                self.generic_dir,
            ]:
                for cache_file in directory.glob("*.cache"):
                    cache_file.unlink()

            # Reset stats
            self._stats = {"hits": 0, "misses": 0, "sets": 0, "deletes": 0, "errors": 0}

            self.logger.info("Cache cleared")
            return True

        except Exception as e:
            self._stats["errors"] += 1
            self.logger.error("Cache clear failed", error=str(e))
            return False

    async def stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        try:
            # Calculate cache size and entry count
            total_size = 0
            total_entries = 0
            expired_entries = 0

            for directory in [
                self.html_dir,
                self.image_dir,
                self.metadata_dir,
                self.robots_dir,
                self.generic_dir,
            ]:
                for cache_file in directory.glob("*.cache"):
                    try:
                        file_size = cache_file.stat().st_size
                        total_size += file_size
                        total_entries += 1

                        # Check if expired (basic check without full deserialization)
                        mtime = cache_file.stat().st_mtime
                        if time.time() - mtime > self.config.ttl_default:
                            expired_entries += 1

                    except OSError:
                        continue

            return {
                **self._stats,
                "total_entries": total_entries,
                "expired_entries": expired_entries,
                "total_size_bytes": total_size,
                "total_size_mb": round(total_size / (1024 * 1024), 2),
                "cache_dir": str(self.cache_dir),
                "hit_rate": (
                    self._stats["hits"] / max(1, self._stats["hits"] + self._stats["misses"])
                )
                * 100,
            }

        except Exception as e:
            self.logger.error("Cache stats failed", error=str(e))
            return {"error": str(e)}

    async def cleanup_expired(self) -> int:
        """Clean up expired cache entries."""
        cleaned = 0

        try:
            for directory in [
                self.html_dir,
                self.image_dir,
                self.metadata_dir,
                self.robots_dir,
                self.generic_dir,
            ]:
                for cache_file in directory.glob("*.cache"):
                    try:
                        # Read and check if expired
                        async with aiofiles.open(cache_file, "rb") as f:
                            data = await f.read()

                        entry_data = self._decompress_data(data, compressed=True)
                        entry = CacheEntry.from_dict(entry_data)

                        if entry.is_expired:
                            cache_file.unlink()
                            cleaned += 1

                    except Exception:
                        # If we can't read the file, it's probably corrupted
                        cache_file.unlink()
                        cleaned += 1
                        continue

            if cleaned > 0:
                self.logger.info("Cleaned up expired cache entries", count=cleaned)

            return cleaned

        except Exception as e:
            self.logger.error("Cache cleanup failed", error=str(e))
            return 0

    async def _enforce_size_limit(self) -> None:
        """Enforce cache size limit by removing oldest entries."""
        try:
            stats = await self.stats()
            current_size_mb = stats.get("total_size_mb", 0)

            if current_size_mb <= self.config.max_cache_size_mb:
                return

            self.logger.info(
                "Cache size limit exceeded, cleaning up",
                current_size_mb=current_size_mb,
                limit_mb=self.config.max_cache_size_mb,
            )

            # Get all cache files with their modification times
            cache_files = []
            for directory in [
                self.html_dir,
                self.image_dir,
                self.metadata_dir,
                self.robots_dir,
                self.generic_dir,
            ]:
                for cache_file in directory.glob("*.cache"):
                    try:
                        mtime = cache_file.stat().st_mtime
                        size = cache_file.stat().st_size
                        cache_files.append((cache_file, mtime, size))
                    except OSError:
                        continue

            # Sort by modification time (oldest first)
            cache_files.sort(key=lambda x: x[1])

            # Remove oldest files until under limit
            removed_size = 0
            removed_count = 0
            target_size = self.config.max_cache_size_mb * 0.8 * 1024 * 1024  # 80% of limit

            for cache_file, mtime, size in cache_files:
                if current_size_mb * 1024 * 1024 - removed_size <= target_size:
                    break

                try:
                    cache_file.unlink()
                    removed_size += size
                    removed_count += 1
                except OSError:
                    continue

            self.logger.info(
                "Cache cleanup completed",
                removed_count=removed_count,
                removed_size_mb=round(removed_size / (1024 * 1024), 2),
            )

        except Exception as e:
            self.logger.error("Cache size enforcement failed", error=str(e))
