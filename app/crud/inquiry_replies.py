"""CRUD operations for inquiry_replies table."""

import logging
from typing import List, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.models.inquiry_replies import InquiryReply

logger = logging.getLogger(__name__)


class InquiryReplyCRUD:
    """CRUD for inquiry replies."""

    def create(
        self,
        db: Session,
        *,
        inquiry_id: int,
        author_id: int,
        body: str,
    ) -> InquiryReply:
        obj = InquiryReply(
            inquiry_id=inquiry_id,
            author_id=author_id,
            body=body,
        )
        db.add(obj)
        db.flush()
        db.refresh(obj)
        return obj

    def get_by_inquiry(
        self,
        db: Session,
        *,
        inquiry_id: int,
        skip: int = 0,
        limit: int = 20,
    ) -> List[InquiryReply]:
        stmt = (
            select(InquiryReply)
            .options(joinedload(InquiryReply.author))
            .where(InquiryReply.inquiry_id == inquiry_id)
            .order_by(InquiryReply.created_at.asc())
            .offset(skip)
            .limit(limit)
        )
        return list(db.execute(stmt).scalars().all())

    def count_by_inquiry(self, db: Session, *, inquiry_id: int) -> int:
        stmt = select(func.count()).select_from(InquiryReply).where(
            InquiryReply.inquiry_id == inquiry_id
        )
        return int(db.execute(stmt).scalar() or 0)

    def get_latest_by_inquiry(self, db: Session, *, inquiry_id: int) -> Optional[InquiryReply]:
        stmt = (
            select(InquiryReply)
            .options(joinedload(InquiryReply.author))
            .where(InquiryReply.inquiry_id == inquiry_id)
            .order_by(InquiryReply.created_at.desc())
            .limit(1)
        )
        return db.execute(stmt).scalar_one_or_none()


inquiry_reply = InquiryReplyCRUD()
