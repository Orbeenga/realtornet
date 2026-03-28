# app/api/endpoints/property_types.py
"""
Property types management endpoints - Canonical compliant
Handles property type lookup data with admin-only mutations and hard delete
"""
from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

# --- DIRECT DEPENDENCY IMPORTS ---
# Highlighting: Directly importing required security and DB dependencies
from app.api.dependencies import (
    get_db, 
    get_current_admin_user, 
    validate_request_size,
    pagination_params,
)

# --- DIRECT CRUD IMPORTS ---
# Highlighting: Using explicit imports to avoid module-level circular logic
from app.crud.property_types import property_type as property_type_crud
from app.crud.properties import property as property_crud

# --- DIRECT SCHEMA & MODEL IMPORTS ---
from app.schemas.users import UserResponse
from app.schemas.property_types import PropertyTypeResponse, PropertyTypeCreate, PropertyTypeUpdate

router = APIRouter()

@router.get("/", response_model=List[PropertyTypeResponse])
def read_property_types(
    db: Session = Depends(get_db), # Updated: Direct dependency call
    pagination: dict = Depends(pagination_params),
) -> Any:
    """
    Retrieve property types.
    """
    # Updated: Using property_type_crud alias
    property_types = property_type_crud.get_multi(db, **pagination,)
    return property_types

@router.get("/{property_type_id}", response_model=PropertyTypeResponse)
def read_property_type(
    *,
    db: Session = Depends(get_db), # Updated: Direct dependency call
    property_type_id: int,
) -> Any:
    """
    Get property type by ID.
    """
    # Updated: Using property_type_crud alias
    property_type = property_type_crud.get(db, property_type_id=property_type_id)
    
    if not property_type:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Property type not found"
        )
    
    return property_type

@router.post("/", response_model=PropertyTypeResponse, status_code=status.HTTP_201_CREATED)
def create_property_type(
    *,
    db: Session = Depends(get_db), # Updated: Direct dependency call
    property_type_in: PropertyTypeCreate,
    current_user: UserResponse = Depends(get_current_admin_user), # Updated: Direct dependency call
    _: None = Depends(validate_request_size) # Updated: Direct dependency call
) -> Any:
    """
    Create new property type. Admin only. No Audit (Table Limitation).
    """
    # Updated: Using property_type_crud alias
    existing_type = property_type_crud.get_by_name(db, name=property_type_in.name)
    
    if existing_type:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Property type with this name already exists"
        )
    
    # Updated: Using property_type_crud alias
    property_type = property_type_crud.create(db, obj_in=property_type_in)
    
    return property_type

@router.put("/{property_type_id}", response_model=PropertyTypeResponse)
def update_property_type(
    *,
    db: Session = Depends(get_db), # Updated: Direct dependency call
    property_type_id: int,
    property_type_in: PropertyTypeUpdate,
    current_user: UserResponse = Depends(get_current_admin_user), # Updated: Direct dependency call
    _: None = Depends(validate_request_size) # Updated: Direct dependency call
) -> Any:
    """
    Update a property type. Admin only. No Audit (Table Limitation).
    """
    # Updated: Using property_type_crud alias
    property_type = property_type_crud.get(db, property_type_id=property_type_id)
    
    if not property_type:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Property type not found"
        )
    
    if property_type_in.name and property_type_in.name != property_type.name:
        # Updated: Using property_type_crud alias
        existing_type = property_type_crud.get_by_name(db, name=property_type_in.name)
        if existing_type:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Property type with this name already exists"
            )
    
    # Updated: Using property_type_crud alias
    property_type = property_type_crud.update(db, db_obj=property_type, obj_in=property_type_in)
    
    return property_type

@router.delete("/{property_type_id}")
def delete_property_type(
    *,
    db: Session = Depends(get_db), # Updated: Direct dependency call
    property_type_id: int,
    current_user: UserResponse = Depends(get_current_admin_user) # Updated: Direct dependency call
) -> Any:
    """
    Hard delete a property type. Admin only.
    """
    # Updated: Using property_type_crud alias
    property_type = property_type_crud.get(db, property_type_id=property_type_id)
    
    if not property_type:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Property type not found"
        )
    
    # Updated: Using property_crud alias to check usage
    properties_count = property_crud.count_by_type(
        db,
        property_type_id=property_type_id,
        include_deleted=True
    )
    if properties_count > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete property type that is in use by existing properties."
        )
    
    # Updated: Using property_type_crud alias
    property_type_crud.remove(db, property_type_id=property_type_id)
    
    return {"message": "Property type deleted successfully"}

@router.get("/stats/usage")
def get_property_type_usage(
    db: Session = Depends(get_db), # Updated: Direct dependency call
    current_user: UserResponse = Depends(get_current_admin_user) # Updated: Direct dependency call
) -> Any:
    """
    Get usage statistics for property types. Admin only.
    """
    # Updated: Using property_type_crud alias
    stats = property_type_crud.get_usage_stats(db)
    return stats
