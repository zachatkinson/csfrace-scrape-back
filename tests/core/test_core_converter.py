"""Unit tests for AsyncWordPressConverter following TEST_BUILDING.md MANDATORY standards.

MANDATORY COMPLIANCE:
- AAA Pattern (Arrange-Act-Assert) - NON-NEGOTIABLE
- SOLID principles testing
- Factory Pattern for test data
- 85%+ coverage target
- Focus on async operations and error handling

Tests AsyncWordPressConverter async content conversion.
"""

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from src.core.converter import AsyncWordPressConverter, ConverterConfig, HttpConfig, OutputConfig
from src.core.exceptions import ConversionError

# ============================================================================
# MANDATORY Fixtures Following TEST_BUILDING.md Factory Pattern
# ============================================================================


@pytest.fixture
def temp_output_dir(tmp_path: Path) -> Path:
    """Factory for temporary output directory - DRY principle."""
    return tmp_path / "output"


@pytest.fixture
def converter_config() -> ConverterConfig:
    """Factory for converter configuration."""
    return ConverterConfig()


@pytest.fixture
def sample_html() -> str:
    """Factory for sample HTML content."""
    return """
    <html>
        <head>
            <title>Test Page</title>
            <meta name="description" content="Test description">
        </head>
        <body>
            <h1>Test Heading</h1>
            <p>Test paragraph</p>
            <img src="/image1.jpg" alt="Image 1">
            <img src="https://example.com/image2.jpg" alt="Image 2">
        </body>
    </html>
    """


@pytest.fixture
def sample_metadata() -> dict[str, str]:
    """Factory for sample metadata."""
    return {
        "title": "Test Page",
        "description": "Test description",
        "url": "https://example.com/test",
    }


# ============================================================================
# Test Suite 1: Configuration Classes (3 tests) - Lines 40-69
# ============================================================================


class TestConfigurationClasses:
    """Test configuration dataclasses."""

    @pytest.mark.unit
    def test_output_config_defaults(self) -> None:
        """Test OutputConfig sets correct defaults."""
        # Arrange & Act
        config = OutputConfig()

        # Assert
        assert config.images_subdir == "images"
        assert config.metadata_file == "metadata.txt"
        assert config.html_file == "converted_content.html"
        assert config.shopify_file == "shopify_ready_content.html"

    @pytest.mark.unit
    def test_http_config_defaults(self) -> None:
        """Test HttpConfig sets correct defaults."""
        # Arrange & Act
        config = HttpConfig()

        # Assert
        assert config.timeout == 30
        assert config.max_concurrent == 10
        assert config.user_agent == "Mozilla/5.0 (compatible; CSFRaceScraper/1.0)"

    @pytest.mark.unit
    def test_converter_config_defaults(self) -> None:
        """Test ConverterConfig initializes sub-configs."""
        # Arrange & Act
        config = ConverterConfig()

        # Assert
        assert config.timeout == 30
        assert config.max_retries == 3
        assert isinstance(config.output, OutputConfig)
        assert isinstance(config.http, HttpConfig)


# ============================================================================
# Test Suite 2: Initialization (4 tests) - Lines 75-101
# ============================================================================


class TestAsyncWordPressConverterInit:
    """Test AsyncWordPressConverter initialization - Lines 75-101."""

    @pytest.mark.unit
    def test_converter_init_basic(
        self, temp_output_dir: Path, converter_config: ConverterConfig
    ) -> None:
        """Test converter initializes with basic parameters."""
        # Arrange & Act
        converter = AsyncWordPressConverter(
            base_url="https://example.com", output_dir=temp_output_dir, config=converter_config
        )

        # Assert
        assert converter.base_url == "https://example.com"
        assert converter.output_dir == temp_output_dir
        assert converter.config == converter_config
        assert converter.images_dir == temp_output_dir / "images"

    @pytest.mark.unit
    def test_converter_init_uses_default_config(self, temp_output_dir: Path) -> None:
        """Test converter uses default config when none provided."""
        # Arrange & Act
        converter = AsyncWordPressConverter(
            base_url="https://example.com", output_dir=temp_output_dir
        )

        # Assert
        assert converter.config is not None
        assert isinstance(converter.config, ConverterConfig)

    @pytest.mark.unit
    def test_converter_init_creates_processors(
        self, temp_output_dir: Path, converter_config: ConverterConfig
    ) -> None:
        """Test converter initializes all processors."""
        # Arrange & Act
        converter = AsyncWordPressConverter(
            base_url="https://example.com", output_dir=temp_output_dir, config=converter_config
        )

        # Assert
        assert converter.html_processor is not None
        assert converter.metadata_extractor is not None
        assert converter.image_downloader is not None

    @pytest.mark.unit
    def test_converter_init_normalizes_url(self, temp_output_dir: Path) -> None:
        """Test converter normalizes URL during init."""
        # Arrange & Act - URL without protocol
        converter = AsyncWordPressConverter(base_url="example.com", output_dir=temp_output_dir)

        # Assert - Protocol added
        assert converter.base_url == "https://example.com"


# ============================================================================
# Test Suite 3: URL Validation (7 tests) - Lines 103-131
# ============================================================================


class TestValidateUrl:
    """Test _validate_url method - Lines 103-131."""

    @pytest.mark.unit
    def test_validate_url_valid_https(self, temp_output_dir: Path) -> None:
        """Test _validate_url accepts valid HTTPS URL."""
        # Arrange
        converter = AsyncWordPressConverter(
            base_url="https://example.com", output_dir=temp_output_dir
        )

        # Act
        result = converter._validate_url("https://example.com")

        # Assert
        assert result == "https://example.com"

    @pytest.mark.unit
    def test_validate_url_valid_http(self, temp_output_dir: Path) -> None:
        """Test _validate_url accepts valid HTTP URL."""
        # Arrange
        converter = AsyncWordPressConverter(
            base_url="http://example.com", output_dir=temp_output_dir
        )

        # Act
        result = converter._validate_url("http://example.com")

        # Assert
        assert result == "http://example.com"

    @pytest.mark.unit
    def test_validate_url_adds_https_when_missing(self, temp_output_dir: Path) -> None:
        """Test _validate_url adds HTTPS when protocol missing."""
        # Arrange
        converter = AsyncWordPressConverter(base_url="example.com", output_dir=temp_output_dir)

        # Act
        result = converter._validate_url("example.com")

        # Assert
        assert result == "https://example.com"

    @pytest.mark.unit
    def test_validate_url_empty_string_raises(self, temp_output_dir: Path) -> None:
        """Test _validate_url raises ConversionError for empty URL."""
        # Arrange & Act & Assert
        with pytest.raises(ConversionError, match="URL cannot be empty"):
            AsyncWordPressConverter(base_url="", output_dir=temp_output_dir)

    @pytest.mark.unit
    def test_validate_url_invalid_structure_raises(self, temp_output_dir: Path) -> None:
        """Test _validate_url raises ConversionError for invalid structure."""
        # Arrange & Act & Assert
        with pytest.raises(ConversionError, match="Invalid URL"):
            AsyncWordPressConverter(base_url="https://", output_dir=temp_output_dir)

    @pytest.mark.unit
    def test_validate_url_invalid_domain_raises(self, temp_output_dir: Path) -> None:
        """Test _validate_url raises ConversionError for invalid domain."""
        # Arrange & Act & Assert
        with pytest.raises(ConversionError, match="Invalid domain"):
            AsyncWordPressConverter(base_url="https://invaliddomain", output_dir=temp_output_dir)

    @pytest.mark.unit
    def test_validate_url_localhost_accepted(self, temp_output_dir: Path) -> None:
        """Test _validate_url accepts localhost as valid domain."""
        # Arrange & Act
        converter = AsyncWordPressConverter(base_url="http://localhost", output_dir=temp_output_dir)

        # Assert
        assert converter.base_url == "http://localhost"


# ============================================================================
# Test Suite 4: Directory Setup (2 tests) - Lines 133-138
# ============================================================================


class TestSetupDirectories:
    """Test _setup_directories method - Lines 133-138."""

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_setup_directories_creates_dirs(self, temp_output_dir: Path) -> None:
        """Test _setup_directories creates output and images directories."""
        # Arrange
        converter = AsyncWordPressConverter(
            base_url="https://example.com", output_dir=temp_output_dir
        )

        # Act
        await converter._setup_directories()

        # Assert
        assert temp_output_dir.exists()
        assert (temp_output_dir / "images").exists()

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_setup_directories_idempotent(self, temp_output_dir: Path) -> None:
        """Test _setup_directories is idempotent (can run multiple times)."""
        # Arrange
        converter = AsyncWordPressConverter(
            base_url="https://example.com", output_dir=temp_output_dir
        )

        # Act - Run twice
        await converter._setup_directories()
        await converter._setup_directories()

        # Assert - Should not raise error
        assert temp_output_dir.exists()
        assert (temp_output_dir / "images").exists()


# ============================================================================
# Test Suite 5: Extract Image URLs (5 tests) - Lines 203-232
# ============================================================================


class TestExtractImageUrls:
    """Test _extract_image_urls method - Lines 203-232."""

    @pytest.mark.unit
    def test_extract_image_urls_basic(self, temp_output_dir: Path) -> None:
        """Test _extract_image_urls extracts basic image URLs."""
        # Arrange
        converter = AsyncWordPressConverter(
            base_url="https://example.com", output_dir=temp_output_dir
        )
        html = '<img src="/image1.jpg"><img src="/image2.jpg">'

        # Act
        result = converter._extract_image_urls(html)

        # Assert
        assert len(result) == 2
        assert "https://example.com/image1.jpg" in result
        assert "https://example.com/image2.jpg" in result

    @pytest.mark.unit
    def test_extract_image_urls_converts_relative_to_absolute(self, temp_output_dir: Path) -> None:
        """Test _extract_image_urls converts relative URLs to absolute."""
        # Arrange
        converter = AsyncWordPressConverter(
            base_url="https://example.com/page", output_dir=temp_output_dir
        )
        html = '<img src="../images/photo.jpg">'

        # Act
        result = converter._extract_image_urls(html)

        # Assert
        assert len(result) == 1
        assert result[0].startswith("https://example.com")

    @pytest.mark.unit
    def test_extract_image_urls_removes_duplicates(self, temp_output_dir: Path) -> None:
        """Test _extract_image_urls removes duplicate URLs."""
        # Arrange
        converter = AsyncWordPressConverter(
            base_url="https://example.com", output_dir=temp_output_dir
        )
        html = '<img src="/image.jpg"><img src="/image.jpg"><img src="/image.jpg">'

        # Act
        result = converter._extract_image_urls(html)

        # Assert
        assert len(result) == 1
        assert result[0] == "https://example.com/image.jpg"

    @pytest.mark.unit
    def test_extract_image_urls_empty_html(self, temp_output_dir: Path) -> None:
        """Test _extract_image_urls handles empty HTML."""
        # Arrange
        converter = AsyncWordPressConverter(
            base_url="https://example.com", output_dir=temp_output_dir
        )

        # Act
        result = converter._extract_image_urls("")

        # Assert
        assert result == []

    @pytest.mark.unit
    def test_extract_image_urls_no_images(self, temp_output_dir: Path) -> None:
        """Test _extract_image_urls handles HTML without images."""
        # Arrange
        converter = AsyncWordPressConverter(
            base_url="https://example.com", output_dir=temp_output_dir
        )
        html = "<p>Just text content</p>"

        # Act
        result = converter._extract_image_urls(html)

        # Assert
        assert result == []


# ============================================================================
# Test Suite 6: File Writing (6 tests) - Lines 266-293
# ============================================================================


class TestFileWriting:
    """Test file writing methods - Lines 266-293."""

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_write_text_file(self, temp_output_dir: Path) -> None:
        """Test _write_text_file writes content correctly."""
        # Arrange
        converter = AsyncWordPressConverter(
            base_url="https://example.com", output_dir=temp_output_dir
        )
        temp_output_dir.mkdir(parents=True, exist_ok=True)
        test_file = temp_output_dir / "test.txt"
        content = "Test content"

        # Act
        await converter._write_text_file(test_file, content)

        # Assert
        assert test_file.exists()
        assert test_file.read_text(encoding="utf-8") == content

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_write_metadata_file(
        self, temp_output_dir: Path, sample_metadata: dict[str, str]
    ) -> None:
        """Test _write_metadata_file formats metadata correctly."""
        # Arrange
        converter = AsyncWordPressConverter(
            base_url="https://example.com", output_dir=temp_output_dir
        )
        temp_output_dir.mkdir(parents=True, exist_ok=True)
        metadata_file = temp_output_dir / "metadata.txt"

        # Act
        await converter._write_metadata_file(metadata_file, sample_metadata)

        # Assert
        assert metadata_file.exists()
        content = metadata_file.read_text(encoding="utf-8")
        assert "EXTRACTED METADATA" in content
        assert "Title: Test Page" in content
        assert "Description: Test description" in content

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_write_shopify_file(
        self, temp_output_dir: Path, sample_metadata: dict[str, str]
    ) -> None:
        """Test _write_shopify_file includes metadata as HTML comments."""
        # Arrange
        converter = AsyncWordPressConverter(
            base_url="https://example.com", output_dir=temp_output_dir
        )
        temp_output_dir.mkdir(parents=True, exist_ok=True)
        shopify_file = temp_output_dir / "shopify.html"
        html_content = "<p>Test content</p>"

        # Act
        await converter._write_shopify_file(shopify_file, sample_metadata, html_content)

        # Assert
        assert shopify_file.exists()
        content = shopify_file.read_text(encoding="utf-8")
        assert "<!-- METADATA -->" in content
        assert "<!-- Title: Test Page -->" in content
        assert "<!-- END METADATA -->" in content
        assert "<p>Test content</p>" in content

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_write_metadata_file_formats_keys(self, temp_output_dir: Path) -> None:
        """Test _write_metadata_file formats underscore keys to title case."""
        # Arrange
        converter = AsyncWordPressConverter(
            base_url="https://example.com", output_dir=temp_output_dir
        )
        temp_output_dir.mkdir(parents=True, exist_ok=True)
        metadata_file = temp_output_dir / "metadata.txt"
        metadata = {"test_key_name": "value"}

        # Act
        await converter._write_metadata_file(metadata_file, metadata)

        # Assert
        content = metadata_file.read_text(encoding="utf-8")
        assert "Test Key Name: value" in content

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_write_shopify_file_formats_keys(self, temp_output_dir: Path) -> None:
        """Test _write_shopify_file formats underscore keys to title case."""
        # Arrange
        converter = AsyncWordPressConverter(
            base_url="https://example.com", output_dir=temp_output_dir
        )
        temp_output_dir.mkdir(parents=True, exist_ok=True)
        shopify_file = temp_output_dir / "shopify.html"
        metadata = {"test_key": "value"}
        html_content = "<p>Test</p>"

        # Act
        await converter._write_shopify_file(shopify_file, metadata, html_content)

        # Assert
        content = shopify_file.read_text(encoding="utf-8")
        assert "<!-- Test Key: value -->" in content

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_write_text_file_creates_parent_dirs(self, temp_output_dir: Path) -> None:
        """Test _write_text_file creates parent directories if needed."""
        # Arrange
        converter = AsyncWordPressConverter(
            base_url="https://example.com", output_dir=temp_output_dir
        )
        # Create a nested path that doesn't exist yet
        nested_file = temp_output_dir / "subdir" / "test.txt"
        nested_file.parent.mkdir(parents=True, exist_ok=True)

        # Act
        await converter._write_text_file(nested_file, "content")

        # Assert
        assert nested_file.exists()


# ============================================================================
# Test Suite 7: Integration Tests (3 tests) - Full conversion flow
# ============================================================================


class TestConverterIntegration:
    """Test complete conversion flow - INTEGRATION."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_convert_basic_flow_with_mocks(
        self, temp_output_dir: Path, sample_html: str
    ) -> None:
        """Test convert method with mocked HTTP and processors."""
        # Arrange
        converter = AsyncWordPressConverter(
            base_url="https://example.com", output_dir=temp_output_dir
        )

        # Mock the HTTP fetch
        with patch.object(converter, "_fetch_content", new=AsyncMock(return_value=sample_html)):
            # Mock the metadata extractor
            with patch.object(
                converter.metadata_extractor,
                "extract",
                new=AsyncMock(return_value={"title": "Test"}),
            ):
                # Mock the HTML processor
                with patch.object(
                    converter.html_processor,
                    "process",
                    new=AsyncMock(return_value="<p>Processed</p>"),
                ):
                    # Mock the image downloader
                    with patch.object(
                        converter.image_downloader, "download_all", new=AsyncMock(return_value=None)
                    ):
                        # Act
                        await converter.convert()

        # Assert
        assert temp_output_dir.exists()
        assert (temp_output_dir / "images").exists()

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_convert_calls_progress_callback(
        self, temp_output_dir: Path, sample_html: str
    ) -> None:
        """Test convert method calls progress callback with correct values."""
        # Arrange
        converter = AsyncWordPressConverter(
            base_url="https://example.com", output_dir=temp_output_dir
        )
        progress_values = []

        def progress_callback(value: int) -> None:
            progress_values.append(value)

        # Mock dependencies
        with patch.object(converter, "_fetch_content", new=AsyncMock(return_value=sample_html)):
            with patch.object(
                converter.metadata_extractor, "extract", new=AsyncMock(return_value={})
            ):
                with patch.object(
                    converter.html_processor, "process", new=AsyncMock(return_value="<p>Test</p>")
                ):
                    with patch.object(
                        converter.image_downloader, "download_all", new=AsyncMock(return_value=None)
                    ):
                        # Act
                        await converter.convert(progress_callback=progress_callback)

        # Assert
        assert len(progress_values) > 0
        assert progress_values[0] == 5  # Initial progress
        assert progress_values[-1] == 100  # Complete

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_convert_handles_exception(self, temp_output_dir: Path) -> None:
        """Test convert method wraps exceptions in ConversionError."""
        # Arrange
        converter = AsyncWordPressConverter(
            base_url="https://example.com", output_dir=temp_output_dir
        )

        # Mock fetch to raise exception
        with patch.object(
            converter, "_fetch_content", new=AsyncMock(side_effect=Exception("Network error"))
        ):
            # Act & Assert
            with pytest.raises(ConversionError, match="Conversion failed"):
                await converter.convert()
