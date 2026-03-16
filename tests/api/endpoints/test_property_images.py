# tests/api/endpoints/test_property_images.py
"""
API-layer tests for property images endpoints.
Covers all routes, all permission branches, all error paths.

Key difference from properties tests:
- upload (POST) and delete (DELETE) are async and call Supabase Storage.
- Those storage calls are ALWAYS mocked — we test our code, not Supabase.
- All other endpoints hit the real DB via TestClient normally.
"""
import pytest
import io
from unittest.mock import patch, AsyncMock, MagicMock
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Shared test data
# ---------------------------------------------------------------------------

FAKE_IMAGE_URL = "https://supabase.example.com/storage/v1/object/public/images/test.jpg"
JPEG_CONTENT = b"\xff\xd8\xff\xe0" + b"x" * 100  # Minimal valid-ish JPEG bytes
PNG_CONTENT = b"\x89PNG\r\n\x1a\n" + b"x" * 100


# ===========================================================================
# GET /property/{property_id}  —  list images for a property
# ===========================================================================

class TestReadPropertyImages:

    def test_property_not_found_returns_404(self, client: TestClient):
        response = client.get("/api/v1/property-images/property/999999")
        assert response.status_code == 404
        assert "property" in response.json()["detail"].lower()

    def test_returns_images_for_existing_property(
        self, client: TestClient, verified_property, sample_property_image
    ):
        response = client.get(
            f"/api/v1/property-images/property/{verified_property.property_id}"
        )
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_returns_empty_list_for_property_with_no_images(
        self, client: TestClient, verified_property
    ):
        response = client.get(
            f"/api/v1/property-images/property/{verified_property.property_id}"
        )
        assert response.status_code == 200
        assert response.json() == []

    def test_public_endpoint_no_auth_required(
        self, client: TestClient, verified_property
    ):
        """No token needed — public endpoint."""
        response = client.get(
            f"/api/v1/property-images/property/{verified_property.property_id}"
        )
        assert response.status_code == 200


# ===========================================================================
# GET /{image_id}  —  single image
# ===========================================================================

class TestReadPropertyImage:

    def test_not_found_returns_404(self, client: TestClient):
        response = client.get("/api/v1/property-images/999999")
        assert response.status_code == 404
        assert "image" in response.json()["detail"].lower()

    def test_returns_image(
        self, client: TestClient, sample_property_image
    ):
        response = client.get(
            f"/api/v1/property-images/{sample_property_image.image_id}"
        )
        assert response.status_code == 200
        assert response.json()["image_id"] == sample_property_image.image_id

    def test_public_endpoint_no_auth_required(
        self, client: TestClient, sample_property_image
    ):
        response = client.get(
            f"/api/v1/property-images/{sample_property_image.image_id}"
        )
        assert response.status_code == 200


# ===========================================================================
# POST /property/{property_id}/upload  —  upload image
# ===========================================================================

class TestUploadPropertyImage:
    """
    Storage calls (upload_property_image) are mocked in every test.
    We test our permission/validation logic, not Supabase.
    """

    def _make_file(self, content=JPEG_CONTENT, filename="test.jpg",
                   content_type="image/jpeg"):
        return {"file": (filename, io.BytesIO(content), content_type)}

    def test_unauthenticated_returns_401(
        self, client: TestClient, verified_property
    ):
        response = client.post(
            f"/api/v1/property-images/property/{verified_property.property_id}/upload",
            files=self._make_file()
        )
        assert response.status_code == 401

    def test_property_not_found_returns_404(
        self, client: TestClient, owner_token_headers
    ):
        with patch(
            "app.api.endpoints.property_images.upload_property_image",
            new_callable=AsyncMock,
            return_value=FAKE_IMAGE_URL
        ):
            response = client.post(
                "/api/v1/property-images/property/999999/upload",
                files=self._make_file(),
                headers=owner_token_headers
            )
        assert response.status_code == 404

    def test_non_owner_non_admin_forbidden(
        self, client: TestClient, normal_user_token_headers, verified_property
    ):
        with patch(
            "app.api.endpoints.property_images.upload_property_image",
            new_callable=AsyncMock,
            return_value=FAKE_IMAGE_URL
        ):
            response = client.post(
                f"/api/v1/property-images/property/{verified_property.property_id}/upload",
                files=self._make_file(),
                headers=normal_user_token_headers
            )
        assert response.status_code == 403
        assert "permissions" in response.json()["detail"].lower()

    def test_invalid_file_type_returns_400(
        self, client: TestClient, owner_token_headers,
        unverified_property_owned_by_agent
    ):
        response = client.post(
            f"/api/v1/property-images/property/"
            f"{unverified_property_owned_by_agent.property_id}/upload",
            files=self._make_file(
                content=b"not an image", filename="doc.pdf",
                content_type="application/pdf"
            ),
            headers=owner_token_headers
        )
        assert response.status_code == 400
        assert "file type" in response.json()["detail"].lower()

    def test_file_too_large_returns_413(
        self, client: TestClient, owner_token_headers,
        unverified_property_owned_by_agent
    ):
        big_content = b"x" * (10 * 1024 * 1024 + 1)  # 10MB + 1 byte
        response = client.post(
            f"/api/v1/property-images/property/"
            f"{unverified_property_owned_by_agent.property_id}/upload",
            files=self._make_file(content=big_content),
            headers=owner_token_headers
        )
        assert response.status_code == 413

    def test_owner_uploads_successfully(
        self, client: TestClient, owner_token_headers,
        unverified_property_owned_by_agent
    ):
        with patch(
            "app.api.endpoints.property_images.upload_property_image",
            new_callable=AsyncMock,
            return_value=FAKE_IMAGE_URL
        ):
            response = client.post(
                f"/api/v1/property-images/property/"
                f"{unverified_property_owned_by_agent.property_id}/upload",
                files=self._make_file(),
                headers=owner_token_headers
            )
        assert response.status_code == 201
        data = response.json()
        assert "image_id" in data
        assert data["image_url"] == FAKE_IMAGE_URL

    def test_admin_uploads_to_any_property(
        self, client: TestClient, admin_token_headers, verified_property
    ):
        with patch(
            "app.api.endpoints.property_images.upload_property_image",
            new_callable=AsyncMock,
            return_value=FAKE_IMAGE_URL
        ):
            response = client.post(
                f"/api/v1/property-images/property/"
                f"{verified_property.property_id}/upload",
                files=self._make_file(),
                headers=admin_token_headers
            )
        assert response.status_code == 201

    def test_upload_png_accepted(
        self, client: TestClient, owner_token_headers,
        unverified_property_owned_by_agent
    ):
        with patch(
            "app.api.endpoints.property_images.upload_property_image",
            new_callable=AsyncMock,
            return_value=FAKE_IMAGE_URL
        ):
            response = client.post(
                f"/api/v1/property-images/property/"
                f"{unverified_property_owned_by_agent.property_id}/upload",
                files=self._make_file(
                    content=PNG_CONTENT,
                    filename="test.png",
                    content_type="image/png"
                ),
                headers=owner_token_headers
            )
        assert response.status_code == 201

    def test_upload_sets_primary_flag(
        self, client: TestClient, owner_token_headers,
        unverified_property_owned_by_agent
    ):
        with patch(
            "app.api.endpoints.property_images.upload_property_image",
            new_callable=AsyncMock,
            return_value=FAKE_IMAGE_URL
        ):
            response = client.post(
                f"/api/v1/property-images/property/"
                f"{unverified_property_owned_by_agent.property_id}/upload"
                f"?is_primary=true",
                files=self._make_file(),
                headers=owner_token_headers
            )
        assert response.status_code == 201
        assert response.json()["is_primary"] is True

    def test_storage_failure_returns_500(
        self, client: TestClient, owner_token_headers,
        unverified_property_owned_by_agent
    ):
        with patch(
            "app.api.endpoints.property_images.upload_property_image",
            new_callable=AsyncMock,
            side_effect=Exception("Supabase unreachable")
        ):
            response = client.post(
                f"/api/v1/property-images/property/"
                f"{unverified_property_owned_by_agent.property_id}/upload",
                files=self._make_file(),
                headers=owner_token_headers
            )
        assert response.status_code == 500
        assert "upload" in response.json()["detail"].lower()


# ===========================================================================
# PUT /{image_id}  —  update image metadata
# ===========================================================================

class TestUpdatePropertyImage:

    def test_not_found_returns_404(
        self, client: TestClient, owner_token_headers
    ):
        response = client.put(
            "/api/v1/property-images/999999",
            json={"caption": "new caption"},
            headers=owner_token_headers
        )
        assert response.status_code == 404

    def test_unauthenticated_returns_401(
        self, client: TestClient, sample_property_image
    ):
        response = client.put(
            f"/api/v1/property-images/{sample_property_image.image_id}",
            json={"caption": "new caption"}
        )
        assert response.status_code == 401

    def test_non_owner_non_admin_forbidden(
        self, client: TestClient, normal_user_token_headers, sample_property_image
    ):
        response = client.put(
            f"/api/v1/property-images/{sample_property_image.image_id}",
            json={"caption": "new caption"},
            headers=normal_user_token_headers
        )
        assert response.status_code == 403

    def test_owner_updates_caption(
        self, client: TestClient, owner_token_headers, sample_property_image
    ):
        response = client.put(
            f"/api/v1/property-images/{sample_property_image.image_id}",
            json={"caption": "Updated caption"},
            headers=owner_token_headers
        )
        assert response.status_code == 200
        assert response.json()["caption"] == "Updated caption"

    def test_admin_updates_any_image(
        self, client: TestClient, admin_token_headers, sample_property_image
    ):
        response = client.put(
            f"/api/v1/property-images/{sample_property_image.image_id}",
            json={"caption": "Admin updated"},
            headers=admin_token_headers
        )
        assert response.status_code == 200

    def test_set_primary_unsets_others(
        self, client: TestClient, owner_token_headers,
        sample_property_image, second_property_image
    ):
        """Setting one image as primary should auto-unset the other."""
        response = client.put(
            f"/api/v1/property-images/{second_property_image.image_id}",
            json={"is_primary": True},
            headers=owner_token_headers
        )
        assert response.status_code == 200
        assert response.json()["is_primary"] is True


# ===========================================================================
# DELETE /{image_id}  —  hard delete image
# ===========================================================================

class TestDeletePropertyImage:

    def test_not_found_returns_404(
        self, client: TestClient, owner_token_headers
    ):
        response = client.delete(
            "/api/v1/property-images/999999",
            headers=owner_token_headers
        )
        assert response.status_code == 404

    def test_unauthenticated_returns_401(
        self, client: TestClient, sample_property_image
    ):
        response = client.delete(
            f"/api/v1/property-images/{sample_property_image.image_id}"
        )
        assert response.status_code == 401

    def test_non_owner_non_admin_forbidden(
        self, client: TestClient, normal_user_token_headers, sample_property_image
    ):
        with patch(
            "app.api.endpoints.property_images.delete_property_image",
            new_callable=AsyncMock
        ):
            response = client.delete(
                f"/api/v1/property-images/{sample_property_image.image_id}",
                headers=normal_user_token_headers
            )
        assert response.status_code == 403

    def test_owner_deletes_successfully(
        self, client: TestClient, owner_token_headers, sample_property_image
    ):
        with patch(
            "app.api.endpoints.property_images.delete_property_image",
            new_callable=AsyncMock
        ):
            response = client.delete(
                f"/api/v1/property-images/{sample_property_image.image_id}",
                headers=owner_token_headers
            )
        assert response.status_code == 200
        assert "deleted" in response.json()["message"].lower()

    def test_admin_deletes_any_image(
        self, client: TestClient, admin_token_headers, sample_property_image
    ):
        with patch(
            "app.api.endpoints.property_images.delete_property_image",
            new_callable=AsyncMock
        ):
            response = client.delete(
                f"/api/v1/property-images/{sample_property_image.image_id}",
                headers=admin_token_headers
            )
        assert response.status_code == 200

    def test_storage_failure_returns_500(
        self, client: TestClient, owner_token_headers, sample_property_image
    ):
        with patch(
            "app.api.endpoints.property_images.delete_property_image",
            new_callable=AsyncMock,
            side_effect=Exception("Storage error")
        ):
            response = client.delete(
                f"/api/v1/property-images/{sample_property_image.image_id}",
                headers=owner_token_headers
            )
        assert response.status_code == 500
        assert "delete" in response.json()["detail"].lower()


# ===========================================================================
# PUT /property/{property_id}/reorder
# ===========================================================================

class TestReorderPropertyImages:

    def test_property_not_found_returns_404(
        self, client: TestClient, owner_token_headers
    ):
        response = client.put(
            "/api/v1/property-images/property/999999/reorder",
            json=[1, 2, 3],
            headers=owner_token_headers
        )
        assert response.status_code == 404

    def test_unauthenticated_returns_401(
        self, client: TestClient, verified_property, sample_property_image
    ):
        response = client.put(
            f"/api/v1/property-images/property/{verified_property.property_id}/reorder",
            json=[sample_property_image.image_id]
        )
        assert response.status_code == 401

    def test_non_owner_non_admin_forbidden(
        self, client: TestClient, normal_user_token_headers,
        unverified_property_owned_by_agent, sample_property_image
    ):
        response = client.put(
            f"/api/v1/property-images/property/"
            f"{unverified_property_owned_by_agent.property_id}/reorder",
            json=[sample_property_image.image_id],
            headers=normal_user_token_headers
        )
        assert response.status_code == 403

    def test_image_not_belonging_to_property_returns_400(
        self, client: TestClient, owner_token_headers,
        unverified_property_owned_by_agent
    ):
        """Image ID that doesn't belong to this property → 400."""
        response = client.put(
            f"/api/v1/property-images/property/"
            f"{unverified_property_owned_by_agent.property_id}/reorder",
            json=[999999],  # Non-existent image ID
            headers=owner_token_headers
        )
        assert response.status_code == 400
        assert "does not belong" in response.json()["detail"].lower()

    def test_owner_reorders_successfully(
        self, client: TestClient, owner_token_headers,
        unverified_property_owned_by_agent,
        sample_property_image, second_property_image
    ):
        new_order = [
            second_property_image.image_id,
            sample_property_image.image_id
        ]
        response = client.put(
            f"/api/v1/property-images/property/"
            f"{unverified_property_owned_by_agent.property_id}/reorder",
            json=new_order,
            headers=owner_token_headers
        )
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_admin_reorders_any_property(
        self, client: TestClient, admin_token_headers,
        unverified_property_owned_by_agent, sample_property_image
    ):
        response = client.put(
            f"/api/v1/property-images/property/"
            f"{unverified_property_owned_by_agent.property_id}/reorder",
            json=[sample_property_image.image_id],
            headers=admin_token_headers
        )
        assert response.status_code == 200


# ===========================================================================
# POST /{image_id}/set-primary
# ===========================================================================

class TestSetPrimaryImage:

    def test_not_found_returns_404(
        self, client: TestClient, owner_token_headers
    ):
        response = client.post(
            "/api/v1/property-images/999999/set-primary",
            headers=owner_token_headers
        )
        assert response.status_code == 404

    def test_unauthenticated_returns_401(
        self, client: TestClient, sample_property_image
    ):
        response = client.post(
            f"/api/v1/property-images/{sample_property_image.image_id}/set-primary"
        )
        assert response.status_code == 401

    def test_non_owner_non_admin_forbidden(
        self, client: TestClient, normal_user_token_headers, sample_property_image
    ):
        response = client.post(
            f"/api/v1/property-images/{sample_property_image.image_id}/set-primary",
            headers=normal_user_token_headers
        )
        assert response.status_code == 403

    def test_owner_sets_primary(
        self, client: TestClient, owner_token_headers, sample_property_image
    ):
        response = client.post(
            f"/api/v1/property-images/{sample_property_image.image_id}/set-primary",
            headers=owner_token_headers
        )
        assert response.status_code == 200
        assert response.json()["is_primary"] is True

    def test_admin_sets_primary_on_any_image(
        self, client: TestClient, admin_token_headers, sample_property_image
    ):
        response = client.post(
            f"/api/v1/property-images/{sample_property_image.image_id}/set-primary",
            headers=admin_token_headers
        )
        assert response.status_code == 200
        assert response.json()["is_primary"] is True