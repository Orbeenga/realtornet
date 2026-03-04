# tests/utils/__init__.py
"""Test utilities and helper functions."""

from typing import Dict
from uuid import UUID
from app.core.security import generate_access_token


def get_auth_headers(
    supabase_id,
    user_id: int,
    user_role: str,
) -> Dict[str, str]:
    """
    Generate Bearer token auth headers for API tests.
    Uses generate_access_token with settings.SECRET_KEY so the app
    can validate the token — a hardcoded test key would always fail.

    Args:
        supabase_id: User's Supabase UUID (UUID object or string)
        user_id: Internal database user ID
        user_role: User role string (e.g. 'seeker', 'agent', 'admin')

    Returns:
        Dict with Authorization header containing valid Bearer token
    """
    token = generate_access_token(
        supabase_id=UUID(str(supabase_id)),
        user_id=user_id,
        user_role=user_role,
    )
    return {"Authorization": f"Bearer {token}"}