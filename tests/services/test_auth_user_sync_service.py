from types import SimpleNamespace
from uuid import uuid4
from unittest.mock import Mock, patch

import pytest

from app.models.users import UserRole
from app.services.auth_user_sync_service import (
    SupabaseUserSyncError,
    _read_response_value,
    sync_supabase_auth_user_metadata,
)


def make_user(**overrides):
    data = {
        "supabase_id": str(uuid4()),
        "user_role": UserRole.AGENT,
        "is_admin": False,
    }
    data.update(overrides)
    return SimpleNamespace(**data)


def test_read_response_value_supports_dict_and_object():
    assert _read_response_value({"id": "abc"}, "id") == "abc"
    assert _read_response_value(SimpleNamespace(id="xyz"), "id") == "xyz"
    assert _read_response_value(None, "id") is None


def test_sync_supabase_auth_user_metadata_updates_role_and_admin_flags():
    user = make_user(user_role=UserRole.AGENT, is_admin=True)
    mock_update = Mock(
        return_value=SimpleNamespace(user=SimpleNamespace(id=user.supabase_id))
    )
    mock_client = SimpleNamespace(
        auth=SimpleNamespace(admin=SimpleNamespace(update_user_by_id=mock_update))
    )

    with patch(
        "app.services.auth_user_sync_service.get_supabase_admin_client",
        return_value=mock_client,
    ):
        sync_supabase_auth_user_metadata(user)

    mock_update.assert_called_once_with(
        user.supabase_id,
        {"app_metadata": {"role": "agent", "is_admin": True, "agency_id": None}},
    )


def test_sync_supabase_auth_user_metadata_accepts_string_roles():
    user = make_user(user_role="seeker")
    mock_update = Mock(
        return_value=SimpleNamespace(user=SimpleNamespace(id=user.supabase_id))
    )
    mock_client = SimpleNamespace(
        auth=SimpleNamespace(admin=SimpleNamespace(update_user_by_id=mock_update))
    )

    with patch(
        "app.services.auth_user_sync_service.get_supabase_admin_client",
        return_value=mock_client,
    ):
        sync_supabase_auth_user_metadata(user)

    mock_update.assert_called_once_with(
        user.supabase_id,
        {"app_metadata": {"role": "seeker", "is_admin": False, "agency_id": None}},
    )


def test_sync_supabase_auth_user_metadata_requires_linked_identity():
    with pytest.raises(SupabaseUserSyncError, match="no linked Supabase Auth identity"):
        sync_supabase_auth_user_metadata(make_user(supabase_id=None))


def test_sync_supabase_auth_user_metadata_requires_expected_user_in_response():
    user = make_user()
    mock_client = SimpleNamespace(
        auth=SimpleNamespace(
            admin=SimpleNamespace(
                update_user_by_id=Mock(
                    return_value=SimpleNamespace(user=SimpleNamespace(id=str(uuid4())))
                )
            )
        )
    )

    with patch(
        "app.services.auth_user_sync_service.get_supabase_admin_client",
        return_value=mock_client,
    ):
        with pytest.raises(SupabaseUserSyncError, match="did not return the expected user"):
            sync_supabase_auth_user_metadata(user)
