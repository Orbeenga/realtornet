# app/api/endpoints/inquiries.py
"""
Inquiries management endpoints - Canonical compliant
Handles property inquiries with user-owner relationships, soft delete, and audit tracking
"""
from typing import Any, List, cast as typing_cast  # Alias typing.cast so endpoint-local narrowing never shadows SQLAlchemy helpers in future edits.
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

# --- DIRECT CRUD IMPORTS ---
from app.crud.inquiries import inquiry as inquiry_crud
from app.crud.properties import property as property_crud
from app.crud.users import user as user_crud
from app.models.users import User  # Narrow endpoint-local user values back to the ORM shape expected by CRUD permission helpers.

# --- DIRECT DEPENDENCY IMPORTS ---
from app.api.dependencies import (
    get_db,
    get_current_user,
    get_current_active_user,
    validate_request_size,
    pagination_params,
)

# --- DIRECT SCHEMA IMPORTS ---
from app.schemas.users import UserResponse
from app.schemas.inquiries import (
    InquiryCreate,
    InquiryExtendedResponse,
    InquiryResponse,
    InquiryUpdate,
)
from app.schemas.properties import PropertyResponse

router = APIRouter()


def _build_inquiry_extended_response(inquiry: Any) -> dict[str, Any]:
    """Serialize an inquiry with lightweight seeker contact details for owners."""
    inquiry_user = getattr(inquiry, "user", None)
    user_payload = None
    if inquiry_user is not None:
        first_name = str(getattr(inquiry_user, "first_name", "") or "").strip()
        last_name = str(getattr(inquiry_user, "last_name", "") or "").strip()
        full_name = f"{first_name} {last_name}".strip() or str(getattr(inquiry_user, "full_name", "") or "").strip()
        email = str(getattr(inquiry_user, "email", "") or "").strip()
        if full_name or email:
            user_payload = {
                "full_name": full_name,
                "email": email,
            }

    property_payload = None
    inquiry_property = getattr(inquiry, "property", None)
    if inquiry_property is not None:
        property_payload = PropertyResponse.model_validate(inquiry_property).model_dump(mode="json")

    return {
        "inquiry_id": inquiry.inquiry_id,
        "user_id": inquiry.user_id,
        "property_id": inquiry.property_id,
        "message": inquiry.message,
        "inquiry_status": inquiry.inquiry_status,
        "created_at": inquiry.created_at,
        "updated_at": inquiry.updated_at,
        "deleted_at": inquiry.deleted_at,
        "deleted_by": inquiry.deleted_by,
        "user": user_payload,
        "property": property_payload,
    }


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
    pagination: dict = Depends(pagination_params),
) -> Any:
    """
    Retrieve all inquiries made by the current user.
    
    Returns only non-deleted inquiries (deleted_at IS NULL).
    """
    inquiries = inquiry_crud.get_by_user(
        db=db,
        user_id=current_user.user_id,
        **pagination,
    )
    return inquiries


@router.get("/received", response_model=List[InquiryExtendedResponse])
def read_received_inquiries(
    db: Session = Depends(get_db),
    current_user: UserResponse = Depends(get_current_active_user),
    pagination: dict = Depends(pagination_params),
) -> Any:
    """
    Retrieve all inquiries for properties owned by the current user.
    
    - Only agents and admins can access
    - Returns inquiries for all properties where user_id matches
    """
    # Check if user is agent or admin
    current_user_model: User = typing_cast(User, current_user)  # typing cast: endpoint local only for CRUD role helper compatibility.
    if not user_crud.is_agent(current_user_model) and not user_crud.is_admin(current_user_model):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Agent or admin privileges required"
        )
    
    inquiries = inquiry_crud.get_by_property_owner(
        db=db,
        owner_user_id=current_user.user_id,
        **pagination,
    )
    return [_build_inquiry_extended_response(inquiry) for inquiry in inquiries]


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
    inquiry_property_id: int = typing_cast(int, inquiry.property_id)  # Narrow the ORM-backed property ID before loading the related property.
    property = property_crud.get(db=db, property_id=inquiry_property_id)
    if not property:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Associated property not found"
        )

    inquiry_user_id: int = typing_cast(int, inquiry.user_id)  # Narrow the ORM-backed inquiry owner ID before the authorization comparison.
    property_owner_id: int = typing_cast(int, property.user_id)  # Narrow the ORM-backed property owner ID before the authorization comparison.
    current_user_id: int = typing_cast(int, current_user.user_id)  # Narrow the authenticated user ID locally without changing the dependency contract.
    current_user_model: User = typing_cast(User, current_user)  # typing cast: endpoint local only for CRUD permission helper compatibility.
    if (inquiry_user_id != current_user_id and 
        property_owner_id != current_user_id and 
        not user_crud.is_admin(current_user_model)):
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
    inquiry_property_id: int = typing_cast(int, inquiry.property_id)  # Narrow the ORM-backed property ID before loading the related property.
    property = property_crud.get(db=db, property_id=inquiry_property_id)
    if not property:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Associated property not found"
        )

    inquiry_user_id: int = typing_cast(int, inquiry.user_id)  # Narrow the ORM-backed inquiry owner ID before the authorization comparison.
    property_owner_id: int = typing_cast(int, property.user_id)  # Narrow the ORM-backed property owner ID before the authorization comparison.
    current_user_id: int = typing_cast(int, current_user.user_id)  # Narrow the authenticated user ID locally without changing the dependency contract.
    current_user_model: User = typing_cast(User, current_user)  # typing cast: endpoint local only for CRUD permission helper compatibility.
    if (inquiry_user_id != current_user_id and 
        property_owner_id != current_user_id and 
        not user_crud.is_admin(current_user_model)):
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
    inquiry_user_id: int = typing_cast(int, inquiry.user_id)  # Narrow the ORM-backed inquiry owner ID before the authorization comparison.
    current_user_id: int = typing_cast(int, current_user.user_id)  # Narrow the authenticated user ID locally without changing the dependency contract.
    current_user_model: User = typing_cast(User, current_user)  # typing cast: endpoint local only for CRUD permission helper compatibility.
    if inquiry_user_id != current_user_id and not user_crud.is_admin(current_user_model):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to delete this inquiry"
        )
    
    # Soft delete with audit trail
    inquiry = inquiry_crud.soft_delete(
        db=db, 
        inquiry_id=inquiry_id,
        deleted_by_supabase_id=str(current_user.supabase_id)  # Normalize the authenticated user's Supabase UUID to the CRUD audit string type at the call site.
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
    pagination: dict = Depends(pagination_params),
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
    property_owner_id: int = typing_cast(int, property.user_id)  # Narrow the ORM-backed property owner ID before the authorization comparison.
    current_user_id: int = typing_cast(int, current_user.user_id)  # Narrow the authenticated user ID locally without changing the dependency contract.
    current_user_model: User = typing_cast(User, current_user)  # typing cast: endpoint local only for CRUD permission helper compatibility.
    if property_owner_id != current_user_id and not user_crud.is_admin(current_user_model):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to view inquiries for this property"
        )
    
    inquiries = inquiry_crud.get_by_property(
        db=db,
        property_id=property_id,
        **pagination,
    )
    return inquiries


@router.patch("/{inquiry_id}/status", response_model=InquiryResponse)
def update_inquiry_status(
    *,
    db: Session = Depends(get_db),
    inquiry_id: int,
    inquiry_status: str,
    current_user: UserResponse = Depends(get_current_active_user)
) -> Any:
    """
    Update inquiry status (new, viewed, responded).
    
    - Property owner can update status
    - Admins can update any inquiry status
    """
    inquiry = inquiry_crud.get(db=db, inquiry_id=inquiry_id)
    if not inquiry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Inquiry not found"
        )
    
    # Check authorization: property owner or admin
    inquiry_property_id: int = typing_cast(int, inquiry.property_id)  # Narrow the ORM-backed property ID before loading the related property.
    property = property_crud.get(db=db, property_id=inquiry_property_id)
    if not property:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Associated property not found"
        )

    property_owner_id: int = typing_cast(int, property.user_id)  # Narrow the ORM-backed property owner ID before the authorization comparison.
    current_user_id: int = typing_cast(int, current_user.user_id)  # Narrow the authenticated user ID locally without changing the dependency contract.
    current_user_model: User = typing_cast(User, current_user)  # typing cast: endpoint local only for CRUD permission helper compatibility.
    if property_owner_id != current_user_id and not user_crud.is_admin(current_user_model):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to update inquiry status"
        )
    
    # Validate status
    valid_statuses = ['new', 'viewed', 'responded']
    if inquiry_status not in valid_statuses:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid inquiry status provided."
        )
    updated_inquiry = inquiry_crud.update_status(
        db=db, 
        inquiry_id=inquiry_id, 
        new_status=inquiry_status
    )
    
    if not updated_inquiry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Inquiry not found during status update"
        )
    
    return updated_inquiry


@router.post("/{inquiry_id}/mark-viewed", response_model=InquiryResponse)
def mark_inquiry_viewed(
    *,
    db: Session = Depends(get_db),
    inquiry_id: int,
    current_user: UserResponse = Depends(get_current_active_user)
) -> Any:
    """
    Mark inquiry as viewed.
    
    - Property owner can mark as viewed
    - Admins can mark any inquiry as viewed
    """
    inquiry = inquiry_crud.get(db=db, inquiry_id=inquiry_id)
    if not inquiry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Inquiry not found"
        )
    
    # Check authorization: property owner or admin
    inquiry_property_id: int = typing_cast(int, inquiry.property_id)  # Narrow the ORM-backed property ID before loading the related property.
    property = property_crud.get(db=db, property_id=inquiry_property_id)
    if not property:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Associated property not found"
        )

    property_owner_id: int = typing_cast(int, property.user_id)  # Narrow the ORM-backed property owner ID before the authorization comparison.
    current_user_id: int = typing_cast(int, current_user.user_id)  # Narrow the authenticated user ID locally without changing the dependency contract.
    current_user_model: User = typing_cast(User, current_user)  # typing cast: endpoint local only for CRUD permission helper compatibility.
    if property_owner_id != current_user_id and not user_crud.is_admin(current_user_model):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to mark inquiry as viewed"
        )
    
    updated_inquiry = inquiry_crud.mark_as_viewed(
        db=db,
        inquiry_id=inquiry_id
    )
    
    if not updated_inquiry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Inquiry not found during mark as viewed"
        )
    
    return updated_inquiry


@router.post("/{inquiry_id}/mark-responded", response_model=InquiryResponse)
def mark_inquiry_responded(
    *,
    db: Session = Depends(get_db),
    inquiry_id: int,
    current_user: UserResponse = Depends(get_current_active_user)
) -> Any:
    """
    Mark inquiry as responded.
    
    - Property owner can mark as responded
    - Admins can mark any inquiry as responded
    """
    inquiry = inquiry_crud.get(db=db, inquiry_id=inquiry_id)
    if not inquiry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Inquiry not found"
        )
    
    # Check authorization: property owner or admin
    inquiry_property_id: int = typing_cast(int, inquiry.property_id)  # Narrow the ORM-backed property ID before loading the related property.
    property = property_crud.get(db=db, property_id=inquiry_property_id)
    if not property:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Associated property not found"
        )

    property_owner_id: int = typing_cast(int, property.user_id)  # Narrow the ORM-backed property owner ID before the authorization comparison.
    current_user_id: int = typing_cast(int, current_user.user_id)  # Narrow the authenticated user ID locally without changing the dependency contract.
    current_user_model: User = typing_cast(User, current_user)  # typing cast: endpoint local only for CRUD permission helper compatibility.
    if property_owner_id != current_user_id and not user_crud.is_admin(current_user_model):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to mark inquiry as responded"
        )
    
    updated_inquiry = inquiry_crud.mark_as_responded(
        db=db,
        inquiry_id=inquiry_id
    )
    
    if not updated_inquiry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Inquiry not found during mark as responded"
        )
    
    return updated_inquiry


@router.get("/count/{property_id}")
def count_inquiries_for_property(
    *,
    db: Session = Depends(get_db),
    property_id: int,
    current_user: UserResponse = Depends(get_current_active_user)
) -> dict:
    """
    Count total active inquiries for a property.
    
    - Property owner can view count
    - Admins can view any property's count
    - Requires active authenticated user
    """
    # Check if property exists
    property = property_crud.get(db=db, property_id=property_id)
    if not property:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Property not found"
        )

    # Check authorization: property owner or admin
    property_owner_id: int = typing_cast(int, property.user_id)  # Narrow the ORM-backed property owner ID before the authorization comparison.
    current_user_id: int = typing_cast(int, current_user.user_id)  # Narrow the authenticated user ID locally without changing the dependency contract.
    current_user_model: User = typing_cast(User, current_user)  # typing cast: endpoint local only for CRUD permission helper compatibility.
    if property_owner_id != current_user_id and not user_crud.is_admin(current_user_model):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to view inquiry count for this property"
        )

    count = inquiry_crud.count_by_property(
        db=db,
        property_id=property_id
    )
    
    return {"property_id": property_id, "inquiry_count": count}


@router.get("/count/{property_id}/by-status")
def count_inquiries_by_status(
    *,
    db: Session = Depends(get_db),
    property_id: int,
    inquiry_status: str,
    current_user: UserResponse = Depends(get_current_user)
) -> dict:
    """
    Count inquiries for a property by status.
    
    - Property owner can view status counts
    - Admins can view any property's status counts
    """
    # Check if property exists
    property = property_crud.get(db=db, property_id=property_id)
    if not property:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Property not found"
        )

    # Check authorization: property owner or admin
    property_owner_id: int = typing_cast(int, property.user_id)  # Narrow the ORM-backed property owner ID before the authorization comparison.
    current_user_id: int = typing_cast(int, current_user.user_id)  # Narrow the authenticated user ID locally without changing the dependency contract.
    current_user_model: User = typing_cast(User, current_user)  # typing cast: endpoint local only for CRUD permission helper compatibility.
    if property_owner_id != current_user_id and not user_crud.is_admin(current_user_model):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to view inquiry counts for this property"
        )
    
    # Validate status
    valid_statuses = ['new', 'viewed', 'responded']

    if inquiry_status not in valid_statuses:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Invalid inquiry status provided."
        )
    
    count = inquiry_crud.count_by_status(
        db=db, 
        property_id=property_id, 
        status=inquiry_status
    )
    
    return {"property_id": property_id, "inquiry_status": inquiry_status, "count": count}
