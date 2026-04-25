# app/schemas/agencies.py
"""
Pydantic schemas for Agency model.
Follows BaseSchema/CreateSchema/UpdateSchema pattern.
DB-controlled fields (id, timestamps) excluded from Create/Update.
"""

from pydantic import BaseModel, EmailStr, ConfigDict, field_validator
from typing import Optional
from datetime import datetime
from uuid import UUID
from enum import Enum


class AgencyStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


# Base Schema (shared fields for responses)
class AgencyBase(BaseModel):
    """Shared agency fields"""
    name: str
    email: Optional[EmailStr] = None
    phone_number: Optional[str] = None
    address: Optional[str] = None
    description: Optional[str] = None
    logo_url: Optional[str] = None
    website_url: Optional[str] = None
    is_verified: bool = False  # Keep bool across base/response to avoid mutable override variance.
    status: AgencyStatus = AgencyStatus.APPROVED
    owner_email: Optional[EmailStr] = None
    owner_name: Optional[str] = None
    owner_phone_number: Optional[str] = None
    rejection_reason: Optional[str] = None

    @field_validator('email')
    @classmethod
    def email_to_lowercase(cls, v: Optional[str]) -> Optional[str]:
        """Ensure email is lowercase (matches DB CHECK constraint)"""
        return v.lower() if v else None

    @field_validator('owner_email')
    @classmethod
    def owner_email_to_lowercase(cls, v: Optional[str]) -> Optional[str]:
        return v.lower() if v else None


# Create Schema (for POST requests - excludes DB-controlled fields)
class AgencyCreate(AgencyBase):
    """Schema for creating a new agency"""
    name: str  # Required
    # All other fields optional via inheritance


class AgencyApplicationCreate(BaseModel):
    """Public agency application payload."""
    name: str
    description: Optional[str] = None
    address: Optional[str] = None
    owner_email: EmailStr
    owner_name: str
    owner_phone_number: Optional[str] = None
    email: Optional[EmailStr] = None
    phone_number: Optional[str] = None

    @field_validator('owner_email', 'email')
    @classmethod
    def application_email_to_lowercase(cls, v: Optional[str]) -> Optional[str]:
        return v.lower() if v else None


class AgencyApplicationResponse(BaseModel):
    agency_id: int
    status: AgencyStatus

    model_config = ConfigDict(from_attributes=True)


class AgencyRejectRequest(BaseModel):
    reason: Optional[str] = None


class AgencyInviteCreate(BaseModel):
    email: EmailStr

    @field_validator('email')
    @classmethod
    def invite_email_to_lowercase(cls, v: EmailStr) -> str:
        return v.lower()


class AgencyInviteResponse(BaseModel):
    invite_token: str
    agency_id: int
    email: EmailStr


class AgencyInviteAcceptRequest(BaseModel):
    invite_token: str


class AgencyInviteAcceptResponse(BaseModel):
    status: str
    agency_id: Optional[int] = None
    user_id: Optional[int] = None
    redirect_url: Optional[str] = None
    email: Optional[EmailStr] = None


# Update Schema (for PATCH/PUT requests - all fields optional)
class AgencyUpdate(BaseModel):
    """Schema for updating an agency"""
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone_number: Optional[str] = None
    address: Optional[str] = None
    description: Optional[str] = None
    logo_url: Optional[str] = None
    website_url: Optional[str] = None
    is_verified: Optional[bool] = None
    status: Optional[AgencyStatus] = None
    owner_email: Optional[EmailStr] = None
    owner_name: Optional[str] = None
    owner_phone_number: Optional[str] = None
    rejection_reason: Optional[str] = None

    @field_validator('email')
    @classmethod
    def email_to_lowercase(cls, v: Optional[str]) -> Optional[str]:
        """Ensure email is lowercase"""
        return v.lower() if v else None

    @field_validator('owner_email')
    @classmethod
    def owner_email_to_lowercase(cls, v: Optional[str]) -> Optional[str]:
        return v.lower() if v else None


# Response Schema (includes DB-controlled fields)
class AgencyResponse(AgencyBase):
    """Schema for agency responses (includes DB-generated fields)"""
    agency_id: int
    name: str
    is_verified: bool = False  # Explicit default keeps pyright aligned with inherited mutable field rules.
    status: AgencyStatus = AgencyStatus.APPROVED
    owner_email: Optional[EmailStr] = None
    owner_name: Optional[str] = None
    owner_phone_number: Optional[str] = None
    rejection_reason: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None
    created_by: Optional[UUID] = None
    updated_by: Optional[UUID] = None
    deleted_by: Optional[UUID] = None

    model_config = ConfigDict(from_attributes=True)


# List Response Schema (for paginated lists)
class AgencyListResponse(BaseModel):
    """Schema for paginated agency lists"""
    agencies: list[AgencyResponse]
    total: int
    page: int
    page_size: int

    model_config = ConfigDict(from_attributes=True)
