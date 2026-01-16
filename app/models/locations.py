# app/models/locations.py
"""Location model - 100% fidelity to database schema."""
from sqlalchemy import Column, ForeignKey
from sqlalchemy.dialects.postgresql import UUID

from sqlalchemy import Column, BigInteger, String
from sqlalchemy.orm import relationship
from geoalchemy2 import Geography

from app.models.base import Base, TimestampMixin, SoftdeleteMixin


class Location(Base, TimestampMixin, SoftdeleteMixin):
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

    # Manually add updated_by (can't use AuditMixin - it adds created_by too)
    updated_by = Column(
        UUID(as_uuid=True),
        ForeignKey("auth.users.id", use_alter=True, name="fk_locations_updated_by"),
        nullable=True
    )

    properties = relationship("Property", back_populates="location")

    def __repr__(self):
        return f"<Location(location_id={self.location_id}, state={self.state}, city={self.city})>"