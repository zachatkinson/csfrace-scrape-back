"""User management Pydantic models following SOLID principles."""

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, EmailStr, Field, field_validator

from .validation_mixins import PasswordValidatorMixin


class User(BaseModel):
    """User model for authentication - Single Responsibility."""

    id: str
    username: str
    email: EmailStr
    full_name: str | None = None
    is_active: bool = True
    is_superuser: bool = False
    created_at: datetime
    last_login: datetime | None = None


class UserInDB(User):
    """User model with hashed password for database storage - Liskov Substitution."""

    hashed_password: str


class UserCreate(BaseModel, PasswordValidatorMixin):
    """User creation request model with DRY validation."""

    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    full_name: str | None = Field(None, max_length=100)

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        """DRY: Use shared password validation."""
        return cls.validate_password_strength(v)


class OAuthUserCreate(BaseModel):
    """OAuth user creation model for passwordless authentication."""

    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    full_name: str | None = Field(None, max_length=100)

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        """Validate username format for OAuth users."""
        result = PasswordValidatorMixin.validate_username(v, allow_dots=True)
        if result is None:
            raise ValueError("Username validation failed")
        return result


class UserLogin(BaseModel):
    """User login request model - Single Responsibility."""

    username: str
    password: str


class PasswordReset(BaseModel):
    """Password reset request model - Single Responsibility."""

    email: EmailStr


class PasswordResetConfirm(BaseModel, PasswordValidatorMixin):
    """Password reset confirmation model with DRY validation."""

    token: str
    new_password: str = Field(..., min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, v: str) -> str:
        """DRY: Use shared password validation."""
        return cls.validate_password_strength(v)


class UserUpdate(BaseModel):
    """User update request model - Open/Closed Principle."""

    email: EmailStr | None = None
    full_name: str | None = Field(None, max_length=100)
    is_active: bool | None = None


class PasswordChange(BaseModel, PasswordValidatorMixin):
    """Password change request model with DRY validation."""

    current_password: str
    new_password: str = Field(..., min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, v: str) -> str:
        """DRY: Use shared password validation."""
        return cls.validate_password_strength(v)


# Type Aliases for Path Parameters - FastAPI Best Practices
UserIdPath = Annotated[str, Field(min_length=1, max_length=50, description="User ID")]
JobIdPath = Annotated[str, Field(min_length=1, max_length=50, description="Job ID")]
