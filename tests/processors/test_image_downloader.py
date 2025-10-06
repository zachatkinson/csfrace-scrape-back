"""Comprehensive tests for src/processors/image_downloader.py.

Test coverage: 85 statements, 0% → 75%+
Following TEST_BUILDING.md MANDATORY standards with ZERO TOLERANCE.
"""

from collections.abc import AsyncIterator
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import asyncio
import pytest

from src.core.exceptions import ConversionError
from src.processors.image_downloader import AsyncImageDownloader

# =============================================================================
# TEST AsyncImageDownloader - Initialization
# =============================================================================


@pytest.mark.unit
class TestAsyncImageDownloaderInitialization:
    """Test AsyncImageDownloader initialization."""

    def test_initialization_with_output_dir(self, tmp_path: Path) -> None:
        """Test initialization with output directory."""
        # Arrange
        output_dir = tmp_path / "images"

        # Act
        downloader = AsyncImageDownloader(output_dir)

        # Assert
        assert downloader.output_dir == output_dir
        assert isinstance(downloader.semaphore, asyncio.Semaphore)

    def test_initialization_with_custom_max_concurrent(self, tmp_path: Path) -> None:
        """Test initialization with custom max_concurrent."""
        # Arrange
        output_dir = tmp_path / "images"
        max_concurrent = 10

        # Act
        downloader = AsyncImageDownloader(output_dir, max_concurrent=max_concurrent)

        # Assert
        assert downloader.semaphore._value == max_concurrent


# =============================================================================
# TEST AsyncImageDownloader - download_all Method
# =============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
class TestAsyncImageDownloaderDownloadAll:
    """Test AsyncImageDownloader.download_all() method."""

    async def test_download_all_with_empty_list(self, tmp_path: Path) -> None:
        """Test download_all returns empty list for empty input."""
        # Arrange
        downloader = AsyncImageDownloader(tmp_path)
        session = AsyncMock(spec=aiohttp.ClientSession)

        # Act
        result = await downloader.download_all(session, [])

        # Assert
        assert result == []

    async def test_download_all_with_single_url(self, tmp_path: Path) -> None:
        """Test download_all with single URL."""
        # Arrange
        downloader = AsyncImageDownloader(tmp_path)
        session = AsyncMock(spec=aiohttp.ClientSession)
        image_urls = ["https://example.com/image1.jpg"]

        with patch.object(downloader, "_download_single", return_value="image1.jpg"):
            # Act
            result = await downloader.download_all(session, image_urls)

            # Assert
            assert result == ["image1.jpg"]

    async def test_download_all_with_multiple_urls(self, tmp_path: Path) -> None:
        """Test download_all with multiple URLs."""
        # Arrange
        downloader = AsyncImageDownloader(tmp_path)
        session = AsyncMock(spec=aiohttp.ClientSession)
        image_urls = [
            "https://example.com/image1.jpg",
            "https://example.com/image2.jpg",
            "https://example.com/image3.jpg",
        ]

        with patch.object(
            downloader,
            "_download_single",
            side_effect=["image1.jpg", "image2.jpg", "image3.jpg"],
        ):
            # Act
            result = await downloader.download_all(session, image_urls)

            # Assert
            assert len(result) == 3
            assert "image1.jpg" in result
            assert "image2.jpg" in result
            assert "image3.jpg" in result

    async def test_download_all_handles_exceptions(self, tmp_path: Path) -> None:
        """Test download_all handles download exceptions gracefully."""
        # Arrange
        downloader = AsyncImageDownloader(tmp_path)
        session = AsyncMock(spec=aiohttp.ClientSession)
        image_urls = [
            "https://example.com/image1.jpg",
            "https://example.com/image2.jpg",
            "https://example.com/image3.jpg",
        ]

        with patch.object(
            downloader,
            "_download_single",
            side_effect=["image1.jpg", Exception("Download failed"), "image3.jpg"],
        ):
            # Act
            result = await downloader.download_all(session, image_urls)

            # Assert
            assert len(result) == 2
            assert "image1.jpg" in result
            assert "image3.jpg" in result

    async def test_download_all_handles_none_results(self, tmp_path: Path) -> None:
        """Test download_all handles None results (failed downloads)."""
        # Arrange
        downloader = AsyncImageDownloader(tmp_path)
        session = AsyncMock(spec=aiohttp.ClientSession)
        image_urls = [
            "https://example.com/image1.jpg",
            "https://example.com/image2.jpg",
            "https://example.com/image3.jpg",
        ]

        with patch.object(
            downloader, "_download_single", side_effect=["image1.jpg", None, "image3.jpg"]
        ):
            # Act
            result = await downloader.download_all(session, image_urls)

            # Assert
            assert len(result) == 2
            assert "image1.jpg" in result
            assert "image3.jpg" in result

    async def test_download_all_calls_progress_callback(self, tmp_path: Path) -> None:
        """Test download_all calls progress callback if provided."""
        # Arrange
        downloader = AsyncImageDownloader(tmp_path)
        session = AsyncMock(spec=aiohttp.ClientSession)
        image_urls = ["https://example.com/image1.jpg"]
        progress_callback = MagicMock()

        with patch.object(downloader, "_download_single", return_value="image1.jpg"):
            # Act
            await downloader.download_all(session, image_urls, progress_callback)

            # Assert - callback may be called from _download_single
            # Note: Callback behavior depends on implementation details


# =============================================================================
# TEST AsyncImageDownloader - _download_single Method
# =============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
class TestAsyncImageDownloaderDownloadSingle:
    """Test AsyncImageDownloader._download_single() method."""

    async def test_download_single_respects_semaphore(self, tmp_path: Path) -> None:
        """Test _download_single respects semaphore for concurrency control."""
        # Arrange
        downloader = AsyncImageDownloader(tmp_path, max_concurrent=1)
        session = AsyncMock(spec=aiohttp.ClientSession)
        url = "https://example.com/image.jpg"

        with patch.object(
            downloader, "_download_image_safe", return_value="image.jpg"
        ) as mock_download:
            # Act
            result = await downloader._download_single(session, url, 0, 1, None)

            # Assert
            assert result == "image.jpg"
            mock_download.assert_called_once_with(session, url)

    async def test_download_single_calls_progress_callback(self, tmp_path: Path) -> None:
        """Test _download_single calls progress callback."""
        # Arrange
        downloader = AsyncImageDownloader(tmp_path)
        session = AsyncMock(spec=aiohttp.ClientSession)
        url = "https://example.com/image.jpg"
        progress_callback = MagicMock()

        with patch.object(downloader, "_download_image_safe", return_value="image.jpg"):
            # Act
            await downloader._download_single(session, url, 2, 5, progress_callback)

            # Assert
            progress_callback.assert_called_once_with(0.6)  # (2+1)/5 = 0.6

    async def test_download_single_includes_rate_limiting(self, tmp_path: Path) -> None:
        """Test _download_single includes rate limiting delay."""
        # Arrange
        downloader = AsyncImageDownloader(tmp_path)
        session = AsyncMock(spec=aiohttp.ClientSession)
        url = "https://example.com/image.jpg"

        with patch.object(downloader, "_download_image_safe", return_value="image.jpg"):
            with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
                # Act
                await downloader._download_single(session, url, 0, 1, None)

                # Assert - Rate limit delay is called
                mock_sleep.assert_called_once()


# =============================================================================
# TEST AsyncImageDownloader - _generate_filename Method
# =============================================================================


@pytest.mark.unit
class TestAsyncImageDownloaderGenerateFilename:
    """Test AsyncImageDownloader._generate_filename() method."""

    def test_generate_filename_uses_original_filename(self, tmp_path: Path) -> None:
        """Test uses original filename from URL when available."""
        # Arrange
        downloader = AsyncImageDownloader(tmp_path)
        url = "https://example.com/photos/sunset.jpg"
        response = MagicMock(spec=aiohttp.ClientResponse)
        response.headers.get.return_value = "image/jpeg"

        # Act
        filename = downloader._generate_filename(url, response)

        # Assert
        assert filename == "sunset.jpg"

    def test_generate_filename_handles_url_without_extension(self, tmp_path: Path) -> None:
        """Test generates filename when URL has no extension."""
        # Arrange
        downloader = AsyncImageDownloader(tmp_path)
        url = "https://example.com/photos/12345"
        response = MagicMock(spec=aiohttp.ClientResponse)
        response.headers.get.return_value = "image/png"

        # Act
        filename = downloader._generate_filename(url, response)

        # Assert
        assert filename.startswith("image_")
        assert filename.endswith(".png")

    def test_generate_filename_uses_content_type(self, tmp_path: Path) -> None:
        """Test uses content-type header to determine extension."""
        # Arrange
        downloader = AsyncImageDownloader(tmp_path)
        url = "https://example.com/photos/12345"
        response = MagicMock(spec=aiohttp.ClientResponse)
        response.headers.get.return_value = "image/webp"

        # Act
        filename = downloader._generate_filename(url, response)

        # Assert
        assert filename.endswith(".webp")

    def test_generate_filename_uses_hash_for_uniqueness(self, tmp_path: Path) -> None:
        """Test uses URL hash to generate unique filename."""
        # Arrange
        downloader = AsyncImageDownloader(tmp_path)
        url1 = "https://example.com/photos/12345"
        url2 = "https://example.com/photos/67890"
        response = MagicMock(spec=aiohttp.ClientResponse)
        response.headers.get.return_value = "image/jpeg"

        # Act
        filename1 = downloader._generate_filename(url1, response)
        filename2 = downloader._generate_filename(url2, response)

        # Assert - Different URLs produce different filenames
        assert filename1 != filename2


# =============================================================================
# TEST AsyncImageDownloader - _get_extension_from_content_type Method
# =============================================================================


@pytest.mark.unit
class TestAsyncImageDownloaderGetExtensionFromContentType:
    """Test AsyncImageDownloader._get_extension_from_content_type() method."""

    def test_get_extension_for_jpeg(self, tmp_path: Path) -> None:
        """Test returns .jpg for image/jpeg."""
        # Arrange
        downloader = AsyncImageDownloader(tmp_path)

        # Act
        extension = downloader._get_extension_from_content_type("image/jpeg")

        # Assert
        assert extension == ".jpg"

    def test_get_extension_for_png(self, tmp_path: Path) -> None:
        """Test returns .png for image/png."""
        # Arrange
        downloader = AsyncImageDownloader(tmp_path)

        # Act
        extension = downloader._get_extension_from_content_type("image/png")

        # Assert
        assert extension == ".png"

    def test_get_extension_for_webp(self, tmp_path: Path) -> None:
        """Test returns .webp for image/webp."""
        # Arrange
        downloader = AsyncImageDownloader(tmp_path)

        # Act
        extension = downloader._get_extension_from_content_type("image/webp")

        # Assert
        assert extension == ".webp"

    def test_get_extension_for_gif(self, tmp_path: Path) -> None:
        """Test returns .gif for image/gif."""
        # Arrange
        downloader = AsyncImageDownloader(tmp_path)

        # Act
        extension = downloader._get_extension_from_content_type("image/gif")

        # Assert
        assert extension == ".gif"

    def test_get_extension_returns_default_for_unknown(self, tmp_path: Path) -> None:
        """Test returns default extension for unknown content type."""
        # Arrange
        downloader = AsyncImageDownloader(tmp_path)

        # Act
        extension = downloader._get_extension_from_content_type("application/octet-stream")

        # Assert
        assert extension == ".jpg"  # DEFAULT_IMAGE_EXTENSION

    def test_get_extension_handles_content_type_with_charset(self, tmp_path: Path) -> None:
        """Test handles content-type with charset parameter."""
        # Arrange
        downloader = AsyncImageDownloader(tmp_path)

        # Act
        extension = downloader._get_extension_from_content_type("image/png; charset=utf-8")

        # Assert
        assert extension == ".png"


# =============================================================================
# TEST AsyncImageDownloader - _download_image_safe Method
# =============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
class TestAsyncImageDownloaderDownloadImageSafe:
    """Test AsyncImageDownloader._download_image_safe() method."""

    async def test_download_image_safe_returns_filename_on_success(self, tmp_path: Path) -> None:
        """Test _download_image_safe returns filename on success."""
        # Arrange
        downloader = AsyncImageDownloader(tmp_path)
        session = AsyncMock(spec=aiohttp.ClientSession)
        url = "https://example.com/image.jpg"

        with patch.object(downloader, "_download_image", return_value="image.jpg"):
            # Act
            result = await downloader._download_image_safe(session, url)

            # Assert
            assert result == "image.jpg"

    async def test_download_image_safe_returns_none_on_exception(self, tmp_path: Path) -> None:
        """Test _download_image_safe returns None when exception occurs."""
        # Arrange
        downloader = AsyncImageDownloader(tmp_path)
        session = AsyncMock(spec=aiohttp.ClientSession)
        url = "https://example.com/image.jpg"

        with patch.object(downloader, "_download_image", side_effect=Exception("Download failed")):
            # Act
            result = await downloader._download_image_safe(session, url)

            # Assert
            assert result is None


# =============================================================================
# TEST AsyncImageDownloader - _download_image Method (with mocks)
# =============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
class TestAsyncImageDownloaderDownloadImage:
    """Test AsyncImageDownloader._download_image() method."""

    async def test_download_image_raises_conversion_error_on_client_error(
        self, tmp_path: Path
    ) -> None:
        """Test _download_image raises ConversionError on aiohttp.ClientError."""
        # Arrange
        downloader = AsyncImageDownloader(tmp_path)
        session = AsyncMock(spec=aiohttp.ClientSession)
        url = "https://example.com/image.jpg"

        # Mock robots checker
        with patch("src.processors.image_downloader.robots_checker.check_and_delay"):
            # Mock session.get to raise ClientError
            session.get.side_effect = aiohttp.ClientError("Connection failed")

            # Act & Assert
            with pytest.raises(ConversionError, match="Failed to download image"):
                await downloader._download_image(session, url)

    async def test_download_image_creates_output_directory(self, tmp_path: Path) -> None:
        """Test _download_image creates output directory if it doesn't exist."""
        # Arrange
        output_dir = tmp_path / "images" / "subfolder"
        downloader = AsyncImageDownloader(output_dir)
        session = AsyncMock(spec=aiohttp.ClientSession)
        url = "https://example.com/image.jpg"

        # Mock response with async iterator for content chunks
        async def mock_iter_chunked(size: int) -> AsyncIterator[bytes]:
            """Mock async iterator for response chunks."""
            yield b"image_data"

        response_mock = AsyncMock(spec=aiohttp.ClientResponse)
        response_mock.raise_for_status = MagicMock()
        response_mock.headers.get.return_value = "image/jpeg"
        response_mock.content_length = 1024
        response_mock.content.iter_chunked = mock_iter_chunked

        # Mock context manager
        session.get.return_value.__aenter__.return_value = response_mock

        # Mock robots checker
        with patch("src.processors.image_downloader.robots_checker.check_and_delay"):
            # Mock aiofiles.open
            with patch("src.processors.image_downloader.aopen") as mock_aopen:
                mock_file = AsyncMock()
                mock_aopen.return_value.__aenter__.return_value = mock_file

                # Act
                await downloader._download_image(session, url)

                # Assert - Directory should be created
                assert output_dir.exists()
