# app/schemas/profiles.py
"""
Pydantic schemas for Profile model.
Follows BaseSchema/CreateSchema/UpdateSchema pattern.
DB-controlled fields (id, timestamps) excluded from Create/Update.
"""

from pydantic import BaseModel, ConfigDict, field_validator
from typing import Optional
from datetime import datetime
from uuid import UUID
from enum import Enum

from app.models.profiles import ProfileStatus  # Import enum from models to ensure consistency

# Enum matching DB exactly
# class ProfileStatus(str, Enum):
    # """Profile status enum - matches DB profile_status_enum"""
    # ACTIVE = "active"
    # INACTIVE = "inactive"


# Base Schema (shared fields for responses)
class ProfileBase(BaseModel):
    """Shared profile fields"""
    full_name: str
    phone_number: Optional[str] = None
    address: Optional[str] = None
    profile_picture: Optional[str] = None
    bio: Optional[str] = None
    # status: Optional[ProfileStatus] = None

    @field_validator('full_name')
    @classmethod
    def validate_full_name(cls, v: str) -> str:
        """Ensure full_name is not empty"""
        if not v or not v.strip():
            raise ValueError('full_name cannot be empty')
        return v.strip()

    @field_validator('phone_number', 'address', 'bio')
    @classmethod
    def validate_optional_text(cls, v: Optional[str]) -> Optional[str]:
        """Ensure optional text fields are not empty strings"""
        if v is not None and not v.strip():
            return None  # Treat empty string as None
        return v.strip() if v else None


# Create Schema (for POST requests - excludes DB-controlled fields)
class ProfileCreate(ProfileBase):
    """Schema for creating a new profile"""
    # user_id comes from auth context, not request body
    full_name: str  # Required


# Update Schema (for PATCH/PUT requests - all fields optional)
class ProfileUpdate(BaseModel):
    """Schema for updating a profile"""
    full_name: Optional[str] = None
    phone_number: Optional[str] = None
    address: Optional[str] = None
    profile_picture: Optional[str] = None
    bio: Optional[str] = None
    status: Optional[ProfileStatus] = None

    @field_validator('full_name')
    @classmethod
    def validate_full_name(cls, v: Optional[str]) -> Optional[str]:
        """Ensure full_name is not empty if provided"""
        if v is not None and not v.strip():
            raise ValueError('full_name cannot be empty')
        return v.strip() if v else None

    @field_validator('phone_number', 'address', 'bio')
    @classmethod
    def validate_optional_text(cls, v: Optional[str]) -> Optional[str]:
        """Ensure optional text fields are not empty strings"""
        if v is not None and not v.strip():
            return None
        return v.strip() if v else None


# Response Schema (includes DB-controlled fields)
class ProfileResponse(ProfileBase):
    """Schema for profile responses (includes DB-generated fields)"""
    profile_id: int  # Matches DB column name exactly
    user_id: Optional[int]
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None
    created_by: Optional[UUID] = None
    updated_by: Optional[UUID] = None
    deleted_by: Optional[UUID] = None

    model_config = ConfigDict(from_attributes=True)


# Extended Response (with nested user data)
class ProfileExtendedResponse(ProfileResponse):
    """Extended response with related user data"""
    user: Optional[dict] = None  # Can be replaced with UserResponse if needed

    model_config = ConfigDict(from_attributes=True)


# List Response Schema (for paginated lists)
class ProfileListResponse(BaseModel):
    """Schema for paginated profile lists"""
    profiles: list[ProfileResponse]
    total: int
    page: int
    page_size: int

    model_config = ConfigDict(from_attributes=True)

# fastapi alias 
