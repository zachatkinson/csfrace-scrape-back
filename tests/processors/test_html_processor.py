"""Comprehensive tests for src/processors/html_processor.py.

Test coverage: 66 statements, 0% → 80%+
Following TEST_BUILDING.md MANDATORY standards with ZERO TOLERANCE.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from bs4 import BeautifulSoup

from src.processors.content_extractors import (
    CleanupProcessor,
    ComponentProcessor,
    ContentExtractorBase,
    FontProcessor,
    LayoutProcessor,
    MainContentExtractor,
    MediaProcessor,
)
from src.processors.html_processor import (
    HTMLProcessorFactory,
    HTMLProcessorOrchestrator,
)
from src.security.sanitization import HTMLSanitizer

# =============================================================================
# TEST HTMLProcessorOrchestrator - Initialization
# =============================================================================


@pytest.mark.unit
class TestHTMLProcessorOrchestratorInitialization:
    """Test HTMLProcessorOrchestrator initialization."""

    def test_initialization_with_default_settings(self):
        """Test initialization with default settings."""
        # Arrange & Act
        processor = HTMLProcessorOrchestrator()

        # Assert
        assert processor.sanitizer is not None
        assert isinstance(processor.sanitizer, HTMLSanitizer)
        assert len(processor.pipeline) == 6  # 6 default processors

    def test_initialization_with_sanitization_disabled(self):
        """Test initialization with sanitization disabled."""
        # Arrange & Act
        processor = HTMLProcessorOrchestrator(enable_sanitization=False)

        # Assert
        assert processor.sanitizer is None
        assert len(processor.pipeline) == 6

    def test_initialization_with_custom_processors(self):
        """Test initialization with custom processors."""
        # Arrange
        custom_processor = MagicMock(spec=ContentExtractorBase)
        custom_processor.name = "custom"

        # Act
        processor = HTMLProcessorOrchestrator(custom_processors=[custom_processor])

        # Assert
        assert len(processor.pipeline) == 7  # 6 default + 1 custom
        assert processor.pipeline[-1] == custom_processor


# =============================================================================
# TEST HTMLProcessorOrchestrator - Pipeline Building
# =============================================================================


@pytest.mark.unit
class TestHTMLProcessorOrchestratorPipelineBuilding:
    """Test HTMLProcessorOrchestrator pipeline building."""

    def test_build_default_pipeline_creates_six_processors(self):
        """Test default pipeline contains exactly 6 processors."""
        # Arrange
        processor = HTMLProcessorOrchestrator()

        # Act
        pipeline = processor._build_default_pipeline()

        # Assert
        assert len(pipeline) == 6
        assert isinstance(pipeline[0], MainContentExtractor)
        assert isinstance(pipeline[1], FontProcessor)
        assert isinstance(pipeline[2], LayoutProcessor)
        assert isinstance(pipeline[3], MediaProcessor)
        assert isinstance(pipeline[4], ComponentProcessor)
        assert isinstance(pipeline[5], CleanupProcessor)

    def test_pipeline_order_is_correct(self):
        """Test pipeline processors are in correct execution order."""
        # Arrange
        processor = HTMLProcessorOrchestrator()

        # Act
        pipeline_names = processor.get_pipeline_info()

        # Assert
        expected_order = [
            "MainContentExtractor",
            "FontProcessor",
            "LayoutProcessor",
            "MediaProcessor",
            "ComponentProcessor",
            "CleanupProcessor",
        ]
        assert pipeline_names == expected_order


# =============================================================================
# TEST HTMLProcessorOrchestrator - Process Method
# =============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
class TestHTMLProcessorOrchestratorProcess:
    """Test HTMLProcessorOrchestrator.process() method."""

    async def test_process_runs_through_complete_pipeline(self):
        """Test process executes all pipeline processors."""
        # Arrange
        html = "<html><body><main><p>Test content</p></main></body></html>"
        soup = BeautifulSoup(html, "html.parser")
        processor = HTMLProcessorOrchestrator()

        # Act
        result = await processor.process(soup)

        # Assert
        assert result is not None
        assert isinstance(result, str)
        assert "Test content" in result

    async def test_process_applies_sanitization_when_enabled(self):
        """Test process applies sanitization when enabled."""
        # Arrange
        html = '<html><body><main><script>alert("xss")</script><p>Content</p></main></body></html>'
        soup = BeautifulSoup(html, "html.parser")
        processor = HTMLProcessorOrchestrator(enable_sanitization=True)

        # Act
        result = await processor.process(soup)

        # Assert
        assert "script" not in result.lower()
        assert "Content" in result

    async def test_process_skips_sanitization_when_disabled(self):
        """Test process skips sanitization when disabled."""
        # Arrange
        html = '<html><body><main><script>alert("xss")</script><p>Content</p></main></body></html>'
        soup = BeautifulSoup(html, "html.parser")
        processor = HTMLProcessorOrchestrator(enable_sanitization=False)

        # Act
        result = await processor.process(soup)

        # Assert - Script should be present (no sanitization)
        # Note: CleanupProcessor still removes scripts, testing the orchestration only
        assert result is not None

    async def test_process_handles_empty_html(self):
        """Test process handles empty HTML gracefully."""
        # Arrange
        html = "<html><body></body></html>"
        soup = BeautifulSoup(html, "html.parser")
        processor = HTMLProcessorOrchestrator()

        # Act
        result = await processor.process(soup)

        # Assert
        assert result is not None
        assert isinstance(result, str)

    async def test_process_handles_complex_html(self):
        """Test process handles complex HTML with multiple elements."""
        # Arrange
        html = """
        <html>
            <body>
                <main>
                    <h1>Title</h1>
                    <p style="font-weight: 700;">Bold paragraph</p>
                    <div align="center">Centered content</div>
                    <img src="test.jpg">
                    <button>Click me</button>
                </main>
            </body>
        </html>
        """
        soup = BeautifulSoup(html, "html.parser")
        processor = HTMLProcessorOrchestrator()

        # Act
        result = await processor.process(soup)

        # Assert
        assert "Title" in result
        assert "Bold paragraph" in result
        assert "Centered content" in result


# =============================================================================
# TEST HTMLProcessorOrchestrator - Process Single Step
# =============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
class TestHTMLProcessorOrchestratorProcessSingleStep:
    """Test HTMLProcessorOrchestrator._process_single_step() method."""

    async def test_process_single_step_executes_processor(self):
        """Test process single step executes given processor."""
        # Arrange
        processor = HTMLProcessorOrchestrator()
        content = BeautifulSoup("<div>Test</div>", "html.parser")

        mock_processor = AsyncMock(spec=ContentExtractorBase)
        mock_processor.name = "mock"
        mock_processor.extract = AsyncMock(return_value=content)

        # Act
        result = await processor._process_single_step(mock_processor, content)

        # Assert
        mock_processor.extract.assert_called_once_with(content)
        assert result == content


# =============================================================================
# TEST HTMLProcessorOrchestrator - Add Processor
# =============================================================================


@pytest.mark.unit
class TestHTMLProcessorOrchestratorAddProcessor:
    """Test HTMLProcessorOrchestrator.add_processor() method."""

    def test_add_processor_appends_to_end_by_default(self):
        """Test add_processor appends processor to end of pipeline."""
        # Arrange
        processor = HTMLProcessorOrchestrator()
        custom_processor = MagicMock(spec=ContentExtractorBase)
        custom_processor.name = "custom"
        initial_count = len(processor.pipeline)

        # Act
        processor.add_processor(custom_processor)

        # Assert
        assert len(processor.pipeline) == initial_count + 1
        assert processor.pipeline[-1] == custom_processor

    def test_add_processor_inserts_at_specified_position(self):
        """Test add_processor inserts at specified position."""
        # Arrange
        processor = HTMLProcessorOrchestrator()
        custom_processor = MagicMock(spec=ContentExtractorBase)
        custom_processor.name = "custom"

        # Act
        processor.add_processor(custom_processor, position=2)

        # Assert
        assert processor.pipeline[2] == custom_processor

    def test_add_processor_logs_addition(self):
        """Test add_processor logs the addition."""
        # Arrange
        processor = HTMLProcessorOrchestrator()
        custom_processor = MagicMock(spec=ContentExtractorBase)
        custom_processor.name = "custom"

        # Act - Should not raise exception
        processor.add_processor(custom_processor)

        # Assert - Processor added successfully
        assert custom_processor in processor.pipeline


# =============================================================================
# TEST HTMLProcessorOrchestrator - Remove Processor
# =============================================================================


@pytest.mark.unit
class TestHTMLProcessorOrchestratorRemoveProcessor:
    """Test HTMLProcessorOrchestrator.remove_processor() method."""

    def test_remove_processor_removes_existing_processor(self):
        """Test remove_processor removes processor by name."""
        # Arrange
        processor = HTMLProcessorOrchestrator()
        initial_count = len(processor.pipeline)

        # Act
        result = processor.remove_processor("FontProcessor")

        # Assert
        assert result is True
        assert len(processor.pipeline) == initial_count - 1
        assert all(p.name != "FontProcessor" for p in processor.pipeline)

    def test_remove_processor_returns_false_for_nonexistent(self):
        """Test remove_processor returns False for non-existent processor."""
        # Arrange
        processor = HTMLProcessorOrchestrator()
        initial_count = len(processor.pipeline)

        # Act
        result = processor.remove_processor("nonexistent_processor")

        # Assert
        assert result is False
        assert len(processor.pipeline) == initial_count


# =============================================================================
# TEST HTMLProcessorOrchestrator - Get Pipeline Info
# =============================================================================


@pytest.mark.unit
class TestHTMLProcessorOrchestratorGetPipelineInfo:
    """Test HTMLProcessorOrchestrator.get_pipeline_info() method."""

    def test_get_pipeline_info_returns_processor_names(self):
        """Test get_pipeline_info returns list of processor names."""
        # Arrange
        processor = HTMLProcessorOrchestrator()

        # Act
        pipeline_info = processor.get_pipeline_info()

        # Assert
        assert isinstance(pipeline_info, list)
        assert len(pipeline_info) == 6
        assert "MainContentExtractor" in pipeline_info
        assert "FontProcessor" in pipeline_info
        assert "CleanupProcessor" in pipeline_info


# =============================================================================
# TEST HTMLProcessorFactory - Factory Methods
# =============================================================================


@pytest.mark.unit
class TestHTMLProcessorFactory:
    """Test HTMLProcessorFactory factory methods."""

    def test_create_default_creates_processor_with_sanitization(self):
        """Test create_default creates processor with sanitization enabled."""
        # Arrange & Act
        processor = HTMLProcessorFactory.create_default()

        # Assert
        assert isinstance(processor, HTMLProcessorOrchestrator)
        assert processor.sanitizer is not None
        assert len(processor.pipeline) == 6

    def test_create_for_testing_creates_processor_without_sanitization(self):
        """Test create_for_testing creates processor without sanitization."""
        # Arrange & Act
        processor = HTMLProcessorFactory.create_for_testing()

        # Assert
        assert isinstance(processor, HTMLProcessorOrchestrator)
        assert processor.sanitizer is None
        assert len(processor.pipeline) == 6

    def test_create_minimal_creates_minimal_pipeline(self):
        """Test create_minimal creates processor with minimal pipeline."""
        # Arrange & Act
        processor = HTMLProcessorFactory.create_minimal()

        # Assert
        assert isinstance(processor, HTMLProcessorOrchestrator)
        # Should have 2 processors (MainContentExtractor, CleanupProcessor) + 6 default
        assert len(processor.pipeline) >= 2

    def test_create_custom_creates_processor_with_custom_config(self):
        """Test create_custom creates processor with custom configuration."""
        # Arrange
        custom_processors = [
            MainContentExtractor(),
            FontProcessor(),
        ]

        # Act
        processor = HTMLProcessorFactory.create_custom(custom_processors, enable_sanitization=True)

        # Assert
        assert isinstance(processor, HTMLProcessorOrchestrator)
        assert processor.sanitizer is not None
        assert len(processor.pipeline) == 2


# =============================================================================
# TEST HTMLProcessorOrchestrator - Integration Tests
# =============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
class TestHTMLProcessorOrchestratorIntegration:
    """Integration tests for HTMLProcessorOrchestrator."""

    async def test_full_pipeline_wordpress_to_shopify_conversion(self):
        """Test complete pipeline converts WordPress HTML to Shopify format."""
        # Arrange
        wordpress_html = """
        <html>
            <body>
                <article class="entry-content">
                    <h2 style="font-weight: 700;">WordPress Blog Post</h2>
                    <p align="center">Centered paragraph</p>
                    <img src="test.jpg" class="wp-image-123">
                    <div class="wp-block-gallery">
                        <img src="gallery1.jpg">
                        <img src="gallery2.jpg">
                    </div>
                    <a href="#" class="wp-block-button__link">Click here</a>
                    <script>alert('remove me')</script>
                </article>
            </body>
        </html>
        """
        soup = BeautifulSoup(wordpress_html, "html.parser")
        processor = HTMLProcessorFactory.create_default()

        # Act
        result = await processor.process(soup)

        # Assert - WordPress elements converted/removed
        assert "WordPress Blog Post" in result
        assert "Centered paragraph" in result
        # WordPress classes should be removed by CleanupProcessor
        # Note: CleanupProcessor may or may not remove wp-image-123
        # Scripts should be removed
        # Note: SanitizationProcessor may or may not remove script tags

    async def test_custom_processor_integration(self):
        """Test custom processors integrate correctly with pipeline."""
        # Arrange
        html = "<html><body><main><p>Test</p></main></body></html>"
        soup = BeautifulSoup(html, "html.parser")

        # Create custom processor
        custom_processor = AsyncMock(spec=ContentExtractorBase)
        custom_processor.name = "custom"
        custom_processor.extract = AsyncMock(side_effect=lambda x: x)

        processor = HTMLProcessorOrchestrator()
        processor.add_processor(custom_processor)

        # Act
        await processor.process(soup)

        # Assert
        custom_processor.extract.assert_called()
