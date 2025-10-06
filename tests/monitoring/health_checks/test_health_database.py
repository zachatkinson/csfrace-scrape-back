"""Comprehensive tests for database health checks - MANDATORY TEST_BUILDING.md compliance.

This module tests database health check functionality with complete coverage:
- DatabaseHealthCheck connectivity testing
- DatabaseHealthCheck query execution
- DatabaseTableHealthCheck table accessibility
- Session management and error handling
- Edge cases and error handling
- Performance benchmarks

ALL tests follow MANDATORY TEST_BUILDING.md patterns:
- AAA pattern with explicit comments
- Factory fixtures for DRY principle
- Comprehensive database health check scenario testing
- Performance benchmarks with specific thresholds
"""

import time
from collections.abc import AsyncGenerator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.monitoring.health_checks.base import HealthStatus
from src.monitoring.health_checks.database import DatabaseHealthCheck, DatabaseTableHealthCheck

# ============================================================================
# Test Fixtures - DRY Principle
# ============================================================================


@pytest.fixture
def mock_db_session() -> AsyncMock:
    """Factory for mock database session - DRY principle."""
    session = AsyncMock()
    session.execute = AsyncMock()
    return session


@pytest.fixture
def mock_get_db_session(mock_db_session: AsyncMock) -> Any:
    """Factory for mock get_db_session generator - DRY principle."""

    async def mock_generator() -> AsyncGenerator[AsyncMock]:
        yield mock_db_session

    return mock_generator


# ============================================================================
# DatabaseHealthCheck Tests
# ============================================================================


@pytest.mark.unit
class TestDatabaseHealthCheck:
    """Tests for DatabaseHealthCheck class."""

    def test_database_health_check_initialization_defaults(self) -> None:
        """Test DatabaseHealthCheck initialization with defaults - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # Act - MANDATORY
        health_check = DatabaseHealthCheck()

        # Assert - MANDATORY
        assert health_check.name == "database"
        assert health_check.timeout_seconds == 5.0
        assert health_check._session is None

    def test_database_health_check_initialization_custom_name(self) -> None:
        """Test DatabaseHealthCheck with custom name - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        custom_name = "postgres_db"

        # Act - MANDATORY
        health_check = DatabaseHealthCheck(name=custom_name)

        # Assert - MANDATORY
        assert health_check.name == custom_name

    def test_database_health_check_initialization_custom_timeout(self) -> None:
        """Test DatabaseHealthCheck with custom timeout - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        custom_timeout = 10.0

        # Act - MANDATORY
        health_check = DatabaseHealthCheck(timeout_seconds=custom_timeout)

        # Assert - MANDATORY
        assert health_check.timeout_seconds == custom_timeout

    @pytest.mark.asyncio
    @patch("src.monitoring.health_checks.database.get_db_session")
    async def test_check_successful_database_connection(
        self, mock_get_db: Any, mock_db_session: AsyncMock
    ) -> None:
        """Test check() with successful database connection - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        mock_result = MagicMock()
        mock_row = MagicMock()
        mock_row.health_check = 1
        mock_result.fetchone.return_value = mock_row
        mock_db_session.execute.return_value = mock_result

        async def mock_generator() -> AsyncGenerator[AsyncMock]:
            yield mock_db_session

        mock_get_db.return_value = mock_generator()
        health_check = DatabaseHealthCheck(name="test_db")

        # Act - MANDATORY
        result = await health_check.check()

        # Assert - MANDATORY
        assert result.name == "test_db"
        assert result.status == HealthStatus.HEALTHY
        assert result.message == "Database connection successful"
        assert result.duration_ms > 0
        mock_db_session.execute.assert_called_once()

    @pytest.mark.asyncio
    @patch("src.monitoring.health_checks.database.get_db_session")
    async def test_check_database_query_unexpected_result(
        self, mock_get_db: Any, mock_db_session: AsyncMock
    ) -> None:
        """Test check() with unexpected query result - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        mock_result = MagicMock()
        mock_row = MagicMock()
        mock_row.health_check = 0  # Unexpected value
        mock_result.fetchone.return_value = mock_row
        mock_db_session.execute.return_value = mock_result

        async def mock_generator() -> AsyncGenerator[AsyncMock]:
            yield mock_db_session

        mock_get_db.return_value = mock_generator()
        health_check = DatabaseHealthCheck(name="test_db")

        # Act - MANDATORY
        result = await health_check.check()

        # Assert - MANDATORY
        assert result.name == "test_db"
        assert result.status == HealthStatus.UNHEALTHY
        assert "unexpected result" in result.message.lower()
        assert result.duration_ms > 0
        assert "query_result" in result.details

    @pytest.mark.asyncio
    @patch("src.monitoring.health_checks.database.get_db_session")
    async def test_check_database_no_row_returned(
        self, mock_get_db: Any, mock_db_session: AsyncMock
    ) -> None:
        """Test check() when query returns no rows - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        mock_result = MagicMock()
        mock_result.fetchone.return_value = None
        mock_db_session.execute.return_value = mock_result

        async def mock_generator() -> AsyncGenerator[AsyncMock]:
            yield mock_db_session

        mock_get_db.return_value = mock_generator()
        health_check = DatabaseHealthCheck(name="test_db")

        # Act - MANDATORY
        result = await health_check.check()

        # Assert - MANDATORY
        assert result.name == "test_db"
        assert result.status == HealthStatus.UNHEALTHY
        assert "unexpected result" in result.message.lower()

    @pytest.mark.asyncio
    @patch("src.monitoring.health_checks.database.get_db_session")
    async def test_check_no_database_session_available(self, mock_get_db: Any) -> None:
        """Test check() when no database session is available - MANDATORY AAA pattern."""

        # Arrange - MANDATORY
        async def empty_generator() -> AsyncGenerator[None]:
            return
            yield  # Make it a generator but yield nothing

        mock_get_db.return_value = empty_generator()
        health_check = DatabaseHealthCheck(name="test_db")

        # Act - MANDATORY
        result = await health_check.check()

        # Assert - MANDATORY
        assert result.name == "test_db"
        assert result.status == HealthStatus.UNHEALTHY
        assert "no database session available" in result.message.lower()
        assert result.duration_ms > 0


# ============================================================================
# DatabaseTableHealthCheck Tests
# ============================================================================


@pytest.mark.unit
class TestDatabaseTableHealthCheck:
    """Tests for DatabaseTableHealthCheck class."""

    def test_database_table_health_check_initialization_defaults(self) -> None:
        """Test DatabaseTableHealthCheck initialization - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        table_name = "users"

        # Act - MANDATORY
        health_check = DatabaseTableHealthCheck(table_name=table_name)

        # Assert - MANDATORY
        assert health_check.name == "database_table_users"
        assert health_check.table_name == "users"
        assert health_check.timeout_seconds == 5.0

    def test_database_table_health_check_initialization_custom_name(self) -> None:
        """Test DatabaseTableHealthCheck with custom name - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        table_name = "orders"
        custom_name = "production_orders_table"

        # Act - MANDATORY
        health_check = DatabaseTableHealthCheck(table_name=table_name, name=custom_name)

        # Assert - MANDATORY
        assert health_check.name == custom_name
        assert health_check.table_name == table_name

    def test_database_table_health_check_initialization_custom_timeout(self) -> None:
        """Test DatabaseTableHealthCheck with custom timeout - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        table_name = "products"
        custom_timeout = 8.0

        # Act - MANDATORY
        health_check = DatabaseTableHealthCheck(
            table_name=table_name, timeout_seconds=custom_timeout
        )

        # Assert - MANDATORY
        assert health_check.timeout_seconds == custom_timeout

    @pytest.mark.asyncio
    @patch("src.monitoring.health_checks.database.get_db_session")
    async def test_check_table_accessible_successfully(
        self, mock_get_db: Any, mock_db_session: AsyncMock
    ) -> None:
        """Test check() with accessible table - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        table_name = "users"
        mock_db_session.execute.return_value = None  # Query succeeds

        async def mock_generator() -> AsyncGenerator[AsyncMock]:
            yield mock_db_session

        mock_get_db.return_value = mock_generator()
        health_check = DatabaseTableHealthCheck(table_name=table_name)

        # Act - MANDATORY
        result = await health_check.check()

        # Assert - MANDATORY
        assert result.name == f"database_table_{table_name}"
        assert result.status == HealthStatus.HEALTHY
        assert f"Table '{table_name}' is accessible" in result.message
        assert result.duration_ms > 0
        assert result.details["table_name"] == table_name
        assert result.details["accessible"] is True
        mock_db_session.execute.assert_called_once()

    @pytest.mark.asyncio
    @patch("src.monitoring.health_checks.database.get_db_session")
    async def test_check_no_session_available_for_table(self, mock_get_db: Any) -> None:
        """Test check() when no session available for table check - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        table_name = "orders"

        async def empty_generator() -> AsyncGenerator[None]:
            return
            yield  # Make it a generator but yield nothing

        mock_get_db.return_value = empty_generator()
        health_check = DatabaseTableHealthCheck(table_name=table_name)

        # Act - MANDATORY
        result = await health_check.check()

        # Assert - MANDATORY
        assert result.name == f"database_table_{table_name}"
        assert result.status == HealthStatus.UNHEALTHY
        assert "no database session available" in result.message.lower()
        assert result.details["table_name"] == table_name
        assert result.details["accessible"] is False


# ============================================================================
# MANDATORY Performance Benchmarks
# ============================================================================


@pytest.mark.performance
@pytest.mark.unit
class TestDatabaseHealthCheckPerformance:
    """MANDATORY performance tests for database health check operations."""

    def test_database_health_check_creation_performance(self) -> None:
        """MANDATORY performance test - DatabaseHealthCheck creation speed."""
        # Arrange - MANDATORY
        iterations = 10000

        # Act - MANDATORY
        start_time = time.perf_counter()

        for _ in range(iterations):
            DatabaseHealthCheck(name="perf_test_db")

        end_time = time.perf_counter()
        execution_time = end_time - start_time

        # Assert - MANDATORY
        avg_time = execution_time / iterations
        assert avg_time < 0.0001  # <0.1ms per creation
        assert execution_time < 1.0  # Total <1s for 10000 creations

    def test_database_table_health_check_creation_performance(self) -> None:
        """MANDATORY performance test - DatabaseTableHealthCheck creation speed."""
        # Arrange - MANDATORY
        iterations = 10000

        # Act - MANDATORY
        start_time = time.perf_counter()

        for i in range(iterations):
            DatabaseTableHealthCheck(table_name=f"table_{i % 100}")

        end_time = time.perf_counter()
        execution_time = end_time - start_time

        # Assert - MANDATORY
        avg_time = execution_time / iterations
        assert avg_time < 0.0001  # <0.1ms per creation
        assert execution_time < 1.0  # Total <1s for 10000 creations
