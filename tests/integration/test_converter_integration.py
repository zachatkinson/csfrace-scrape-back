"""Integration tests for the complete conversion pipeline."""

import pytest
from pathlib import Path
from unittest.mock import AsyncMock, patch
import aiohttp

from src.core.converter import AsyncWordPressConverter
from src.core.exceptions import ConversionError, FetchError


class TestAsyncWordPressConverter:
    """Integration tests for the async converter."""
    
    @pytest.mark.integration
    async def test_converter_initialization(self, temp_dir: Path):
        """Test proper initialization of converter components."""
        converter = AsyncWordPressConverter(
            base_url="https://test.example.com/blog/post",
            output_dir=temp_dir
        )
        
        assert converter.base_url == "https://test.example.com/blog/post"
        assert converter.output_dir == temp_dir
        assert converter.images_dir == temp_dir / "images"
        assert converter.html_processor is not None
        assert converter.metadata_extractor is not None
        assert converter.image_downloader is not None
    
    @pytest.mark.integration
    async def test_url_validation(self, temp_dir: Path):
        """Test URL validation during initialization."""
        # Valid URLs should work
        valid_urls = [
            "https://example.com",
            "http://example.com/path",
            "example.com",  # Should add https://
            "example.com/blog/post"
        ]
        
        for url in valid_urls:
            converter = AsyncWordPressConverter(url, temp_dir)
            assert converter.base_url.startswith('http')
        
        # Invalid URLs should raise ConversionError
        invalid_urls = ["", "not-a-url", "://invalid"]
        
        for url in invalid_urls:
            with pytest.raises(ConversionError):
                AsyncWordPressConverter(url, temp_dir)
    
    @pytest.mark.integration
    async def test_directory_setup(self, temp_dir: Path):
        """Test that converter creates necessary directories."""
        converter = AsyncWordPressConverter(
            "https://test.example.com",
            temp_dir / "conversion_output"
        )
        
        await converter._setup_directories()
        
        assert converter.output_dir.exists()
        assert converter.images_dir.exists()
        assert converter.output_dir.is_dir()
        assert converter.images_dir.is_dir()
    
    @pytest.mark.integration
    async def test_complete_conversion_pipeline(self, temp_dir: Path, sample_html: str):
        """Test the complete conversion pipeline with mocked HTTP responses."""
        converter = AsyncWordPressConverter(
            "https://test.example.com/blog/post",
            temp_dir
        )
        
        # Mock the HTTP session and responses
        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_session = AsyncMock()
            mock_session_class.return_value.__aenter__.return_value = mock_session
            
            # Mock main content fetch
            main_response = AsyncMock()
            main_response.status = 200
            main_response.text.return_value = sample_html
            main_response.raise_for_status.return_value = None
            
            # Mock image download responses
            image_response = AsyncMock()
            image_response.status = 200
            image_response.content_length = 1024
            image_response.headers = {'content-type': 'image/jpeg'}
            image_response.content.iter_chunked.return_value = [b'fake image data']
            image_response.raise_for_status.return_value = None
            
            # Configure session to return appropriate responses
            mock_session.get.return_value.__aenter__.side_effect = [
                main_response,  # Main page fetch
                image_response,  # Image download
            ]
            
            # Mock robots.txt checking
            with patch('src.utils.robots.robots_checker.check_and_delay') as mock_robots:
                mock_robots.return_value = None  # Allow all requests
                
                # Run conversion
                await converter.convert()
        
        # Verify output files were created
        assert (converter.output_dir / "metadata.txt").exists()
        assert (converter.output_dir / "converted_content.html").exists()
        assert (converter.output_dir / "shopify_ready_content.html").exists()
        
        # Check metadata content
        metadata_content = (converter.output_dir / "metadata.txt").read_text()
        assert "Test Blog Post" in metadata_content
        assert "A test blog post for unit testing" in metadata_content
        
        # Check converted HTML content
        html_content = (converter.output_dir / "converted_content.html").read_text()
        assert "<strong>" in html_content  # Font formatting converted
        assert "<em>" in html_content
        assert "media-grid-2" in html_content  # Kadence layouts converted
        assert "button--full-width" in html_content  # Buttons converted
        assert "<script>" not in html_content  # Scripts removed
        
        # Check Shopify-ready content
        shopify_content = (converter.output_dir / "shopify_ready_content.html").read_text()
        assert "<!-- METADATA -->" in shopify_content
        assert "<!-- Title: Test Blog Post -->" in shopify_content
        assert "<!-- END METADATA -->" in shopify_content
    
    @pytest.mark.integration
    async def test_fetch_error_handling(self, temp_dir: Path):
        """Test handling of HTTP errors during content fetching."""
        converter = AsyncWordPressConverter(
            "https://nonexistent.example.com/blog/post",
            temp_dir
        )
        
        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_session = AsyncMock()
            mock_session_class.return_value.__aenter__.return_value = mock_session
            
            # Mock HTTP error
            mock_response = AsyncMock()
            mock_response.raise_for_status.side_effect = aiohttp.ClientError("Not found")
            mock_session.get.return_value.__aenter__.return_value = mock_response
            
            # Mock robots.txt to allow request
            with patch('src.utils.robots.robots_checker.check_and_delay'):
                with pytest.raises(FetchError):
                    await converter.convert()
    
    @pytest.mark.integration
    async def test_timeout_handling(self, temp_dir: Path):
        """Test handling of request timeouts."""
        converter = AsyncWordPressConverter(
            "https://slow.example.com/blog/post",
            temp_dir
        )
        
        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_session = AsyncMock()
            mock_session_class.return_value.__aenter__.return_value = mock_session
            
            # Mock timeout error
            mock_session.get.side_effect = aiohttp.ServerTimeoutError("Timeout")
            
            with patch('src.utils.robots.robots_checker.check_and_delay'):
                with pytest.raises(FetchError):
                    await converter.convert()
    
    @pytest.mark.integration
    async def test_progress_callback(self, temp_dir: Path, sample_html: str):
        """Test progress callback functionality."""
        converter = AsyncWordPressConverter(
            "https://test.example.com/blog/post",
            temp_dir
        )
        
        progress_updates = []
        
        def progress_callback(progress: int):
            progress_updates.append(progress)
        
        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_session = AsyncMock()
            mock_session_class.return_value.__aenter__.return_value = mock_session
            
            # Mock successful responses
            main_response = AsyncMock()
            main_response.status = 200
            main_response.text.return_value = sample_html
            main_response.raise_for_status.return_value = None
            
            mock_session.get.return_value.__aenter__.return_value = main_response
            
            with patch('src.utils.robots.robots_checker.check_and_delay'):
                await converter.convert(progress_callback=progress_callback)
        
        # Verify progress updates were made
        assert len(progress_updates) > 0
        assert progress_updates[0] >= 0
        assert progress_updates[-1] == 100
        assert all(0 <= p <= 100 for p in progress_updates)
        assert progress_updates == sorted(progress_updates)  # Should be monotonic
    
    @pytest.mark.integration
    async def test_image_extraction_and_download(self, temp_dir: Path):
        """Test image extraction and download pipeline."""
        html_with_images = """
        <html>
        <head><title>Image Test</title></head>
        <body>
        <div class="entry-content">
            <img src="/image1.jpg" alt="Image 1">
            <img src="https://external.com/image2.png" alt="Image 2">
            <div class="wp-block-image">
                <img src="/nested/image3.webp" alt="Image 3">
            </div>
        </div>
        </body>
        </html>
        """
        
        converter = AsyncWordPressConverter(
            "https://test.example.com/blog/post",
            temp_dir
        )
        
        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_session = AsyncMock()
            mock_session_class.return_value.__aenter__.return_value = mock_session
            
            # Mock main content response
            main_response = AsyncMock()
            main_response.status = 200
            main_response.text.return_value = html_with_images
            main_response.raise_for_status.return_value = None
            
            # Mock image download responses
            image_response = AsyncMock()
            image_response.status = 200
            image_response.content_length = 2048
            image_response.headers = {'content-type': 'image/jpeg'}
            image_response.content.iter_chunked.return_value = [b'image data chunk']
            image_response.raise_for_status.return_value = None
            
            mock_session.get.return_value.__aenter__.side_effect = [
                main_response,  # Main page
                image_response,  # Image 1
                image_response,  # Image 2  
                image_response,  # Image 3
            ]
            
            with patch('src.utils.robots.robots_checker.check_and_delay'):
                await converter.convert()
        
        # Verify images directory was created and contains files
        assert converter.images_dir.exists()
        image_files = list(converter.images_dir.glob('*'))
        assert len(image_files) > 0
        
        # Check that images were converted to absolute URLs
        html_content = (converter.output_dir / "converted_content.html").read_text()
        # Should contain absolute URLs or simplified img tags
        assert 'src=' in html_content
    
    @pytest.mark.integration
    async def test_robots_txt_integration(self, temp_dir: Path):
        """Test integration with robots.txt checking."""
        converter = AsyncWordPressConverter(
            "https://test.example.com/blocked/content",
            temp_dir
        )
        
        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_session = AsyncMock()
            mock_session_class.return_value.__aenter__.return_value = mock_session
            
            # Mock robots.txt that blocks the URL
            from src.core.exceptions import RateLimitError
            with patch('src.utils.robots.robots_checker.check_and_delay') as mock_robots:
                mock_robots.side_effect = RateLimitError("Blocked by robots.txt")
                
                with pytest.raises(RateLimitError):
                    await converter.convert()
    
    @pytest.mark.integration
    async def test_concurrent_operation_safety(self, temp_dir: Path, sample_html: str):
        """Test that converter handles concurrent operations safely."""
        import asyncio
        
        # Create multiple converters for different URLs
        converters = [
            AsyncWordPressConverter(f"https://test{i}.example.com", temp_dir / f"output{i}")
            for i in range(3)
        ]
        
        async def run_conversion(converter, html_content):
            with patch('aiohttp.ClientSession') as mock_session_class:
                mock_session = AsyncMock()
                mock_session_class.return_value.__aenter__.return_value = mock_session
                
                main_response = AsyncMock()
                main_response.status = 200
                main_response.text.return_value = html_content
                main_response.raise_for_status.return_value = None
                
                mock_session.get.return_value.__aenter__.return_value = main_response
                
                with patch('src.utils.robots.robots_checker.check_and_delay'):
                    await converter.convert()
        
        # Run conversions concurrently
        tasks = [run_conversion(converter, sample_html) for converter in converters]
        await asyncio.gather(*tasks)
        
        # Verify all conversions completed successfully
        for i, converter in enumerate(converters):
            output_dir = temp_dir / f"output{i}"
            assert (output_dir / "metadata.txt").exists()
            assert (output_dir / "converted_content.html").exists()
            assert (output_dir / "shopify_ready_content.html").exists()
    
    @pytest.mark.integration
    @pytest.mark.slow
    async def test_large_content_handling(self, temp_dir: Path):
        """Test handling of large content files."""
        # Create large HTML content
        large_content = f"""
        <html>
        <head><title>Large Content Test</title></head>
        <body>
        <div class="entry-content">
        {'<p>This is paragraph content. ' * 1000}
        {'<img src="/image{}.jpg" alt="Image {}">'.format(i, i) for i in range(50)}
        </p>
        </div>
        </body>
        </html>
        """
        
        converter = AsyncWordPressConverter(
            "https://test.example.com/large-content",
            temp_dir
        )
        
        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_session = AsyncMock()
            mock_session_class.return_value.__aenter__.return_value = mock_session
            
            main_response = AsyncMock()
            main_response.status = 200
            main_response.text.return_value = large_content
            main_response.raise_for_status.return_value = None
            
            # Mock image responses
            image_response = AsyncMock()
            image_response.status = 200
            image_response.content_length = 5120
            image_response.headers = {'content-type': 'image/jpeg'}
            image_response.content.iter_chunked.return_value = [b'x' * 1024 for _ in range(5)]
            image_response.raise_for_status.return_value = None
            
            mock_session.get.return_value.__aenter__.side_effect = (
                [main_response] + [image_response] * 50
            )
            
            with patch('src.utils.robots.robots_checker.check_and_delay'):
                await converter.convert()
        
        # Verify large content was processed successfully
        html_content = (converter.output_dir / "converted_content.html").read_text()
        assert len(html_content) > 1000  # Should be substantial content
        
        # Verify images were processed
        assert converter.images_dir.exists()
        image_files = list(converter.images_dir.glob('*'))
        assert len(image_files) > 0