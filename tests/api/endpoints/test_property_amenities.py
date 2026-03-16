# tests/api/endpoints/test_property_amenities.py
"""
Surgical API-layer tests for /property-amenities endpoints.
Covers all routes, all permission branches, all error paths.
"""

import pytest
from fastapi.testclient import TestClient


# ===========================================================================
# GET /property/{property_id}  — list amenities (public)
# ===========================================================================

class TestReadPropertyAmenities:

    def test_property_not_found_returns_404(self, client: TestClient):
        response = client.get("/api/v1/property-amenities/property/999999")
        assert response.status_code == 404
        assert "property" in response.json()["detail"].lower()

    def test_returns_empty_list_when_no_amenities(
        self, client: TestClient, verified_property
    ):
        response = client.get(
            f"/api/v1/property-amenities/property/{verified_property.property_id}"
        )
        assert response.status_code == 200
        assert response.json() == []

    def test_returns_amenities_for_property(
        self, client: TestClient, property_with_amenity, sample_amenity
    ):
        response = client.get(
            f"/api/v1/property-amenities/property/{property_with_amenity.property_id}"
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["amenity_id"] == sample_amenity.amenity_id

    def test_public_no_auth_required(self, client: TestClient, verified_property):
        response = client.get(
            f"/api/v1/property-amenities/property/{verified_property.property_id}"
        )
        assert response.status_code == 200


# ===========================================================================
# POST /  — add single amenity to property
# ===========================================================================

class TestAddAmenityToProperty:

    def test_unauthenticated_returns_401(
        self, client: TestClient,
        unverified_property_owned_by_agent, sample_amenity
    ):
        response = client.post(
            "/api/v1/property-amenities/",
            json={
                "property_id": unverified_property_owned_by_agent.property_id,
                "amenity_id": sample_amenity.amenity_id,
            }
        )
        assert response.status_code == 401

    def test_property_not_found_returns_404(
        self, client: TestClient, owner_token_headers, sample_amenity
    ):
        response = client.post(
            "/api/v1/property-amenities/",
            json={"property_id": 999999, "amenity_id": sample_amenity.amenity_id},
            headers=owner_token_headers
        )
        assert response.status_code == 404
        assert "property" in response.json()["detail"].lower()

    def test_amenity_not_found_returns_404(
        self, client: TestClient, owner_token_headers,
        unverified_property_owned_by_agent
    ):
        response = client.post(
            "/api/v1/property-amenities/",
            json={
                "property_id": unverified_property_owned_by_agent.property_id,
                "amenity_id": 999999,
            },
            headers=owner_token_headers
        )
        assert response.status_code == 404
        assert "amenity" in response.json()["detail"].lower()

    def test_non_owner_non_admin_returns_403(
        self, client: TestClient, normal_user_token_headers,
        unverified_property_owned_by_agent, sample_amenity
    ):
        response = client.post(
            "/api/v1/property-amenities/",
            json={
                "property_id": unverified_property_owned_by_agent.property_id,
                "amenity_id": sample_amenity.amenity_id,
            },
            headers=normal_user_token_headers
        )
        assert response.status_code == 403

    def test_duplicate_association_returns_400(
        self, client: TestClient, owner_token_headers,
        property_with_amenity, sample_amenity
    ):
        response = client.post(
            "/api/v1/property-amenities/",
            json={
                "property_id": property_with_amenity.property_id,
                "amenity_id": sample_amenity.amenity_id,
            },
            headers=owner_token_headers
        )
        assert response.status_code == 400
        assert "already" in response.json()["detail"].lower()

    def test_owner_adds_amenity_success(
        self, client: TestClient, owner_token_headers,
        unverified_property_owned_by_agent, sample_amenity
    ):
        response = client.post(
            "/api/v1/property-amenities/",
            json={
                "property_id": unverified_property_owned_by_agent.property_id,
                "amenity_id": sample_amenity.amenity_id,
            },
            headers=owner_token_headers
        )
        assert response.status_code == 201
        data = response.json()
        assert data["amenity_id"] == sample_amenity.amenity_id

    def test_admin_adds_amenity_to_any_property(
        self, client: TestClient, admin_token_headers,
        unverified_property_owned_by_agent, sample_amenity
    ):
        response = client.post(
            "/api/v1/property-amenities/",
            json={
                "property_id": unverified_property_owned_by_agent.property_id,
                "amenity_id": sample_amenity.amenity_id,
            },
            headers=admin_token_headers
        )
        assert response.status_code == 201


# ===========================================================================
# POST /bulk  — add multiple amenities
# ===========================================================================

class TestAddAmenitiesBulk:

    def test_unauthenticated_returns_401(
        self, client: TestClient,
        unverified_property_owned_by_agent, sample_amenity
    ):
        response = client.post(
            "/api/v1/property-amenities/bulk",
            json={
                "property_id": unverified_property_owned_by_agent.property_id,
                "amenity_ids": [sample_amenity.amenity_id],
            }
        )
        assert response.status_code == 401

    def test_property_not_found_returns_404(
        self, client: TestClient, owner_token_headers, sample_amenity
    ):
        response = client.post(
            "/api/v1/property-amenities/bulk",
            json={"property_id": 999999, "amenity_ids": [sample_amenity.amenity_id]},
            headers=owner_token_headers
        )
        assert response.status_code == 404

    def test_amenity_not_found_returns_404(
        self, client: TestClient, owner_token_headers,
        unverified_property_owned_by_agent
    ):
        response = client.post(
            "/api/v1/property-amenities/bulk",
            json={
                "property_id": unverified_property_owned_by_agent.property_id,
                "amenity_ids": [999999],
            },
            headers=owner_token_headers
        )
        assert response.status_code == 404

    def test_non_owner_returns_403(
        self, client: TestClient, normal_user_token_headers,
        unverified_property_owned_by_agent, sample_amenity
    ):
        response = client.post(
            "/api/v1/property-amenities/bulk",
            json={
                "property_id": unverified_property_owned_by_agent.property_id,
                "amenity_ids": [sample_amenity.amenity_id],
            },
            headers=normal_user_token_headers
        )
        assert response.status_code == 403

    def test_owner_bulk_adds_amenities(
        self, client: TestClient, owner_token_headers,
        unverified_property_owned_by_agent, sample_amenity, second_amenity
    ):
        response = client.post(
            "/api/v1/property-amenities/bulk",
            json={
                "property_id": unverified_property_owned_by_agent.property_id,
                "amenity_ids": [sample_amenity.amenity_id, second_amenity.amenity_id],
            },
            headers=owner_token_headers
        )
        assert response.status_code == 201
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 2

    def test_admin_bulk_adds_to_any_property(
        self, client: TestClient, admin_token_headers,
        unverified_property_owned_by_agent, sample_amenity
    ):
        response = client.post(
            "/api/v1/property-amenities/bulk",
            json={
                "property_id": unverified_property_owned_by_agent.property_id,
                "amenity_ids": [sample_amenity.amenity_id],
            },
            headers=admin_token_headers
        )
        assert response.status_code == 201


# ===========================================================================
# DELETE /  — remove single amenity
# ===========================================================================

class TestRemoveAmenityFromProperty:

    def test_unauthenticated_returns_401(
        self, client: TestClient,
        property_with_amenity, sample_amenity
    ):
        response = client.delete(
            "/api/v1/property-amenities/",
            params={
                "property_id": property_with_amenity.property_id,
                "amenity_id": sample_amenity.amenity_id,
            }
        )
        assert response.status_code == 401

    def test_property_not_found_returns_404(
        self, client: TestClient, owner_token_headers, sample_amenity
    ):
        response = client.delete(
            "/api/v1/property-amenities/",
            params={"property_id": 999999, "amenity_id": sample_amenity.amenity_id},
            headers=owner_token_headers
        )
        assert response.status_code == 404

    def test_association_not_found_returns_404(
        self, client: TestClient, owner_token_headers,
        unverified_property_owned_by_agent, sample_amenity
    ):
        """Amenity exists but not associated with this property → 404."""
        response = client.delete(
            "/api/v1/property-amenities/",
            params={
                "property_id": unverified_property_owned_by_agent.property_id,
                "amenity_id": sample_amenity.amenity_id,
            },
            headers=owner_token_headers
        )
        assert response.status_code == 404
        assert "association" in response.json()["detail"].lower()

    def test_non_owner_returns_403(
        self, client: TestClient, normal_user_token_headers,
        property_with_amenity, sample_amenity
    ):
        response = client.delete(
            "/api/v1/property-amenities/",
            params={
                "property_id": property_with_amenity.property_id,
                "amenity_id": sample_amenity.amenity_id,
            },
            headers=normal_user_token_headers
        )
        assert response.status_code == 403

    def test_owner_removes_amenity_success(
        self, client: TestClient, owner_token_headers,
        property_with_amenity, sample_amenity
    ):
        response = client.delete(
            "/api/v1/property-amenities/",
            params={
                "property_id": property_with_amenity.property_id,
                "amenity_id": sample_amenity.amenity_id,
            },
            headers=owner_token_headers
        )
        assert response.status_code == 200
        assert "removed" in response.json()["message"].lower()

    def test_admin_removes_from_any_property(
        self, client: TestClient, admin_token_headers,
        property_with_amenity, sample_amenity
    ):
        response = client.delete(
            "/api/v1/property-amenities/",
            params={
                "property_id": property_with_amenity.property_id,
                "amenity_id": sample_amenity.amenity_id,
            },
            headers=admin_token_headers
        )
        assert response.status_code == 200


# ===========================================================================
# DELETE /bulk  — remove multiple amenities
# ===========================================================================

class TestRemoveAmenitiesBulk:

    def test_unauthenticated_returns_401(
        self, client: TestClient,
        property_with_amenity, sample_amenity
    ):
        response = client.delete(
            "/api/v1/property-amenities/bulk",
            params={
                "property_id": property_with_amenity.property_id,
                "amenity_ids": [sample_amenity.amenity_id],
            }
        )
        assert response.status_code == 401

    def test_property_not_found_returns_404(
        self, client: TestClient, owner_token_headers, sample_amenity
    ):
        response = client.delete(
            "/api/v1/property-amenities/bulk",
            params={"property_id": 999999, "amenity_ids": [sample_amenity.amenity_id]},
            headers=owner_token_headers
        )
        assert response.status_code == 404

    def test_non_owner_returns_403(
        self, client: TestClient, normal_user_token_headers,
        property_with_amenity, sample_amenity
    ):
        response = client.delete(
            "/api/v1/property-amenities/bulk",
            params={
                "property_id": property_with_amenity.property_id,
                "amenity_ids": [sample_amenity.amenity_id],
            },
            headers=normal_user_token_headers
        )
        assert response.status_code == 403

    def test_owner_bulk_removes_amenities(
        self, client: TestClient, owner_token_headers,
        property_with_amenity, sample_amenity
    ):
        response = client.delete(
            "/api/v1/property-amenities/bulk",
            params={
                "property_id": property_with_amenity.property_id,
                "amenity_ids": [sample_amenity.amenity_id],
            },
            headers=owner_token_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "removed" in data["message"].lower()

    def test_admin_bulk_removes_from_any_property(
        self, client: TestClient, admin_token_headers,
        property_with_amenity, sample_amenity
    ):
        response = client.delete(
            "/api/v1/property-amenities/bulk",
            params={
                "property_id": property_with_amenity.property_id,
                "amenity_ids": [sample_amenity.amenity_id],
            },
            headers=admin_token_headers
        )
        assert response.status_code == 200


# ===========================================================================
# PUT /property/{property_id}/sync  — sync amenities to exact list
# ===========================================================================

class TestSyncPropertyAmenities:

    def test_unauthenticated_returns_401(
        self, client: TestClient, unverified_property_owned_by_agent
    ):
        response = client.put(
            f"/api/v1/property-amenities/property/"
            f"{unverified_property_owned_by_agent.property_id}/sync",
            json=[]
        )
        assert response.status_code == 401

    def test_property_not_found_returns_404(
        self, client: TestClient, owner_token_headers
    ):
        response = client.put(
            "/api/v1/property-amenities/property/999999/sync",
            json=[],
            headers=owner_token_headers
        )
        assert response.status_code == 404

    def test_invalid_amenity_id_returns_404(
        self, client: TestClient, owner_token_headers,
        unverified_property_owned_by_agent
    ):
        response = client.put(
            f"/api/v1/property-amenities/property/"
            f"{unverified_property_owned_by_agent.property_id}/sync",
            json=[999999],
            headers=owner_token_headers
        )
        assert response.status_code == 404

    def test_non_owner_returns_403(
        self, client: TestClient, normal_user_token_headers,
        unverified_property_owned_by_agent
    ):
        response = client.put(
            f"/api/v1/property-amenities/property/"
            f"{unverified_property_owned_by_agent.property_id}/sync",
            json=[],
            headers=normal_user_token_headers
        )
        assert response.status_code == 403

    def test_owner_syncs_to_empty_removes_all(
        self, client: TestClient, owner_token_headers,
        property_with_amenity
    ):
        response = client.put(
            f"/api/v1/property-amenities/property/"
            f"{property_with_amenity.property_id}/sync",
            json=[],
            headers=owner_token_headers
        )
        assert response.status_code == 200
        assert response.json() == []

    def test_owner_syncs_amenities(
        self, client: TestClient, owner_token_headers,
        unverified_property_owned_by_agent, sample_amenity, second_amenity
    ):
        response = client.put(
            f"/api/v1/property-amenities/property/"
            f"{unverified_property_owned_by_agent.property_id}/sync",
            json=[sample_amenity.amenity_id, second_amenity.amenity_id],
            headers=owner_token_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 2

    def test_admin_syncs_any_property(
        self, client: TestClient, admin_token_headers,
        unverified_property_owned_by_agent, sample_amenity
    ):
        response = client.put(
            f"/api/v1/property-amenities/property/"
            f"{unverified_property_owned_by_agent.property_id}/sync",
            json=[sample_amenity.amenity_id],
            headers=admin_token_headers
        )
        assert response.status_code == 200
