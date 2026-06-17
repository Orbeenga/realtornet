# app/utils/supabase_client.py
"""
Supabase client initialization with singleton pattern.
Provides an admin client using the secret key for backend Supabase operations.
"""

from functools import lru_cache
from supabase import Client, create_client
from app.core.config import settings


@lru_cache(maxsize=1)
def get_supabase_admin_client() -> Client:
    """
    Get Supabase client with secret key (for admin operations).

    WARNING: This client BYPASSES Row Level Security (RLS).
    Use only for:
    - Admin operations
    - System maintenance
    - Data migrations

    Returns:
        Supabase client configured with secret key

    Raises:
        ValueError: If secret key not configured
    """
    url = settings.SUPABASE_URL
    key = settings.SUPABASE_SECRET_KEY

    if not url or not key:
        raise ValueError(
            "Supabase configuration missing. "
            "Ensure SUPABASE_URL and SUPABASE_SECRET_KEY are set in .env"
        )

    return create_client(supabase_url=url, supabase_key=key)


# Export
__all__ = ["get_supabase_admin_client"]
