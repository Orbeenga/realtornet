# app/models/amenities.py
"""Amenity model - 100% fidelity to database schema."""

from sqlalchemy import Column, BigInteger, Text
from sqlalchemy.orm import relationship

from app.models.base import Base, TimestampMixin


class Amenity(Base, TimestampMixin):
    """
    Amenity model for property features (e.g., pool, gym, parking).
    Primary Key: id (bigint GENERATED ALWAYS AS IDENTITY)
    """
    __tablename__ = "amenities"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    name = Column(Text, unique=True, nullable=False)
    description = Column(Text, nullable=True)

    properties = relationship("Property", secondary="property_amenities", back_populates="amenities")

    def __repr__(self):
        return f"<Amenity(id={self.id}, name={self.name})>"