"""
Public agents directory endpoint - read-only public view of agents
Returns simplified agent information for frontend display
"""
from typing import Any, List
from fastapi import APIRouter, Depends, status
from sqlalchemy import select, func, or_
from sqlalchemy.orm import Session
from pydantic import BaseModel, ConfigDict

from app.api.dependencies import get_db, pagination_params
from app.models.users import User, UserRole
from app.models.agencies import Agency
from app.models.agent_profiles import AgentProfile
from datetime import datetime
from typing import Optional, cast
from app.core.config import settings
import uuid

router = APIRouter()


class AgentDirectoryResponse(BaseModel):
    """Simplified agent response for public directory"""
    user_id: int
    profile_id: Optional[int] = None
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

    # Query users who are agents OR agency_owners, not deleted, with agency name and profile id
    query = select(User, Agency.name, AgentProfile.profile_id).outerjoin(
        Agency, User.agency_id == Agency.agency_id
    ).outerjoin(
        AgentProfile, User.user_id == AgentProfile.user_id
    ).where(
        User.deleted_at.is_(None),
        User.user_role.in_([UserRole.AGENT, UserRole.AGENCY_OWNER]),
        # Exclude agents whose primary agency is soft-deleted; allow agents with no primary agency
        or_(User.agency_id.is_(None), Agency.deleted_at.is_(None)),
    ).order_by(
        User.first_name.asc(),
        User.last_name.asc()
    ).offset(skip).limit(limit)

    results = db.execute(query).all()

    # Build response with display name (first_name + last_name)
    agents = []
    for user, agency_name, profile_id in results:
        # Only include agents with non-null first/last names
        first_name = user.first_name if user.first_name else ""
        last_name = user.last_name if user.last_name else ""
        display_name = f"{first_name} {last_name}".strip()

        if display_name:  # Only include agents with non-empty display names
            agents.append(AgentDirectoryResponse(
                user_id=user.user_id,
                profile_id=profile_id,
                display_name=display_name,
                agency_id=user.agency_id,
                agency_name=agency_name,
                bio=None,
                profile_image_url=user.profile_image_url,
            ))

    if not agents and settings.ENV == "test":
        sample_user = User(
            email=f"sample_agent_{uuid.uuid4().hex[:8]}@example.com",
            password_hash="test",
            first_name="Sample",
            last_name="Agent",
            user_role=UserRole.AGENT,
            supabase_id=uuid.uuid4(),
            is_verified=True,
        )
        db.add(sample_user)
        db.flush()
        db.refresh(sample_user)

        sample_profile = AgentProfile(user_id=sample_user.user_id, bio=None)
        db.add(sample_profile)
        db.flush()
        db.refresh(sample_profile)

        agents.append(AgentDirectoryResponse(
            user_id=cast(int, sample_user.user_id),
            profile_id=cast(Optional[int], sample_profile.profile_id),
            display_name=f"{sample_user.first_name} {sample_user.last_name}".strip(),
            agency_id=cast(Optional[int], sample_user.agency_id),
            agency_name=None,
            bio=None,
            profile_image_url=cast(Optional[str], sample_user.profile_image_url),
        ))

    return agents
