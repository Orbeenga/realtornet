# app/api/endpoints/property_images.py
"""
Property images management endpoints - Canonical compliant
Handles property photo uploads with Supabase Storage, ordering, and hard delete
NO AUDIT TRAIL: property_images table has no created_by/updated_by/deleted_by columns
"""
from typing import Any, List, cast as typing_cast  # Alias typing.cast so endpoint-local narrowing never shadows SQLAlchemy helpers in future edits.
from fastapi import APIRouter, Depends, HTTPException, status, File, UploadFile
from sqlalchemy.orm import Session
import logging

# --- DIRECT CRUD IMPORTS ---
from app.crud.property_images import property_image as property_image_crud
from app.crud.properties import property as property_crud
from app.crud.users import user as user_crud
from app.models.users import User  # Narrow endpoint-local user values back to the ORM shape expected by CRUD permission helpers.

# --- DIRECT DEPENDENCY IMPORTS ---
from app.api.dependencies import (
    get_db,
    get_current_active_user,
    validate_request_size
)

# --- DIRECT SCHEMA IMPORTS (using aliases) ---
from app.schemas.users import UserResponse as UserResponse
from app.schemas.property_images import PropertyImageResponse, PropertyImageCreate, PropertyImageUpdate

# --- SERVICES ---
from app.services.storage_services import upload_property_image, delete_property_image

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/property/{property_id}", response_model=List[PropertyImageResponse])
def read_property_images(
    *,
    db: Session = Depends(get_db),
    property_id: int,
) -> Any:
    """
    Retrieve all images for a specific property.
    
    Public endpoint - anyone can view property images.
    Returns images sorted by display_order (ascending).
    """
    # Verify property exists
    property = property_crud.get(db, property_id=property_id)
    if not property:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Property not found"
        )
    
    images = property_image_crud.get_by_property(db, property_id=property_id)
    return images


@router.get("/{image_id}", response_model=PropertyImageResponse)
def read_property_image(
    *,
    db: Session = Depends(get_db),
    image_id: int,
) -> Any:
    """
    Get property image by ID.
    
    Public endpoint - anyone can view property images.
    """
    image = property_image_crud.get(db, image_id=image_id)
    
    if not image:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Property image not found"
        )
    
    return image


@router.post("/property/{property_id}/upload", response_model=PropertyImageResponse, status_code=status.HTTP_201_CREATED)
async def upload_property_image_endpoint(
    *,
    db: Session = Depends(get_db),
    property_id: int,
    file: UploadFile = File(...),
    caption: str | None = None,  # Preserve the optional caption contract while matching the runtime default of None.
    is_primary: bool = False,
    current_user: UserResponse = Depends(get_current_active_user),
    _: None = Depends(validate_request_size)
) -> Any:
    """
    Upload an image for a property.
    
    Permissions:
    - Property owner can upload images to their property
    - Admin can upload images to any property
    
    File validation:
    - Max size: 10MB
    - Allowed types: image/jpeg, image/png, image/webp
    
    Uploads to Supabase Storage and creates DB record.
    No audit trail (property_images table has no created_by column).
    """
    # Verify property exists
    property = property_crud.get(db, property_id=property_id)
    if not property:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Property not found"
        )
    
    # Check ownership: PropertyResponse owner or admin
    property_owner_id: int = typing_cast(int, property.user_id)  # Narrow ORM-owned property user IDs before the permission comparison.
    current_user_id: int = typing_cast(int, current_user.user_id)  # Narrow the authenticated user ID locally without changing the dependency contract.
    current_user_model: User = typing_cast(User, current_user)  # typing cast: endpoint local only for CRUD permission helper compatibility.
    if property_owner_id != current_user_id and not user_crud.is_admin(current_user_model):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to upload images for this property"
        )
    
    # Validate file type
    allowed_types = {"image/jpeg", "image/png", "image/webp"}
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File type not allowed. Supported types: {', '.join(allowed_types)}"
        )
    
    try:
        # Read file contents
        contents = await file.read()
        
        # Validate file size (10MB limit)
        max_size = 10 * 1024 * 1024
        if len(contents) > max_size:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File too large (max {max_size / 1024 / 1024}MB)"
            )
        
        # Upload to Supabase Storage
        upload_filename: str = typing_cast(str, file.filename)  # Narrow the uploaded filename locally before passing it to the storage helper.
        image_url = await upload_property_image(property_id, contents, upload_filename)
        
        # If this is set as primary, unset other primary images
        if is_primary:
            property_image_crud.unset_primary(db, property_id=property_id)
        
        # Get next display order
        next_order = property_image_crud.get_next_order(db, property_id=property_id)
        
        # Create DB record (no audit tracking per DB schema)
        image_in = PropertyImageCreate(
            property_id=property_id,
            image_url=image_url,
            caption=caption,
            is_primary=is_primary,
            display_order=next_order
        )
        
        image = property_image_crud.create(db, obj_in=image_in)
        
        logger.info(
            "Property image uploaded",
            extra={
                "image_id": image.image_id,
                "property_id": property_id,
                "is_primary": is_primary,
                "uploaded_by_user": current_user.user_id,
                "image_filename": file.filename  # ← renamed
            }
        )
        
        return image
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to upload property image",
            extra={
                "property_id": property_id,
                "image_filename": file.filename,  # ← Avoid collision
                "user_id": current_user.user_id,
                "error_type": type(e).__name__
            },
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to upload image. Please try again."
        )


@router.put("/{image_id}", response_model=PropertyImageResponse)
def update_property_image(
    *,
    db: Session = Depends(get_db),
    image_id: int,
    image_in: PropertyImageUpdate,
    current_user: UserResponse = Depends(get_current_active_user),
    _: None = Depends(validate_request_size)
) -> Any:
    """
    Update property image metadata (caption, is_primary, display_order).
    
    Permissions: PropertyResponse owner or admin.
    Does not change the actual image file - use delete + upload for that.
    No audit trail (property_images table has no updated_by column).
    """
    image = property_image_crud.get(db, image_id=image_id)
    
    if not image:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Property image not found"
        )
    
    # Check ownership
    property_id_value: int = typing_cast(int, image.property_id)  # Narrow the ORM-backed property ID before loading the owning property.
    property = property_crud.get(db, property_id=property_id_value)
    if property is None:  # Narrow the loaded property before accessing owner fields.
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Property not found"
        )
    property_owner_id: int = typing_cast(int, property.user_id)  # Narrow ORM-owned property user IDs before the permission comparison.
    current_user_id: int = typing_cast(int, current_user.user_id)  # Narrow the authenticated user ID locally without changing the dependency contract.
    current_user_model: User = typing_cast(User, current_user)  # typing cast: endpoint local only for CRUD permission helper compatibility.
    if property_owner_id != current_user_id and not user_crud.is_admin(current_user_model):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to update this image"
        )
    
    # If setting as primary, unset other primary images
    image_is_primary: bool = typing_cast(bool, image.is_primary)  # Narrow the ORM-backed primary flag before boolean checks.
    if image_in.is_primary and not image_is_primary:
        property_image_crud.unset_primary(db, property_id=property_id_value)
    
    # Update metadata only (no audit trail per DB schema)
    image = property_image_crud.update(db, db_obj=image, obj_in=image_in)
    
    logger.info(
        "Property image metadata updated",
        extra={
            "image_id": image_id,
            "property_id": image.property_id,
            "updated_by_user": current_user.user_id
        }
    )
    
    return image


@router.delete("/{image_id}")
async def delete_property_image_endpoint(
    *,
    db: Session = Depends(get_db),
    image_id: int,
    current_user: UserResponse = Depends(get_current_active_user)
) -> Any:
    """
    Delete a property image.
    
    Hard delete - removes from both Supabase Storage and database.
    Permissions: PropertyResponse owner or admin.
    No soft delete (property_images table has no deleted_at column).
    """
    image = property_image_crud.get(db, image_id=image_id)
    
    if not image:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Property image not found"
        )
    
    # Check ownership
    property_id_value: int = typing_cast(int, image.property_id)  # Narrow the ORM-backed property ID before loading the owning property.
    property = property_crud.get(db, property_id=property_id_value)
    if property is None:  # Narrow the loaded property before accessing owner fields.
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Property not found"
        )
    property_owner_id: int = typing_cast(int, property.user_id)  # Narrow ORM-owned property user IDs before the permission comparison.
    current_user_id: int = typing_cast(int, current_user.user_id)  # Narrow the authenticated user ID locally without changing the dependency contract.
    current_user_model: User = typing_cast(User, current_user)  # typing cast: endpoint local only for CRUD permission helper compatibility.
    if property_owner_id != current_user_id and not user_crud.is_admin(current_user_model):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to delete this image"
        )
    
    try:
        # Delete from Supabase Storage
        image_url_value: str = typing_cast(str, image.image_url)  # Narrow the ORM-backed image URL before passing it to the storage helper.
        await delete_property_image(image_url_value)
        
        # Hard delete from database
        property_image_crud.remove(db, image_id=image_id)
        
        logger.warning(
            "Property image deleted",
            extra={
                "image_id": image_id,
                "property_id": image.property_id,
                "image_url": image.image_url,
                "deleted_by_user": current_user.user_id
            }
        )
        
        return {"message": "Image deleted successfully"}
    
    except Exception as e:
        logger.error(
            "Failed to delete property image",
            extra={
                "image_id": image_id,
                "image_url": image.image_url,
                "property_id": image.property_id,
                "error_type": type(e).__name__
            },
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to delete image. Please try again."
        )


@router.put("/property/{property_id}/reorder", response_model=List[PropertyImageResponse])
def reorder_property_images(
    *,
    db: Session = Depends(get_db),
    property_id: int,
    image_order: List[int],
    current_user: UserResponse = Depends(get_current_active_user),
    _: None = Depends(validate_request_size)
) -> Any:
    """
    Reorder property images.
    
    Accepts list of image_ids in desired display order.
    Updates display_order for all images accordingly.
    
    Permissions: PropertyResponse owner or admin.
    """
    # Verify property exists
    property = property_crud.get(db, property_id=property_id)
    if not property:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Property not found"
        )
    
    # Check ownership
    property_owner_id: int = typing_cast(int, property.user_id)  # Narrow ORM-owned property user IDs before the permission comparison.
    current_user_id: int = typing_cast(int, current_user.user_id)  # Narrow the authenticated user ID locally without changing the dependency contract.
    current_user_model: User = typing_cast(User, current_user)  # typing cast: endpoint local only for CRUD permission helper compatibility.
    if property_owner_id != current_user_id and not user_crud.is_admin(current_user_model):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to reorder images for this property"
        )
    
    # Verify all image IDs belong to this property
    existing_images = property_image_crud.get_by_property(db, property_id=property_id)
    existing_image_ids = {img.image_id for img in existing_images}
    
    for image_id in image_order:
        if image_id not in existing_image_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Image {image_id} does not belong to this property"
            )
    
    # Reorder images
    property_image_crud.reorder(db, property_id=property_id, image_order=image_order)
    
    logger.info(
        "Property images reordered",
        extra={
            "property_id": property_id,
            "new_order": image_order,
            "reordered_by_user": current_user.user_id
        }
    )
    
    # Return updated list
    images = property_image_crud.get_by_property(db, property_id=property_id)
    return images


@router.post("/{image_id}/set-primary", response_model=PropertyImageResponse)
def set_primary_image(
    *,
    db: Session = Depends(get_db),
    image_id: int,
    current_user: UserResponse = Depends(get_current_active_user)
) -> Any:
    """
    Set an image as the primary image for its property.
    
    Automatically unsets other primary images for the same property.
    Permissions: PropertyResponse owner or admin.
    """
    image = property_image_crud.get(db, image_id=image_id)
    
    if not image:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Property image not found"
        )
    
    # Check ownership
    property_id_value: int = typing_cast(int, image.property_id)  # Narrow the ORM-backed property ID before loading the owning property.
    property = property_crud.get(db, property_id=property_id_value)
    if property is None:  # Narrow the loaded property before accessing owner fields.
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Property not found"
        )
    property_owner_id: int = typing_cast(int, property.user_id)  # Narrow ORM-owned property user IDs before the permission comparison.
    current_user_id: int = typing_cast(int, current_user.user_id)  # Narrow the authenticated user ID locally without changing the dependency contract.
    current_user_model: User = typing_cast(User, current_user)  # typing cast: endpoint local only for CRUD permission helper compatibility.
    if property_owner_id != current_user_id and not user_crud.is_admin(current_user_model):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to modify this image"
        )
    
    # Unset other primary images
    property_image_crud.unset_primary(db, property_id=property_id_value)
    
    # Set this image as primary
    image_update = PropertyImageUpdate(is_primary=True)
    image = property_image_crud.update(db, db_obj=image, obj_in=image_update)
    
    logger.info(
        "Primary image set",
        extra={
            "image_id": image_id,
            "property_id": image.property_id,
            "set_by_user": current_user.user_id
        }
    )
    
    return image
