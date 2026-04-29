# app/api/endpoints/properties.py
"""
Property management endpoints - Canonical compliant
Handles property CRUD with geography, multi-tenant enforcement, and soft delete
"""
from decimal import Decimal  # Narrow float query inputs to the Decimal-compatible type expected by the filter schema.
from typing import Any, List, Optional, cast as typing_cast  # Alias typing.cast so endpoint-local narrowing never shadows SQLAlchemy helpers elsewhere.
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

# --- DIRECT CRUD IMPORTS ---
from app.crud.properties import property as property_crud
from app.crud.users import user as user_crud

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
    PropertyFilter,
    ListingStatus as PropertyListingStatus,
    ListingType as PropertyListingType,
    ModerationStatus,
)

# --- DIRECT MODEL ENUM IMPORTS ---
from app.models.properties import ListingStatus, ListingType, ModerationStatus as PropertyModerationStatus
from app.models.users import User

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
    
    # Create property with owner tracking
    created_by_supabase_id: str = str(current_user.supabase_id)  # Normalize the authenticated UUID to the string audit format expected by the CRUD layer.
    property = property_crud.create_with_owner(
        db=db, 
        obj_in=property_in, 
        user_id=current_user.user_id,  # Explicit FK reference
        created_by=created_by_supabase_id
    )
    
    return property


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
    
    # Visibility check
    if current_user:
        current_user_model: User = typing_cast(User, current_user)  # Narrow the optional dependency result before calling ORM-oriented role helpers.
        property_user_id: int = typing_cast(int, property.user_id)  # Narrow the ORM integer attribute to the runtime int carried on the loaded entity.
        property_status = getattr(
            typing_cast(Any, property).moderation_status,
            "value",
            typing_cast(Any, property).moderation_status,
        )
        property_is_verified: bool = (
            property_status == PropertyModerationStatus.verified.value
            or typing_cast(bool, property.is_verified)
        )
        if user_crud.is_admin(current_user_model):
            # Admins can see any property
            return property
        elif property_user_id == current_user.user_id:
            # Owners can see their own properties
            return property
        elif property_is_verified:
            # Anyone can see verified properties
            return property
        else:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not enough permissions to view this property"
            )
    else:
        # Anonymous users can only see verified
        property_status = getattr(
            typing_cast(Any, property).moderation_status,
            "value",
            typing_cast(Any, property).moderation_status,
        )
        property_is_verified: bool = (
            property_status == PropertyModerationStatus.verified.value
            or typing_cast(bool, property.is_verified)
        )
        if property_is_verified:
            return property
        else:
            # Intentional 404 instead of 403 - prevents property ID enumeration
            # by anonymous users (security obfuscation)
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Property not found"
            )


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
    
    # Update with audit tracking
    updated_by_supabase_id: str = str(current_user.supabase_id)  # Normalize the authenticated UUID to the string audit format expected by the CRUD layer.
    property = property_crud.update(
        db=db,
        db_obj=property,
        obj_in=property_in,
        updated_by_supabase_id=updated_by_supabase_id
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

    Permissions:
    - Admins can set any moderation status
    - The owning agent can verify or return their own listing to pending review

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
    is_agent_owner = (
        property_user_id == current_user.user_id
        and user_crud.is_agent(current_user_model)
    )

    if not is_admin and not is_agent_owner:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to verify this property"
        )

    requested_status = verification_in.resolved_moderation_status
    if not is_admin and requested_status in {ModerationStatus.rejected, ModerationStatus.revoked}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can reject or revoke property moderation",
        )

    updated_by_supabase_id: str = str(current_user.supabase_id)  # Normalize the authenticated UUID to the string audit format expected by the CRUD layer.
    property = property_crud.verify_property(
        db=db,
        property_id=property_id,
        is_verified=requested_status == ModerationStatus.verified,
        moderation_status=requested_status.value,
        moderation_reason=verification_in.moderation_reason,
        updated_by=updated_by_supabase_id
    )

    return property


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
