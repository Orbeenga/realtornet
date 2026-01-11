# app/api/endpoints/profiles.py
"""
Profile management endpoints - Canonical compliant
Handles user profile CRUD and avatar uploads via Supabase Storage
FULL AUDIT TRAIL: created_by, updated_by, deleted_by (profiles table has all 3)
"""
from typing import Any, List
import logging

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session

# --- DIRECT CRUD IMPORTS ---
from app.crud.profiles import profile as profile_crud
from app.crud.users import user as user_crud

# --- DIRECT DEPENDENCY IMPORTS ---
from app.api.dependencies import (
    get_db,
    get_current_user,
    get_current_active_user,
    validate_request_size
)

# --- DIRECT SCHEMA IMPORTS (using aliases) ---
from app.schemas.users import User
from app.schemas.profiles import Profile, ProfileCreate, ProfileUpdate

# --- SERVICES ---
from app.services.storage_services import upload_profile_image

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/me", response_model=Profile)
def read_profile_me(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> Any:
    """
    Get current user's profile.
    
    Returns 404 if profile doesn't exist (should be created on user registration).
    """
    user_profile = profile_crud.get_by_user_id(db=db, user_id=current_user.user_id)
    
    if not user_profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found for current user"
        )
    
    return user_profile


@router.get("/{profile_id}", response_model=Profile)
def read_profile_by_id(
    profile_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """
    Get a specific profile by ID.
    
    Users can read their own profile.
    Admins can read any profile.
    """
    user_profile = profile_crud.get(db=db, profile_id=profile_id)
    
    if not user_profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found"
        )
    
    # Users can read their own profile
    if user_profile.user_id == current_user.user_id:
        return user_profile
    
    # Admins can read any profile
    if user_crud.is_admin(current_user):
        return user_profile
    
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Not enough permissions"
    )


@router.post("/", response_model=Profile, status_code=status.HTTP_201_CREATED)
def create_profile(
    *,
    db: Session = Depends(get_db),
    profile_in: ProfileCreate,
    current_user: User = Depends(get_current_active_user),
    _: None = Depends(validate_request_size)
) -> Any:
    """
    Create a new profile for current user.
    
    Note: Typically profiles are auto-created on user registration.
    This endpoint allows manual creation if needed.
    
    Audit: Tracks creator via created_by (Supabase UUID)
    """
    # Check if profile already exists
    existing_profile = profile_crud.get_by_user_id(db=db, user_id=current_user.user_id)
    
    if existing_profile:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Profile already exists for this user"
        )
    
    # Ensure profile_in.user_id matches current user
    if profile_in.user_id != current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot create profile for another user"
        )
    
    # Create with audit tracking
    user_profile = profile_crud.create(
        db=db,
        obj_in=profile_in,
        created_by=current_user.supabase_id
    )
    
    logger.info(
        "Profile created",
        extra={
            "profile_id": user_profile.profile_id,
            "user_id": user_profile.user_id,
            "created_by": current_user.supabase_id
        }
    )
    
    return user_profile


@router.put("/me", response_model=Profile)
def update_profile_me(
    *,
    db: Session = Depends(get_db),
    profile_in: ProfileUpdate,
    current_user: User = Depends(get_current_active_user),
    _: None = Depends(validate_request_size)
) -> Any:
    """
    Update current user's profile.
    
    Audit: Tracks updater via updated_by (Supabase UUID)
    """
    user_profile = profile_crud.get_by_user_id(db=db, user_id=current_user.user_id)
    
    if not user_profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found for current user"
        )
    
    # Update with audit tracking
    updated_profile = profile_crud.update(
        db=db,
        db_obj=user_profile,
        obj_in=profile_in,
        updated_by=current_user.supabase_id
    )
    
    logger.info(
        "Profile updated",
        extra={
            "profile_id": updated_profile.profile_id,
            "user_id": updated_profile.user_id,
            "updated_by": current_user.supabase_id
        }
    )
    
    return updated_profile


@router.post("/me/avatar", response_model=Profile)
async def upload_avatar(
    *,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    _: None = Depends(validate_request_size)
) -> Any:
    """
    Upload profile avatar for current user to Supabase Storage.
    
    File validation:
    - Max size: 2MB
    - Allowed types: image/jpeg, image/png, image/gif
    
    Audit: Tracks uploader via updated_by
    """
    user_profile = profile_crud.get_by_user_id(db=db, user_id=current_user.user_id)
    
    if not user_profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found for current user"
        )
    
    allowed_types = {"image/jpeg", "image/png", "image/gif"}
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File type not allowed. Supported types: {', '.join(allowed_types)}"
        )
    
    try:
        contents = await file.read()
        max_size = 2 * 1024 * 1024
        if len(contents) > max_size:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File too large (max {max_size / 1024 / 1024}MB)"
            )
        
        avatar_url = await upload_profile_image(
            current_user.user_id,
            contents,
            file.filename
        )
        
        # Update with audit tracking
        profile_update = ProfileUpdate(profile_picture_url=avatar_url)
        updated_profile = profile_crud.update(
            db=db,
            db_obj=user_profile,
            obj_in=profile_update,
            updated_by=current_user.supabase_id
        )
        
        logger.info(
            "Profile avatar uploaded",
            extra={
                "profile_id": updated_profile.profile_id,
                "user_id": updated_profile.user_id,
                "avatar_url": avatar_url,
                "updated_by": current_user.supabase_id
            }
        )
        
        return updated_profile
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Avatar upload failed",
            extra={
                "user_id": current_user.user_id,
                "error": str(e)
            },
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error uploading avatar: {str(e)}"
        )


@router.delete("/me/avatar", response_model=Profile)
def delete_avatar(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> Any:
    """
    Remove avatar from current user's profile.
    
    Audit: Tracks deletion via updated_by
    """
    user_profile = profile_crud.get_by_user_id(db=db, user_id=current_user.user_id)
    
    if not user_profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found for current user"
        )
    
    if not user_profile.profile_picture_url:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No avatar to delete"
        )
    
    # Update with audit tracking
    profile_update = ProfileUpdate(profile_picture_url=None)
    updated_profile = profile_crud.update(
        db=db,
        db_obj=user_profile,
        obj_in=profile_update,
        updated_by=current_user.supabase_id
    )
    
    logger.info(
        "Profile avatar deleted",
        extra={
            "profile_id": updated_profile.profile_id,
            "user_id": updated_profile.user_id,
            "updated_by": current_user.supabase_id
        }
    )
    
    return updated_profile