# app/api/endpoints/admin.py
"""
Admin management endpoints - Canonical compliant
Handles system-wide operations with proper soft delete, audit tracking, and RLS enforcement
"""
import logging
from typing import Any, Dict, List, cast as typing_cast  # Alias typing.cast so endpoint-local narrowing never shadows SQLAlchemy helpers in future edits.
from decimal import Decimal
from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session

from app.api.dependencies import (
    get_db,
    get_current_admin_user,
    validate_request_size,
    pagination_params,
)
from app.models.users import User as User

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
from app.tasks.email_tasks import (
    dispatch_email_task,
    send_agency_approval_email,
    send_agency_rejection_email,
)

# --- DIRECT SCHEMA IMPORTS ---
# from app.schemas.users import UserResponse, UserCreate, UserUpdate
from app.schemas.users import UserResponse, UserCreate, UserUpdate, UserRole
from app.schemas.agencies import AgencyCreate, AgencyRejectRequest, AgencyResponse
from app.schemas.agent_profiles import AgentProfileCreate
from app.schemas.properties import PropertyResponse, PropertyUpdate, ListingStatus, PropertyVerificationUpdate
from app.schemas.properties import PropertyCreate, ListingType as PropertyListingType
from app.schemas.inquiries import InquiryResponse
from app.schemas.stats import SystemStatsResponse as SystemStats

# Set up logging
logger = logging.getLogger(__name__)

router = APIRouter()


PROPERTY_RESPONSE_FIELD_NAMES = tuple(PropertyResponse.model_fields.keys())


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

    owner_user = user_crud.get_by_email(db, email=owner_email)
    if owner_user is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Applicant user account not found",
        )

    actor_supabase_id = str(current_user.supabase_id)
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
    )
    return agency


@router.patch("/agencies/{agency_id}/reject/", response_model=AgencyResponse)
def reject_agency_application(
    *,
    db: Session = Depends(get_db),
    agency_id: int,
    reject_in: AgencyRejectRequest | None = None,
    current_user: UserResponse = Depends(get_current_admin_user),
    _: None = Depends(validate_request_size)
) -> Any:
    """Reject a pending agency application with an optional reason."""
    agency = agency_crud.get(db, agency_id=agency_id)
    if agency is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agency not found",
        )

    reason = reject_in.reason if reject_in is not None else None
    agency = agency_crud.update(
        db,
        db_obj=agency,
        obj_in={
            "status": "rejected",
            "is_verified": False,
            "rejection_reason": reason,
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
    current_user: UserResponse = Depends(get_current_admin_user),
    _: None = Depends(validate_request_size)
) -> Any:
    """Revoke an approved agency back to pending review."""
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
            "rejection_reason": None,
        },
        updated_by=str(current_user.supabase_id),
    )


@router.patch("/agencies/{agency_id}/suspend/", response_model=AgencyResponse)
def suspend_agency(
    *,
    db: Session = Depends(get_db),
    agency_id: int,
    current_user: UserResponse = Depends(get_current_admin_user),
    _: None = Depends(validate_request_size)
) -> Any:
    """Suspend an agency without soft-deleting its data."""
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
        updated_by=str(current_user.supabase_id)  # Normalize the admin Supabase UUID to the CRUD audit string type at the call site.
    )
    
    logger.info(f"User deactivated: {user_id} by admin {current_user.user_id}")
    return db_user



# PROPERTY MANAGEMENT ENDPOINTS

@router.get("/properties", response_model=Dict[str, Any])
def get_properties(
    db: Session = Depends(get_db),
    pagination: dict = Depends(pagination_params),
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
    """
    properties = property_crud.get_multi(db, **pagination,)
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

    # Use CRUD method with audit tracking
    prop = property_crud.verify_property(
        db,
        property_id=property_id,
        is_verified=requested_status.value == "verified",
        moderation_status=requested_status.value,
        moderation_reason=moderation_update.moderation_reason,
        updated_by=str(current_user.supabase_id)  # Normalize the admin Supabase UUID to the CRUD audit string type at the call site.
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
        logger.error(f"Error generating stats overview")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to generate statistics. Please try again later."
        )
