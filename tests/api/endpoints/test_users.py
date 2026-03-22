# tests/api/endpoints/test_users.py
"""
Surgical API-layer tests for /users endpoints.
Covers permission branches, error paths, and happy paths.
"""

import io
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient


FAKE_PROFILE_URL = "https://supabase.example.com/storage/v1/object/public/profiles/u1.jpg"
JPEG_CONTENT = b"\xff\xd8\xff\xe0" + b"x" * 100


class TestReadUsers:

    def test_unauthenticated_returns_401(self, client: TestClient):
        response = client.get("/api/v1/users/")
        assert response.status_code == 401

    def test_non_admin_returns_403(
        self, client: TestClient, normal_user_token_headers
    ):
        response = client.get("/api/v1/users/", headers=normal_user_token_headers)
        assert response.status_code == 403

    def test_admin_reads_users_success(
        self, client: TestClient, admin_token_headers
    ):
        response = client.get("/api/v1/users/", headers=admin_token_headers)
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_admin_pagination_params_accepted(
        self, client: TestClient, admin_token_headers
    ):
        response = client.get(
            "/api/v1/users/",
            params={"skip": 0, "limit": 5},
            headers=admin_token_headers,
        )
        assert response.status_code == 200


class TestReadRealtors:

    def test_public_no_auth_required(self, client: TestClient):
        response = client.get("/api/v1/users/realtors")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_returns_realtor_list(self, client: TestClient, agent_user):
        response = client.get("/api/v1/users/realtors")
        assert response.status_code == 200
        assert isinstance(response.json(), list)


class TestReadUserById:

    def test_unauthenticated_returns_401(self, client: TestClient, normal_user):
        response = client.get(f"/api/v1/users/{normal_user.user_id}")
        assert response.status_code == 401

    def test_not_found_returns_404(
        self, client: TestClient, normal_user_token_headers
    ):
        response = client.get(
            "/api/v1/users/999999",
            headers=normal_user_token_headers,
        )
        assert response.status_code == 404

    def test_user_reads_own_profile(
        self, client: TestClient, normal_user, normal_user_token_headers
    ):
        response = client.get(
            f"/api/v1/users/{normal_user.user_id}",
            headers=normal_user_token_headers,
        )
        assert response.status_code == 200
        assert response.json()["user_id"] == normal_user.user_id

    def test_non_admin_cannot_read_other_user(
        self, client: TestClient, agent_user, normal_user_token_headers
    ):
        response = client.get(
            f"/api/v1/users/{agent_user.user_id}",
            headers=normal_user_token_headers,
        )
        assert response.status_code == 403
        assert response.json()["detail"] == "Not enough permissions"

    def test_admin_reads_any_user(
        self, client: TestClient, agent_user, admin_token_headers
    ):
        response = client.get(
            f"/api/v1/users/{agent_user.user_id}",
            headers=admin_token_headers,
        )
        assert response.status_code == 200
        assert response.json()["user_id"] == agent_user.user_id


class TestUpdateUserMe:

    def test_unauthenticated_returns_401(self, client: TestClient):
        response = client.put("/api/v1/users/me", json={"first_name": "New"})
        assert response.status_code == 401

    def test_updates_own_profile_success(
        self, client: TestClient, normal_user_token_headers
    ):
        response = client.put(
            "/api/v1/users/me",
            json={"first_name": "Updated", "phone_number": "  +111222333  "},
            headers=normal_user_token_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["first_name"] == "Updated"
        assert data["phone_number"] == "+111222333"

    def test_invalid_password_returns_422(
        self, client: TestClient, normal_user_token_headers
    ):
        response = client.put(
            "/api/v1/users/me",
            json={"password": "short"},
            headers=normal_user_token_headers,
        )
        assert response.status_code == 422


class TestUpdateUserAdmin:

    def test_unauthenticated_returns_401(self, client: TestClient, normal_user):
        response = client.put(
            f"/api/v1/users/{normal_user.user_id}",
            json={"first_name": "AdminEdit"},
        )
        assert response.status_code == 401

    def test_non_admin_returns_403(
        self, client: TestClient, normal_user, normal_user_token_headers
    ):
        response = client.put(
            f"/api/v1/users/{normal_user.user_id}",
            json={"first_name": "Nope"},
            headers=normal_user_token_headers,
        )
        assert response.status_code == 403

    def test_not_found_returns_404(
        self, client: TestClient, admin_token_headers
    ):
        response = client.put(
            "/api/v1/users/999999",
            json={"first_name": "Missing"},
            headers=admin_token_headers,
        )
        assert response.status_code == 404

    def test_admin_updates_user_success(
        self, client: TestClient, normal_user, admin_token_headers
    ):
        response = client.put(
            f"/api/v1/users/{normal_user.user_id}",
            json={"first_name": "AdminUpdated"},
            headers=admin_token_headers,
        )
        assert response.status_code == 200
        assert response.json()["first_name"] == "AdminUpdated"


class TestDeleteUser:

    def test_unauthenticated_returns_401(self, client: TestClient, normal_user):
        response = client.delete(f"/api/v1/users/{normal_user.user_id}")
        assert response.status_code == 401

    def test_non_admin_returns_403(
        self, client: TestClient, agent_user, normal_user_token_headers
    ):
        response = client.delete(
            f"/api/v1/users/{agent_user.user_id}",
            headers=normal_user_token_headers,
        )
        assert response.status_code == 403

    def test_not_found_returns_404(
        self, client: TestClient, admin_token_headers
    ):
        response = client.delete(
            "/api/v1/users/999999",
            headers=admin_token_headers,
        )
        assert response.status_code == 404

    def test_admin_cannot_delete_self(
        self, client: TestClient, admin_user, admin_token_headers
    ):
        response = client.delete(
            f"/api/v1/users/{admin_user.user_id}",
            headers=admin_token_headers,
        )
        assert response.status_code == 400
        assert response.json()["detail"] == "Cannot delete your own account"

    def test_admin_deletes_other_user_success(
        self, client: TestClient, normal_user, admin_token_headers
    ):
        response = client.delete(
            f"/api/v1/users/{normal_user.user_id}",
            headers=admin_token_headers,
        )
        assert response.status_code == 200
        assert response.json()["user_id"] == normal_user.user_id

    def test_deleted_user_not_returned_by_get(
        self, client: TestClient, normal_user, admin_token_headers
    ):
        delete_response = client.delete(
            f"/api/v1/users/{normal_user.user_id}",
            headers=admin_token_headers,
        )
        assert delete_response.status_code == 200

        response = client.get(
            f"/api/v1/users/{normal_user.user_id}",
            headers=admin_token_headers,
        )
        assert response.status_code == 404
        assert response.json()["detail"] == "User not found"


class TestUploadUserProfileImage:

    def _make_file(self, content=JPEG_CONTENT, filename="profile.jpg", content_type="image/jpeg"):
        return {"file": (filename, io.BytesIO(content), content_type)}

    def test_unauthenticated_returns_401(self, client: TestClient, normal_user):
        response = client.post(
            f"/api/v1/users/{normal_user.user_id}/upload-profile-image",
            files=self._make_file(),
        )
        assert response.status_code == 401

    def test_non_owner_non_admin_forbidden(
        self, client: TestClient, normal_user, owner_token_headers
    ):
        response = client.post(
            f"/api/v1/users/{normal_user.user_id}/upload-profile-image",
            files=self._make_file(),
            headers=owner_token_headers,
        )
        assert response.status_code == 403

    def test_user_not_found_returns_404(
        self, client: TestClient, admin_token_headers
    ):
        with patch(
            "app.api.endpoints.users.upload_profile_image",
            new_callable=AsyncMock,
            return_value=FAKE_PROFILE_URL,
        ):
            response = client.post(
                "/api/v1/users/999999/upload-profile-image",
                files=self._make_file(),
                headers=admin_token_headers,
            )
        assert response.status_code == 404

    def test_invalid_file_type_returns_400(
        self, client: TestClient, normal_user, normal_user_token_headers
    ):
        response = client.post(
            f"/api/v1/users/{normal_user.user_id}/upload-profile-image",
            files=self._make_file(content=b"abc", filename="x.pdf", content_type="application/pdf"),
            headers=normal_user_token_headers,
        )
        assert response.status_code == 400

    def test_file_too_large_returns_413(
        self, client: TestClient, normal_user, normal_user_token_headers
    ):
        big_content = b"x" * (5 * 1024 * 1024 + 1)
        response = client.post(
            f"/api/v1/users/{normal_user.user_id}/upload-profile-image",
            files=self._make_file(content=big_content),
            headers=normal_user_token_headers,
        )
        assert response.status_code == 413

    def test_owner_uploads_success(
        self, client: TestClient, normal_user, normal_user_token_headers
    ):
        with patch(
            "app.api.endpoints.users.upload_profile_image",
            new_callable=AsyncMock,
            return_value=FAKE_PROFILE_URL,
        ):
            response = client.post(
                f"/api/v1/users/{normal_user.user_id}/upload-profile-image",
                files=self._make_file(),
                headers=normal_user_token_headers,
            )
        assert response.status_code == 200
        assert response.json()["url"] == FAKE_PROFILE_URL

    def test_admin_uploads_for_any_user(
        self, client: TestClient, normal_user, admin_token_headers
    ):
        with patch(
            "app.api.endpoints.users.upload_profile_image",
            new_callable=AsyncMock,
            return_value=FAKE_PROFILE_URL,
        ):
            response = client.post(
                f"/api/v1/users/{normal_user.user_id}/upload-profile-image",
                files=self._make_file(),
                headers=admin_token_headers,
            )
        assert response.status_code == 200

    def test_storage_failure_returns_500(
        self, client: TestClient, normal_user, normal_user_token_headers
    ):
        with patch(
            "app.api.endpoints.users.upload_profile_image",
            new_callable=AsyncMock,
            side_effect=Exception("storage outage"),
        ):
            response = client.post(
                f"/api/v1/users/{normal_user.user_id}/upload-profile-image",
                files=self._make_file(),
                headers=normal_user_token_headers,
            )
        assert response.status_code == 500
