from app.schemas.users import UserResponse
# app/api/endpoints/agent_profiles.py
"""
Agent profiles management endpoints - Canonical compliant
Handles agent professional data (1:1 with users) with agency context and full audit
"""
from typing import Any, List
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
    validate_request_size
)

# --- DIRECT SCHEMA IMPORTS ---
# Highlighting: Importing short aliases from schemas as per naming strategy
from app.schemas.users import UserResponse as UserResponse
from app.schemas.agent_profiles import (
    AgentProfileResponse, 
    AgentProfileCreate, 
    AgentProfileUpdate
)

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/", response_model=List[AgentProfileResponse])
def read_agent_profiles(
    db: Session = Depends(get_db), # Updated: Direct dependency call
    skip: int = 0,
    limit: int = 100,
    agency_id: int = None,
) -> Any:
    """
    Retrieve agent profiles with optional agency filtering.
    
    Public endpoint - returns only non-deleted, active agent profiles.
    Used for agent directory, search, or agency team pages.
    CRUD layer enforces deleted_at IS NULL filtering.
    """
    if agency_id:
        # Updated: Using direct crud alias agent_profile_crud
        agent_profiles = agent_profile_crud.get_by_agency(
            db, 
            agency_id=agency_id, 
            skip=skip, 
            limit=limit
        )
    else:
        # Updated: Using direct crud alias agent_profile_crud
        agent_profiles = agent_profile_crud.get_multi(db, skip=skip, limit=limit)
    
    return agent_profiles


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
    
    if not agent_profile:
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
    
    if not agent_profile:
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
    if not user:
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
    agency = agency_crud.get(db, agency_id=agent_profile_in.agency_id)
    if not agency:
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
        created_by=current_user.supabase_id
    )
    
    logger.info(
        "Agent profile created",
        extra={
            "profile_id": agent_profile.profile_id,
            "user_id": agent_profile.user_id,
            "agency_id": agent_profile.agency_id,
            "created_by": current_user.supabase_id
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
    
    if not agent_profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent profile not found"
        )
    
    # Check authorization - Updated: Using user_crud alias
    if agent_profile.user_id != current_user.user_id and not user_crud.is_admin(current_user):
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
        if existing_license and existing_license.profile_id != profile_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Agent with this license number already exists"
            )
    
    # Agency check - Updated: Using agency_crud alias
    if agent_profile_in.agency_id and agent_profile_in.agency_id != agent_profile.agency_id:
        agency = agency_crud.get(db, agency_id=agent_profile_in.agency_id)
        if not agency:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Agency not found"
            )
    
    # Update with audit tracking - Updated: Using agent_profile_crud alias
    agent_profile = agent_profile_crud.update(
        db, 
        db_obj=agent_profile, 
        obj_in=agent_profile_in,
        updated_by=current_user.supabase_id
    )
    
    logger.info(
        "Agent profile updated", 
        extra={
            "profile_id": agent_profile.profile_id,
            "updated_by": current_user.supabase_id
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
    
    if not agent_profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent profile not found"
        )
    
    # Check properties - Updated: Using property_crud alias
    active_properties_count = property_crud.count_by_user(db, user_id=agent_profile.user_id)
    if active_properties_count > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot delete agent profile with {active_properties_count} active properties"
        )

    # Soft delete with audit trail - Updated: Using agent_profile_crud alias
    agent_profile = agent_profile_crud.soft_delete(
        db, 
        profile_id=profile_id,
        deleted_by_supabase_id=current_user.supabase_id
    )
    
    if not agent_profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent profile not found during delete attempt"
        )
    
    logger.warning(
        "Agent profile soft deleted",
        extra={
            "profile_id": profile_id,
            "user_id": agent_profile.user_id,
            "agency_id": agent_profile.agency_id,
            "deleted_by": current_user.supabase_id
        }
    )

    return agent_profile


@router.get("/{profile_id}/properties", response_model=List[dict])
def read_agent_properties(
    *,
    db: Session = Depends(get_db), # Updated: Direct dependency call
    profile_id: int,
    skip: int = 0,
    limit: int = 100,
) -> Any:
    """
    Retrieve all properties managed by an agent.
    """
    # Updated: Using agent_profile_crud alias
    agent_profile = agent_profile_crud.get(db, profile_id=profile_id)
    if not agent_profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent profile not found"
        )
    
    # Updated: Using property_crud alias
    properties = property_crud.get_by_owner_approved(
        db, 
        user_id=agent_profile.user_id, 
        skip=skip, 
        limit=limit
    )
    return properties


@router.get("/{profile_id}/reviews", response_model=List[dict])
def read_agent_reviews(
    *,
    db: Session = Depends(get_db), # Updated: Direct dependency call
    profile_id: int,
    skip: int = 0,
    limit: int = 100,
) -> Any:
    """
    Retrieve all reviews for an agent.
    """
    # Updated: Using agent_profile_crud alias
    agent_profile = agent_profile_crud.get(db, profile_id=profile_id)
    if not agent_profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent profile not found"
        )
    
    # Updated: Using review_crud alias
    reviews = review_crud.get_agent_reviews(
        db, 
        agent_id=agent_profile.user_id, 
        skip=skip, 
        limit=limit
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
    if not agent_profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent profile not found"
        )
    
    # Updated: Using agent_profile_crud alias
    stats = agent_profile_crud.get_stats(db, profile_id=profile_id)
    return stats
