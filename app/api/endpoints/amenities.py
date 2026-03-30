# app/api/endpoints/amenities.py
"""
Amenities management endpoints - Canonical compliant
Handles AmenityResponse lookup data with admin-only mutations and hard delete
"""
from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

# --- DIRECT CRUD IMPORTS ---
from app.crud.amenities import amenity as amenity_crud
from app.crud.property_amenities import property_amenities as property_amenity_crud
from app.crud.users import user as user_crud

# --- DIRECT DEPENDENCY IMPORTS ---
from app.api.dependencies import (
    get_db,
    get_current_admin_user,
    validate_request_size,
    pagination_params,
)

# --- DIRECT SCHEMA IMPORTS (using aliases from schema file) ---
from app.schemas.users import UserResponse as UserResponse
from app.schemas.amenities import AmenityResponse, AmenityCreate, AmenityUpdate

router = APIRouter()


@router.get("/", response_model=List[AmenityResponse])
def read_amenities(
    db: Session = Depends(get_db),
    pagination: dict = Depends(pagination_params),
    category: str | None = None,  # Treat the category filter as optional so pyright matches the query parameter's default.
) -> Any:
    """
    Retrieve amenities with optional category filtering.
    
    Public endpoint - returns all amenities.
    Used for populating AmenityResponse selection in property forms.
    """
    if category is not None:
        amenities = amenity_crud.get_by_category(db, category=category, **pagination,)
    else:
        amenities = amenity_crud.get_multi(db, **pagination,)
    
    return amenities


@router.get("/categories", response_model=List[str])
def read_amenity_categories(
    db: Session = Depends(get_db),
) -> Any:
    """
    Get all unique AmenityResponse categories.
    
    Public endpoint for populating category filters.
    Returns all distinct categories from amenities.
    """
    categories = amenity_crud.get_categories(db)
    return categories


@router.get("/{amenity_id}", response_model=AmenityResponse)
def read_AmenityResponse(
    *,
    db: Session = Depends(get_db),
    amenity_id: int,
) -> Any:
    """
    Get AmenityResponse by ID.
    
    Public endpoint - anyone can view amenities.
    """
    AmenityResponse = amenity_crud.get(db, amenity_id=amenity_id)
    
    if AmenityResponse is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="AmenityResponse not found"
        )
    
    return AmenityResponse


@router.post("/", response_model=AmenityResponse, status_code=status.HTTP_201_CREATED)
def create_AmenityResponse(
    *,
    db: Session = Depends(get_db),
    amenity_in: AmenityCreate,
    current_user: UserResponse = Depends(get_current_admin_user),
    _: None = Depends(validate_request_size)
) -> Any:
    """
    Create new AmenityResponse. Admin only.
    
    Validates name uniqueness before creation.
    No audit tracking - amenities table has no created_by/updated_by columns.
    """
    # Check if AmenityResponse with same name exists
    existing_AmenityResponse = amenity_crud.get_by_name(db, name=amenity_in.name)
    
    if existing_AmenityResponse is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="AmenityResponse with this name already exists"
        )
    
    # Create AmenityResponse (no audit tracking per DB schema)
    AmenityResponse = amenity_crud.create(db, obj_in=amenity_in)
    
    return AmenityResponse


@router.put("/{amenity_id}", response_model=AmenityResponse)
def update_AmenityResponse(
    *,
    db: Session = Depends(get_db),
    amenity_id: int,
    amenity_in: AmenityUpdate,
    current_user: UserResponse = Depends(get_current_admin_user),
    _: None = Depends(validate_request_size)
) -> Any:
    """
    Update an AmenityResponse. Admin only.
    
    Validates name uniqueness if name is being changed.
    No audit tracking - amenities table has no updated_by column.
    """
    AmenityResponse = amenity_crud.get(db, amenity_id=amenity_id)
    
    if AmenityResponse is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="AmenityResponse not found"
        )
    
    # If name is being changed, check uniqueness
    if amenity_in.name and amenity_in.name != AmenityResponse.name:
        existing_AmenityResponse = amenity_crud.get_by_name(db, name=amenity_in.name)
        if existing_AmenityResponse is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="AmenityResponse with this name already exists"
            )
    
    # Update AmenityResponse (no audit tracking per DB schema)
    AmenityResponse = amenity_crud.update(db, db_obj=AmenityResponse, obj_in=amenity_in)
    
    return AmenityResponse


@router.delete("/{amenity_id}")
def delete_AmenityResponse(
    *,
    db: Session = Depends(get_db),
    amenity_id: int,
    current_user: UserResponse = Depends(get_current_admin_user)
) -> Any:
    """
    Hard delete an AmenityResponse. Admin only.
    
    Permanently removes the AmenityResponse from the database.
    Properties using this AmenityResponse will lose the association (FK cascade).
    
    Note: Amenities table has no deleted_at column - uses hard delete.
    Optional usage protection prevents deletion of amenities in use.
    """
    AmenityResponse = amenity_crud.get(db, amenity_id=amenity_id)
    
    if AmenityResponse is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="AmenityResponse not found"
        )
    
    # Optional: Check if AmenityResponse is in use by active properties
    # Prevent deletion of amenities in use
    usage_count = property_amenity_crud.count_by_amenity(db, amenity_id=amenity_id)
    if usage_count > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot delete AmenityResponse that is used by {usage_count} properties"
        )
    
    # Hard delete
    amenity_crud.remove(db, amenity_id=amenity_id)
    
    return {"message": "AmenityResponse deleted successfully"}


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
