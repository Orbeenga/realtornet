# tests/api/endpoints/test_profiles.py
"""
Surgical API-layer tests for /profiles endpoints.
"""
from fastapi.testclient import TestClient

from app.api.endpoints import profiles as profiles_api
from app.models.profiles import Profile


class TestReadProfileMe:

    def test_unauthenticated_returns_401(self, client: TestClient):
        response = client.get("/api/v1/profiles/me")
        assert response.status_code == 401

    def test_profile_missing_returns_404(
        self, client: TestClient, normal_user_token_headers
    ):
        response = client.get(
            "/api/v1/profiles/me",
            headers=normal_user_token_headers
        )
        assert response.status_code == 404

    def test_read_profile_me_success(
        self, client: TestClient, db, normal_user, normal_user_token_headers
    ):
        profile = Profile(user_id=normal_user.user_id, full_name="Test User")
        db.add(profile)
        db.flush()
        db.refresh(profile)

        response = client.get(
            "/api/v1/profiles/me",
            headers=normal_user_token_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["user_id"] == normal_user.user_id


class TestReadProfileById:

    def test_profile_not_found_returns_404(
        self, client: TestClient, normal_user_token_headers
    ):
        response = client.get(
            "/api/v1/profiles/999999",
            headers=normal_user_token_headers
        )
        assert response.status_code == 404

    def test_user_can_read_own_profile(
        self, client: TestClient, db, normal_user, normal_user_token_headers
    ):
        profile = Profile(user_id=normal_user.user_id, full_name="Own Profile")
        db.add(profile)
        db.flush()
        db.refresh(profile)

        response = client.get(
            f"/api/v1/profiles/{profile.profile_id}",
            headers=normal_user_token_headers
        )
        assert response.status_code == 200

    def test_admin_can_read_any_profile(
        self, client: TestClient, db, normal_user, admin_token_headers
    ):
        profile = Profile(user_id=normal_user.user_id, full_name="Admin Read")
        db.add(profile)
        db.flush()
        db.refresh(profile)

        response = client.get(
            f"/api/v1/profiles/{profile.profile_id}",
            headers=admin_token_headers
        )
        assert response.status_code == 200

    def test_non_owner_cannot_read_profile_returns_403(
        self, client: TestClient, db, normal_user, agent_token_headers
    ):
        profile = Profile(user_id=normal_user.user_id, full_name="Blocked Read")
        db.add(profile)
        db.flush()
        db.refresh(profile)

        response = client.get(
            f"/api/v1/profiles/{profile.profile_id}",
            headers=agent_token_headers
        )
        assert response.status_code == 403


class TestCreateProfile:

    def test_unauthenticated_returns_401(self, client: TestClient):
        response = client.post("/api/v1/profiles/", json={"full_name": "Test"})
        assert response.status_code == 401

    def test_create_profile_success(
        self, client: TestClient, normal_user_token_headers
    ):
        response = client.post(
            "/api/v1/profiles/",
            json={"full_name": "Test User", "bio": "Test bio"},
            headers=normal_user_token_headers
        )
        assert response.status_code == 201
        data = response.json()
        assert data["deleted_at"] is None
        assert data["created_by"] is not None

    def test_existing_profile_returns_400(
        self, client: TestClient, normal_user_token_headers
    ):
        client.post(
            "/api/v1/profiles/",
            json={"full_name": "First"},
            headers=normal_user_token_headers
        )
        response = client.post(
            "/api/v1/profiles/",
            json={"full_name": "Second"},
            headers=normal_user_token_headers
        )
        assert response.status_code == 400


class TestUpdateProfileMe:

    def test_unauthenticated_returns_401(self, client: TestClient):
        response = client.put("/api/v1/profiles/me", json={"bio": "Update"})
        assert response.status_code == 401

    def test_profile_missing_returns_404(
        self, client: TestClient, normal_user_token_headers
    ):
        response = client.put(
            "/api/v1/profiles/me",
            json={"bio": "Update"},
            headers=normal_user_token_headers
        )
        assert response.status_code == 404

    def test_update_profile_me_success(
        self, client: TestClient, db, normal_user, normal_user_token_headers
    ):
        profile = Profile(user_id=normal_user.user_id, full_name="Updatable")
        db.add(profile)
        db.flush()
        db.refresh(profile)

        response = client.put(
            "/api/v1/profiles/me",
            json={"bio": "Updated bio"},
            headers=normal_user_token_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["bio"] == "Updated bio"


class TestUploadAvatar:

    def test_profile_missing_returns_404(
        self, client: TestClient, normal_user_token_headers
    ):
        response = client.post(
            "/api/v1/profiles/me/avatar",
            headers=normal_user_token_headers,
            files={"file": ("avatar.png", b"data", "image/png")}
        )
        assert response.status_code == 404

    def test_invalid_file_type_returns_400(
        self, client: TestClient, db, normal_user, normal_user_token_headers
    ):
        profile = Profile(user_id=normal_user.user_id, full_name="Avatar User")
        db.add(profile)
        db.flush()
        db.refresh(profile)

        response = client.post(
            "/api/v1/profiles/me/avatar",
            headers=normal_user_token_headers,
            files={"file": ("avatar.txt", b"data", "text/plain")}
        )
        assert response.status_code == 400

    def test_file_too_large_returns_413(
        self, client: TestClient, db, normal_user, normal_user_token_headers
    ):
        profile = Profile(user_id=normal_user.user_id, full_name="Avatar User")
        db.add(profile)
        db.flush()
        db.refresh(profile)

        large_bytes = b"a" * (2 * 1024 * 1024 + 1)
        response = client.post(
            "/api/v1/profiles/me/avatar",
            headers=normal_user_token_headers,
            files={"file": ("avatar.png", large_bytes, "image/png")}
        )
        assert response.status_code == 413

    def test_upload_avatar_success(
        self, client: TestClient, db, normal_user, normal_user_token_headers, monkeypatch
    ):
        profile = Profile(user_id=normal_user.user_id, full_name="Avatar User")
        db.add(profile)
        db.flush()
        db.refresh(profile)

        async def _fake_upload(*args, **kwargs):
            return "https://example.com/avatar.png"

        monkeypatch.setattr(profiles_api, "upload_profile_image", _fake_upload)

        response = client.post(
            "/api/v1/profiles/me/avatar",
            headers=normal_user_token_headers,
            files={"file": ("avatar.png", b"data", "image/png")}
        )
        assert response.status_code == 200

    def test_upload_avatar_exception_returns_500(
        self, client: TestClient, db, normal_user, normal_user_token_headers, monkeypatch
    ):
        profile = Profile(user_id=normal_user.user_id, full_name="Avatar User")
        db.add(profile)
        db.flush()
        db.refresh(profile)

        async def _fail_upload(*args, **kwargs):
            raise Exception("boom")

        monkeypatch.setattr(profiles_api, "upload_profile_image", _fail_upload)

        response = client.post(
            "/api/v1/profiles/me/avatar",
            headers=normal_user_token_headers,
            files={"file": ("avatar.png", b"data", "image/png")}
        )
        assert response.status_code == 500


class TestDeleteAvatar:

    def test_profile_missing_returns_404(
        self, client: TestClient, normal_user_token_headers
    ):
        response = client.delete(
            "/api/v1/profiles/me/avatar",
            headers=normal_user_token_headers
        )
        assert response.status_code == 404

    def test_no_avatar_returns_400(
        self, client: TestClient, db, normal_user, normal_user_token_headers, monkeypatch
    ):
        profile = Profile(user_id=normal_user.user_id, full_name="Avatar User")
        profile.profile_picture_url = None
        db.add(profile)
        db.flush()
        db.refresh(profile)

        monkeypatch.setattr(profiles_api.profile_crud, "get_by_user_id", lambda *args, **kwargs: profile)
        response = client.delete(
            "/api/v1/profiles/me/avatar",
            headers=normal_user_token_headers
        )
        assert response.status_code == 400

    def test_delete_avatar_success(
        self, client: TestClient, db, normal_user, normal_user_token_headers, monkeypatch
    ):
        profile = Profile(user_id=normal_user.user_id, full_name="Avatar User")
        profile.profile_picture_url = "https://example.com/avatar.png"
        db.add(profile)
        db.flush()
        db.refresh(profile)

        monkeypatch.setattr(profiles_api.profile_crud, "get_by_user_id", lambda *args, **kwargs: profile)
        response = client.delete(
            "/api/v1/profiles/me/avatar",
            headers=normal_user_token_headers
        )
        assert response.status_code == 200
