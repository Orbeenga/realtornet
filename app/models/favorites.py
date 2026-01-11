# app/models/favorites.py
"""Favorite model - 100% fidelity to database schema."""

from sqlalchemy import Column, BigInteger, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.models.base import Base, TimestampMixin, SoftDeleteMixin


class Favorite(Base, TimestampMixin, SoftDeleteMixin):
    """
    Favorite properties model with composite primary key.
    Primary Key: (user_id, property_id)
    """
    __tablename__ = "favorites"

    user_id = Column(BigInteger, ForeignKey("users.user_id"), primary_key=True, nullable=False)
    property_id = Column(BigInteger, ForeignKey("properties.property_id"), primary_key=True, nullable=False)
    # Remove created_at/updated_at lines - inherited from mixin

    user = relationship("User", back_populates="favorites")
    property = relationship("Property", back_populates="favorites")

    def __repr__(self):
        return f"<Favorite(user_id={self.user_id}, property_id={self.property_id})>"