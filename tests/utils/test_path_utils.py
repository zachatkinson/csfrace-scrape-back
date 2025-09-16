"""Tests for path utilities following DRY/SOLID principles."""

import os
import tempfile
from pathlib import Path, PurePath
from unittest.mock import patch

import pytest

from src.utils.path_utils import (
    ensure_path_exists,
    get_directory_name,
    get_file_extension,
    get_filename_without_extension,
    get_path_parts,
    is_absolute_path,
    is_directory,
    is_file,
    join_path_parts,
    make_relative_to,
    normalize_path_separators,
    path_exists,
    resolve_path,
    safe_filename,
    split_directory_path,
    truncate_path_component,
)


class TestPathNormalization:
    """Test path normalization functionality following SOLID principles."""

    def test_normalize_path_separators_windows_style(self):
        """Test normalization of Windows-style path separators."""
        windows_path = "C:\\Users\\Name\\Documents\\file.txt"
        normalized = normalize_path_separators(windows_path)

        assert "/" in normalized
        assert "\\" not in normalized
        assert normalized == "C:/Users/Name/Documents/file.txt"

    def test_normalize_path_separators_unix_style(self):
        """Test normalization preserves Unix-style separators."""
        unix_path = "/home/user/documents/file.txt"
        normalized = normalize_path_separators(unix_path)

        assert normalized == "/home/user/documents/file.txt"

    def test_normalize_path_separators_mixed_style(self):
        """Test normalization of mixed path separators."""
        mixed_path = "C:\\Users/Name\\Documents/file.txt"
        normalized = normalize_path_separators(mixed_path)

        assert "\\" not in normalized
        assert normalized == "C:/Users/Name/Documents/file.txt"

    def test_normalize_path_separators_path_object(self):
        """Test normalization with Path object input."""
        path_obj = Path("folder") / "subfolder" / "file.txt"
        normalized = normalize_path_separators(path_obj)

        assert isinstance(normalized, str)
        assert "/" in normalized or len(normalized.split("/")) == 1  # Single file case

    def test_normalize_path_separators_purepath_object(self):
        """Test normalization with PurePath object input."""
        pure_path = PurePath("folder", "subfolder", "file.txt")
        normalized = normalize_path_separators(pure_path)

        assert isinstance(normalized, str)
        assert "folder" in normalized
        assert "subfolder" in normalized
        assert "file.txt" in normalized


class TestPathParts:
    """Test path parts functionality following DRY principles."""

    def test_get_path_parts_simple_path(self):
        """Test getting parts from simple path."""
        path = "folder/subfolder/file.txt"
        parts = get_path_parts(path)

        expected_parts = ["folder", "subfolder", "file.txt"]
        assert parts == expected_parts

    def test_get_path_parts_absolute_unix_path(self):
        """Test getting parts from absolute Unix path."""
        path = "/home/user/documents/file.txt"
        parts = get_path_parts(path)

        assert parts[0] == "/"  # Root in Unix paths
        assert "home" in parts
        assert "user" in parts
        assert "documents" in parts
        assert "file.txt" in parts

    def test_get_path_parts_single_file(self):
        """Test getting parts from single filename."""
        path = "file.txt"
        parts = get_path_parts(path)

        assert parts == ["file.txt"]

    def test_get_path_parts_empty_string(self):
        """Test getting parts from empty string."""
        path = ""
        parts = get_path_parts(path)

        assert parts == ["."]  # Current directory for empty path

    def test_get_path_parts_path_object(self):
        """Test getting parts from Path object."""
        path = Path("folder") / "subfolder" / "file.txt"
        parts = get_path_parts(path)

        assert "folder" in parts
        assert "subfolder" in parts
        assert "file.txt" in parts

    def test_join_path_parts_multiple_parts(self):
        """Test joining multiple path parts."""
        joined = join_path_parts("folder", "subfolder", "file.txt")

        # Result should be a valid path string
        assert isinstance(joined, str)
        assert "folder" in joined
        assert "subfolder" in joined
        assert "file.txt" in joined

    def test_join_path_parts_single_part(self):
        """Test joining single path part."""
        joined = join_path_parts("file.txt")

        assert joined == "file.txt"

    def test_join_path_parts_empty_parts(self):
        """Test joining with empty parts."""
        joined = join_path_parts("")

        assert joined == "."  # Current directory

    def test_join_path_parts_with_separators(self):
        """Test joining parts that already contain separators."""
        joined = join_path_parts("folder/sub", "another", "file.txt")

        assert isinstance(joined, str)
        assert "folder" in joined
        assert "sub" in joined
        assert "another" in joined
        assert "file.txt" in joined


class TestPathInformation:
    """Test path information extraction following SOLID principles."""

    def test_get_directory_name_file_path(self):
        """Test getting directory name from file path."""
        path = "/home/user/documents/file.txt"
        name = get_directory_name(path)

        assert name == "file.txt"

    def test_get_directory_name_directory_path(self):
        """Test getting directory name from directory path."""
        path = "/home/user/documents"
        name = get_directory_name(path)

        assert name == "documents"

    def test_get_directory_name_single_component(self):
        """Test getting name from single path component."""
        path = "filename.txt"
        name = get_directory_name(path)

        assert name == "filename.txt"

    def test_split_directory_path_file(self):
        """Test splitting file path into directory and name."""
        path = "/home/user/documents/file.txt"
        parent, name = split_directory_path(path)

        assert name == "file.txt"
        assert "documents" in parent

    def test_split_directory_path_directory(self):
        """Test splitting directory path."""
        path = "/home/user/documents"
        parent, name = split_directory_path(path)

        assert name == "documents"
        assert "user" in parent

    def test_split_directory_path_root(self):
        """Test splitting root-level path."""
        path = "/root_file.txt"
        parent, name = split_directory_path(path)

        assert name == "root_file.txt"
        assert parent == "/"

    def test_split_directory_path_relative(self):
        """Test splitting relative path."""
        path = "folder/file.txt"
        parent, name = split_directory_path(path)

        assert name == "file.txt"
        assert parent == "folder"


class TestPathExistence:
    """Test path existence functionality following modern testing practices."""

    def setup_method(self):
        """Set up temporary directory for each test."""
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)

    def teardown_method(self):
        """Clean up temporary directory."""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_ensure_path_exists_new_directory(self):
        """Test creating new directory."""
        new_dir = self.temp_path / "new_directory"

        assert not new_dir.exists()

        created_path = ensure_path_exists(new_dir)

        assert created_path.exists()
        assert created_path.is_dir()
        assert created_path == new_dir

    def test_ensure_path_exists_nested_directories(self):
        """Test creating nested directories."""
        nested_dir = self.temp_path / "level1" / "level2" / "level3"

        assert not nested_dir.exists()

        created_path = ensure_path_exists(nested_dir)

        assert created_path.exists()
        assert created_path.is_dir()
        assert (self.temp_path / "level1").exists()
        assert (self.temp_path / "level1" / "level2").exists()

    def test_ensure_path_exists_existing_directory(self):
        """Test with existing directory."""
        existing_dir = self.temp_path / "existing"
        existing_dir.mkdir()

        assert existing_dir.exists()

        result_path = ensure_path_exists(existing_dir)

        assert result_path.exists()
        assert result_path == existing_dir

    def test_path_exists_true(self):
        """Test path_exists with existing path."""
        existing_file = self.temp_path / "test_file.txt"
        existing_file.write_text("test content")

        assert path_exists(existing_file)

    def test_path_exists_false(self):
        """Test path_exists with non-existing path."""
        non_existing = self.temp_path / "non_existing.txt"

        assert not path_exists(non_existing)

    def test_is_directory_true(self):
        """Test is_directory with actual directory."""
        test_dir = self.temp_path / "test_directory"
        test_dir.mkdir()

        assert is_directory(test_dir)

    def test_is_directory_false_file(self):
        """Test is_directory with file."""
        test_file = self.temp_path / "test_file.txt"
        test_file.write_text("content")

        assert not is_directory(test_file)

    def test_is_directory_false_non_existing(self):
        """Test is_directory with non-existing path."""
        non_existing = self.temp_path / "non_existing"

        assert not is_directory(non_existing)

    def test_is_file_true(self):
        """Test is_file with actual file."""
        test_file = self.temp_path / "test_file.txt"
        test_file.write_text("content")

        assert is_file(test_file)

    def test_is_file_false_directory(self):
        """Test is_file with directory."""
        test_dir = self.temp_path / "test_directory"
        test_dir.mkdir()

        assert not is_file(test_dir)

    def test_is_file_false_non_existing(self):
        """Test is_file with non-existing path."""
        non_existing = self.temp_path / "non_existing.txt"

        assert not is_file(non_existing)


class TestPathResolution:
    """Test path resolution functionality following DRY principles."""

    def test_is_absolute_path_unix_absolute(self):
        """Test absolute path detection for Unix paths."""
        assert is_absolute_path("/home/user/file.txt")

    def test_is_absolute_path_windows_absolute(self):
        """Test absolute path detection for Windows paths."""
        # Mock Windows behavior
        with patch("pathlib.Path.is_absolute", return_value=True):
            assert is_absolute_path("C:\\Users\\file.txt")

    def test_is_absolute_path_relative(self):
        """Test absolute path detection for relative paths."""
        assert not is_absolute_path("folder/file.txt")
        assert not is_absolute_path("./file.txt")
        assert not is_absolute_path("../file.txt")

    def test_make_relative_to_success(self):
        """Test making path relative to base."""
        path = "/home/user/documents/file.txt"
        base = "/home/user"

        relative = make_relative_to(path, base)

        assert relative == "documents/file.txt"

    def test_make_relative_to_same_path(self):
        """Test making path relative when paths are the same."""
        path = "/home/user/documents"
        base = "/home/user/documents"

        relative = make_relative_to(path, base)

        assert relative == "."

    def test_resolve_path_relative(self):
        """Test resolving relative path to absolute."""
        relative_path = "folder/file.txt"

        resolved = resolve_path(relative_path)

        assert os.path.isabs(resolved)
        assert "folder" in resolved
        assert "file.txt" in resolved

    def test_resolve_path_absolute(self):
        """Test resolving already absolute path."""
        absolute_path = "C:\\Users\\file.txt" if os.name == "nt" else "/home/user/file.txt"

        resolved = resolve_path(absolute_path)

        assert os.path.isabs(resolved)


class TestFileExtensions:
    """Test file extension utilities following SOLID principles."""

    def test_get_file_extension_with_extension(self):
        """Test getting file extension from path with extension."""
        path = "document.txt"
        extension = get_file_extension(path)

        assert extension == ".txt"

    def test_get_file_extension_multiple_dots(self):
        """Test getting extension from file with multiple dots."""
        path = "archive.tar.gz"
        extension = get_file_extension(path)

        assert extension == ".gz"  # Only last extension

    def test_get_file_extension_no_extension(self):
        """Test getting extension from file without extension."""
        path = "README"
        extension = get_file_extension(path)

        assert extension == ""

    def test_get_file_extension_hidden_file(self):
        """Test getting extension from hidden file."""
        path = ".gitignore"
        extension = get_file_extension(path)

        assert extension == ""  # .gitignore is considered filename, not extension

    def test_get_file_extension_with_path(self):
        """Test getting extension from full path."""
        path = "/home/user/documents/file.pdf"
        extension = get_file_extension(path)

        assert extension == ".pdf"

    def test_get_filename_without_extension_simple(self):
        """Test getting filename without extension."""
        path = "document.txt"
        filename = get_filename_without_extension(path)

        assert filename == "document"

    def test_get_filename_without_extension_multiple_dots(self):
        """Test getting filename from file with multiple dots."""
        path = "archive.tar.gz"
        filename = get_filename_without_extension(path)

        assert filename == "archive.tar"

    def test_get_filename_without_extension_no_extension(self):
        """Test getting filename when no extension exists."""
        path = "README"
        filename = get_filename_without_extension(path)

        assert filename == "README"

    def test_get_filename_without_extension_with_path(self):
        """Test getting filename from full path."""
        path = "/home/user/documents/report.pdf"
        filename = get_filename_without_extension(path)

        assert filename == "report"


class TestSafeFilename:
    """Test safe filename generation following security best practices."""

    def test_safe_filename_unsafe_characters(self):
        """Test replacing unsafe characters in filename."""
        unsafe_filename = 'file<name>with:unsafe"chars/in\\it|and?more*'
        safe = safe_filename(unsafe_filename)

        # Verify no unsafe characters remain
        unsafe_chars = '<>:"/\\|?*'
        for char in unsafe_chars:
            assert char not in safe

        # Verify replacement character is used
        assert "_" in safe

    def test_safe_filename_include_dots(self):
        """Test safe filename with dots as unsafe characters."""
        filename_with_dots = "file.with.many.dots.txt"
        safe = safe_filename(filename_with_dots, include_dots=True)

        assert "." not in safe
        assert "_" in safe

    def test_safe_filename_custom_replacement(self):
        """Test safe filename with custom replacement character."""
        unsafe_filename = "file<with>unsafe:chars"
        replacement = "-"
        safe = safe_filename(unsafe_filename, replacement=replacement)

        assert "<" not in safe
        assert ">" not in safe
        assert ":" not in safe
        assert replacement in safe

    def test_safe_filename_consecutive_replacements(self):
        """Test that consecutive replacement characters are collapsed."""
        unsafe_filename = "file<>:with||multiple**unsafe"
        safe = safe_filename(unsafe_filename)

        # Should not have consecutive underscores
        assert "__" not in safe

    def test_safe_filename_leading_trailing_replacement(self):
        """Test removal of leading and trailing replacement characters."""
        unsafe_filename = "<filename>"
        safe = safe_filename(unsafe_filename)

        # Should not start or end with replacement character
        assert not safe.startswith("_")
        assert not safe.endswith("_")

    def test_safe_filename_already_safe(self):
        """Test safe filename with already safe input."""
        safe_filename_input = "perfectly_safe_filename.txt"
        safe = safe_filename(safe_filename_input)

        assert safe == safe_filename_input

    def test_safe_filename_empty_string(self):
        """Test safe filename with empty string."""
        safe = safe_filename("")

        assert safe == ""

    def test_safe_filename_only_unsafe_characters(self):
        """Test safe filename with only unsafe characters."""
        unsafe_filename = '<>:"/\\|?*'
        safe = safe_filename(unsafe_filename)

        # Should result in empty string after cleaning
        assert safe == ""


class TestPathTruncation:
    """Test path component truncation following SOLID principles."""

    def test_truncate_path_component_short_component(self):
        """Test truncation of component shorter than max length."""
        component = "short_name"
        truncated = truncate_path_component(component, max_length=50)

        assert truncated == component

    def test_truncate_path_component_exact_length(self):
        """Test truncation of component exactly at max length."""
        component = "a" * 50
        truncated = truncate_path_component(component, max_length=50)

        assert truncated == component

    def test_truncate_path_component_long_component(self):
        """Test truncation of component longer than max length."""
        component = "very_long_component_name_that_exceeds_maximum_length_significantly"
        truncated = truncate_path_component(component, max_length=30)

        assert len(truncated) <= 30
        assert "..." in truncated
        assert truncated.startswith("very_long_compo")  # Start of original
        assert truncated.endswith("cantly")  # End of original

    def test_truncate_path_component_very_short_max_length(self):
        """Test truncation with very short max length."""
        component = "long_component_name"
        truncated = truncate_path_component(component, max_length=5)

        assert len(truncated) <= 5
        assert truncated == "long_"  # Should just cut off

    def test_truncate_path_component_medium_max_length(self):
        """Test truncation with medium max length that allows ellipsis."""
        component = "this_is_a_moderately_long_component_name"
        truncated = truncate_path_component(component, max_length=20)

        assert len(truncated) <= 20
        assert "..." in truncated
        # Should have beginning and end of original string

    def test_truncate_path_component_default_max_length(self):
        """Test truncation with default max length."""
        component = "a" * 100  # Very long component
        truncated = truncate_path_component(component)

        assert len(truncated) <= 50  # Default max length
        if len(component) > 50:
            assert "..." in truncated


class TestPathTypeHandling:
    """Test handling of different PathLike types following type safety principles."""

    def test_pathlike_string_input(self):
        """Test functions with string input."""
        path_str = "folder/file.txt"

        # Test various functions accept string input
        assert get_directory_name(path_str) == "file.txt"
        assert is_absolute_path(path_str) is False
        parts = get_path_parts(path_str)
        assert "folder" in parts and "file.txt" in parts

    def test_pathlike_path_object_input(self):
        """Test functions with Path object input."""
        path_obj = Path("folder") / "file.txt"

        # Test various functions accept Path object input
        assert get_directory_name(path_obj) == "file.txt"
        assert is_absolute_path(path_obj) is False
        parts = get_path_parts(path_obj)
        assert "folder" in parts and "file.txt" in parts

    def test_pathlike_purepath_object_input(self):
        """Test functions with PurePath object input."""
        pure_path = PurePath("folder", "file.txt")

        # Test various functions accept PurePath object input
        assert get_directory_name(pure_path) == "file.txt"
        parts = get_path_parts(pure_path)
        assert "folder" in parts and "file.txt" in parts

    def test_pathlike_mixed_inputs(self):
        """Test functions work consistently across different PathLike types."""
        str_path = "test/folder/file.txt"
        path_obj = Path("test") / "folder" / "file.txt"
        pure_path = PurePath("test", "folder", "file.txt")

        # All should give same results for directory name
        str_name = get_directory_name(str_path)
        path_name = get_directory_name(path_obj)
        pure_name = get_directory_name(pure_path)

        assert str_name == path_name == pure_name == "file.txt"

        # All should give same results for file extension
        str_ext = get_file_extension(str_path)
        path_ext = get_file_extension(path_obj)
        pure_ext = get_file_extension(pure_path)

        assert str_ext == path_ext == pure_ext == ".txt"


class TestPathUtilsEdgeCases:
    """Test edge cases and error conditions following modern testing practices."""

    def test_make_relative_to_invalid_base(self):
        """Test make_relative_to with invalid base path."""
        path = "/home/user/documents/file.txt"
        base = "/completely/different/path"

        # This should raise ValueError when path is not relative to base
        with pytest.raises(ValueError):
            make_relative_to(path, base)

    def test_empty_path_handling(self):
        """Test functions with empty path input."""
        empty_path = ""

        # Most functions should handle empty path gracefully
        assert get_directory_name(empty_path) == ""
        assert get_file_extension(empty_path) == ""
        assert get_filename_without_extension(empty_path) == ""

    def test_root_path_handling(self):
        """Test functions with root path."""
        root_path = "/"

        assert get_directory_name(root_path) == ""
        assert is_absolute_path(root_path) is True
        parent, name = split_directory_path(root_path)
        assert name == ""

    def test_current_directory_path_handling(self):
        """Test functions with current directory path."""
        current_path = "."

        assert get_directory_name(current_path) == "."
        assert is_absolute_path(current_path) is False

    def test_parent_directory_path_handling(self):
        """Test functions with parent directory path."""
        parent_path = ".."

        assert get_directory_name(parent_path) == ".."
        assert is_absolute_path(parent_path) is False

    def test_path_with_unicode_characters(self):
        """Test path utilities with Unicode characters."""
        unicode_path = "folder/文件名.txt"

        assert get_directory_name(unicode_path) == "文件名.txt"
        assert get_file_extension(unicode_path) == ".txt"
        assert get_filename_without_extension(unicode_path) == "文件名"

        # Safe filename should handle Unicode appropriately
        safe = safe_filename("文件名.txt")
        assert isinstance(safe, str)
