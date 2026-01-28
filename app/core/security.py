# app/core/security.py
"""
RealtorNet Security Module - JWT Token Management & Password Hashing
Aligned with Phase 2 canonical rules: Supabase integration, multi-tenant support

Consolidated security module containing:
- Password hashing (bcrypt)
- JWT token generation and validation
- Multi-tenant authentication
- Using bcrypt directly instead of passlib (passlib has bugs)
"""

from __future__ import annotations
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from jose import jwt, JWTError
from pydantic import BaseModel, Field, field_validator
import bcrypt

from app.core.config import settings
from app.core.exceptions import AuthenticationException


# PASSWORD HASHING (Bcrypt)
def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify that a plain text password matches the stored hashed password.
    UPDATED: Uses bcrypt directly to avoid passlib bugs
    
    Args:
        plain_password: Plain text password from user input
        hashed_password: Bcrypt hash from database
        
    Returns:
        True if password matches, False otherwise
    """
    try:
        password_bytes = plain_password.encode('utf-8')
        hashed_bytes = hashed_password.encode('utf-8')
        return bcrypt.checkpw(password_bytes, hashed_bytes)
    except (ValueError, TypeError):
        return False


def get_password_hash(password: str) -> str:
    """
    Generate a bcrypt hash for the provided plain text password.
    UPDATED: Uses bcrypt directly to avoid passlib bugs
    
    Args:
        password: Plain text password to hash
        
    Returns:
        Bcrypt hash string (12 rounds)
        
    Note: 12 rounds provides strong security while maintaining performance
    """
    password_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode('utf-8')


# JWT TOKEN MANAGEMENT

class TokenPayload(BaseModel):
    """
    Enhanced JWT token payload with Supabase integration and multi-tenant support.
    
    Canonical Rules Applied:
    - supabase_id: UUID for secure public identifier (Rule #2)
    - agency_id: Optional[int] for multi-tenant RLS enforcement
    - Timezone-aware datetime (Rule #1)
    """
    sub: str  # Subject: stringified supabase_id for JWT compatibility
    supabase_id: UUID  # Explicit Supabase auth UUID
    user_id: int  # Internal database user_id (BigInteger)
    exp: datetime  # Expiration time
    iat: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    token_type: str = "access"
    user_role: Optional[str] = None
    agency_id: Optional[int] = None  # Multi-tenant context
    refresh_token_id: Optional[str] = None

    @field_validator('exp')
    def validate_expiration(cls, v):
        now = datetime.now(timezone.utc)
        if v.tzinfo is None:
            raise ValueError("Expiration must be timezone-aware")
        if v <= now:
            raise ValueError("Token expiration must be in the future")
        max_future = now + timedelta(days=30)
        if v > max_future:
            raise ValueError("Token expiration is too far in the future")
        return v


def create_token(
    supabase_id: UUID,
    user_id: int,
    token_type: str = "access",
    expires_delta: Optional[timedelta] = None,
    user_role: Optional[str] = None,
    agency_id: Optional[int] = None
) -> str:
    """
    Create a JWT token with enhanced security.
    
    Args:
        supabase_id: User's Supabase auth UUID (public identifier)
        user_id: Internal database user_id (BigInteger)
        token_type: "access" or "refresh"
        expires_delta: Custom expiration time
        user_role: User role for authorization
        agency_id: Agency context for multi-tenant RLS
    
    Returns:
        Encoded JWT token string
    """
    if token_type == "access" and not expires_delta:
        expires_delta = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    if token_type == "refresh" and not expires_delta:
        expires_delta = timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

    expire = datetime.now(timezone.utc) + expires_delta

    payload_dict = {
        "sub": str(supabase_id),
        "supabase_id": str(supabase_id),
        "user_id": user_id,
        "exp": int(expire.timestamp()),  # ← Convert to Unix timestamp!
        "iat": int(datetime.now(timezone.utc).timestamp()),
        "token_type": token_type,
        "user_role": user_role,
        "agency_id": agency_id
    }

    return jwt.encode(
        payload_dict, 
        settings.SECRET_KEY, 
        algorithm=settings.ALGORITHM
    )


def decode_token(token: str) -> TokenPayload:
    """
    Decode and validate a JWT token.
    
    Args:
        token: JWT token string
        
    Returns:
        Validated TokenPayload
        
    Raises:
        AuthenticationException: On any validation failure (generic message for security)
    """
    try:
        payload_dict = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )

        return TokenPayload(**payload_dict)
    except jwt.ExpiredSignatureError:
        raise AuthenticationException(
            message="Token has expired",
            details={"error_type": "TokenExpired"}
        )
    except jwt.JWTClaimsError:
        raise AuthenticationException(
            message="Invalid authentication credentials",
            details={"error_type": "InvalidClaims"}
        )
    except JWTError:
        raise AuthenticationException(
            message="Invalid authentication credentials",
            details={"error_type": "InvalidToken"}
        )


def generate_access_token(
    supabase_id: UUID,
    user_id: int,
    user_role: Optional[str] = None,
    agency_id: Optional[int] = None
) -> str:
    """
    Generate a short-lived access token.
    
    Duration: 15 minutes (configurable via ACCESS_TOKEN_EXPIRE_MINUTES)
    """
    return create_token(
        supabase_id=supabase_id,
        user_id=user_id,
        token_type="access",
        user_role=user_role,
        agency_id=agency_id
    )


def generate_refresh_token(
    supabase_id: UUID,
    user_id: int,
    user_role: Optional[str] = None,
    agency_id: Optional[int] = None
) -> str:
    """
    Generate a long-lived refresh token.
    
    Duration: 30 days (configurable via REFRESH_TOKEN_EXPIRE_DAYS)
    """
    return create_token(
        supabase_id=supabase_id,
        user_id=user_id,
        token_type="refresh",
        user_role=user_role,
        agency_id=agency_id
    )


def validate_token_refresh(refresh_token: str, current_supabase_id: UUID) -> str:
    """
    Validate a refresh token and generate a new access token if valid.
    
    Args:
        refresh_token: The refresh token to validate
        current_supabase_id: Expected supabase_id for validation
    
    Returns:
        New access token string
    
    Raises:
        AuthenticationException: If token invalid or type mismatch
    """
    try:
        refresh_payload = decode_token(refresh_token)
        
        # Validate token type
        if refresh_payload.token_type != "refresh":
            raise AuthenticationException(
                message="Invalid token type for refresh operation",
                details={"error_type": "InvalidTokenType"}
            )
        
        # Validate subject matches
        if refresh_payload.supabase_id != current_supabase_id:
            raise AuthenticationException(
                message="Invalid refresh token",
                details={"error_type": "InvalidRefreshToken"}
            )
        
        return generate_access_token(
            supabase_id=refresh_payload.supabase_id,
            user_id=refresh_payload.user_id,
            user_role=refresh_payload.user_role,
            agency_id=refresh_payload.agency_id
        )
    except AuthenticationException:
        raise
    except Exception:
        # SECURITY: Don't expose internal error details
        raise AuthenticationException(
            message="Token refresh failed",
            details={"error_type": "RefreshFailed"}
        )


# Export all public functions
__all__ = [
    "verify_password",
    "get_password_hash",
    "TokenPayload",
    "create_token",
    "decode_token",
    "generate_access_token",
    "generate_refresh_token",
    "validate_token_refresh"
]