# app/models/users.py

""" 
User model - strictly matching database schema.
DB Tables: users
Phase 2 Aligned: Soft delete, proper FK naming, Supabase integration
"""

# from __future__ import annotations # <--- Added for forward ref support
# from typing import TYPE_CHECKING

from sqlalchemy import Column, String, Boolean, BigInteger, ForeignKey, CheckConstraint, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.types import Enum as SQLAEnum
from sqlalchemy.orm import relationship
import enum

from app.models.base import Base, AuditMixin, SoftDeleteMixin

# Prevent circular imports for type checking only
# if TYPE_CHECKING:
   # from app.models.agent_profiles import AgentProfile
   # from app.models.agencies import Agency
    # Add other models here as needed for type hints

class UserRole(str, enum.Enum):
    # User role enum - matches DB CHECK constraint exactly.
    SEEKER = "seeker"
    AGENT = "agent"
    AGENCY_OWNER = "agency_owner"
    ADMIN = "admin"

class User(Base, AuditMixin, SoftDeleteMixin):
    # User model for property seekers, agents, and admins.
    # Matches DB table: users.
    # Primary Key: user_id (bigint GENERATED ALWAYS AS IDENTITY).
    #
    # Canonical Compliance:
    # - BigInteger PK with proper naming (user_id, not id)
    # - Supabase UUID integration
    # - Soft delete via SoftDeleteMixin
    # - Audit trail via AuditMixin
    # - Multi-tenant via agency_id FK
    __tablename__ = "users"

    # Primary key
    user_id = Column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
        index=True
    )

    # Supabase Auth integration (CRITICAL for token mapping)
    supabase_id = Column(
        UUID(as_uuid=True),
        unique=True,
        nullable=False,
        index=True
    )

    # Multi-tenant: Agency relationship (Canonical requirement)
    agency_id = Column(
        BigInteger,
        ForeignKey("agencies.agency_id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )

    # Authentication fields
    email = Column(
        String,
        unique=True,
        nullable=False,
        index=True
    )
    password_hash = Column(String, nullable=False)

    # Basic information
    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)
    phone_number = Column(String, nullable=True)

    # User role and verification
    user_role = Column(
        SQLAEnum(
            UserRole,
            name="user_role_enum",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        index=True
    )
    is_verified = Column(Boolean, default=False, nullable=False)
    verification_code = Column(String, nullable=True)

    # Admin flag
    is_admin = Column(Boolean, default=False, nullable=False)

    # Profile image
    profile_image_url = Column(String, nullable=True)

    # Last login tracking
    last_login = Column(DateTime(timezone=True), nullable=True)

    # Timestamps + audit + soft delete inherited from mixins:
    # - created_at, updated_at, updated_by (AuditMixin)
    # - deleted_at, deleted_by (SoftDeleteMixin)

    # Table constraints
    __table_args__ = (
        CheckConstraint(
            "email = lower(email)",
            name="users_email_lowercase_check"
        ),
        CheckConstraint(
            "phone_number IS NULL OR length(trim(phone_number)) > 0",
            name="users_phone_number_not_empty_check"
        ),
        CheckConstraint(
            "user_role::text = ANY (ARRAY['seeker'::text, 'agent'::text, 'agency_owner'::text, 'admin'::text])",
            name="users_user_role_check"
        ),
    )

    # Relationships (using STRING literals to avoid circular imports)
    agency = relationship("Agency", back_populates="users")
    
    # Phase 2 Fix: String "AgentProfile" prevents ImportErrors
    agent_profile = relationship("AgentProfile", back_populates="user", uselist=False)
    
    # Assumes these models exist elsewhere; using strings is safe
    properties = relationship("Property", back_populates="owner", foreign_keys="Property.user_id")
    favorites = relationship("Favorite", back_populates="user")
    saved_searches = relationship("SavedSearch", back_populates="user")
    
    # Reviews
    reviews_given = relationship("Review", back_populates="user", foreign_keys="Review.user_id")
    reviews_received = relationship("Review", back_populates="agent", foreign_keys="Review.agent_id")
    
    inquiries = relationship("Inquiry", back_populates="user")
    
    # Note: If 'Profile' is a legacy table distinct from AgentProfile, keep this. 
    # If not, this might be redundant, but keeping per instructions.
    profile = relationship("Profile", back_populates="user", uselist=False)

    def __repr__(self):
        return f"<User(user_id={self.user_id}, email={self.email}, role={self.user_role})>"

    @property
    def full_name(self) -> str:
        """Helper property for display purposes."""
        return f"{self.first_name} {self.last_name}"

    @property
    def is_active(self) -> bool:
        """Check if user is active (not soft deleted)."""
        return self.deleted_at is None
