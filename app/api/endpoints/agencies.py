# app/api/endpoints/agencies.py
"""
Agencies management endpoints - Canonical compliant
Handles real estate agencies (multi-tenant hub) with full audit trail and soft delete
"""
from datetime import datetime, timedelta, timezone
from typing import Any, List, cast  # Narrow dependency-backed values locally without changing the frozen endpoint contract.
from fastapi import APIRouter, Depends, HTTPException, status
from jose import JWTError, jwt
from sqlalchemy.orm import Session
import logging

# --- DIRECT CRUD IMPORTS ---
from app.crud.agencies import agency as agency_crud
from app.crud.agent_profiles import agent_profile as agent_profile_crud
from app.crud.properties import property as property_crud
from app.crud.users import user as user_crud

# --- DIRECT DEPENDENCY IMPORTS ---
from app.api.dependencies import (
    get_db,
    get_current_user,
    get_current_active_user,
    get_current_agency_owner_user,
    get_current_admin_user,
    validate_request_size,
    pagination_params,
)

# --- DIRECT SCHEMA IMPORTS ---
from app.schemas.users import UserResponse
from app.models.users import User  # Narrow endpoint-local user values back to the ORM shape expected by CRUD permission helpers.
from app.schemas.agencies import (
    AgencyResponse,
    AgencyApplicationCreate,
    AgencyApplicationResponse,
    AgencyCreate,
    AgencyInviteAcceptRequest,
    AgencyInviteAcceptResponse,
    AgencyInviteCreate,
    AgencyInviteResponse,
    AgencyUpdate
)
from app.schemas.agent_profiles import AgentProfileResponse
from app.schemas.properties import PropertyResponse
from app.core.config import settings
from app.models.users import UserRole

router = APIRouter()

# Set up logging
logger = logging.getLogger(__name__)

AGENCY_INVITE_TOKEN_TYPE = "agency_invite"


def _create_agency_invite_token(*, agency_id: int, email: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=7)
    return jwt.encode(
        {
            "token_type": AGENCY_INVITE_TOKEN_TYPE,
            "agency_id": agency_id,
            "email": email.lower(),
            "exp": int(expire.timestamp()),
            "iat": int(datetime.now(timezone.utc).timestamp()),
        },
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )


def _decode_agency_invite_token(token: str) -> dict[str, Any]:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired invite token",
        ) from exc

    if payload.get("token_type") != AGENCY_INVITE_TOKEN_TYPE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid invite token",
        )
    return payload


@router.get("/", response_model=List[AgencyResponse])
def read_agencies(
    db: Session = Depends(get_db),
    pagination: dict = Depends(pagination_params),
) -> Any:
    """
    Retrieve agencies.
    
    Public endpoint - returns only non-deleted agencies.
    Used for browsing agencies or populating agency selection.
    CRUD layer enforces deleted_at IS NULL filtering.
    """
    agencies = agency_crud.get_multi(db, **pagination,)
    return agencies


@router.post("/apply/", response_model=AgencyApplicationResponse, status_code=status.HTTP_201_CREATED)
def apply_for_agency(
    *,
    db: Session = Depends(get_db),
    agency_in: AgencyApplicationCreate,
    _: None = Depends(validate_request_size),
) -> Any:
    """
    Public agency application.

    Applications start pending. Admin approval later promotes the owner account
    attached to owner_email.
    """
    if agency_crud.get_by_name(db, name=agency_in.name):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Agency with this name already exists",
        )

    agency_email = agency_in.email or agency_in.owner_email
    if agency_email and agency_crud.get_by_email(db, email=str(agency_email)):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Agency with this email already exists",
        )

    agency = agency_crud.create_application(db, obj_in=agency_in)
    return {"agency_id": agency.agency_id, "status": agency.status}


@router.post("/accept-invite/", response_model=AgencyInviteAcceptResponse)
def accept_agency_invite(
    *,
    db: Session = Depends(get_db),
    invite_in: AgencyInviteAcceptRequest,
    _: None = Depends(validate_request_size),
) -> Any:
    payload = _decode_agency_invite_token(invite_in.invite_token)
    email = str(payload.get("email", "")).lower()
    raw_agency_id = payload.get("agency_id")
    if raw_agency_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid invite token",
        )
    agency_id = int(raw_agency_id)

    agency = agency_crud.get(db, agency_id=agency_id)
    if agency is None or str(agency.status) != "approved":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agency not found",
        )

    invited_user = user_crud.get_by_email(db, email=email)
    if invited_user is None:
        return {
            "status": "registration_required",
            "agency_id": agency_id,
            "redirect_url": f"/register?invite_token={invite_in.invite_token}",
            "email": email,
        }

    invited_user = user_crud.update(
        db,
        db_obj=invited_user,
        obj_in={"user_role": UserRole.AGENT, "agency_id": agency_id},
        updated_by=str(invited_user.supabase_id),
    )
    return {
        "status": "accepted",
        "agency_id": agency_id,
        "user_id": invited_user.user_id,
        "email": email,
    }


@router.get("/{agency_id}", response_model=AgencyResponse)
def read_agency(
    *,
    db: Session = Depends(get_db),
    agency_id: int,
) -> Any:
    """
    Get agency by ID.
    
    Public endpoint - anyone can view agency details.
    Returns 404 if agency not found or soft-deleted.
    """
    agency = agency_crud.get(db, agency_id=agency_id)
    
    if agency is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agency not found"
        )
    
    return agency


@router.post("/", response_model=AgencyResponse, status_code=status.HTTP_201_CREATED)
def create_agency(
    *,
    db: Session = Depends(get_db),
    agency_in: AgencyCreate,
    current_user: UserResponse = Depends(get_current_admin_user),
    _: None = Depends(validate_request_size)
) -> Any:
    """
    Create new agency. Admin only.
    
    Creates the multi-tenant container for agents and properties.
    Validates name and email uniqueness.
    
    Audit: Tracks creator via created_by (Supabase UUID).
    """
    # Check if agency with same name already exists
    existing_agency = agency_crud.get_by_name(db, name=agency_in.name)
    if existing_agency:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Agency with this name already exists"
        )
    
    # Check if agency with same email exists (if provided)
    if agency_in.email:
        existing_agency_email = agency_crud.get_by_email(db, email=agency_in.email)
        if existing_agency_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Agency with this email already exists"
            )
    
    # Create with audit tracking
    agency = agency_crud.create(
        db, 
        obj_in=agency_in,
        created_by=str(current_user.supabase_id)  # Normalize the dependency UUID to the CRUD audit field's string type.
    )

    logger.info("Agency created", extra={
        "agency_id": agency.agency_id,
        "agency_name": agency.name,
        "created_by": str(current_user.supabase_id)
    })

    return agency


@router.put("/{agency_id}", response_model=AgencyResponse)
def update_agency(
    *,
    db: Session = Depends(get_db),
    agency_id: int,
    agency_in: AgencyUpdate,
    current_user: UserResponse = Depends(get_current_admin_user),
    _: None = Depends(validate_request_size)
) -> Any:
    """
    Update an agency. Admin only.
    
    Validates name and email uniqueness if being changed.
    
    Audit: Tracks updater via updated_by (Supabase UUID).
    """
    agency = agency_crud.get(db, agency_id=agency_id)
    
    if agency is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agency not found"
        )
    
    # If name is being changed, check uniqueness
    if agency_in.name and agency_in.name != agency.name:
        existing_agency = agency_crud.get_by_name(db, name=agency_in.name)
        if existing_agency:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Agency with this name already exists"
            )
    
    # If email is being changed, check uniqueness
    if agency_in.email and agency_in.email != agency.email:
        existing_agency_email = agency_crud.get_by_email(db, email=agency_in.email)
        if existing_agency_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Agency with this email already exists"
            )
    
    # Update with audit tracking
    agency = agency_crud.update(
        db, 
        db_obj=agency, 
        obj_in=agency_in,
        updated_by=str(current_user.supabase_id)  # Normalize the dependency UUID to the CRUD audit field's string type.
    )

    logger.info("Agency updated", extra={
        "agency_id": agency.agency_id,
        "updated_by": str(current_user.supabase_id)
    })

    return agency


@router.delete("/{agency_id}", response_model=AgencyResponse)
def delete_agency(
    *,
    db: Session = Depends(get_db),
    agency_id: int,
    current_user: UserResponse = Depends(get_current_admin_user)
) -> Any:
    """
    Soft delete an agency. Admin only.
    
    CRITICAL: This is a multi-tenant hub operation.
    Sets deleted_at timestamp, preserves all data.
    
    Considerations:
    - Agents belonging to this agency remain (FK preserved)
    - Properties remain (FK preserved)
    - Consider business rules: prevent deletion if active agents/properties exist
    
    Audit: Tracks who deleted via deleted_by (Supabase UUID).
    """
    agency = agency_crud.get(db, agency_id=agency_id)
    
    if agency is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agency not found"
        )
    
    # Optional business rule: Prevent deletion if agency has active agents
    active_agents_count = user_crud.count_by_agency(db, agency_id=agency_id)
    if active_agents_count > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete agency with active agents. Reassign or remove agents first."
        )
    
    # Optional business rule: Prevent deletion if agency has active properties
    active_properties_count = property_crud.count_by_agency(db, agency_id=agency_id)
    if active_properties_count > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete agency with active properties. Remove properties first."
        )
    
    # Soft delete with audit trail
    agency = agency_crud.soft_delete(
        db, 
        agency_id=agency_id,
        deleted_by_supabase_id=str(current_user.supabase_id)  # Normalize the dependency UUID to the CRUD soft-delete audit field's string type.
    )

    if agency is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agency not found during delete attempt"
        )

    logger.warning("Agency soft deleted", extra={
        "agency_id": agency_id,
        "agency_name": agency.name,
        "deleted_by": str(current_user.supabase_id)
    })

    return agency


@router.get("/{agency_id}/agents", response_model=List[AgentProfileResponse])
def read_agency_agents(
    *,
    db: Session = Depends(get_db),
    agency_id: int,
    pagination: dict = Depends(pagination_params),
) -> Any:
    """
    Retrieve all agents belonging to an agency.
    
    Public endpoint - useful for "Meet Our Team" pages.
    Returns only active (non-deleted) agents.
    """
    # Verify agency exists
    agency = agency_crud.get(db, agency_id=agency_id)
    if agency is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agency not found"
        )
    
    agents = agent_profile_crud.get_by_agency(db, agency_id=agency_id, **pagination,)
    return agents


@router.get("/{agency_id}/properties", response_model=List[PropertyResponse])
def read_agency_properties(
    *,
    db: Session = Depends(get_db),
    agency_id: int,
    pagination: dict = Depends(pagination_params),
) -> Any:
    """
    Retrieve all properties managed by an agency.
    
    Public endpoint - shows agency's property portfolio.
    Returns only approved, non-deleted properties.
    """
    # Verify agency exists
    agency = agency_crud.get(db, agency_id=agency_id)
    if agency is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agency not found"
        )
    
    properties = property_crud.get_by_agency_approved(
        db, 
        agency_id=agency_id, 
        **pagination,
    )
    return properties


@router.post("/{agency_id}/invite/", response_model=AgencyInviteResponse)
def invite_agency_agent(
    *,
    db: Session = Depends(get_db),
    agency_id: int,
    invite_in: AgencyInviteCreate,
    current_user: UserResponse = Depends(get_current_agency_owner_user),
    _: None = Depends(validate_request_size),
) -> Any:
    """
    Create a signed agency invite token.

    Email delivery is intentionally deferred; Phase G returns the token directly
    so the accept-invite flow can be exercised end to end.
    """
    current_user_model = cast(User, current_user)
    current_agency_id = cast(int | None, current_user_model.agency_id)
    if current_agency_id != agency_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Agency owners can only invite agents to their own agency",
        )

    agency = agency_crud.get(db, agency_id=agency_id)
    if agency is None or str(agency.status) != "approved":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agency not found",
        )

    invite_token = _create_agency_invite_token(
        agency_id=agency_id,
        email=str(invite_in.email),
    )
    return {
        "invite_token": invite_token,
        "agency_id": agency_id,
        "email": invite_in.email,
    }


@router.get("/{agency_id}/stats")
def read_agency_stats(
    *,
    db: Session = Depends(get_db),
    agency_id: int,
    current_user: UserResponse = Depends(get_current_user)
) -> Any:
    """
    Get agency statistics.
    
    Permissions:
    - Agency agents can view their own agency stats
    - Admins can view any agency stats
    
    Returns: agent count, property count, active listings, etc.
    """
    # Verify agency exists
    agency = agency_crud.get(db, agency_id=agency_id)
    if agency is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agency not found"
        )
    
    # Check authorization: agent of this agency or admin
    current_user_model = cast(User, current_user)  # Narrow the dependency response object to the ORM user shape expected by the CRUD authorization helper.
    if not user_crud.is_admin(current_user_model):
        # Check if user is an agent of this agency
        current_agency_id = cast(int | None, current_user_model.agency_id)  # Narrow the optional ORM agency foreign key before comparing it to the route parameter.
        if current_agency_id is None or current_agency_id != agency_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not enough permissions to view this agency's statistics"
            )
    
    stats = agency_crud.get_stats(db, agency_id=agency_id)
    return stats
