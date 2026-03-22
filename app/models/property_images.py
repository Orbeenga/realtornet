# app/models/property_images.py
# PropertyImage model - 100% fidelity to database schema.

from sqlalchemy import Column, Integer, BigInteger, ForeignKey, String, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import text

from app.models.base import Base, TimestampMixin


class PropertyImage(Base, TimestampMixin):
    # Property image model for property photos.
    # Primary Key: image_id (bigint GENERATED ALWAYS AS IDENTITY).
    __tablename__ = "property_images"

    image_id = Column(BigInteger, primary_key=True, autoincrement=True)
    property_id = Column(BigInteger, ForeignKey("properties.property_id"), nullable=False) # False for integrity
    image_url = Column(String, nullable=False)
    
    # Optional fields with defaults
    caption = Column(String, nullable=True)
    display_order = Column(Integer, nullable=False, server_default=text("0"))
    
    is_primary = Column(Boolean, nullable=True, server_default=text("false"))
    is_verified = Column(Boolean, nullable=True, server_default=text("false"))

    property = relationship("Property", back_populates="images")

    def __repr__(self):
        return f"<PropertyImage(image_id={self.image_id}, property_id={self.property_id})>"
