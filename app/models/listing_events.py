"""Listing lifecycle events (Phase M event sourcing)."""

from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Text, func
from sqlalchemy.dialects.postgresql import ENUM as PGEnum
from sqlalchemy.orm import relationship

from app.models.base import Base
from app.models.properties import ModerationStatus


class ListingEvent(Base):
    """Append-only record of every listing moderation state transition.

    This mirrors the listing_events table created in the Phase M M.1 migration
    and is used for read-only audit views and future /properties/events/{id}/
    endpoints.
    """

    __tablename__ = "listing_events"

    event_id = Column(BigInteger, primary_key=True, autoincrement=True, index=True)
    listing_id = Column(BigInteger, ForeignKey("properties.property_id", ondelete="CASCADE"), nullable=False, index=True)
    actor_id = Column(BigInteger, ForeignKey("users.user_id", ondelete="SET NULL"), nullable=False, index=True)
    from_status = Column(
        PGEnum(
            ModerationStatus,
            name="moderation_status_enum",
            values_callable=lambda x: [e.value for e in x],
            create_type=False,
        ),
        nullable=True,
    )
    to_status = Column(
        PGEnum(
            ModerationStatus,
            name="moderation_status_enum",
            values_callable=lambda x: [e.value for e in x],
            create_type=False,
        ),
        nullable=False,
    )
    reason = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), index=True)

    listing = relationship("Property", foreign_keys=[listing_id])
    actor = relationship("User", foreign_keys=[actor_id])
