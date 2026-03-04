# app/schemas/favorites.py
"""
Pydantic schemas for Favorite model (junction table).
Follows BaseSchema/CreateSchema/UpdateSchema pattern.
Composite PK (user_id, property_id) - NO id column.
"""

from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime


# Base Schema (shared fields for responses)
class FavoriteBase(BaseModel):
    """Shared favorite fields - composite key only"""
    user_id: int
    property_id: int


# Create Schema (for POST requests - no timestamps)
class FavoriteCreate(BaseModel):
    """Schema for creating a new favorite"""
    property_id: int  # user_id comes from auth context
    # Note: user_id typically set by current_user in endpoint


# No Update Schema - favorites are created or deleted, not updated


# Response Schema (includes DB-controlled fields)
class FavoriteResponse(FavoriteBase):
    """Schema for favorite responses (includes timestamps)"""
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# Extended Response (with nested property data)
class FavoriteExtendedResponse(FavoriteResponse):
    """Extended response with related property data"""
    property: Optional[dict] = None  # Can be replaced with PropertyResponse

    model_config = ConfigDict(from_attributes=True)


# List Response Schema (for paginated lists)
class FavoriteListResponse(BaseModel):
    """Schema for paginated favorite lists"""
    favorites: list[FavoriteResponse]
    total: int
    page: int
    page_size: int

    model_config = ConfigDict(from_attributes=True)

# alias for backward compatibility
