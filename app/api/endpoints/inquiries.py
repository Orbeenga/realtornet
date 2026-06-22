# app/api/endpoints/inquiries.py
"""
Inquiries management endpoints - Canonical compliant
Handles property inquiries with user-owner relationships, soft delete, and audit tracking
"""
from datetime import datetime
from typing import Any, List, Optional, cast as typing_cast
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

# --- DIRECT CRUD IMPORTS ---
from app.crud.inquiries import inquiry as inquiry_crud
from app.crud.inquiry_replies import inquiry_reply as inquiry_reply_crud
from app.crud.properties import property as property_crud
from app.crud.users import user as user_crud
from app.crud.notifications import create_notification_fail_open
from app.models.users import User
from app.tasks.email_tasks import dispatch_email_task, send_inquiry_received_email, send_inquiry_reply_email

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
    InquiryReplyCreate,
    InquiryReplyResponse,
    InquiryResponse,
    InquiryUpdate,
)
from app.schemas.properties import PropertyResponse

router = APIRouter()


def _build_inquiry_extended_response(inquiry: Any, *, can_respond: bool = False) -> dict[str, Any]:
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
        "can_respond": can_respond,
        "reply_count": getattr(inquiry, "reply_count", 0),
        "latest_reply": InquiryReplyResponse.model_validate(inquiry.latest_reply).model_dump(mode="json") if getattr(inquiry, "latest_reply", None) else None,
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

    property_owner_id: int | None = typing_cast(int | None, property.user_id)
    if property_owner_id is not None:
        property_owner = user_crud.get(db, user_id=property_owner_id)
        owner_email = str(getattr(property_owner, "email", "") or "").strip() if property_owner is not None else ""
        if owner_email:
            seeker_name = f"{current_user.first_name} {current_user.last_name}".strip()
            dispatch_email_task(
                send_inquiry_received_email,
                owner_email,
                str(property.title),
                seeker_name,
                str(current_user.email),
                typing_cast(str | None, current_user.phone_number),
                str(inquiry.message or inquiry_in.message),
                typing_cast(int, property.property_id),
            )
    
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
    can_respond = user_crud.is_agent(current_user_model) and not user_crud.is_admin(current_user_model)
    return [_build_inquiry_extended_response(inquiry, can_respond=can_respond) for inquiry in inquiries]


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
    if property_owner_id != current_user_id:
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
    if property_owner_id != current_user_id:
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


@router.post("/{inquiry_id}/reply/", response_model=InquiryReplyResponse, status_code=status.HTTP_201_CREATED)
def reply_to_inquiry(
    *,
    db: Session = Depends(get_db),
    inquiry_id: int,
    reply_in: InquiryReplyCreate,
    current_user: UserResponse = Depends(get_current_active_user),
    _: None = Depends(validate_request_size)
) -> Any:
    """
    Reply to an inquiry.
    
    - Agent or agency_owner who received the inquiry can reply
    - First reply auto-marks inquiry as responded
    - Seeker receives in-platform notification
    - Email dispatched to seeker if MAIL_FROM is verified (fail-open)
    """
    inquiry = inquiry_crud.get(db=db, inquiry_id=inquiry_id)
    if not inquiry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Inquiry not found"
        )

    inquiry_property_id: int = typing_cast(int, inquiry.property_id)
    property = property_crud.get(db=db, property_id=inquiry_property_id)
    if not property:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Associated property not found"
        )

    current_user_id: int = typing_cast(int, current_user.user_id)
    current_user_model: User = typing_cast(User, current_user)
    property_owner_id: int = typing_cast(int, property.user_id)
    is_property_owner = property_owner_id == current_user_id

    is_agency_member = False
    if property.agency_id is not None:
        from app.models.agency_join_requests import AgencyAgentMembership
        from sqlalchemy import select, and_
        stmt = select(AgencyAgentMembership).where(
            and_(
                AgencyAgentMembership.user_id == current_user_id,
                AgencyAgentMembership.agency_id == property.agency_id,
                AgencyAgentMembership.status == 'active',
                AgencyAgentMembership.deleted_at.is_(None),
            )
        )
        is_agency_member = db.execute(stmt).scalar_one_or_none() is not None

    if not is_property_owner and not is_agency_member and not user_crud.is_admin(current_user_model):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to reply to this inquiry"
        )

    reply = inquiry_reply_crud.create(
        db=db,
        inquiry_id=inquiry_id,
        author_id=current_user_id,
        body=reply_in.body,
    )

    is_first_reply = inquiry_reply_crud.count_by_inquiry(db=db, inquiry_id=inquiry_id) == 1
    if is_first_reply:
        inquiry_crud.mark_as_responded(db=db, inquiry_id=inquiry_id)

    seeker_id: int = typing_cast(int, inquiry.user_id)
    seeker_user = user_crud.get(db=db, user_id=seeker_id)
    property_title = str(getattr(property, "title", "") or "") or "a property"
    agent_name = f"{current_user.first_name} {current_user.last_name}".strip() or "An agent"

    create_notification_fail_open(
        db,
        user_id=seeker_id,
        event_type="inquiry_replied",
        listing_id=typing_cast(int, property.property_id),
        body_text=f"{agent_name} replied to your inquiry on {property_title}",
    )

    if seeker_user is not None:
        seeker_email = str(getattr(seeker_user, "email", "") or "").strip()
        if seeker_email:
            dispatch_email_task(
                send_inquiry_reply_email,
                seeker_email,
                property_title,
                agent_name,
                reply.body,
                typing_cast(int, property.property_id),
            )

    db.flush()
    db.refresh(reply)

    author_display_name = agent_name
    return InquiryReplyResponse(
        reply_id=typing_cast(int, reply.reply_id),
        inquiry_id=typing_cast(int, reply.inquiry_id),
        author_id=typing_cast(int, reply.author_id),
        author_display_name=author_display_name,
        body=typing_cast(str, reply.body),
        created_at=typing_cast(datetime, reply.created_at),
        viewed_at=typing_cast(datetime | None, reply.viewed_at),
        edited_at=typing_cast(datetime | None, reply.edited_at),
    )


@router.get("/{inquiry_id}/replies/", response_model=List[InquiryReplyResponse])
def read_inquiry_replies(
    *,
    db: Session = Depends(get_db),
    inquiry_id: int,
    current_user: UserResponse = Depends(get_current_active_user),
    pagination: dict = Depends(pagination_params),
) -> Any:
    """
    Get replies for an inquiry.
    
    - Seeker who sent the inquiry can read
    - Agent/agency_owner who received the inquiry can read
    - Admin can read all
    """
    inquiry = inquiry_crud.get(db=db, inquiry_id=inquiry_id)
    if not inquiry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Inquiry not found"
        )

    inquiry_property_id: int = typing_cast(int, inquiry.property_id)
    property = property_crud.get(db=db, property_id=inquiry_property_id)
    if not property:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Associated property not found"
        )

    inquiry_user_id: int = typing_cast(int, inquiry.user_id)
    property_owner_id: int = typing_cast(int, property.user_id)
    current_user_id: int = typing_cast(int, current_user.user_id)
    current_user_model: User = typing_cast(User, current_user)

    is_agency_member = False
    if property.agency_id is not None:
        from app.models.agency_join_requests import AgencyAgentMembership
        from sqlalchemy import select, and_
        stmt = select(AgencyAgentMembership).where(
            and_(
                AgencyAgentMembership.user_id == current_user_id,
                AgencyAgentMembership.agency_id == property.agency_id,
                AgencyAgentMembership.status == 'active',
                AgencyAgentMembership.deleted_at.is_(None),
            )
        )
        is_agency_member = db.execute(stmt).scalar_one_or_none() is not None

    if (inquiry_user_id != current_user_id
        and property_owner_id != current_user_id
        and not is_agency_member
        and not user_crud.is_admin(current_user_model)):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to view replies to this inquiry"
        )

    replies = inquiry_reply_crud.get_by_inquiry(
        db=db,
        inquiry_id=inquiry_id,
        skip=pagination["skip"],
        limit=pagination["limit"],
    )

    result = []
    for reply in replies:
        author = getattr(reply, "author", None)
        display_name = ""
        if author is not None:
            first = str(getattr(author, "first_name", "") or "").strip()
            last = str(getattr(author, "last_name", "") or "").strip()
            display_name = f"{first} {last}".strip()
        result.append(InquiryReplyResponse(
            reply_id=typing_cast(int, reply.reply_id),
            inquiry_id=typing_cast(int, reply.inquiry_id),
            author_id=typing_cast(int, reply.author_id),
            author_display_name=display_name,
            body=typing_cast(str, reply.body),
            created_at=typing_cast(datetime, reply.created_at),
            viewed_at=typing_cast(datetime | None, reply.viewed_at),
            edited_at=typing_cast(datetime | None, reply.edited_at),
        ))

    return result


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


@router.post("/{inquiry_id}/mark-responded", response_model=InquiryResponse)
def mark_inquiry_responded(
    *,
    db: Session = Depends(get_db),
    inquiry_id: int,
    current_user: UserResponse = Depends(get_current_active_user)
) -> Any:
    """
    Mark inquiry as responded (deprecated).

    This endpoint is deprecated in Phase R. Inquiry status now transitions
    to 'responded' automatically when the first reply is posted via
    POST /{inquiry_id}/reply/. Use the reply endpoint instead.

    - Property owner can mark as responded
    - Admins can mark any inquiry as responded
    """
    inquiry = inquiry_crud.get(db=db, inquiry_id=inquiry_id)
    if not inquiry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Inquiry not found"
        )

    inquiry_property_id: int = typing_cast(int, inquiry.property_id)
    property = property_crud.get(db=db, property_id=inquiry_property_id)
    if not property:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Associated property not found"
        )

    property_owner_id: int = typing_cast(int, property.user_id)
    current_user_id: int = typing_cast(int, current_user.user_id)
    current_user_model: User = typing_cast(User, current_user)
    if property_owner_id != current_user_id:
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
