# app/models/inquiries.py
"""
Inquiry model - strictly matching database schema.
DB Table: inquiries
Phase 2 Aligned: Canonical PK naming, ENUM type, soft delete
"""

from sqlalchemy import Column, BigInteger, ForeignKey, Text, Enum as SQLEnum
from sqlalchemy.orm import relationship

from app.models.base import Base, TimestampMixin, SoftDeleteMixin


class Inquiry(Base, TimestampMixin, SoftDeleteMixin):
    """
    Property inquiry model.
    Matches DB table: inquiries
    Primary Key: inquiry_id (bigint GENERATED ALWAYS AS IDENTITY)
    
    Canonical Compliance:
    - BigInteger PK with proper naming (inquiry_id, not id)
    - ENUM type matching DB (inquiry_status_enum)
    - BigInteger FKs matching referenced tables
    - SoftDeleteMixin for deleted_at
    """
    __tablename__ = "inquiries"

    # Primary key - CORRECTED to match DB naming
    inquiry_id = Column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
        index=True
    )

    # Foreign keys - CORRECTED to BigInteger
    user_id = Column(
        BigInteger, 
        ForeignKey("users.user_id", ondelete="CASCADE"), 
        nullable=True, 
        index=True
    )
    property_id = Column(
        BigInteger, 
        ForeignKey("properties.property_id", ondelete="CASCADE"), 
        nullable=True, 
        index=True
    )

    # Inquiry content
    message = Column(Text, nullable=True)

    # Status - CORRECTED to use ENUM type
    inquiry_status = Column(
        SQLEnum(
            'new', 'viewed', 'responded',
            name='inquiry_status_enum',
            create_type=False  # ENUM already exists in DB
        ),
        nullable=False,
        server_default='new',
        index=True
    )

    # Timestamps inherited from TimestampMixin:
    # - created_at, updated_at
    
    # Soft delete inherited from SoftDeleteMixin:
    # - deleted_at

    # Relationships
    property = relationship(
        "Property", 
        back_populates="inquiries",
        foreign_keys=[property_id]
    )
    user = relationship(
        "User", 
        back_populates="inquiries",
        foreign_keys=[user_id]
    )

    def __repr__(self):
        return f"<Inquiry(inquiry_id={self.inquiry_id}, status={self.inquiry_status}, user_id={self.user_id})>"