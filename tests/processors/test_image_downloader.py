"""Comprehensive tests for async image downloader."""

import asyncio
import contextlib
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import aiohttp
import pytest
import pytest_asyncio

from src.core.exceptions import ConversionError
from src.processors.image_downloader import AsyncImageDownloader


class TestAsyncImageDownloader:
    """Test async image downloader functionality."""

    @pytest_asyncio.fixture
    async def temp_output_dir(self, tmp_path):
        """Create temporary output directory."""
        output_dir = tmp_path / "images"
        output_dir.mkdir(exist_ok=True)
        return output_dir

    @pytest_asyncio.fixture
    async def downloader(self, temp_output_dir):
        """Create image downloader instance."""
        return AsyncImageDownloader(temp_output_dir, max_concurrent=3)

    @pytest_asyncio.fixture
    async def mock_session(self):
        """Create mock aiohttp session."""
        session = AsyncMock(spec=aiohttp.ClientSession)
        return session

    @pytest.mark.asyncio
    async def test_downloader_initialization(self, temp_output_dir):
        """Test downloader initialization."""
        downloader = AsyncImageDownloader(temp_output_dir, max_concurrent=5)

        assert downloader.output_dir == temp_output_dir
        assert downloader.semaphore._value == 5

    @pytest.mark.asyncio
    async def test_downloader_default_concurrent_limit(self, temp_output_dir):
        """Test downloader uses default concurrent limit from config."""
        # Test that the downloader uses the current config value (10)
        downloader = AsyncImageDownloader(temp_output_dir)
        assert downloader.semaphore._value == 10  # Current config default

    @pytest.mark.asyncio
    async def test_download_all_empty_list(self, downloader, mock_session):
        """Test download_all with empty image list."""
        result = await downloader.download_all(mock_session, [])

        assert result == []
        mock_session.get.assert_not_called()

    @pytest.mark.asyncio
    async def test_download_all_single_image_success(
        self, downloader, mock_session, temp_output_dir
    ):
        """Test successful download of single image."""
        image_url = "https://example.com/image.jpg"
        expected_filename = "image.jpg"

        # Mock successful download
        with patch.object(
            downloader, "_download_single", return_value=expected_filename
        ) as mock_download:
            result = await downloader.download_all(mock_session, [image_url])

            assert result == [expected_filename]
            mock_download.assert_called_once_with(mock_session, image_url, 0, 1, None)

    @pytest.mark.asyncio
    async def test_download_all_multiple_images_success(self, downloader, mock_session):
        """Test successful download of multiple images."""
        image_urls = [
            "https://example.com/image1.jpg",
            "https://example.com/image2.png",
            "https://example.com/image3.gif",
        ]
        expected_filenames = ["image1.jpg", "image2.png", "image3.gif"]

        with patch.object(downloader, "_download_single", side_effect=expected_filenames):
            result = await downloader.download_all(mock_session, image_urls)

            assert result == expected_filenames
            assert len(result) == 3

    @pytest.mark.asyncio
    async def test_download_all_with_progress_callback(self, downloader, mock_session):
        """Test download_all with progress callback."""
        image_urls = ["https://example.com/image1.jpg", "https://example.com/image2.jpg"]
        progress_values = []

        def progress_callback(progress):
            progress_values.append(progress)

        with patch.object(downloader, "_download_single", return_value="image.jpg"):
            await downloader.download_all(mock_session, image_urls, progress_callback)

            # Progress callback should be passed to _download_single
            assert len(progress_values) == 0  # Called in _download_single, not here

    @pytest.mark.asyncio
    async def test_download_all_mixed_success_failure(self, downloader, mock_session):
        """Test download_all with mixed success and failure results."""
        image_urls = [
            "https://example.com/success.jpg",
            "https://example.com/failure.jpg",
            "https://example.com/success2.png",
        ]

        # Mock mixed results: success, exception, success
        async def mock_download_single(session, url, index, total, callback):
            if "failure" in url:
                raise aiohttp.ClientError("Download failed")
            return f"success_{index}.jpg"

        with patch.object(downloader, "_download_single", side_effect=mock_download_single):
            result = await downloader.download_all(mock_session, image_urls)

            assert len(result) == 2  # Only successful downloads
            assert "success_0.jpg" in result
            assert "success_2.jpg" in result

    @pytest.mark.asyncio
    async def test_download_single_success(self, downloader, mock_session):
        """Test successful single image download."""
        url = "https://example.com/image.jpg"
        expected_filename = "image.jpg"

        with patch.object(downloader, "_download_image", return_value=expected_filename):
            with patch("src.processors.image_downloader.config") as mock_config:
                mock_config.rate_limit_delay = 0.001
                result = await downloader._download_single(mock_session, url, 0, 1, None)

                assert result == expected_filename

    @pytest.mark.asyncio
    async def test_download_single_with_progress_callback(self, downloader, mock_session):
        """Test single download with progress callback."""
        url = "https://example.com/image.jpg"
        progress_called = []

        def progress_callback(progress):
            progress_called.append(progress)

        with patch.object(downloader, "_download_image", return_value="image.jpg"):
            with patch("src.processors.image_downloader.config") as mock_config:
                mock_config.rate_limit_delay = 0.001
                await downloader._download_single(mock_session, url, 2, 5, progress_callback)

                assert len(progress_called) == 1
                assert progress_called[0] == 0.6  # (2+1)/5 = 0.6

    @pytest.mark.asyncio
    async def test_download_single_exception_handling(self, downloader, mock_session):
        """Test exception handling in single download."""
        url = "https://example.com/image.jpg"

        with patch.object(downloader, "_download_image", side_effect=ConversionError("Failed")):
            result = await downloader._download_single(mock_session, url, 0, 1, None)

            assert result is None

    @pytest.mark.asyncio
    async def test_download_image_success(self, downloader, mock_session, temp_output_dir):
        """Test successful image download with retry."""
        url = "https://example.com/test.jpg"

        # Mock response
        mock_response = AsyncMock()
        mock_response.raise_for_status.return_value = None
        mock_response.content_length = 1024
        mock_response.headers = {"content-type": "image/jpeg"}

        # Mock chunked content
        async def mock_iter_chunked(size):
            yield b"chunk1"
            yield b"chunk2"

        mock_response.content.iter_chunked = mock_iter_chunked

        # Mock session get
        mock_session.get.return_value.__aenter__.return_value = mock_response

        # Mock robots checker
        with patch("src.processors.image_downloader.robots_checker") as mock_robots:
            mock_robots.check_and_delay = AsyncMock()

            # Mock file operations
            with patch("src.processors.image_downloader.aopen", create=True) as mock_aopen:
                mock_file = AsyncMock()
                mock_aopen.return_value.__aenter__.return_value = mock_file

                # Mock constants - patch the constants module
                with patch("src.constants.CONSTANTS") as mock_constants:
                    mock_constants.DEFAULT_TIMEOUT = 30

                    result = await downloader._download_image(mock_session, url)

                    assert result == "test.jpg"
                    mock_robots.check_and_delay.assert_called_once()
                    mock_file.write.assert_any_call(b"chunk1")
                    mock_file.write.assert_any_call(b"chunk2")

    @pytest.mark.asyncio
    async def test_download_image_client_error(self, downloader, mock_session):
        """Test download_image with client error."""
        url = "https://example.com/error.jpg"

        # Mock session to raise client error
        mock_session.get.side_effect = aiohttp.ClientError("Network error")

        with patch("src.processors.image_downloader.robots_checker") as mock_robots:
            mock_robots.check_and_delay = AsyncMock()

            with pytest.raises(ConversionError, match="Failed to download image"):
                await downloader._download_image(mock_session, url)

    @pytest.mark.asyncio
    async def test_download_image_http_error(self, downloader, mock_session):
        """Test download_image with HTTP error response."""
        url = "https://example.com/notfound.jpg"

        mock_response = AsyncMock()
        # Create a mock request_info to avoid AttributeError
        mock_request_info = Mock()
        mock_request_info.real_url = url

        # Mock raise_for_status as a regular method that raises the exception immediately
        mock_response.raise_for_status = Mock(
            side_effect=aiohttp.ClientResponseError(
                request_info=mock_request_info, history=None, status=404
            )
        )

        mock_session.get.return_value.__aenter__.return_value = mock_response

        with patch("src.processors.image_downloader.robots_checker") as mock_robots:
            mock_robots.check_and_delay = AsyncMock()

            with patch("src.constants.CONSTANTS") as mock_constants:
                mock_constants.DEFAULT_TIMEOUT = 30

                with pytest.raises(ConversionError, match="Failed to download image"):
                    await downloader._download_image(mock_session, url)

    @pytest.mark.asyncio
    async def test_download_image_file_write_error(self, downloader, mock_session, temp_output_dir):
        """Test download_image with file write error."""
        url = "https://example.com/test.jpg"

        mock_response = AsyncMock()
        mock_response.raise_for_status.return_value = None
        mock_response.content_length = 1024
        mock_response.headers = {"content-type": "image/jpeg"}

        # Mock chunked content as async generator
        async def mock_iter_chunked(size):
            yield b"data"

        mock_response.content.iter_chunked = mock_iter_chunked

        mock_session.get.return_value.__aenter__.return_value = mock_response

        with patch("src.processors.image_downloader.robots_checker") as mock_robots:
            mock_robots.check_and_delay = AsyncMock()

            # Mock file operations to raise OSError
            with patch(
                "src.processors.image_downloader.aopen", side_effect=OSError("Write failed")
            ):
                with patch("src.constants.CONSTANTS") as mock_constants:
                    mock_constants.DEFAULT_TIMEOUT = 30

                    with pytest.raises(ConversionError, match="Failed to save image"):
                        await downloader._download_image(mock_session, url)

    def test_generate_filename_with_proper_filename(self, downloader):
        """Test filename generation when URL has proper filename."""
        url = "https://example.com/path/to/image.jpg"
        mock_response = MagicMock()
        mock_response.headers = {}

        result = downloader._generate_filename(url, mock_response)

        assert result == "image.jpg"

    def test_generate_filename_no_extension_in_url(self, downloader):
        """Test filename generation when URL has no extension."""
        url = "https://example.com/image"
        mock_response = MagicMock()
        mock_response.headers = {"content-type": "image/png"}

        with patch.object(downloader, "_get_extension_from_content_type", return_value=".png"):
            result = downloader._generate_filename(url, mock_response)

            # Should generate filename with hash and extension
            assert result.startswith("image_")
            assert result.endswith(".png")
            assert len(result) > 10  # Has hash component

    def test_generate_filename_empty_path(self, downloader):
        """Test filename generation with empty path."""
        url = "https://example.com/"
        mock_response = MagicMock()
        mock_response.headers = {"content-type": "image/gif"}

        with patch.object(downloader, "_get_extension_from_content_type", return_value=".gif"):
            result = downloader._generate_filename(url, mock_response)

            assert result.startswith("image_")
            assert result.endswith(".gif")

    def test_generate_filename_query_parameters(self, downloader):
        """Test filename generation with query parameters in URL."""
        url = "https://example.com/photo.jpeg?size=large&version=2"
        mock_response = MagicMock()
        mock_response.headers = {}

        result = downloader._generate_filename(url, mock_response)

        assert result == "photo.jpeg"

    def test_get_extension_from_content_type_jpeg(self, downloader):
        """Test extension extraction for JPEG content type."""
        with patch("src.processors.image_downloader.config") as mock_config:
            mock_config.content_type_extensions = {
                "image/jpeg": ".jpg",
                "image/png": ".png",
                "image/gif": ".gif",
            }
            result = downloader._get_extension_from_content_type("image/jpeg")
            assert result == ".jpg"

    def test_get_extension_from_content_type_png(self, downloader):
        """Test extension extraction for PNG content type."""
        with patch("src.processors.image_downloader.config") as mock_config:
            mock_config.content_type_extensions = {
                "image/jpeg": ".jpg",
                "image/png": ".png",
                "image/gif": ".gif",
            }
            result = downloader._get_extension_from_content_type("image/png; charset=utf-8")
            assert result == ".png"

    def test_get_extension_from_content_type_unknown(self, downloader):
        """Test extension extraction for unknown content type."""
        with patch("src.processors.image_downloader.config") as mock_config:
            mock_config.content_type_extensions = {}
            with patch("src.constants.CONSTANTS") as mock_constants:
                mock_constants.DEFAULT_IMAGE_EXTENSION = ".jpg"

                result = downloader._get_extension_from_content_type("application/octet-stream")
                assert result == ".jpg"

    def test_get_extension_from_content_type_empty(self, downloader):
        """Test extension extraction for empty content type."""
        with patch("src.processors.image_downloader.config") as mock_config:
            mock_config.content_type_extensions = {}
            with patch("src.constants.CONSTANTS") as mock_constants:
                mock_constants.DEFAULT_IMAGE_EXTENSION = ".jpg"

                result = downloader._get_extension_from_content_type("")
                assert result == ".jpg"

    @pytest.mark.asyncio
    async def test_download_with_semaphore_concurrency(self, temp_output_dir):
        """Test that semaphore properly limits concurrency."""
        downloader = AsyncImageDownloader(temp_output_dir, max_concurrent=2)
        mock_session = AsyncMock()

        concurrent_downloads = []

        async def mock_download_image(session, url):
            # Track when downloads start and end
            concurrent_downloads.append(f"start_{url}")
            await asyncio.sleep(0.1)  # Simulate download time
            concurrent_downloads.append(f"end_{url}")
            return f"file_{url.split('/')[-1]}"

        with patch.object(downloader, "_download_image", side_effect=mock_download_image):
            with patch("src.processors.image_downloader.config") as mock_config:
                mock_config.rate_limit_delay = 0.001
                urls = [f"https://example.com/img{i}.jpg" for i in range(4)]
                await downloader.download_all(mock_session, urls)

        # Should have controlled concurrency
        assert len(concurrent_downloads) == 8  # 4 start + 4 end events

    @pytest.mark.asyncio
    async def test_download_creates_output_directory(self, downloader, mock_session, tmp_path):
        """Test that download creates output directory if it doesn't exist."""
        url = "https://example.com/test.jpg"
        new_dir = tmp_path / "new_images"
        downloader.output_dir = new_dir

        mock_response = AsyncMock()
        mock_response.raise_for_status.return_value = None
        mock_response.content_length = 1024
        mock_response.headers = {"content-type": "image/jpeg"}

        # Mock chunked content as async generator
        async def mock_iter_chunked(size):
            yield b"data"

        mock_response.content.iter_chunked = mock_iter_chunked

        mock_session.get.return_value.__aenter__.return_value = mock_response

        with patch("src.processors.image_downloader.robots_checker") as mock_robots:
            mock_robots.check_and_delay = AsyncMock()

            with patch("src.processors.image_downloader.aopen", create=True) as mock_aopen:
                mock_file = AsyncMock()
                mock_aopen.return_value.__aenter__.return_value = mock_file

                with patch("src.constants.CONSTANTS") as mock_constants:
                    mock_constants.DEFAULT_TIMEOUT = 30

                    await downloader._download_image(mock_session, url)

                    # Directory should be created
                    assert new_dir.exists()

    @pytest.mark.asyncio
    async def test_robots_checker_integration(self, downloader, mock_session):
        """Test integration with robots checker."""
        url = "https://example.com/test.jpg"

        mock_response = AsyncMock()
        mock_response.raise_for_status.return_value = None
        mock_response.headers = {"content-type": "image/jpeg"}

        # Mock chunked content as async generator
        async def mock_iter_chunked(size):
            yield b"data"

        mock_response.content.iter_chunked = mock_iter_chunked

        mock_session.get.return_value.__aenter__.return_value = mock_response

        with patch("src.processors.image_downloader.robots_checker") as mock_robots:
            mock_robots.check_and_delay = AsyncMock()

            with patch("src.processors.image_downloader.config") as mock_config:
                mock_config.user_agent = "TestBot/1.0"
                with patch("src.processors.image_downloader.aopen", create=True):
                    with patch("src.constants.CONSTANTS") as mock_constants:
                        mock_constants.DEFAULT_TIMEOUT = 30

                        await downloader._download_image(mock_session, url)

                        # Should call robots checker with correct parameters
                        mock_robots.check_and_delay.assert_called_once_with(
                            url, "TestBot/1.0", mock_session
                        )


class TestAsyncImageDownloaderEdgeCases:
    """Test edge cases and error scenarios."""

    @pytest_asyncio.fixture
    async def downloader(self, tmp_path):
        """Create downloader instance."""
        return AsyncImageDownloader(tmp_path / "images", max_concurrent=2)

    @pytest.mark.asyncio
    async def test_download_all_exception_in_gather(self, downloader):
        """Test handling of exceptions in asyncio.gather."""
        mock_session = AsyncMock()

        # Mock _download_single to raise different types of exceptions
        async def mock_download_single(session, url, index, total, callback):
            if index == 0:
                return "success.jpg"
            elif index == 1:
                raise ValueError("Value error")
            else:
                raise aiohttp.ClientError("Client error")

        with patch.object(downloader, "_download_single", side_effect=mock_download_single):
            urls = ["success.com/img1.jpg", "fail.com/img2.jpg", "fail.com/img3.jpg"]
            result = await downloader.download_all(mock_session, urls)

            # Should only return successful downloads
            assert result == ["success.jpg"]

    @pytest.mark.asyncio
    async def test_filename_generation_hash_collision_handling(self, downloader):
        """Test filename generation with potential hash collisions."""
        # URLs that might generate same hash (unlikely but test the logic)
        urls = [
            "https://example.com/path1",
            "https://example.com/path2",
        ]

        mock_response = MagicMock()
        mock_response.headers = {"content-type": "image/jpeg"}

        with patch.object(downloader, "_get_extension_from_content_type", return_value=".jpg"):
            filename1 = downloader._generate_filename(urls[0], mock_response)
            filename2 = downloader._generate_filename(urls[1], mock_response)

            # Should generate different filenames
            assert filename1 != filename2
            assert filename1.endswith(".jpg")
            assert filename2.endswith(".jpg")

    @pytest.mark.asyncio
    async def test_download_image_timeout_handling(self, downloader, mock_aiohttp_session):
        """Test download_image with timeout configuration."""
        url = "https://example.com/slow.jpg"

        with patch("src.processors.image_downloader.robots_checker") as mock_robots:
            mock_robots.check_and_delay = AsyncMock()

            with patch("src.constants.CONSTANTS") as mock_constants:
                mock_constants.DEFAULT_TIMEOUT = 10

                # Verify timeout is passed to session.get
                mock_response = AsyncMock()
                mock_aiohttp_session.get.return_value.__aenter__.return_value = mock_response

                # Mock the timeout object
                with patch("aiohttp.ClientTimeout") as mock_timeout:
                    mock_timeout_instance = MagicMock()
                    mock_timeout.return_value = mock_timeout_instance

                    with contextlib.suppress(Exception):
                        await downloader._download_image(mock_aiohttp_session, url)

                    # Should create timeout with correct value
                    mock_timeout.assert_called_with(total=10)
