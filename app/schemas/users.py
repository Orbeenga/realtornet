# app/schemas/users.py
"""
Pydantic schemas for User model.
Follows BaseSchema/CreateSchema/UpdateSchema pattern.
DB-controlled fields (user_id, timestamps, supabase_id) excluded from Create/Update.
"""

from pydantic import BaseModel, EmailStr, ConfigDict, field_validator, Field
from typing import Optional
from datetime import datetime
from enum import Enum
from uuid import UUID


# Enum matching DB exactly
class UserRole(str, Enum):
    """User role enum - matches DB user_role_enum"""
    SEEKER = "seeker"
    AGENT = "agent"
    AGENCY_OWNER = "agency_owner"
    ADMIN = "admin"


# Base Schema (shared fields for responses)
class UserBase(BaseModel):
    """Shared user fields"""
    email: EmailStr
    first_name: str
    last_name: str
    phone_number: Optional[str] = None
    user_role: UserRole
    agency_id: Optional[int] = None
    profile_image_url: Optional[str] = None

    @field_validator('email')
    @classmethod
    def email_to_lowercase(cls, v: EmailStr) -> str:
        """Ensure email is lowercase (matches DB CHECK constraint)"""
        return v.lower()

    @field_validator('first_name', 'last_name')
    @classmethod
    def validate_not_empty(cls, v: str) -> str:
        """Ensure required fields are not empty"""
        if not v or not v.strip():
            raise ValueError('field cannot be empty')
        return v.strip()

    @field_validator('phone_number')
    @classmethod
    def validate_phone_number(cls, v: Optional[str]) -> Optional[str]:
        """Ensure phone_number is not empty if provided (matches DB CHECK)"""
        if v is not None and not v.strip():
            return None  # Treat empty string as None
        return v.strip() if v else None


# Create Schema (for POST requests - excludes DB-controlled fields)
class UserCreate(UserBase):
    """Schema for creating a new user"""
    password: str = Field(..., min_length=8)  # Required for registration
    # REMOVED: supabase_id - API generates this, not user input!

    @field_validator('password')
    @classmethod
    def validate_password(cls, v: str) -> str:
        """Ensure password meets minimum requirements"""
        if len(v) < 8:
            raise ValueError('password must be at least 8 characters')
        return v


# Update Schema (for PATCH/PUT requests - all fields optional)
class UserUpdate(BaseModel):
    """Schema for updating a user"""
    email: Optional[EmailStr] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone_number: Optional[str] = None
    profile_image_url: Optional[str] = None
    user_role: Optional[UserRole] = None
    # Password change (if provided, must be validated)
    password: Optional[str] = None

    @field_validator('email')
    @classmethod
    def email_to_lowercase(cls, v: Optional[EmailStr]) -> Optional[str]:
        """Ensure email is lowercase"""
        return v.lower() if v else None

    @field_validator('first_name', 'last_name')
    @classmethod
    def validate_not_empty(cls, v: Optional[str]) -> Optional[str]:
        """Ensure fields are not empty if provided"""
        if v is not None and not v.strip():
            raise ValueError('field cannot be empty')
        return v.strip() if v else None

    @field_validator('phone_number')
    @classmethod
    def validate_phone_number(cls, v: Optional[str]) -> Optional[str]:
        """Ensure phone_number is not empty if provided"""
        if v is not None and not v.strip():
            return None
        return v.strip() if v else None

    @field_validator('password')
    @classmethod
    def validate_password(cls, v: Optional[str]) -> Optional[str]:
        """Ensure password meets minimum requirements if provided"""
        if v is not None and len(v) < 8:
            raise ValueError('password must be at least 8 characters')
        return v


# Response Schema (includes DB-controlled fields, excludes password_hash)
class UserResponse(UserBase):
    """Schema for user responses (includes DB-generated fields, no sensitive data)"""
    user_id: int  # Matches DB column name exactly
    supabase_id: UUID
    is_verified: bool
    is_admin: bool
    created_at: datetime
    updated_at: datetime
    last_login: Optional[datetime] = None
    deleted_at: Optional[datetime] = None
    created_by: Optional[UUID] = None
    updated_by: Optional[UUID] = None
    deleted_by: Optional[UUID] = None

    model_config = ConfigDict(from_attributes=True)


# Internal Schema (includes password_hash for auth operations)
class UserInDB(UserResponse):
    """Internal schema with sensitive fields (never returned to client)"""
    password_hash: str
    verification_code: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


# List Response Schema (for paginated lists)
class UserListResponse(BaseModel):
    """Schema for paginated user lists"""
    users: list[UserResponse]
    total: int
    page: int
    page_size: int

    model_config = ConfigDict(from_attributes=True)


# Login/Auth Schemas
class UserLogin(BaseModel):
    """Schema for user login"""
    email: EmailStr
    password: str

    @field_validator('email')
    @classmethod
    def email_to_lowercase(cls, v: EmailStr) -> str:
        """Ensure email is lowercase"""
        return v.lower()


class UserRegister(UserCreate):
    """Schema for user registration (alias for UserCreate)"""
    pass

# Alias for convenience
