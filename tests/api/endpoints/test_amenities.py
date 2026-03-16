# tests/api/endpoints/test_amenities.py
"""
Surgical API-layer tests for app/api/endpoints/amenities.py
Target: 100% endpoint coverage
All tests go through the HTTP layer via TestClient.
Amenities has no audit trail (reference table — no created_by/updated_by/deleted_at).
Uses hard delete, not soft delete.
"""
import pytest
from starlette.testclient import TestClient


class TestReadAmenities:
    def test_read_amenities_no_auth_returns_200(self, client: TestClient):
        """Public endpoint — no auth required."""
        response = client.get("/api/v1/amenities/")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_read_amenities_with_category_filter(self, client: TestClient, db):
        """Category filter hits get_by_category branch."""
        response = client.get("/api/v1/amenities/?category=Outdoor")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_read_amenities_pagination(self, client: TestClient):
        """skip/limit params are accepted."""
        response = client.get("/api/v1/amenities/?skip=0&limit=5")
        assert response.status_code == 200


class TestReadAmenityCategories:
    def test_read_categories_returns_list(self, client: TestClient):
        """Public endpoint — returns list of strings."""
        response = client.get("/api/v1/amenities/categories")
        assert response.status_code == 200
        assert isinstance(response.json(), list)


class TestReadAmenity:
    def test_read_amenity_success(self, client: TestClient, sample_amenity):
        """GET /{amenity_id} — existing amenity returns 200."""
        response = client.get(f"/api/v1/amenities/{sample_amenity.amenity_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["amenity_id"] == sample_amenity.amenity_id
        assert data["name"] == sample_amenity.name

    def test_read_amenity_not_found_returns_404(self, client: TestClient):
        """GET /{amenity_id} — non-existent ID returns 404."""
        response = client.get("/api/v1/amenities/999999")
        assert response.status_code == 404


class TestCreateAmenity:
    def test_create_amenity_success(
        self, client: TestClient, admin_token_headers
    ):
        """Admin creates a new amenity — 201 returned."""
        response = client.post(
            "/api/v1/amenities/",
            json={"name": "Rooftop Terrace", "category": "Outdoor"},
            headers=admin_token_headers
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Rooftop Terrace"
        # Amenities have no audit fields — confirm they are absent
        assert "deleted_at" not in data
        assert "created_by" not in data

    def test_create_duplicate_amenity_returns_400(
        self, client: TestClient, admin_token_headers, sample_amenity
    ):
        """Duplicate name triggers 400 guard condition."""
        response = client.post(
            "/api/v1/amenities/",
            json={"name": sample_amenity.name},
            headers=admin_token_headers
        )
        assert response.status_code == 400
        assert "already exists" in response.json()["detail"]

    def test_create_amenity_non_admin_returns_403(
        self, client: TestClient, normal_user_token_headers
    ):
        """Non-admin cannot create amenities."""
        response = client.post(
            "/api/v1/amenities/",
            json={"name": "Private Pool"},
            headers=normal_user_token_headers
        )
        assert response.status_code == 403

    def test_create_amenity_unauthenticated_returns_401(self, client: TestClient):
        """Unauthenticated request returns 401."""
        response = client.post(
            "/api/v1/amenities/",
            json={"name": "Private Pool"}
        )
        assert response.status_code == 401


class TestUpdateAmenity:
    def test_update_amenity_success(
        self, client: TestClient, admin_token_headers, sample_amenity
    ):
        """Admin updates amenity name — 200 returned."""
        response = client.put(
            f"/api/v1/amenities/{sample_amenity.amenity_id}",
            json={"name": f"Updated {sample_amenity.name}"},
            headers=admin_token_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "Updated" in data["name"]

    def test_update_amenity_same_name_succeeds(
        self, client: TestClient, admin_token_headers, sample_amenity
    ):
        """Updating with the same name skips uniqueness check — must not 400."""
        response = client.put(
            f"/api/v1/amenities/{sample_amenity.amenity_id}",
            json={"name": sample_amenity.name},
            headers=admin_token_headers
        )
        assert response.status_code == 200

    def test_update_amenity_duplicate_name_returns_400(
        self, client: TestClient, admin_token_headers, sample_amenity, second_amenity
    ):
        """Changing to an existing name triggers 400 guard condition."""
        response = client.put(
            f"/api/v1/amenities/{sample_amenity.amenity_id}",
            json={"name": second_amenity.name},
            headers=admin_token_headers
        )
        assert response.status_code == 400
        assert "already exists" in response.json()["detail"]

    def test_update_amenity_not_found_returns_404(
        self, client: TestClient, admin_token_headers
    ):
        """Non-existent amenity_id returns 404."""
        response = client.put(
            "/api/v1/amenities/999999",
            json={"name": "Ghost Amenity"},
            headers=admin_token_headers
        )
        assert response.status_code == 404

    def test_update_amenity_non_admin_returns_403(
        self, client: TestClient, normal_user_token_headers, sample_amenity
    ):
        """Non-admin cannot update amenities."""
        response = client.put(
            f"/api/v1/amenities/{sample_amenity.amenity_id}",
            json={"name": "Attempted Update"},
            headers=normal_user_token_headers
        )
        assert response.status_code == 403


class TestDeleteAmenity:
    def test_delete_unused_amenity_success(
        self, client: TestClient, admin_token_headers, db
    ):
        """Hard delete of amenity with no property associations — 200 returned."""
        from app.models.amenities import Amenity
        fresh = Amenity(name=f"Temp Amenity For Delete {id(db)}")
        db.add(fresh)
        db.flush()
        db.refresh(fresh)

        response = client.delete(
            f"/api/v1/amenities/{fresh.amenity_id}",
            headers=admin_token_headers
        )
        assert response.status_code == 200
        assert "deleted successfully" in response.json()["message"]

    def test_delete_amenity_in_use_returns_400(
        self, client: TestClient, admin_token_headers, property_with_amenity, sample_amenity
    ):
        """Amenity used by a property triggers 400 guard condition."""
        response = client.delete(
            f"/api/v1/amenities/{sample_amenity.amenity_id}",
            headers=admin_token_headers
        )
        assert response.status_code == 400
        assert "used by" in response.json()["detail"]

    def test_delete_amenity_not_found_returns_404(
        self, client: TestClient, admin_token_headers
    ):
        """Non-existent amenity_id returns 404."""
        response = client.delete(
            "/api/v1/amenities/999999",
            headers=admin_token_headers
        )
        assert response.status_code == 404

    def test_delete_amenity_non_admin_returns_403(
        self, client: TestClient, normal_user_token_headers, sample_amenity
    ):
        """Non-admin cannot delete amenities."""
        response = client.delete(
            f"/api/v1/amenities/{sample_amenity.amenity_id}",
            headers=normal_user_token_headers
        )
        assert response.status_code == 403


class TestGetPopularAmenities:
    def test_get_popular_amenities_public(self, client: TestClient):
        """Public endpoint — no auth required, returns list."""
        response = client.get("/api/v1/amenities/stats/popular")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_get_popular_amenities_limit_param(self, client: TestClient):
        """limit param is accepted."""
        response = client.get("/api/v1/amenities/stats/popular?limit=3")
        assert response.status_code == 200