# app/api/endpoints/properties.py
"""
Property management endpoints - Canonical compliant
Handles property CRUD with geography, multi-tenant enforcement, and soft delete
"""
from typing import Any, List, Optional
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
    PropertyFilter
)

# --- DIRECT MODEL ENUM IMPORTS ---
from app.models.properties import ListingStatus, ListingType
from app.models.users import UserRole

router = APIRouter()


@router.get("/", response_model=List[PropertyResponse])
def read_properties(
    db: Session = Depends(get_db),
    pagination: dict = Depends(pagination_params),
    location_id: Optional[int] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    bedrooms: Optional[int] = None,
    bathrooms: Optional[float] = None,
    listing_type: Optional[ListingType] = None,
    listing_status: Optional[ListingStatus] = None,
    current_user: Optional[UserResponse] = Depends(get_current_user_optional)
) -> Any:
    """
    Retrieve properties with optional filtering.
    
    Public users: Only see approved, non-deleted properties
    Agents: See approved properties + their own (any status)
    Admins: See all properties
    
    CRUD layer enforces soft delete filtering (deleted_at IS NULL).
    """
    search_params = PropertyFilter(
        location_id=location_id,
        min_price=min_price,
        max_price=max_price,
        bedrooms=bedrooms,
        bathrooms=bathrooms,
        listing_type=listing_type,
        listing_status=listing_status
    )
    
    # Determine visibility based on user role
    if current_user:
        if user_crud.is_admin(current_user):
            # Admins see all properties
            properties = property_crud.get_multi_by_params(
                db, 
                **pagination, 
                params=search_params
            )
        elif user_crud.is_agent(current_user):
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
    # Check if user is allowed to create properties
    if not user_crud.is_agent_or_admin(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only agents and admins can create property listings"
        )
    
    # Multi-tenant enforcement: Agents can only create for their agency
    if user_crud.is_agent(current_user):
        if not current_user.agency_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Agent must belong to an agency to create properties"
            )
        
        # If property_in has agency_id, it must match agent's agency
        if hasattr(property_in, 'agency_id') and property_in.agency_id and property_in.agency_id != current_user.agency_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot create property for another agency"
            )
        
        # Auto-assign agent's agency if not specified
        if hasattr(property_in, 'agency_id') and not property_in.agency_id:
            property_in.agency_id = current_user.agency_id
    
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
    property = property_crud.create_with_owner(
        db=db, 
        obj_in=property_in, 
        user_id=current_user.user_id,  # Explicit FK reference
        created_by=current_user.supabase_id
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
        if user_crud.is_admin(current_user):
            # Admins can see any property
            return property
        elif property.user_id == current_user.user_id:
            # Owners can see their own properties
            return property
        elif property.is_verified:
            # Anyone can see verified properties
            return property
        else:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not enough permissions to view this property"
            )
    else:
        # Anonymous users can only see verified
        if property.is_verified:
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
    if property.user_id != current_user.user_id and not user_crud.is_admin(current_user):
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
    property = property_crud.update(
        db=db,
        db_obj=property,
        obj_in=property_in,
        updated_by_supabase_id=current_user.supabase_id  # UUID audit trail
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
    if property.user_id != current_user.user_id and not user_crud.is_admin(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to delete this property"
        )
    
    # Soft delete with audit trail
    property = property_crud.soft_delete(
        db=db, 
        property_id=property_id,
        deleted_by_supabase_id=current_user.supabase_id
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
        if user_crud.is_admin(current_user):
            properties = property_crud.get_by_LocationResponse(
                db=db, 
                location_id=location_id, 
                **pagination,
            )
        elif user_crud.is_agent(current_user):
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
        if user_crud.is_admin(current_user) or current_user.user_id == agent_user_id:
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
    search_params = PropertyFilter(
        min_price=min_price,
        max_price=max_price,
        bedrooms=bedrooms,
        bathrooms=bathrooms,
        listing_type=listing_type,
        listing_status=listing_status
    )
    
    # Apply visibility logic
    if current_user:
        if user_crud.is_admin(current_user):
            properties = property_crud.get_within_radius(
                db=db,
                latitude=latitude,
                longitude=longitude,
                radius=radius,
                **pagination,
                params=search_params
            )
        elif user_crud.is_agent(current_user):
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
