# app/models/agencies.py
""" 
Agency model - strictly matching database schema.
DB Table: agencies.
Phase 2 Aligned: Canonical location, soft delete, audit trail.
"""

from sqlalchemy import Column, BigInteger, String, Text, Boolean, CheckConstraint, text
from sqlalchemy.orm import relationship

from app.models.base import Base, AuditMixin, SoftDeleteMixin


class Agency(Base, AuditMixin, SoftDeleteMixin):
    # Agency model for real estate companies.
    # Matches DB table: agencies.
    # Primary Key: agency_id (bigint GENERATED ALWAYS AS IDENTITY).
    #
    # Canonical Compliance:
    # - BigInteger PK with proper naming (agency_id, not id)
    # - AuditMixin for updated_by tracking (Rule #12)
    # - SoftDeleteMixin for deleted_at (Rule #10)
    # - Proper relationship naming (agents per Option A)
    __tablename__ = "agencies"
    
    # Primary key
    agency_id = Column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
        index=True
    )
    
    # Agency information
    name = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=True)
    phone_number = Column(String, nullable=True)
    address = Column(Text, nullable=True)
    description = Column(Text, nullable=True)

    # Branding
    logo_url = Column(String, nullable=True)
    website_url = Column(String, nullable=True)
    
    # Verification status
    is_verified = Column(Boolean, nullable=True, server_default=text('false'))
    status = Column(String, nullable=False, server_default=text("'approved'"))
    owner_email = Column(String, nullable=True)
    owner_name = Column(String, nullable=True)
    owner_phone_number = Column(String, nullable=True)
    rejection_reason = Column(Text, nullable=True)
    status_reason = Column(Text, nullable=True)
    
    # Timestamps + audit + soft delete inherited from mixins:
    # - created_at, updated_at, updated_by (AuditMixin)
    # - deleted_at (SoftDeleteMixin)
    
    # Table constraints
    __table_args__ = (
        CheckConstraint(
            "email = lower(email)",
            name="agencies_email_lowercase_check"
        ),
        CheckConstraint(
            "phone_number IS NULL OR length(trim(phone_number)) > 0",
            name="agencies_phone_number_not_empty_check"
        ),
        CheckConstraint(
            "status IN ('pending', 'approved', 'rejected', 'suspended')",
            name="agencies_status_check"
        ),
    )
    
    # Relationships (using 'agents' per Option A - more intuitive)
    agents = relationship(
        "AgentProfile",
        back_populates="agency",
        cascade="all, delete-orphan"
    )
    users = relationship(
        "User",
        back_populates="agency",
        foreign_keys="User.agency_id"
    )
    
    def __repr__(self):
        return f"<Agency(agency_id={self.agency_id}, name={self.name}, is_verified={self.is_verified})>"
    
    @property
    def is_active(self) -> bool:
        """Check if agency is active (not soft deleted)."""
        return self.deleted_at is None
    
    @property
    def agent_count(self) -> int:
        """Get count of active agents (excluding soft-deleted)."""
        return sum(1 for agent in self.agents if agent.deleted_at is None)
