# app/api/endpoints/agent_profiles.py
"""
Agent profiles management endpoints - Canonical compliant
Handles agent professional data (1:1 with users) with agency context and full audit
"""
from typing import Any, List, cast  # Narrow dependency-backed and ORM-backed values locally without changing the frozen endpoint contract.
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
import logging

# --- DIRECT CRUD IMPORTS ---
# Highlighting: Using explicit imports to avoid partially initialized module errors
from app.crud.agent_profiles import agent_profile as agent_profile_crud
from app.crud.users import user as user_crud
from app.crud.agencies import agency as agency_crud
from app.crud.properties import property as property_crud
from app.crud.reviews import review as review_crud

# --- DIRECT DEPENDENCY IMPORTS ---
# Highlighting: Directly importing required security and DB dependencies
from app.api.dependencies import (
    get_db, 
    get_current_active_user, 
    get_current_admin_user,
    validate_request_size,
    pagination_params,
)

# --- DIRECT SCHEMA IMPORTS ---
# Highlighting: Importing short aliases from schemas as per naming strategy
from app.schemas.users import UserResponse as UserResponse
from app.models.users import User  # Narrow endpoint-local user values back to the ORM shape expected by CRUD permission helpers.
from app.schemas.agent_profiles import (
    AgentProfileResponse, 
    AgentProfileCreate, 
    AgentProfileUpdate
)
from app.schemas.properties import PropertyResponse
from app.schemas.reviews import AgentReviewResponse

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/", response_model=List[AgentProfileResponse])
def read_agent_profiles(
    db: Session = Depends(get_db), # Updated: Direct dependency call
    pagination: dict = Depends(pagination_params),
    agency_id: int | None = None,  # Treat the agency filter as optional so pyright matches the query parameter's default.
    location_id: int | None = None,
) -> Any:
    """
    Retrieve agent profiles with optional agency filtering.
    
    Public endpoint - returns only non-deleted, active agent profiles.
    Used for agent directory, search, or agency team pages.
    CRUD layer enforces deleted_at IS NULL filtering.
    """
    return agent_profile_crud.get_public_directory(
        db,
        agency_id=agency_id,
        location_id=location_id,
        **pagination,
    )


@router.get("/{profile_id}", response_model=AgentProfileResponse)
def read_agent_profile(
    *,
    db: Session = Depends(get_db), # Updated: Direct dependency call
    profile_id: int,
) -> Any:
    """
    Get agent profile by ID.
    
    Public endpoint - anyone can view agent profiles.
    Returns 404 if profile not found or soft-deleted.
    """
    # Updated: Using direct crud alias
    agent_profile = agent_profile_crud.get(db, profile_id=profile_id)
    
    if agent_profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent profile not found"
        )
    
    return agent_profile


@router.get("/by-user/{user_id}", response_model=AgentProfileResponse)
def read_agent_profile_by_user(
    *,
    db: Session = Depends(get_db), # Updated: Direct dependency call
    user_id: int,
) -> Any:
    """
    Get agent profile by user_id (1:1 relationship).
    
    Public endpoint - anyone can view agent profiles.
    Useful for getting agent details when you have user_id.
    """
    # Updated: Using direct crud alias
    agent_profile = agent_profile_crud.get_by_user_id(db, user_id=user_id)
    
    if agent_profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent profile not found for this user"
        )
    
    return agent_profile


@router.post("/", response_model=AgentProfileResponse, status_code=status.HTTP_201_CREATED)
def create_agent_profile(
    *,
    db: Session = Depends(get_db), # Updated: Direct dependency call
    agent_profile_in: AgentProfileCreate,
    current_user: UserResponse = Depends(get_current_admin_user), # Updated: Direct dependency call
    _: None = Depends(validate_request_size) # Updated: Direct dependency call
) -> Any:
    """
    Create new agent profile. Admin only.
    """
    # Verify user exists and is an agent - Updated: Using user_crud alias
    user = user_crud.get(db, user_id=agent_profile_in.user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    if not user_crud.is_agent(user):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User must have agent role to create agent profile"
        )
    
    # Check if user already has a profile (1:1 constraint) - Updated: Using agent_profile_crud alias
    existing_profile = agent_profile_crud.get_by_user_id(db, user_id=agent_profile_in.user_id)
    if existing_profile:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Agent profile already exists for this user"
        )
    
    # Verify agency exists - Updated: Using agency_crud alias
    created_agency_id = cast(int, agent_profile_in.agency_id)  # Narrow the create schema's persisted agency id before passing it into the CRUD lookup.
    agency = agency_crud.get(db, agency_id=created_agency_id)
    if agency is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agency not found"
        )
    
    # Verify license number uniqueness - Updated: Using agent_profile_crud alias
    if agent_profile_in.license_number:
        existing_license = agent_profile_crud.get_by_license(
            db, 
            license_number=agent_profile_in.license_number
        )
        if existing_license:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Agent with this license number already exists"
            )
    
    # Create with audit tracking - Updated: Using agent_profile_crud alias
    agent_profile = agent_profile_crud.create(
        db, 
        obj_in=agent_profile_in,
        created_by=str(current_user.supabase_id)  # Normalize the dependency UUID to the CRUD audit field's string type.
    )
    
    logger.info(
        "Agent profile created",
        extra={
            "profile_id": agent_profile.profile_id,
            "user_id": agent_profile.user_id,
            "agency_id": agent_profile.agency_id,
            "created_by": str(current_user.supabase_id)
        }
    )

    return agent_profile


@router.put("/{profile_id}", response_model=AgentProfileResponse)
def update_agent_profile(
    *,
    db: Session = Depends(get_db), # Updated: Direct dependency call
    profile_id: int,
    agent_profile_in: AgentProfileUpdate,
    current_user: UserResponse = Depends(get_current_active_user), # Updated: Direct dependency call
    _: None = Depends(validate_request_size) # Updated: Direct dependency call
) -> Any:
    """
    Update an agent profile.
    """
    # Updated: Using agent_profile_crud alias
    agent_profile = agent_profile_crud.get(db, profile_id=profile_id)
    
    if agent_profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent profile not found"
        )
    
    # Check authorization - Updated: Using user_crud alias
    profile_user_id = cast(int, agent_profile.user_id)  # Narrow the ORM-backed foreign key before comparing it to dependency data or CRUD helper inputs.
    current_user_id = cast(int, current_user.user_id)  # Narrow the dependency user id to a plain int for endpoint-local authorization checks.
    current_user_model = cast(User, current_user)  # Narrow the dependency response object to the ORM user shape expected by the CRUD admin helper.
    if profile_user_id != current_user_id and not user_crud.is_admin(current_user_model):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to update this agent profile"
        )
    
    # License check - Updated: Using agent_profile_crud alias
    if (agent_profile_in.license_number and 
        agent_profile_in.license_number != agent_profile.license_number):
        existing_license = agent_profile_crud.get_by_license(
            db, 
            license_number=agent_profile_in.license_number
        )
        existing_license_profile_id = cast(int, existing_license.profile_id) if existing_license is not None else None  # Narrow the ORM-backed profile id before comparing it to the route parameter.
        if existing_license_profile_id is not None and existing_license_profile_id != profile_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Agent with this license number already exists"
            )
    
    # Agency check - Updated: Using agency_crud alias
    current_agency_id = cast(int | None, agent_profile.agency_id)  # Narrow the ORM-backed optional agency foreign key before comparing it to incoming update data.
    if agent_profile_in.agency_id is not None and agent_profile_in.agency_id != current_agency_id:
        updated_agency_id = cast(int, agent_profile_in.agency_id)  # Narrow the optional incoming agency id after the explicit None guard before passing it to CRUD lookups.
        agency = agency_crud.get(db, agency_id=updated_agency_id)
        if agency is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Agency not found"
            )
    
    # Update with audit tracking - Updated: Using agent_profile_crud alias
    try:
        agent_profile = agent_profile_crud.update(
            db, 
            db_obj=agent_profile, 
            obj_in=agent_profile_in,
            updated_by=str(current_user.supabase_id)  # Normalize the dependency UUID to the CRUD audit field's string type.
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc)
        ) from exc
    
    logger.info(
        "Agent profile updated", 
        extra={
            "profile_id": agent_profile.profile_id,
            "updated_by": str(current_user.supabase_id)
        }
    )

    return agent_profile


@router.delete("/{profile_id}", response_model=AgentProfileResponse)
def delete_agent_profile(
    *,
    db: Session = Depends(get_db), # Updated: Direct dependency call
    profile_id: int,
    current_user: UserResponse = Depends(get_current_admin_user) # Updated: Direct dependency call
) -> Any:
    """
    Soft delete an agent profile. Admin only.
    """
    # Updated: Using agent_profile_crud alias
    agent_profile = agent_profile_crud.get(db, profile_id=profile_id)
    
    if agent_profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent profile not found"
        )
    
    # Check properties - Updated: Using property_crud alias
    profile_user_id = cast(int, agent_profile.user_id)  # Narrow the ORM-backed foreign key before passing it into the CRUD count helper.
    active_properties_count = property_crud.count_by_user(db, user_id=profile_user_id)
    if active_properties_count > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot delete agent profile with {active_properties_count} active properties"
        )

    # Soft delete with audit trail - Updated: Using agent_profile_crud alias
    agent_profile = agent_profile_crud.soft_delete(
        db, 
        profile_id=profile_id,
        deleted_by_supabase_id=str(current_user.supabase_id)  # Normalize the dependency UUID to the CRUD soft-delete audit field's string type.
    )
    
    if agent_profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent profile not found during delete attempt"
        )
    
    logger.warning(
        "Agent profile soft deleted",
        extra={
            "profile_id": profile_id,
            "user_id": cast(int, agent_profile.user_id),  # Narrow the ORM-backed foreign key to a plain int for structured logging.
            "agency_id": cast(int, agent_profile.agency_id),  # Narrow the ORM-backed agency key to a plain int for structured logging.
            "deleted_by": str(current_user.supabase_id)
        }
    )

    return agent_profile


@router.get("/{profile_id}/properties", response_model=List[PropertyResponse])
def read_agent_properties(
    *,
    db: Session = Depends(get_db), # Updated: Direct dependency call
    profile_id: int,
    pagination: dict = Depends(pagination_params),
) -> Any:
    """
    Retrieve all properties managed by an agent.
    """
    # Updated: Using agent_profile_crud alias
    agent_profile = agent_profile_crud.get(db, profile_id=profile_id)
    if agent_profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent profile not found"
        )
    
    # Updated: Using property_crud alias
    profile_user_id = cast(int, agent_profile.user_id)  # Narrow the ORM-backed foreign key before passing it into the CRUD list helper.
    properties = property_crud.get_by_owner_approved(
        db, 
        user_id=profile_user_id, 
        **pagination,
    )
    return properties


@router.get("/{profile_id}/reviews", response_model=List[AgentReviewResponse])
def read_agent_reviews(
    *,
    db: Session = Depends(get_db), # Updated: Direct dependency call
    profile_id: int,
    pagination: dict = Depends(pagination_params),
) -> Any:
    """
    Retrieve all reviews for an agent.
    """
    # Updated: Using agent_profile_crud alias
    agent_profile = agent_profile_crud.get(db, profile_id=profile_id)
    if agent_profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent profile not found"
        )
    
    # Updated: Using review_crud alias
    agent_user_id = cast(int, agent_profile.user_id)  # Narrow the ORM-backed foreign key before passing it into the CRUD review helper.
    reviews = review_crud.get_agent_reviews(
        db, 
        agent_id=agent_user_id, 
        **pagination,
    )
    return reviews


@router.get("/{profile_id}/stats")
def read_agent_stats(
    *,
    db: Session = Depends(get_db), # Updated: Direct dependency call
    profile_id: int,
) -> Any:
    """
    Get agent statistics.
    """
    # Updated: Using agent_profile_crud alias
    agent_profile = agent_profile_crud.get(db, profile_id=profile_id)
    if agent_profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent profile not found"
        )
    
    # Updated: Using agent_profile_crud alias
    stats = agent_profile_crud.get_stats(db, profile_id=profile_id)
    return stats
