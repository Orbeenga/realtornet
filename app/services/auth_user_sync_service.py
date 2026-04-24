"""
Helpers for keeping local user changes in sync with Supabase Auth metadata.
"""

from typing import Any
from uuid import UUID

from app.models.users import User
from app.utils.supabase_client import get_supabase_admin_client


class SupabaseUserSyncError(RuntimeError):
    """Raised when a local user change cannot be mirrored to Supabase Auth."""


def _read_response_value(source: Any, key: str) -> Any:
    """Support both SDK objects and dict-like response wrappers."""
    if source is None:
        return None
    if isinstance(source, dict):
        return source.get(key)
    return getattr(source, key, None)


def sync_supabase_auth_user_metadata(user: User) -> None:
    """
    Mirror backend-owned authorization metadata into Supabase Auth.

    Public clients should never become the source of truth for roles. The
    backend owns those fields in the local `users` table and pushes the same
    values into Supabase Auth whenever an admin changes them.
    """
    supabase_id = getattr(user, "supabase_id", None)
    if supabase_id is None:
        raise SupabaseUserSyncError(
            "User has no linked Supabase Auth identity to sync."
        )

    supabase_uuid = str(UUID(str(supabase_id)))
    client = get_supabase_admin_client()
    response = client.auth.admin.update_user_by_id(
        supabase_uuid,
        {
            "app_metadata": {
                "role": getattr(getattr(user, "user_role", None), "value", user.user_role),
                "is_admin": bool(user.is_admin),
            }
        },
    )

    auth_user = _read_response_value(response, "user")
    auth_user_id = _read_response_value(auth_user, "id")
    if str(auth_user_id) != supabase_uuid:
        raise SupabaseUserSyncError(
            "Supabase Auth user metadata update did not return the expected user."
        )


__all__ = [
    "SupabaseUserSyncError",
    "sync_supabase_auth_user_metadata",
]
