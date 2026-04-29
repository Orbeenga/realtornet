"""Authenticated agency membership visibility endpoints."""

from typing import Any, List, cast

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_active_user, get_db, pagination_params
from app.models.agencies import Agency
from app.models.agency_join_requests import AgencyAgentMembership, AgencyMembershipReviewRequest
from app.models.users import User, UserRole
from app.schemas.agencies import MyAgencyMembershipResponse, MyAgentMembershipStatusResponse
from app.schemas.users import UserResponse

router = APIRouter()

MEMBERSHIP_RESTRICTION_RANK = {
    "active": 0,
    "inactive": 1,
    "suspended": 2,
    "blocked": 3,
}


def _agent_membership_status_payload(
    *,
    membership: AgencyAgentMembership | None,
    agency_name: str | None,
    current_user: User,
) -> dict[str, Any]:
    if membership is None:
        return {
            "agent_id": current_user.supabase_id,
            "status": "revoked",
            "reason": "No agency membership found",
            "updated_at": current_user.updated_at,
            "membership_id": None,
            "agency_id": None,
            "agency_name": None,
        }

    raw_status = str(membership.status)
    status_value = "revoked" if raw_status == "inactive" else raw_status
    return {
        "agent_id": current_user.supabase_id,
        "status": status_value,
        "reason": membership.status_reason,
        "updated_at": membership.status_decided_at or membership.updated_at,
        "membership_id": membership.membership_id,
        "agency_id": membership.agency_id,
        "agency_name": agency_name,
    }


@router.get("/mine/", response_model=List[MyAgencyMembershipResponse])
def read_my_agency_memberships(
    *,
    db: Session = Depends(get_db),
    current_user: UserResponse = Depends(get_current_active_user),
    pagination: dict = Depends(pagination_params),
) -> Any:
    """Return all agency memberships for the authenticated agent-facing user."""
    current_user_model = cast(User, current_user)
    current_role = cast(UserRole, current_user_model.user_role)
    if current_role not in {UserRole.SEEKER, UserRole.AGENT, UserRole.AGENCY_OWNER}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Agency membership history is available to seekers and agents",
        )

    membership_rows = db.execute(
        select(AgencyAgentMembership, Agency.name)
        .join(Agency, Agency.agency_id == AgencyAgentMembership.agency_id)
        .where(
            AgencyAgentMembership.user_id == current_user_model.user_id,
            AgencyAgentMembership.deleted_at.is_(None),
            Agency.deleted_at.is_(None),
        )
        .order_by(AgencyAgentMembership.updated_at.desc())
        .offset(pagination["skip"])
        .limit(pagination["limit"])
    ).all()

    membership_ids = [cast(int, membership.membership_id) for membership, _ in membership_rows]
    pending_reviews: dict[int, AgencyMembershipReviewRequest] = {}
    if membership_ids:
        review_rows = db.execute(
            select(AgencyMembershipReviewRequest)
            .where(
                AgencyMembershipReviewRequest.membership_id.in_(membership_ids),
                AgencyMembershipReviewRequest.status == "pending",
                AgencyMembershipReviewRequest.deleted_at.is_(None),
            )
            .order_by(AgencyMembershipReviewRequest.created_at.desc())
        ).scalars()
        for review_request in review_rows:
            membership_id = cast(int, review_request.membership_id)
            if membership_id not in pending_reviews:
                pending_reviews[membership_id] = review_request

    response_rows: list[dict[str, Any]] = []
    for membership, agency_name in membership_rows:
        membership_id = cast(int, membership.membership_id)
        pending_review = pending_reviews.get(membership_id)
        response_rows.append(
            {
                "membership_id": membership_id,
                "agency_id": membership.agency_id,
                "agency_name": agency_name,
                "status": membership.status,
                "status_reason": membership.status_reason,
                "status_decided_at": membership.status_decided_at,
                "status_decided_by": membership.status_decided_by,
                "source_join_request_id": membership.source_join_request_id,
                "pending_review_request_id": (
                    pending_review.review_request_id if pending_review is not None else None
                ),
                "pending_review_reason": pending_review.reason if pending_review is not None else None,
                "pending_review_submitted_at": pending_review.created_at if pending_review is not None else None,
                "created_at": membership.created_at,
                "updated_at": membership.updated_at,
            }
        )
    return response_rows


@router.get("/me/status", response_model=MyAgentMembershipStatusResponse)
def read_my_agent_membership_status(
    *,
    db: Session = Depends(get_db),
    current_user: UserResponse = Depends(get_current_active_user),
) -> Any:
    """Return the most restrictive agency membership state for dashboard guards."""
    current_user_model = cast(User, current_user)
    current_role = cast(UserRole, current_user_model.user_role)
    if current_role not in {UserRole.AGENT, UserRole.AGENCY_OWNER}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Agent membership status is available to agents",
        )

    rows = db.execute(
        select(AgencyAgentMembership, Agency.name)
        .join(Agency, Agency.agency_id == AgencyAgentMembership.agency_id)
        .where(
            AgencyAgentMembership.user_id == current_user_model.user_id,
            AgencyAgentMembership.deleted_at.is_(None),
            Agency.deleted_at.is_(None),
        )
    ).all()
    if not rows:
        return _agent_membership_status_payload(
            membership=None,
            agency_name=None,
            current_user=current_user_model,
        )

    selected_membership, selected_agency_name = max(
        rows,
        key=lambda row: MEMBERSHIP_RESTRICTION_RANK.get(str(row[0].status), 0),
    )
    return _agent_membership_status_payload(
        membership=selected_membership,
        agency_name=selected_agency_name,
        current_user=current_user_model,
    )
