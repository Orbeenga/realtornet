# app/schemas/property_images.py
"""
Pydantic schemas for PropertyImage model.
Follows BaseSchema/CreateSchema/UpdateSchema pattern.
DB-controlled fields (image_id, timestamps) excluded from Create/Update.
"""

from pydantic import BaseModel, ConfigDict, field_validator
from typing import Optional
from datetime import datetime


# Base Schema (shared fields for responses)
class PropertyImageBase(BaseModel):
    """Shared property image fields"""
    image_url: str
    caption: Optional[str] = None      # Add this
    display_order: Optional[int] = 0
    is_primary: Optional[bool] = False
    is_verified: Optional[bool] = False

    @field_validator('image_url')
    @classmethod
    def validate_image_url(cls, v: str) -> str:
        """Ensure image_url is not empty"""
        if not v or not v.strip():
            raise ValueError('image_url cannot be empty')
        return v.strip()


# Create Schema (for POST requests - excludes DB-controlled fields)
class PropertyImageCreate(PropertyImageBase):
    """Schema for creating a new property image"""
    property_id: int  # Required - must link to a property
    image_url: str  # Required


# Update Schema (for PATCH/PUT requests - all fields optional)
class PropertyImageUpdate(BaseModel):
    """Schema for updating a property image"""
    image_url: Optional[str] = None
    caption: Optional[str] = None      
    display_order: Optional[int] = None 
    is_primary: Optional[bool] = None
    is_verified: Optional[bool] = None

    @field_validator('image_url')
    @classmethod
    def validate_image_url(cls, v: Optional[str]) -> Optional[str]:
        """Ensure image_url is not empty if provided"""
        if v is not None and (not v or not v.strip()):
            raise ValueError('image_url cannot be empty')
        return v.strip() if v else None


# Response Schema (includes DB-controlled fields)
class PropertyImageResponse(PropertyImageBase):
    """Schema for property image responses (includes DB-generated fields)"""
    image_id: int  # Matches DB column name exactly
    property_id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# List Response Schema (for paginated lists)
class PropertyImageListResponse(BaseModel):
    """Schema for paginated property image lists"""
    property_images: list[PropertyImageResponse]
    total: int
    page: int
    page_size: int

    model_config = ConfigDict(from_attributes=True)


# Bulk Create Schema (for uploading multiple images at once)
class PropertyImageBulkCreate(BaseModel):
    """Schema for bulk creating property images"""
    property_id: int
    images: list[PropertyImageBase]

    @field_validator('images')
    @classmethod
    def validate_images_list(cls, v: list) -> list:
        """Ensure at least one image is provided"""
        if not v or len(v) == 0:
            raise ValueError('At least one image must be provided')
        return v

# alias for backward compatibility
