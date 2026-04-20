from types import SimpleNamespace

from app.schemas.users import UserCreate, UserRole
from app.services.auth_registration_service import (
    SupabaseRegistrationError,
    create_supabase_auth_user_for_registration,
    delete_supabase_auth_user,
)


class _FakeAdminAuth:
    def __init__(self, response):
        self.response = response
        self.created_payloads = []
        self.deleted_ids = []
        self.admin = self

    def create_user(self, payload):
        self.created_payloads.append(payload)
        return self.response

    def delete_user(self, supabase_id):
        self.deleted_ids.append(supabase_id)


class _FakeClient:
    def __init__(self, response):
        self.auth = _FakeAdminAuth(response)


def test_create_supabase_auth_user_for_registration_sets_safe_metadata(monkeypatch):
    fake_client = _FakeClient(SimpleNamespace(user=SimpleNamespace(id="auth-user-123")))
    monkeypatch.setattr(
        "app.services.auth_registration_service.get_supabase_admin_client",
        lambda: fake_client,
    )
    user_in = UserCreate(
        email="new@example.com",
        password="ValidPass123!",
        first_name="New",
        last_name="User",
        phone_number="+1234567890",
        user_role=UserRole.SEEKER,
        profile_image_url=None,
    )

    supabase_id = create_supabase_auth_user_for_registration(user_in)

    assert supabase_id == "auth-user-123"
    payload = fake_client.auth.created_payloads[0]
    assert payload["email"] == "new@example.com"
    assert payload["password"] == "ValidPass123!"
    assert payload["email_confirm"] is False
    assert payload["user_metadata"]["full_name"] == "New User"
    assert payload["app_metadata"]["role"] == "seeker"
    assert payload["app_metadata"]["is_admin"] is False


def test_create_supabase_auth_user_for_registration_raises_when_id_missing(monkeypatch):
    fake_client = _FakeClient(SimpleNamespace(user=SimpleNamespace(id=None)))
    monkeypatch.setattr(
        "app.services.auth_registration_service.get_supabase_admin_client",
        lambda: fake_client,
    )
    user_in = UserCreate(
        email="broken@example.com",
        password="ValidPass123!",
        first_name="Broken",
        last_name="User",
        phone_number=None,
        user_role=UserRole.SEEKER,
        profile_image_url=None,
    )

    try:
        create_supabase_auth_user_for_registration(user_in)
        assert False, "Expected SupabaseRegistrationError"
    except SupabaseRegistrationError:
        pass


def test_delete_supabase_auth_user_calls_admin_delete(monkeypatch):
    fake_client = _FakeClient(SimpleNamespace(user=SimpleNamespace(id="ignored")))
    monkeypatch.setattr(
        "app.services.auth_registration_service.get_supabase_admin_client",
        lambda: fake_client,
    )

    delete_supabase_auth_user("auth-user-456")

    assert fake_client.auth.deleted_ids == ["auth-user-456"]
