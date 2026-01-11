# app/schemas/properties.py
"""
Pydantic schemas for Property model.
Follows BaseSchema/CreateSchema/UpdateSchema pattern.
100% aligned with normalized DB schema.
"""

from pydantic import BaseModel, ConfigDict, field_validator
from typing import Optional, List
from datetime import datetime
from decimal import Decimal

# ✅ IMPORT enums from models instead of redefining them
from app.models.properties import ListingType, ListingStatus


# Base Schema (shared fields for responses)
class PropertyBase(BaseModel):
    """Shared property fields"""
    title: str
    description: str
    property_type_id: Optional[int] = None
    location_id: Optional[int] = None
    price: Decimal
    price_currency: Optional[str] = "NGN"
    bedrooms: Optional[int] = None
    bathrooms: Optional[int] = None
    property_size: Optional[Decimal] = None
    listing_type: ListingType  # ✅ Changed from ListingTypeEnum
    year_built: Optional[int] = None
    parking_spaces: Optional[int] = None
    has_garden: Optional[bool] = False
    has_security: Optional[bool] = False
    has_swimming_pool: Optional[bool] = False

    @field_validator('price')
    @classmethod
    def validate_price(cls, v: Decimal) -> Decimal:
        """Ensure price is positive (matches DB CHECK constraint)"""
        if v <= 0:
            raise ValueError('price must be greater than 0')
        return v

    @field_validator('bedrooms', 'bathrooms', 'parking_spaces')
    @classmethod
    def validate_non_negative(cls, v: Optional[int]) -> Optional[int]:
        """Ensure counts are non-negative (matches DB CHECK constraints)"""
        if v is not None and v < 0:
            raise ValueError('value must be non-negative')
        return v

    @field_validator('property_size')
    @classmethod
    def validate_property_size(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        """Ensure property_size is positive (matches DB CHECK constraint)"""
        if v is not None and v <= 0:
            raise ValueError('property_size must be greater than 0')
        return v

    @field_validator('year_built')
    @classmethod
    def validate_year_built(cls, v: Optional[int]) -> Optional[int]:
        """Ensure year_built is within valid range (matches DB CHECK constraint)"""
        from datetime import datetime
        current_year = datetime.now().year
        if v is not None and (v < 1950 or v > current_year + 2):
            raise ValueError(f'year_built must be between 1950 and {current_year + 2}')
        return v


# Create Schema (for POST requests - excludes DB-controlled fields)
class PropertyCreate(PropertyBase):
    """Schema for creating a new property"""
    user_id: int  # Required - must link to a user
    is_featured: Optional[bool] = False
    # Optional: amenity IDs to link
    amenity_ids: Optional[List[int]] = None
    # Optional: image URLs to create
    image_urls: Optional[List[str]] = None
    # Optional: latitude/longitude for geom
    latitude: Optional[float] = None
    longitude: Optional[float] = None


# Update Schema (for PATCH/PUT requests - all fields optional)
class PropertyUpdate(BaseModel):
    """Schema for updating a property"""
    title: Optional[str] = None
    description: Optional[str] = None
    property_type_id: Optional[int] = None
    location_id: Optional[int] = None
    price: Optional[Decimal] = None
    price_currency: Optional[str] = None
    bedrooms: Optional[int] = None
    bathrooms: Optional[int] = None
    property_size: Optional[Decimal] = None
    listing_type: Optional[ListingType] = None  # ✅ Changed
    listing_status: Optional[ListingStatus] = None  # ✅ Changed
    is_featured: Optional[bool] = None
    is_verified: Optional[bool] = None
    year_built: Optional[int] = None
    parking_spaces: Optional[int] = None
    has_garden: Optional[bool] = None
    has_security: Optional[bool] = None
    has_swimming_pool: Optional[bool] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None

    @field_validator('price')
    @classmethod
    def validate_price(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        """Ensure price is positive if provided"""
        if v is not None and v <= 0:
            raise ValueError('price must be greater than 0')
        return v

    @field_validator('bedrooms', 'bathrooms', 'parking_spaces')
    @classmethod
    def validate_non_negative(cls, v: Optional[int]) -> Optional[int]:
        """Ensure counts are non-negative if provided"""
        if v is not None and v < 0:
            raise ValueError('value must be non-negative')
        return v

    @field_validator('property_size')
    @classmethod
    def validate_property_size(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        """Ensure property_size is positive if provided"""
        if v is not None and v <= 0:
            raise ValueError('property_size must be greater than 0')
        return v

    @field_validator('year_built')
    @classmethod
    def validate_year_built(cls, v: Optional[int]) -> Optional[int]:
        """Ensure year_built is within valid range if provided"""
        from datetime import datetime
        current_year = datetime.now().year
        if v is not None and (v < 1950 or v > current_year + 2):
            raise ValueError(f'year_built must be between 1950 and {current_year + 2}')
        return v


# Response Schema (includes DB-controlled fields)
class PropertyResponse(PropertyBase):
    """Schema for property responses (includes DB-generated fields)"""
    property_id: int
    user_id: int
    is_featured: bool
    listing_status: ListingStatus  # ✅ Changed
    is_verified: bool
    verification_date: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# Extended Response (with nested relations)
class PropertyExtendedResponse(PropertyResponse):
    """Extended response with related data"""
    # Nested responses (import from respective schema files)
    images: Optional[List[dict]] = None  # PropertyImageResponse
    amenities: Optional[List[dict]] = None  # AmenityResponse
    location: Optional[dict] = None  # LocationResponse
    property_type: Optional[dict] = None  # PropertyTypeResponse
    owner: Optional[dict] = None  # UserResponse (basic info only)
    
    # Distance for geo queries
    distance_km: Optional[float] = None

    model_config = ConfigDict(from_attributes=True)


# Filter Schema (for search/filtering)
class PropertyFilter(BaseModel):
    """Schema for filtering properties"""
    # Location filters
    state: Optional[str] = None
    city: Optional[str] = None
    neighborhood: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    radius_km: Optional[float] = None
    
    # Price filters
    min_price: Optional[Decimal] = None
    max_price: Optional[Decimal] = None
    
    # Property attributes
    bedrooms: Optional[int] = None
    bathrooms: Optional[int] = None
    property_type_id: Optional[int] = None
    min_property_size: Optional[Decimal] = None
    max_property_size: Optional[Decimal] = None
    
    # Listing filters
    listing_type: Optional[ListingType] = None  # ✅ Changed
    listing_status: Optional[ListingStatus] = None  # ✅ Changed
    is_featured: Optional[bool] = None
    is_verified: Optional[bool] = None
    
    # New amenity filters
    min_year_built: Optional[int] = None
    max_year_built: Optional[int] = None
    min_parking_spaces: Optional[int] = None
    has_garden: Optional[bool] = None
    has_security: Optional[bool] = None
    has_swimming_pool: Optional[bool] = None
    
    # Sorting
    sort_by: Optional[str] = "created_at_desc"  # Options: price_asc, price_desc, created_at_asc, created_at_desc, distance
    
    # Pagination
    page: int = 1
    page_size: int = 20


# List Response Schema (for paginated lists)
class PropertyListResponse(BaseModel):
    """Schema for paginated property lists"""
    properties: List[PropertyResponse]
    total: int
    page: int
    page_size: int
    total_pages: int

    model_config = ConfigDict(from_attributes=True)

#  Fast API alias
Property = PropertyResponse 