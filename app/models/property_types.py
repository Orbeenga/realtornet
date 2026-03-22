# app/models/property_types.py
# PropertyType model - 100% fidelity to database schema.

from sqlalchemy import Column, BigInteger, String, Text
from sqlalchemy.orm import relationship

from app.models.base import Base, TimestampMixin


class PropertyType(Base, TimestampMixin):
    # Property type model (e.g., apartment, house, land).
    # Primary Key: property_type_id (bigint GENERATED ALWAYS AS IDENTITY).
    __tablename__ = "property_types"

    property_type_id = Column(BigInteger, primary_key=True, autoincrement=True)
    name = Column(String, unique=True, nullable=False)
    description = Column(Text, nullable=True)

    properties = relationship("Property", back_populates="property_type")

    def __repr__(self):
        return f"<PropertyType(property_type_id={self.property_type_id}, name={self.name})>"
