# app/api/endpoints/users.py
"""
User management endpoints - Canonical compliant
Handles CRUD operations with proper soft delete, audit tracking, and multi-tenant support
FULL AUDIT TRAIL: created_by, updated_by, deleted_by (users table has all 3)
"""
from typing import Any, List, cast
import logging

from fastapi import APIRouter, Body, Depends, HTTPException, status, File, UploadFile
from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session

# --- DIRECT CRUD IMPORTS ---
from app.crud.users import user as user_crud
from app.models.users import User  # Narrow endpoint-local values back to the ORM user shape expected by CRUD helpers without changing the route contract.

# --- DIRECT DEPENDENCY IMPORTS ---
from app.api.dependencies import (
    get_db,
    get_current_admin_user,
    get_current_user,
    get_current_active_user,
    validate_request_size,
    pagination_params,
)

# --- DIRECT SCHEMA IMPORTS (using aliases) ---
from app.schemas.users import UserResponse as UserResponse, UserCreate, UserUpdate

# --- SERVICES ---
from app.services.storage_services import upload_profile_image

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/", response_model=List[UserResponse])
def read_users(
    db: Session = Depends(get_db),
    pagination: dict = Depends(pagination_params),
    current_user: UserResponse = Depends(get_current_admin_user),
) -> Any:
    """
    Retrieve users. Admin only.
    
    Returns only non-deleted users (deleted_at IS NULL).
    """
    users = user_crud.get_multi(db, **pagination,)
    return users


@router.get("/realtors", response_model=List[UserResponse])
def read_realtors(
    db: Session = Depends(get_db),
    pagination: dict = Depends(pagination_params),
) -> Any:
    """
    Retrieve realtors. Public endpoint.
    
    Returns only active, non-deleted realtors.
    """
    realtors = user_crud.get_realtors(db, **pagination,)
    return realtors


@router.get("/{user_id}", response_model=UserResponse)
def read_user_by_id(
    user_id: int,
    current_user: UserResponse = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Any:
    """
    Get a specific user by id.
    
    Users can read their own profile.
    Admins can read any user profile.
    """
    user = user_crud.get(db, user_id=user_id)
    
    if user is None:  # Narrow the optional ORM lookup explicitly before reading fields from the returned user object.
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Allow users to read their own profile
    current_user_id = cast(int, current_user.user_id)  # Narrow the dependency-backed user id to a concrete int before ownership checks.
    target_user_id = cast(int, user.user_id)  # Narrow the ORM-backed user id to a concrete int before equality checks so pyright doesn't interpret it as SQL expression building.
    if target_user_id == current_user_id:
        return user
    
    # Otherwise, require admin privileges
    current_user_model = cast(User, current_user)  # Narrow the dependency-backed user payload to the ORM user shape expected by the CRUD helper.
    if not user_crud.is_admin(current_user_model):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    return user


@router.put("/me", response_model=UserResponse)
def update_user_me(
    *,
    db: Session = Depends(get_db),
    user_in: UserUpdate,
    current_user: UserResponse = Depends(get_current_active_user),
    _: None = Depends(validate_request_size)
) -> Any:
    """
    Update own user profile.
    
    Audit: Tracks updater via updated_by (Supabase UUID)
    """
    # Update with audit tracking
    current_user_model = cast(User, current_user)  # Narrow the dependency-backed user payload to the ORM user shape expected by the CRUD helper.
    updated_by_supabase_id = str(current_user.supabase_id)  # Normalize the dependency-backed UUID to the string audit format expected by CRUD.
    user = user_crud.update(
        db,
        db_obj=current_user_model,
        obj_in=user_in,
        updated_by=updated_by_supabase_id
    )
    
    logger.info(
        "User updated self",
        extra={
            "user_id": current_user.user_id,
            "updated_by": updated_by_supabase_id
        }
    )
    
    return user


@router.put("/{user_id}", response_model=UserResponse)
def update_user(
    *,
    db: Session = Depends(get_db),
    user_id: int,
    user_in: UserUpdate,
    current_user: UserResponse = Depends(get_current_admin_user),
    _: None = Depends(validate_request_size)
) -> Any:
    """
    Update a user. Admin only.
    
    Audit: Tracks admin who made the update via updated_by
    """
    user = user_crud.get(db, user_id=user_id)
    
    if user is None:  # Narrow the optional ORM lookup explicitly before reading fields from the returned user object.
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    
    # Update with audit tracking
    updated_by_supabase_id = str(current_user.supabase_id)  # Normalize the dependency-backed UUID to the string audit format expected by CRUD.
    user = user_crud.update(
        db,
        db_obj=user,
        obj_in=user_in,
        updated_by=updated_by_supabase_id
    )
    
    logger.info(
        "User updated by admin",
        extra={
            "user_id": user.user_id,
            "updated_by": updated_by_supabase_id
        }
    )
    
    return user


@router.delete("/{user_id}", response_model=UserResponse)
def delete_user(
    *,
    db: Session = Depends(get_db),
    user_id: int,
    current_user: UserResponse = Depends(get_current_admin_user),
) -> Any:
    """
    Soft delete a user. Admin only.
    
    Audit: Tracks who deleted via deleted_by (Supabase UUID)
    """
    user = user_crud.get(db, user_id=user_id)
    
    if user is None:  # Narrow the optional ORM lookup explicitly before reading fields from the returned user object.
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    
    # Prevent self-deletion
    current_user_id = cast(int, current_user.user_id)  # Narrow the dependency-backed user id to a concrete int before self-delete checks.
    target_user_id = cast(int, user.user_id)  # Narrow the ORM-backed user id to a concrete int before equality checks so pyright doesn't interpret it as SQL expression building.
    if target_user_id == current_user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your own account"
        )
    
    # Soft delete with audit trail
    deleted_by_supabase_id = str(current_user.supabase_id)  # Normalize the dependency-backed UUID to the string audit format expected by CRUD.
    user = user_crud.soft_delete(
        db,
        user_id=user_id,
        deleted_by_supabase_id=deleted_by_supabase_id
    )

    if user is None:  # Narrow the soft-delete result explicitly before reading fields from the returned user object.
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    
    logger.warning(
        "User soft deleted",
        extra={
            "user_id": user_id,
            "email": user.email,
            "deleted_by": deleted_by_supabase_id
        }
    )
    
    return user


@router.post("/{user_id}/upload-profile-image", response_model=dict)
async def upload_user_profile_image(
    user_id: int,
    file: UploadFile = File(...),
    current_user: UserResponse = Depends(get_current_user),
    db: Session = Depends(get_db),
    _: None = Depends(validate_request_size)
) -> Any:
    """
    Upload a profile image for a user to Supabase Storage.
    
    Permissions:
    - Users can upload their own image
    - Admins can upload for any user
    
    File validation:
    - Max size: 5MB
    - Allowed types: image/jpeg, image/png, image/gif
    
    Audit: Tracks uploader via updated_by
    """
    # Check permissions
    current_user_id = cast(int, current_user.user_id)  # Narrow the dependency-backed user id to a concrete int before permission checks.
    current_user_model = cast(User, current_user)  # Narrow the dependency-backed user payload to the ORM user shape expected by the CRUD helper.
    if current_user_id != user_id and not user_crud.is_admin(current_user_model):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to upload image for this user"
        )
    
    # Ensure user exists and not deleted
    user_obj = user_crud.get(db, user_id=user_id)
    if user_obj is None:  # Narrow the optional ORM lookup explicitly before reading fields from the returned user object.
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Validate file type
    allowed_types = {"image/jpeg", "image/png", "image/gif"}
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File type not allowed. Supported formats: JPEG, PNG, GIF."
        )
    
    try:
        contents = await file.read()
        
        # Validate file size (5MB limit)
        if len(contents) > 5 * 1024 * 1024:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="File too large (max 5MB)"
            )
        
        # Upload to Supabase Storage
        file_name = file.filename if file.filename is not None else "profile-image"  # Narrow the optional uploaded filename to a concrete string before passing it to storage.
        url = await upload_profile_image(user_id, contents, file_name)
        
        # Update user with new profile image URL
        user_update = UserUpdate(profile_image_url=url)
        updated_by_supabase_id = str(current_user.supabase_id)  # Normalize the dependency-backed UUID to the string audit format expected by CRUD.
        user = user_crud.update(
            db,
            db_obj=user_obj,
            obj_in=user_update,
            updated_by=updated_by_supabase_id
        )
        
        logger.info(
            "User profile image uploaded",
            extra={
                "user_id": user.user_id,
                "image_url": url,
                "uploaded_by": updated_by_supabase_id
            }
        )
        
        return {"url": url}
    
    except HTTPException:
        raise
    except Exception:
        logger.error(
            "Profile image upload failed",
            extra={"user_id": user_id},
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to upload image. Please verify the file format (JPEG, PNG, GIF) and size (max 5MB)."
        )
