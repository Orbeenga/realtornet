# app/schemas/inquiries.py
"""
Pydantic schemas for Inquiry model.
Follows BaseSchema/CreateSchema/UpdateSchema pattern.
DB-controlled fields (id, timestamps) excluded from Create/Update.
"""

from pydantic import BaseModel, ConfigDict, field_validator
from typing import Optional
from datetime import datetime
from enum import Enum


# Enum matching DB CHECK constraint
class InquiryStatus(str, Enum):
    """Inquiry status enum - matches DB CHECK constraint"""
    NEW = "new"
    VIEWED = "viewed"
    RESPONDED = "responded"


# Base Schema (shared fields for responses)
class InquiryBase(BaseModel):
    """Shared inquiry fields"""
    property_id: Optional[int] = None
    message: Optional[str] = None

    @field_validator('message')
    @classmethod
    def validate_message(cls, v: Optional[str]) -> Optional[str]:
        """Ensure message is not empty if provided"""
        if v is not None and not v.strip():
            return None
        return v.strip() if v else None


# Create Schema (for POST requests - excludes DB-controlled fields)
class InquiryCreate(InquiryBase):
    """Schema for creating a new inquiry"""
    property_id: int  # Required
    message: str  # Required
    # user_id typically set by current_user in endpoint

    @field_validator('message')
    @classmethod
    def validate_message_required(cls, v: str) -> str:
        """Ensure message is not empty"""
        if not v or not v.strip():
            raise ValueError('message cannot be empty')
        return v.strip()


# Update Schema (for PATCH/PUT requests - all fields optional)
class InquiryUpdate(BaseModel):
    """Schema for updating an inquiry"""
    message: Optional[str] = None
    inquiry_status: Optional[InquiryStatus] = None

    @field_validator('message')
    @classmethod
    def validate_message(cls, v: Optional[str]) -> Optional[str]:
        """Ensure message is not empty if provided"""
        if v is not None and not v.strip():
            raise ValueError('message cannot be empty')
        return v.strip() if v else None


# Response Schema (includes DB-controlled fields)
class InquiryResponse(InquiryBase):
    """Schema for inquiry responses (includes DB-generated fields)"""
    inquiry_id: int  # Matches DB column name exactly
    user_id: Optional[int] = None
    inquiry_status: str
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# Extended Response (with nested user/property data)
class InquiryExtendedResponse(InquiryResponse):
    """Extended response with related data"""
    user: Optional[dict] = None  # Can be replaced with UserResponse
    property: Optional[dict] = None  # Can be replaced with PropertyResponse

    model_config = ConfigDict(from_attributes=True)


# List Response Schema (for paginated lists)
class InquiryListResponse(BaseModel):
    """Schema for paginated inquiry lists"""
    inquiries: list[InquiryResponse]
    total: int
    page: int
    page_size: int

    model_config = ConfigDict(from_attributes=True)


# Filter Schema (for filtering inquiries)
class InquiryFilter(BaseModel):
    """Schema for filtering inquiries"""
    user_id: Optional[int] = None
    property_id: Optional[int] = None
    inquiry_status: Optional[InquiryStatus] = None
    include_deleted: bool = False

# Alias for convenience
Inquiry = InquiryResponse