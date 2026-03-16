from app.schemas.users import UserResponse
# app/api/endpoints/locations.py
"""
LocationResponse management endpoints - Canonical compliant
Handles geography data with PostGIS support, admin-only mutations, soft delete
"""
from typing import Any, List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

# --- DIRECT CRUD IMPORTS ---
from app.crud.locations import location as location_crud
from app.crud.users import user as user_crud

# --- DIRECT DEPENDENCY IMPORTS ---
from app.api.dependencies import (
    get_db,
    get_current_active_user,
    get_current_admin_user,
    validate_request_size
)

# --- DIRECT SCHEMA IMPORTS ---
from app.schemas.users import UserResponse
from app.schemas.locations import (
    LocationResponse,
    LocationCreate,
    LocationUpdate,
    LocationListResponse
)

router = APIRouter()


@router.get("/", response_model=List[LocationResponse])
def read_locations(
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
    state: str = None,
    city: str = None,
    neighborhood: str = None,
) -> Any:
    """
    Retrieve locations with optional filtering.
    
    Public endpoint - returns only non-deleted locations.
    CRUD layer enforces soft delete filtering (deleted_at IS NULL).
    """
    # Normalize filter strings to match DB CHECK constraints (lowercase, trimmed)
    if state:
        state = state.strip().lower()
    if city:
        city = city.strip().lower()
    if neighborhood:
        neighborhood = neighborhood.strip().lower()
    
    locations = location_crud.get_by_filters(
        db, 
        state=state, 
        city=city, 
        neighborhood=neighborhood, 
        skip=skip, 
        limit=limit
    )
    return locations


@router.post("/", response_model=LocationResponse, status_code=status.HTTP_201_CREATED)
def create_LocationResponse(
    *,
    db: Session = Depends(get_db),
    location_in: LocationCreate,
    current_user: UserResponse = Depends(get_current_admin_user),
    _: None = Depends(validate_request_size)
) -> Any:
    """
    Create new LocationResponse. Admin only.
    
    Validates geography coordinates if provided.
    CRUD layer converts lat/lon to PostGIS Geography(POINT, 4326).
    
    Audit: No created_by for locations per schema.
    """
    # Validate geography coordinates if present
    if hasattr(location_in, 'latitude') and location_in.latitude is not None:
        if not (-90 <= location_in.latitude <= 90):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Latitude must be between -90 and 90"
            )
    
    if hasattr(location_in, 'longitude') and location_in.longitude is not None:
        if not (-180 <= location_in.longitude <= 180):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Longitude must be between -180 and 180"
            )
    
    # Create with audit tracking
    LocationResponse = location_crud.create(
        db, 
        obj_in=location_in
    )
    
    return LocationResponse


@router.get("/states", response_model=List[str])
def read_states(
    db: Session = Depends(get_db),
) -> Any:
    """
    Get all unique states from non-deleted locations.
    
    Public endpoint for populating state dropdowns.
    """
    states = location_crud.get_states(db)
    return states


@router.get("/cities", response_model=List[str])
def read_cities(
    db: Session = Depends(get_db),
    state: str = None,
) -> Any:
    """
    Get all unique cities, optionally filtered by state.
    
    Public endpoint for populating city dropdowns (cascading from state).
    Only returns cities from non-deleted locations.
    """
    # Normalize state to match DB CHECK constraint
    if state:
        state = state.strip().lower()

    cities = location_crud.get_cities(db, state=state)
    return cities


@router.get("/neighborhoods", response_model=List[str])
def read_neighborhoods(
    db: Session = Depends(get_db),
    state: str = None,
    city: str = None,
) -> Any:
    """
    Get all unique neighborhoods, optionally filtered by state and/or city.
    
    Public endpoint for populating neighborhood dropdowns.
    Only returns neighborhoods from non-deleted locations.
    """
    # Normalize filters to match DB CHECK constraints
    if state:
        state = state.strip().lower()
    if city:
        city = city.strip().lower()

    neighborhoods = location_crud.get_neighborhoods(db, state=state, city=city)
    return neighborhoods


@router.get("/{location_id}", response_model=LocationResponse)
def read_LocationResponse(
    *,
    db: Session = Depends(get_db),
    location_id: int,
) -> Any:
    """
    Get LocationResponse by ID.
    
    Public endpoint - returns 404 if LocationResponse not found or soft-deleted.
    """
    LocationResponse = location_crud.get(db, location_id=location_id)
    
    if not LocationResponse:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="LocationResponse not found",
        )
    
    return LocationResponse


@router.put("/{location_id}", response_model=LocationResponse)
def update_LocationResponse(
    *,
    db: Session = Depends(get_db),
    location_id: int,
    location_in: LocationUpdate,
    current_user: UserResponse = Depends(get_current_admin_user),
    _: None = Depends(validate_request_size)
) -> Any:
    """
    Update a LocationResponse. Admin only.
    
    Validates geography coordinates if being updated.
    CRUD layer handles WKT conversion for PostGIS.
    
    Audit: Tracks updater via updated_by (Supabase UUID)
    """
    LocationResponse = location_crud.get(db, location_id=location_id)
    
    if not LocationResponse:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="LocationResponse not found",
        )
    
    # Validate geography if coordinates being updated
    if hasattr(location_in, 'latitude') and location_in.latitude is not None:
        if not (-90 <= location_in.latitude <= 90):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Latitude must be between -90 and 90"
            )
    
    if hasattr(location_in, 'longitude') and location_in.longitude is not None:
        if not (-180 <= location_in.longitude <= 180):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Longitude must be between -180 and 180"
            )
    
    # Update with audit tracking
    LocationResponse = location_crud.update(
        db, 
        db_obj=LocationResponse, 
        obj_in=location_in,
        updated_by=current_user.supabase_id  # UUID audit trail
    )
    
    return LocationResponse


@router.delete("/{location_id}", response_model=LocationResponse)
def delete_LocationResponse(
    *,
    db: Session = Depends(get_db),
    location_id: int,
    current_user: UserResponse = Depends(get_current_admin_user)
) -> Any:
    """
    Soft delete a LocationResponse. Admin only.
    
    Sets deleted_at timestamp, preserves data for audit trail.
    Consider: LocationResponse may have FK relationships with properties.
    
    Audit: Tracks who deleted via deleted_by (Supabase UUID)
    """
    LocationResponse = location_crud.get(db, location_id=location_id)
    
    if not LocationResponse:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="LocationResponse not found",
        )
    
    # Check if LocationResponse has active properties (optional business rule)
    # Prevent deletion of locations with properties:
    from app.crud.properties import property as property_crud
    active_properties = property_crud.count_by_LocationResponse(db, location_id=location_id)
    if active_properties > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot delete LocationResponse with {active_properties} active properties"
        )
    
    # Soft delete with audit trail
    LocationResponse = location_crud.soft_delete(
        db, 
        location_id=location_id,
        deleted_by_supabase_id=current_user.supabase_id
    )
    
    return LocationResponse


@router.get("/by-coordinates/", response_model=List[LocationResponse])
def read_locations_by_coordinates(
    *,
    db: Session = Depends(get_db),
    latitude: float = Query(..., description="Latitude coordinate", ge=-90, le=90),
    longitude: float = Query(..., description="Longitude coordinate", ge=-180, le=180),
    distance_km: float = Query(5.0, description="Search radius in kilometers", gt=0, le=1000),
    skip: int = 0,
    limit: int = 100
) -> Any:
    """
    Get locations within a certain radius of given coordinates.
    
    Uses PostGIS ST_DWithin for efficient geography queries.
    Coordinates validated via Query constraints (ge/le).
    
    Public endpoint - returns only non-deleted locations.
    CRUD layer converts lat/lon to WKT POINT for PostGIS comparison.
    """
    locations = location_crud.get_by_coordinates(
        db, 
        latitude=latitude, 
        longitude=longitude, 
        distance_km=distance_km,
        skip=skip,
        limit=limit
    )
    
    return locations
