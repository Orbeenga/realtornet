# app/models/property_amenities.py
"""PropertyAmenity junction table - 100% fidelity to database schema."""

from sqlalchemy import Table, Column, BigInteger, ForeignKey

from app.models.base import Base


property_amenities = Table(
    "property_amenities",
    Base.metadata,
    Column("property_id", BigInteger, ForeignKey("properties.property_id"), primary_key=True, nullable=False),
    Column("amenity_id", BigInteger, ForeignKey("amenities.amenity_id"), primary_key=True, nullable=False),
)