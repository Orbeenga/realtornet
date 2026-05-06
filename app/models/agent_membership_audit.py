"""Append-only agency membership state history."""

from sqlalchemy import BigInteger, CheckConstraint, Column, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import ENUM as PGEnum
from sqlalchemy.orm import relationship

from app.models.base import Base
from app.models.users import UserRole


class AgentMembershipAudit(Base):
    """Immutable memory layer for every known user/agency membership state change."""

    __tablename__ = "agent_membership_audit"

    id = Column(BigInteger, primary_key=True, autoincrement=True, index=True)
    user_id = Column(BigInteger, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, index=True)
    agency_id = Column(BigInteger, ForeignKey("agencies.agency_id", ondelete="CASCADE"), nullable=False, index=True)
    action = Column(String, nullable=False, index=True)
    actor_id = Column(BigInteger, ForeignKey("users.user_id", ondelete="SET NULL"), nullable=True, index=True)
    reason = Column(Text, nullable=True)
    prior_role = Column(
        PGEnum(
            UserRole,
            name="user_role_enum",
            values_callable=lambda x: [e.value for e in x],
            create_type=False,
        ),
        nullable=True,
    )
    post_role = Column(
        PGEnum(
            UserRole,
            name="user_role_enum",
            values_callable=lambda x: [e.value for e in x],
            create_type=False,
        ),
        nullable=True,
    )
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), index=True)

    user = relationship("User", foreign_keys=[user_id])
    agency = relationship("Agency", foreign_keys=[agency_id])
    actor = relationship("User", foreign_keys=[actor_id])

    __table_args__ = (
        CheckConstraint(
            "action IN ('invited', 'joined', 'suspended', 'revoked', 'left', 'reinstated')",
            name="agent_membership_audit_action_check",
        ),
    )
