from app.schemas.users import UserResponse
# app/api/endpoints/inquiries.py
"""
Inquiries management endpoints - Canonical compliant
Handles property inquiries with user-owner relationships, soft delete, and audit tracking
"""
from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

# --- DIRECT CRUD IMPORTS ---
from app.crud.inquiries import inquiry as inquiry_crud
from app.crud.properties import property as property_crud
from app.crud.users import user as user_crud

# --- DIRECT DEPENDENCY IMPORTS ---
from app.api.dependencies import (
    get_db,
    get_current_active_user,
    validate_request_size
)

# --- DIRECT SCHEMA IMPORTS ---
from app.schemas.users import UserResponse
from app.schemas.inquiries import InquiryResponse, InquiryCreate, InquiryUpdate

router = APIRouter()


@router.post("/", response_model=InquiryResponse, status_code=status.HTTP_201_CREATED)
def create_inquiry(
    *,
    db: Session = Depends(get_db),
    inquiry_in: InquiryCreate,
    current_user: UserResponse = Depends(get_current_active_user),
    _: None = Depends(validate_request_size)
) -> Any:
    """
    Create a new property inquiry.
    
    - Validates property exists
    - Associates inquiry with current user
    - Property owner can be notified via background task
    
    Audit: Tracks inquirer via user_id FK
    """
    # Check if property exists
    property = property_crud.get(db=db, property_id=inquiry_in.property_id)
    if not property:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Property not found"
        )
    
    # Create inquiry with user association
    inquiry = inquiry_crud.create(
        db=db,
        obj_in=inquiry_in,
        user_id=current_user.user_id  # Pass user_id explicitly
    )
    
    # Optional: Trigger notification to property owner
    # background_tasks.add_task(notify_property_owner, property.user_id, inquiry)
    
    return inquiry


@router.get("/", response_model=List[InquiryResponse])
def read_user_inquiries(
    db: Session = Depends(get_db),
    current_user: UserResponse = Depends(get_current_active_user),
    skip: int = 0,
    limit: int = 100,
) -> Any:
    """
    Retrieve all inquiries made by the current user.
    
    Returns only non-deleted inquiries (deleted_at IS NULL).
    """
    inquiries = inquiry_crud.get_by_user(
        db=db,
        user_id=current_user.user_id,
        skip=skip,
        limit=limit
    )
    return inquiries


@router.get("/received", response_model=List[InquiryResponse])
def read_received_inquiries(
    db: Session = Depends(get_db),
    current_user: UserResponse = Depends(get_current_active_user),
    skip: int = 0,
    limit: int = 100,
) -> Any:
    """
    Retrieve all inquiries for properties owned by the current user.
    
    - Only agents and admins can access
    - Returns inquiries for all properties where user_id matches
    """
    # Check if user is agent or admin
    if not user_crud.is_agent(current_user) and not user_crud.is_admin(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Agent or admin privileges required"
        )
    
    inquiries = inquiry_crud.get_by_property_owner(
        db=db,
        owner_user_id=current_user.user_id,
        skip=skip,
        limit=limit
    )
    return inquiries


@router.get("/{inquiry_id}", response_model=InquiryResponse)
def read_inquiry(
    *,
    db: Session = Depends(get_db),
    inquiry_id: int,
    current_user: UserResponse = Depends(get_current_active_user),
) -> Any:
    """
    Get inquiry by ID.
    
    - Inquiry creator can view
    - Property owner can view
    - Admins can view
    """
    inquiry = inquiry_crud.get(db=db, inquiry_id=inquiry_id)
    if not inquiry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Inquiry not found"
        )
    
    # Check authorization: inquirer, property owner, or admin
    property = property_crud.get(db=db, property_id=inquiry.property_id)
    if not property:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Associated property not found"
        )

    if (inquiry.user_id != current_user.user_id and 
        property.user_id != current_user.user_id and 
        not user_crud.is_admin(current_user)):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to view this inquiry"
        )
    
    return inquiry


@router.put("/{inquiry_id}", response_model=InquiryResponse)
def update_inquiry(
    *,
    db: Session = Depends(get_db),
    inquiry_id: int,
    inquiry_in: InquiryUpdate,
    current_user: UserResponse = Depends(get_current_active_user),
    _: None = Depends(validate_request_size)
) -> Any:
    """
    Update an inquiry (typically to mark as responded or update message).
    
    - Inquiry creator can update their message
    - Property owner can update response/status
    - Admins can update any field
    
    Audit: updated_at handled by DB trigger
    """
    inquiry = inquiry_crud.get(db=db, inquiry_id=inquiry_id)
    if not inquiry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Inquiry not found"
        )
    
    # Check authorization
    property = property_crud.get(db=db, property_id=inquiry.property_id)
    if not property:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Associated property not found"
        )

    if (inquiry.user_id != current_user.user_id and 
        property.user_id != current_user.user_id and 
        not user_crud.is_admin(current_user)):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to update this inquiry"
        )
    
    # Update with correct method signature
    inquiry = inquiry_crud.update(
        db=db,
        db_obj=inquiry,
        obj_in=inquiry_in 
    )
    return inquiry


@router.delete("/{inquiry_id}", response_model=InquiryResponse)
def delete_inquiry(
    *,
    db: Session = Depends(get_db),
    inquiry_id: int,
    current_user: UserResponse = Depends(get_current_active_user)
) -> Any:
    """
    Soft delete an inquiry.
    
    - Only inquiry creator or admin can delete
    - Sets deleted_at timestamp
    
    Audit: Tracks who deleted via deleted_by (Supabase UUID)
    """
    inquiry = inquiry_crud.get(db=db, inquiry_id=inquiry_id)
    if not inquiry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Inquiry not found"
        )

    # Check authorization: only creator or admin can delete
    if inquiry.user_id != current_user.user_id and not user_crud.is_admin(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to delete this inquiry"
        )
    
    # Soft delete with audit trail
    inquiry = inquiry_crud.soft_delete(
        db=db, 
        inquiry_id=inquiry_id,
        deleted_by_supabase_id=current_user.supabase_id
    )
    
    if not inquiry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Inquiry not found during delete attempt"
        )
    
    return inquiry


@router.get("/by-property/{property_id}", response_model=List[InquiryResponse])
def read_inquiries_by_property(
    *,
    db: Session = Depends(get_db),
    property_id: int,
    current_user: UserResponse = Depends(get_current_active_user),
    skip: int = 0,
    limit: int = 100,
) -> Any:
    """
    Retrieve all inquiries for a specific property.
    
    - Only property owner or admin can view
    - Returns non-deleted inquiries
    """
    # Check if property exists
    property = property_crud.get(db=db, property_id=property_id)
    if not property:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Property not found"
        )

    # Check authorization: PropertyResponse owner or admin
    if property.user_id != current_user.user_id and not user_crud.is_admin(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to view inquiries for this property"
        )
    
    inquiries = inquiry_crud.get_by_property(
        db=db,
        property_id=property_id,
        skip=skip,
        limit=limit
    )
    return inquiries
