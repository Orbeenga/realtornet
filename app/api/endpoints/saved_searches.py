# app/api/endpoints/saved_searches.py
"""
Saved searches management endpoints - Canonical compliant
Handles user search preferences with JSONB criteria storage, soft delete, and audit tracking
"""
from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
import logging

# --- DIRECT CRUD IMPORTS ---
from app.crud.saved_searches import saved_search as saved_search_crud
from app.crud.users import user as user_crud

# --- DIRECT DEPENDENCY IMPORTS ---
from app.api.dependencies import (
    get_db,
    get_current_user,
    get_current_active_user,
    validate_request_size
)

# --- DIRECT SCHEMA IMPORTS ---
from app.schemas.users import UserResponse
from app.schemas.saved_searches import (
    SavedSearchResponse,
    SavedSearchCreate,
    SavedSearchUpdate
)

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/", response_model=SavedSearchResponse, status_code=status.HTTP_201_CREATED)
def create_saved_search(
    *,
    db: Session = Depends(get_db),
    saved_search_in: SavedSearchCreate,
    current_user: UserResponse = Depends(get_current_active_user),
    _: None = Depends(validate_request_size)
) -> Any:
    """
    Create a new saved search for the current user.
    
    Search criteria stored as JSONB for flexible filtering.
    Audit: Tracks creator via user_id FK.
    """
    # Create saved search with user association
    saved_search = saved_search_crud.create(
        db=db,
        obj_in=saved_search_in,
        user_id=current_user.user_id  # FK to users table
    )
    return saved_search


@router.get("/", response_model=List[SavedSearchResponse])
def read_user_saved_searches(
    db: Session = Depends(get_db),
    current_user: UserResponse = Depends(get_current_user),
    skip: int = 0,
    limit: int = 100,
) -> Any:
    """
    Retrieve all saved searches for the current user.
    
    Returns only active (non-deleted) searches.
    CRUD layer enforces deleted_at IS NULL filtering.
    """
    saved_searches = saved_search_crud.get_user_saved_searches(
        db=db,
        user_id=current_user.user_id,
        skip=skip,
        limit=limit
    )
    return saved_searches


@router.get("/{search_id}", response_model=SavedSearchResponse)
def read_saved_search(
    *,
    db: Session = Depends(get_db),
    search_id: int,
    current_user: UserResponse = Depends(get_current_user)
) -> Any:
    """
    Get a specific saved search by ID.
    
    Users can only access their own searches (unless admin).
    """
    saved_search = saved_search_crud.get(db=db, search_id=search_id)
    
    if not saved_search:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Saved search not found"
        )

    # Check authorization
    if saved_search.user_id != current_user.user_id and not user_crud.is_admin(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to access this saved search"
        )

    return saved_search


@router.put("/{search_id}", response_model=SavedSearchResponse)
def update_saved_search(
    *,
    db: Session = Depends(get_db),
    search_id: int,
    saved_search_in: SavedSearchUpdate,
    current_user: UserResponse = Depends(get_current_active_user),
    _: None = Depends(validate_request_size)
) -> Any:
    """
    Update a saved search owned by the current user.
    
    Audit: No updated_by for saved_searches per schema.
    """
    # Get existing search to check ownership
    existing_saved_search = saved_search_crud.get(db=db, search_id=search_id)
    
    if not existing_saved_search:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Saved search not found"
        )

    # Check authorization
    if existing_saved_search.user_id != current_user.user_id and not user_crud.is_admin(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to update this saved search"
        )

    # Update with audit tracking
    updated_saved_search = saved_search_crud.update(
        db=db,
        db_obj=existing_saved_search,
        obj_in=saved_search_in
    )

    logger.info(
        "Saved search updated", 
        extra={
            "search_id": updated_saved_search.search_id,
            "user_id": current_user.user_id,
            "search_name": getattr(updated_saved_search, 'name', None)
        }
    )
    
    return updated_saved_search


@router.delete("/{search_id}", response_model=SavedSearchResponse)
def delete_saved_search(
    *,
    db: Session = Depends(get_db),
    search_id: int,
    current_user: UserResponse = Depends(get_current_active_user)
) -> Any:
    """
    Soft delete a saved search owned by the current user.
    
    Sets deleted_at timestamp, preserves data for audit trail.
    Audit: Tracks who deleted via deleted_by (Supabase UUID).
    """
    # Get the object first to check ownership
    saved_search_to_delete = saved_search_crud.get(db=db, search_id=search_id)
    
    if not saved_search_to_delete:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Saved search not found"
        )

    # Check authorization
    if saved_search_to_delete.user_id != current_user.user_id and not user_crud.is_admin(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to delete this saved search"
        )

    # Soft delete with audit trail
    deleted_saved_search = saved_search_crud.soft_delete(
        db=db, 
        search_id=search_id,
        deleted_by_supabase_id=current_user.supabase_id  # UUID audit trail
    )

    if not deleted_saved_search:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Saved search not found during delete attempt"
        )

    logger.warning(
            "Saved search soft deleted",
            extra={
                "search_id": search_id,
                "user_id": deleted_saved_search.user_id,
                "deleted_by": current_user.supabase_id
            }
        )

    return deleted_saved_search


@router.post("/{search_id}/execute", response_model=List[dict])
def execute_saved_search(
    *,
    db: Session = Depends(get_db),
    search_id: int,
    current_user: UserResponse = Depends(get_current_user),
    skip: int = 0,
    limit: int = Query(100, le=1000)
) -> Any:
    """
    Execute a saved search and return matching properties.
    
    Applies the stored JSONB search criteria to current property data.
    Users can only execute their own searches (unless admin).
    Max limit: 1000 results per execution.
    """
    saved_search = saved_search_crud.get(db=db, search_id=search_id)
    
    if not saved_search:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Saved search not found"
        )

    # Check authorization
    if saved_search.user_id != current_user.user_id and not user_crud.is_admin(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to execute this saved search"
        )

    # Execute search with JSONB criteria
    # CRUD layer parses search_criteria JSONB and applies filters
    results = saved_search_crud.execute_search(
        db=db,
        saved_search=saved_search,
        skip=skip,
        limit=limit
    )
    
    return results
