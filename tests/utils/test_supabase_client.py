from unittest.mock import Mock

import pytest

from app.core.config import settings
from app.utils import supabase_client


@pytest.fixture(autouse=True)
def clear_supabase_client_caches() -> None:
    supabase_client.get_supabase_client.cache_clear()
    supabase_client.get_supabase_admin_client.cache_clear()


def test_get_supabase_client_requires_url_and_anon_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "SUPABASE_URL", "")
    monkeypatch.setattr(settings, "SUPABASE_ANON_KEY", "")

    with pytest.raises(ValueError, match="Supabase configuration missing"):
        supabase_client.get_supabase_client()


def test_get_supabase_client_uses_anon_key(monkeypatch: pytest.MonkeyPatch) -> None:
    created = Mock()
    create_client = Mock(return_value=created)
    monkeypatch.setattr(settings, "SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setattr(settings, "SUPABASE_ANON_KEY", "anon-key")
    monkeypatch.setattr(supabase_client, "create_client", create_client)

    assert supabase_client.get_supabase_client() is created
    create_client.assert_called_once_with(
        supabase_url="https://example.supabase.co",
        supabase_key="anon-key",
    )


def test_get_supabase_admin_client_requires_service_role_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setattr(settings, "SUPABASE_SERVICE_ROLE_KEY", "")

    with pytest.raises(ValueError, match="Supabase admin configuration missing"):
        supabase_client.get_supabase_admin_client()


def test_get_supabase_admin_client_uses_service_role_key(monkeypatch: pytest.MonkeyPatch) -> None:
    created = Mock()
    create_client = Mock(return_value=created)
    monkeypatch.setattr(settings, "SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setattr(settings, "SUPABASE_SERVICE_ROLE_KEY", "service-role-key")
    monkeypatch.setattr(supabase_client, "create_client", create_client)

    assert supabase_client.get_supabase_admin_client() is created
    create_client.assert_called_once_with(
        supabase_url="https://example.supabase.co",
        supabase_key="service-role-key",
    )
