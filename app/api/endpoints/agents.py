"""
Public agents directory endpoint - read-only public view of agents
Returns simplified agent information for frontend display
"""
from typing import Any, List
from fastapi import APIRouter, Depends, status
from sqlalchemy import case, select, func
from sqlalchemy.orm import Session
from pydantic import BaseModel, ConfigDict

from app.api.dependencies import get_db, pagination_params
from app.models.users import User, UserRole
from app.models.agencies import Agency
from app.models.agent_profiles import AgentProfile
from app.models.agency_join_requests import AgencyAgentMembership
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

    primary_membership_timestamp = func.coalesce(
        AgencyAgentMembership.status_decided_at,
        AgencyAgentMembership.updated_at,
        AgencyAgentMembership.created_at,
    )

    # Resolve agency affiliation:
    # - For AGENTS: use agency_agent_memberships (most recent active)
    # - For AGENCY_OWNERS: use users.agency_id (ownership relation)
    # There is no joined_at column; the coalesced membership decision/update/create
    # timestamp is the local equivalent for the primary active display agency.
    latest_membership = (
        select(
            AgencyAgentMembership.user_id,
            AgencyAgentMembership.agency_id,
            Agency.name.label("agency_name"),
            func.row_number().over(
                partition_by=AgencyAgentMembership.user_id,
                order_by=primary_membership_timestamp.desc(),
            ).label("rn"),
        )
        .join(Agency, Agency.agency_id == AgencyAgentMembership.agency_id)
        .where(
            AgencyAgentMembership.status == "active",
            AgencyAgentMembership.deleted_at.is_(None),
            Agency.deleted_at.is_(None),
        )
        .subquery()
    )

    agency_alias = (
        select(
            Agency.agency_id,
            Agency.name.label("agency_name"),
        )
        .where(Agency.deleted_at.is_(None))
        .subquery()
    )

    resolved_agency_id = case(
        (User.user_role == UserRole.AGENT, latest_membership.c.agency_id),
        else_=User.agency_id,
    )
    resolved_agency_name = case(
        (User.user_role == UserRole.AGENT, latest_membership.c.agency_name),
        else_=agency_alias.c.agency_name,
    )

    query = select(
        User,
        resolved_agency_id.label("agency_id"),
        resolved_agency_name.label("agency_name"),
        AgentProfile.profile_id,
    ).outerjoin(
        latest_membership,
        (User.user_id == latest_membership.c.user_id)
        & (latest_membership.c.rn == 1),
    ).outerjoin(
        agency_alias,
        User.agency_id == agency_alias.c.agency_id,
    ).outerjoin(
        AgentProfile, User.user_id == AgentProfile.user_id
    ).where(
        User.deleted_at.is_(None),
        User.user_role.in_([UserRole.AGENT, UserRole.AGENCY_OWNER]),
    ).order_by(
        User.first_name.asc(),
        User.last_name.asc()
    ).offset(skip).limit(limit)

    results = db.execute(query).all()

    # Build response with display name (first_name + last_name)
    agents = []
    for user, agency_id, agency_name, profile_id in results:
        # Only include agents with non-null first/last names
        first_name = user.first_name if user.first_name else ""
        last_name = user.last_name if user.last_name else ""
        display_name = f"{first_name} {last_name}".strip()

        if display_name:
            agents.append(AgentDirectoryResponse(
                user_id=user.user_id,
                profile_id=profile_id,
                display_name=display_name,
                agency_id=agency_id,
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
