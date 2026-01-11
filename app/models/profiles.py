# app/models/profiles.py
"""
Profile model - strictly matching database schema.
DB Table: profiles
"""

from sqlalchemy import Column, BigInteger, ForeignKey, Text, String
from sqlalchemy.dialects.postgresql import ENUM
from sqlalchemy.orm import relationship
import enum

from app.models.base import Base, TimestampMixin


# Enums (Match DB exactly)
class ProfileStatus(str, enum.Enum):
    """Profile status enum - matches DB USER-DEFINED type"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"


# Profile Model
class Profile(Base, TimestampMixin):
    """
    Extended profile information for users.
    Matches DB table: profiles
    Primary Key: id (bigint GENERATED ALWAYS AS IDENTITY)
    """
    __tablename__ = "profiles"
    
    # Primary key - matches DB exactly
    id = Column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
        index=True
    )
    
    # Foreign key to users (one-to-one)
    user_id = Column(
        BigInteger,
        ForeignKey("users.user_id"),
        unique=True,
        nullable=True,
        index=True
    )
    
    # Profile information
    full_name = Column(Text, nullable=False)
    phone_number = Column(Text, nullable=True)
    address = Column(Text, nullable=True)
    profile_picture = Column(Text, nullable=True)
    bio = Column(Text, nullable=True)
    
    # Status
    status = Column(
        ENUM(ProfileStatus, name="profile_status_enum", create_type=False),
        nullable=True
    )
    
    # Timestamps inherited from TimestampMixin:
    # created_at, updated_at
    
    # Relationship with User (one-to-one)
    user = relationship("User", back_populates="profile")
    
    def __repr__(self):
        return f"<Profile(id={self.id}, user_id={self.user_id}, full_name={self.full_name})>"
