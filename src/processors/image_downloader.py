"""Async image downloader with concurrent processing."""

import asyncio
from pathlib import Path
from typing import Callable, Optional
from urllib.parse import urlparse

import aiohttp
import structlog
from aiofiles import open as aopen

from ..core.config import config
from ..core.exceptions import ConversionError
from ..utils.retry import with_retry
from ..utils.robots import robots_checker

logger = structlog.get_logger(__name__)


class AsyncImageDownloader:
    """Async image downloader with concurrency control."""

    def __init__(self, output_dir: Path, max_concurrent: int = config.max_concurrent_downloads):
        """Initialize image downloader.

        Args:
            output_dir: Directory to save images
            max_concurrent: Maximum concurrent downloads
        """
        self.output_dir = output_dir
        self.semaphore = asyncio.Semaphore(max_concurrent)

        logger.debug(
            "Initialized image downloader",
            output_dir=str(output_dir),
            max_concurrent=max_concurrent,
        )

    async def download_all(
        self,
        session: aiohttp.ClientSession,
        image_urls: list[str],
        progress_callback: Optional[Callable[[float], None]] = None,
    ) -> list[str]:
        """Download all images concurrently.

        Args:
            session: aiohttp client session
            image_urls: List of image URLs to download
            progress_callback: Optional progress callback (0.0-1.0)

        Returns:
            List of successfully downloaded filenames
        """
        if not image_urls:
            logger.info("No images to download")
            return []

        logger.info("Starting concurrent image downloads", count=len(image_urls))

        # Create download tasks
        download_tasks = [
            self._download_single(session, url, i, len(image_urls), progress_callback)
            for i, url in enumerate(image_urls)
        ]

        # Execute downloads concurrently
        results = await asyncio.gather(*download_tasks, return_exceptions=True)

        # Process results
        successful_downloads = []
        failed_count = 0

        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.warning("Image download failed", url=image_urls[i], error=str(result))
                failed_count += 1
            elif result:
                successful_downloads.append(result)

        logger.info(
            "Image downloads completed",
            successful=len(successful_downloads),
            failed=failed_count,
            total=len(image_urls),
        )

        return successful_downloads

    async def _download_single(
        self,
        session: aiohttp.ClientSession,
        url: str,
        index: int,
        total: int,
        progress_callback: Optional[Callable[[float], None]] = None,
    ) -> Optional[str]:
        """Download a single image with concurrency control.

        Args:
            session: aiohttp client session
            url: Image URL to download
            index: Current image index (for progress)
            total: Total number of images
            progress_callback: Optional progress callback

        Returns:
            Filename if successful, None if failed
        """
        async with self.semaphore:
            try:
                filename = await self._download_image(session, url)

                # Update progress
                if progress_callback:
                    progress = (index + 1) / total
                    progress_callback(progress)

                # Rate limiting
                await asyncio.sleep(config.rate_limit_delay)

                return filename

            except Exception as e:
                logger.error("Failed to download image", url=url, error=str(e))
                return None

    @with_retry()
    async def _download_image(self, session: aiohttp.ClientSession, url: str) -> str:
        """Download image with retry logic.

        Args:
            session: aiohttp client session
            url: Image URL to download

        Returns:
            Downloaded filename

        Raises:
            ConversionError: If download fails after retries
        """
        try:
            logger.debug("Downloading image", url=url)

            # Check robots.txt and enforce crawl delay for images
            await robots_checker.check_and_delay(url, config.user_agent, session)

            async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as response:
                response.raise_for_status()

                # Generate filename
                filename = self._generate_filename(url, response)
                filepath = self.output_dir / filename

                # Ensure output directory exists
                self.output_dir.mkdir(parents=True, exist_ok=True)

                # Download and save image
                async with aopen(filepath, "wb") as f:
                    async for chunk in response.content.iter_chunked(8192):
                        await f.write(chunk)

                logger.debug(
                    "Successfully downloaded image",
                    url=url,
                    filename=filename,
                    size=response.content_length,
                )
                return filename

        except aiohttp.ClientError as e:
            raise ConversionError(f"Failed to download image {url}: {e}") from e
        except OSError as e:
            raise ConversionError(f"Failed to save image {url}: {e}") from e

    def _generate_filename(self, url: str, response: aiohttp.ClientResponse) -> str:
        """Generate filename for downloaded image.

        Args:
            url: Original image URL
            response: HTTP response object

        Returns:
            Generated filename
        """
        # Try to get filename from URL
        parsed_url = urlparse(url)
        original_filename = Path(parsed_url.path).name

        # If we have a proper filename with extension, use it
        if original_filename and "." in original_filename:
            return original_filename

        # Generate filename based on content type
        content_type = response.headers.get("content-type", "").lower()
        extension = self._get_extension_from_content_type(content_type)

        # Use hash of URL to generate unique filename
        url_hash = abs(hash(url)) % 100000
        filename = f"image_{url_hash}{extension}"

        return filename

    def _get_extension_from_content_type(self, content_type: str) -> str:
        """Get file extension from HTTP content-type header.

        Args:
            content_type: Content-Type header value

        Returns:
            File extension including dot
        """
        for mime_type, ext in config.content_type_extensions.items():
            if mime_type in content_type:
                return ext

        # Default extension
        return ".jpg"
