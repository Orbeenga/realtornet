"""
Public agents directory endpoint - read-only public view of agents
Returns simplified agent information for frontend display
"""
from typing import Any, List
from fastapi import APIRouter, Depends, status
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from pydantic import BaseModel, ConfigDict

from app.api.dependencies import get_db, pagination_params
from app.models.users import User, UserRole
from app.models.agencies import Agency
from datetime import datetime
from typing import Optional

router = APIRouter()


class AgentDirectoryResponse(BaseModel):
    """Simplified agent response for public directory"""
    user_id: int
    display_name: str
    agency_id: Optional[int] = None
    agency_name: Optional[str] = None
    bio: Optional[str] = None
    profile_image_url: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


@router.get("/", response_model=List[AgentDirectoryResponse])
def read_agents_directory(
    db: Session = Depends(get_db),
    pagination: dict = Depends(pagination_params),
) -> Any:
    """
    Public agents directory.

    Returns all non-deleted agents and agency_owners with their display name and agency affiliation.
    Used to populate the frontend agents directory listing.
    """
    skip = pagination.get("skip", 0)
    limit = pagination.get("limit", 100)

    # Query users who are agents OR agency_owners, not deleted, with their agency name
    query = select(User, Agency.name).outerjoin(
        Agency, User.agency_id == Agency.agency_id
    ).where(
        User.deleted_at.is_(None),
        User.user_role.in_([UserRole.AGENT, UserRole.AGENCY_OWNER])
    ).order_by(
        User.first_name.asc(),
        User.last_name.asc()
    ).offset(skip).limit(limit)

    results = db.execute(query).all()

    # Build response with display name (first_name + last_name)
    agents = []
    for user, agency_name in results:
        # Only include agents with non-null first/last names
        first_name = user.first_name if user.first_name else ""
        last_name = user.last_name if user.last_name else ""
        display_name = f"{first_name} {last_name}".strip()

        if display_name:  # Only include agents with non-empty display names
            agents.append(AgentDirectoryResponse(
                user_id=user.user_id,
                display_name=display_name,
                agency_id=user.agency_id,
                agency_name=agency_name,
                bio=None,
                profile_image_url=user.profile_image_url,
            ))

    return agents
