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
from app.schemas.users import User
from app.schemas.reviews import (
    PropertyReview,
    PropertyReviewCreate,
    PropertyReviewUpdate,
    AgentReview,
    AgentReviewCreate,
    AgentReviewUpdate
)

router = APIRouter()
logger = logging.getLogger(__name__)


# PROPERTY REVIEW ENDPOINTS

@router.post("/property/", response_model=PropertyReview, status_code=status.HTTP_201_CREATED)
def create_property_review(
    *,
    db: Session = Depends(get_db),
    review_in: PropertyReviewCreate,
    current_user: User = Depends(get_current_active_user),
    _: None = Depends(validate_request_size)
) -> Any:
    """
    Create a new property review.
    
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

    # Create review with user association (no created_by per DB schema)
    review = review_crud.create_property_review(
        db=db,
        obj_in=review_in,
        user_id=current_user.user_id
    )
    
    logger.info(
        "Property review created",
        extra={
            "review_id": review.review_id,
            "property_id": review_in.property_id,
            "user_id": current_user.user_id,
            "rating": review_in.rating
        }
    )
    
    return review


@router.get("/property/by-property/{property_id}", response_model=List[PropertyReview])
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


@router.get("/property/{review_id}", response_model=PropertyReview)
def read_property_review(
    *,
    db: Session = Depends(get_db),
    review_id: int,
) -> Any:
    """
    Get property review by ID.
    
    Public endpoint - anyone can read reviews.
    """
    review = review_crud.get_property_review(db=db, review_id=review_id)
    if not review:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Property review not found"
        )
    return review


@router.put("/property/{review_id}", response_model=PropertyReview)
def update_property_review(
    *,
    db: Session = Depends(get_db),
    review_id: int,
    review_in: PropertyReviewUpdate,
    current_user: User = Depends(get_current_active_user),
    _: None = Depends(validate_request_size)
) -> Any:
    """
    Update a property review.
    
    - Only review author or admin can update
    - Rating validation handled by schema
    
    Note: reviews table has no updated_by column per DB schema
    """
    review = review_crud.get_property_review(db=db, review_id=review_id)
    if not review:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Property review not found"
        )

    # Check authorization: owner or admin
    if review.user_id != current_user.user_id and not user_crud.is_admin(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to update this review"
        )

    # Update (no updated_by per DB schema)
    updated_review = review_crud.update_property_review(
        db=db,
        db_obj=review,
        obj_in=review_in
    )
    
    logger.info(
        "Property review updated",
        extra={
            "review_id": review_id,
            "property_id": review.property_id,
            "updated_by_user": current_user.user_id
        }
    )
    
    return updated_review


@router.delete("/property/{review_id}", response_model=PropertyReview)
def delete_property_review(
    *,
    db: Session = Depends(get_db),
    review_id: int,
    current_user: User = Depends(get_current_active_user)
) -> Any:
    """
    Soft delete a property review.
    
    - Only review author or admin can delete
    - Sets deleted_at timestamp
    
    Audit: Tracks who deleted via deleted_by (Supabase UUID)
    """
    review = review_crud.get_property_review(db=db, review_id=review_id)
    if not review:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Property review not found"
        )

    # Check authorization: owner or admin
    if review.user_id != current_user.user_id and not user_crud.is_admin(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to delete this review"
        )

    # Soft delete with audit trail
    deleted_review = review_crud.soft_delete_property_review(
        db=db,
        review_id=review_id,
        deleted_by_supabase_id=current_user.supabase_id
    )
    
    if not deleted_review:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Property review not found during delete attempt"
        )
    
    logger.warning(
        "Property review soft deleted",
        extra={
            "review_id": review_id,
            "property_id": deleted_review.property_id,
            "user_id": deleted_review.user_id,
            "deleted_by": current_user.supabase_id
        }
    )

    return deleted_review


# AGENT REVIEW ENDPOINTS

@router.post("/agent/", response_model=AgentReview, status_code=status.HTTP_201_CREATED)
def create_agent_review(
    *,
    db: Session = Depends(get_db),
    review_in: AgentReviewCreate,
    current_user: User = Depends(get_current_active_user),
    _: None = Depends(validate_request_size)
) -> Any:
    """
    Create a new agent review.
    
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

    # Create review with user association (no created_by per DB schema)
    review = review_crud.create_agent_review(
        db=db,
        obj_in=review_in,
        user_id=current_user.user_id
    )
    
    logger.info(
        "Agent review created",
        extra={
            "review_id": review.review_id,
            "agent_id": review_in.agent_id,
            "user_id": current_user.user_id,
            "rating": review_in.rating
        }
    )
    
    return review


@router.get("/agent/by-agent/{agent_id}", response_model=List[AgentReview])
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


@router.get("/agent/{review_id}", response_model=AgentReview)
def read_agent_review(
    *,
    db: Session = Depends(get_db),
    review_id: int,
) -> Any:
    """
    Get agent review by ID.
    
    Public endpoint - anyone can read reviews.
    """
    review = review_crud.get_agent_review(db=db, review_id=review_id)
    if not review:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent review not found"
        )
    return review


@router.put("/agent/{review_id}", response_model=AgentReview)
def update_agent_review(
    *,
    db: Session = Depends(get_db),
    review_id: int,
    review_in: AgentReviewUpdate,
    current_user: User = Depends(get_current_active_user),
    _: None = Depends(validate_request_size)
) -> Any:
    """
    Update an agent review.
    
    - Only review author or admin can update
    
    Note: reviews table has no updated_by column per DB schema
    """
    review = review_crud.get_agent_review(db=db, review_id=review_id)
    if not review:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent review not found"
        )

    # Check authorization
    if review.user_id != current_user.user_id and not user_crud.is_admin(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to update this review"
        )

    # Update (no updated_by per DB schema)
    updated_review = review_crud.update_agent_review(
        db=db,
        db_obj=review,
        obj_in=review_in
    )
    
    logger.info(
        "Agent review updated",
        extra={
            "review_id": review_id,
            "agent_id": review.agent_id,
            "updated_by_user": current_user.user_id
        }
    )
    
    return updated_review


@router.delete("/agent/{review_id}", response_model=AgentReview)
def delete_agent_review(
    *,
    db: Session = Depends(get_db),
    review_id: int,
    current_user: User = Depends(get_current_active_user)
) -> Any:
    """
    Soft delete an agent review.
    
    Audit: Tracks who deleted via deleted_by (Supabase UUID)
    """
    review = review_crud.get_agent_review(db=db, review_id=review_id)
    if not review:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent review not found"
        )

    # Check authorization
    if review.user_id != current_user.user_id and not user_crud.is_admin(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to delete this review"
        )

    # Soft delete with audit trail
    deleted_review = review_crud.soft_delete_agent_review(
        db=db,
        review_id=review_id,
        deleted_by_supabase_id=current_user.supabase_id
    )
    
    if not deleted_review:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent review not found during delete attempt"
        )
    
    logger.warning(
        "Agent review soft deleted",
        extra={
            "review_id": review_id,
            "agent_id": deleted_review.agent_id,
            "user_id": deleted_review.user_id,
            "deleted_by": current_user.supabase_id
        }
    )

    return deleted_review


# USER'S REVIEWS ENDPOINTS

@router.get("/by-user/property/", response_model=List[PropertyReview])
def read_user_property_reviews(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
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


@router.get("/by-user/agent/", response_model=List[AgentReview])
def read_user_agent_reviews(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
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