"""CRUD operations for the notifications table."""

import logging
from typing import List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.notifications import Notification

logger = logging.getLogger(__name__)


def create_notification_fail_open(
    db: Session,
    *,
    user_id: int,
    event_type: str,
    listing_id: Optional[int],
    body_text: str,
) -> None:
    """Write a notification row with fail-open semantics.

    A notification write failure must not block the primary action.  This
    follows the same fail-open pattern as transactional email dispatch.
    On failure the notification object is expunged from the session so that
    the subsequent auto-commit in get_db does not attempt to flush a
    failed INSERT.
    """
    obj: Optional[Notification] = None
    try:
        obj = Notification(
            user_id=user_id,
            event_type=event_type,
            listing_id=listing_id,
            body_text=body_text,
            is_read=False,
        )
        db.add(obj)
        db.flush()
    except Exception:
        logger.warning(
            "Failed to write notification (user_id=%s, event_type=%s); continuing",
            user_id,
            event_type,
            exc_info=True,
        )
        if obj is not None:
            try:
                db.expunge(obj)
            except Exception:
                pass


class NotificationCRUD:
    """CRUD for in-platform notifications."""

    def create(
        self,
        db: Session,
        *,
        user_id: int,
        event_type: str,
        listing_id: Optional[int],
        body_text: str,
    ) -> Notification:
        obj = Notification(
            user_id=user_id,
            event_type=event_type,
            listing_id=listing_id,
            body_text=body_text,
            is_read=False,
        )
        db.add(obj)
        db.flush()
        db.refresh(obj)
        return obj

    def get_unread_count(self, db: Session, *, user_id: int) -> int:
        return (
            db.query(func.count(Notification.notification_id))
            .filter(
                Notification.user_id == user_id,
                Notification.is_read.is_(False),
            )
            .scalar()
            or 0
        )

    def get_notifications(
        self,
        db: Session,
        *,
        user_id: int,
        skip: int = 0,
        limit: int = 20,
    ) -> List[Notification]:
        return (
            db.query(Notification)
            .filter(Notification.user_id == user_id)
            .order_by(Notification.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def mark_as_read(
        self,
        db: Session,
        *,
        notification_id: int,
        user_id: int,
    ) -> Optional[Notification]:
        obj = (
            db.query(Notification)
            .filter(
                Notification.notification_id == notification_id,
                Notification.user_id == user_id,
            )
            .first()
        )
        if obj is None:
            return None
        obj.is_read = True  # type: ignore[reportAttributeAccessIssue]
        db.flush()
        db.refresh(obj)
        return obj

    def mark_all_as_read(self, db: Session, *, user_id: int) -> int:
        result = (
            db.query(Notification)
            .filter(
                Notification.user_id == user_id,
                Notification.is_read.is_(False),
            )
            .update(
                {Notification.is_read: True},
                synchronize_session="fetch",
            )
        )
        db.flush()
        return result


notification = NotificationCRUD()
