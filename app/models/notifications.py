from sqlalchemy import BigInteger, Boolean, Column, DateTime, ForeignKey, Text, func, text as sa_text
from sqlalchemy.orm import relationship

from app.models.base import Base


class Notification(Base):
    __tablename__ = "notifications"

    notification_id = Column(BigInteger, primary_key=True, autoincrement=True, index=True)
    user_id = Column(BigInteger, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, index=True)
    event_type = Column(Text, nullable=False)
    listing_id = Column(BigInteger, ForeignKey("properties.property_id", ondelete="CASCADE"), nullable=True, index=True)
    body_text = Column(Text, nullable=False)
    is_read = Column(Boolean, nullable=False, server_default=sa_text("FALSE"))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), index=True)

    user = relationship("User", foreign_keys=[user_id])
    listing = relationship("Property", foreign_keys=[listing_id])
