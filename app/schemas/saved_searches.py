# app/schemas/saved_searches.py
"""
Pydantic schemas for SavedSearch model.
Follows BaseSchema/CreateSchema/UpdateSchema pattern.
DB-controlled fields (search_id, timestamps) excluded from Create/Update.
"""

from pydantic import BaseModel, ConfigDict, field_validator
from typing import Optional, Dict, Any
from datetime import datetime


# Base Schema (shared fields for responses)
class SavedSearchBase(BaseModel):
    """Shared saved search fields"""
    search_params: Dict[str, Any]
    name: Optional[str] = None

    @field_validator('search_params')
    @classmethod
    def validate_search_params(cls, v: Dict[str, Any]) -> Dict[str, Any]:
        """Ensure search_params is not empty"""
        if not v:
            raise ValueError('search_params cannot be empty')
        return v

    @field_validator('name')
    @classmethod
    def validate_name(cls, v: Optional[str]) -> Optional[str]:
        """Ensure name is not empty if provided"""
        if v is not None and not v.strip():
            return None
        return v.strip() if v else None


# Create Schema (for POST requests - excludes DB-controlled fields)
class SavedSearchCreate(SavedSearchBase):
    """Schema for creating a new saved search"""
    search_params: Dict[str, Any]  # Required
    # user_id set by current_user in endpoint


# Update Schema (for PATCH/PUT requests - all fields optional)
class SavedSearchUpdate(BaseModel):
    """Schema for updating a saved search"""
    search_params: Optional[Dict[str, Any]] = None
    name: Optional[str] = None

    @field_validator('search_params')
    @classmethod
    def validate_search_params(cls, v: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Ensure search_params is not empty if provided"""
        if v is not None and not v:
            raise ValueError('search_params cannot be empty')
        return v

    @field_validator('name')
    @classmethod
    def validate_name(cls, v: Optional[str]) -> Optional[str]:
        """Ensure name is not empty if provided"""
        if v is not None and not v.strip():
            return None
        return v.strip() if v else None


# Response Schema (includes DB-controlled fields)
class SavedSearchResponse(SavedSearchBase):
    """Schema for saved search responses (includes DB-generated fields)"""
    search_id: int  # Matches DB column name exactly
    user_id: int
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# Extended Response (with nested user data)
class SavedSearchExtendedResponse(SavedSearchResponse):
    """Extended response with related user data"""
    user: Optional[dict] = None  # Can be replaced with UserResponse

    model_config = ConfigDict(from_attributes=True)


# List Response Schema (for paginated lists)
class SavedSearchListResponse(BaseModel):
    """Schema for paginated saved search lists"""
    saved_searches: list[SavedSearchResponse]
    total: int
    page: int
    page_size: int

    model_config = ConfigDict(from_attributes=True)

# alias for backward compatibility
SavedSearch = SavedSearchResponse