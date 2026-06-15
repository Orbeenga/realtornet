# app/api/endpoints/properties.py
"""
Property management endpoints - Canonical compliant
Handles property CRUD with geography, multi-tenant enforcement, and soft delete
"""
from decimal import Decimal  # Narrow float query inputs to the Decimal-compatible type expected by the filter schema.
from typing import Any, List, Optional, cast as typing_cast  # Alias typing.cast so endpoint-local narrowing never shadows SQLAlchemy helpers elsewhere.
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc
from sqlalchemy.orm import Session

# --- DIRECT CRUD IMPORTS ---
from app.crud.properties import property as property_crud
from app.crud.users import user as user_crud
from app.services.location_resolution_service import resolve_location_name_to_record
from app.services.saved_search_notification_service import notify_saved_search_matches_for_property
from app.services.listing_moderation_guard import ensure_legal_moderation_transition
from app.core.config import settings
from app.tasks.email_tasks import (
    dispatch_email_task,
    send_property_moderation_email,
    send_submission_notification_email,
    send_agency_approval_notification_email,
    send_instruction_notification_email,
)

# --- DIRECT DEPENDENCY IMPORTS ---
from app.api.dependencies import (
    get_db,
    get_current_user,
    get_current_active_user,
    get_current_user_optional,
    validate_request_size,
    pagination_params,
)

# --- DIRECT SCHEMA IMPORTS ---
from app.schemas.users import UserResponse
from app.schemas.properties import (
    PropertyResponse,
    PropertyCreate,
    PropertyUpdate,
    PropertyVerificationUpdate,
    PropertyAgencyActionUpdate,
    PropertyFilter,
    ListingStatus as PropertyListingStatus,
    ListingType as PropertyListingType,
    ModerationStatus,
    ListingEventResponse,
    InstructionCreate,
    ListingInstructionResponse,
)

# --- DIRECT MODEL ENUM IMPORTS ---
from app.models.properties import Property, ListingStatus, ListingType, ModerationStatus as PropertyModerationStatus
from app.models.users import User, UserRole
from app.models.agencies import Agency

router = APIRouter()


@router.get("/", response_model=List[PropertyResponse])
def read_properties(
    db: Session = Depends(get_db),
    pagination: dict = Depends(pagination_params),
    search: Optional[str] = Query(None),
    location_id: Optional[int] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    bedrooms: Optional[int] = None,
    bathrooms: Optional[float] = None,
    property_type_id: Optional[int] = None,
    agency_id: Optional[int] = None,
    listing_type: Optional[ListingType] = None,
    listing_status: Optional[ListingStatus] = None,
    moderation_status: Optional[ModerationStatus] = None,
    current_user: Optional[UserResponse] = Depends(get_current_user_optional)
) -> Any:
    """
    Retrieve properties with optional filtering.
    
    Public users: Only see approved, non-deleted properties
    Agents: See approved properties + their own (any status)
    Admins: See all properties
    
    CRUD layer enforces soft delete filtering (deleted_at IS NULL).
    """
    if agency_id is not None and (
        current_user is None
        or not (
            user_crud.is_agent(typing_cast(User, current_user))
            or user_crud.is_agency_owner(typing_cast(User, current_user))
            or user_crud.is_admin(typing_cast(User, current_user))
        )
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="agency_id filter requires agent, agency_owner, or admin role",
        )

    min_price_value: Decimal | None = typing_cast(Decimal | None, min_price)  # Preserve FastAPI's runtime coercion while narrowing the filter input for pyright.
    max_price_value: Decimal | None = typing_cast(Decimal | None, max_price)  # Preserve FastAPI's runtime coercion while narrowing the filter input for pyright.
    bathrooms_value: int | None = typing_cast(int | None, bathrooms)  # Preserve the existing query value flow while matching the filter schema's integer field.
    listing_type_value: PropertyListingType | None = typing_cast(PropertyListingType | None, listing_type)  # Narrow the enum locally because model and schema enums share the same runtime values.
    listing_status_value: PropertyListingStatus | None = typing_cast(PropertyListingStatus | None, listing_status)  # Narrow the enum locally because model and schema enums share the same runtime values.
    search_params = PropertyFilter(
        search=search,
        location_id=location_id,
        min_price=min_price_value,
        max_price=max_price_value,
        bedrooms=bedrooms,
        bathrooms=bathrooms_value,
        property_type_id=property_type_id,
        agency_id=agency_id,
        listing_type=listing_type_value,
        listing_status=listing_status_value,
        moderation_status=moderation_status,
    )
    
    # Determine visibility based on user role
    if current_user:
        current_user_model: User = typing_cast(User, current_user)  # Narrow the dependency result to the ORM-backed user type expected by CRUD role helpers.
        if user_crud.is_admin(current_user_model):
            # Admins see all properties
            properties = property_crud.get_multi_by_params(
                db, 
                **pagination, 
                params=search_params
            )
        elif user_crud.is_agency_owner(current_user_model):
            # Agency owners see all properties in their agency (any status)
            properties = property_crud.get_multi_by_params_for_agency_owner(
                db,
                **pagination,
                params=search_params,
                agency_owner_user_id=current_user.user_id
            )
        elif user_crud.is_agent(current_user_model):
            # Agents see approved + their own properties
            properties = property_crud.get_multi_by_params_for_agent(
                db,
                **pagination,
                params=search_params,
                agent_user_id=current_user.user_id
            )
        else:
            # Regular users see only approved
            properties = property_crud.get_multi_by_params_approved(
                db,
                **pagination,
                params=search_params
            )
    else:
        # Anonymous users see only approved
        properties = property_crud.get_multi_by_params_approved(
            db, 
            **pagination, 
            params=search_params
        )
    
    return properties


@router.get("/featured", response_model=List[PropertyResponse])
def read_featured_properties(
    db: Session = Depends(get_db),
    limit: int = Query(default=6, ge=1, le=24, description="Maximum featured properties"),
) -> Any:
    """Return recent public featured properties for the landing page."""
    return property_crud.get_public_featured(db, limit=limit)


@router.post("/", response_model=PropertyResponse, status_code=status.HTTP_201_CREATED)
def create_property(
    *,
    db: Session = Depends(get_db),
    property_in: PropertyCreate,
    current_user: UserResponse = Depends(get_current_active_user),
    _: None = Depends(validate_request_size)
) -> Any:
    """
    Create new property listing.
    
    Permissions:
    - User must be an agent or admin
    - Agents can only create properties for their own agency
    - Admins can create properties for any agency
    
    Audit: Tracks creator via user_id FK
    """
    current_user_model: User = typing_cast(User, current_user)  # Narrow the authenticated dependency result to the ORM-backed user type used by CRUD permission helpers.
    # Check if user is allowed to create properties
    if not user_crud.is_agent_or_admin(current_user_model):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only agents and admins can create property listings"
        )
    
    # Multi-tenant enforcement: Agents can only create for their agency
    if user_crud.is_agent(current_user_model):
        current_user_agency_id: int | None = typing_cast(int | None, current_user_model.agency_id)  # Narrow the optional agency foreign key before tenant checks.
        if not current_user_agency_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Agent must belong to an agency to create properties"
            )
        
        # If property_in has agency_id, it must match agent's agency
        if hasattr(property_in, 'agency_id') and property_in.agency_id and property_in.agency_id != current_user_agency_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot create property for another agency"
            )
        
        # Auto-assign agent's agency if not specified
        if hasattr(property_in, 'agency_id') and not property_in.agency_id:
            property_in.agency_id = current_user_agency_id
    
    # Validate geography if coordinates provided
    if hasattr(property_in, 'latitude') and property_in.latitude is not None:
        if not (-90 <= property_in.latitude <= 90):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Latitude must be between -90 and 90"
            )
    
    if hasattr(property_in, 'longitude') and property_in.longitude is not None:
        if not (-180 <= property_in.longitude <= 180):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Longitude must be between -180 and 180"
            )

    if property_in.location_name and property_in.location_id is None:
        location_record = resolve_location_name_to_record(db, location_name=property_in.location_name)
        if location_record is not None:
            property_in.location_id = typing_cast(int, location_record.location_id)
    
    # Create property with owner tracking
    created_by_supabase_id: str = str(current_user.supabase_id)  # Normalize the authenticated UUID to the string audit format expected by the CRUD layer.
    property = property_crud.create_with_owner(
        db=db, 
        obj_in=property_in, 
        user_id=current_user.user_id,  # Explicit FK reference
        created_by=created_by_supabase_id
    )
    
    return property


@router.get("/agency-queue", response_model=List[PropertyResponse])
def get_agency_queue(
    *,
    db: Session = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    current_user: UserResponse = Depends(get_current_active_user),
) -> Any:
    """Returns listings where moderation_status = 'agency_review' AND agency_id = current_user.agency_id.
    Role gate: agency_owner only."""
    if current_user.user_role != UserRole.AGENCY_OWNER:
        raise HTTPException(status_code=403, detail="Only agency owners can view the agency queue")

    if not current_user.agency_id:
        raise HTTPException(status_code=400, detail="User does not belong to an agency")

    properties = (
        db.query(Property)
        .filter(
            Property.moderation_status == PropertyModerationStatus.agency_review,
            Property.agency_id == current_user.agency_id,
            Property.deleted_at.is_(None),
        )
        .order_by(desc(Property.created_at))
        .offset(skip)
        .limit(limit)
        .all()
    )
    return properties


@router.get("/agency-inventory", response_model=List[PropertyResponse])
def get_agency_inventory(
    *,
    db: Session = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    current_user: UserResponse = Depends(get_current_active_user),
) -> Any:
    """Returns listings where moderation_status = 'live' AND agency_id = current_user.agency_id.
    Role gate: agent or agency_owner with active membership in that agency."""
    if current_user.user_role not in [UserRole.AGENT, UserRole.AGENCY_OWNER]:
        raise HTTPException(status_code=403, detail="Only agents and agency owners can view the agency inventory")

    if not current_user.agency_id:
        raise HTTPException(status_code=400, detail="User does not belong to an agency")

    properties = (
        db.query(Property)
        .filter(
            Property.moderation_status == PropertyModerationStatus.live,
            Property.agency_id == current_user.agency_id,
            Property.deleted_at.is_(None),
        )
        .order_by(desc(Property.created_at))
        .offset(skip)
        .limit(limit)
        .all()
    )
    return properties


@router.get("/pending-admin", response_model=List[PropertyResponse])
def get_pending_admin(
    *,
    db: Session = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    current_user: UserResponse = Depends(get_current_active_user),
) -> Any:
    """Returns listings where moderation_status = 'admin_review' AND agency_id = current_user.agency_id.
    Role gate: agency_owner only."""
    if current_user.user_role != UserRole.AGENCY_OWNER:
        raise HTTPException(status_code=403, detail="Only agency owners can view pending admin listings")

    if not current_user.agency_id:
        raise HTTPException(status_code=400, detail="User does not belong to an agency")

    properties = (
        db.query(Property)
        .filter(
            Property.moderation_status == PropertyModerationStatus.admin_review,
            Property.agency_id == current_user.agency_id,
            Property.deleted_at.is_(None),
        )
        .order_by(desc(Property.created_at))
        .offset(skip)
        .limit(limit)
        .all()
    )
    return properties


@router.get("/{property_id}", response_model=PropertyResponse)
def read_property(
    *,
    db: Session = Depends(get_db),
    property_id: int,
    current_user: Optional[UserResponse] = Depends(get_current_user_optional)
) -> Any:
    """
    Get property by ID.
    
    Public/anonymous: Only approved properties
    Agents: Approved properties + their own
    Admins: All properties
    """
    property = property_crud.get(db=db, property_id=property_id)
    
    if not property:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Property not found"
        )

    # Phase N N.1: enrich response with instruction fields for listing creator / agency_owner / admin
    if current_user:
        from app.services.listing_instruction_service import enrich_property_with_instruction_fields
        enrich_property_with_instruction_fields(
            db,
            property_obj=property,
            current_user_id=current_user.user_id,
            current_user_role=getattr(current_user, "user_role", ""),
        )

    # Visibility check
    if current_user:
        current_user_model: User = typing_cast(User, current_user)  # Narrow the optional dependency result before calling ORM-oriented role helpers.
        property_user_id: int = typing_cast(int, property.user_id)  # Narrow the ORM integer attribute to the runtime int carried on the loaded entity.
        property_status = getattr(
            typing_cast(Any, property).moderation_status,
            "value",
            typing_cast(Any, property).moderation_status,
        )
        # Phase M: treat `live` as canonical published state, but honor legacy
        # `verified` and historical is_verified flag for backward compatibility.
        is_published_for_authenticated: bool = (
            property_status in {PropertyModerationStatus.live.value, PropertyModerationStatus.verified.value}
            or typing_cast(bool, property.is_verified)
        )
        if user_crud.is_admin(current_user_model):
            return property
        elif property_user_id == current_user.user_id:
            return property
        elif (
            getattr(current_user, 'agency_id', None) is not None
            and getattr(property, 'agency_id', None) is not None
            and int(typing_cast(int, current_user.agency_id)) == int(typing_cast(int, property.agency_id))
        ):
            return property
        elif is_published_for_authenticated:
            return property
        else:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not enough permissions to view this property"
            )
    else:
        # Anonymous users can only see published listings. Phase M treats
        # `live` as the canonical public state but still honors legacy
        # `verified` and the historical is_verified flag.
        property_status = getattr(
            typing_cast(Any, property).moderation_status,
            "value",
            typing_cast(Any, property).moderation_status,
        )
        is_published_for_anonymous: bool = (
            property_status in {PropertyModerationStatus.live.value, PropertyModerationStatus.verified.value}
            or typing_cast(bool, property.is_verified)
        )
        if is_published_for_anonymous:
            return property
        else:
            # Intentional 404 instead of 403 - prevents property ID enumeration
            # by anonymous users (security obfuscation)
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Property not found"
            )


@router.get("/{property_id}/events", response_model=List[ListingEventResponse])
def read_property_listing_events(
    *,
    db: Session = Depends(get_db),
    property_id: int,
    current_user: UserResponse = Depends(get_current_active_user),
) -> Any:
    """Get ordered listing event history for a property.

    Access:
    - Admin: any listing
    - Agent: their own listings
    - Agency owner: listings in their agency
    """
    property = property_crud.get(db=db, property_id=property_id)
    if not property:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Property not found",
        )

    current_user_model: User = typing_cast(User, current_user)
    property_user_id: int = typing_cast(int, property.user_id)
    property_agency_id: int | None = typing_cast(int | None, property.agency_id)
    current_user_agency_id: int | None = typing_cast(int | None, current_user_model.agency_id)

    is_admin = user_crud.is_admin(current_user_model)
    is_owning_agent = (
        property_user_id == current_user.user_id
        and user_crud.is_agent(current_user_model)
    )
    is_agency_owner_for_listing = (
        user_crud.is_agency_owner(current_user_model)
        and property_agency_id is not None
        and property_agency_id == current_user_agency_id
    )

    if not is_admin and not is_owning_agent and not is_agency_owner_for_listing:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to view this listing's event history",
        )

    events = property_crud.get_listing_events(db=db, property_id=property_id)
    return events


@router.put("/{property_id}", response_model=PropertyResponse)
def update_property(
    *,
    db: Session = Depends(get_db),
    property_id: int,
    property_in: PropertyUpdate,
    current_user: UserResponse = Depends(get_current_active_user),
    _: None = Depends(validate_request_size)
) -> Any:
    """
    Update a property.
    
    Permissions:
    - Owner can update their own property
    - Admin can update any property
    
    Audit: Tracks updater via updated_by (Supabase UUID)
    """
    property = property_crud.get(db=db, property_id=property_id)
    
    if not property:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Property not found"
        )
    
    # Permission check: owner or admin
    current_user_model: User = typing_cast(User, current_user)  # Narrow the authenticated dependency result to the ORM-backed user type used by permission helpers.
    property_user_id: int = typing_cast(int, property.user_id)  # Narrow the ORM integer attribute to the runtime int carried on the loaded entity.
    if property_user_id != current_user.user_id and not user_crud.is_admin(current_user_model):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to update this property"
        )
    
    # Validate geography if coordinates being updated
    if hasattr(property_in, 'latitude') and property_in.latitude is not None:
        if not (-90 <= property_in.latitude <= 90):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Latitude must be between -90 and 90"
            )
    
    if hasattr(property_in, 'longitude') and property_in.longitude is not None:
        if not (-180 <= property_in.longitude <= 180):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Longitude must be between -180 and 180"
            )

    if property_in.location_name and property_in.location_id is None:
        location_record = resolve_location_name_to_record(db, location_name=property_in.location_name)
        if location_record is not None:
            property_in.location_id = typing_cast(int, location_record.location_id)

    # Phase N N.1: instruction mediation gate — revoked/admin_rejected require agency instruction
    from app.services.listing_instruction_service import (
        check_instruction_gate,
        enrich_property_with_instruction_fields,
    )
    check_instruction_gate(db, property_obj=property)

    # Update with audit tracking
    updated_by_supabase_id: str = str(current_user.supabase_id)  # Normalize the authenticated UUID to the string audit format expected by the CRUD layer.
    property = property_crud.update(
        db=db,
        db_obj=property,
        obj_in=property_in,
        updated_by_supabase_id=updated_by_supabase_id
    )

    enrich_property_with_instruction_fields(
        db,
        property_obj=property,
        current_user_id=current_user.user_id,
        current_user_role=str(getattr(current_user, "user_role", "")),
    )

    return property


@router.patch("/{property_id}/verify", response_model=PropertyResponse)
def verify_property(
    *,
    db: Session = Depends(get_db),
    property_id: int,
    verification_in: PropertyVerificationUpdate,
    current_user: UserResponse = Depends(get_current_active_user),
    _: None = Depends(validate_request_size)
) -> Any:
    """
    Update the public-verification state of a property listing.

    Permissions (three-tier moderation):
    - Admins can set any moderation status; verifying to 'verified'
      is only allowed from 'agency_approved' status.
    - Agency owners and owning agents can return their listing to
      pending_review, but can no longer directly publish.

    This endpoint exists separately from the general update endpoint so the UI
    can expose a clear "verification" action without asking operators to edit
    raw listing fields or fall back to manual SQL.
    """
    property = property_crud.get(db=db, property_id=property_id)

    if not property:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Property not found"
        )

    current_user_model: User = typing_cast(User, current_user)  # Narrow the authenticated dependency result to the ORM-backed user type used by permission helpers.
    property_user_id: int = typing_cast(int, property.user_id)  # Narrow the ORM integer attribute to the runtime int carried on the loaded entity.
    is_admin = user_crud.is_admin(current_user_model)
    property_agency_id: int | None = typing_cast(int | None, property.agency_id)
    current_user_agency_id: int | None = typing_cast(int | None, current_user_model.agency_id)
    is_owning_agent = (
        property_user_id == current_user.user_id
        and user_crud.is_agent(current_user_model)
    )
    is_agency_owner_for_listing = (
        user_crud.is_agency_owner(current_user_model)
        and property_agency_id is not None
        and property_agency_id == current_user_agency_id
    )

    if not is_admin and not is_owning_agent and not is_agency_owner_for_listing:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to verify this property"
        )

    requested_status = verification_in.resolved_moderation_status
    previous_status = str(getattr(property.moderation_status, "value", property.moderation_status))

    # Normalize publish target: treat both 'verified' and 'live' inputs as a
    # request to move the listing into the Phase M `live` state.
    is_publish = requested_status in {ModerationStatus.verified, ModerationStatus.live}
    target_status = ModerationStatus.live if is_publish else requested_status

    # Three-tier moderation: only admins can publish a listing, and they may
    # do so only from business-legal states. For backward compatibility we
    # allow:
    # - agency_approved (Phase L),
    # - admin_review (Phase M),
    # - verified/live (idempotent).
    if target_status == ModerationStatus.live:
        if not is_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only admins can verify listings",
            )
        allowed_from = {
            ModerationStatus.agency_approved.value,
            ModerationStatus.admin_review.value,
            ModerationStatus.verified.value,
            ModerationStatus.live.value,
        }
        if previous_status not in allowed_from:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Admin can only verify listings that have been approved by the agency or are under admin review",
            )

    if not is_admin and not is_agency_owner_for_listing and target_status in {ModerationStatus.rejected, ModerationStatus.revoked}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can reject or revoke property moderation",
        )

    updated_by_supabase_id: str = str(current_user.supabase_id)  # Normalize the authenticated UUID to the string audit format expected by the CRUD layer.
    is_published = target_status == ModerationStatus.live
    property = property_crud.verify_property(
        db=db,
        property_id=property_id,
        is_verified=is_published,
        moderation_status=target_status.value,
        moderation_reason=verification_in.moderation_reason,
        updated_by=updated_by_supabase_id,
        actor_user_id=current_user.user_id,
    )

    if property is not None:
        owner_user_id: int | None = typing_cast(int | None, property.user_id)
        property_id_value: int = typing_cast(int, property.property_id)
        if owner_user_id is not None:
            owner = user_crud.get(db, user_id=owner_user_id)
            owner_email = str(getattr(owner, "email", "") or "").strip() if owner is not None else ""
            if owner_email:
                dispatch_email_task(
                    send_property_moderation_email,
                    owner_email,
                    str(property.title),
                    target_status.value,
                    property_id_value,
                    verification_in.moderation_reason,
                )

        # Only send saved-search match emails the first time a listing becomes
        # publicly visible. Treat both legacy `verified` and new `live` as
        # published states, but only transition into `live` triggers matches.
        if target_status == ModerationStatus.live and previous_status not in {
            ModerationStatus.verified.value,
            ModerationStatus.live.value,
        }:
            notify_saved_search_matches_for_property(db, property_obj=property)

    return property


@router.patch("/{property_id}/submit-for-review", response_model=PropertyResponse)
def submit_property_for_review(
    *,
    db: Session = Depends(get_db),
    property_id: int,
    current_user: UserResponse = Depends(get_current_active_user),
    _: None = Depends(validate_request_size),
) -> Any:
    """Agent submits a draft listing for agency review (draft → agency_review)."""
    property = property_crud.get(db=db, property_id=property_id)

    if not property:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Property not found",
        )

    target_status = ModerationStatus.agency_review
    ensure_legal_moderation_transition(
        property_obj=property,
        target_status=target_status,
        current_user=current_user,
    )

    updated_by_supabase_id: str = str(current_user.supabase_id)
    property = property_crud.verify_property(
        db=db,
        property_id=property_id,
        is_verified=False,
        moderation_status=target_status.value,
        moderation_reason=None,
        updated_by=updated_by_supabase_id,
        actor_user_id=current_user.user_id,
    )

    if property is not None and property.agency_id is not None:
        agency = db.query(Agency).filter(Agency.agency_id == property.agency_id).first()
        if agency:
            agency_owner = (
                db.query(User)
                .filter(
                    User.agency_id == property.agency_id,
                    User.user_role == UserRole.AGENCY_OWNER,
                )
                .first()
            )
            if agency_owner is not None and typing_cast(Any, agency_owner).email:
                agent_name = f"{current_user.first_name} {current_user.last_name}".strip() or current_user.email or "An agent"
                from datetime import datetime, timezone
                submission_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
                dispatch_email_task(
                    send_submission_notification_email,
                    agency_owner.email,
                    agent_name,
                    str(property.title),
                    typing_cast(int, property.property_id),
                    submission_time,
                )

    return property


@router.patch("/{property_id}/submit-to-admin", response_model=PropertyResponse)
def submit_property_to_admin(
    *,
    db: Session = Depends(get_db),
    property_id: int,
    current_user: UserResponse = Depends(get_current_active_user),
    _: None = Depends(validate_request_size),
) -> Any:
    """Agency owner submits a draft listing directly to admin review (draft → admin_review)."""
    property = property_crud.get(db=db, property_id=property_id)

    if not property:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Property not found",
        )

    target_status = ModerationStatus.admin_review
    ensure_legal_moderation_transition(
        property_obj=property,
        target_status=target_status,
        current_user=current_user,
    )

    updated_by_supabase_id: str = str(current_user.supabase_id)
    property = property_crud.verify_property(
        db=db,
        property_id=property_id,
        is_verified=False,
        moderation_status=target_status.value,
        moderation_reason=None,
        updated_by=updated_by_supabase_id,
        actor_user_id=current_user.user_id,
    )

    return property


@router.patch("/{property_id}/agency-approve", response_model=PropertyResponse)
def agency_approve_property(
    *,
    db: Session = Depends(get_db),
    property_id: int,
    current_user: UserResponse = Depends(get_current_active_user),
    _: None = Depends(validate_request_size)
) -> Any:
    """Agency owner approves a listing for admin review (agency_review → admin_review)."""
    property = property_crud.get(db=db, property_id=property_id)

    if not property:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Property not found",
        )

    target_status = ModerationStatus.admin_review
    ensure_legal_moderation_transition(
        property_obj=property,
        target_status=target_status,
        current_user=current_user,
    )

    updated_by_supabase_id: str = str(current_user.supabase_id)
    property = property_crud.verify_property(
        db=db,
        property_id=property_id,
        is_verified=False,
        moderation_status=target_status.value,
        moderation_reason=None,
        updated_by=updated_by_supabase_id,
        actor_user_id=current_user.user_id,
    )

    if property is not None:
        admins = db.query(User).filter(User.user_role == UserRole.ADMIN).all()
        admin_emails = [u.email for u in admins if typing_cast(Any, u).email]
        if settings.ADMIN_NOTIFICATION_EMAIL:
            admin_emails = [settings.ADMIN_NOTIFICATION_EMAIL]

        agency_name = f"{current_user.first_name} {current_user.last_name}".strip() or "Your agency"
        for admin_email in admin_emails:
            dispatch_email_task(
                send_agency_approval_notification_email,
                admin_email,
                agency_name,
                str(property.title),
                typing_cast(int, property.property_id),
            )

    return property


@router.patch("/{property_id}/agency-reject", response_model=PropertyResponse)
def agency_reject_property(
    *,
    db: Session = Depends(get_db),
    property_id: int,
    action_in: PropertyAgencyActionUpdate,
    current_user: UserResponse = Depends(get_current_active_user),
    _: None = Depends(validate_request_size)
) -> Any:
    """Agency owner rejects a listing back to the agent (agency_review → agency_rejected)."""
    property = property_crud.get(db=db, property_id=property_id)

    if not property:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Property not found",
        )

    if not action_in.moderation_reason or not str(action_in.moderation_reason).strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="A moderation reason is required for rejection",
        )

    target_status = ModerationStatus.agency_rejected
    ensure_legal_moderation_transition(
        property_obj=property,
        target_status=target_status,
        current_user=current_user,
    )

    updated_by_supabase_id: str = str(current_user.supabase_id)
    property = property_crud.verify_property(
        db=db,
        property_id=property_id,
        is_verified=False,
        moderation_status=target_status.value,
        moderation_reason=action_in.moderation_reason,
        updated_by=updated_by_supabase_id,
        actor_user_id=current_user.user_id,
    )

    if property is not None:
        owner_user_id: int | None = typing_cast(int | None, property.user_id)
        property_id_value: int = typing_cast(int, property.property_id)
        if owner_user_id is not None:
            owner = user_crud.get(db, user_id=owner_user_id)
            owner_email = str(getattr(owner, "email", "") or "").strip() if owner is not None else ""
            if owner_email:
                dispatch_email_task(
                    send_property_moderation_email,
                    owner_email,
                    str(property.title),
                    target_status.value,
                    property_id_value,
                    action_in.moderation_reason,
                )

    return property


@router.patch("/{property_id}/withdraw", response_model=PropertyResponse)
def withdraw_property_from_review(
    *,
    db: Session = Depends(get_db),
    property_id: int,
    current_user: UserResponse = Depends(get_current_active_user),
    _: None = Depends(validate_request_size),
) -> Any:
    """Agent withdraws a listing from agency review (agency_review → draft)."""
    property = property_crud.get(db=db, property_id=property_id)

    if not property:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Property not found",
        )

    target_status = ModerationStatus.draft
    ensure_legal_moderation_transition(
        property_obj=property,
        target_status=target_status,
        current_user=current_user,
    )

    updated_by_supabase_id: str = str(current_user.supabase_id)
    property = property_crud.verify_property(
        db=db,
        property_id=property_id,
        is_verified=False,
        moderation_status=target_status.value,
        moderation_reason=None,
        updated_by=updated_by_supabase_id,
        actor_user_id=current_user.user_id,
    )

    return property


@router.patch("/{property_id}/resubmit", response_model=PropertyResponse)
def resubmit_property_after_agency_rejection(
    *,
    db: Session = Depends(get_db),
    property_id: int,
    current_user: UserResponse = Depends(get_current_active_user),
    _: None = Depends(validate_request_size),
) -> Any:
    """Agent resubmits a previously agency-rejected listing (agency_rejected → agency_review)."""
    property = property_crud.get(db=db, property_id=property_id)

    if not property:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Property not found",
        )

    target_status = ModerationStatus.agency_review
    ensure_legal_moderation_transition(
        property_obj=property,
        target_status=target_status,
        current_user=current_user,
    )

    updated_by_supabase_id: str = str(current_user.supabase_id)
    property = property_crud.verify_property(
        db=db,
        property_id=property_id,
        is_verified=False,
        moderation_status=target_status.value,
        moderation_reason=None,
        updated_by=updated_by_supabase_id,
        actor_user_id=current_user.user_id,
    )

    return property


@router.patch("/{property_id}/recall", response_model=PropertyResponse)
def recall_property_from_admin_review(
    *,
    db: Session = Depends(get_db),
    property_id: int,
    current_user: UserResponse = Depends(get_current_active_user),
    _: None = Depends(validate_request_size),
) -> Any:
    """Agency owner recalls a listing from admin review.

    - Own listing: admin_review → draft (bypass agency_review)
    - Agent's listing: admin_review → agency_review
    """
    property = property_crud.get(db=db, property_id=property_id)

    if not property:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Property not found",
        )

    property_user_id: int = typing_cast(int, property.user_id)
    if property_user_id == current_user.user_id:
        target_status = ModerationStatus.draft  # Own listing → draft
    else:
        target_status = ModerationStatus.agency_review  # Agent's listing → agency_review

    ensure_legal_moderation_transition(
        property_obj=property,
        target_status=target_status,
        current_user=current_user,
    )

    updated_by_supabase_id: str = str(current_user.supabase_id)
    property = property_crud.verify_property(
        db=db,
        property_id=property_id,
        is_verified=False,
        moderation_status=target_status.value,
        moderation_reason=None,
        updated_by=updated_by_supabase_id,
        actor_user_id=current_user.user_id,
    )

    return property


@router.patch("/{property_id}/admin-reject", response_model=PropertyResponse)
def admin_reject_property(
    *,
    db: Session = Depends(get_db),
    property_id: int,
    action_in: PropertyAgencyActionUpdate,
    current_user: UserResponse = Depends(get_current_active_user),
    _: None = Depends(validate_request_size),
) -> Any:
    """Admin rejects a listing from admin review (admin_review → admin_rejected)."""
    property = property_crud.get(db=db, property_id=property_id)

    if not property:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Property not found",
        )

    if not action_in.moderation_reason or not str(action_in.moderation_reason).strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="A moderation reason is required for rejection",
        )

    target_status = ModerationStatus.admin_rejected
    ensure_legal_moderation_transition(
        property_obj=property,
        target_status=target_status,
        current_user=current_user,
    )

    updated_by_supabase_id: str = str(current_user.supabase_id)
    property = property_crud.verify_property(
        db=db,
        property_id=property_id,
        is_verified=False,
        moderation_status=target_status.value,
        moderation_reason=action_in.moderation_reason,
        updated_by=updated_by_supabase_id,
        actor_user_id=current_user.user_id,
    )

    if property is not None:
        owner_user_id: int | None = typing_cast(int | None, property.user_id)
        property_id_value: int = typing_cast(int, property.property_id)
        if owner_user_id is not None:
            owner = user_crud.get(db, user_id=owner_user_id)
            owner_email = str(getattr(owner, "email", "") or "").strip() if owner is not None else ""
            if owner_email:
                dispatch_email_task(
                    send_property_moderation_email,
                    owner_email,
                    str(property.title),
                    target_status.value,
                    property_id_value,
                    action_in.moderation_reason,
                )

        # Concurrently notify the agency owner
        listing_agency_id: int | None = typing_cast(int | None, getattr(property, "agency_id", None))
        if listing_agency_id is not None:
            agency_owner = (
                db.query(User)
                .filter(
                    User.agency_id == listing_agency_id,
                    User.user_role == UserRole.AGENCY_OWNER,
                    User.deleted_at.is_(None),
                )
                .first()
            )
            agency_owner_email = str(getattr(agency_owner, "email", "") or "").strip() if agency_owner is not None else ""
            if agency_owner_email:
                dispatch_email_task(
                    send_property_moderation_email,
                    agency_owner_email,
                    str(property.title),
                    target_status.value,
                    property_id_value,
                    action_in.moderation_reason,
                )

    return property


@router.patch("/{property_id}/reinstate", response_model=PropertyResponse)
def reinstate_property_from_admin_rejected(
    *,
    db: Session = Depends(get_db),
    property_id: int,
    current_user: UserResponse = Depends(get_current_active_user),
    _: None = Depends(validate_request_size),
) -> Any:
    """Admin reinstates a listing to admin review (admin_rejected → admin_review)."""
    property = property_crud.get(db=db, property_id=property_id)

    if not property:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Property not found",
        )

    target_status = ModerationStatus.admin_review
    ensure_legal_moderation_transition(
        property_obj=property,
        target_status=target_status,
        current_user=current_user,
    )

    updated_by_supabase_id: str = str(current_user.supabase_id)
    property = property_crud.verify_property(
        db=db,
        property_id=property_id,
        is_verified=False,
        moderation_status=target_status.value,
        moderation_reason=None,
        updated_by=updated_by_supabase_id,
        actor_user_id=current_user.user_id,
    )

    return property


@router.patch("/{property_id}/revoke", response_model=PropertyResponse)
def revoke_property(
    *,
    db: Session = Depends(get_db),
    property_id: int,
    action_in: PropertyAgencyActionUpdate,
    current_user: UserResponse = Depends(get_current_active_user),
    _: None = Depends(validate_request_size),
) -> Any:
    """Admin revokes a live listing (live → revoked)."""
    property = property_crud.get(db=db, property_id=property_id)

    if not property:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Property not found",
        )

    if not action_in.moderation_reason or not str(action_in.moderation_reason).strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="A moderation reason is required for revocation",
        )

    target_status = ModerationStatus.revoked
    ensure_legal_moderation_transition(
        property_obj=property,
        target_status=target_status,
        current_user=current_user,
    )

    updated_by_supabase_id: str = str(current_user.supabase_id)
    property = property_crud.verify_property(
        db=db,
        property_id=property_id,
        is_verified=False,
        moderation_status=target_status.value,
        moderation_reason=action_in.moderation_reason,
        updated_by=updated_by_supabase_id,
        actor_user_id=current_user.user_id,
    )

    if property is not None:
        owner_user_id: int | None = typing_cast(int | None, property.user_id)
        property_id_value: int = typing_cast(int, property.property_id)
        if owner_user_id is not None:
            owner = user_crud.get(db, user_id=owner_user_id)
            owner_email = str(getattr(owner, "email", "") or "").strip() if owner is not None else ""
            if owner_email:
                dispatch_email_task(
                    send_property_moderation_email,
                    owner_email,
                    str(property.title),
                    target_status.value,
                    property_id_value,
                    action_in.moderation_reason,
                )

        # Concurrently notify the agency owner — it's their inventory and reputation.
        listing_agency_id: int | None = typing_cast(int | None, getattr(property, "agency_id", None))
        if listing_agency_id is not None:
            agency_owner = (
                db.query(User)
                .filter(
                    User.agency_id == listing_agency_id,
                    User.user_role == UserRole.AGENCY_OWNER,
                    User.deleted_at.is_(None),
                )
                .first()
            )
            agency_owner_email = str(getattr(agency_owner, "email", "") or "").strip() if agency_owner is not None else ""
            if agency_owner_email:
                dispatch_email_task(
                    send_property_moderation_email,
                    agency_owner_email,
                    str(property.title),
                    target_status.value,
                    property_id_value,
                    action_in.moderation_reason,
                )

    return property


@router.patch("/{property_id}/reject-permanent", response_model=PropertyResponse)
def reject_permanent(
    *,
    db: Session = Depends(get_db),
    property_id: int,
    action_in: PropertyAgencyActionUpdate,
    current_user: UserResponse = Depends(get_current_active_user),
    _: None = Depends(validate_request_size),
) -> Any:
    """Admin permanently rejects a revoked listing (revoked → admin_rejected).
    After this, the standard admin_rejected mediation rules apply:
    agency must instruct before agent can act."""
    property = property_crud.get(db=db, property_id=property_id)
    if not property:
        raise HTTPException(status_code=404, detail="Property not found")

    if not action_in.moderation_reason or not action_in.moderation_reason.strip():
        raise HTTPException(
            status_code=422,
            detail="A reason is required for permanent rejection"
        )

    target_status = ModerationStatus.admin_rejected
    ensure_legal_moderation_transition(
        property_obj=property,
        target_status=target_status,
        current_user=current_user,
    )

    updated_by_supabase_id: str = str(current_user.supabase_id)
    property = property_crud.verify_property(
        db=db,
        property_id=property_id,
        is_verified=False,
        moderation_status=target_status.value,
        moderation_reason=action_in.moderation_reason,
        updated_by=updated_by_supabase_id,
        actor_user_id=current_user.user_id,
    )

    return property


@router.patch("/{property_id}/restore", response_model=PropertyResponse)
def restore_property_from_revoked(
    *,
    db: Session = Depends(get_db),
    property_id: int,
    current_user: UserResponse = Depends(get_current_active_user),
    _: None = Depends(validate_request_size),
) -> Any:
    """Admin restores a revoked listing to live (revoked → live)."""
    property = property_crud.get(db=db, property_id=property_id)

    if not property:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Property not found",
        )

    target_status = ModerationStatus.live
    ensure_legal_moderation_transition(
        property_obj=property,
        target_status=target_status,
        current_user=current_user,
    )

    updated_by_supabase_id: str = str(current_user.supabase_id)
    # Restoring to live uses the same publish semantics as verify.
    property = property_crud.verify_property(
        db=db,
        property_id=property_id,
        is_verified=True,
        moderation_status=target_status.value,
        moderation_reason=None,
        updated_by=updated_by_supabase_id,
        actor_user_id=current_user.user_id,
    )

    if property is not None:
        owner_user_id: int | None = typing_cast(int | None, property.user_id)
        property_id_value: int = typing_cast(int, property.property_id)
        if owner_user_id is not None:
            owner = user_crud.get(db, user_id=owner_user_id)
            owner_email = str(getattr(owner, "email", "") or "").strip() if owner is not None else ""
            if owner_email:
                dispatch_email_task(
                    send_property_moderation_email,
                    owner_email,
                    str(property.title),
                    target_status.value,
                    property_id_value,
                    None,
                )

    return property


@router.patch("/{property_id}/pull-back", response_model=PropertyResponse)
def pull_back_property_to_draft(
    *,
    db: Session = Depends(get_db),
    property_id: int,
    current_user: UserResponse = Depends(get_current_active_user),
    _: None = Depends(validate_request_size),
) -> Any:
    """Agent pulls back a revoked or admin-rejected listing to draft.

    Legal transitions via the central guard:
    - revoked → draft
    - admin_rejected → draft
    """
    property = property_crud.get(db=db, property_id=property_id)

    if not property:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Property not found",
        )

    target_status = ModerationStatus.draft
    ensure_legal_moderation_transition(
        property_obj=property,
        target_status=target_status,
        current_user=current_user,
    )

    # Phase N N.1: instruction mediation gate — revoked/admin_rejected require agency instruction
    from app.services.listing_instruction_service import (
        check_instruction_gate,
        enrich_property_with_instruction_fields,
    )
    check_instruction_gate(db, property_obj=property)

    updated_by_supabase_id: str = str(current_user.supabase_id)
    property = property_crud.verify_property(
        db=db,
        property_id=property_id,
        is_verified=False,
        moderation_status=target_status.value,
        moderation_reason=None,
        updated_by=updated_by_supabase_id,
        actor_user_id=current_user.user_id,
    )

    if property is not None:
        enrich_property_with_instruction_fields(
            db,
            property_obj=property,
            current_user_id=current_user.user_id,
            current_user_role=getattr(current_user, "user_role", ""),
        )

    return property


@router.patch("/{property_id}/instruct", response_model=PropertyResponse)
def instruct_agent(
    *,
    db: Session = Depends(get_db),
    property_id: int,
    instruction_in: InstructionCreate,
    current_user: UserResponse = Depends(get_current_active_user),
    _: None = Depends(validate_request_size),
) -> Any:
    """Agency owner writes instruction to agent for a revoked/rejected listing.

    The instruction is tied to the most recent revocation/rejection event so that
    instructions from a prior lifecycle cycle do not unlock CTAs in a new cycle.
    """
    from app.services.listing_instruction_service import (
        get_most_relevant_rejection_event,
        write_instruction,
        enrich_property_with_instruction_fields,
    )

    property = property_crud.get(db=db, property_id=property_id)
    if not property:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Property not found",
        )

    current_user_model: User = typing_cast(User, current_user)
    if current_user.user_role != UserRole.AGENCY_OWNER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only agency owners can write instructions",
        )
    property_agency_id: int | None = typing_cast(int | None, property.agency_id)
    if property_agency_id is None or property_agency_id != current_user.agency_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not the owner of this listing's agency",
        )

    property_status = str(getattr(property.moderation_status, "value", property.moderation_status))
    if property_status not in ("revoked", "admin_rejected"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Can only instruct on revoked or admin_rejected listings",
        )

    most_recent_event = get_most_relevant_rejection_event(db, listing_id=property_id)
    if not most_recent_event:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No revocation or rejection event found for this listing",
        )

    event_id_val: int = int(typing_cast(Any, most_recent_event).event_id)
    write_instruction(
        db=db,
        listing_id=property_id,
        agency_id=property_agency_id,
        actor_id=typing_cast(int, current_user.user_id),
        triggered_by_event_id=event_id_val,
        instruction_text=instruction_in.instruction_text,
    )

    # Write a listing_events row (communication event, not a transition — status stays the same)
    property_crud._append_listing_event(
        db,
        property_obj=property,
        actor_user_id=typing_cast(int, current_user.user_id),
        from_status=property_status,
        to_status=property_status,
        reason="Agency instruction written",
    )

    db.flush()

    # Fire instruction notification to the listing agent
    if property.user_id is not None:
        agent = db.query(User).filter(User.user_id == property.user_id).first()
        if agent is not None and typing_cast(Any, agent).email:
            agency_owner_name = f"{current_user.first_name} {current_user.last_name}".strip() or "Your agency owner"
            dispatch_email_task(
                send_instruction_notification_email,
                agent.email,
                agency_owner_name,
                str(property.title),
                instruction_in.instruction_text,
                typing_cast(int, property.property_id),
            )

    # Enrich response with instruction fields (force since actor is agency_owner, not creator)
    enrich_property_with_instruction_fields(
        db,
        property_obj=property,
        current_user_id=typing_cast(int, current_user.user_id),
            current_user_role=current_user.user_role,
        force_has_instruction=True,
        force_instruction_text=instruction_in.instruction_text,
    )

    return property


@router.get("/{property_id}/instructions", response_model=List[ListingInstructionResponse])
def get_property_instructions(
    *,
    db: Session = Depends(get_db),
    property_id: int,
    current_user: UserResponse = Depends(get_current_active_user),
) -> Any:
    """Get all instructions for a listing, ordered by created_at ascending.

    Role gate: creator (own listing), agency_owner (own agency), admin (all).
    """
    from app.services.listing_instruction_service import get_listing_instructions

    property = property_crud.get(db=db, property_id=property_id)
    if not property:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Property not found",
        )

    current_user_model: User = typing_cast(User, current_user)
    is_creator = int(typing_cast(Any, property).user_id) == int(typing_cast(Any, current_user).user_id)
    property_agency_id: int | None = typing_cast(int | None, property.agency_id)
    current_user_agency_id: int | None = typing_cast(int | None, current_user_model.agency_id)
    is_agency_owner = (
        current_user.user_role == UserRole.AGENCY_OWNER
        and property_agency_id is not None
        and property_agency_id == current_user_agency_id
    )
    is_admin = current_user.user_role == UserRole.ADMIN

    if not is_creator and not is_agency_owner and not is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view instructions for this listing",
        )

    instructions = get_listing_instructions(db, listing_id=property_id)
    return instructions


@router.delete("/{property_id}", response_model=PropertyResponse)
def delete_property(
    *,
    db: Session = Depends(get_db),
    property_id: int,
    current_user: UserResponse = Depends(get_current_active_user)
) -> Any:
    """
    Soft delete a property.
    
    Permissions:
    - Owner can delete their own property
    - Admin can delete any property
    
    Sets deleted_at timestamp, preserves data for audit trail.
    """
    property = property_crud.get(db=db, property_id=property_id)
    
    if not property:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Property not found"
        )
    
    # Permission check: owner or admin
    current_user_model: User = typing_cast(User, current_user)  # Narrow the authenticated dependency result to the ORM-backed user type used by permission helpers.
    property_user_id: int = typing_cast(int, property.user_id)  # Narrow the ORM integer attribute to the runtime int carried on the loaded entity.
    if property_user_id != current_user.user_id and not user_crud.is_admin(current_user_model):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to delete this property"
        )
    
    # Soft delete with audit trail
    deleted_by_supabase_id: str = str(current_user.supabase_id)  # Normalize the authenticated UUID to the string audit format expected by the CRUD layer.
    property = property_crud.soft_delete(
        db=db, 
        property_id=property_id,
        deleted_by_supabase_id=deleted_by_supabase_id
    )
    
    return property


@router.get("/by-LocationResponse/{location_id}", response_model=List[PropertyResponse])
def read_properties_by_LocationResponse(
    location_id: int,
    db: Session = Depends(get_db),
    pagination: dict = Depends(pagination_params),
    current_user: Optional[UserResponse] = Depends(get_current_user_optional)
) -> Any:
    """
    Retrieve properties by LocationResponse ID.
    
    Respects same visibility rules as main property list.
    CRUD layer filters by deleted_at IS NULL.
    """
    # Apply visibility logic based on user role
    if current_user:
        current_user_model: User = typing_cast(User, current_user)  # Narrow the optional dependency result before calling ORM-oriented role helpers.
        if user_crud.is_admin(current_user_model):
            properties = property_crud.get_by_LocationResponse(
                db=db, 
                location_id=location_id, 
                **pagination,
            )
        elif user_crud.is_agent(current_user_model):
            properties = property_crud.get_by_location_for_agent(
                db=db,
                location_id=location_id,
                **pagination,
                agent_user_id=current_user.user_id
            )
        else:
            properties = property_crud.get_by_location_approved(
                db=db,
                location_id=location_id,
                **pagination,
            )
    else:
        properties = property_crud.get_by_location_approved(
            db=db,
            location_id=location_id,
            **pagination,
        )
    
    return properties


@router.get("/by-agent/{agent_user_id}", response_model=List[PropertyResponse])
def read_properties_by_agent(
    agent_user_id: int,
    db: Session = Depends(get_db),
    pagination: dict = Depends(pagination_params),
    current_user: Optional[UserResponse] = Depends(get_current_user_optional)
) -> Any:
    """
    Retrieve properties by agent/owner user_id.
    
    Public: Only approved properties by this agent
    Agent (self): All their own properties
    Admin: All properties by this agent
    """
    if current_user:
        current_user_model: User = typing_cast(User, current_user)  # Narrow the optional dependency result before calling ORM-oriented role helpers.
        if user_crud.is_admin(current_user_model) or current_user.user_id == agent_user_id:
            # Admin or self - see all properties by this agent
            properties = property_crud.get_by_owner(
                db=db, 
                user_id=agent_user_id,  # Explicit parameter name
                **pagination,
            )
        else:
            # Other users - only approved properties
            properties = property_crud.get_by_owner_approved(
                db=db,
                user_id=agent_user_id,
                **pagination,
            )
    else:
        # Anonymous - only approved
        properties = property_crud.get_by_owner_approved(
            db=db,
            user_id=agent_user_id,
            **pagination,
        )
    
    return properties


@router.get("/search/radius", response_model=List[PropertyResponse])
def search_properties_by_radius(
    latitude: float = Query(..., description="Center point latitude", ge=-90, le=90),
    longitude: float = Query(..., description="Center point longitude", ge=-180, le=180),
    radius: float = Query(..., description="Search radius in kilometers", gt=0, le=1000),
    db: Session = Depends(get_db),
    pagination: dict = Depends(pagination_params),
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    bedrooms: Optional[int] = None,
    bathrooms: Optional[float] = None,
    listing_type: Optional[ListingType] = None,
    listing_status: Optional[ListingStatus] = None,
    current_user: Optional[UserResponse] = Depends(get_current_user_optional)
) -> Any:
    """
    Search properties within a radius of a geographical point.
    
    Uses PostGIS ST_DWithin for efficient geography queries.
    Coordinates validated via Query constraints (ge/le).
    
    Visibility rules apply based on user role.
    CRUD layer converts lat/lon to WKT POINT for PostGIS.
    """
    min_price_value: Decimal | None = typing_cast(Decimal | None, min_price)  # Preserve FastAPI's runtime coercion while narrowing the filter input for pyright.
    max_price_value: Decimal | None = typing_cast(Decimal | None, max_price)  # Preserve FastAPI's runtime coercion while narrowing the filter input for pyright.
    bathrooms_value: int | None = typing_cast(int | None, bathrooms)  # Preserve the existing query value flow while matching the filter schema's integer field.
    listing_type_value: PropertyListingType | None = typing_cast(PropertyListingType | None, listing_type)  # Narrow the enum locally because model and schema enums share the same runtime values.
    listing_status_value: PropertyListingStatus | None = typing_cast(PropertyListingStatus | None, listing_status)  # Narrow the enum locally because model and schema enums share the same runtime values.
    search_params = PropertyFilter(
        min_price=min_price_value,
        max_price=max_price_value,
        bedrooms=bedrooms,
        bathrooms=bathrooms_value,
        listing_type=listing_type_value,
        listing_status=listing_status_value
    )
    
    # Apply visibility logic
    if current_user:
        current_user_model: User = typing_cast(User, current_user)  # Narrow the optional dependency result before calling ORM-oriented role helpers.
        if user_crud.is_admin(current_user_model):
            properties = property_crud.get_within_radius(
                db=db,
                latitude=latitude,
                longitude=longitude,
                radius=radius,
                **pagination,
                params=search_params
            )
        elif user_crud.is_agent(current_user_model):
            properties = property_crud.get_within_radius_for_agent(
                db=db,
                latitude=latitude,
                longitude=longitude,
                radius=radius,
                **pagination,
                params=search_params,
                agent_user_id=current_user.user_id
            )
        else:
            properties = property_crud.get_within_radius_approved(
                db=db,
                latitude=latitude,
                longitude=longitude,
                radius=radius,
                **pagination,
                params=search_params
            )
    else:
        properties = property_crud.get_within_radius_approved(
            db=db,
            latitude=latitude,
            longitude=longitude,
            radius=radius,
            **pagination,
            params=search_params
        )
    
    return properties
