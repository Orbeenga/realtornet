# app/models/properties.py
"""Property model - 100% fidelity to database schema."""

from sqlalchemy import Column, BigInteger, ForeignKey, String, Text, Numeric, Boolean, CheckConstraint, DateTime, Integer
from sqlalchemy.dialects.postgresql import ENUM
from sqlalchemy.orm import relationship
from geoalchemy2 import Geography
import enum

from app.models.base import Base, AuditMixin, SoftDeleteMixin


class ListingType(str, enum.Enum):  
    """Listing type enum matching DB listing_type_enum"""
    FOR_SALE = "for sale"
    FOR_RENT = "for rent"
    LEASE = "lease"


class ListingStatus(str, enum.Enum):  
    """Listing status enum matching DB listing_status_enum"""
    AVAILABLE = "available"
    ACTIVE = "active"
    PENDING = "pending"
    SOLD = "sold"
    RENTED = "rented"
    UNAVAILABLE = "unavailable"

class Property(Base, AuditMixin, SoftDeleteMixin):
    """
    Property listing model.
    Primary Key: property_id (bigint GENERATED ALWAYS AS IDENTITY)
    """
    __tablename__ = "properties"

    property_id = Column(BigInteger, primary_key=True, autoincrement=True)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    user_id = Column(BigInteger, ForeignKey("users.user_id"), nullable=True)
    property_type_id = Column(BigInteger, ForeignKey("property_types.property_type_id"), nullable=True)
    location_id = Column(BigInteger, ForeignKey("locations.location_id"), nullable=True)
    geom = Column(Geography(geometry_type='POINT', srid=4326), nullable=True)
    price = Column(Numeric(precision=12, scale=2), nullable=False)
    price_currency = Column(String, nullable=True, server_default="'NGN'::character varying")
    bedrooms = Column(Integer, nullable=True)
    bathrooms = Column(Integer, nullable=True)
    property_size = Column(Numeric(precision=10, scale=2), nullable=True)
    is_featured = Column(Boolean, nullable=True, server_default="false")
    listing_type = Column(
        ENUM(ListingType, name="listing_type_enum", create_type=False),  # ✅ Updated reference
        nullable=False
    )
    listing_status = Column(
        ENUM(ListingStatus, name="listing_status_enum", create_type=False),  # ✅ Updated reference
        nullable=False,
        server_default="'available'::listing_status_enum"
    )
    is_verified = Column(Boolean, nullable=True, server_default="false")
    verification_date = Column(DateTime(timezone=True), nullable=True)
    
    # New amenity/feature columns
    year_built = Column(Integer, nullable=True)
    parking_spaces = Column(Integer, nullable=True)
    has_garden = Column(Boolean, nullable=True, server_default="false")
    has_security = Column(Boolean, nullable=True, server_default="false")
    has_swimming_pool = Column(Boolean, nullable=True, server_default="false")

    __table_args__ = (
        CheckConstraint("price > 0::numeric", name="properties_price_check"),
        CheckConstraint("bedrooms IS NULL OR bedrooms >= 0", name="properties_bedrooms_check"),
        CheckConstraint("bathrooms IS NULL OR bathrooms >= 0", name="properties_bathrooms_check"),
        CheckConstraint("property_size IS NULL OR property_size > 0::numeric", name="properties_property_size_check"),
        CheckConstraint("year_built IS NULL OR (year_built >= 1950 AND year_built <= EXTRACT(YEAR FROM CURRENT_DATE) + 2)", name="properties_year_built_check"),
        CheckConstraint("parking_spaces IS NULL OR parking_spaces >= 0", name="properties_parking_spaces_check"),
    )

    # Relationships
    owner = relationship("User", back_populates="properties", foreign_keys=[user_id])
    property_type = relationship("PropertyType", back_populates="properties")
    location = relationship("Location", back_populates="properties")
    images = relationship("PropertyImage", back_populates="property")
    favorites = relationship("Favorite", back_populates="property")
    reviews = relationship("Review", back_populates="property")
    inquiries = relationship("Inquiry", back_populates="property")
    amenities = relationship("Amenity", secondary="property_amenities", back_populates="properties")

    def __repr__(self):
        return f"<Property(property_id={self.property_id}, title={self.title})>"