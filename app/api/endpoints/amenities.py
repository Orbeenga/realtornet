# app/api/endpoints/amenities.py
"""
Amenities management endpoints - Canonical compliant
Handles amenity lookup data with admin-only mutations and hard delete
"""
from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

# --- DIRECT CRUD IMPORTS ---
from app.crud.amenities import amenity as amenity_crud
from app.crud.property_amenities import property_amenity as property_amenity_crud
from app.crud.users import user as user_crud

# --- DIRECT DEPENDENCY IMPORTS ---
from app.api.dependencies import (
    get_db,
    get_current_admin_user,
    validate_request_size
)

# --- DIRECT SCHEMA IMPORTS (using aliases from schema file) ---
from app.schemas.users import User
from app.schemas.amenities import Amenity, AmenityCreate, AmenityUpdate

router = APIRouter()


@router.get("/", response_model=List[Amenity])
def read_amenities(
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
    category: str = None,
) -> Any:
    """
    Retrieve amenities with optional category filtering.
    
    Public endpoint - returns all amenities.
    Used for populating amenity selection in property forms.
    """
    if category:
        amenities = amenity_crud.get_by_category(db, category=category, skip=skip, limit=limit)
    else:
        amenities = amenity_crud.get_multi(db, skip=skip, limit=limit)
    
    return amenities


@router.get("/categories", response_model=List[str])
def read_amenity_categories(
    db: Session = Depends(get_db),
) -> Any:
    """
    Get all unique amenity categories.
    
    Public endpoint for populating category filters.
    Returns all distinct categories from amenities.
    """
    categories = amenity_crud.get_categories(db)
    return categories


@router.get("/{amenity_id}", response_model=Amenity)
def read_amenity(
    *,
    db: Session = Depends(get_db),
    amenity_id: int,
) -> Any:
    """
    Get amenity by ID.
    
    Public endpoint - anyone can view amenities.
    """
    amenity = amenity_crud.get(db, amenity_id=amenity_id)
    
    if not amenity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Amenity not found"
        )
    
    return amenity


@router.post("/", response_model=Amenity, status_code=status.HTTP_201_CREATED)
def create_amenity(
    *,
    db: Session = Depends(get_db),
    amenity_in: AmenityCreate,
    current_user: User = Depends(get_current_admin_user),
    _: None = Depends(validate_request_size)
) -> Any:
    """
    Create new amenity. Admin only.
    
    Validates name uniqueness before creation.
    No audit tracking - amenities table has no created_by/updated_by columns.
    """
    # Check if amenity with same name exists
    existing_amenity = amenity_crud.get_by_name(db, name=amenity_in.name)
    
    if existing_amenity:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Amenity with this name already exists"
        )
    
    # Create amenity (no audit tracking per DB schema)
    amenity = amenity_crud.create(db, obj_in=amenity_in)
    
    return amenity


@router.put("/{amenity_id}", response_model=Amenity)
def update_amenity(
    *,
    db: Session = Depends(get_db),
    amenity_id: int,
    amenity_in: AmenityUpdate,
    current_user: User = Depends(get_current_admin_user),
    _: None = Depends(validate_request_size)
) -> Any:
    """
    Update an amenity. Admin only.
    
    Validates name uniqueness if name is being changed.
    No audit tracking - amenities table has no updated_by column.
    """
    amenity = amenity_crud.get(db, amenity_id=amenity_id)
    
    if not amenity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Amenity not found"
        )
    
    # If name is being changed, check uniqueness
    if amenity_in.name and amenity_in.name != amenity.name:
        existing_amenity = amenity_crud.get_by_name(db, name=amenity_in.name)
        if existing_amenity:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Amenity with this name already exists"
            )
    
    # Update amenity (no audit tracking per DB schema)
    amenity = amenity_crud.update(db, db_obj=amenity, obj_in=amenity_in)
    
    return amenity


@router.delete("/{amenity_id}")
def delete_amenity(
    *,
    db: Session = Depends(get_db),
    amenity_id: int,
    current_user: User = Depends(get_current_admin_user)
) -> Any:
    """
    Hard delete an amenity. Admin only.
    
    Permanently removes the amenity from the database.
    Properties using this amenity will lose the association (FK cascade).
    
    Note: Amenities table has no deleted_at column - uses hard delete.
    Optional usage protection prevents deletion of amenities in use.
    """
    amenity = amenity_crud.get(db, amenity_id=amenity_id)
    
    if not amenity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Amenity not found"
        )
    
    # Optional: Check if amenity is in use by active properties
    # Prevent deletion of amenities in use
    usage_count = property_amenity_crud.count_by_amenity(db, amenity_id=amenity_id)
    if usage_count > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot delete amenity that is used by {usage_count} properties"
        )
    
    # Hard delete
    amenity_crud.remove(db, amenity_id=amenity_id)
    
    return {"message": "Amenity deleted successfully"}


@router.get("/stats/popular")
def get_popular_amenities(
    db: Session = Depends(get_db),
    limit: int = 10,
) -> Any:
    """
    Get most popular amenities based on usage in active properties.
    
    Public endpoint - useful for highlighting common features.
    Returns amenities sorted by usage count (descending).
    """
    popular = amenity_crud.get_popular(db, limit=limit)
    return popular