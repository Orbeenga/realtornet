# app/models/agent_profiles.py
"""
AgentProfile model - strictly matching database schema.
DB Table: agent_profiles
Phase 2 Aligned: Canonical agent data, soft delete, audit trail
"""
from __future__ import annotations # <--- Added for string forward ref support
from typing import TYPE_CHECKING

from sqlalchemy import Column, BigInteger, String, ForeignKey, Integer, Text
from sqlalchemy.orm import relationship

from app.models.base import Base, AuditMixin, SoftDeleteMixin

# Prevent circular imports for type checking only
if TYPE_CHECKING:
    from app.models.users import User
    from app.models.agencies import Agency

class AgentProfile(Base, AuditMixin, SoftDeleteMixin):
    """
    Agent profile model for real estate agents.
    Matches DB table: agent_profiles
    Primary Key: profile_id (bigint GENERATED ALWAYS AS IDENTITY)
    
    Canonical Compliance:
    - BigInteger PK/FK with proper naming
    - AuditMixin for updated_by tracking
    - SoftDeleteMixin for deleted_at
    """
    __tablename__ = "agent_profiles"
    
    # Primary key
    profile_id = Column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
        index=True
    )
    
    # Foreign keys
    # Phase 2 Fix: user_id is BigInteger to match Users.user_id
    user_id = Column(
        BigInteger,
        ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True
    )
    
    agency_id = Column(
        BigInteger,
        ForeignKey("agencies.agency_id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    
    # Agent-specific fields
    license_number = Column(String(50), nullable=True)
    specialization = Column(String(255), nullable=True)
    bio = Column(Text, nullable=True) # Changed to Text for longer bios
    years_experience = Column(Integer, nullable=True)
    website = Column(String, nullable=True)
    company_name = Column(String, nullable=True)
    
    # Timestamps + audit + soft delete inherited from mixins
    
    # Relationships
    # Phase 2 Fix: Used string literals "User" and "Agency" to prevent circular import crash
    user = relationship(
        "User",
        back_populates="agent_profile",
        foreign_keys=[user_id]
    )
    
    agency = relationship(
        "Agency",
        back_populates="agents",
        foreign_keys=[agency_id]
    )
    
    def __repr__(self):
        return f"<AgentProfile(profile_id={self.profile_id}, user_id={self.user_id}, license={self.license_number})>"