"""Generic agency review request model."""

from sqlalchemy import BigInteger, CheckConstraint, Column, DateTime, ForeignKey, String, Text, func, text
from sqlalchemy.orm import relationship

from app.models.base import Base


class ReviewRequest(Base):
    """User request for an agency to review prior membership context."""

    __tablename__ = "review_requests"

    id = Column(BigInteger, primary_key=True, autoincrement=True, index=True)
    user_id = Column(BigInteger, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, index=True)
    agency_id = Column(BigInteger, ForeignKey("agencies.agency_id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(String, nullable=False, server_default=text("'pending'"), index=True)
    message = Column(Text, nullable=True)
    reason = Column(Text, nullable=True)
    actor_id = Column(BigInteger, ForeignKey("users.user_id", ondelete="SET NULL"), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    user = relationship("User", foreign_keys=[user_id])
    agency = relationship("Agency", foreign_keys=[agency_id])
    actor = relationship("User", foreign_keys=[actor_id])

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'accepted', 'declined')",
            name="review_requests_status_check",
        ),
    )
