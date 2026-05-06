"""Membership audit read/write helpers."""

from datetime import datetime
from typing import Any, cast

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.agent_membership_audit import AgentMembershipAudit
from app.models.agencies import Agency
from app.models.users import UserRole


def serialize_user_role(value: Any) -> str | None:
    if value is None:
        return None
    role_value = getattr(value, "value", value)
    return str(role_value)


def write_membership_audit(
    *,
    db: Session,
    user_id: int,
    agency_id: int,
    action: str,
    actor_id: int | None,
    reason: str | None,
    prior_role: UserRole | str | None,
    post_role: UserRole | str | None,
    created_at: datetime | None = None,
) -> AgentMembershipAudit:
    audit = AgentMembershipAudit(
        user_id=user_id,
        agency_id=agency_id,
        action=action,
        actor_id=actor_id,
        reason=reason,
        prior_role=serialize_user_role(prior_role),
        post_role=serialize_user_role(post_role),
    )
    if created_at is not None:
        cast(Any, audit).created_at = created_at
    db.add(audit)
    db.flush()
    db.refresh(audit)
    return audit


def membership_audit_action_for_status(status_value: str) -> str:
    if status_value == "active":
        return "reinstated"
    if status_value == "suspended":
        return "suspended"
    if status_value in {"inactive", "blocked"}:
        return "revoked"
    raise ValueError(f"Unsupported membership status for audit: {status_value}")


def get_user_membership_history(
    *,
    db: Session,
    user_id: int,
    skip: int,
    limit: int,
) -> list[dict[str, Any]]:
    rows = db.execute(
        select(AgentMembershipAudit, Agency.name)
        .join(Agency, Agency.agency_id == AgentMembershipAudit.agency_id)
        .where(AgentMembershipAudit.user_id == user_id)
        .order_by(AgentMembershipAudit.created_at.desc(), AgentMembershipAudit.id.desc())
        .offset(skip)
        .limit(limit)
    ).all()
    return [_audit_payload(audit, agency_name) for audit, agency_name in rows]


def get_agency_member_history(
    *,
    db: Session,
    agency_id: int,
    user_id: int,
    skip: int,
    limit: int,
) -> list[dict[str, Any]]:
    rows = db.execute(
        select(AgentMembershipAudit, Agency.name)
        .join(Agency, Agency.agency_id == AgentMembershipAudit.agency_id)
        .where(
            AgentMembershipAudit.agency_id == agency_id,
            AgentMembershipAudit.user_id == user_id,
        )
        .order_by(AgentMembershipAudit.created_at.desc(), AgentMembershipAudit.id.desc())
        .offset(skip)
        .limit(limit)
    ).all()
    return [_audit_payload(audit, agency_name) for audit, agency_name in rows]


def _audit_payload(audit: AgentMembershipAudit, agency_name: str | None) -> dict[str, Any]:
    return {
        "id": audit.id,
        "user_id": audit.user_id,
        "agency_id": audit.agency_id,
        "agency_name": agency_name,
        "action": audit.action,
        "actor_id": audit.actor_id,
        "reason": audit.reason,
        "prior_role": audit.prior_role,
        "post_role": audit.post_role,
        "created_at": audit.created_at,
    }
