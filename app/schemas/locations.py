# app/schemas/locations.py
"""
Pydantic schemas for Location model.
Follows BaseSchema/CreateSchema/UpdateSchema pattern.
DB-controlled fields (location_id, timestamps) excluded from Create/Update.
"""

from pydantic import BaseModel, ConfigDict, field_validator
from typing import Optional
from datetime import datetime


# Base Schema (shared fields for responses)
class LocationBase(BaseModel):
    """Shared location fields"""
    state: str
    city: str
    neighborhood: Optional[str] = None

    @field_validator('state', 'city')
    @classmethod
    def validate_not_empty(cls, v: str) -> str:
        """Ensure required fields are not empty"""
        if not v or not v.strip():
            raise ValueError('field cannot be empty')
        return v.strip()

    @field_validator('neighborhood')
    @classmethod
    def validate_neighborhood(cls, v: Optional[str]) -> Optional[str]:
        """Ensure neighborhood is not empty if provided"""
        if v is not None and not v.strip():
            return None  # Treat empty string as None
        return v.strip() if v else None


# Create Schema (for POST requests - excludes DB-controlled fields)
class LocationCreate(LocationBase):
    """Schema for creating a new location"""
    state: str  # Required
    city: str  # Required
    # Optional: latitude/longitude for geom point
    latitude: Optional[float] = None
    longitude: Optional[float] = None

    @field_validator('latitude')
    @classmethod
    def validate_latitude(cls, v: Optional[float]) -> Optional[float]:
        """Ensure latitude is within valid range"""
        if v is not None and (v < -90 or v > 90):
            raise ValueError('latitude must be between -90 and 90')
        return v

    @field_validator('longitude')
    @classmethod
    def validate_longitude(cls, v: Optional[float]) -> Optional[float]:
        """Ensure longitude is within valid range"""
        if v is not None and (v < -180 or v > 180):
            raise ValueError('longitude must be between -180 and 180')
        return v


# Update Schema (for PATCH/PUT requests - all fields optional)
class LocationUpdate(BaseModel):
    """Schema for updating a location"""
    state: Optional[str] = None
    city: Optional[str] = None
    neighborhood: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None

    @field_validator('state', 'city')
    @classmethod
    def validate_not_empty(cls, v: Optional[str]) -> Optional[str]:
        """Ensure fields are not empty if provided"""
        if v is not None and not v.strip():
            raise ValueError('field cannot be empty')
        return v.strip() if v else None

    @field_validator('latitude')
    @classmethod
    def validate_latitude(cls, v: Optional[float]) -> Optional[float]:
        """Ensure latitude is within valid range"""
        if v is not None and (v < -90 or v > 90):
            raise ValueError('latitude must be between -90 and 90')
        return v

    @field_validator('longitude')
    @classmethod
    def validate_longitude(cls, v: Optional[float]) -> Optional[float]:
        """Ensure longitude is within valid range"""
        if v is not None and (v < -180 or v > 180):
            raise ValueError('longitude must be between -180 and 180')
        return v


# Response Schema (includes DB-controlled fields)
class LocationResponse(LocationBase):
    """Schema for location responses (includes DB-generated fields)"""
    location_id: int  # Matches DB column name exactly
    created_at: datetime
    updated_at: datetime
    # Optional: Include lat/long if geom exists
    latitude: Optional[float] = None
    longitude: Optional[float] = None

    model_config = ConfigDict(from_attributes=True)


# List Response Schema (for paginated lists)
class LocationListResponse(BaseModel):
    """Schema for paginated location lists"""
    locations: list[LocationResponse]
    total: int
    page: int
    page_size: int

    model_config = ConfigDict(from_attributes=True)


# Search/Filter Schema
class LocationFilter(BaseModel):
    """Schema for filtering/searching locations"""
    state: Optional[str] = None
    city: Optional[str] = None
    neighborhood: Optional[str] = None
    # Geo-radius search
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    radius_km: Optional[float] = None

# fastapi alias
