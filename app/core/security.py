# app/core/security.py
"""
RealtorNet Security Module - JWT Token Management & Password Hashing
Aligned with Phase 2 canonical rules: Supabase integration, multi-tenant support
"""

from __future__ import annotations
from datetime import datetime, timedelta, timezone
from typing import Optional, cast
from uuid import UUID

from jose import JWTError, jwt
from jose.exceptions import ExpiredSignatureError, JWTClaimsError
from pydantic import BaseModel
import bcrypt

from app.core.config import settings
from app.core.exceptions import AuthenticationException


# PASSWORD HASHING

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify plain text password against bcrypt hash."""
    try:
        return bcrypt.checkpw(
            plain_password.encode('utf-8'),
            hashed_password.encode('utf-8')
        )
    except (ValueError, TypeError):
        return False


def get_password_hash(password: str) -> str:
    """Generate bcrypt hash for password (12 rounds)."""
    salt = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')


# TOKEN PAYLOAD SCHEMA
# Single definition — no duplicates

class TokenPayload(BaseModel):
    """
    JWT Token Payload Schema.
    All UUID fields stored as strings to avoid UUID↔VARCHAR mismatch in DB queries.
    Field names match exactly what create_token encodes into the JWT.
    """
    sub: Optional[str] = None           # Standard JWT subject (stringified supabase_id)
    supabase_id: Optional[str] = None   # Explicit supabase_id for lookup
    user_id: Optional[int] = None       # Internal DB user_id
    role: Optional[str] = None          # User role (seeker/agent/admin)
    token_type: Optional[str] = None    # "access" or "refresh"
    agency_id: Optional[int] = None     # Multi-tenant context


# TOKEN CREATION
# Single create_token — no duplicates

def create_token(
    supabase_id: UUID,
    user_id: int,
    token_type: str = "access",
    user_role: Optional[str] = None,
    agency_id: Optional[int] = None
) -> str:
    """
    Generate a signed JWT token.
    Uses settings.SECRET_KEY — must match what decode_token uses.
    Refresh tokens default to 7 days if REFRESH_TOKEN_EXPIRE_DAYS not set.
    """
    if token_type == "access":
        minutes = settings.ACCESS_TOKEN_EXPIRE_MINUTES
    else:
        # Safe default: 7 days in minutes
        refresh_days = getattr(settings, 'REFRESH_TOKEN_EXPIRE_DAYS', 7)
        minutes = refresh_days * 24 * 60

    expire = datetime.now(timezone.utc) + timedelta(minutes=minutes)

    # Field names MUST match TokenPayload field names above
    payload_dict = {
        "sub": str(supabase_id),
        "supabase_id": str(supabase_id),
        "user_id": user_id,
        "exp": int(expire.timestamp()),
        "iat": int(datetime.now(timezone.utc).timestamp()),
        "token_type": token_type,
        "role": user_role,
        "agency_id": agency_id,
    }

    return jwt.encode(
        payload_dict,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM
    )


# TOKEN DECODE

def decode_token(token: str) -> TokenPayload:
    """
    Decode and validate a JWT token.
    Raises AuthenticationException on any failure.
    """
    try:
        payload_dict = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )
        return TokenPayload(**payload_dict)

    except ExpiredSignatureError:
        raise AuthenticationException(message="Token has expired")
    except JWTClaimsError:
        raise AuthenticationException(message="Invalid authentication credentials")
    except JWTError:
        raise AuthenticationException(message="Invalid authentication credentials")
    except Exception:
        raise AuthenticationException(message="Invalid authentication credentials")


# CONVENIENCE WRAPPERS

def generate_access_token(
    supabase_id: UUID,
    user_id: int,
    user_role: Optional[str] = None,
    agency_id: Optional[int] = None
) -> str:
    """Generate a short-lived access token."""
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
    """Generate a long-lived refresh token."""
    return create_token(
        supabase_id=supabase_id,
        user_id=user_id,
        token_type="refresh",
        user_role=user_role,
        agency_id=agency_id
    )


def validate_token_refresh(refresh_token: str, current_supabase_id: UUID) -> str:
    """
    Validate a refresh token and return a new access token.
    Raises AuthenticationException if invalid.
    """
    try:
        refresh_payload = decode_token(refresh_token)

        if refresh_payload.token_type != "refresh":
            raise AuthenticationException(message="Invalid token type for refresh operation")

        if refresh_payload.supabase_id != str(current_supabase_id):
            raise AuthenticationException(message="Invalid refresh token")

        return generate_access_token(
            supabase_id=UUID(refresh_payload.supabase_id),
            user_id=cast(int, refresh_payload.user_id),
            user_role=refresh_payload.role,
            agency_id=refresh_payload.agency_id
        )
    except AuthenticationException:
        raise
    except Exception:
        raise AuthenticationException(message="Token refresh failed")


# EXPORTS

__all__ = [
    "verify_password",
    "get_password_hash",
    "TokenPayload",
    "create_token",
    "decode_token",
    "generate_access_token",
    "generate_refresh_token",
    "validate_token_refresh",
]
