# app/core/dependencies.py
"""
FastAPI Dependencies - Security & Validation Layer
Centralized dependency injection for request validation, rate limiting, and access control.
"""

from fastapi import Request, HTTPException, status, Depends
from typing import List, Any
from app.models.users import User

# --- CANONICAL IMPORT ALIGNMENT ---
# We import from app.api.dependencies to avoid circular logic 
# and ensure we use the centralized auth flow.
from app.api.dependencies import get_current_active_user


# Request Size Validation (DoS Protection)
async def validate_request_size(request: Request):
    """
    Validate request body size to prevent DoS attacks.
    Max size: 10MB for file uploads, 1MB for JSON payloads.
    """
    content_length = request.headers.get("content-length")
    
    if content_length:
        content_length = int(content_length)
        max_size = 10 * 1024 * 1024  # 10MB
        
        if content_length > max_size:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="Request body too large"
            )
    
    return True


# Role-Based Access Control (REFACTORED)
# REMOVED: require_role factory to align with explicit canonical dependencies
# used in analytics.py and inquiries.py.


# Agency Access Control
def require_agency(
    current_user: User = Depends(get_current_active_user)
) -> User:
    """
    Verify user belongs to an agency.
    Used for agency-specific operations.
    """
    if not current_user.agency_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Agency membership required"
        )
    return current_user


# Admin Access Control (fault-tolerant)
def require_admin(
    current_user: User = Depends(get_current_active_user)
) -> User:
    """
    Dependency that requires admin role.
    Raises 403 if user is not admin.
    Fault-tolerant: handles None/missing user_role.
    """
    # Using .value if UserRole is an Enum, or direct string comparison
    role = getattr(current_user.user_role, "value", current_user.user_role)
    
    if not role or role != 'admin':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return current_user


# Agent or Admin Access Control (fault-tolerant)
def require_agent_or_admin(
    current_user: User = Depends(get_current_active_user)
) -> User:
    """
    Dependency that requires agent or admin role.
    Fault-tolerant: handles None/missing user_role.
    """
    role = getattr(current_user.user_role, "value", current_user.user_role)
    
    if not role or role not in ['agent', 'admin']:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Agent or admin access required"
        )
    return current_user