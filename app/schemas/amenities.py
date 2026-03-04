# app/schemas/amenities.py
"""
Pydantic schemas for Amenity model.
Follows BaseSchema/CreateSchema/UpdateSchema pattern.
DB-controlled fields (id, timestamps) excluded from Create/Update.
"""

from pydantic import BaseModel, ConfigDict, field_validator
from typing import Optional
from datetime import datetime


# Base Schema (shared fields for responses)
class AmenityBase(BaseModel):
    """Shared amenity fields"""
    name: str
    description: Optional[str] = None

    @field_validator('name')
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        """Ensure name is not empty or whitespace"""
        if not v or not v.strip():
            raise ValueError('name cannot be empty')
        return v.strip()


# Create Schema (for POST requests - excludes DB-controlled fields)
class AmenityCreate(AmenityBase):
    """Schema for creating a new amenity"""
    name: str  # Required, unique enforced at DB level


# Update Schema (for PATCH/PUT requests - all fields optional)
class AmenityUpdate(BaseModel):
    """Schema for updating an amenity"""
    name: Optional[str] = None
    description: Optional[str] = None

    @field_validator('name')
    @classmethod
    def name_not_empty(cls, v: Optional[str]) -> Optional[str]:
        """Ensure name is not empty or whitespace if provided"""
        if v is not None and (not v or not v.strip()):
            raise ValueError('name cannot be empty')
        return v.strip() if v else None


# Response Schema (includes DB-controlled fields)
class AmenityResponse(AmenityBase):
    """Schema for amenity responses (includes DB-generated fields)"""
    id: int  # Matches DB column name exactly
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# List Response Schema (for paginated lists)
class AmenityListResponse(BaseModel):
    """Schema for paginated amenity lists"""
    amenities: list[AmenityResponse]
    total: int
    page: int
    page_size: int

    model_config = ConfigDict(from_attributes=True)

# fastapi alias
