# app/utils/supabase_client.py
"""
Supabase client initialization with singleton pattern.
Provides both anon (user) and service role (admin) clients.
"""

from functools import lru_cache
from supabase import Client, create_client
from app.core.config import settings


@lru_cache(maxsize=1)
def get_supabase_client() -> Client:
    """
    Get Supabase client with anon key (for user operations).
    
    Uses singleton pattern via lru_cache to reuse connection.
    Respects Row Level Security (RLS) policies.
    
    Returns:
        Supabase client configured with anon key
    """
    if not settings.SUPABASE_URL or not settings.SUPABASE_ANON_KEY:
        raise ValueError(
            "Supabase configuration missing. "
            "Ensure SUPABASE_URL and SUPABASE_ANON_KEY are set in .env"
        )
    
    return create_client(
        supabase_url=settings.SUPABASE_URL,
        supabase_key=settings.SUPABASE_ANON_KEY
    )


@lru_cache(maxsize=1)
def get_supabase_admin_client() -> Client:
    """
    Get Supabase client with service role key (for admin operations).
    
    WARNING: This client BYPASSES Row Level Security (RLS).
    Use only for:
    - Admin operations
    - System maintenance
    - Data migrations
    
    Returns:
        Supabase client configured with service role key
        
    Raises:
        ValueError: If service role key not configured
    """
    if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_ROLE_KEY:
        raise ValueError(
            "Supabase admin configuration missing. "
            "Ensure SUPABASE_SERVICE_ROLE_KEY is set in .env for admin operations"
        )
    
    return create_client(
        supabase_url=settings.SUPABASE_URL,
        supabase_key=settings.SUPABASE_SERVICE_ROLE_KEY
    )


# Export
__all__ = ["get_supabase_client", "get_supabase_admin_client"]