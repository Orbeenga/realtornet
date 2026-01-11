# app/schemas/views.py
"""
Pydantic schemas for database views (read-only).
Views: active_properties, agent_performance
These are read-only views with security_invoker=true (RLS-safe).
"""

from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime
from decimal import Decimal


# ACTIVE_PROPERTIES VIEW SCHEMA

class ActivePropertyResponse(BaseModel):
    """
    Schema for active_properties view.
    Maps 1:1 to view columns (read-only, no Create/Update).
    """
    # Property fields
    property_id: int
    title: str
    description: str
    user_id: Optional[int] = None
    property_type_id: Optional[int] = None
    location_id: Optional[int] = None
    geom: Optional[str] = None  # Geography as WKT string
    price: Decimal
    price_currency: Optional[str] = None
    bedrooms: Optional[int] = None
    bathrooms: Optional[int] = None
    property_size: Optional[Decimal] = None
    is_featured: Optional[bool] = None
    listing_type: str
    listing_status: str
    is_verified: Optional[bool] = None
    verification_date: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    updated_by: Optional[str] = None
    deleted_at: Optional[datetime] = None
    
    # Joined location data
    state: Optional[str] = None
    city: Optional[str] = None
    neighborhood: Optional[str] = None
    
    # Joined property type
    property_type_name: Optional[str] = None
    
    # Joined owner data
    owner_name: Optional[str] = None
    owner_email: Optional[str] = None
    
    # Aggregated counts
    image_count: int
    amenity_count: int
    review_count: int
    avg_rating: Optional[Decimal] = None

    model_config = ConfigDict(
        from_attributes=True,
        json_encoders={
            Decimal: lambda v: float(v)
        }
    )


class ActivePropertyListResponse(BaseModel):
    """Schema for paginated active properties list"""
    properties: list[ActivePropertyResponse]
    total: int
    page: int
    page_size: int

    model_config = ConfigDict(from_attributes=True)


# AGENT_PERFORMANCE VIEW SCHEMA

class AgentPerformanceResponse(BaseModel):
    """
    Schema for agent_performance view.
    Maps 1:1 to view columns (read-only, no Create/Update).
    """
    user_id: int
    agent_name: str
    license_number: Optional[str] = None
    agency_name: Optional[str] = None
    
    # Property metrics
    total_listings: int
    active_listings: int
    sold_count: int
    
    # Review metrics
    avg_rating: Optional[Decimal] = None
    review_count: int

    model_config = ConfigDict(
        from_attributes=True,
        json_encoders={
            Decimal: lambda v: float(v)
        }
    )


class AgentPerformanceListResponse(BaseModel):
    """Schema for paginated agent performance list"""
    agents: list[AgentPerformanceResponse]
    total: int
    page: int
    page_size: int

    model_config = ConfigDict(from_attributes=True)


# VIEW FILTER SCHEMAS (for query parameters)

class ActivePropertyFilter(BaseModel):
    """Filter parameters for active_properties view"""
    state: Optional[str] = None
    city: Optional[str] = None
    neighborhood: Optional[str] = None
    property_type_name: Optional[str] = None
    min_price: Optional[Decimal] = None
    max_price: Optional[Decimal] = None
    bedrooms: Optional[int] = None
    bathrooms: Optional[int] = None
    is_featured: Optional[bool] = None
    is_verified: Optional[bool] = None
    listing_type: Optional[str] = None
    listing_status: Optional[str] = None
    # Pagination
    page: int = 1
    page_size: int = 20
    # Sorting
    sort_by: Optional[str] = "created_at_desc"


class AgentPerformanceFilter(BaseModel):
    """Filter parameters for agent_performance view"""
    agency_name: Optional[str] = None
    min_total_listings: Optional[int] = None
    min_avg_rating: Optional[Decimal] = None
    has_license: Optional[bool] = None
    # Pagination
    page: int = 1
    page_size: int = 20
    # Sorting
    sort_by: Optional[str] = "total_listings_desc"