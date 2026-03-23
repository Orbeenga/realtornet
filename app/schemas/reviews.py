# app/schemas/reviews.py
"""
Pydantic schemas for Review model.
Follows BaseSchema/CreateSchema/UpdateSchema pattern.
DB-controlled fields (review_id, timestamps) excluded from Create/Update.
"""

from pydantic import BaseModel, Field, ConfigDict, field_validator
from typing import Optional
from datetime import datetime
from uuid import UUID


# Base Schema (shared fields for responses)
class ReviewBase(BaseModel):
    """Shared review fields"""
    rating: int = Field(..., ge=1, le=5)
    comment: Optional[str] = None

    @field_validator('comment')
    @classmethod
    def validate_comment(cls, v: Optional[str]) -> Optional[str]:
        """Ensure comment is not empty if provided"""
        if v is not None and not v.strip():
            return None
        return v.strip() if v else None


# Create Schema - Property Review
class PropertyReviewCreate(ReviewBase):
    """Schema for creating a property review"""
    property_id: int  # Required
    # user_id set by current_user in endpoint


# Create Schema - Agent Review
class AgentReviewCreate(ReviewBase):
    """Schema for creating an agent review"""
    agent_id: int  # Required
    # user_id set by current_user in endpoint


# Update Schema (for PATCH/PUT requests - all fields optional)
class ReviewUpdate(BaseModel):
    """Schema for updating a review"""
    rating: Optional[int] = Field(None, ge=1, le=5)
    comment: Optional[str] = None

    @field_validator('comment')
    @classmethod
    def validate_comment(cls, v: Optional[str]) -> Optional[str]:
        """Ensure comment is not empty if provided"""
        if v is not None and not v.strip():
            return None
        return v.strip() if v else None


# Response Schema - Base
class ReviewResponse(ReviewBase):
    """Schema for review responses (includes DB-generated fields)"""
    review_id: int  # Matches DB column name exactly
    user_id: Optional[int] = None
    property_id: Optional[int] = None
    agent_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None
    deleted_by: Optional[UUID] = None

    model_config = ConfigDict(from_attributes=True)


# Response Schema - Property Review
class PropertyReviewResponse(ReviewResponse):
    """Response for property reviews"""
    property_id: int  # Required for property reviews


# Response Schema - Agent Review
class AgentReviewResponse(ReviewResponse):
    """Response for agent reviews"""
    agent_id: int  # Required for agent reviews


# Extended Response (with nested user/property/agent data)
class ReviewExtendedResponse(ReviewResponse):
    """Extended response with related data"""
    user: Optional[dict] = None  # Can be replaced with UserResponse
    property: Optional[dict] = None  # For property reviews
    agent: Optional[dict] = None  # For agent reviews

    model_config = ConfigDict(from_attributes=True)


# List Response Schema (for paginated lists)
class ReviewListResponse(BaseModel):
    """Schema for paginated review lists"""
    reviews: list[ReviewResponse]
    total: int
    page: int
    page_size: int

    model_config = ConfigDict(from_attributes=True)


# Filter Schema (for filtering reviews)
class ReviewFilter(BaseModel):
    """Schema for filtering reviews"""
    user_id: Optional[int] = None
    property_id: Optional[int] = None
    agent_id: Optional[int] = None
    min_rating: Optional[int] = Field(None, ge=1, le=5)
    max_rating: Optional[int] = Field(None, ge=1, le=5)
    include_deleted: bool = False

# Aliases for backward compatibility
PropertyReviewUpdate = ReviewUpdate
AgentReviewUpdate = ReviewUpdate
ReviewCreate = PropertyReviewCreate
