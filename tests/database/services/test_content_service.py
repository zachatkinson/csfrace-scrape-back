"""Comprehensive test suite for ContentService following TEST_BUILDING.md standards.

This module tests all content-related database operations:
- Saving content results (create/update)
- Retrieving content by job
- Getting content metadata
- Deleting content
- Edge cases and error handling
"""

import pytest

from src.core.exceptions import ValidationError
from src.database.models.auth import (
    User,  # noqa: F401 - Import at module level for test_database_engine
)
from src.database.services.content_service import ContentService
from src.database.services.job_service import JobService
from tests.conftest import JobFactory


class TestContentServiceCreation:
    """Test content creation operations."""

    @pytest.mark.database
    def test_save_content_result_creates_new(self, test_session):
        """Test saving new content result."""
        # Arrange
        job_service = JobService(test_session)
        job_request = JobFactory.create_job_request(session=test_session)
        job = job_service.create_job(job_request)
        test_session.commit()
        service = ContentService(test_session)

        content = "<html><body>Test content</body></html>"
        metadata = {
            "title": "Test Title",
            "author": "Test Author",
            "word_count": 100,
            "image_count": 5,
            "link_count": 10,
            "html_file_path": "/tmp/test.html",
        }

        # Act
        result = service.save_content_result(
            job_id=job.id, content=content, content_type="converted", metadata=metadata
        )
        test_session.commit()

        # Assert
        assert result is not None
        assert result.job_id == job.id
        assert result.converted_html == content
        assert result.title == "Test Title"
        assert result.author == "Test Author"
        assert result.word_count == 100
        assert result.image_count == 5
        assert result.link_count == 10
        assert result.html_file_path == "/tmp/test.html"
        assert result.created_at is not None

    @pytest.mark.database
    def test_save_content_result_original_type(self, test_session):
        """Test saving original HTML content."""
        # Arrange
        job_service = JobService(test_session)
        job_request = JobFactory.create_job_request(session=test_session)
        job = job_service.create_job(job_request)
        test_session.commit()
        service = ContentService(test_session)

        content = "<html><body>Original</body></html>"

        # Act
        result = service.save_content_result(
            job_id=job.id, content=content, content_type="original"
        )
        test_session.commit()

        # Assert
        assert result.original_html == content
        assert result.converted_html is None
        assert result.shopify_html is None

    @pytest.mark.database
    def test_save_content_result_shopify_type(self, test_session):
        """Test saving Shopify-formatted content."""
        # Arrange
        job_service = JobService(test_session)
        job_request = JobFactory.create_job_request(session=test_session)
        job = job_service.create_job(job_request)
        test_session.commit()
        service = ContentService(test_session)

        content = "<div class='shopify-content'>Test</div>"

        # Act
        result = service.save_content_result(job_id=job.id, content=content, content_type="shopify")
        test_session.commit()

        # Assert
        assert result.shopify_html == content
        assert result.converted_html is None
        assert result.original_html is None

    @pytest.mark.database
    def test_save_content_result_default_type(self, test_session):
        """Test saving content with default type (converted)."""
        # Arrange
        job_service = JobService(test_session)
        job_request = JobFactory.create_job_request(session=test_session)
        job = job_service.create_job(job_request)
        test_session.commit()
        service = ContentService(test_session)

        content = "<html><body>Default type</body></html>"

        # Act
        result = service.save_content_result(
            job_id=job.id, content=content, content_type="unknown_type"
        )
        test_session.commit()

        # Assert
        # Unknown types default to converted_html
        assert result.converted_html == content

    @pytest.mark.database
    def test_save_content_result_with_minimal_metadata(self, test_session):
        """Test saving content with minimal metadata."""
        # Arrange
        job_service = JobService(test_session)
        job_request = JobFactory.create_job_request(session=test_session)
        job = job_service.create_job(job_request)
        test_session.commit()
        service = ContentService(test_session)

        content = "<html><body>Minimal</body></html>"

        # Act
        result = service.save_content_result(
            job_id=job.id, content=content, content_type="converted", metadata={}
        )
        test_session.commit()

        # Assert
        assert result.converted_html == content
        assert result.title is None
        assert result.author is None

    @pytest.mark.database
    def test_save_content_result_with_null_metadata(self, test_session):
        """Test saving content with None metadata."""
        # Arrange
        job_service = JobService(test_session)
        job_request = JobFactory.create_job_request(session=test_session)
        job = job_service.create_job(job_request)
        test_session.commit()
        service = ContentService(test_session)

        content = "<html><body>No metadata</body></html>"

        # Act
        result = service.save_content_result(
            job_id=job.id, content=content, content_type="converted", metadata=None
        )
        test_session.commit()

        # Assert
        assert result.converted_html == content
        assert result.extra_metadata == {}

    @pytest.mark.database
    def test_save_content_result_empty_content_allowed(self, test_session):
        """Test saving empty content (allowed for minimal saves)."""
        # Arrange
        job_service = JobService(test_session)
        job_request = JobFactory.create_job_request(session=test_session)
        job = job_service.create_job(job_request)
        test_session.commit()
        service = ContentService(test_session)

        # Act
        result = service.save_content_result(job_id=job.id, content=None, content_type="converted")
        test_session.commit()

        # Assert
        assert result.converted_html is None
        assert result.job_id == job.id


class TestContentServiceUpdates:
    """Test content update operations."""

    @pytest.mark.database
    def test_save_content_result_updates_existing(self, test_session):
        """Test updating existing content result."""
        # Arrange
        job_service = JobService(test_session)
        job_request = JobFactory.create_job_request(session=test_session)
        job = job_service.create_job(job_request)
        test_session.commit()
        service = ContentService(test_session)

        # Create initial content
        initial_content = "<html><body>Initial</body></html>"
        result1 = service.save_content_result(
            job_id=job.id,
            content=initial_content,
            content_type="converted",
            metadata={"title": "Initial Title"},
        )
        test_session.commit()
        result1_id = result1.id

        # Act - Update with new content
        updated_content = "<html><body>Updated</body></html>"
        result2 = service.save_content_result(
            job_id=job.id,
            content=updated_content,
            content_type="converted",
            metadata={"title": "Updated Title"},
        )
        test_session.commit()

        # Assert
        assert result2.id == result1_id  # Same record updated
        assert result2.converted_html == updated_content
        assert result2.title == "Updated Title"
        assert result2.updated_at is not None

    @pytest.mark.database
    def test_save_content_result_preserves_other_fields_on_update(self, test_session):
        """Test that updating content preserves other fields."""
        # Arrange
        job_service = JobService(test_session)
        job_request = JobFactory.create_job_request(session=test_session)
        job = job_service.create_job(job_request)
        test_session.commit()
        service = ContentService(test_session)

        # Create initial content with metadata
        result1 = service.save_content_result(
            job_id=job.id,
            content="<html>Initial</html>",
            content_type="converted",
            metadata={"title": "Title", "author": "Author", "word_count": 100},
        )
        test_session.commit()

        # Act - Update only title
        result2 = service.save_content_result(
            job_id=job.id,
            content="<html>Updated</html>",
            content_type="converted",
            metadata={"title": "New Title"},
        )
        test_session.commit()

        # Assert
        assert result2.title == "New Title"
        assert result2.author == "Author"  # Preserved
        assert result2.word_count == 100  # Preserved

    @pytest.mark.database
    def test_save_content_result_updates_different_content_types(self, test_session):
        """Test updating different content type fields."""
        # Arrange
        job_service = JobService(test_session)
        job_request = JobFactory.create_job_request(session=test_session)
        job = job_service.create_job(job_request)
        test_session.commit()
        service = ContentService(test_session)

        # Create with original content
        service.save_content_result(
            job_id=job.id, content="<html>Original</html>", content_type="original"
        )
        test_session.commit()

        # Act - Add converted content
        result = service.save_content_result(
            job_id=job.id, content="<html>Converted</html>", content_type="converted"
        )
        test_session.commit()

        # Assert - Both fields should be populated
        assert result.original_html == "<html>Original</html>"
        assert result.converted_html == "<html>Converted</html>"


class TestContentServiceRetrieval:
    """Test content retrieval operations."""

    @pytest.mark.database
    def test_get_content_by_job_found(self, test_session):
        """Test retrieving existing content."""
        # Arrange
        job_service = JobService(test_session)
        job_request = JobFactory.create_job_request(session=test_session)
        job = job_service.create_job(job_request)
        test_session.commit()
        service = ContentService(test_session)

        content = "<html><body>Test</body></html>"
        service.save_content_result(job_id=job.id, content=content, content_type="converted")
        test_session.commit()

        # Act
        result = service.get_content_by_job(job.id)

        # Assert
        assert result is not None
        assert result.job_id == job.id
        assert result.converted_html == content

    @pytest.mark.database
    def test_get_content_by_job_not_found(self, test_session):
        """Test retrieving non-existent content."""
        # Arrange
        service = ContentService(test_session)
        fake_job_id = "00000000-0000-0000-0000-000000000000"

        # Act
        result = service.get_content_by_job(fake_job_id)

        # Assert
        assert result is None

    @pytest.mark.database
    def test_get_content_metadata_found(self, test_session):
        """Test retrieving content metadata."""
        # Arrange
        job_service = JobService(test_session)
        job_request = JobFactory.create_job_request(session=test_session)
        job = job_service.create_job(job_request)
        test_session.commit()
        service = ContentService(test_session)

        metadata_input = {
            "title": "Test Title",
            "author": "Test Author",
            "word_count": 500,
            "image_count": 10,
            "link_count": 20,
        }
        service.save_content_result(
            job_id=job.id,
            content="<html>Content</html>",
            content_type="converted",
            metadata=metadata_input,
        )
        test_session.commit()

        # Act
        metadata = service.get_content_metadata(job.id)

        # Assert
        assert metadata is not None
        assert metadata["job_id"] == job.id
        assert metadata["content_type"] == "converted"
        assert metadata["title"] == "Test Title"
        assert metadata["author"] == "Test Author"
        assert metadata["word_count"] == 500
        assert metadata["image_count"] == 10
        assert metadata["link_count"] == 20
        assert "content_size_bytes" in metadata
        assert metadata["content_size_bytes"] > 0

    @pytest.mark.database
    def test_get_content_metadata_not_found(self, test_session):
        """Test retrieving metadata for non-existent content."""
        # Arrange
        service = ContentService(test_session)
        fake_job_id = "00000000-0000-0000-0000-000000000000"

        # Act
        metadata = service.get_content_metadata(fake_job_id)

        # Assert
        assert metadata is None

    @pytest.mark.database
    def test_get_content_metadata_determines_type_from_original(self, test_session):
        """Test metadata correctly identifies original content type."""
        # Arrange
        job_service = JobService(test_session)
        job_request = JobFactory.create_job_request(session=test_session)
        job = job_service.create_job(job_request)
        test_session.commit()
        service = ContentService(test_session)

        service.save_content_result(
            job_id=job.id, content="<html>Original</html>", content_type="original"
        )
        test_session.commit()

        # Act
        metadata = service.get_content_metadata(job.id)

        # Assert
        assert metadata["content_type"] == "original"
        assert metadata["content_size_bytes"] > 0

    @pytest.mark.database
    def test_get_content_metadata_determines_type_from_shopify(self, test_session):
        """Test metadata correctly identifies Shopify content type."""
        # Arrange
        job_service = JobService(test_session)
        job_request = JobFactory.create_job_request(session=test_session)
        job = job_service.create_job(job_request)
        test_session.commit()
        service = ContentService(test_session)

        service.save_content_result(
            job_id=job.id, content="<div>Shopify</div>", content_type="shopify"
        )
        test_session.commit()

        # Act
        metadata = service.get_content_metadata(job.id)

        # Assert
        assert metadata["content_type"] == "shopify"


class TestContentServiceDeletion:
    """Test content deletion operations."""

    @pytest.mark.database
    def test_delete_content_success(self, test_session):
        """Test successfully deleting content."""
        # Arrange
        job_service = JobService(test_session)
        job_request = JobFactory.create_job_request(session=test_session)
        job = job_service.create_job(job_request)
        test_session.commit()
        service = ContentService(test_session)

        service.save_content_result(
            job_id=job.id, content="<html>Test</html>", content_type="converted"
        )
        test_session.commit()

        # Act
        deleted = service.delete_content(job.id)
        test_session.commit()

        # Assert
        assert deleted is True
        # Verify content no longer exists
        result = service.get_content_by_job(job.id)
        assert result is None

    @pytest.mark.database
    def test_delete_content_not_found(self, test_session):
        """Test deleting non-existent content."""
        # Arrange
        service = ContentService(test_session)
        fake_job_id = "00000000-0000-0000-0000-000000000000"

        # Act
        deleted = service.delete_content(fake_job_id)

        # Assert
        assert deleted is False


class TestContentServiceValidation:
    """Test input validation."""

    @pytest.mark.database
    def test_save_content_result_empty_job_id_raises_error(self, test_session):
        """Test that empty job_id raises ValidationError."""
        # Arrange
        service = ContentService(test_session)

        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            service.save_content_result(job_id="", content="<html>Test</html>")

        assert "Job ID is required" in str(exc_info.value)
        assert exc_info.value.details.get("field") == "job_id"

    @pytest.mark.database
    def test_save_content_result_none_job_id_raises_error(self, test_session):
        """Test that None job_id raises ValidationError."""
        # Arrange
        service = ContentService(test_session)

        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            service.save_content_result(job_id=None, content="<html>Test</html>")

        assert "Job ID is required" in str(exc_info.value)


class TestContentServiceEdgeCases:
    """Test edge cases and special scenarios."""

    @pytest.mark.database
    def test_save_content_with_large_content(self, test_session):
        """Test saving very large content."""
        # Arrange
        job_service = JobService(test_session)
        job_request = JobFactory.create_job_request(session=test_session)
        job = job_service.create_job(job_request)
        test_session.commit()
        service = ContentService(test_session)

        # Create 1MB of content
        large_content = "<html><body>" + ("x" * 1024 * 1024) + "</body></html>"

        # Act
        result = service.save_content_result(
            job_id=job.id, content=large_content, content_type="converted"
        )
        test_session.commit()

        # Assert
        assert result.converted_html == large_content
        assert len(result.converted_html) > 1024 * 1024

    @pytest.mark.database
    def test_save_content_with_unicode_characters(self, test_session):
        """Test saving content with Unicode characters."""
        # Arrange
        job_service = JobService(test_session)
        job_request = JobFactory.create_job_request(session=test_session)
        job = job_service.create_job(job_request)
        test_session.commit()
        service = ContentService(test_session)

        unicode_content = "<html><body>Hello 世界 🌍 Ça va?</body></html>"

        # Act
        result = service.save_content_result(
            job_id=job.id, content=unicode_content, content_type="converted"
        )
        test_session.commit()

        # Assert
        assert result.converted_html == unicode_content

    @pytest.mark.database
    def test_save_content_with_special_html_characters(self, test_session):
        """Test saving content with HTML special characters."""
        # Arrange
        job_service = JobService(test_session)
        job_request = JobFactory.create_job_request(session=test_session)
        job = job_service.create_job(job_request)
        test_session.commit()
        service = ContentService(test_session)

        special_content = "<html><body>&lt;script&gt;alert('xss')&lt;/script&gt;</body></html>"

        # Act
        result = service.save_content_result(
            job_id=job.id, content=special_content, content_type="converted"
        )
        test_session.commit()

        # Assert
        assert result.converted_html == special_content

    @pytest.mark.database
    def test_metadata_with_all_fields_populated(self, test_session):
        """Test metadata extraction with all possible fields."""
        # Arrange
        job_service = JobService(test_session)
        job_request = JobFactory.create_job_request(session=test_session)
        job = job_service.create_job(job_request)
        test_session.commit()
        service = ContentService(test_session)

        full_metadata = {
            "title": "Complete Title",
            "meta_description": "Complete Description",
            "author": "Complete Author",
            "tags": ["tag1", "tag2"],
            "categories": ["cat1", "cat2"],
            "word_count": 1000,
            "image_count": 50,
            "link_count": 100,
            "html_file_path": "/path/to/file.html",
            "metadata_file_path": "/path/to/metadata.json",
            "images_directory": "/path/to/images",
        }

        service.save_content_result(
            job_id=job.id,
            content="<html>Complete</html>",
            content_type="converted",
            metadata=full_metadata,
        )
        test_session.commit()

        # Act
        metadata = service.get_content_metadata(job.id)

        # Assert
        assert metadata["title"] == "Complete Title"
        assert metadata["author"] == "Complete Author"
        assert metadata["word_count"] == 1000
        assert metadata["image_count"] == 50
        assert metadata["link_count"] == 100

    @pytest.mark.database
    def test_content_with_null_timestamps_handled(self, test_session):
        """Test metadata handles null timestamps gracefully."""
        # Arrange
        job_service = JobService(test_session)
        job_request = JobFactory.create_job_request(session=test_session)
        job = job_service.create_job(job_request)
        test_session.commit()
        service = ContentService(test_session)

        # Create content (timestamps are auto-populated but test None handling)
        result = service.save_content_result(
            job_id=job.id, content="<html>Test</html>", content_type="converted"
        )
        test_session.commit()

        # Act
        metadata = service.get_content_metadata(job.id)

        # Assert
        # Timestamps should be ISO format strings or None
        assert isinstance(metadata["created_at"], (str, type(None)))
        assert isinstance(metadata["updated_at"], (str, type(None)))
        assert isinstance(metadata["published_date"], (str, type(None)))


class TestContentServiceUpdateEdgeCases:
    """Test edge cases for updating existing content (lines 74, 77-80)."""

    @pytest.mark.database
    def test_update_existing_with_original_type(self, test_session):
        """Test updating existing content with original content type (covers line 74)."""
        # Arrange
        job_service = JobService(test_session)
        job_request = JobFactory.create_job_request(session=test_session)
        job = job_service.create_job(job_request)
        test_session.commit()
        service = ContentService(test_session)

        # Create initial content
        service.save_content_result(
            job_id=job.id, content="<html>Initial</html>", content_type="converted"
        )
        test_session.commit()

        # Act - Update with original content type
        result = service.save_content_result(
            job_id=job.id, content="<html>Original HTML</html>", content_type="original"
        )
        test_session.commit()

        # Assert
        assert result.original_html == "<html>Original HTML</html>"
        assert result.converted_html == "<html>Initial</html>"  # Preserved

    @pytest.mark.database
    def test_update_existing_with_shopify_type(self, test_session):
        """Test updating existing content with shopify content type (covers lines 77-78)."""
        # Arrange
        job_service = JobService(test_session)
        job_request = JobFactory.create_job_request(session=test_session)
        job = job_service.create_job(job_request)
        test_session.commit()
        service = ContentService(test_session)

        # Create initial content
        service.save_content_result(
            job_id=job.id, content="<html>Initial</html>", content_type="converted"
        )
        test_session.commit()

        # Act - Update with shopify content type
        result = service.save_content_result(
            job_id=job.id,
            content="<div class='shopify'>Shopify HTML</div>",
            content_type="shopify",
        )
        test_session.commit()

        # Assert
        assert result.shopify_html == "<div class='shopify'>Shopify HTML</div>"
        assert result.converted_html == "<html>Initial</html>"  # Preserved

    @pytest.mark.database
    def test_update_existing_with_unknown_type_defaults_to_converted(self, test_session):
        """Test updating with unknown content type defaults to converted (covers lines 79-80)."""
        # Arrange
        job_service = JobService(test_session)
        job_request = JobFactory.create_job_request(session=test_session)
        job = job_service.create_job(job_request)
        test_session.commit()
        service = ContentService(test_session)

        # Create initial content
        service.save_content_result(
            job_id=job.id, content="<html>Initial</html>", content_type="converted"
        )
        test_session.commit()

        # Act - Update with unknown content type
        result = service.save_content_result(
            job_id=job.id, content="<html>Updated</html>", content_type="unknown"
        )
        test_session.commit()

        # Assert - Should default to converted_html
        assert result.converted_html == "<html>Updated</html>"


class TestContentServiceRetrievalEdgeCases:
    """Test edge cases for retrieving content (lines 165-166, 170-172, 209-213)."""

    @pytest.mark.database
    def test_get_content_by_job_with_original_html(self, test_session):
        """Test retrieving content when only original_html is present (covers lines 165-166)."""
        # Arrange
        job_service = JobService(test_session)
        job_request = JobFactory.create_job_request(session=test_session)
        job = job_service.create_job(job_request)
        test_session.commit()
        service = ContentService(test_session)

        # Create content with only original_html
        service.save_content_result(
            job_id=job.id, content="<html>Original content</html>", content_type="original"
        )
        test_session.commit()

        # Act
        result = service.get_content_by_job(job.id)

        # Assert
        assert result is not None
        assert result.original_html == "<html>Original content</html>"
        assert result.converted_html is None
        assert result.shopify_html is None

    @pytest.mark.database
    def test_get_content_by_job_with_shopify_html(self, test_session):
        """Test retrieving content when only shopify_html is present (covers lines 170-172)."""
        # Arrange
        job_service = JobService(test_session)
        job_request = JobFactory.create_job_request(session=test_session)
        job = job_service.create_job(job_request)
        test_session.commit()
        service = ContentService(test_session)

        # Create content with only shopify_html
        service.save_content_result(
            job_id=job.id,
            content="<div class='shopify'>Shopify content</div>",
            content_type="shopify",
        )
        test_session.commit()

        # Act
        result = service.get_content_by_job(job.id)

        # Assert
        assert result is not None
        assert result.shopify_html == "<div class='shopify'>Shopify content</div>"
        assert result.original_html is None
        assert result.converted_html is None

    @pytest.mark.database
    def test_get_content_metadata_with_shopify_html(self, test_session):
        """Test metadata determination when only shopify_html is present (covers lines 209-213)."""
        # Arrange
        job_service = JobService(test_session)
        job_request = JobFactory.create_job_request(session=test_session)
        job = job_service.create_job(job_request)
        test_session.commit()
        service = ContentService(test_session)

        # Create content with only shopify_html
        shopify_content = "<div class='shopify'>Shopify content for metadata</div>"
        service.save_content_result(job_id=job.id, content=shopify_content, content_type="shopify")
        test_session.commit()

        # Act
        metadata = service.get_content_metadata(job.id)

        # Assert
        assert metadata is not None
        assert metadata["content_type"] == "shopify"
        assert metadata["content_size_bytes"] == len(shopify_content.encode("utf-8"))
