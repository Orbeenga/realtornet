"""
Helpers for keeping public registration in sync with Supabase Auth.

The application keeps its own `users` table for domain data and audit fields,
but Supabase Auth is still the source of truth for identity. Public signup must
therefore create the Auth identity first, then mirror the same UUID into the
local user row.
"""

from typing import Any

from app.schemas.users import UserCreate
from app.utils.supabase_client import get_supabase_admin_client


class SupabaseRegistrationError(RuntimeError):
    """Raised when Supabase Auth signup cannot be completed safely."""


def _read_response_value(source: Any, key: str) -> Any:
    """
    Read a value from either an SDK object or a dictionary-like payload.

    The Supabase Python SDK has changed response wrappers across versions. This
    helper keeps the registration flow stable by accepting both shapes.
    """
    if source is None:
        return None
    if isinstance(source, dict):
        return source.get(key)
    return getattr(source, key, None)


def create_supabase_auth_user_for_registration(user_in: UserCreate) -> str:
    """
    Create the matching Supabase Auth identity for a public registration.

    We use the server-side admin client because roles are backend-owned in this
    codebase. That lets us stamp safe app metadata at creation time without
    trusting browser-supplied claims for authorization.
    """
    client = get_supabase_admin_client()
    full_name = f"{user_in.first_name} {user_in.last_name}".strip()
    response = client.auth.admin.create_user(
        {
            "email": user_in.email,
            "password": user_in.password,
            "email_confirm": False,
            "user_metadata": {
                "first_name": user_in.first_name,
                "last_name": user_in.last_name,
                "full_name": full_name,
            },
            # Authorization data belongs in app metadata because users can edit
            # normal profile metadata themselves.
            "app_metadata": {
                "role": user_in.user_role.value,
                "is_admin": False,
            },
        }
    )
    auth_user = _read_response_value(response, "user")
    auth_user_id = _read_response_value(auth_user, "id")
    if not auth_user_id:
        raise SupabaseRegistrationError(
            "Supabase Auth signup did not return a user id."
        )
    return str(auth_user_id)


def delete_supabase_auth_user(supabase_id: str) -> None:
    """
    Best-effort rollback for Auth users created before a local DB failure.

    Public registration should not leave behind an Auth identity if the local
    user/profile records fail to save.
    """
    client = get_supabase_admin_client()
    client.auth.admin.delete_user(supabase_id)


__all__ = [
    "SupabaseRegistrationError",
    "create_supabase_auth_user_for_registration",
    "delete_supabase_auth_user",
]
