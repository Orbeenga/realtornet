# app/models/locations.py
"""Location model - 100% fidelity to database schema."""
from sqlalchemy.dialects.postgresql import UUID

from sqlalchemy import Column, BigInteger, String, text, Boolean
from sqlalchemy.orm import relationship
from geoalchemy2 import Geography

from app.models.base import Base, TimestampMixin, SoftDeleteMixin


class Location(Base, TimestampMixin, SoftDeleteMixin):
    """
    Location model for property addresses.
    Primary Key: location_id (bigint GENERATED ALWAYS AS IDENTITY)
    """
    __tablename__ = "locations"

    location_id = Column(BigInteger, primary_key=True, autoincrement=True)
    state = Column(String, nullable=False)
    city = Column(String, nullable=False)
    neighborhood = Column(String, nullable=True)
    geom = Column(Geography(geometry_type='POINT', srid=4326), nullable=True)
    is_active = Column(Boolean, nullable=False, server_default=text("true"))

    # Manually add updated_by (can't use AuditMixin - it adds created_by too)
    # References auth.users.id (application-level validation only)
    updated_by = Column(
        UUID(as_uuid=True),
        nullable=True,
        comment="References auth.users.id (application-level validation only)"    
    )

    properties = relationship("Property", back_populates="location")

    def __repr__(self):
        return f"<Location(location_id={self.location_id}, state={self.state}, city={self.city})>"