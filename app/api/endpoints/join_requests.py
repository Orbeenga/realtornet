# app/api/endpoints/join_requests.py
"""Authenticated join-request visibility endpoints."""

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
