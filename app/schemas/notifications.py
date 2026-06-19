"""Notification schemas for in-platform notification system."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class NotificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    notification_id: int
    user_id: int
    event_type: str
    listing_id: Optional[int] = None
    body_text: str
    is_read: bool
    created_at: datetime


class UnreadCountResponse(BaseModel):
    count: int
