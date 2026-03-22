# app/api/endpoints/admin.py
"""
Admin management endpoints - Canonical compliant
Handles system-wide operations with proper soft delete, audit tracking, and RLS enforcement
"""
import logging
from typing import Any, Dict, List
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session

from app.api.dependencies import (
    get_db,
    get_current_admin_user,
    validate_request_size
)
from app.models.users import User as User

# --- DIRECT CRUD IMPORTS ---
# We point directly to the files to avoid __init__.py circular/missing reference issues
from app.crud.users import user as user_crud
from app.crud.properties import property as property_crud
from app.crud.inquiries import inquiry as inquiry_crud
from app.services.analytics_services import analytics_service 

# --- DIRECT SCHEMA IMPORTS ---
# from app.schemas.users import UserResponse, UserCreate, UserUpdate
from app.schemas.users import UserResponse, UserCreate, UserUpdate
from app.schemas.properties import PropertyResponse, PropertyUpdate
from app.schemas.inquiries import InquiryResponse
from app.schemas.stats import SystemStatsResponse as SystemStats

# Set up logging
logger = logging.getLogger(__name__)

router = APIRouter()


# USER MANAGEMENT ENDPOINTS

@router.get("/users", response_model=Dict[str, Any])
def get_users(
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
    current_user: UserResponse = Depends(get_current_admin_user)
) -> Any:
    """
    Retrieve users with pagination (admin only).
    
    Returns only non-deleted users (deleted_at IS NULL).
    CRUD layer enforces soft delete filtering.
    """
    users = user_crud.get_multi(db, skip=skip, limit=limit)
    total = user_crud.count_active(db)  # Use CRUD method that filters deleted_at
    
    return {
        "items": jsonable_encoder(users),
        "total": total,
        "page": skip // limit + 1 if limit else 1,
        "pages": (total + limit - 1) // limit if limit else 1
    }


@router.post("/users", response_model=UserResponse)
def create_user(
    *,
    db: Session = Depends(get_db),
    user_in: UserCreate,
    current_user: UserResponse = Depends(get_current_admin_user),
    _: None = Depends(validate_request_size)
) -> Any:
    """
    Create new user as admin.
    
    Validates email uniqueness (including soft-deleted users).
    """
    # Check if user with email already exists (including soft-deleted)
    db_user = user_crud.get_by_email(db, email=user_in.email)
    
    if db_user:
        if db_user.deleted_at is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User with this email was previously deleted. Contact support to restore.",
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email already exists in the system",
        )
    
    import uuid
    supabase_id = str(uuid.uuid4())
    db_user = user_crud.create(
        db,
        obj_in=user_in,
        supabase_id=supabase_id,
        created_by=current_user.supabase_id
    )
    logger.info(f"User created: {db_user.user_id} by admin {current_user.user_id}")
    
    return db_user


@router.get("/users/{user_id}", response_model=UserResponse)
def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: UserResponse = Depends(get_current_admin_user)
) -> Any:
    """
    Get user by ID (admin only).
    
    Returns 404 if user not found or soft-deleted.
    """
    db_user = user_crud.get(db, user_id=user_id)
    
    # FIX: user_crud.get uses PK lookup and may include soft-deleted users; enforce visibility guard here.
    if not db_user or db_user.deleted_at is not None:
        logger.warning(f"Failed user lookup: UserResponse {user_id} not found")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return db_user


@router.put("/users/{user_id}", response_model=UserResponse)
def update_user(
    *,
    db: Session = Depends(get_db),
    user_id: int,
    user_in: UserUpdate,
    current_user: UserResponse = Depends(get_current_admin_user),
    _: None = Depends(validate_request_size)
) -> Any:
    """
    Update user (admin only).
    
    Tracks admin who made the update via updated_by (Supabase UUID).
    updated_at handled automatically by DB trigger.
    """
    db_user = user_crud.get(db, user_id=user_id)
    
    # FIX: Block updates on soft-deleted users.
    if not db_user or db_user.deleted_at is not None:
        logger.warning(f"Failed user update: UserResponse {user_id} not found")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Update with audit tracking
    db_user = user_crud.update(
        db, 
        db_obj=db_user, 
        obj_in=user_in,
        updated_by=current_user.supabase_id  # UUID audit trail
    )
    
    logger.info(f"User updated: {user_id} by admin {current_user.user_id}")
    return db_user


@router.delete("/users/{user_id}", response_model=UserResponse)
def delete_user(
    *,
    db: Session = Depends(get_db),
    user_id: int,
    current_user: UserResponse = Depends(get_current_admin_user)
) -> Any:
    """
    Soft delete user (admin only).
    
    Sets deleted_at timestamp and tracks who deleted via deleted_by.
    User data preserved for audit trail, FK relationships intact.
    """
    db_user = user_crud.get(db, user_id=user_id)
    
    # FIX: Treat already soft-deleted users as not found for admin delete endpoint.
    if not db_user or db_user.deleted_at is not None:
        logger.warning(f"Failed user deletion: UserResponse {user_id} not found")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Prevent admin from deleting themselves
    if db_user.user_id == current_user.user_id:
        logger.warning(f"Self-deletion attempt by admin {current_user.user_id}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Admins cannot delete themselves"
        )
    
    # Soft delete with audit trail
    db_user = user_crud.soft_delete(
        db, 
        user_id=user_id,
        deleted_by_supabase_id=current_user.supabase_id
    )
    
    logger.info(f"User soft-deleted: {user_id} by admin {current_user.user_id}")
    return db_user


# Activate_user function signature
@router.post("/users/{user_id}/activate", response_model=UserResponse)
def activate_user(
    *,
    db: Session = Depends(get_db),
    user_id: int,
    current_user: UserResponse = Depends(get_current_admin_user),
    _: None = Depends(validate_request_size)
) -> Any:
    """
    Restore a soft-deleted user (admin only).

    Clears deleted_at to restore access. deleted_by audit record is preserved.
    Tracks who restored via updated_by.
    """
    # FIX: `activate()` is the restore path and must work for soft-deleted users.
    db_user = user_crud.activate(
        db,
        user_id=user_id,
        updated_by=current_user.supabase_id
    )

    if not db_user:
        logger.warning(f"Failed user activation: UserResponse {user_id} not found")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    logger.info(f"User activated: {user_id} by admin {current_user.user_id}")
    return db_user


# Deactivate_user function signature
@router.post("/users/{user_id}/deactivate", response_model=UserResponse)
def deactivate_user(
    *,
    db: Session = Depends(get_db),
    user_id: int,
    current_user: UserResponse = Depends(get_current_admin_user),
    _: None = Depends(validate_request_size)
) -> Any:
    """
    Soft delete a user (admin only).

    Sets deleted_at to revoke access. Use DELETE /users/{user_id} for the
    standard soft delete path. This endpoint exists for explicit admin
    deactivation with the same audit trail.
    Tracks who deactivated via updated_by (written to deleted_by as well).
    """
    db_user = user_crud.get(db, user_id=user_id)
    
    # FIX: Block deactivation flow for soft-deleted users.
    if not db_user or db_user.deleted_at is not None:
        logger.warning(f"Failed user deactivation: UserResponse {user_id} not found")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    
    # Prevent admin from deactivating themselves
    if db_user.user_id == current_user.user_id:
        logger.warning(f"Self-deactivation attempt by admin {current_user.user_id}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Admins cannot deactivate themselves",
        )
    
    # Use CRUD method with audit tracking
    db_user = user_crud.deactivate(
        db, 
        user_id=user_id,
        updated_by=current_user.supabase_id
    )
    
    logger.info(f"User deactivated: {user_id} by admin {current_user.user_id}")
    return db_user



# PROPERTY MANAGEMENT ENDPOINTS

@router.get("/properties", response_model=Dict[str, Any])
def get_properties(
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
    current_user: UserResponse = Depends(get_current_admin_user)
) -> Any:
    """
    Retrieve properties with pagination (admin only).
    
    Returns only non-deleted properties (deleted_at IS NULL).
    CRUD layer enforces soft delete filtering.
    """
    properties = property_crud.get_multi(db, skip=skip, limit=limit)
    total = property_crud.count_active(db)  # Use CRUD method that filters deleted_at
    
    return {
        "items": jsonable_encoder(properties),
        "total": total,
        "page": skip // limit + 1 if limit else 1,
        "pages": (total + limit - 1) // limit if limit else 1
    }


@router.delete("/properties/{property_id}", response_model=PropertyResponse)
def delete_property(
    *,
    db: Session = Depends(get_db),
    property_id: int,
    current_user: UserResponse = Depends(get_current_admin_user)
) -> Any:
    """
    Soft delete property (admin only).
    
    Sets deleted_at timestamp and tracks who deleted via deleted_by.
    Property data preserved for audit trail, FK relationships intact.
    """
    prop = property_crud.get(db, property_id=property_id)
    
    if not prop:
        logger.warning(f"Failed property deletion: PropertyResponse {property_id} not found")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Property not found"
        )
    
    # Soft delete with audit trail
    prop = property_crud.soft_delete(
        db, 
        property_id=property_id,
        deleted_by_supabase_id=current_user.supabase_id
    )
    
    logger.info(f"Property soft-deleted: {property_id} by admin {current_user.user_id}")
    return prop


# Verify_property function signature
@router.post("/properties/{property_id}/verify", response_model=PropertyResponse)
def verify_property(
    *,
    db: Session = Depends(get_db),
    property_id: int,
    current_user: UserResponse = Depends(get_current_admin_user),
    _: None = Depends(validate_request_size)
) -> Any:
    """
    Mark a property as verified.
    
    Tracks who verified via updated_by.
    """
    prop = property_crud.get(db, property_id=property_id)
    
    # FIX: Guard not-found/deleted path (property_crud.get already excludes deleted by default).
    if not prop:
        logger.warning(f"Failed property verification: PropertyResponse {property_id} not found")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Property not found",
        )

    # FIX: Idempotent endpoint behavior for already-verified properties.
    if prop.is_verified:
        return prop

    # Use CRUD method with audit tracking
    prop = property_crud.verify_property(
        db,
        property_id=property_id,
        updated_by=current_user.supabase_id
    )
    
    logger.info(f"Property verified: {property_id} by admin {current_user.user_id}")
    return prop


@router.put("/properties/{property_id}/approve", response_model=PropertyResponse)
def approve_property(
    *,
    db: Session = Depends(get_db),
    property_id: int,
    current_user: UserResponse = Depends(get_current_admin_user),
    _: None = Depends(validate_request_size)
) -> Any:
    """
    Approve a property listing (admin only).
    
    Sets is_approved = true and tracks who approved.
    """
    prop = property_crud.get(db, property_id=property_id)
    
    # FIX: Guard not-found/deleted path (property_crud.get already excludes deleted by default).
    if not prop:
        logger.warning(f"Failed property approval: PropertyResponse {property_id} not found")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Property not found"
        )

    # FIX: Idempotent endpoint behavior for already-active listings.
    if getattr(prop.listing_status, "value", prop.listing_status) == "active":
        return prop

    # FIX: Align approve semantics with verification workflow before activation.
    if not prop.is_verified:
        property_crud.verify_property(
            db,
            property_id=property_id,
            updated_by=current_user.supabase_id
        )

    # Update with audit tracking
    prop_update = PropertyUpdate(listing_status="active")
    updated_prop = property_crud.update(
        db, 
        db_obj=prop, 
        obj_in=prop_update,
        updated_by=current_user.supabase_id
    )
    
    logger.info(f"Property approved: {property_id} by admin {current_user.user_id}")
    return updated_prop



# INQUIRY MANAGEMENT ENDPOINTS

@router.get("/inquiries", response_model=Dict[str, Any])
def read_all_inquiries(
    db: Session = Depends(get_db),
    current_user: UserResponse = Depends(get_current_admin_user),
    skip: int = 0,
    limit: int = 100,
) -> Any:
    """
    Retrieve all inquiries with pagination (admin only).
    
    Returns only non-deleted inquiries (deleted_at IS NULL).
    CRUD layer enforces soft delete filtering.
    """
    inquiries = inquiry_crud.get_multi(db, skip=skip, limit=limit)
    total = inquiry_crud.count_active(db)  # Use CRUD method that filters deleted_at
    
    return {
        "items": jsonable_encoder(inquiries),
        "total": total,
        "page": skip // limit + 1 if limit else 1,
        "pages": (total + limit - 1) // limit if limit else 1
    }



# STATISTICS ENDPOINTS

@router.get("/stats", response_model=SystemStats)
def get_system_stats(
    db: Session = Depends(get_db),
    current_user: UserResponse = Depends(get_current_admin_user)
) -> Any:
    """Get comprehensive system statistics."""
    # ✅ Use existing analytics service (not non-existent crud)
    stats = analytics_service.get_system_stats(db)
    return stats


@router.get("/stats/overview")
def get_stats_overview(
    db: Session = Depends(get_db),
    current_user: UserResponse = Depends(get_current_admin_user)
) -> Any:
    """
    Get quick system overview statistics (admin only).
    
    All counts exclude soft-deleted records.
    Uses CRUD layer methods that enforce deleted_at IS NULL filtering.
    """
    try:
        # Use CRUD methods that respect soft delete
        total_users = user_crud.count_active(db)
        total_properties = property_crud.count_active(db)
        
        # Get approved/pending counts (also filtering deleted_at)
        approved_properties = property_crud.count_approved(db)
        pending_properties = property_crud.count_pending(db)
        
        return {
            "total_users": total_users,
            "total_properties": total_properties,
            "approved_properties": approved_properties,
            "pending_properties": pending_properties
        }
    except Exception as e:
        logger.error(f"Error generating stats overview")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to generate statistics. Please try again later."
        )
