from unittest.mock import Mock

import pytest

from app.core.config import settings
from app.utils import supabase_client


@pytest.fixture(autouse=True)
def clear_supabase_admin_client_cache() -> None:
    supabase_client.get_supabase_admin_client.cache_clear()


def test_get_supabase_admin_client_requires_secret_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "SUPABASE_URL", "")
    monkeypatch.setattr(settings, "SUPABASE_SECRET_KEY", "")

    with pytest.raises(ValueError, match="Supabase configuration missing"):
        supabase_client.get_supabase_admin_client()


def test_get_supabase_admin_client_uses_secret_key(monkeypatch: pytest.MonkeyPatch) -> None:
    created = Mock()
    create_client = Mock(return_value=created)
    monkeypatch.setattr(settings, "SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setattr(settings, "SUPABASE_SECRET_KEY", "secret-key")
    monkeypatch.setattr(supabase_client, "create_client", create_client)

    assert supabase_client.get_supabase_admin_client() is created
    create_client.assert_called_once_with(
        supabase_url="https://example.supabase.co",
        supabase_key="secret-key",
    )
