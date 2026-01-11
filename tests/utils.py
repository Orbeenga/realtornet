# tests/utils.py
"""
Test utility functions for authentication and API testing.
Provides helpers for creating auth tokens and headers.
"""

from typing import Dict, Optional
from uuid import UUID

from app.core.security import generate_access_token, generate_refresh_token


def get_auth_headers(
    supabase_id: UUID,
    user_id: int,
    user_role: Optional[str] = None,
    agency_id: Optional[int] = None
) -> Dict[str, str]:
    """
    Create authorization headers with Bearer token for a user.
    
    Args:
        supabase_id: User's Supabase UUID
        user_id: Internal database user_id
        user_role: Optional user role (seeker, agent, admin)
        agency_id: Optional agency ID for multi-tenant context
        
    Returns:
        Headers dictionary with Authorization Bearer token
        
    Example:
        headers = get_auth_headers(
            supabase_id=user.supabase_id,
            user_id=user.user_id,
            user_role="agent"
        )
    """
    access_token = generate_access_token(
        supabase_id=supabase_id,
        user_id=user_id,
        user_role=user_role,
        agency_id=agency_id
    )
    return {"Authorization": f"Bearer {access_token}"}


def get_refresh_token_str(
    supabase_id: UUID,
    user_id: int,
    user_role: Optional[str] = None,
    agency_id: Optional[int] = None
) -> str:
    """
    Create a refresh token for a user.
    
    Args:
        supabase_id: User's Supabase UUID
        user_id: Internal database user_id
        user_role: Optional user role
        agency_id: Optional agency ID
        
    Returns:
        JWT refresh token string
    """
    return generate_refresh_token(
        supabase_id=supabase_id,
        user_id=user_id,
        user_role=user_role,
        agency_id=agency_id
    )


def user_authentication_headers(
    client,
    email: str,
    password: str
) -> Dict[str, str]:
    """
    Get authorization headers by authenticating a user via login endpoint.
    
    Args:
        client: TestClient instance
        email: User email
        password: User password
        
    Returns:
        Headers dictionary with Authorization Bearer token
        
    Raises:
        AssertionError: If login fails
        
    Example:
        headers = user_authentication_headers(
            client, 
            "user@example.com", 
            "password"
        )
    """
    data = {"username": email, "password": password}
    response = client.post("/api/v1/auth/login", data=data)
    
    assert response.status_code == 200, f"Login failed: {response.json()}"
    
    tokens = response.json()
    return {"Authorization": f"Bearer {tokens['access_token']}"}


# Export utility functions
__all__ = [
    "get_auth_headers",
    "get_refresh_token_str",
    "user_authentication_headers"
]