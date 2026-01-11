# app/api/dependencies.py
"""
RealtorNet API Dependencies - Authentication & Authorization
Phase 2 Aligned: Supabase UUID, soft delete, multi-tenant, DoS protection

Security Enhancements (Vercel CVE Mitigation):
- Request validation at dependency level
- Generic error messages (no auth flow leakage)
- Soft delete filtering (prevent deleted user access)
- Agency context for multi-tenant RLS
"""

from typing import Optional
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

# --- DIRECT IMPORTS ---
from app.core.config import settings
from app.core.database import get_db
from app.core.security import decode_token, TokenPayload
from app.core.exceptions import AuthenticationException, AuthorizationException
from app.models.users import User, UserRole
from app.models.agencies import Agency
from app.crud.users import user as user_crud

# OAuth2 scheme for token authentication
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/auth/login"
)


# --- Request Size Validation (DoS Protection: CVE-2025-55184) ---

MAX_REQUEST_BODY_SIZE = 10 * 1024 * 1024  # 10MB limit

def validate_request_size(request: Request):
    """
    Validate request body size to prevent DoS attacks.
    
    Protects against CVE-2025-55184 (malicious large payloads).
    Applied automatically via Depends() in protected routes.
    """
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > MAX_REQUEST_BODY_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Request body too large"
        )


# --- Core Authentication Dependencies ---

def get_current_user(
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme)
) -> User:
    """
    Get the current authenticated user from JWT token.
    
    Canonical Compliance:
    - Uses supabase_id (UUID) for secure lookup
    - Filters soft-deleted users
    - Generic error messages (security best practice)
    
    Raises:
        HTTPException 401: Invalid/expired token or user not found
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid authentication credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        # Decode token and extract payload
        token_payload: TokenPayload = decode_token(token)
        
        # Lookup user by Supabase UUID (secure public identifier)
        user = db.query(User).filter(
            User.supabase_id == token_payload.supabase_id,
            User.deleted_at.is_(None)  # Soft delete filter (canonical rule #10)
        ).first()
        
        if user is None:
            raise credentials_exception
        
        # Verify internal user_id matches (additional security layer)
        if user.user_id != token_payload.user_id:
            raise credentials_exception
        
        return user
        
    except AuthenticationException:
        raise credentials_exception
    except Exception:
        # Generic error - don't leak internal details (Vercel insight)
        raise credentials_exception


def get_current_user_optional(
    db: Session = Depends(get_db),
    token: Optional[str] = Depends(oauth2_scheme)
) -> Optional[User]:
    """
    Get current user if token provided, otherwise return None.
    
    For endpoints that work for both authenticated and anonymous users.
    Examples: public property listings, browse pages
    """
    if not token:
        return None
    
    try:
        return get_current_user(db=db, token=token)
    except HTTPException:
        return None


def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    Ensure the current user is active (not soft deleted).
    
    Uses the is_active property from User model which checks deleted_at == None
    """
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive"
        )
    return current_user


# --- Role-Based Authorization Dependencies ---

def get_current_admin_user(
    current_user: User = Depends(get_current_active_user),
) -> User:
    """
    Ensure the current user has admin privileges.
    
    Uses CRUD helper for consistent authorization checks.
    """
    if not user_crud.is_admin(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator privileges required"
        )
    return current_user


def get_current_agent_user(
    current_user: User = Depends(get_current_active_user),
) -> User:
    """
    Ensure the current user is a real estate agent.
    
    Uses CRUD helper for consistent authorization checks.
    """
    if not user_crud.is_agent(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Real estate agent privileges required"
        )
    return current_user


def get_current_seeker_user(
    current_user: User = Depends(get_current_active_user),
) -> User:
    """
    Ensure the current user is a property seeker (buyer/seller).
    
    Uses CRUD helper for consistent authorization checks.
    """
    if not user_crud.is_seeker(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Property seeker privileges required"
        )
    return current_user


# --- Multi-Tenant Context Dependencies ---

def get_current_agency(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Optional[Agency]:
    """
    Extract agency context for multi-tenant operations.
    
    Returns:
        Agency object if user belongs to one, None otherwise
    
    Use Cases:
        - RLS enforcement (filter properties by agency_id)
        - Agent-specific operations
        - Agency admin operations
    """
    if not current_user.agency_id:
        return None
    
    agency = db.query(Agency).filter(
        Agency.agency_id == current_user.agency_id,
        Agency.deleted_at.is_(None)  # Soft delete filter
    ).first()
    
    return agency


def require_agency(
    agency: Optional[Agency] = Depends(get_current_agency)
) -> Agency:
    """
    Ensure user belongs to an agency (strict requirement).
    
    Use for agency-specific operations like creating listings.
    """
    if agency is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Agency membership required for this operation"
        )
    return agency


# --- Combined Protection Dependency ---

def protected_route(
    _: None = Depends(validate_request_size),
    current_user: User = Depends(get_current_active_user)
) -> User:
    """
    Combined dependency for protected routes requiring:
    - Request size validation (DoS protection)
    - Active authenticated user
    
    Usage:
        @router.post("/properties", dependencies=[Depends(protected_route)])
        def create_property(...):
            pass
    """
    return current_user