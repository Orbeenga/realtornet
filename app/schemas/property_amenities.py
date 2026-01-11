# app/schemas/property_amenities.py
"""
Pydantic schemas for PropertyAmenity junction table.
Since this is a simple junction table with composite PK, schemas are minimal.
"""

from pydantic import BaseModel, ConfigDict, field_validator
from typing import List


# Base Schema (shared fields)
class PropertyAmenityBase(BaseModel):
    """Base schema for property-amenity association"""
    property_id: int
    amenity_id: int

    @field_validator('property_id', 'amenity_id')
    @classmethod
    def validate_positive_ids(cls, v: int) -> int:
        """Ensure IDs are positive"""
        if v <= 0:
            raise ValueError('ID must be positive')
        return v


# Create Schema (for POST requests)
class PropertyAmenityCreate(PropertyAmenityBase):
    """Schema for creating a property-amenity association"""
    pass


# Bulk Create Schema (for adding multiple amenities at once)
class PropertyAmenityBulkCreate(BaseModel):
    """Schema for bulk adding amenities to a property"""
    property_id: int
    amenity_ids: List[int]

    @field_validator('property_id')
    @classmethod
    def validate_property_id(cls, v: int) -> int:
        """Ensure property_id is positive"""
        if v <= 0:
            raise ValueError('property_id must be positive')
        return v

    @field_validator('amenity_ids')
    @classmethod
    def validate_amenity_ids(cls, v: List[int]) -> List[int]:
        """Ensure amenity_ids list is not empty and all positive"""
        if not v:
            raise ValueError('amenity_ids cannot be empty')
        if any(aid <= 0 for aid in v):
            raise ValueError('All amenity_ids must be positive')
        # Remove duplicates while preserving order
        seen = set()
        unique_ids = []
        for aid in v:
            if aid not in seen:
                seen.add(aid)
                unique_ids.append(aid)
        return unique_ids

    model_config = ConfigDict(from_attributes=True)


# Update/Sync Schema (for replacing all amenities)
class PropertyAmenitySync(BaseModel):
    """Schema for syncing property amenities (replaces all)"""
    amenity_ids: List[int]

    @field_validator('amenity_ids')
    @classmethod
    def validate_amenity_ids(cls, v: List[int]) -> List[int]:
        """Validate amenity IDs list"""
        # Allow empty list (removes all amenities)
        if any(aid <= 0 for aid in v):
            raise ValueError('All amenity_ids must be positive')
        # Remove duplicates
        return list(set(v))

    model_config = ConfigDict(from_attributes=True)


# Response Schema (for GET responses)
class PropertyAmenityResponse(PropertyAmenityBase):
    """
    Schema for property-amenity response.
    Note: Junction tables typically don't have their own response schema.
    Usually, endpoints return full Amenity objects instead.
    This schema exists for completeness.
    """
    model_config = ConfigDict(from_attributes=True)


# Alias for backward compatibility with existing endpoint code
PropertyAmenity = PropertyAmenityResponse