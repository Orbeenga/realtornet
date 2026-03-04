# app/schemas/agencies.py
"""
Pydantic schemas for Agency model.
Follows BaseSchema/CreateSchema/UpdateSchema pattern.
DB-controlled fields (id, timestamps) excluded from Create/Update.
"""

from pydantic import BaseModel, EmailStr, ConfigDict, field_validator
from typing import Optional
from datetime import datetime


# Base Schema (shared fields for responses)
class AgencyBase(BaseModel):
    """Shared agency fields"""
    name: str
    email: Optional[EmailStr] = None
    phone_number: Optional[str] = None
    address: Optional[str] = None
    description: Optional[str] = None
    logo_url: Optional[str] = None
    website_url: Optional[str] = None
    is_verified: Optional[bool] = False

    @field_validator('email')
    @classmethod
    def email_to_lowercase(cls, v: Optional[str]) -> Optional[str]:
        """Ensure email is lowercase (matches DB CHECK constraint)"""
        return v.lower() if v else None


# Create Schema (for POST requests - excludes DB-controlled fields)
class AgencyCreate(AgencyBase):
    """Schema for creating a new agency"""
    name: str  # Required
    # All other fields optional via inheritance


# Update Schema (for PATCH/PUT requests - all fields optional)
class AgencyUpdate(BaseModel):
    """Schema for updating an agency"""
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone_number: Optional[str] = None
    address: Optional[str] = None
    description: Optional[str] = None
    logo_url: Optional[str] = None
    website_url: Optional[str] = None
    is_verified: Optional[bool] = None

    @field_validator('email')
    @classmethod
    def email_to_lowercase(cls, v: Optional[str]) -> Optional[str]:
        """Ensure email is lowercase"""
        return v.lower() if v else None


# Response Schema (includes DB-controlled fields)
class AgencyResponse(AgencyBase):
    """Schema for agency responses (includes DB-generated fields)"""
    agency_id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# List Response Schema (for paginated lists)
class AgencyListResponse(BaseModel):
    """Schema for paginated agency lists"""
    agencies: list[AgencyResponse]
    total: int
    page: int
    page_size: int

    model_config = ConfigDict(from_attributes=True)

# Alias for backward compatibility
