# app/api/endpoints/agency_invitations.py
"""Agent-facing agency invitation endpoints."""

from datetime import datetime, timezone
from typing import Any, List, cast

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, joinedload

from app.api.dependencies import get_current_active_user, get_db, validate_request_size
from app.api.endpoints.agencies import (
    _accept_agency_invitation_for_user,
    _agency_invitation_payload,
    _expire_invitation_if_needed,
    _get_pending_invitation_or_raise,
)
from app.models.agency_join_requests import AgencyInvitation
from app.models.users import User
from app.schemas.agencies import AgencyInvitationResponse, AgencyInviteAcceptResponse

router = APIRouter()


@router.get("/mine/", response_model=List[AgencyInvitationResponse])
def read_my_agency_invitations(
    *,
    db: Session = Depends(get_db),
    invitation_status: str = Query(default="pending", alias="status"),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """Return invitations addressed to the authenticated user's email."""
    current_user_model = cast(User, current_user)
    allowed_statuses = {"pending", "accepted", "rejected", "expired", "revoked", "all"}
    if invitation_status not in allowed_statuses:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid invitation status filter",
        )

    query = (
        select(AgencyInvitation)
        .options(joinedload(AgencyInvitation.agency))
        .where(
            AgencyInvitation.deleted_at.is_(None),
            or_(
                AgencyInvitation.email == str(current_user_model.email).lower(),
                AgencyInvitation.invited_user_id == current_user_model.user_id,
            ),
        )
        .order_by(AgencyInvitation.created_at.desc())
    )
    if invitation_status != "all":
        query = query.where(AgencyInvitation.status == invitation_status)
    invitations = list(db.execute(query).scalars().all())
    changed = False
    for invitation in invitations:
        old_status = str(invitation.status)
        _expire_invitation_if_needed(db=db, invitation=invitation)
        changed = changed or str(invitation.status) != old_status
    if changed:
        db.flush()

    return [_agency_invitation_payload(invitation) for invitation in invitations if invitation_status == "all" or str(invitation.status) == invitation_status]


@router.patch("/{invitation_id}/accept/", response_model=AgencyInviteAcceptResponse)
def accept_my_agency_invitation(
    *,
    db: Session = Depends(get_db),
    invitation_id: int,
    current_user: User = Depends(get_current_active_user),
    _: None = Depends(validate_request_size),
) -> Any:
    """Accept a pending agency invitation for the authenticated user."""
    current_user_model = cast(User, current_user)
    invitation = _get_pending_invitation_or_raise(
        db=db,
        invitation_id=invitation_id,
        current_user=current_user_model,
    )
    return _accept_agency_invitation_for_user(
        db=db,
        invitation=invitation,
        invited_user=current_user_model,
        actor=current_user_model,
    )


@router.patch("/{invitation_id}/reject/", response_model=AgencyInvitationResponse)
def reject_my_agency_invitation(
    *,
    db: Session = Depends(get_db),
    invitation_id: int,
    current_user: User = Depends(get_current_active_user),
    _: None = Depends(validate_request_size),
) -> Any:
    """Reject a pending agency invitation for the authenticated user."""
    current_user_model = cast(User, current_user)
    invitation = _get_pending_invitation_or_raise(
        db=db,
        invitation_id=invitation_id,
        current_user=current_user_model,
    )
    cast(Any, invitation).status = "rejected"
    cast(Any, invitation).rejected_at = datetime.now(timezone.utc)
    cast(Any, invitation).invited_user_id = current_user_model.user_id
    invitation.updated_by = current_user_model.supabase_id
    db.add(invitation)
    db.flush()
    db.refresh(invitation)
    return _agency_invitation_payload(invitation)
