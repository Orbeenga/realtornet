# tests/api/endpoints/test_property_types.py
"""
Surgical API-layer tests for /property-types endpoints.
Covers all routes, all permission branches, all error paths.
"""
import pytest
from fastapi.testclient import TestClient


# ===========================================================================
# GET /  — list all property types (public)
# ===========================================================================

class TestReadPropertyTypes:

    def test_no_auth_required(self, client: TestClient):
        response = client.get("/api/v1/property-types/")
        assert response.status_code == 200

    def test_returns_list(self, client: TestClient, sample_property_type):
        response = client.get("/api/v1/property-types/")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_pagination_skip_limit_accepted(self, client: TestClient):
        response = client.get("/api/v1/property-types/", params={"skip": 0, "limit": 5})
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_response_contains_required_fields(
        self, client: TestClient, sample_property_type
    ):
        response = client.get("/api/v1/property-types/")
        data = response.json()
        assert len(data) >= 1
        item = next(
            (d for d in data if d["property_type_id"] == sample_property_type.property_type_id),
            None
        )
        assert item is not None
        assert "name" in item
        assert "property_type_id" in item


# ===========================================================================
# GET /{property_type_id}  — get single property type (public)
# ===========================================================================

class TestReadPropertyType:

    def test_not_found_returns_404(self, client: TestClient):
        response = client.get("/api/v1/property-types/999999")
        assert response.status_code == 404
        assert "property type" in response.json()["detail"].lower()

    def test_returns_correct_property_type(
        self, client: TestClient, sample_property_type
    ):
        response = client.get(
            f"/api/v1/property-types/{sample_property_type.property_type_id}"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["property_type_id"] == sample_property_type.property_type_id
        assert data["name"] == sample_property_type.name

    def test_no_auth_required(self, client: TestClient, sample_property_type):
        response = client.get(
            f"/api/v1/property-types/{sample_property_type.property_type_id}"
        )
        assert response.status_code == 200


# ===========================================================================
# POST /  — create property type (admin only)
# ===========================================================================

class TestCreatePropertyType:

    def test_unauthenticated_returns_401(self, client: TestClient):
        response = client.post(
            "/api/v1/property-types/",
            json={"name": "Mansion"}
        )
        assert response.status_code == 401

    def test_non_admin_seeker_returns_403(
        self, client: TestClient, normal_user_token_headers
    ):
        response = client.post(
            "/api/v1/property-types/",
            json={"name": "Mansion"},
            headers=normal_user_token_headers
        )
        assert response.status_code == 403

    def test_non_admin_agent_returns_403(
        self, client: TestClient, agent_token_headers
    ):
        response = client.post(
            "/api/v1/property-types/",
            json={"name": "Mansion"},
            headers=agent_token_headers
        )
        assert response.status_code == 403

    def test_duplicate_name_returns_400(
        self, client: TestClient, admin_token_headers, sample_property_type
    ):
        response = client.post(
            "/api/v1/property-types/",
            json={"name": sample_property_type.name},
            headers=admin_token_headers
        )
        assert response.status_code == 400
        assert "already exists" in response.json()["detail"].lower()

    def test_admin_creates_property_type_success(
        self, client: TestClient, admin_token_headers
    ):
        response = client.post(
            "/api/v1/property-types/",
            json={"name": "Penthouse Suite", "description": "Top-floor luxury unit"},
            headers=admin_token_headers
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Penthouse Suite"
        assert "property_type_id" in data

    def test_admin_creates_without_description(
        self, client: TestClient, admin_token_headers
    ):
        response = client.post(
            "/api/v1/property-types/",
            json={"name": "Bungalow"},
            headers=admin_token_headers
        )
        assert response.status_code == 201
        assert response.json()["name"] == "Bungalow"


# ===========================================================================
# PUT /{property_type_id}  — update property type (admin only)
# ===========================================================================

class TestUpdatePropertyType:

    def test_not_found_returns_404(
        self, client: TestClient, admin_token_headers
    ):
        response = client.put(
            "/api/v1/property-types/999999",
            json={"name": "Updated"},
            headers=admin_token_headers
        )
        assert response.status_code == 404

    def test_unauthenticated_returns_401(
        self, client: TestClient, sample_property_type
    ):
        response = client.put(
            f"/api/v1/property-types/{sample_property_type.property_type_id}",
            json={"name": "Updated"}
        )
        assert response.status_code == 401

    def test_non_admin_returns_403(
        self, client: TestClient, normal_user_token_headers, sample_property_type
    ):
        response = client.put(
            f"/api/v1/property-types/{sample_property_type.property_type_id}",
            json={"name": "Updated"},
            headers=normal_user_token_headers
        )
        assert response.status_code == 403

    def test_duplicate_name_returns_400(
        self, client: TestClient, admin_token_headers,
        sample_property_type, second_property_type
    ):
        response = client.put(
            f"/api/v1/property-types/{sample_property_type.property_type_id}",
            json={"name": second_property_type.name},
            headers=admin_token_headers
        )
        assert response.status_code == 400
        assert "already exists" in response.json()["detail"].lower()

    def test_admin_updates_name(
        self, client: TestClient, admin_token_headers, sample_property_type
    ):
        response = client.put(
            f"/api/v1/property-types/{sample_property_type.property_type_id}",
            json={"name": "Renovated Studio"},
            headers=admin_token_headers
        )
        assert response.status_code == 200
        assert response.json()["name"] == "Renovated Studio"

    def test_admin_updates_description_only(
        self, client: TestClient, admin_token_headers, sample_property_type
    ):
        response = client.put(
            f"/api/v1/property-types/{sample_property_type.property_type_id}",
            json={"description": "New description"},
            headers=admin_token_headers
        )
        assert response.status_code == 200
        assert response.json()["description"] == "New description"

    def test_same_name_update_does_not_conflict(
        self, client: TestClient, admin_token_headers, sample_property_type
    ):
        """Updating to same name (case match) should not raise duplicate error."""
        response = client.put(
            f"/api/v1/property-types/{sample_property_type.property_type_id}",
            json={"name": sample_property_type.name},
            headers=admin_token_headers
        )
        assert response.status_code == 200


# ===========================================================================
# DELETE /{property_type_id}  — hard delete (admin only)
# ===========================================================================

class TestDeletePropertyType:

    def test_not_found_returns_404(
        self, client: TestClient, admin_token_headers
    ):
        response = client.delete(
            "/api/v1/property-types/999999",
            headers=admin_token_headers
        )
        assert response.status_code == 404

    def test_unauthenticated_returns_401(
        self, client: TestClient, sample_property_type
    ):
        response = client.delete(
            f"/api/v1/property-types/{sample_property_type.property_type_id}"
        )
        assert response.status_code == 401

    def test_non_admin_returns_403(
        self, client: TestClient, normal_user_token_headers, sample_property_type
    ):
        response = client.delete(
            f"/api/v1/property-types/{sample_property_type.property_type_id}",
            headers=normal_user_token_headers
        )
        assert response.status_code == 403

    def test_in_use_type_returns_400(
        self, client: TestClient, admin_token_headers,
        property_type, verified_property
    ):
        """property_type fixture is used by verified_property → 400."""
        response = client.delete(
            f"/api/v1/property-types/{property_type.property_type_id}",
            headers=admin_token_headers
        )
        assert response.status_code == 400
        assert response.json()["detail"] == "Cannot delete property type that is in use by existing properties."

    def test_soft_deleted_property_still_blocks_delete(
        self, client: TestClient, admin_token_headers,
        property_type, sample_property
    ):
        delete_property_response = client.delete(
            f"/api/v1/properties/{sample_property.property_id}",
            headers=admin_token_headers
        )
        assert delete_property_response.status_code == 200

        response = client.delete(
            f"/api/v1/property-types/{property_type.property_type_id}",
            headers=admin_token_headers
        )
        assert response.status_code == 400
        assert response.json()["detail"] == "Cannot delete property type that is in use by existing properties."

    def test_admin_deletes_unused_type(
        self, client: TestClient, admin_token_headers, unused_property_type
    ):
        response = client.delete(
            f"/api/v1/property-types/{unused_property_type.property_type_id}",
            headers=admin_token_headers
        )
        assert response.status_code == 200
        assert "deleted" in response.json()["message"].lower()

    def test_deleted_type_no_longer_accessible(
        self, client: TestClient, admin_token_headers, unused_property_type
    ):
        pt_id = unused_property_type.property_type_id
        client.delete(f"/api/v1/property-types/{pt_id}", headers=admin_token_headers)
        response = client.get(f"/api/v1/property-types/{pt_id}")
        assert response.status_code == 404


# ===========================================================================
# GET /stats/usage  — admin only usage stats
# ===========================================================================

class TestGetPropertyTypeUsageStats:

    def test_unauthenticated_returns_401(self, client: TestClient):
        response = client.get("/api/v1/property-types/stats/usage")
        assert response.status_code == 401

    def test_non_admin_seeker_returns_403(
        self, client: TestClient, normal_user_token_headers
    ):
        response = client.get(
            "/api/v1/property-types/stats/usage",
            headers=normal_user_token_headers
        )
        assert response.status_code == 403

    def test_non_admin_agent_returns_403(
        self, client: TestClient, agent_token_headers
    ):
        response = client.get(
            "/api/v1/property-types/stats/usage",
            headers=agent_token_headers
        )
        assert response.status_code == 403

    def test_admin_gets_stats_list(
        self, client: TestClient, admin_token_headers, sample_property_type
    ):
        response = client.get(
            "/api/v1/property-types/stats/usage",
            headers=admin_token_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_stats_contain_required_fields(
        self, client: TestClient, admin_token_headers, sample_property_type
    ):
        response = client.get(
            "/api/v1/property-types/stats/usage",
            headers=admin_token_headers
        )
        data = response.json()
        if data:
            item = data[0]
            assert "property_type_id" in item
            assert "name" in item
            assert "property_count" in item

    def test_in_use_type_shows_nonzero_count(
        self, client: TestClient, admin_token_headers,
        property_type, verified_property
    ):
        """The property_type fixture is used by verified_property — count must be ≥ 1."""
        response = client.get(
            "/api/v1/property-types/stats/usage",
            headers=admin_token_headers
        )
        data = response.json()
        entry = next(
            (d for d in data if d["property_type_id"] == property_type.property_type_id),
            None
        )
        assert entry is not None
        assert entry["property_count"] >= 1
