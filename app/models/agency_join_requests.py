# app/models/agency_join_requests.py
"""Agency join request and membership models."""

from sqlalchemy import BigInteger, CheckConstraint, Column, DateTime, ForeignKey, String, Text, UniqueConstraint, text
from sqlalchemy.orm import relationship

from app.models.base import AuditMixin, Base, SoftDeleteMixin


class AgencyJoinRequest(Base, AuditMixin, SoftDeleteMixin):
    """Request from a seeker to become an agent under a specific agency."""

    __tablename__ = "agency_join_requests"

    join_request_id = Column(BigInteger, primary_key=True, autoincrement=True, index=True)
    agency_id = Column(BigInteger, ForeignKey("agencies.agency_id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(BigInteger, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, index=True)
    cover_note = Column(Text, nullable=True)
    portfolio_details = Column(Text, nullable=True)
    status = Column(String, nullable=False, server_default=text("'pending'"))
    rejection_reason = Column(Text, nullable=True)
    decided_at = Column(DateTime(timezone=True), nullable=True)
    decided_by = Column(BigInteger, ForeignKey("users.user_id", ondelete="SET NULL"), nullable=True)

    agency = relationship("Agency", foreign_keys=[agency_id])
    user = relationship("User", foreign_keys=[user_id])
    decider = relationship("User", foreign_keys=[decided_by])

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'approved', 'rejected')",
            name="agency_join_requests_status_check",
        ),
    )

    @property
    def seeker_email(self) -> str | None:
        user_obj = self.__dict__.get("user")
        return getattr(user_obj, "email", None) if user_obj is not None else None

    @property
    def seeker_name(self) -> str | None:
        user_obj = self.__dict__.get("user")
        if user_obj is None:
            return None
        return " ".join(
            part for part in [getattr(user_obj, "first_name", None), getattr(user_obj, "last_name", None)] if part
        ) or None


class AgencyAgentMembership(Base, AuditMixin, SoftDeleteMixin):
    """Approved agent membership for an agency.

    This preserves a multi-agency representation while `users.agency_id`
    remains the user's primary agency for legacy authorization paths.
    """

    __tablename__ = "agency_agent_memberships"

    membership_id = Column(BigInteger, primary_key=True, autoincrement=True, index=True)
    agency_id = Column(BigInteger, ForeignKey("agencies.agency_id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(BigInteger, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, index=True)
    agent_profile_id = Column(
        BigInteger,
        ForeignKey("agent_profiles.profile_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    status = Column(String, nullable=False, server_default=text("'active'"))
    status_reason = Column(Text, nullable=True)
    status_decided_at = Column(DateTime(timezone=True), nullable=True)
    status_decided_by = Column(BigInteger, ForeignKey("users.user_id", ondelete="SET NULL"), nullable=True)
    source_join_request_id = Column(
        BigInteger,
        ForeignKey("agency_join_requests.join_request_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    agency = relationship("Agency", foreign_keys=[agency_id])
    user = relationship("User", foreign_keys=[user_id])
    agent_profile = relationship("AgentProfile", foreign_keys=[agent_profile_id])
    status_decider = relationship("User", foreign_keys=[status_decided_by])
    source_join_request = relationship("AgencyJoinRequest", foreign_keys=[source_join_request_id])

    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'inactive', 'suspended', 'blocked')",
            name="agency_agent_memberships_status_check",
        ),
        UniqueConstraint("agency_id", "user_id", name="agency_agent_memberships_agency_user_key"),
    )


class AgencyMembershipReviewRequest(Base, AuditMixin, SoftDeleteMixin):
    """Agent appeal for an inactive, suspended, or blocked agency membership."""

    __tablename__ = "agency_membership_review_requests"

    review_request_id = Column(BigInteger, primary_key=True, autoincrement=True, index=True)
    membership_id = Column(
        BigInteger,
        ForeignKey("agency_agent_memberships.membership_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    agency_id = Column(BigInteger, ForeignKey("agencies.agency_id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(BigInteger, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(String, nullable=False, server_default=text("'pending'"))
    reason = Column(Text, nullable=True)
    response_reason = Column(Text, nullable=True)
    decided_at = Column(DateTime(timezone=True), nullable=True)
    decided_by = Column(BigInteger, ForeignKey("users.user_id", ondelete="SET NULL"), nullable=True)

    membership = relationship("AgencyAgentMembership", foreign_keys=[membership_id])
    agency = relationship("Agency", foreign_keys=[agency_id])
    user = relationship("User", foreign_keys=[user_id])
    decider = relationship("User", foreign_keys=[decided_by])

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'reviewed', 'approved', 'rejected')",
            name="agency_membership_review_requests_status_check",
        ),
    )
