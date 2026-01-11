#app/api/endpoints/property_amenities.py
"""
Property amenities management endpoints - Canonical compliant
Handles property-amenity associations (junction table) with ownership validation
"""
from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

# --- DIRECT CRUD IMPORTS ---
from app.crud.property_amenities import property_amenity as property_amenity_crud
from app.crud.properties import property as property_crud
from app.crud.amenities import amenity as amenity_crud
from app.crud.users import user as user_crud

# --- DIRECT DEPENDENCY IMPORTS ---
from app.api.dependencies import (
    get_db, 
    get_current_active_user, 
    validate_request_size
)

# --- DIRECT SCHEMA IMPORTS ---
from app.schemas.users import UserResponse
from app.schemas.amenities import Amenity
from app.schemas.property_amenities import (
    PropertyAmenity, 
    PropertyAmenityCreate, 
    PropertyAmenityBulkCreate
)

router = APIRouter()


@router.get("/property/{property_id}", response_model=List[Amenity])
def read_property_amenities(
    *,
    db: Session = Depends(get_db),
    property_id: int,
) -> Any:
    """
    Retrieve all amenities for a specific property.
    
    Public endpoint - anyone can view property amenities.
    Returns full amenity objects (not just IDs).
    """
    # Verify property exists
    db_property = property_crud.get(db, property_id=property_id)
    if not db_property:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Property not found"
        )
    
    amenities = property_amenity_crud.get_amenities_for_property(db, property_id=property_id)
    return amenities


@router.post("/", response_model=PropertyAmenity, status_code=status.HTTP_201_CREATED)
def add_amenity_to_property(
    *,
    db: Session = Depends(get_db),
    property_amenity_in: PropertyAmenityCreate,
    current_user: UserResponse = Depends(get_current_active_user),
    _: None = Depends(validate_request_size)
) -> Any:
    """
    Add an amenity to a property.
    
    Permissions:
    - Property owner can add amenities to their property
    - Admin can add amenities to any property

    Note: Junction table - no soft delete, no audit trail.
    """
    # Verify property exists
    db_property = property_crud.get(db, property_id=property_amenity_in.property_id)
    if not db_property:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Property not found"
        )
    
    # Check ownership: property owner or admin
    if db_property.user_id != current_user.user_id and not user_crud.is_admin(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to modify this property's amenities"
        )
    
    # Verify amenity exists
    amenity = amenity_crud.get(db, amenity_id=property_amenity_in.amenity_id)
    if not amenity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Amenity not found"
        )
    
    # Check if association already exists
    existing = property_amenity_crud.get(
        db, 
        property_id=property_amenity_in.property_id, 
        amenity_id=property_amenity_in.amenity_id
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This amenity is already associated with the property"
        )
    
    # Create association
    db_obj = property_amenity_crud.create(db, obj_in=property_amenity_in)
    return db_obj


@router.post("/bulk", response_model=List[PropertyAmenity], status_code=status.HTTP_201_CREATED)
def add_amenities_to_property_bulk(
    *,
    db: Session = Depends(get_db),
    bulk_in: PropertyAmenityBulkCreate,
    current_user: UserResponse = Depends(get_current_active_user),
    _: None = Depends(validate_request_size)
) -> Any:
    """
    Add multiple amenities to a property at once.

    Efficient bulk operation - validates ownership once.
    Skips amenities already associated with the property.
    
    Permissions: Property owner or admin.
    """
    # Verify property exists
    db_property = property_crud.get(db, property_id=bulk_in.property_id)
    if not db_property:
        raise HTTPException(status_code=404, detail="Property not found")
    
    # Check ownership
    if db_property.user_id != current_user.user_id and not user_crud.is_admin(current_user):
        raise HTTPException(status_code=403, detail="Not enough permissions")
    
    # Validate all amenities exist
    for amenity_id in bulk_in.amenity_ids:
        if not amenity_crud.get(db, amenity_id=amenity_id):
            raise HTTPException(status_code=404, detail=f"Amenity {amenity_id} not found")
    
    # Bulk create (CRUD handles duplicate detection)
    return property_amenity_crud.create_bulk(
        db, 
        property_id=bulk_in.property_id, 
        amenity_ids=bulk_in.amenity_ids
    )


@router.delete("/")
def remove_amenity_from_property(
    *,
    db: Session = Depends(get_db),
    property_id: int,
    amenity_id: int,
    current_user: UserResponse = Depends(get_current_active_user)
) -> Any:
    """
    Remove an amenity from a property.

     Hard delete - removes the association permanently.
    Junction tables typically don't use soft delete.
    
    Permissions: Property owner or admin.
    """
    # Verify property exists
    db_property = property_crud.get(db, property_id=property_id)
    if not db_property:
        raise HTTPException(status_code=404, detail="Property not found")
    
    # Check ownership
    if db_property.user_id != current_user.user_id and not user_crud.is_admin(current_user):
        raise HTTPException(status_code=403, detail="Not enough permissions")
    
    # Check if association exists
    existing = property_amenity_crud.get(db, property_id=property_id, amenity_id=amenity_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Association not found")
    
    # Hard delete (remove association)
    property_amenity_crud.remove(db, property_id=property_id, amenity_id=amenity_id)
    return {"message": "Amenity removed successfully"}


@router.delete("/bulk")
def remove_amenities_from_property_bulk(
    *,
    db: Session = Depends(get_db),
    bulk_in: PropertyAmenityBulkCreate,
    current_user: UserResponse = Depends(get_current_active_user)
) -> Any:
    """
    Remove multiple amenities from a property at once.

    Efficient bulk operation - hard deletes all associations.
    
    Permissions: Property owner or admin.
    """
    # Verify property exists
    db_property = property_crud.get(db, property_id=bulk_in.property_id)
    if not db_property:
        raise HTTPException(status_code=404, detail="Property not found")
    
    # Check ownership
    if db_property.user_id != current_user.user_id and not user_crud.is_admin(current_user):
        raise HTTPException(status_code=403, detail="Not enough permissions")
    
    # Bulk remove
    removed_count = property_amenity_crud.remove_bulk(
        db, 
        property_id=bulk_in.property_id, 
        amenity_ids=bulk_in.amenity_ids
    )
    return {"message": f"Removed {removed_count} amenities"}


@router.put("/property/{property_id}/sync", response_model=List[Amenity])
def sync_property_amenities(
    *,
    db: Session = Depends(get_db),
    property_id: int,
    amenity_ids: List[int],
    current_user: UserResponse = Depends(get_current_active_user),
    _: None = Depends(validate_request_size)
) -> Any:
    """
    Sync property amenities to exactly match the provided list.

    Removes amenities not in list, adds amenities not already associated.
    Useful for "save all" forms where user selects amenities from checkboxes.
    
    Permissions: Property owner or admin.
    """
    # Verify property exists
    db_property = property_crud.get(db, property_id=property_id)
    if not db_property:
        raise HTTPException(status_code=404, detail="Property not found")
    
    # Check ownership
    if db_property.user_id != current_user.user_id and not user_crud.is_admin(current_user):
        raise HTTPException(status_code=403, detail="Not enough permissions")
    
    # Validate all amenities exist
    for amenity_id in amenity_ids:
        if not amenity_crud.get(db, amenity_id=amenity_id):
            raise HTTPException(status_code=404, detail=f"Amenity {amenity_id} not found")
    
    # Sync operation (CRUD handles add/remove logic)
    property_amenity_crud.sync(db, property_id=property_id, amenity_ids=amenity_ids)

    # Return updated list
    return property_amenity_crud.get_amenities_for_property(db, property_id=property_id)