# app/schemas/agent_profiles
"""
Pydantic schemas for AgentProfile model.
Follows BaseSchema/CreateSchema/UpdateSchema pattern.
DB-controlled fields (id, timestamps) excluded from Create/Update.
"""

from pydantic import BaseModel, ConfigDict, field_validator
from typing import Optional
from datetime import datetime


# Base Schema (shared fields for responses)
class AgentProfileBase(BaseModel):
    """Shared agent profile fields"""
    user_id: Optional[int] = None
    agency_id: Optional[int] = None
    license_number: Optional[str] = None
    years_experience: Optional[int] = None
    specialization: Optional[str] = None
    bio: Optional[str] = None
    website: Optional[str] = None
    company_name: Optional[str] = None

    @field_validator('years_experience')
    @classmethod
    def validate_years_experience(cls, v: Optional[int]) -> Optional[int]:
        """Ensure years_experience is non-negative"""
        if v is not None and v < 0:
            raise ValueError('years_experience must be non-negative')
        return v


# Create Schema (for POST requests - excludes DB-controlled fields)
class AgentProfileCreate(AgentProfileBase):
    """Schema for creating a new agent profile"""
    user_id: int  # Required - must link to a user
    # All other fields optional via inheritance


# Update Schema (for PATCH/PUT requests - all fields optional)
class AgentProfileUpdate(BaseModel):
    """Schema for updating an agent profile"""
    agency_id: Optional[int] = None
    license_number: Optional[str] = None
    years_experience: Optional[int] = None
    specialization: Optional[str] = None
    bio: Optional[str] = None
    website: Optional[str] = None
    company_name: Optional[str] = None

    @field_validator('years_experience')
    @classmethod
    def validate_years_experience(cls, v: Optional[int]) -> Optional[int]:
        """Ensure years_experience is non-negative"""
        if v is not None and v < 0:
            raise ValueError('years_experience must be non-negative')
        return v


# Response Schema (includes DB-controlled fields)
class AgentProfileResponse(AgentProfileBase):
    """Schema for agent profile responses (includes DB-generated fields)"""
    profile_id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# Extended Response (with nested user/agency data)
class AgentProfileExtendedResponse(AgentProfileResponse):
    """Extended response with related user and agency data"""
    user: Optional[dict] = None  # Can be replaced with UserResponse if needed
    agency: Optional[dict] = None  # Can be replaced with AgencyResponse if needed

    model_config = ConfigDict(from_attributes=True)


# List Response Schema (for paginated lists)
class AgentProfileListResponse(BaseModel):
    """Schema for paginated agent profile lists"""
    agent_profiles: list[AgentProfileResponse]
    total: int
    page: int
    page_size: int

    model_config = ConfigDict(from_attributes=True)

# Fast API alias
