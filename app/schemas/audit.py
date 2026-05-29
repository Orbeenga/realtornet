"""Schemas for admin audit activity responses."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AuditCreationEntry(BaseModel):
    table_name: str
    record_id: int
    created_at: datetime
    created_by: Optional[UUID] = None
    created_by_email: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class AuditDeletionEntry(BaseModel):
    table_name: str
    record_id: int
    deleted_at: datetime
    deleted_by: Optional[UUID] = None
    deleted_by_email: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class AuditRecentChangeEntry(BaseModel):
    table_name: str
    record_id: int
    created_at: Optional[datetime] = None
    created_by: Optional[UUID] = None
    updated_at: Optional[datetime] = None
    updated_by: Optional[UUID] = None
    deleted_at: Optional[datetime] = None
    deleted_by: Optional[UUID] = None

    model_config = ConfigDict(from_attributes=True)


class AuditActivityResponse(BaseModel):
    creation_count_30d: int
    deletion_count_30d: int
    recent_changes: list[AuditRecentChangeEntry]
