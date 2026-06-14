"""Listing instructions for post-enforcement mediation (Phase N N.1)."""

from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Text, func
from sqlalchemy.orm import relationship

from app.models.base import Base


class ListingInstruction(Base):
    """Append-only record of agency instructions written in response to admin enforcement actions.

    Each instruction is tied to a specific revocation or rejection event via
    triggered_by_event_id, ensuring that instructions from prior lifecycle cycles
    do not carry over and unlock CTAs in a new cycle.
    """

    __tablename__ = "listing_instructions"

    instruction_id = Column(BigInteger, primary_key=True, autoincrement=True, index=True)
    listing_id = Column(BigInteger, ForeignKey("properties.property_id", ondelete="CASCADE"), nullable=False, index=True)
    agency_id = Column(BigInteger, ForeignKey("agencies.agency_id", ondelete="CASCADE"), nullable=False, index=True)
    actor_id = Column(BigInteger, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, index=True)
    triggered_by_event_id = Column(BigInteger, ForeignKey("listing_events.event_id", ondelete="CASCADE"), nullable=False, index=True)
    instruction_text = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    listing = relationship("Property", foreign_keys=[listing_id])
    agency = relationship("Agency", foreign_keys=[agency_id])
    actor = relationship("User", foreign_keys=[actor_id])
    triggered_by_event = relationship("ListingEvent", foreign_keys=[triggered_by_event_id])
