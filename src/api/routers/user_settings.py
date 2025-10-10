"""User Settings API Router.

Handles user-specific settings management including:
- Getting user settings (with defaults for new users)
- Updating user settings
- Creating settings for new users
"""

from uuid import uuid4

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...auth.dependencies import get_current_user_from_cookie
from ...database.models.auth import User, UserSettings
from ..dependencies import get_db_session
from ..schemas import UserSettingsResponse, UserSettingsUpdate

router = APIRouter(prefix="/user/settings", tags=["user-settings"])


@router.get("/", response_model=UserSettingsResponse)
async def get_user_settings(
    current_user: User = Depends(get_current_user_from_cookie),
    db: AsyncSession = Depends(get_db_session),
) -> UserSettingsResponse:
    """
    Get current user's settings.

    If user has no settings yet, creates default settings and returns them.
    This ensures every user always has settings available.
    """
    # Query for existing settings
    query = select(UserSettings).where(UserSettings.user_id == current_user.id)
    result = await db.execute(query)
    user_settings = result.scalar_one_or_none()

    # If no settings exist, create defaults for the user
    if user_settings is None:
        user_settings = UserSettings(
            id=str(uuid4()),
            user_id=current_user.id,
            # All defaults are already defined in the model
        )
        db.add(user_settings)
        await db.commit()
        await db.refresh(user_settings)

    return UserSettingsResponse.model_validate(user_settings)


@router.put("/", response_model=UserSettingsResponse)
async def update_user_settings(
    settings_update: UserSettingsUpdate,
    current_user: User = Depends(get_current_user_from_cookie),
    db: AsyncSession = Depends(get_db_session),
) -> UserSettingsResponse:
    """
    Update current user's settings.

    Creates settings if they don't exist, otherwise updates existing settings.
    Only updates fields that are provided in the request.
    """
    # Query for existing settings
    query = select(UserSettings).where(UserSettings.user_id == current_user.id)
    result = await db.execute(query)
    user_settings = result.scalar_one_or_none()

    # Create settings if they don't exist
    if user_settings is None:
        user_settings = UserSettings(
            id=str(uuid4()),
            user_id=current_user.id,
        )
        db.add(user_settings)

    # Update only the provided fields
    update_data = settings_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if hasattr(user_settings, field):
            setattr(user_settings, field, value)

    await db.commit()
    await db.refresh(user_settings)

    return UserSettingsResponse.model_validate(user_settings)


@router.delete("/")
async def reset_user_settings(
    current_user: User = Depends(get_current_user_from_cookie),
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, str]:
    """
    Reset user settings to defaults by deleting current settings.

    Next GET request will automatically create new default settings.
    """
    # Delete existing settings
    query = select(UserSettings).where(UserSettings.user_id == current_user.id)
    result = await db.execute(query)
    user_settings = result.scalar_one_or_none()

    if user_settings:
        await db.delete(user_settings)
        await db.commit()

    return {"message": "User settings reset to defaults"}
