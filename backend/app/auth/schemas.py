"""Pydantic schemas for authentication request/response.

Adapted from Digital-FTE's schemas.py pattern.
"""

import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class SignupRequest(BaseModel):
    """User registration payload."""
    username: str = Field(min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str | None = None

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        return v


class LoginRequest(BaseModel):
    """User login payload."""
    email: EmailStr
    password: str


class UserOut(BaseModel):
    """User data returned in API responses."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    username: str
    email: str
    full_name: str | None
    auth_provider: str
    is_verified: bool
    created_at: datetime


class AuthResponse(BaseModel):
    """Authentication response with JWT token."""
    message: str
    user: UserOut
    access_token: str | None = None
    token_type: str = "bearer"


class OrganizationOut(BaseModel):
    """Organization data returned in API responses."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str
    subscription_plan: str
    is_active: bool
    created_at: datetime


class CreateOrganizationRequest(BaseModel):
    """Payload for creating a new organization."""
    name: str = Field(min_length=2, max_length=255)
    slug: str = Field(min_length=2, max_length=255, pattern=r"^[a-z0-9][a-z0-9\-]*$")
    description: str | None = None
