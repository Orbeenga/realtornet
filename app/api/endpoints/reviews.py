from app.schemas.users import UserResponse
# app/api/endpoints/reviews.py
"""
Reviews management endpoints - Canonical compliant
Handles property and agent reviews with separate schemas, soft delete, and audit tracking
PARTIAL AUDIT TRAIL: reviews table has NO created_by, NO updated_by, but HAS deleted_by
"""
from typing import Any, List
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

# --- DIRECT CRUD IMPORTS ---
from app.crud.reviews import review as review_crud
from app.crud.properties import property as property_crud
from app.crud.users import user as user_crud

# --- DIRECT DEPENDENCY IMPORTS ---
from app.api.dependencies import (
    get_db,
    get_current_user,
    get_current_active_user,
    validate_request_size
)

# --- DIRECT SCHEMA IMPORTS (using aliases) ---
from app.schemas.users import UserResponse as UserResponse
from app.schemas.reviews import (
    PropertyReviewResponse,
    PropertyReviewCreate,
    PropertyReviewUpdate,
    AgentReviewResponse,
    AgentReviewCreate,
    AgentReviewUpdate
)

router = APIRouter()
logger = logging.getLogger(__name__)


# PROPERTY ReviewResponse ENDPOINTS

@router.post("/property/", response_model=PropertyReviewResponse, status_code=status.HTTP_201_CREATED)
def create_property_ReviewResponse(
    *,
    db: Session = Depends(get_db),
    review_in: PropertyReviewCreate,
    current_user: UserResponse = Depends(get_current_active_user),
    _: None = Depends(validate_request_size)
) -> Any:
    """
    Create a new property ReviewResponse.
    
    - Validates property exists
    - Prevents duplicate reviews (one per user per property)
    - Rating validation handled by schema
    
    Audit: Tracks reviewer via user_id FK (reviews table has no created_by column)
    """
    # Check if property exists
    property_obj = property_crud.get(db=db, property_id=review_in.property_id)
    if not property_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Property not found"
        )

    # Check if user has already reviewed this property
    existing_review = review_crud.get_property_review_by_user_and_property(
        db=db,
        user_id=current_user.user_id,
        property_id=review_in.property_id
    )
    if existing_review:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You have already reviewed this property"
        )

    # Create ReviewResponse with user association (no created_by per DB schema)
    review_obj = review_crud.create_property_ReviewResponse(
        db=db,
        obj_in=review_in,
        user_id=current_user.user_id
    )
    
    logger.info(
        "Property ReviewResponse created",
        extra={
            "review_id": review_obj.review_id,
            "property_id": review_in.property_id,
            "user_id": current_user.user_id,
            "rating": review_in.rating
        }
    )
    
    return review_obj


@router.get("/property/by-property/{property_id}", response_model=List[PropertyReviewResponse])
def read_reviews_by_property(
    *,
    db: Session = Depends(get_db),
    property_id: int,
    skip: int = 0,
    limit: int = 100,
) -> Any:
    """
    Retrieve all reviews for a specific property.
    
    Public endpoint - returns only non-deleted reviews.
    CRUD layer enforces deleted_at IS NULL filtering.
    """
    # Check if property exists
    property_obj = property_crud.get(db=db, property_id=property_id)
    if not property_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Property not found"
        )

    reviews = review_crud.get_property_reviews(
        db=db,
        property_id=property_id,
        skip=skip,
        limit=limit
    )
    return reviews


@router.get("/property/{review_id}", response_model=PropertyReviewResponse)
def read_property_ReviewResponse(
    *,
    db: Session = Depends(get_db),
    review_id: int,
) -> Any:
    """
    Get property ReviewResponse by ID.
    
    Public endpoint - anyone can read reviews.
    """
    review_obj = review_crud.get_property_ReviewResponse(db=db, review_id=review_id)
    if not review_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Property ReviewResponse not found"
        )
    return review_obj


@router.put("/property/{review_id}", response_model=PropertyReviewResponse)
def update_property_ReviewResponse(
    *,
    db: Session = Depends(get_db),
    review_id: int,
    review_in: PropertyReviewUpdate,
    current_user: UserResponse = Depends(get_current_active_user),
    _: None = Depends(validate_request_size)
) -> Any:
    """
    Update a property ReviewResponse.
    
    - Only ReviewResponse author or admin can update
    - Rating validation handled by schema
    
    Note: reviews table has no updated_by column per DB schema
    """
    review_obj = review_crud.get_property_ReviewResponse(db=db, review_id=review_id)
    if not review_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Property ReviewResponse not found"
        )

    # Check authorization: owner or admin
    if review_obj.user_id != current_user.user_id and not user_crud.is_admin(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to update this ReviewResponse"
        )

    # Update (no updated_by per DB schema)
    updated_review = review_crud.update_property_ReviewResponse(
        db=db,
        db_obj=review_obj,
        obj_in=review_in
    )
    
    logger.info(
        "Property ReviewResponse updated",
        extra={
            "review_id": review_id,
            "property_id": review_obj.property_id,
            "updated_by_user": current_user.user_id
        }
    )
    
    return updated_review


@router.delete("/property/{review_id}", response_model=PropertyReviewResponse)
def delete_property_ReviewResponse(
    *,
    db: Session = Depends(get_db),
    review_id: int,
    current_user: UserResponse = Depends(get_current_active_user)
) -> Any:
    """
    Soft delete a property ReviewResponse.
    
    - Only ReviewResponse author or admin can delete
    - Sets deleted_at timestamp
    
    Audit: Tracks who deleted via deleted_by (Supabase UUID)
    """
    review_obj = review_crud.get_property_ReviewResponse(db=db, review_id=review_id)
    if not review_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Property ReviewResponse not found"
        )

    # Check authorization: owner or admin
    if review_obj.user_id != current_user.user_id and not user_crud.is_admin(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to delete this ReviewResponse"
        )

    # Soft delete with audit trail
    deleted_review = review_crud.soft_delete_property_ReviewResponse(
        db=db,
        review_id=review_id,
        deleted_by_supabase_id=current_user.supabase_id
    )
    
    if not deleted_review:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Property ReviewResponse not found during delete attempt"
        )
    
    logger.warning(
        "Property ReviewResponse soft deleted",
        extra={
            "review_id": review_id,
            "property_id": deleted_review.property_id,
            "user_id": deleted_review.user_id,
            "deleted_by": current_user.supabase_id
        }
    )

    return deleted_review


# AGENT ReviewResponse ENDPOINTS

@router.post("/agent/", response_model=AgentReviewResponse, status_code=status.HTTP_201_CREATED)
def create_agent_ReviewResponse(
    *,
    db: Session = Depends(get_db),
    review_in: AgentReviewCreate,
    current_user: UserResponse = Depends(get_current_active_user),
    _: None = Depends(validate_request_size)
) -> Any:
    """
    Create a new agent ReviewResponse.
    
    - Validates agent exists
    - Prevents duplicate reviews (one per user per agent)
    - Rating validation handled by schema
    
    Audit: Tracks reviewer via user_id FK (reviews table has no created_by column)
    """
    # Ensure agent exists
    agent_obj = user_crud.get(db=db, user_id=review_in.agent_id)
    if not agent_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found"
        )
    
    # Verify the user is actually an agent
    if not user_crud.is_agent(agent_obj):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is not an agent"
        )

    # Check if user has already reviewed this agent
    existing_review = review_crud.get_agent_review_by_user_and_agent(
        db=db,
        user_id=current_user.user_id,
        agent_id=review_in.agent_id
    )
    if existing_review:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You have already reviewed this agent"
        )

    # Create ReviewResponse with user association (no created_by per DB schema)
    review_obj = review_crud.create_agent_ReviewResponse(
        db=db,
        obj_in=review_in,
        user_id=current_user.user_id
    )
    
    logger.info(
        "Agent ReviewResponse created",
        extra={
            "review_id": review_obj.review_id,
            "agent_id": review_in.agent_id,
            "user_id": current_user.user_id,
            "rating": review_in.rating
        }
    )
    
    return review_obj


@router.get("/agent/by-agent/{agent_id}", response_model=List[AgentReviewResponse])
def read_reviews_by_agent(
    *,
    db: Session = Depends(get_db),
    agent_id: int,
    skip: int = 0,
    limit: int = 100,
) -> Any:
    """
    Retrieve all reviews for a specific agent.
    
    Public endpoint - returns only non-deleted reviews.
    """
    # Verify agent exists
    agent_obj = user_crud.get(db=db, user_id=agent_id)
    if not agent_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found"
        )

    reviews = review_crud.get_agent_reviews(
        db=db,
        agent_id=agent_id,
        skip=skip,
        limit=limit
    )
    return reviews


@router.get("/agent/{review_id}", response_model=AgentReviewResponse)
def read_agent_ReviewResponse(
    *,
    db: Session = Depends(get_db),
    review_id: int,
) -> Any:
    """
    Get agent ReviewResponse by ID.
    
    Public endpoint - anyone can read reviews.
    """
    review_obj = review_crud.get_agent_ReviewResponse(db=db, review_id=review_id)
    if not review_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent ReviewResponse not found"
        )
    return review_obj


@router.put("/agent/{review_id}", response_model=AgentReviewResponse)
def update_agent_ReviewResponse(
    *,
    db: Session = Depends(get_db),
    review_id: int,
    review_in: AgentReviewUpdate,
    current_user: UserResponse = Depends(get_current_active_user),
    _: None = Depends(validate_request_size)
) -> Any:
    """
    Update an agent ReviewResponse.
    
    - Only ReviewResponse author or admin can update
    
    Note: reviews table has no updated_by column per DB schema
    """
    review_obj = review_crud.get_agent_ReviewResponse(db=db, review_id=review_id)
    if not review_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent ReviewResponse not found"
        )

    # Check authorization
    if review_obj.user_id != current_user.user_id and not user_crud.is_admin(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to update this ReviewResponse"
        )

    # Update (no updated_by per DB schema)
    updated_review = review_crud.update_agent_ReviewResponse(
        db=db,
        db_obj=review_obj,
        obj_in=review_in
    )
    
    logger.info(
        "Agent ReviewResponse updated",
        extra={
            "review_id": review_id,
            "agent_id": review_obj.agent_id,
            "updated_by_user": current_user.user_id
        }
    )
    
    return updated_review


@router.delete("/agent/{review_id}", response_model=AgentReviewResponse)
def delete_agent_ReviewResponse(
    *,
    db: Session = Depends(get_db),
    review_id: int,
    current_user: UserResponse = Depends(get_current_active_user)
) -> Any:
    """
    Soft delete an agent ReviewResponse.
    
    Audit: Tracks who deleted via deleted_by (Supabase UUID)
    """
    review_obj = review_crud.get_agent_ReviewResponse(db=db, review_id=review_id)
    if not review_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent ReviewResponse not found"
        )

    # Check authorization
    if review_obj.user_id != current_user.user_id and not user_crud.is_admin(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to delete this ReviewResponse"
        )

    # Soft delete with audit trail
    deleted_review = review_crud.soft_delete_agent_ReviewResponse(
        db=db,
        review_id=review_id,
        deleted_by_supabase_id=current_user.supabase_id
    )
    
    if not deleted_review:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent ReviewResponse not found during delete attempt"
        )
    
    logger.warning(
        "Agent ReviewResponse soft deleted",
        extra={
            "review_id": review_id,
            "agent_id": deleted_review.agent_id,
            "user_id": deleted_review.user_id,
            "deleted_by": current_user.supabase_id
        }
    )

    return deleted_review


# USER'S REVIEWS ENDPOINTS

@router.get("/by-user/property/", response_model=List[PropertyReviewResponse])
def read_user_property_reviews(
    db: Session = Depends(get_db),
    current_user: UserResponse = Depends(get_current_user),
    skip: int = 0,
    limit: int = 100,
) -> Any:
    """
    Retrieve property reviews by the current user.
    
    Returns only non-deleted reviews.
    """
    reviews = review_crud.get_property_reviews_by_user(
        db=db,
        user_id=current_user.user_id,
        skip=skip,
        limit=limit
    )
    return reviews


@router.get("/by-user/agent/", response_model=List[AgentReviewResponse])
def read_user_agent_reviews(
    db: Session = Depends(get_db),
    current_user: UserResponse = Depends(get_current_user),
    skip: int = 0,
    limit: int = 100,
) -> Any:
    """
    Retrieve agent reviews by the current user.
    
    Returns only non-deleted reviews.
    """
    reviews = review_crud.get_agent_reviews_by_user(
        db=db,
        user_id=current_user.user_id,
        skip=skip,
        limit=limit
    )
    return reviews
