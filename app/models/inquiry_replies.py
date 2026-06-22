from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Text, func
from sqlalchemy.orm import relationship

from app.models.base import Base


class InquiryReply(Base):
    __tablename__ = "inquiry_replies"

    reply_id = Column(BigInteger, primary_key=True, autoincrement=True, index=True)
    inquiry_id = Column(BigInteger, ForeignKey("inquiries.inquiry_id", ondelete="CASCADE"), nullable=False, index=True)
    author_id = Column(BigInteger, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, index=True)
    body = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    viewed_at = Column(DateTime(timezone=True), nullable=True)
    edited_at = Column(DateTime(timezone=True), nullable=True)

    inquiry = relationship("Inquiry", foreign_keys=[inquiry_id])
    author = relationship("User", foreign_keys=[author_id])
