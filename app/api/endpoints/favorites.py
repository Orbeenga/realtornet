# app/api/endpoints/favorites.py
"""
Favorites management endpoints - Canonical compliant
Handles user property favorites with composite key, soft delete, and audit tracking
"""
from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

# --- DIRECT CRUD IMPORTS ---
from app.crud.favorites import favorite as favorite_crud
from app.crud.properties import property as property_crud
from app.crud.users import user as user_crud

# --- DIRECT DEPENDENCY IMPORTS ---
from app.api.dependencies import (
    get_db,
    get_current_user,
    get_current_active_user,
    validate_request_size
)

# --- DIRECT SCHEMA IMPORTS (using aliases from schema file) ---
from app.schemas.users import UserResponse as UserResponse
from app.schemas.favorites import FavoriteResponse, FavoriteCreate

router = APIRouter()


@router.post("/", response_model=FavoriteResponse, status_code=status.HTTP_201_CREATED)
def create_favorite(
    favorite_in: FavoriteCreate,
    current_user: UserResponse = Depends(get_current_active_user),
    db: Session = Depends(get_db),
    _: None = Depends(validate_request_size)
):
    """
    Create a new favorite for the authenticated user and a property.
    
    - Prevents duplicate favorites
    - Automatically sets is_active to True
    - Enforces user authentication and ownership
    
    Audit: Tracks creator via user_id FK (no created_by column per DB schema)
    """
    # Check if FavoriteResponse already exists (including soft-deleted)
    existing_favorite = favorite_crud.get(
        db, 
        user_id=current_user.user_id,
        property_id=favorite_in.property_id
    )
    
    if existing_favorite:
        if existing_favorite.deleted_at is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Favorite already exists for this property."
            )
        else:
            # Soft-deleted FavoriteResponse exists - suggest restore instead
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Favorite was previously removed. Use the restore endpoint to reactivate."
            )
    
    # Verify property exists
    property = property_crud.get(db, property_id=favorite_in.property_id)
    if not property:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Property not found"
        )
    
    # Create (favorites table has no created_by column per DB schema)
    return favorite_crud.create(db, obj_in=favorite_in, user_id=current_user.user_id)


@router.delete("/", response_model=FavoriteResponse)
def delete_favorite(
    property_id: int,
    current_user: UserResponse = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Soft delete a favorite for the authenticated user and property.
    
    - Marks the FavoriteResponse as inactive
    - Sets deleted_at timestamp
    - Uses authenticated user context for ownership
    
    Audit: Tracks who deleted via deleted_by (Supabase UUID)
    """
    # Soft delete with audit trail
    deleted_favorite = favorite_crud.soft_delete(
        db, 
        user_id=current_user.user_id,
        property_id=property_id,
        deleted_by_supabase_id=current_user.supabase_id  # UUID audit trail
    )
    
    if not deleted_favorite:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Favorite not found"
        )
    
    return deleted_favorite


@router.get("/user/{user_id}", response_model=List[FavoriteResponse])
def get_user_favorites(
    user_id: int,
    skip: int = 0,
    limit: int = 100,
    current_user: UserResponse = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Retrieve active favorites for a specific user.
    
    - Supports pagination
    - Returns only active favorites (deleted_at IS NULL)
    - Users can only access their own favorites
    - Admins can access any user's favorites
    """
    # Ensure user can only access their own favorites (unless admin)
    if user_id != current_user.user_id and not user_crud.is_admin(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot access another user's favorites"
        )

    return favorite_crud.get_user_favorites(
        db, 
        user_id=user_id, 
        skip=skip, 
        limit=limit
    )


@router.post("/restore", response_model=FavoriteResponse)
def restore_favorite(
    property_id: int,
    current_user: UserResponse = Depends(get_current_active_user),
    db: Session = Depends(get_db),
    _: None = Depends(validate_request_size)
):
    """
    Restore a previously soft-deleted favorite for the authenticated user.
    
    - Reactivates the FavoriteResponse
    - Clears deleted_at timestamp
    - Uses authenticated user context for ownership
    
    Note: Favorites table has no updated_by column per DB schema
    """
    # Restore (favorites table has no updated_by per DB schema)
    restored_favorite = favorite_crud.restore_favorite(
        db, 
        user_id=current_user.user_id,
        property_id=property_id
    )
    
    if not restored_favorite:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No removed favorite found to restore for this property."
        )
    
    return restored_favorite


@router.get("/is-favorited")
def check_is_favorited(
    property_id: int,
    current_user: UserResponse = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> dict:
    """
    Check if a property is currently favorited by the authenticated user.
    
    - Returns object with FavoriteResponse status for future extensibility.
    - Only checks active (non-deleted) favorites
    - Uses authenticated user context
    """
    is_favorited = favorite_crud.is_favorited(
        db, 
        user_id=current_user.user_id,
        property_id=property_id
    )
    
    return {"is_favorited": is_favorited}


@router.get("/count/{property_id}")
def count_property_favorites(
    property_id: int,
    db: Session = Depends(get_db)
) -> dict:
    """
    Count the number of active favorites for a property.
    
    - Returns total active (non-deleted) favorites
    - Public endpoint (no authentication required)
    - Useful for displaying property popularity
    
    Note: Consider rate limiting for public endpoints.
    """
    # Verify property exists
    property = property_crud.get(db, property_id=property_id)
    if not property:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Property not found"
        )
    
    count = favorite_crud.count_active_favorites(db, property_id=property_id)
    return {"property_id": property_id, "favorite_count": count}


@router.get("/count/user/{user_id}")
def count_user_favorites(
    user_id: int,
    current_user: UserResponse = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> dict:
    """
    Count the number of active favorites for a user.
    
    - Users can only check their own favorite count
    - Admins can check any user's favorite count
    """
    # Ensure user can only access their own favorites (unless admin)
    if user_id != current_user.user_id and not user_crud.is_admin(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot access another user's favorite count"
        )

    count = favorite_crud.count_user_favorites(db, user_id=user_id)
    return {"user_id": user_id, "favorite_count": count}


@router.delete("/bulk", status_code=200)
def bulk_delete_favorites(
    property_ids: List[int] = Query(..., description="List of property IDs to remove from favorites"),
    current_user: UserResponse = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> dict:
    """
    Bulk soft-delete multiple favorites.
    - Users can only delete their own favorites
    - Single atomic SQL UPDATE (not a loop)
    - Returns count of successfully deleted favorites
    """
    deleted_count = favorite_crud.bulk_soft_delete(
        db,
        user_id=current_user.user_id,
        property_ids=property_ids,
        deleted_by_supabase_id=current_user.supabase_id
    )
    return {
        "status": "success",
        "deleted_count": deleted_count,
        "total_requested": len(property_ids)
    }
