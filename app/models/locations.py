# app/models/locations.py
"""Location model - 100% fidelity to database schema."""

from sqlalchemy import Column, BigInteger, String
from sqlalchemy.orm import relationship
from geoalchemy2 import Geography

from app.models.base import Base, AuditMixin


class Location(Base, AuditMixin):
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

    properties = relationship("Property", back_populates="location")

    def __repr__(self):
        return f"<Location(location_id={self.location_id}, state={self.state}, city={self.city})>"