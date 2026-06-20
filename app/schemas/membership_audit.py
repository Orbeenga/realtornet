"""Schemas for membership audit history responses."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict

from app.schemas.users import UserRole


class AgentMembershipAuditResponse(BaseModel):
    id: int
    user_id: int
    agency_id: int
    agency_name: Optional[str] = None
    action: str
    actor_id: Optional[int] = None
    reason: Optional[str] = None
    prior_role: Optional[UserRole] = None
    post_role: Optional[UserRole] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AgencyMembershipHistoryResponse(AgentMembershipAuditResponse):
    user_display_name: str
