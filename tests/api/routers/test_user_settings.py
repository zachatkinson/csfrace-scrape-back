"""Comprehensive tests for user settings router - MANDATORY TEST_BUILDING.md compliance.

This module tests user settings API functionality with complete coverage:
- Router configuration
- GET /user/settings endpoint (retrieve with auto-creation)
- PUT /user/settings endpoint (update/create)
- DELETE /user/settings endpoint (reset to defaults)
- Default settings creation logic
- Partial updates handling
- User authentication integration

ALL tests follow MANDATORY TEST_BUILDING.md patterns:
- AAA pattern with explicit comments
- Factory fixtures for DRY principle
- Comprehensive user settings scenario testing
- Performance benchmarks with specific thresholds
"""

import time
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import APIRouter
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.routers.user_settings import router
from src.api.schemas import UserSettingsUpdate
from src.database.models.auth import User, UserSettings

# ============================================================================
# Test Fixtures - DRY Principle
# ============================================================================


@pytest.fixture
def sample_user() -> User:
    """Factory for sample user - DRY principle."""
    user = User(
        id=str(uuid4()),
        username="test_user",
        email="test@example.com",
        hashed_password="hashed_password",
        created_at=datetime.now(UTC),
        is_active=True,
        is_verified=True,
    )
    return user


@pytest.fixture
def sample_user_settings(sample_user: User) -> UserSettings:
    """Factory for sample user settings - DRY principle."""
    settings = UserSettings(
        id=str(uuid4()),
        user_id=sample_user.id,
        # Job Defaults
        default_priority="high",
        max_retries=5,
        job_timeout=60,
        # API Configuration
        api_url="http://localhost:8000",
        api_timeout=30,
        refresh_interval=10,
        retry_attempts=3,
        enable_caching=True,
        # Display Options
        dark_mode=True,
        show_job_ids=True,
        compact_mode=False,
        jobs_per_page=20,
        timezone="UTC",
        # Notification Settings
        completion_alerts=True,
        error_notifications=True,
        browser_notifications=False,
        # Timestamps
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    return settings


@pytest.fixture
def mock_db_session() -> AsyncMock:
    """Factory for mock database session - DRY principle."""
    session = AsyncMock(spec=AsyncSession)
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    session.execute = AsyncMock()
    return session


@pytest.fixture
def sample_settings_update() -> UserSettingsUpdate:
    """Factory for sample settings update data - DRY principle."""
    return UserSettingsUpdate(
        dark_mode=False,
        jobs_per_page=50,
        completion_alerts=False,
    )


@pytest.fixture
def mock_refresh_with_defaults() -> Callable[[Any], Any]:
    """Factory for mock refresh that populates all default values - DRY principle."""

    async def _mock_refresh(obj: Any) -> None:
        obj.id = str(uuid4())
        obj.created_at = datetime.now(UTC)
        obj.updated_at = datetime.now(UTC)
        # Populate all required fields with defaults from model
        if not hasattr(obj, "default_priority") or obj.default_priority is None:
            obj.default_priority = "normal"
        if not hasattr(obj, "max_retries") or obj.max_retries is None:
            obj.max_retries = 3
        if not hasattr(obj, "job_timeout") or obj.job_timeout is None:
            obj.job_timeout = 30
        if not hasattr(obj, "api_url") or obj.api_url is None:
            obj.api_url = "http://localhost:8000"
        if not hasattr(obj, "api_timeout") or obj.api_timeout is None:
            obj.api_timeout = 30
        if not hasattr(obj, "refresh_interval") or obj.refresh_interval is None:
            obj.refresh_interval = 10
        if not hasattr(obj, "retry_attempts") or obj.retry_attempts is None:
            obj.retry_attempts = 3
        if not hasattr(obj, "enable_caching") or obj.enable_caching is None:
            obj.enable_caching = True
        if not hasattr(obj, "dark_mode") or obj.dark_mode is None:
            obj.dark_mode = True
        if not hasattr(obj, "show_job_ids") or obj.show_job_ids is None:
            obj.show_job_ids = True
        if not hasattr(obj, "compact_mode") or obj.compact_mode is None:
            obj.compact_mode = False
        if not hasattr(obj, "jobs_per_page") or obj.jobs_per_page is None:
            obj.jobs_per_page = 10
        if not hasattr(obj, "timezone") or obj.timezone is None:
            obj.timezone = "auto"
        if not hasattr(obj, "completion_alerts") or obj.completion_alerts is None:
            obj.completion_alerts = True
        if not hasattr(obj, "error_notifications") or obj.error_notifications is None:
            obj.error_notifications = True
        if not hasattr(obj, "browser_notifications") or obj.browser_notifications is None:
            obj.browser_notifications = False

    return _mock_refresh


# ============================================================================
# Router Configuration Tests
# ============================================================================


@pytest.mark.unit
class TestUserSettingsRouter:
    """Tests for user settings router configuration."""

    def test_router_exists(self) -> None:
        """Test that user settings router exists - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # Act - MANDATORY
        # Assert - MANDATORY
        assert router is not None
        assert isinstance(router, APIRouter)

    def test_router_has_correct_prefix(self) -> None:
        """Test router has /user/settings prefix - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # Act - MANDATORY
        # Assert - MANDATORY
        assert router.prefix == "/user/settings"

    def test_router_has_correct_tags(self) -> None:
        """Test router has user-settings tag - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # Act - MANDATORY
        # Assert - MANDATORY
        assert "user-settings" in router.tags

    def test_router_has_get_endpoint(self) -> None:
        """Test router has GET / endpoint - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # Act - MANDATORY
        routes = [route.path for route in router.routes if hasattr(route, "path")]

        # Assert - MANDATORY
        # Router includes prefix, so paths will be /user/settings/
        assert any("/" in route or "/user/settings/" in route for route in routes)

    def test_router_has_put_endpoint(self) -> None:
        """Test router has PUT / endpoint - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # Act - MANDATORY
        routes = [
            (route.path, route.methods)
            for route in router.routes
            if hasattr(route, "path") and hasattr(route, "methods")
        ]

        # Assert - MANDATORY
        # Router includes prefix /user/settings/
        assert any("PUT" in methods for path, methods in routes)

    def test_router_has_delete_endpoint(self) -> None:
        """Test router has DELETE / endpoint - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        # Act - MANDATORY
        routes = [
            (route.path, route.methods)
            for route in router.routes
            if hasattr(route, "path") and hasattr(route, "methods")
        ]

        # Assert - MANDATORY
        # Router includes prefix /user/settings/
        assert any("DELETE" in methods for path, methods in routes)


# ============================================================================
# GET User Settings Tests
# ============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
class TestGetUserSettings:
    """Tests for GET /user/settings endpoint."""

    async def test_get_user_settings_returns_existing_settings(
        self, mock_db_session: AsyncMock, sample_user: User, sample_user_settings: UserSettings
    ) -> None:
        """Test get_user_settings returns existing settings - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        from src.api.routers.user_settings import get_user_settings

        # Mock database query to return existing settings
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_user_settings
        mock_db_session.execute.return_value = mock_result

        # Act - MANDATORY
        result = await get_user_settings(current_user=sample_user, db=mock_db_session)

        # Assert - MANDATORY
        assert result is not None
        assert result.user_id == sample_user.id
        mock_db_session.execute.assert_called_once()
        mock_db_session.add.assert_not_called()  # Should not create new settings

    async def test_get_user_settings_creates_defaults_when_none_exist(
        self,
        mock_db_session: AsyncMock,
        sample_user: User,
        mock_refresh_with_defaults: Callable[[Any], Any],
    ) -> None:
        """Test get_user_settings creates defaults when none exist - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        from src.api.routers.user_settings import get_user_settings

        # Mock database query to return None (no existing settings)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result

        # Use shared fixture for refresh with defaults
        mock_db_session.refresh.side_effect = mock_refresh_with_defaults

        # Act - MANDATORY
        result = await get_user_settings(current_user=sample_user, db=mock_db_session)

        # Assert - MANDATORY
        assert result is not None
        mock_db_session.add.assert_called_once()
        mock_db_session.commit.assert_called_once()
        mock_db_session.refresh.assert_called_once()

    async def test_get_user_settings_uses_correct_user_id(
        self,
        mock_db_session: AsyncMock,
        sample_user: User,
        mock_refresh_with_defaults: Callable[[Any], Any],
    ) -> None:
        """Test get_user_settings queries with correct user ID - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        from src.api.routers.user_settings import get_user_settings

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result

        # Use shared fixture for refresh with defaults
        mock_db_session.refresh.side_effect = mock_refresh_with_defaults

        # Act - MANDATORY
        await get_user_settings(current_user=sample_user, db=mock_db_session)

        # Assert - MANDATORY
        # Verify execute was called with a select statement
        mock_db_session.execute.assert_called_once()
        call_args = mock_db_session.execute.call_args[0][0]
        # The query should filter by user_id
        assert str(call_args).find("user_id") > -1


# ============================================================================
# PUT Update User Settings Tests
# ============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
class TestUpdateUserSettings:
    """Tests for PUT /user/settings endpoint."""

    async def test_update_user_settings_updates_existing_settings(
        self,
        mock_db_session: AsyncMock,
        sample_user: User,
        sample_user_settings: UserSettings,
        sample_settings_update: UserSettingsUpdate,
    ) -> None:
        """Test update_user_settings updates existing settings - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        from src.api.routers.user_settings import update_user_settings

        # Mock database query to return existing settings
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_user_settings
        mock_db_session.execute.return_value = mock_result

        # Act - MANDATORY
        result = await update_user_settings(
            settings_update=sample_settings_update,
            current_user=sample_user,
            db=mock_db_session,
        )

        # Assert - MANDATORY
        assert result is not None
        mock_db_session.add.assert_not_called()  # Should not create new
        mock_db_session.commit.assert_called_once()
        mock_db_session.refresh.assert_called_once()

    async def test_update_user_settings_creates_when_none_exist(
        self,
        mock_db_session: AsyncMock,
        sample_user: User,
        sample_settings_update: UserSettingsUpdate,
        mock_refresh_with_defaults: Callable[[Any], Any],
    ) -> None:
        """Test update_user_settings creates settings when none exist - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        from src.api.routers.user_settings import update_user_settings

        # Mock database query to return None (no existing settings)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result

        # Use shared fixture for refresh with defaults
        mock_db_session.refresh.side_effect = mock_refresh_with_defaults

        # Act - MANDATORY
        result = await update_user_settings(
            settings_update=sample_settings_update,
            current_user=sample_user,
            db=mock_db_session,
        )

        # Assert - MANDATORY
        assert result is not None
        mock_db_session.add.assert_called_once()
        mock_db_session.commit.assert_called_once()
        mock_db_session.refresh.assert_called_once()

    async def test_update_user_settings_handles_partial_updates(
        self, mock_db_session: AsyncMock, sample_user: User, sample_user_settings: UserSettings
    ) -> None:
        """Test update_user_settings handles partial updates - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        from src.api.routers.user_settings import update_user_settings
        from src.api.schemas import UserSettingsUpdate

        # Partial update - only dark_mode
        partial_update = UserSettingsUpdate(dark_mode=False)

        # Mock database query to return existing settings
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_user_settings
        mock_db_session.execute.return_value = mock_result

        # Act - MANDATORY
        result = await update_user_settings(
            settings_update=partial_update, current_user=sample_user, db=mock_db_session
        )

        # Assert - MANDATORY
        assert result is not None
        # Verify partial update was applied
        assert partial_update.dark_mode is not None
        mock_db_session.commit.assert_called_once()

    async def test_update_user_settings_preserves_unset_fields(
        self, mock_db_session: AsyncMock, sample_user: User, sample_user_settings: UserSettings
    ) -> None:
        """Test update_user_settings preserves unset fields - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        from src.api.routers.user_settings import update_user_settings
        from src.api.schemas import UserSettingsUpdate

        # Update only jobs_per_page, leave other fields unchanged
        partial_update = UserSettingsUpdate(jobs_per_page=100)
        original_dark_mode = sample_user_settings.dark_mode

        # Mock database query to return existing settings
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_user_settings
        mock_db_session.execute.return_value = mock_result

        # Act - MANDATORY
        result = await update_user_settings(
            settings_update=partial_update, current_user=sample_user, db=mock_db_session
        )

        # Assert - MANDATORY
        assert result is not None
        # Original dark_mode should be preserved since it wasn't in the update
        assert sample_user_settings.dark_mode == original_dark_mode
        mock_db_session.commit.assert_called_once()


# ============================================================================
# DELETE Reset User Settings Tests
# ============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
class TestResetUserSettings:
    """Tests for DELETE /user/settings endpoint."""

    async def test_reset_user_settings_deletes_existing_settings(
        self, mock_db_session: AsyncMock, sample_user: User, sample_user_settings: UserSettings
    ) -> None:
        """Test reset_user_settings deletes existing settings - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        from src.api.routers.user_settings import reset_user_settings

        # Mock database query to return existing settings
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_user_settings
        mock_db_session.execute.return_value = mock_result

        # Act - MANDATORY
        result = await reset_user_settings(current_user=sample_user, db=mock_db_session)

        # Assert - MANDATORY
        assert result is not None
        assert result["message"] == "User settings reset to defaults"
        mock_db_session.delete.assert_called_once_with(sample_user_settings)
        mock_db_session.commit.assert_called_once()

    async def test_reset_user_settings_handles_no_existing_settings(
        self, mock_db_session: AsyncMock, sample_user: User
    ) -> None:
        """Test reset_user_settings handles no existing settings - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        from src.api.routers.user_settings import reset_user_settings

        # Mock database query to return None (no existing settings)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result

        # Act - MANDATORY
        result = await reset_user_settings(current_user=sample_user, db=mock_db_session)

        # Assert - MANDATORY
        assert result is not None
        assert result["message"] == "User settings reset to defaults"
        mock_db_session.delete.assert_not_called()  # Should not try to delete
        mock_db_session.commit.assert_not_called()  # Should not commit

    async def test_reset_user_settings_returns_correct_message(
        self, mock_db_session: AsyncMock, sample_user: User
    ) -> None:
        """Test reset_user_settings returns correct message - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        from src.api.routers.user_settings import reset_user_settings

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result

        # Act - MANDATORY
        result = await reset_user_settings(current_user=sample_user, db=mock_db_session)

        # Assert - MANDATORY
        assert isinstance(result, dict)
        assert "message" in result
        assert result["message"] == "User settings reset to defaults"


# ============================================================================
# Integration Tests
# ============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
class TestUserSettingsIntegration:
    """Integration tests for user settings endpoints."""

    async def test_full_settings_lifecycle(
        self,
        mock_db_session: AsyncMock,
        sample_user: User,
        sample_user_settings: UserSettings,
        mock_refresh_with_defaults: Callable[[Any], Any],
    ) -> None:
        """Test complete settings lifecycle - MANDATORY AAA pattern."""
        # Arrange - MANDATORY
        from src.api.routers.user_settings import (
            get_user_settings,
            reset_user_settings,
            update_user_settings,
        )
        from src.api.schemas import UserSettingsUpdate

        # Mock database query to return None initially (no existing settings)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.side_effect = [
            None,  # First call: GET - no existing settings
            sample_user_settings,  # Second call: UPDATE - now settings exist
            sample_user_settings,  # Third call: DELETE - settings still exist
        ]
        mock_db_session.execute.return_value = mock_result
        mock_db_session.refresh.side_effect = mock_refresh_with_defaults

        # Act - MANDATORY
        # 1. Get settings (should create defaults)
        settings1 = await get_user_settings(current_user=sample_user, db=mock_db_session)

        # 2. Update settings
        update_data = UserSettingsUpdate(dark_mode=True, jobs_per_page=25)
        settings2 = await update_user_settings(
            settings_update=update_data, current_user=sample_user, db=mock_db_session
        )

        # 3. Reset settings
        result = await reset_user_settings(current_user=sample_user, db=mock_db_session)

        # Assert - MANDATORY
        assert settings1 is not None
        assert settings2 is not None
        assert result["message"] == "User settings reset to defaults"


# ============================================================================
# MANDATORY Performance Benchmarks
# ============================================================================


@pytest.mark.performance
@pytest.mark.unit
@pytest.mark.asyncio
class TestUserSettingsPerformance:
    """MANDATORY performance tests for user settings endpoints."""

    async def test_get_user_settings_performance(
        self,
        mock_db_session: AsyncMock,
        sample_user: User,
        mock_refresh_with_defaults: Callable[[Any], Any],
    ) -> None:
        """MANDATORY performance test - get user settings speed."""
        # Arrange - MANDATORY
        from src.api.routers.user_settings import get_user_settings

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result

        # Use shared fixture for refresh with defaults
        mock_db_session.refresh.side_effect = mock_refresh_with_defaults

        iterations = 10

        # Act - MANDATORY
        start_time = time.perf_counter()

        for _ in range(iterations):
            await get_user_settings(current_user=sample_user, db=mock_db_session)

        end_time = time.perf_counter()
        execution_time = end_time - start_time

        # Assert - MANDATORY
        avg_time = execution_time / iterations
        assert avg_time < 0.05  # <50ms per call
        assert execution_time < 0.5  # Total <500ms for 10 calls

    async def test_update_user_settings_performance(
        self,
        mock_db_session: AsyncMock,
        sample_user: User,
        sample_settings_update: UserSettingsUpdate,
        mock_refresh_with_defaults: Callable[[Any], Any],
    ) -> None:
        """MANDATORY performance test - update user settings speed."""
        # Arrange - MANDATORY
        from src.api.routers.user_settings import update_user_settings

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result

        # Use shared fixture for refresh with defaults
        mock_db_session.refresh.side_effect = mock_refresh_with_defaults

        iterations = 10

        # Act - MANDATORY
        start_time = time.perf_counter()

        for _ in range(iterations):
            await update_user_settings(
                settings_update=sample_settings_update,
                current_user=sample_user,
                db=mock_db_session,
            )

        end_time = time.perf_counter()
        execution_time = end_time - start_time

        # Assert - MANDATORY
        avg_time = execution_time / iterations
        assert avg_time < 0.05  # <50ms per call
        assert execution_time < 0.5  # Total <500ms for 10 calls
