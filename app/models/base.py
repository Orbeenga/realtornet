# app/models/base.py
# SQLAlchemy Base Configuration - Database-First Canonical Approach.
# All definitions strictly match the normalized database schema.

from sqlalchemy import MetaData, Column, DateTime, ForeignKey, Table
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, declared_attr
from sqlalchemy.sql import func


# Naming Convention (CRITICAL for Alembic autogenerate stability)
naming_convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

metadata = MetaData(naming_convention=naming_convention)


# Declarative Base
class Base(DeclarativeBase):
    # Base class for all SQLAlchemy models.
    #
    # IMPORTANT: Do NOT define generic columns here.
    # Each table has its own specific primary key naming per DB schema.
    # All timestamp and identity columns are defined per-table.
    metadata = metadata


# Mixins (Match Database Schema Exactly)
class TimestampMixin:
    # Standard timestamp fields for all tables.
    # Matches DB: timestamptz DEFAULT now().
    
    created_at = Column(
        DateTime(timezone=True),
        nullable=True,
        server_default=func.now()
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=True,
        server_default=func.now()
    )


class AuditMixin(TimestampMixin):
    # Audit trail mixin with created_by and updated_by tracking.
    # Use for: users, properties, agencies, agent_profiles, locations.
    # Matches DB: created_by and updated_by uuid.
    # Intentionally no ForeignKey (Supabase auth.users)
    @declared_attr
    def created_by(cls):
        return Column(
            UUID(as_uuid=True),
            nullable=True
        )

    @declared_attr
    def updated_by(cls):
        return Column(
            UUID(as_uuid=True),
            nullable=True
        )


class SoftDeleteMixin:
    # Soft delete functionality via deleted_at timestamp.
    # Use for: properties, reviews, inquiries, favorites, saved_searches.
    # Matches DB: deleted_at timestamp with time zone.
    deleted_at = Column(DateTime(timezone=True), nullable=True)

    # Intentionally no ForeignKey (Supabase auth.users)
    @declared_attr
    def deleted_by(cls):
        return Column(
            UUID(as_uuid=True),
            nullable=True
        )


# Export
__all__ = ["Base", "metadata", "TimestampMixin", "AuditMixin", "SoftDeleteMixin"]
