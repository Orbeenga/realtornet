# app/api/endpoints/join_requests.py
"""Authenticated join-request visibility endpoints."""

from datetime import datetime, timezone
from typing import Any, List, cast

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_active_user, get_db, pagination_params
from app.models.agencies import Agency
from app.models.agency_join_requests import AgencyJoinRequest
from app.models.users import User, UserRole
from app.schemas.agencies import MyAgencyJoinRequestResponse
from app.schemas.users import UserResponse

router = APIRouter()


@router.delete("/{request_id}/", status_code=status.HTTP_204_NO_CONTENT)
def cancel_my_join_request(
    *,
    db: Session = Depends(get_db),
    request_id: int,
    current_user: UserResponse = Depends(get_current_active_user),
) -> None:
    """Cancel a pending join request owned by the authenticated user."""
    current_user_model = cast(User, current_user)
    join_request = db.execute(
        select(AgencyJoinRequest).where(
            AgencyJoinRequest.join_request_id == request_id,
            AgencyJoinRequest.deleted_at.is_(None),
        )
    ).scalar_one_or_none()
    if join_request is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Join request not found",
        )
    if cast(int, join_request.user_id) != cast(int, current_user_model.user_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only cancel your own join requests",
        )
    if str(join_request.status) != "pending":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only pending join requests can be cancelled",
        )
    cast(Any, join_request).status = "cancelled"
    cast(Any, join_request).decided_at = datetime.now(timezone.utc)
    join_request.decided_by = current_user_model.user_id
    db.flush()


@router.get("/mine/", response_model=List[MyAgencyJoinRequestResponse])
def read_my_join_requests(
    *,
    db: Session = Depends(get_db),
    current_user: UserResponse = Depends(get_current_active_user),
    pagination: dict = Depends(pagination_params),
) -> Any:
    """Return agency join requests submitted by the authenticated seeker."""
    current_user_model = cast(User, current_user)
    current_role = cast(UserRole, current_user_model.user_role)
    if current_role not in {UserRole.SEEKER, UserRole.AGENT, UserRole.AGENCY_OWNER}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Join request history is available to seekers and agents",
        )
    query = (
        select(AgencyJoinRequest, Agency.name)
        .join(Agency, Agency.agency_id == AgencyJoinRequest.agency_id)
        .where(
            AgencyJoinRequest.user_id == current_user_model.user_id,
            AgencyJoinRequest.deleted_at.is_(None),
            Agency.deleted_at.is_(None),
        )
        .order_by(AgencyJoinRequest.created_at.desc())
        .offset(pagination["skip"])
        .limit(pagination["limit"])
    )

    rows = db.execute(query).all()
    return [
        {
            "join_request_id": join_request.join_request_id,
            "agency_id": join_request.agency_id,
            "agency_name": agency_name,
            "status": join_request.status,
            "rejection_reason": join_request.rejection_reason,
            "decided_at": join_request.decided_at,
            "decided_by": join_request.decided_by,
            "submitted_at": join_request.created_at,
        }
        for join_request, agency_name in rows
    ]
