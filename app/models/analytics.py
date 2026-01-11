# app/models/analytics.py
"""
Analytics ORM Models - Read-Only Views
Maps to DB views: active_properties, agent_performance
These are NOT tables - they are pre-computed views with SECURITY INVOKER enabled.

Usage:
- Query like normal models: db.query(ActivePropertiesView).all()
- NO INSERT/UPDATE/DELETE operations (views are read-only)
- Always current (views reflect real-time data)
"""

from sqlalchemy import Column, Integer, String, Numeric, DateTime, Boolean, Text
from sqlalchemy.dialects.postgresql import UUID
from geoalchemy2 import Geography
from app.models.base import Base


class ActivePropertiesView(Base):
    """
    Read-only ORM model for active_properties view.
    
    This view pre-computes property listings with:
    - Location data (state, city, neighborhood)
    - Property type name
    - Owner information
    - Aggregated counts (images, amenities, reviews)
    - Average rating
    
    Filters: deleted_at IS NULL (only active properties)
    RLS: security_invoker = true (caller's permissions apply)
    """
    __tablename__ = "active_properties"
    __table_args__ = {
        "info": {"is_view": True},
        "schema": "public"
    }
    
    # Primary identifier
    property_id = Column(Integer, primary_key=True)
    
    # Core property fields
    title = Column(String(255), nullable=False)
    description = Column(Text)
    user_id = Column(Integer, nullable=False)
    property_type_id = Column(Integer)
    location_id = Column(Integer)
    
    # Geography
    geom = Column(Geography(geometry_type='POINT', srid=4326))
    
    # Pricing
    price = Column(Numeric(12, 2))
    price_currency = Column(String(3))
    
    # Property details
    bedrooms = Column(Integer)
    bathrooms = Column(Numeric(3, 1))
    property_size = Column(Numeric(10, 2))
    
    # Status flags
    is_featured = Column(Boolean, default=False)
    listing_type = Column(String(50))
    listing_status = Column(String(50))
    is_verified = Column(Boolean, default=False)
    verification_date = Column(DateTime(timezone=True))
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), nullable=False)
    updated_at = Column(DateTime(timezone=True))
    updated_by = Column(UUID(as_uuid=True))
    deleted_at = Column(DateTime(timezone=True))
    
    # Joined lookup data (from view joins)
    state = Column(String(100))
    city = Column(String(100))
    neighborhood = Column(String(100))
    property_type_name = Column(String(100))
    owner_name = Column(String(200))
    owner_email = Column(String(255))
    
    # Aggregated metrics (computed by subqueries in view)
    image_count = Column(Integer, default=0)
    amenity_count = Column(Integer, default=0)
    review_count = Column(Integer, default=0)
    avg_rating = Column(Numeric(3, 2))


class AgentPerformanceView(Base):
    """
    Read-only ORM model for agent_performance view.
    
    This view pre-computes agent metrics:
    - Total/active/sold listings
    - Review count and average rating
    - Agency affiliation
    
    Filters: user_role = 'agent'
    RLS: security_invoker = true (caller's permissions apply)
    """
    __tablename__ = "agent_performance"
    __table_args__ = {
        "info": {"is_view": True},
        "schema": "public"
    }
    
    # Primary identifier
    user_id = Column(Integer, primary_key=True)
    
    # Agent identification
    agent_name = Column(String(200), nullable=False)
    license_number = Column(String(50))
    agency_name = Column(String(200))
    
    # Property listing metrics (computed by subqueries in view)
    total_listings = Column(Integer, default=0)
    active_listings = Column(Integer, default=0)
    sold_count = Column(Integer, default=0)
    
    # Review metrics (computed by subqueries in view)
    avg_rating = Column(Numeric(3, 2))
    review_count = Column(Integer, default=0)