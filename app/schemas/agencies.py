# app/schemas/agencies.py
"""
Pydantic schemas for Agency model.
Follows BaseSchema/CreateSchema/UpdateSchema pattern.
DB-controlled fields (id, timestamps) excluded from Create/Update.
"""

from pydantic import BaseModel, EmailStr, ConfigDict, Field, field_validator
from typing import Optional, Dict
from datetime import datetime
from uuid import UUID
from enum import Enum

from app.schemas.membership_audit import AgentMembershipAuditResponse
from app.utils.validation import validate_not_placeholder, validate_not_test_email


class AgencyStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    SUSPENDED = "suspended"


class AgencyJoinRequestStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


class AgencyAgentMembershipStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    BLOCKED = "blocked"
    REVOKED = "revoked"
    LEFT = "left"


class AgencyMembershipReviewRequestStatus(str, Enum):
    PENDING = "pending"
    REVIEWED = "reviewed"
    APPROVED = "approved"
    REJECTED = "rejected"


class AgencyReviewRequestStatus(str, Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    DECLINED = "declined"


class AgentMembershipRestrictionStatus(str, Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    BLOCKED = "blocked"
    REVOKED = "revoked"


class AgencyInvitationStatus(str, Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    EXPIRED = "expired"
    REVOKED = "revoked"


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
    status_reason: Optional[str] = None

    @field_validator('name')
    @classmethod
    def validate_name(cls, v: str) -> str:
        return validate_not_placeholder(v, "name") or v

    @field_validator('owner_name')
    @classmethod
    def validate_owner_name(cls, v: Optional[str]) -> Optional[str]:
        return validate_not_placeholder(v, "owner_name")

    @field_validator('email')
    @classmethod
    def email_to_lowercase(cls, v: Optional[str]) -> Optional[str]:
        result = v.lower() if v else None
        return validate_not_test_email(result, "email") or result

    @field_validator('owner_email')
    @classmethod
    def owner_email_to_lowercase(cls, v: Optional[str]) -> Optional[str]:
        result = v.lower() if v else None
        return validate_not_test_email(result, "owner_email") or result


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
    website_url: Optional[str] = None
    owner_email: EmailStr
    owner_name: str
    owner_phone_number: Optional[str] = None
    email: Optional[EmailStr] = None
    phone_number: Optional[str] = None

    @field_validator('name')
    @classmethod
    def validate_application_name(cls, v: str) -> str:
        return validate_not_placeholder(v, "name") or v

    @field_validator('owner_name')
    @classmethod
    def validate_application_owner_name(cls, v: str) -> str:
        return validate_not_placeholder(v, "owner_name") or v

    @field_validator('owner_email', 'email')
    @classmethod
    def application_email_to_lowercase(cls, v: Optional[str]) -> Optional[str]:
        result = v.lower() if v else None
        return validate_not_test_email(result, "owner_email") or result


class AgencyApplicationResponse(BaseModel):
    agency_id: int
    status: AgencyStatus

    model_config = ConfigDict(from_attributes=True)


class AgencyDecisionRequest(BaseModel):
    reason: str = Field(..., min_length=1)

    @field_validator("reason")
    @classmethod
    def reason_must_not_be_blank(cls, value: str) -> str:
        reason = value.strip()
        if not reason:
            raise ValueError("reason is required")
        return reason


class AgencyRejectRequest(AgencyDecisionRequest):
    pass


class AgencyJoinRequestCreate(BaseModel):
    cover_note: Optional[str] = None
    portfolio_details: Optional[str] = None


class AgencyJoinRequestRejectRequest(AgencyDecisionRequest):
    pass


class AgencyAgentMembershipActionRequest(AgencyDecisionRequest):
    pass


class AgencyMembershipReviewRequestCreate(BaseModel):
    reason: Optional[str] = None


class AgencyMembershipReviewDecisionRequest(AgencyDecisionRequest):
    pass


class AgencyReviewRequestCreate(BaseModel):
    message: Optional[str] = None


class AgencyReviewRequestDecisionRequest(BaseModel):
    reason: Optional[str] = None

    @field_validator("reason")
    @classmethod
    def optional_reason_must_not_be_blank(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        reason = value.strip()
        return reason or None


class AgencyJoinRequestResponse(BaseModel):
    join_request_id: int
    agency_id: int
    user_id: int
    status: AgencyJoinRequestStatus
    cover_note: Optional[str] = None
    portfolio_details: Optional[str] = None
    rejection_reason: Optional[str] = None
    decided_at: Optional[datetime] = None
    decided_by: Optional[int] = None
    seeker_email: Optional[EmailStr] = None
    seeker_name: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MyAgencyJoinRequestResponse(BaseModel):
    join_request_id: int
    agency_id: int
    agency_name: str
    status: AgencyJoinRequestStatus
    rejection_reason: Optional[str] = None
    decided_at: Optional[datetime] = None
    decided_by: Optional[int] = None
    submitted_at: datetime


class AgencyAgentRosterResponse(BaseModel):
    user_id: int
    agency_id: int
    membership_id: int
    membership_status: AgencyAgentMembershipStatus
    status_reason: Optional[str] = None
    status_decided_at: Optional[datetime] = None
    status_decided_by: Optional[int] = None
    display_name: str
    email: EmailStr
    phone_number: Optional[str] = None
    profile_image_url: Optional[str] = None
    profile_id: Optional[int] = None
    specialization: Optional[str] = None
    years_experience: Optional[int] = None
    license_number: Optional[str] = None
    bio: Optional[str] = None
    company_name: Optional[str] = None
    last_login: Optional[datetime] = None
    listing_count: int = 0
    pending_review_request_id: Optional[int] = None
    pending_review_reason: Optional[str] = None
    pending_review_submitted_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class AgencyAgentMembershipResponse(BaseModel):
    membership_id: int
    agency_id: int
    user_id: int
    agent_profile_id: Optional[int] = None
    status: AgencyAgentMembershipStatus
    status_reason: Optional[str] = None
    status_decided_at: Optional[datetime] = None
    status_decided_by: Optional[int] = None
    source_join_request_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AgencyMembershipReviewRequestResponse(BaseModel):
    review_request_id: int
    membership_id: int
    agency_id: int
    user_id: int
    status: AgencyMembershipReviewRequestStatus
    reason: Optional[str] = None
    response_reason: Optional[str] = None
    decided_at: Optional[datetime] = None
    decided_by: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AgencyReviewRequestResponse(BaseModel):
    id: int
    user_id: int
    agency_id: int
    status: AgencyReviewRequestStatus
    message: Optional[str] = None
    reason: Optional[str] = None
    actor_id: Optional[int] = None
    requester_email: Optional[EmailStr] = None
    requester_name: Optional[str] = None
    membership_history: list[AgentMembershipAuditResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MyAgencyMembershipResponse(BaseModel):
    membership_id: int
    agency_id: int
    agency_name: str
    status: AgencyAgentMembershipStatus
    status_reason: Optional[str] = None
    status_decided_at: Optional[datetime] = None
    status_decided_by: Optional[int] = None
    source_join_request_id: Optional[int] = None
    listing_count: int = 0
    pending_review_request_id: Optional[int] = None
    pending_review_reason: Optional[str] = None
    pending_review_submitted_at: Optional[datetime] = None
    role_changed: bool = False
    new_role: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class MyAgentMembershipStatusResponse(BaseModel):
    agent_id: UUID
    status: AgentMembershipRestrictionStatus
    reason: Optional[str] = None
    updated_at: datetime
    membership_id: Optional[int] = None
    agency_id: Optional[int] = None
    agency_name: Optional[str] = None


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
    invitation_id: Optional[int] = None
    status: Optional[AgencyInvitationStatus] = None
    expires_at: Optional[datetime] = None


class AgencyInviteAcceptRequest(BaseModel):
    invite_token: str


class AgencyInviteAcceptResponse(BaseModel):
    status: str
    agency_id: Optional[int] = None
    user_id: Optional[int] = None
    invitation_id: Optional[int] = None
    redirect_url: Optional[str] = None
    email: Optional[EmailStr] = None


class AgencyInvitationResponse(BaseModel):
    invitation_id: int
    agency_id: int
    agency_name: str
    email: EmailStr
    invited_user_id: Optional[int] = None
    status: AgencyInvitationStatus
    created_at: datetime
    updated_at: datetime
    expires_at: datetime
    accepted_at: Optional[datetime] = None
    rejected_at: Optional[datetime] = None
    revoked_at: Optional[datetime] = None


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
    status_reason: Optional[str] = None

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
    status_reason: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None
    created_by: Optional[UUID] = None
    updated_by: Optional[UUID] = None
    deleted_by: Optional[UUID] = None
    agent_count: int = 0
    property_count: int = 0

    model_config = ConfigDict(from_attributes=True)


# List Response Schema (for paginated lists)
class AgencyListResponse(BaseModel):
    """Schema for paginated agency lists"""
    agencies: list[AgencyResponse]
    total: int
    page: int
    page_size: int

    model_config = ConfigDict(from_attributes=True)


class AgencyStatsResponse(BaseModel):
    """Agency-level statistics with breakdowns by listing and agent status."""
    agent_count: int = 0
    agents_by_status: Dict[str, int] = Field(default_factory=dict)
    property_count: int = 0
    total_listings: int = 0
    listings_by_status: Dict[str, int] = Field(default_factory=dict)

    model_config = ConfigDict(from_attributes=True)
