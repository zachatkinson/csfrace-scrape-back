"""Comprehensive tests for path utilities - MANDATORY TEST_BUILDING.md compliance.

This module tests cross-platform path utilities with complete coverage:
- Path separator normalization
- Path parsing and splitting
- Path joining and resolution
- File system operations
- Safe filename generation
- Path truncation
- Edge cases and cross-platform behavior

ALL tests follow MANDATORY TEST_BUILDING.md patterns:
- AAA pattern with explicit comments
- Factory fixtures for DRY principle
- Comprehensive path utility scenario testing
- Performance benchmarks with specific thresholds
"""

import tempfile
import time
from pathlib import Path

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

# ============================================================================
# Test Fixtures - DRY Principle
# ============================================================================


@pytest.fixture
def temp_test_dir():
    """Factory for temporary test directory - DRY principle."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_file_path(temp_test_dir: Path) -> Path:
    """Factory for sample file path - DRY principle."""
    file_path = temp_test_dir / "test_file.txt"
    file_path.write_text("test content")
    return file_path


@pytest.fixture
def nested_dir_structure(temp_test_dir: Path) -> Path:
    """Factory for nested directory structure - DRY principle."""
    nested = temp_test_dir / "level1" / "level2" / "level3"
    nested.mkdir(parents=True, exist_ok=True)
    return nested


# ============================================================================
# normalize_path_separators Tests
# ============================================================================


@pytest.mark.unit
class TestNormalizePathSeparators:
    """Tests for normalize_path_separators function."""

    def test_normalize_windows_separators(self):
        """Test normalize_path_separators with Windows paths - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        windows_path = "C:\\Users\\test\\Documents\\file.txt"

        # Act - MANDATORY
        result = normalize_path_separators(windows_path)

        # Assert - MANDATORY
        assert result == "C:/Users/test/Documents/file.txt"
        assert "\\" not in result

    def test_normalize_unix_separators(self):
        """Test normalize_path_separators with Unix paths - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        unix_path = "/home/user/documents/file.txt"

        # Act - MANDATORY
        result = normalize_path_separators(unix_path)

        # Assert - MANDATORY
        assert result == "/home/user/documents/file.txt"

    def test_normalize_mixed_separators(self):
        """Test normalize_path_separators with mixed separators - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        mixed_path = "C:/Users\\test/Documents\\file.txt"

        # Act - MANDATORY
        result = normalize_path_separators(mixed_path)

        # Assert - MANDATORY
        assert result == "C:/Users/test/Documents/file.txt"
        assert "\\" not in result

    def test_normalize_path_object(self):
        """Test normalize_path_separators with Path object - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        path_obj = Path("test") / "dir" / "file.txt"

        # Act - MANDATORY
        result = normalize_path_separators(path_obj)

        # Assert - MANDATORY
        assert "/" in result
        assert result.endswith("file.txt")


# ============================================================================
# get_path_parts Tests
# ============================================================================


@pytest.mark.unit
class TestGetPathParts:
    """Tests for get_path_parts function."""

    def test_get_path_parts_simple_path(self):
        """Test get_path_parts with simple path - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        path = "dir1/dir2/file.txt"

        # Act - MANDATORY
        result = get_path_parts(path)

        # Assert - MANDATORY
        assert result == ["dir1", "dir2", "file.txt"]

    def test_get_path_parts_absolute_unix(self):
        """Test get_path_parts with absolute Unix path - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        path = "/home/user/documents"

        # Act - MANDATORY
        result = get_path_parts(path)

        # Assert - MANDATORY
        assert result[0] == "/"
        assert "user" in result
        assert "documents" in result

    def test_get_path_parts_empty_path(self):
        """Test get_path_parts with empty path - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        path = ""

        # Act - MANDATORY
        result = get_path_parts(path)

        # Assert - MANDATORY
        assert result == ["."]

    def test_get_path_parts_single_component(self):
        """Test get_path_parts with single component - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        path = "filename.txt"

        # Act - MANDATORY
        result = get_path_parts(path)

        # Assert - MANDATORY
        assert result == ["filename.txt"]


# ============================================================================
# join_path_parts Tests
# ============================================================================


@pytest.mark.unit
class TestJoinPathParts:
    """Tests for join_path_parts function."""

    def test_join_path_parts_multiple_components(self):
        """Test join_path_parts with multiple components - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        parts = ("dir1", "dir2", "file.txt")

        # Act - MANDATORY
        result = join_path_parts(*parts)

        # Assert - MANDATORY
        assert "file.txt" in result
        expected = str(Path("dir1") / "dir2" / "file.txt")
        assert result == expected

    def test_join_path_parts_single_component(self):
        """Test join_path_parts with single component - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        part = "filename.txt"

        # Act - MANDATORY
        result = join_path_parts(part)

        # Assert - MANDATORY
        assert result == "filename.txt"

    def test_join_path_parts_empty_parts(self):
        """Test join_path_parts with some empty parts - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        parts = ("dir1", "", "dir2", "file.txt")

        # Act - MANDATORY
        result = join_path_parts(*parts)

        # Assert - MANDATORY
        assert "dir1" in result
        assert "dir2" in result
        assert "file.txt" in result


# ============================================================================
# get_directory_name Tests
# ============================================================================


@pytest.mark.unit
class TestGetDirectoryName:
    """Tests for get_directory_name function."""

    def test_get_directory_name_from_path(self):
        """Test get_directory_name from full path - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        path = "/home/user/documents/report.pdf"

        # Act - MANDATORY
        result = get_directory_name(path)

        # Assert - MANDATORY
        assert result == "report.pdf"

    def test_get_directory_name_from_directory(self):
        """Test get_directory_name from directory path - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        path = "/home/user/documents"

        # Act - MANDATORY
        result = get_directory_name(path)

        # Assert - MANDATORY
        assert result == "documents"

    def test_get_directory_name_empty_string(self):
        """Test get_directory_name with empty string - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        path = ""

        # Act - MANDATORY
        result = get_directory_name(path)

        # Assert - MANDATORY
        assert result == ""

    def test_get_directory_name_current_directory(self):
        """Test get_directory_name with current directory - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        path = "."

        # Act - MANDATORY
        result = get_directory_name(path)

        # Assert - MANDATORY
        assert result == "."


# ============================================================================
# split_directory_path Tests
# ============================================================================


@pytest.mark.unit
class TestSplitDirectoryPath:
    """Tests for split_directory_path function."""

    def test_split_directory_path_full_path(self):
        """Test split_directory_path with full path - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        path = "/home/user/documents/file.txt"

        # Act - MANDATORY
        parent, name = split_directory_path(path)

        # Assert - MANDATORY
        assert name == "file.txt"
        assert "documents" in parent

    def test_split_directory_path_single_component(self):
        """Test split_directory_path with single component - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        path = "file.txt"

        # Act - MANDATORY
        parent, name = split_directory_path(path)

        # Assert - MANDATORY
        assert name == "file.txt"
        assert parent == "."


# ============================================================================
# ensure_path_exists Tests
# ============================================================================


@pytest.mark.unit
class TestEnsurePathExists:
    """Tests for ensure_path_exists function."""

    def test_ensure_path_exists_creates_directory(self, temp_test_dir: Path):
        """Test ensure_path_exists creates directory - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        new_dir = temp_test_dir / "new_directory"
        assert not new_dir.exists()

        # Act - MANDATORY
        result = ensure_path_exists(new_dir)

        # Assert - MANDATORY
        assert result.exists()
        assert result.is_dir()

    def test_ensure_path_exists_nested_directories(self, temp_test_dir: Path):
        """Test ensure_path_exists creates nested directories - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        nested = temp_test_dir / "level1" / "level2" / "level3"
        assert not nested.exists()

        # Act - MANDATORY
        result = ensure_path_exists(nested)

        # Assert - MANDATORY
        assert result.exists()
        assert result.is_dir()

    def test_ensure_path_exists_already_exists(self, temp_test_dir: Path):
        """Test ensure_path_exists with existing directory - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        existing_dir = temp_test_dir / "existing"
        existing_dir.mkdir()

        # Act - MANDATORY
        result = ensure_path_exists(existing_dir)

        # Assert - MANDATORY
        assert result.exists()
        assert result.is_dir()


# ============================================================================
# is_absolute_path Tests
# ============================================================================


@pytest.mark.unit
class TestIsAbsolutePath:
    """Tests for is_absolute_path function."""

    def test_is_absolute_path_unix_absolute(self):
        """Test is_absolute_path with Unix absolute path - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        path = "/home/user/documents"

        # Act - MANDATORY
        result = is_absolute_path(path)

        # Assert - MANDATORY
        assert result is True

    def test_is_absolute_path_relative(self):
        """Test is_absolute_path with relative path - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        path = "documents/file.txt"

        # Act - MANDATORY
        result = is_absolute_path(path)

        # Assert - MANDATORY
        assert result is False

    def test_is_absolute_path_current_directory(self):
        """Test is_absolute_path with current directory - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        path = "."

        # Act - MANDATORY
        result = is_absolute_path(path)

        # Assert - MANDATORY
        assert result is False


# ============================================================================
# make_relative_to Tests
# ============================================================================


@pytest.mark.unit
class TestMakeRelativeTo:
    """Tests for make_relative_to function."""

    def test_make_relative_to_subdirectory(self, temp_test_dir: Path):
        """Test make_relative_to with subdirectory - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        subdir = temp_test_dir / "sub" / "nested" / "file.txt"
        base = temp_test_dir

        # Act - MANDATORY
        result = make_relative_to(subdir, base)

        # Assert - MANDATORY
        assert result == str(Path("sub") / "nested" / "file.txt")
        assert not Path(result).is_absolute()


# ============================================================================
# resolve_path Tests
# ============================================================================


@pytest.mark.unit
class TestResolvePath:
    """Tests for resolve_path function."""

    def test_resolve_path_current_directory(self):
        """Test resolve_path with current directory - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        path = "."

        # Act - MANDATORY
        result = resolve_path(path)

        # Assert - MANDATORY
        assert Path(result).is_absolute()

    def test_resolve_path_relative(self):
        """Test resolve_path with relative path - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        path = "test/file.txt"

        # Act - MANDATORY
        result = resolve_path(path)

        # Assert - MANDATORY
        assert Path(result).is_absolute()
        assert "file.txt" in result


# ============================================================================
# path_exists, is_directory, is_file Tests
# ============================================================================


@pytest.mark.unit
class TestPathChecks:
    """Tests for path existence and type checking functions."""

    def test_path_exists_existing_file(self, sample_file_path: Path):
        """Test path_exists with existing file - MANDATORY AAA pattern."""
        # Arrange - MANDATORY (done by fixture)

        # Act - MANDATORY
        result = path_exists(sample_file_path)

        # Assert - MANDATORY
        assert result is True

    def test_path_exists_nonexistent(self, temp_test_dir: Path):
        """Test path_exists with nonexistent path - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        nonexistent = temp_test_dir / "does_not_exist.txt"

        # Act - MANDATORY
        result = path_exists(nonexistent)

        # Assert - MANDATORY
        assert result is False

    def test_is_directory_with_directory(self, temp_test_dir: Path):
        """Test is_directory with directory - MANDATORY AAA pattern."""
        # Arrange - MANDATORY (done by fixture)

        # Act - MANDATORY
        result = is_directory(temp_test_dir)

        # Assert - MANDATORY
        assert result is True

    def test_is_directory_with_file(self, sample_file_path: Path):
        """Test is_directory with file - MANDATORY AAA pattern."""
        # Arrange - MANDATORY (done by fixture)

        # Act - MANDATORY
        result = is_directory(sample_file_path)

        # Assert - MANDATORY
        assert result is False

    def test_is_file_with_file(self, sample_file_path: Path):
        """Test is_file with file - MANDATORY AAA pattern."""
        # Arrange - MANDATORY (done by fixture)

        # Act - MANDATORY
        result = is_file(sample_file_path)

        # Assert - MANDATORY
        assert result is True

    def test_is_file_with_directory(self, temp_test_dir: Path):
        """Test is_file with directory - MANDATORY AAA pattern."""
        # Arrange - MANDATORY (done by fixture)

        # Act - MANDATORY
        result = is_file(temp_test_dir)

        # Assert - MANDATORY
        assert result is False


# ============================================================================
# get_file_extension Tests
# ============================================================================


@pytest.mark.unit
class TestGetFileExtension:
    """Tests for get_file_extension function."""

    def test_get_file_extension_with_extension(self):
        """Test get_file_extension with extension - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        path = "/home/user/document.pdf"

        # Act - MANDATORY
        result = get_file_extension(path)

        # Assert - MANDATORY
        assert result == ".pdf"

    def test_get_file_extension_multiple_dots(self):
        """Test get_file_extension with multiple dots - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        path = "archive.tar.gz"

        # Act - MANDATORY
        result = get_file_extension(path)

        # Assert - MANDATORY
        assert result == ".gz"

    def test_get_file_extension_no_extension(self):
        """Test get_file_extension without extension - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        path = "/home/user/README"

        # Act - MANDATORY
        result = get_file_extension(path)

        # Assert - MANDATORY
        assert result == ""


# ============================================================================
# get_filename_without_extension Tests
# ============================================================================


@pytest.mark.unit
class TestGetFilenameWithoutExtension:
    """Tests for get_filename_without_extension function."""

    def test_get_filename_without_extension_simple(self):
        """Test get_filename_without_extension simple case - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        path = "/home/user/document.pdf"

        # Act - MANDATORY
        result = get_filename_without_extension(path)

        # Assert - MANDATORY
        assert result == "document"

    def test_get_filename_without_extension_multiple_dots(self):
        """Test get_filename_without_extension with multiple dots - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        path = "archive.tar.gz"

        # Act - MANDATORY
        result = get_filename_without_extension(path)

        # Assert - MANDATORY
        assert result == "archive.tar"

    def test_get_filename_without_extension_no_extension(self):
        """Test get_filename_without_extension no extension - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        path = "README"

        # Act - MANDATORY
        result = get_filename_without_extension(path)

        # Assert - MANDATORY
        assert result == "README"


# ============================================================================
# safe_filename Tests
# ============================================================================


@pytest.mark.unit
class TestSafeFilename:
    """Tests for safe_filename function."""

    def test_safe_filename_removes_unsafe_characters(self):
        """Test safe_filename removes unsafe characters - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        filename = 'file<name>:with"unsafe|chars?.txt'

        # Act - MANDATORY
        result = safe_filename(filename)

        # Assert - MANDATORY
        assert result == "file_name_with_unsafe_chars_.txt"
        assert "<" not in result
        assert ">" not in result
        assert ":" not in result

    def test_safe_filename_removes_multiple_consecutive_replacements(self):
        """Test safe_filename removes consecutive replacements - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        filename = "file<<>>name.txt"

        # Act - MANDATORY
        result = safe_filename(filename)

        # Assert - MANDATORY
        assert "__" not in result
        assert result == "file_name.txt"

    def test_safe_filename_strips_edge_replacements(self):
        """Test safe_filename strips edge replacements - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        filename = "<filename>.txt"

        # Act - MANDATORY
        result = safe_filename(filename)

        # Assert - MANDATORY
        assert not result.startswith("_")
        assert result == "filename_.txt"  # > replaced by _, then . preserved

    def test_safe_filename_custom_replacement(self):
        """Test safe_filename with custom replacement - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        filename = "file:name.txt"

        # Act - MANDATORY
        result = safe_filename(filename, replacement="-")

        # Assert - MANDATORY
        assert result == "file-name.txt"

    def test_safe_filename_include_dots(self):
        """Test safe_filename including dots as unsafe - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        filename = "file.name.txt"

        # Act - MANDATORY
        result = safe_filename(filename, include_dots=True)

        # Assert - MANDATORY
        assert "." not in result
        assert result == "file_name_txt"

    def test_safe_filename_already_safe(self):
        """Test safe_filename with already safe filename - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        filename = "safe_filename.txt"

        # Act - MANDATORY
        result = safe_filename(filename)

        # Assert - MANDATORY
        assert result == "safe_filename.txt"


# ============================================================================
# truncate_path_component Tests
# ============================================================================


@pytest.mark.unit
class TestTruncatePathComponent:
    """Tests for truncate_path_component function."""

    def test_truncate_path_component_short_component(self):
        """Test truncate_path_component with short component - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        component = "short_name"

        # Act - MANDATORY
        result = truncate_path_component(component, max_length=50)

        # Assert - MANDATORY
        assert result == "short_name"

    def test_truncate_path_component_long_component(self):
        """Test truncate_path_component with long component - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        component = "a" * 100

        # Act - MANDATORY
        result = truncate_path_component(component, max_length=50)

        # Assert - MANDATORY
        assert len(result) <= 50
        assert "..." in result
        assert result.startswith("a" * 25)
        assert result.endswith("a" * 21)

    def test_truncate_path_component_exact_length(self):
        """Test truncate_path_component at exact max length - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        component = "a" * 50

        # Act - MANDATORY
        result = truncate_path_component(component, max_length=50)

        # Assert - MANDATORY
        assert result == component

    def test_truncate_path_component_very_short_max(self):
        """Test truncate_path_component with very short max - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        component = "very_long_component_name"

        # Act - MANDATORY
        result = truncate_path_component(component, max_length=5)

        # Assert - MANDATORY
        assert len(result) <= 5
        assert result == "very_"


# ============================================================================
# MANDATORY Performance Benchmarks
# ============================================================================


@pytest.mark.performance
@pytest.mark.unit
class TestPathUtilsPerformance:
    """MANDATORY performance tests for path utilities."""

    def test_normalize_path_separators_performance(self):
        """MANDATORY performance test - path normalization speed."""
        # Arrange - MANDATORY
        test_path = "C:\\Users\\test\\very\\long\\path\\to\\some\\file.txt"
        iterations = 100000

        # Act - MANDATORY
        start_time = time.perf_counter()

        for _ in range(iterations):
            normalize_path_separators(test_path)

        end_time = time.perf_counter()
        execution_time = end_time - start_time

        # Assert - MANDATORY
        avg_time = execution_time / iterations
        assert avg_time < 0.00001  # <0.01ms per normalization
        assert execution_time < 1.0  # Total <1s for 100000 normalizations

    def test_safe_filename_performance(self):
        """MANDATORY performance test - safe filename generation speed."""
        # Arrange - MANDATORY
        unsafe_filename = 'test<file>:name"with|unsafe?.txt'
        iterations = 50000

        # Act - MANDATORY
        start_time = time.perf_counter()

        for _ in range(iterations):
            safe_filename(unsafe_filename)

        end_time = time.perf_counter()
        execution_time = end_time - start_time

        # Assert - MANDATORY
        avg_time = execution_time / iterations
        assert avg_time < 0.00002  # <0.02ms per safe filename
        assert execution_time < 1.0  # Total <1s for 50000 generations

    def test_path_operations_batch_performance(self):
        """MANDATORY performance test - batch path operations."""
        # Arrange - MANDATORY
        test_paths = [f"/home/user/dir{i}/file{i}.txt" for i in range(1000)]
        iterations = 100

        # Act - MANDATORY
        start_time = time.perf_counter()

        for _ in range(iterations):
            for path in test_paths:
                get_path_parts(path)
                get_directory_name(path)
                get_file_extension(path)

        end_time = time.perf_counter()
        execution_time = end_time - start_time

        # Assert - MANDATORY
        total_operations = iterations * len(test_paths) * 3
        avg_time = execution_time / total_operations
        assert avg_time < 0.00001  # <0.01ms per operation
