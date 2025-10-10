"""Async WordPress to Shopify content converter using aiohttp."""

from collections.abc import Callable, Coroutine
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import aiohttp
import asyncio
from bs4 import BeautifulSoup

from src.core.decorators import content_processing_error_handler, network_error_handler
from src.core.logging_hierarchy import get_scraping_logger

from ..constants import (
    DEFAULT_IMAGES_DIR,
    DEFAULT_TIMEOUT,
    HTTP_PROTOCOL,
    HTTPS_PROTOCOL,
    LOCALHOST_DOMAIN,
    MAX_RETRIES,
    PROGRESS_COMPLETE,
    PROGRESS_FETCH,
    PROGRESS_PROCESS,
    PROGRESS_SETUP,
)
from ..processors.html_processor import HTMLProcessorOrchestrator
from ..processors.image_downloader import AsyncImageDownloader
from ..processors.metadata_extractor import MetadataExtractor
from ..utils.http import safe_http_get_with_raise
from ..utils.retry import with_retry
from ..utils.robots import robots_checker

# from .config import ConverterConfig, config as default_config  # type: ignore[import-not-found]
from .exceptions import ConversionError

logger = get_scraping_logger()


# Temporary config class until config.py is available
class OutputConfig:
    """Output configuration."""

    def __init__(self) -> None:
        self.images_subdir = DEFAULT_IMAGES_DIR
        self.metadata_file = "metadata.txt"
        self.html_file = "converted_content.html"
        self.shopify_file = "shopify_ready_content.html"


class HttpConfig:
    """HTTP configuration."""

    def __init__(self) -> None:
        self.timeout = DEFAULT_TIMEOUT
        self.max_concurrent = 10
        self.user_agent = "Mozilla/5.0 (compatible; CSFRaceScraper/1.0)"


class ConverterConfig:
    """Temporary converter configuration."""

    def __init__(self) -> None:
        self.timeout = DEFAULT_TIMEOUT
        self.max_retries = MAX_RETRIES
        self.output = OutputConfig()
        self.http = HttpConfig()


default_config = ConverterConfig()


class AsyncWordPressConverter:
    """Async WordPress to Shopify content converter."""

    def __init__(self, base_url: str, output_dir: Path, config: ConverterConfig | None = None):
        """Initialize the async converter.

        Args:
            base_url: WordPress URL to convert
            output_dir: Directory to save converted content
            config: Optional converter configuration (uses global config if None)
        """
        self.base_url = self._validate_url(base_url)
        self.output_dir = Path(output_dir)
        self.config = config or default_config  # Use provided config or global default
        self.images_dir = self.output_dir / self.config.output.images_subdir

        # Initialize processors
        self.html_processor = HTMLProcessorOrchestrator()
        self.metadata_extractor = MetadataExtractor(self.base_url)
        self.image_downloader = AsyncImageDownloader(
            self.images_dir, max_concurrent=self.config.http.max_concurrent
        )

        logger.info(
            "Initialized async converter",
            url=self.base_url,
            output_dir=str(self.output_dir),
            config_timeout=self.config.http.timeout,
            config_max_concurrent=self.config.http.max_concurrent,
        )

    def _validate_url(self, url: str) -> str:
        """Validate and normalize URL.

        Args:
            url: URL to validate

        Returns:
            Normalized URL

        Raises:
            ConversionError: If URL is invalid
        """
        if not url:
            raise ConversionError("URL cannot be empty")

        # Add protocol if missing
        if not url.startswith((HTTP_PROTOCOL, HTTPS_PROTOCOL)):
            url = f"{HTTPS_PROTOCOL}{url}"

        # Validate URL structure
        parsed = urlparse(url)
        if not parsed.netloc:
            raise ConversionError(f"Invalid URL: {url}")

        # Check for valid domain structure (must have at least one dot or be localhost)
        if "." not in parsed.netloc and parsed.netloc != LOCALHOST_DOMAIN:
            raise ConversionError(f"Invalid domain: {parsed.netloc}")

        return url

    @content_processing_error_handler("setup output directories")
    async def _setup_directories(self) -> None:
        """Create necessary output directories."""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.images_dir.mkdir(exist_ok=True)
        logger.debug("Created output directories", output_dir=str(self.output_dir))

    @with_retry()
    @network_error_handler("fetch content")
    async def _fetch_content(self, session: aiohttp.ClientSession) -> str:
        """Fetch webpage content using aiohttp.

        Args:
            session: aiohttp client session

        Returns:
            HTML content as string

        Raises:
            FetchError: If fetching fails
        """
        logger.info("Fetching content", url=self.base_url)

        # Check robots.txt and enforce crawl delay
        await robots_checker.check_and_delay(self.base_url, self.config.http.user_agent, session)

        content = await safe_http_get_with_raise(
            session, self.base_url, timeout=self.config.http.timeout
        )

        logger.info("Successfully fetched content", url=self.base_url, size=len(content))

        return content

    @content_processing_error_handler("process HTML content")
    async def _process_content(self, html_content: str) -> tuple[dict[str, str], str, list[str]]:
        """Process HTML content and extract components.

        Args:
            html_content: Raw HTML content

        Returns:
            Tuple of (metadata, converted_html, image_urls)

        Raises:
            ProcessingError: If processing fails
        """
        logger.info("Processing HTML content")

        # Parse HTML
        soup = BeautifulSoup(html_content, "html.parser")

        # Extract metadata
        metadata = await self.metadata_extractor.extract(soup)

        # Process HTML content
        processed_html = await self.html_processor.process(soup)

        # Extract image URLs
        image_urls = self._extract_image_urls(processed_html)

        logger.info(
            "Content processing completed",
            metadata_fields=len(metadata),
            html_size=len(processed_html),
            image_count=len(image_urls),
        )

        return metadata, processed_html, image_urls

    def _extract_image_urls(self, html_content: str) -> list[str]:
        """Extract image URLs from HTML content.

        Args:
            html_content: Processed HTML content

        Returns:
            List of absolute image URLs
        """
        soup = BeautifulSoup(html_content, "html.parser")
        img_tags = soup.find_all("img")

        image_urls = []
        for img in img_tags:
            if hasattr(img, "get"):  # Type guard for Tag
                src = img.get("src")
                if src and isinstance(src, str):
                    # Convert to absolute URL
                    absolute_url = urljoin(self.base_url, src)
                    image_urls.append(absolute_url)

        # Remove duplicates while preserving order
        seen = set()
        unique_urls = []
        for url in image_urls:
            if url not in seen:
                seen.add(url)
                unique_urls.append(url)

        return unique_urls

    @content_processing_error_handler("save content")
    async def _save_content(self, metadata: dict[str, str], html_content: str) -> None:
        """Save converted content and metadata to files.

        Args:
            metadata: Extracted metadata
            html_content: Converted HTML content

        Raises:
            SaveError: If saving fails
        """
        logger.info("Saving converted content")

        # Save metadata
        metadata_path = self.output_dir / self.config.output.metadata_file
        await self._write_metadata_file(metadata_path, metadata)

        # Save HTML only
        html_path = self.output_dir / self.config.output.html_file
        await self._write_text_file(html_path, html_content)

        # Save combined Shopify-ready content
        shopify_path = self.output_dir / self.config.output.shopify_file
        await self._write_shopify_file(shopify_path, metadata, html_content)

        logger.info(
            "Files saved successfully",
            metadata_file=str(metadata_path),
            html_file=str(html_path),
            shopify_file=str(shopify_path),
        )

    async def _write_metadata_file(self, path: Path, metadata: dict[str, str]) -> None:
        """Write metadata to text file."""
        content = "EXTRACTED METADATA\n" + "=" * 50 + "\n\n"
        for key, value in metadata.items():
            formatted_key = key.replace("_", " ").title()
            content += f"{formatted_key}: {value}\n"

        await self._write_text_file(path, content)

    async def _write_shopify_file(
        self, path: Path, metadata: dict[str, str], html_content: str
    ) -> None:
        """Write Shopify-ready content with metadata comments."""
        content = "<!-- METADATA -->\n"
        for key, value in metadata.items():
            formatted_key = key.replace("_", " ").title()
            content += f"<!-- {formatted_key}: {value} -->\n"
        content += "<!-- END METADATA -->\n\n"
        content += html_content

        await self._write_text_file(path, content)

    async def _write_text_file(self, path: Path, content: str) -> None:
        """Write text content to file asynchronously."""
        # Use asyncio to write file (simulated async I/O)
        await asyncio.get_event_loop().run_in_executor(
            None, lambda: path.write_text(content, encoding="utf-8")
        )

    async def convert(
        self,
        progress_callback: Callable[[int], None | Coroutine[Any, Any, None]] | None = None,
    ) -> None:
        """Main conversion method with progress tracking.

        Args:
            progress_callback: Optional callback for progress updates (0-100)
                             Can be sync or async function

        Raises:
            ConversionError: If conversion fails
        """
        try:
            logger.info("Starting async conversion", url=self.base_url)

            # Helper to call progress callback (handles both sync and async)
            async def call_progress(percent: int) -> None:
                if progress_callback:
                    result = progress_callback(percent)
                    # If callback returns a coroutine, await it
                    if asyncio.iscoroutine(result):
                        await result

            await call_progress(5)

            # Setup directories
            await self._setup_directories()
            await call_progress(PROGRESS_SETUP)

            # Create HTTP session with proper headers
            connector = aiohttp.TCPConnector(limit=self.config.http.max_concurrent)
            timeout = aiohttp.ClientTimeout(total=self.config.http.timeout)

            async with aiohttp.ClientSession(
                connector=connector,
                timeout=timeout,
                headers={"User-Agent": self.config.http.user_agent},
            ) as session:
                await call_progress(PROGRESS_FETCH)

                # Fetch webpage content
                html_content = await self._fetch_content(session)
                await call_progress(40)

                # Process content
                metadata, processed_html, image_urls = await self._process_content(html_content)
                await call_progress(PROGRESS_PROCESS)

                # Save converted content
                await self._save_content(metadata, processed_html)
                await call_progress(70)

                # Download images concurrently
                if image_urls:
                    # Create sync wrapper for image downloader's progress callback
                    def sync_image_progress(p: float) -> None:
                        """Synchronous progress wrapper for image downloads."""
                        if progress_callback:
                            result = progress_callback(70 + int(p * 0.3))
                            # Schedule coroutine if needed (don't await in sync context)
                            if asyncio.iscoroutine(result):
                                asyncio.create_task(result)

                    await self.image_downloader.download_all(
                        session,
                        image_urls,
                        progress_callback=sync_image_progress,
                    )

                await call_progress(PROGRESS_COMPLETE)

            logger.info(
                "Conversion completed successfully",
                output_dir=str(self.output_dir),
                images_downloaded=len(image_urls),
            )

        except ConversionError:
            raise
        except Exception as e:
            logger.exception("Unexpected error during conversion", error=str(e))
            raise ConversionError(
                f"Conversion failed: {e}", url=self.base_url, original_error=e
            ) from e
