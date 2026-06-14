# app/api/endpoints/admin.py
"""
Admin management endpoints - Canonical compliant
Handles system-wide operations with proper soft delete, audit tracking, and RLS enforcement
"""
import logging
from typing import Any, Dict, List, Optional, cast as typing_cast  # Alias typing.cast so endpoint-local narrowing never shadows SQLAlchemy helpers in future edits.
from decimal import Decimal
from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from fastapi.encoders import jsonable_encoder
from sqlalchemy import text, func, and_
from sqlalchemy.orm import Session

from app.api.dependencies import (
    get_db,
    get_current_admin_user,
    get_current_active_user,
    validate_request_size,
    pagination_params,
)
from app.models.users import User as User
from app.models.listing_events import ListingEvent
from app.models.listing_instructions import ListingInstruction
from app.models.properties import Property

# --- DIRECT CRUD IMPORTS ---
# We point directly to the files to avoid __init__.py circular/missing reference issues
from app.crud.users import user as user_crud
from app.crud.agencies import agency as agency_crud
from app.crud.agent_profiles import agent_profile as agent_profile_crud
from app.crud.locations import location as location_crud
from app.crud.properties import property as property_crud
from app.crud.property_types import property_type as property_type_crud
from app.crud.inquiries import inquiry as inquiry_crud
from app.services.analytics_services import analytics_service 
from app.services.auth_user_sync_service import (
    SupabaseUserSyncError,
    sync_supabase_auth_user_metadata,
)
from app.services.saved_search_notification_service import notify_saved_search_matches_for_property
from app.tasks.email_tasks import (
    dispatch_email_task,
    send_agency_approval_email,
    send_agency_rejection_email,
    send_property_moderation_email,
    send_role_change_email,
)

# --- DIRECT SCHEMA IMPORTS ---
# from app.schemas.users import UserResponse, UserCreate, UserUpdate
from app.schemas.users import (
    UserDeactivateRequest,
    UserResponse,
    UserCreate,
    UserUpdate,
    UserRole,
)
from app.schemas.agencies import AgencyCreate, AgencyRejectRequest, AgencyResponse
from app.schemas.agent_profiles import AgentProfileCreate
from app.schemas.properties import PropertyResponse, PropertyUpdate, ListingStatus, PropertyVerificationUpdate, ModerationStatus
from app.schemas.properties import PropertyCreate, ListingType as PropertyListingType
from app.schemas.inquiries import InquiryResponse
from app.schemas.stats import SystemStatsResponse as SystemStats
from app.schemas.audit import AuditActivityResponse

# Set up logging
logger = logging.getLogger(__name__)

router = APIRouter()


PROPERTY_RESPONSE_FIELD_NAMES = tuple(PropertyResponse.model_fields.keys())


def _role_value(role: Any) -> str:
    return str(getattr(role, "value", role))


def _user_display_name(user: User) -> str:
    return f"{user.first_name} {user.last_name}".strip()


def _serialize_property_item(property_obj: Any) -> dict[str, Any]:
    """
    Build a property response from explicit schema fields only.

    The first fix attempted to hand the whole ORM object to
    `PropertyResponse.model_validate(...)`. That works in most places, but it
    still gives Pydantic a live SQLAlchemy object to inspect. On production, the
    property model carries a PostGIS `geom` value (`WKBElement`), and that extra
    attribute can still surface during serialization even though the API schema
    does not expose it.

    By copying only the fields that `PropertyResponse` actually defines, we make
    the response builder blind to `geom`, `location.geom`, and any other ORM-only
    attributes the admin dashboard does not need.
    """
    raw_payload = {
        field_name: getattr(property_obj, field_name, None)
        for field_name in PROPERTY_RESPONSE_FIELD_NAMES
    }
    return typing_cast(
        dict[str, Any],
        PropertyResponse.model_validate(raw_payload).model_dump(mode="json"),
    )


def _serialize_property_items(properties: List[Any]) -> List[dict[str, Any]]:
    """
    Convert ORM property rows into plain JSON-safe dictionaries.

    We do this explicitly instead of handing raw ORM objects to
    `jsonable_encoder` because the property model carries a PostGIS geography
    field. That field is useful in the database layer, but it is not something
    the admin dashboard needs in the API response and it can trigger 500 errors
    when FastAPI tries to encode the whole ORM object directly.
    """
    return [_serialize_property_item(property_obj) for property_obj in properties]


# USER MANAGEMENT ENDPOINTS

@router.get("/agencies/", response_model=List[AgencyResponse])
def get_admin_agencies(
    db: Session = Depends(get_db),
    status_filter: str | None = Query(default=None, alias="status"),
    pagination: dict = Depends(pagination_params),
    current_user: UserResponse = Depends(get_current_admin_user)
) -> Any:
    """List agencies for admin review, optionally filtered by status."""
    if status_filter is not None and status_filter not in {"pending", "approved", "rejected", "suspended"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid agency status",
        )
    return agency_crud.get_multi(db, **pagination, status=status_filter)


@router.patch("/agencies/{agency_id}/approve/", response_model=AgencyResponse)
def approve_agency_application(
    *,
    db: Session = Depends(get_db),
    agency_id: int,
    decision_in: AgencyRejectRequest,
    current_user: UserResponse = Depends(get_current_admin_user),
    _: None = Depends(validate_request_size)
) -> Any:
    """
    Approve a pending agency and promote the applicant atomically.

    The applicant is resolved by agencies.owner_email. If Supabase Auth metadata
    sync fails, the transaction is rolled back so local DB role and external JWT
    claims cannot drift.
    """
    agency = agency_crud.get(db, agency_id=agency_id)
    if agency is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agency not found",
        )

    owner_email = typing_cast(str | None, agency.owner_email)
    if owner_email is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Agency application has no owner email",
        )

    actor_supabase_id = str(current_user.supabase_id)
    owner_user = user_crud.get_by_email(db, email=owner_email)

    if owner_user is None:
        agency = agency_crud.update(
            db,
            db_obj=agency,
            obj_in={
                "status": "approved",
                "is_verified": True,
                "rejection_reason": None,
                "status_reason": decision_in.reason,
            },
            updated_by=actor_supabase_id,
        )
        dispatch_email_task(
            send_agency_approval_email,
            owner_email,
            str(agency.name),
            True,
        )
        return agency

    try:
        owner_user = user_crud.update(
            db,
            db_obj=owner_user,
            obj_in={"user_role": UserRole.AGENCY_OWNER, "agency_id": agency_id},
            updated_by=actor_supabase_id,
        )
        agency = agency_crud.update(
            db,
            db_obj=agency,
            obj_in={
                "status": "approved",
                "is_verified": True,
                "rejection_reason": None,
                "status_reason": decision_in.reason,
            },
            updated_by=actor_supabase_id,
        )
        sync_supabase_auth_user_metadata(owner_user)
    except SupabaseUserSyncError as exc:
        db.rollback()
        logger.warning(
            "Agency approval rolled back because Supabase Auth sync failed",
            extra={"agency_id": agency_id, "owner_email": owner_email},
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    dispatch_email_task(
        send_agency_approval_email,
        owner_email,
        str(agency.name),
        False,
    )
    return agency


@router.patch("/agencies/{agency_id}/reject/", response_model=AgencyResponse)
def reject_agency_application(
    *,
    db: Session = Depends(get_db),
    agency_id: int,
    reject_in: AgencyRejectRequest,
    current_user: UserResponse = Depends(get_current_admin_user),
    _: None = Depends(validate_request_size)
) -> Any:
    """Reject a pending agency application with a required audit reason."""
    agency = agency_crud.get(db, agency_id=agency_id)
    if agency is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agency not found",
        )

    reason = reject_in.reason
    agency = agency_crud.update(
        db,
        db_obj=agency,
        obj_in={
            "status": "rejected",
            "is_verified": False,
            "rejection_reason": reason,
            "status_reason": reason,
        },
        updated_by=str(current_user.supabase_id),
    )
    owner_email = typing_cast(str | None, agency.owner_email)
    if owner_email:
        dispatch_email_task(
            send_agency_rejection_email,
            owner_email,
            str(agency.name),
            reason,
        )
    return agency


@router.patch("/agencies/{agency_id}/revoke/", response_model=AgencyResponse)
def revoke_agency_approval(
    *,
    db: Session = Depends(get_db),
    agency_id: int,
    decision_in: AgencyRejectRequest,
    current_user: UserResponse = Depends(get_current_admin_user),
    _: None = Depends(validate_request_size)
) -> Any:
    """Revoke an approved agency back to pending review with a required reason."""
    agency = agency_crud.get(db, agency_id=agency_id)
    if agency is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agency not found",
        )

    return agency_crud.update(
        db,
        db_obj=agency,
        obj_in={
            "status": "pending",
            "is_verified": False,
            "status_reason": decision_in.reason,
        },
        updated_by=str(current_user.supabase_id),
    )


@router.patch("/agencies/{agency_id}/suspend/", response_model=AgencyResponse)
def suspend_agency(
    *,
    db: Session = Depends(get_db),
    agency_id: int,
    decision_in: AgencyRejectRequest,
    current_user: UserResponse = Depends(get_current_admin_user),
    _: None = Depends(validate_request_size)
) -> Any:
    """Suspend an agency without soft-deleting its data, requiring a reason."""
    agency = agency_crud.get(db, agency_id=agency_id)
    if agency is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agency not found",
        )

    return agency_crud.update(
        db,
        db_obj=agency,
        obj_in={
            "status": "suspended",
            "is_verified": False,
            "status_reason": decision_in.reason,
        },
        updated_by=str(current_user.supabase_id),
    )


@router.get("/users", response_model=Dict[str, Any])
def get_users(
    db: Session = Depends(get_db),
    pagination: dict = Depends(pagination_params),
    current_user: UserResponse = Depends(get_current_admin_user)
) -> Any:
    """
    Retrieve users with pagination (admin only).
    
    Returns only non-deleted users (deleted_at IS NULL).
    CRUD layer enforces soft delete filtering.
    """
    users = user_crud.get_multi(db, **pagination,)
    total = user_crud.count_active(db)  # Use CRUD method that filters deleted_at
    
    return {
        "items": jsonable_encoder(users),
        "total": total,
        "page": pagination["skip"] // pagination["limit"] + 1 if pagination["limit"] else 1,
        "pages": (total + pagination["limit"] - 1) // pagination["limit"] if pagination["limit"] else 1
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
        created_by=str(current_user.supabase_id)  # Normalize the admin Supabase UUID to the CRUD audit string type at the call site.
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
    update_data = user_in.dict(exclude_unset=True)
    should_sync_supabase_auth = "user_role" in update_data
    next_role = update_data.get("user_role")
    current_role = _role_value(db_user.user_role)
    next_role_value = _role_value(next_role)
    role_changed = should_sync_supabase_auth and current_role != next_role_value
    is_access_reducing_role_change = (
        current_role in {UserRole.AGENT.value, UserRole.AGENCY_OWNER.value}
        and next_role_value == UserRole.SEEKER.value
    )
    if is_access_reducing_role_change and not update_data.get("role_change_reason"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="A role change reason is required when demoting a user",
        )

    try:
        db_user = user_crud.update(
            db, 
            db_obj=db_user, 
            obj_in=user_in,
            updated_by=str(current_user.supabase_id)  # Normalize the admin Supabase UUID to the CRUD audit string type at the call site.
        )

        if should_sync_supabase_auth:
            sync_supabase_auth_user_metadata(db_user)
    except SupabaseUserSyncError as exc:
        db.rollback()
        logger.warning(
            "Admin user update rolled back because Supabase Auth sync failed",
            extra={"target_user_id": user_id},
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    if role_changed:
        dispatch_email_task(
            send_role_change_email,
            str(db_user.email),
            _user_display_name(db_user),
            current_role,
            _role_value(db_user.user_role),
            typing_cast(str | None, db_user.role_change_reason),
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
    target_user_id: int = typing_cast(int, db_user.user_id)  # Narrow the ORM-backed target user ID before the self-delete comparison.
    current_user_id: int = typing_cast(int, current_user.user_id)  # Narrow the authenticated admin user ID locally without changing the dependency contract.
    if target_user_id == current_user_id:
        logger.warning(f"Self-deletion attempt by admin {current_user.user_id}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Admins cannot delete themselves"
        )
    
    # Soft delete with audit trail
    db_user = user_crud.soft_delete(
        db, 
        user_id=user_id,
        deleted_by_supabase_id=str(current_user.supabase_id)  # Normalize the admin Supabase UUID to the CRUD audit string type at the call site.
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
        updated_by=str(current_user.supabase_id)  # Normalize the admin Supabase UUID to the CRUD audit string type at the call site.
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
    deactivation_in: UserDeactivateRequest,
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
    target_user_id: int = typing_cast(int, db_user.user_id)  # Narrow the ORM-backed target user ID before the self-deactivate comparison.
    current_user_id: int = typing_cast(int, current_user.user_id)  # Narrow the authenticated admin user ID locally without changing the dependency contract.
    if target_user_id == current_user_id:
        logger.warning(f"Self-deactivation attempt by admin {current_user.user_id}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Admins cannot deactivate themselves",
        )
    
    # Use CRUD method with audit tracking
    db_user = user_crud.deactivate(
        db, 
        user_id=user_id,
        updated_by=str(current_user.supabase_id),  # Normalize the admin Supabase UUID to the CRUD audit string type at the call site.
        reason=deactivation_in.reason,
    )
    if db_user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found during deactivation",
        )

    dispatch_email_task(
        send_role_change_email,
        str(db_user.email),
        _user_display_name(db_user),
        _role_value(db_user.user_role),
        "deactivated",
        deactivation_in.reason,
    )
    
    logger.info(f"User deactivated: {user_id} by admin {current_user.user_id}")
    return db_user



# PROPERTY MANAGEMENT ENDPOINTS

@router.get("/properties", response_model=Dict[str, Any])
def get_properties(
    db: Session = Depends(get_db),
    pagination: dict = Depends(pagination_params),
    moderation_status: Optional[ModerationStatus] = Query(None),
    current_user: UserResponse = Depends(get_current_admin_user)
) -> Any:
    """
    Retrieve properties with pagination (admin only).

    Returns only non-deleted properties (deleted_at IS NULL).
    CRUD layer enforces soft delete filtering.

    The admin dashboard only needs the schema-backed listing fields, so we
    serialize through `PropertyResponse` instead of exposing the raw ORM model.
    That avoids production-only encoding failures from the database geometry
    column while keeping the response shape stable for the frontend.

    Query params:
    - moderation_status: filter by moderation status (e.g. agency_approved for queue).
    """
    filters: Dict[str, Any] = {}
    if moderation_status is not None:
        filters["moderation_status"] = moderation_status.value
    else:
        # Admin 'All' tab: exclude drafts by default so the All view mirrors the
        # UI expectation of showing all visible listings but not private drafts.
        # This avoids returning owner-only draft listings in a global admin list.
        filters["exclude_moderation_status"] = "draft"

    properties = property_crud.get_multi(db, **pagination, filters=filters if filters else None)

    # Admin "All" view excludes agent drafts — drafts are pre-submission
    # and irrelevant to admin governance.
    if moderation_status is None:
        properties = [p for p in properties if str(p.moderation_status) != ModerationStatus.draft.value]
    total = property_crud.count_active(db)  # Use CRUD method that filters deleted_at

    return {
        "items": _serialize_property_items(properties),
        "total": total,
        "page": pagination["skip"] // pagination["limit"] + 1 if pagination["limit"] else 1,
        "pages": (total + pagination["limit"] - 1) // pagination["limit"] if pagination["limit"] else 1
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
        deleted_by_supabase_id=str(current_user.supabase_id)  # Normalize the admin Supabase UUID to the CRUD audit string type at the call site.
    )
    
    logger.info(f"Property soft-deleted: {property_id} by admin {current_user.user_id}")
    return prop


# Verify_property function signature
@router.post("/properties/{property_id}/verify", response_model=PropertyResponse)
def verify_property(
    *,
    db: Session = Depends(get_db),
    property_id: int,
    verification_in: PropertyVerificationUpdate | None = None,
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

    moderation_update = verification_in or PropertyVerificationUpdate()
    requested_status = moderation_update.resolved_moderation_status
    previous_status = str(getattr(prop.moderation_status, "value", prop.moderation_status))

    # Normalize publish target: treat both 'verified' and 'live' inputs as a
    # request to move the listing into the Phase M `live` state.
    is_publish = requested_status in {ModerationStatus.verified, ModerationStatus.live}
    target_status = ModerationStatus.live if is_publish else requested_status

    # Three-tier moderation: admin can only publish from business-legal states.
    # For backward compatibility we allow:
    # - agency_approved (Phase L),
    # - admin_review (Phase M),
    # - verified/live (idempotent).
    if target_status.value == "live" and previous_status not in {"agency_approved", "admin_review", "verified", "live"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Admin can only verify listings that have been approved by the agency or are under admin review",
        )

    # Use CRUD method with audit tracking
    is_published = target_status.value == "live"
    prop = property_crud.verify_property(
        db,
        property_id=property_id,
        is_verified=is_published,
        moderation_status=target_status.value,
        moderation_reason=moderation_update.moderation_reason,
        updated_by=str(current_user.supabase_id),  # Normalize the admin Supabase UUID to the CRUD audit string type at the call site.
        actor_user_id=current_user.user_id,
    )

    if prop is not None:
        owner_user_id = typing_cast(int | None, prop.user_id)
        if owner_user_id is not None:
            owner = user_crud.get(db, user_id=owner_user_id)
            owner_email = str(getattr(owner, "email", "") or "").strip() if owner is not None else ""
            if owner_email:
                dispatch_email_task(
                    send_property_moderation_email,
                    owner_email,
                    str(prop.title),
                    target_status.value,
                    typing_cast(int, prop.property_id),
                    moderation_update.moderation_reason,
                )

        # Only send saved-search match emails the first time a listing becomes
        # publicly visible. Treat both legacy `verified` and new `live` as
        # published states, but only transition into `live` triggers matches.
        if target_status.value == "live" and previous_status not in {"verified", "live"}:
            notify_saved_search_matches_for_property(db, property_obj=prop)
    
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
    property_listing_status: str = str(getattr(prop.listing_status, "value", prop.listing_status))  # Normalize the ORM-backed listing status to a plain string before the idempotency check.
    if property_listing_status == "active":
        return prop

    # FIX: Align approve semantics with verification workflow before activation.
    property_is_verified: bool = typing_cast(bool, prop.is_verified)  # Narrow the ORM-backed verification flag before the approval precondition check.
    if not property_is_verified:
        property_crud.verify_property(
            db,
            property_id=property_id,
            updated_by=str(current_user.supabase_id)  # Normalize the admin Supabase UUID to the CRUD audit string type at the call site.
        )

    # Update with audit tracking
    prop_update = PropertyUpdate(listing_status=ListingStatus.active)  # Use the schema enum explicitly so the endpoint keeps the same response shape with precise typing.
    updated_prop = property_crud.update(
        db, 
        db_obj=prop, 
        obj_in=prop_update,
        updated_by=str(current_user.supabase_id)  # Normalize the admin Supabase UUID to the CRUD audit string type at the call site.
    )
    
    logger.info(f"Property approved: {property_id} by admin {current_user.user_id}")
    return updated_prop



# INQUIRY MANAGEMENT ENDPOINTS

@router.get("/inquiries", response_model=Dict[str, Any])
def read_all_inquiries(
    db: Session = Depends(get_db),
    current_user: UserResponse = Depends(get_current_admin_user),
    pagination: dict = Depends(pagination_params),
) -> Any:
    """
    Retrieve all inquiries with pagination (admin only).
    
    Returns only non-deleted inquiries (deleted_at IS NULL).
    CRUD layer enforces soft delete filtering.
    """
    inquiries = inquiry_crud.get_multi(db, **pagination,)
    total = inquiry_crud.count_active(db)  # Use CRUD method that filters deleted_at
    
    return {
        "items": jsonable_encoder(inquiries),
        "total": total,
        "page": pagination["skip"] // pagination["limit"] + 1 if pagination["limit"] else 1,
        "pages": (total + pagination["limit"] - 1) // pagination["limit"] if pagination["limit"] else 1
    }


@router.post("/bootstrap/demo-data", response_model=Dict[str, Any])
def bootstrap_demo_data(
    *,
    db: Session = Depends(get_db),
    agent_user_id: int = Body(..., embed=True),
    current_user: UserResponse = Depends(get_current_admin_user),
    _: None = Depends(validate_request_size)
) -> Any:
    """
    Idempotently bootstrap the minimum production data needed for journey smoke tests.

    Requires an existing agent user so the seeded property chain is attached to a
    real account rather than a hidden synthetic seed user.
    """
    agent_user = user_crud.get(db, user_id=agent_user_id)
    if agent_user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent user not found"
        )

    if not user_crud.is_agent(agent_user):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="bootstrap/demo-data requires an existing agent user"
        )

    actor_supabase_id = str(current_user.supabase_id)

    location = location_crud.get_or_create(
        db,
        state="lagos",
        city="lekki",
        neighborhood="phase 1",
        latitude=6.4474,
        longitude=3.4746,
    )

    property_type = property_type_crud.get_or_create(
        db,
        name="Apartment",
        description="Default seeded property type for production smoke tests."
    )

    agency = agency_crud.get_by_name(db, name="RealtorNet Demo Agency")
    if agency is None:
        agency = agency_crud.create(
            db,
            obj_in=AgencyCreate(
                name="RealtorNet Demo Agency",
                email="demo-agency@realtornet.example",
                phone_number="+2347000000000",
                address="Lekki Phase 1, Lagos",
                description="Seeded agency for production smoke tests."
            ),
            created_by=actor_supabase_id
        )

    agent_agency_id = typing_cast(int | None, agent_user.agency_id)
    if agent_agency_id != agency.agency_id:
        agent_user = user_crud.update(
            db,
            db_obj=agent_user,
            obj_in={"agency_id": agency.agency_id},
            updated_by=actor_supabase_id
        )

    agent_profile = agent_profile_crud.get_by_user_id(db, user_id=agent_user_id)
    if agent_profile is None:
        agency_id_value = typing_cast(int | None, agency.agency_id)
        agency_name_value = typing_cast(str | None, agency.name)
        agent_profile = agent_profile_crud.create(
            db,
            obj_in=AgentProfileCreate(
                user_id=agent_user_id,
                agency_id=agency_id_value,
                company_name=agency_name_value,
                specialization="Residential sales",
                bio="Seeded agent profile for production smoke tests."
            ),
            created_by=actor_supabase_id
        )

    existing_properties = property_crud.get_by_owner(
        db,
        user_id=agent_user_id,
        skip=0,
        limit=50,
    )

    verified_property = next(
        (property_item for property_item in existing_properties if typing_cast(bool, property_item.is_verified)),
        None
    )
    pending_property = next(
        (property_item for property_item in existing_properties if not typing_cast(bool, property_item.is_verified)),
        None
    )

    if verified_property is None:
        property_type_id_value = typing_cast(int | None, property_type.property_type_id)
        location_id_value = typing_cast(int | None, location.location_id)
        agency_id_value = typing_cast(int | None, agency.agency_id)
        verified_property = property_crud.create_with_owner(
            db,
            obj_in=PropertyCreate(
                title="Seeded Demo Apartment",
                description="Seeded listing used to unblock production smoke journeys.",
                property_type_id=property_type_id_value,
                location_id=location_id_value,
                price=Decimal("85000000"),
                bedrooms=3,
                bathrooms=3,
                property_size=Decimal("145"),
                listing_type=PropertyListingType.sale,
                agency_id=agency_id_value,
                latitude=6.4474,
                longitude=3.4746,
                has_security=True,
                has_garden=False,
                has_swimming_pool=False,
            ),
            user_id=agent_user_id,
            created_by=actor_supabase_id
        )

    if not typing_cast(bool, verified_property.is_verified):
        verified_property = property_crud.verify_property(
            db,
            property_id=typing_cast(int, verified_property.property_id),
            is_verified=True,
            updated_by=actor_supabase_id,
        )

    verified_property_value = typing_cast(Any, verified_property)
    property_listing_status = str(getattr(verified_property_value.listing_status, "value", verified_property_value.listing_status))
    if property_listing_status != "available":
        verified_property = property_crud.update_listing_status(
            db,
            property_id=typing_cast(int, verified_property_value.property_id),
            listing_status=typing_cast(Any, ListingStatus.available),
            updated_by=actor_supabase_id,
        )

    if pending_property is None:
        # We keep one seeded listing unverified on purpose so the moderation UI
        # always has a real "pending review" record to work with in production.
        property_type_id_value = typing_cast(int | None, property_type.property_type_id)
        location_id_value = typing_cast(int | None, location.location_id)
        agency_id_value = typing_cast(int | None, agency.agency_id)
        pending_property = property_crud.create_with_owner(
            db,
            obj_in=PropertyCreate(
                title="Seeded Pending Verification Listing",
                description="Seeded unverified listing used to test the admin verification workflow without SQL.",
                property_type_id=property_type_id_value,
                location_id=location_id_value,
                price=Decimal("91000000"),
                bedrooms=4,
                bathrooms=3,
                property_size=Decimal("168"),
                listing_type=PropertyListingType.sale,
                agency_id=agency_id_value,
                latitude=6.4474,
                longitude=3.4746,
                has_security=True,
                has_garden=True,
                has_swimming_pool=False,
            ),
            user_id=agent_user_id,
            created_by=actor_supabase_id
        )

    return {
        "location_id": location.location_id,
        "property_type_id": property_type.property_type_id,
        "agency_id": agency.agency_id,
        "agent_profile_id": agent_profile.profile_id,
        "property_id": typing_cast(int | None, verified_property.property_id) if verified_property is not None else None,
        "verified_property_id": typing_cast(int | None, verified_property.property_id) if verified_property is not None else None,
        "pending_property_id": typing_cast(int | None, pending_property.property_id) if pending_property is not None else None,
        "agent_user_id": agent_user_id
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
        logger.error(
            "Stats overview aggregation failed",
            extra={"error_type": type(e).__name__},
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to generate statistics. Please try again later."
        )


# AUDIT ACTIVITY ENDPOINT

@router.get("/audit/", response_model=AuditActivityResponse)
def get_audit_activity(
    db: Session = Depends(get_db),
    current_user: UserResponse = Depends(get_current_admin_user),
    limit: int = Query(default=20, ge=1, le=100),
) -> Any:
    """
    Admin-only audit activity summary.

    Returns creation count (last 30 days), deletion count (last 30 days),
    and a paginated list of recent changes from the audit views.
    """
    try:
        creation_count_result = db.execute(
            text("""
                SELECT COUNT(*) FROM public.audit_creations
                WHERE created_at > NOW() - INTERVAL '30 days'
            """)
        ).scalar()
        creation_count_30d = int(creation_count_result or 0)

        deletion_count_result = db.execute(
            text("""
                SELECT COUNT(*) FROM public.audit_deletions
                WHERE deleted_at > NOW() - INTERVAL '30 days'
            """)
        ).scalar()
        deletion_count_30d = int(deletion_count_result or 0)

        recent_changes_result = db.execute(
            text("""
                SELECT
                    table_name,
                    record_id,
                    created_at,
                    created_by,
                    updated_at,
                    updated_by,
                    deleted_at,
                    deleted_by,
                    actor_name
                FROM public.audit_recent_changes
                ORDER BY updated_at DESC NULLS LAST
                LIMIT :limit
            """),
            {"limit": limit},
        ).mappings().all()

        recent_changes = [
            {
                "table_name": str(row["table_name"]),
                "record_id": int(row["record_id"]),
                "created_at": row["created_at"],
                "created_by": row["created_by"],
                "updated_at": row["updated_at"],
                "updated_by": row["updated_by"],
                "deleted_at": row["deleted_at"],
                "deleted_by": row["deleted_by"],
                "actor_name": str(row["actor_name"]),
            }
            for row in recent_changes_result
        ]

        return {
            "creation_count_30d": creation_count_30d,
            "deletion_count_30d": deletion_count_30d,
            "recent_changes": recent_changes,
        }
    except Exception as e:
        logger.error(
            "Audit activity query failed",
            extra={"error_type": type(e).__name__},
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to retrieve audit activity. Please try again later.",
        )


@router.get("/properties/revocation-history", response_model=List[PropertyResponse])
def get_revocation_history(
    *,
    db: Session = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    current_user: UserResponse = Depends(get_current_active_user),
) -> Any:
    """Returns ALL listings that have EVER been revoked (to_status='revoked' in listing_events),
    regardless of current moderation_status. Ordered by most recent revocation event descending.
    Admin only."""
    if current_user.user_role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Admin only")

    latest_revocation = (
        db.query(
            ListingEvent.listing_id,
            func.max(ListingEvent.created_at).label("max_created_at"),
        )
        .filter(ListingEvent.to_status == "revoked")
        .group_by(ListingEvent.listing_id)
        .subquery()
    )

    most_recent_revocation_events = (
        db.query(ListingEvent)
        .join(
            latest_revocation,
            and_(
                ListingEvent.listing_id == latest_revocation.c.listing_id,
                ListingEvent.created_at == latest_revocation.c.max_created_at,
                ListingEvent.to_status == "revoked",
            ),
        )
        .subquery()
    )

    properties = (
        db.query(Property)
        .join(
            most_recent_revocation_events,
            Property.property_id == most_recent_revocation_events.c.listing_id,
        )
        .filter(Property.deleted_at.is_(None))
        .order_by(most_recent_revocation_events.c.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )

    for prop in properties:
        most_recent_event = (
            db.query(ListingEvent)
            .filter(
                ListingEvent.listing_id == prop.property_id,
                ListingEvent.to_status == "revoked",
            )
            .order_by(ListingEvent.created_at.desc())
            .first()
        )

        if most_recent_event:
            instruction = (
                db.query(ListingInstruction)
                .filter(
                    ListingInstruction.listing_id == prop.property_id,
                    ListingInstruction.triggered_by_event_id == most_recent_event.event_id,
                )
                .first()
            )
            typing_cast(Any, prop).has_instruction = instruction is not None
            typing_cast(Any, prop).latest_event_reason = most_recent_event.reason
        else:
            typing_cast(Any, prop).has_instruction = False
            typing_cast(Any, prop).latest_event_reason = None

    return properties


@router.get("/properties/rejection-history", response_model=List[PropertyResponse])
def get_rejection_history(
    *,
    db: Session = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    current_user: UserResponse = Depends(get_current_active_user),
) -> Any:
    """Returns ALL listings that have EVER been admin-rejected (to_status='admin_rejected' in listing_events),
    regardless of current moderation_status. Ordered by most recent rejection event descending.
    Admin only."""
    if current_user.user_role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Admin only")

    latest_rejection = (
        db.query(
            ListingEvent.listing_id,
            func.max(ListingEvent.created_at).label("max_created_at"),
        )
        .filter(ListingEvent.to_status == "admin_rejected")
        .group_by(ListingEvent.listing_id)
        .subquery()
    )

    most_recent_rejection_events = (
        db.query(ListingEvent)
        .join(
            latest_rejection,
            and_(
                ListingEvent.listing_id == latest_rejection.c.listing_id,
                ListingEvent.created_at == latest_rejection.c.max_created_at,
                ListingEvent.to_status == "admin_rejected",
            ),
        )
        .subquery()
    )

    properties = (
        db.query(Property)
        .join(
            most_recent_rejection_events,
            Property.property_id == most_recent_rejection_events.c.listing_id,
        )
        .filter(Property.deleted_at.is_(None))
        .order_by(most_recent_rejection_events.c.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )

    for prop in properties:
        most_recent_event = (
            db.query(ListingEvent)
            .filter(
                ListingEvent.listing_id == prop.property_id,
                ListingEvent.to_status == "admin_rejected",
            )
            .order_by(ListingEvent.created_at.desc())
            .first()
        )

        if most_recent_event:
            instruction = (
                db.query(ListingInstruction)
                .filter(
                    ListingInstruction.listing_id == prop.property_id,
                    ListingInstruction.triggered_by_event_id == most_recent_event.event_id,
                )
                .first()
            )
            typing_cast(Any, prop).has_instruction = instruction is not None
            typing_cast(Any, prop).latest_event_reason = most_recent_event.reason
        else:
            typing_cast(Any, prop).has_instruction = False
            typing_cast(Any, prop).latest_event_reason = None

    return properties
