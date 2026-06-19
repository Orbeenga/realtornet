"""Notification endpoints — in-platform notification polling, read, and badge count."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_active_user, get_db
from app.crud.notifications import notification as notification_crud
from app.schemas.notifications import NotificationResponse, UnreadCountResponse
from app.schemas.users import UserResponse

router = APIRouter()


@router.get("/", response_model=list[NotificationResponse])
def get_notifications(
    *,
    db: Session = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=50),
    current_user: UserResponse = Depends(get_current_active_user),
) -> Any:
    """Return notifications for the current user, newest first. Default 20, cap 50."""
    return notification_crud.get_notifications(
        db,
        user_id=current_user.user_id,
        skip=skip,
        limit=limit,
    )


@router.get("/unread-count", response_model=UnreadCountResponse)
def get_unread_count(
    *,
    db: Session = Depends(get_db),
    current_user: UserResponse = Depends(get_current_active_user),
) -> Any:
    """Return the unread notification count for the badge."""
    count = notification_crud.get_unread_count(db, user_id=current_user.user_id)
    return UnreadCountResponse(count=count)


@router.patch("/{notification_id}/read", response_model=NotificationResponse)
def mark_notification_read(
    *,
    db: Session = Depends(get_db),
    notification_id: int,
    current_user: UserResponse = Depends(get_current_active_user),
) -> Any:
    """Mark a single notification as read."""
    obj = notification_crud.mark_as_read(
        db,
        notification_id=notification_id,
        user_id=current_user.user_id,
    )
    if obj is None:
        raise HTTPException(status_code=404, detail="Notification not found")
    return obj


@router.patch("/read-all", response_model=dict)
def mark_all_notifications_read(
    *,
    db: Session = Depends(get_db),
    current_user: UserResponse = Depends(get_current_active_user),
) -> Any:
    """Mark all unread notifications as read for the current user."""
    updated = notification_crud.mark_all_as_read(db, user_id=current_user.user_id)
    return {"updated": updated}
