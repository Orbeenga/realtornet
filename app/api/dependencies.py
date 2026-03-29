# app/api/dependencies.py
"""
RealtorNet API Dependencies - Authentication & Authorization
Phase 2 Aligned: Supabase UUID, soft delete, multi-tenant, DoS protection
"""

from typing import Optional
from uuid import UUID

from fastapi import Depends, HTTPException, Query, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.security import decode_token, TokenPayload
from app.core.exceptions import AuthenticationException, AuthorizationException
from app.models.users import User, UserRole
from app.models.agencies import Agency
from app.crud.users import user as user_crud

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/auth/login",
    auto_error=True
)

oauth2_scheme_optional = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/auth/login",
    auto_error=False
)


# --- Request Size Validation (DoS Protection: CVE-2025-55184) ---

MAX_REQUEST_BODY_SIZE = 10 * 1024 * 1024  # 10MB limit

def validate_request_size(request: Request):
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > MAX_REQUEST_BODY_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Request body too large"
        )


# --- Pagination Dependency ---

def pagination_params(
    skip: int = Query(default=0, ge=0, description="Records to skip"),
    limit: int = Query(default=20, ge=1, le=100, description="Page size (max 100)"),
) -> dict:
    return {"skip": skip, "limit": limit}


# --- Core Authentication Dependencies ---

def get_current_user(
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme)
) -> User:
    """
    Get the current authenticated user from JWT token.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid authentication credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        # Step 1: Decode token
        token_payload: TokenPayload = decode_token(token)

        # Step 2: Resolve the UUID string to query with
        s_id = token_payload.supabase_id or token_payload.sub

        if not s_id:
            raise credentials_exception

        s_id_str = str(s_id)

        # Step 3: Query user
        user = db.query(User).filter(
            User.supabase_id == s_id_str,
            User.deleted_at.is_(None)
        ).first()

        if user is None:
            # Extra debug: check if user exists at all (ignore soft delete)
            user_any = db.query(User).filter(User.supabase_id == s_id_str).first()
            raise credentials_exception

        # Step 4: Verify user_id if present
        if token_payload.user_id and user.user_id != token_payload.user_id:
            raise credentials_exception

        return user

    except HTTPException:
        raise  # Re-raise our own 401s directly — do NOT let except Exception swallow them
    except AuthenticationException:
        raise credentials_exception
    except Exception:
        raise credentials_exception


def get_current_user_optional(
    db: Session = Depends(get_db),
    token: Optional[str] = Depends(oauth2_scheme_optional)
) -> Optional[User]:
    """
    Get current user if token provided, otherwise return None.
    For endpoints that work for both authenticated and anonymous users.
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
    """Ensure the current user is active (not soft deleted)."""
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
    if not user_crud.is_admin(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator privileges required"
        )
    return current_user


def get_current_agent_user(
    current_user: User = Depends(get_current_active_user),
) -> User:
    if not user_crud.is_agent(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Real estate agent privileges required"
        )
    return current_user


def get_current_seeker_user(
    current_user: User = Depends(get_current_active_user),
) -> User:
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
    if not current_user.agency_id:
        return None

    agency = db.query(Agency).filter(
        Agency.agency_id == current_user.agency_id,
        Agency.deleted_at.is_(None)
    ).first()

    return agency


def require_agency(
    agency: Optional[Agency] = Depends(get_current_agency)
) -> Agency:
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
    return current_user
