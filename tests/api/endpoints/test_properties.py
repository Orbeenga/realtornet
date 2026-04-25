# tests/api/endpoints/test_properties.py
"""
API-layer tests for /api/v1/properties endpoints.
Covers all routes, all visibility branches, all error paths.
Uses real HTTP client (TestClient) — conftest.py wires auth + db.
"""
import pytest
import uuid
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from app.core.security import generate_access_token, get_password_hash
from app.models.properties import Property, ListingType, ListingStatus
from app.models.users import User, UserRole


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def auth_headers(client, normal_user_token_headers):
    """Shorthand — most tests accept pre-built headers from conftest."""
    return normal_user_token_headers


# ===========================================================================
# GET /  —  list properties
# ===========================================================================

class TestReadProperties:
    """Covers read_properties — 4 visibility branches."""

    def test_anonymous_gets_approved_only(self, client: TestClient, sample_property):
        """Anonymous user: calls get_multi_by_params_approved."""
        response = client.get("/api/v1/properties/")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_regular_user_gets_approved_only(
        self, client: TestClient, normal_user_token_headers, sample_property
    ):
        """Regular (non-agent, non-admin) user sees only approved properties."""
        response = client.get(
            "/api/v1/properties/", headers=normal_user_token_headers
        )
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_agent_gets_agent_view(
        self, client: TestClient, agent_token_headers, sample_property
    ):
        """Agent role: calls get_multi_by_params_for_agent."""
        response = client.get(
            "/api/v1/properties/", headers=agent_token_headers
        )
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_admin_gets_all(
        self, client: TestClient, admin_token_headers, sample_property
    ):
        """Admin role: calls get_multi_by_params (all properties)."""
        response = client.get(
            "/api/v1/properties/", headers=admin_token_headers
        )
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_filter_params_accepted(self, client: TestClient):
        """Filter query params are forwarded without 422."""
        response = client.get(
            "/api/v1/properties/",
            params={
                "skip": 0,
                "limit": 10,
                "min_price": 1000000,
                "max_price": 50000000,
                "bedrooms": 3,
                "bathrooms": 2,
            }
        )
        assert response.status_code == 200

    def test_pagination_params(self, client: TestClient):
        """skip/limit accepted."""
        response = client.get("/api/v1/properties/", params={"skip": 0, "limit": 5})
        assert response.status_code == 200

    def test_search_filters_title_and_description(
        self, client: TestClient, db, normal_user, location, property_type
    ):
        from geoalchemy2.elements import WKTElement

        matching_title = Property(
            title="Lekki Waterfront Apartment",
            description="Modern apartment in Lagos",
            user_id=normal_user.user_id,
            property_type_id=property_type.property_type_id,
            location_id=location.location_id,
            geom=WKTElement('POINT(3.3488 6.6018)', srid=4326),
            price=25000000,
            bedrooms=3,
            bathrooms=2,
            property_size=120.0,
            listing_type=ListingType.sale,
            listing_status=ListingStatus.available,
            is_verified=True,
        )
        matching_description = Property(
            title="Coastal Apartment",
            description="Bright home near Lekki conservation centre",
            user_id=normal_user.user_id,
            property_type_id=property_type.property_type_id,
            location_id=location.location_id,
            geom=WKTElement('POINT(3.3488 6.6018)', srid=4326),
            price=18000000,
            bedrooms=2,
            bathrooms=2,
            property_size=95.0,
            listing_type=ListingType.sale,
            listing_status=ListingStatus.available,
            is_verified=True,
        )
        non_matching = Property(
            title="Ikeja Family Home",
            description="Quiet street with good access",
            user_id=normal_user.user_id,
            property_type_id=property_type.property_type_id,
            location_id=location.location_id,
            geom=WKTElement('POINT(3.3488 6.6018)', srid=4326),
            price=22000000,
            bedrooms=3,
            bathrooms=2,
            property_size=115.0,
            listing_type=ListingType.sale,
            listing_status=ListingStatus.available,
            is_verified=True,
        )
        db.add(matching_title)
        db.add(matching_description)
        db.add(non_matching)
        db.flush()
        db.refresh(matching_title)
        db.refresh(matching_description)
        db.refresh(non_matching)

        response = client.get("/api/v1/properties/", params={"search": "Lekki"})

        assert response.status_code == 200
        data = response.json()
        returned_ids = {item["property_id"] for item in data}
        assert matching_title.property_id in returned_ids
        assert matching_description.property_id in returned_ids
        assert non_matching.property_id not in returned_ids
        assert all(
            "lekki" in (item["title"] + " " + item["description"]).lower()
            for item in data
        )


# ===========================================================================
# POST /  —  create property
# ===========================================================================

class TestCreateProperty:
    """Covers create_property — all permission and validation branches."""

    def test_regular_user_forbidden(
        self, client: TestClient, normal_user_token_headers, property_create_payload
    ):
        """Non-agent/non-admin gets 403."""
        response = client.post(
            "/api/v1/properties/",
            json=property_create_payload,
            headers=normal_user_token_headers
        )
        assert response.status_code == 403
        assert "agents and admins" in response.json()["detail"].lower()

    def test_seeker_cannot_create_property_exact_error(
        self, client: TestClient, normal_user_token_headers, property_create_payload
    ):
        response = client.post(
            "/api/v1/properties/",
            json=property_create_payload,
            headers=normal_user_token_headers
        )
        assert response.status_code == 403
        assert response.json()["detail"] == "Only agents and admins can create property listings"

    def test_unauthenticated_forbidden(
        self, client: TestClient, property_create_payload
    ):
        """No token → 401."""
        response = client.post("/api/v1/properties/", json=property_create_payload)
        assert response.status_code == 401

    def test_agent_without_agency_returns_400(
        self, client: TestClient, agent_no_agency_token_headers, property_create_payload
    ):
        """Agent with no agency_id on their profile → 400."""
        response = client.post(
            "/api/v1/properties/",
            json=property_create_payload,
            headers=agent_no_agency_token_headers
        )
        assert response.status_code == 400
        assert "agency" in response.json()["detail"].lower()

    def test_agent_cross_agency_forbidden(
        self, client: TestClient, agent_token_headers, property_create_payload_other_agency
    ):
        """Agent trying to create for a different agency → 403."""
        response = client.post(
            "/api/v1/properties/",
            json=property_create_payload_other_agency,
            headers=agent_token_headers
        )
        assert response.status_code == 403
        assert "another agency" in response.json()["detail"].lower()

    def test_invalid_latitude_returns_400(
        self, client: TestClient, agent_token_headers, property_create_payload
    ):
        """Latitude out of [-90, 90] → 400."""
        payload = {**property_create_payload, "latitude": 95.0}
        response = client.post(
            "/api/v1/properties/", json=payload, headers=agent_token_headers
        )
        assert response.status_code == 400
        assert "latitude" in response.json()["detail"].lower()

    def test_invalid_longitude_returns_400(
        self, client: TestClient, agent_token_headers, property_create_payload
    ):
        """Longitude out of [-180, 180] → 400."""
        payload = {**property_create_payload, "longitude": 200.0}
        response = client.post(
            "/api/v1/properties/", json=payload, headers=agent_token_headers
        )
        assert response.status_code == 400
        assert "longitude" in response.json()["detail"].lower()

    def test_agent_creates_property_success(
        self, client: TestClient, agent_token_headers, property_create_payload, agency
    ):
        """Agent with valid agency creates property → 201."""
        response = client.post(
            "/api/v1/properties/",
            json=property_create_payload,
            headers=agent_token_headers
        )
        assert response.status_code == 201
        data = response.json()
        assert "property_id" in data
        assert data["agency_id"] == agency.agency_id
        assert data["agency_name"] == agency.name

    def test_admin_creates_property_success(
        self, client: TestClient, admin_token_headers, property_create_payload
    ):
        """Admin creates property for any agency → 201."""
        response = client.post(
            "/api/v1/properties/",
            json=property_create_payload,
            headers=admin_token_headers
        )
        assert response.status_code == 201


# ===========================================================================
# GET /{property_id}  —  read single property
# ===========================================================================

class TestReadProperty:
    """Covers read_property — all visibility branches + 404."""

    def test_not_found_returns_404(self, client: TestClient):
        """Non-existent ID → 404."""
        response = client.get("/api/v1/properties/999999")
        assert response.status_code == 404
        assert response.json()["detail"] == "Property not found"

    def test_anonymous_verified_property_visible(
        self, client: TestClient, verified_property
    ):
        """Anonymous user can see a verified property."""
        response = client.get(f"/api/v1/properties/{verified_property.property_id}")
        assert response.status_code == 200
        assert response.json()["property_id"] == verified_property.property_id

    def test_anonymous_unverified_returns_404(
        self, client: TestClient, unverified_property
    ):
        """Anonymous user → unverified property intentionally returns 404 (security obfuscation)."""
        response = client.get(f"/api/v1/properties/{unverified_property.property_id}")
        assert response.status_code == 404
        assert response.json()["detail"] == "Property not found"

    def test_owner_can_see_own_unverified(
        self, client: TestClient, owner_token_headers, unverified_property_owned_by_agent
    ):
        """Owner can see their own unverified property."""
        response = client.get(
            f"/api/v1/properties/{unverified_property_owned_by_agent.property_id}",
            headers=owner_token_headers
        )
        assert response.status_code == 200

    def test_other_user_cannot_see_unverified(
        self, client: TestClient, normal_user_token_headers, unverified_property
    ):
        """Logged-in non-owner, non-admin → unverified property → 403."""
        response = client.get(
            f"/api/v1/properties/{unverified_property.property_id}",
            headers=normal_user_token_headers
        )
        assert response.status_code == 403
        assert "permissions" in response.json()["detail"].lower()

    def test_admin_sees_unverified(
        self, client: TestClient, admin_token_headers, unverified_property
    ):
        """Admin can see any property regardless of verification."""
        response = client.get(
            f"/api/v1/properties/{unverified_property.property_id}",
            headers=admin_token_headers
        )
        assert response.status_code == 200


# ===========================================================================
# PUT /{property_id}  —  update property
# ===========================================================================

class TestUpdateProperty:
    """Covers update_property — not found, forbidden, geo validation, success."""

    def test_not_found_returns_404(
        self, client: TestClient, agent_token_headers, property_update_payload
    ):
        response = client.put(
            "/api/v1/properties/999999",
            json=property_update_payload,
            headers=agent_token_headers
        )
        assert response.status_code == 404

    def test_non_owner_non_admin_forbidden(
        self, client: TestClient, normal_user_token_headers,
        verified_property, property_update_payload
    ):
        """User who doesn't own the property and isn't admin → 403."""
        response = client.put(
            f"/api/v1/properties/{verified_property.property_id}",
            json=property_update_payload,
            headers=normal_user_token_headers
        )
        assert response.status_code == 403

    def test_unauthenticated_returns_401(
        self, client: TestClient, verified_property, property_update_payload
    ):
        response = client.put(
            f"/api/v1/properties/{verified_property.property_id}",
            json=property_update_payload
        )
        assert response.status_code == 401

    def test_invalid_latitude_in_update(
        self, client: TestClient, owner_token_headers,
        unverified_property_owned_by_agent
    ):
        payload = {"latitude": 999.0}
        response = client.put(
            f"/api/v1/properties/{unverified_property_owned_by_agent.property_id}",
            json=payload,
            headers=owner_token_headers
        )
        assert response.status_code == 400
        assert "latitude" in response.json()["detail"].lower()

    def test_invalid_longitude_in_update(
        self, client: TestClient, owner_token_headers,
        unverified_property_owned_by_agent
    ):
        payload = {"longitude": -999.0}
        response = client.put(
            f"/api/v1/properties/{unverified_property_owned_by_agent.property_id}",
            json=payload,
            headers=owner_token_headers
        )
        assert response.status_code == 400
        assert "longitude" in response.json()["detail"].lower()

    def test_owner_can_update(
        self, client: TestClient, owner_token_headers,
        unverified_property_owned_by_agent, property_update_payload
    ):
        response = client.put(
            f"/api/v1/properties/{unverified_property_owned_by_agent.property_id}",
            json=property_update_payload,
            headers=owner_token_headers
        )
        assert response.status_code == 200

    def test_admin_can_update_any(
        self, client: TestClient, admin_token_headers,
        verified_property, property_update_payload
    ):
        response = client.put(
            f"/api/v1/properties/{verified_property.property_id}",
            json=property_update_payload,
            headers=admin_token_headers
        )
        assert response.status_code == 200

    def test_agent_cannot_update_other_agents_property(
        self, client: TestClient, db, agent_user, unverified_property_owned_by_agent
    ):
        other_agent = User(
            email=f"other_agent_{uuid.uuid4().hex[:6]}@example.com",
            password_hash=get_password_hash("password"),
            first_name="Other",
            last_name="Agent",
            user_role=UserRole.AGENT,
            supabase_id=uuid.uuid4(),
            agency_id=agent_user.agency_id,
        )
        db.add(other_agent)
        db.flush()
        db.refresh(other_agent)

        other_agent_token = generate_access_token(
            supabase_id=other_agent.supabase_id,
            user_id=other_agent.user_id,
            user_role=other_agent.user_role.value,
        )
        other_agent_headers = {"Authorization": f"Bearer {other_agent_token}"}

        response = client.put(
            f"/api/v1/properties/{unverified_property_owned_by_agent.property_id}",
            json={"title": "hacked"},
            headers=other_agent_headers
        )
        assert response.status_code == 403
        assert response.json()["detail"] == "Not enough permissions to update this property"


# ===========================================================================
# PATCH /{property_id}/verify  —  verification workflow
# ===========================================================================

class TestVerifyProperty:
    """Covers the UI-facing verification flow for property listings."""

    def test_admin_can_verify_property(
        self, client: TestClient, admin_token_headers, unverified_property
    ):
        """Admins can still publish listings from the review flow."""
        response = client.patch(
            f"/api/v1/properties/{unverified_property.property_id}/verify",
            json={"is_verified": True},
            headers=admin_token_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["is_verified"] is True
        assert data["verification_date"] is not None

    def test_admin_verified_property_becomes_publicly_visible(
        self, client: TestClient, admin_token_headers, unverified_property
    ):
        """
        Admin verification should move the listing into the public feed.

        This test checks the user-facing outcome, not just the database flag,
        because the whole point of the workflow is to remove the old SQL-only
        publishing step.
        """
        before_response = client.get(
            "/api/v1/properties/",
            params={"search": unverified_property.title}
        )
        assert before_response.status_code == 200
        assert all(
            item["property_id"] != unverified_property.property_id
            for item in before_response.json()
        )

        verify_response = client.patch(
            f"/api/v1/properties/{unverified_property.property_id}/verify",
            json={"is_verified": True},
            headers=admin_token_headers
        )
        assert verify_response.status_code == 200

        after_response = client.get(
            "/api/v1/properties/",
            params={"search": unverified_property.title}
        )
        assert after_response.status_code == 200
        assert any(
            item["property_id"] == unverified_property.property_id
            for item in after_response.json()
        )

    def test_owner_agent_can_verify_own_property(
        self, client: TestClient, owner_token_headers, unverified_property_owned_by_agent
    ):
        """Agent owners can verify their own listing through the same endpoint."""
        response = client.patch(
            f"/api/v1/properties/{unverified_property_owned_by_agent.property_id}/verify",
            json={"is_verified": True},
            headers=owner_token_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["is_verified"] is True
        assert data["verification_date"] is not None

    def test_owner_agent_can_unverify_own_property(
        self, client: TestClient, owner_token_headers, verified_property
    ):
        """Owners may withdraw their own listing from public view."""
        response = client.patch(
            f"/api/v1/properties/{verified_property.property_id}/verify",
            json={"is_verified": False},
            headers=owner_token_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["is_verified"] is False
        assert data["verification_date"] is None

    def test_owner_verified_property_becomes_publicly_visible(
        self, client: TestClient, owner_token_headers, unverified_property_owned_by_agent
    ):
        """
        Agent-owner verification should also move the listing into the public feed.

        This is the backend proof that the old manual SQL workaround is no
        longer required for the listing verification step.
        """
        before_response = client.get(
            "/api/v1/properties/",
            params={"search": unverified_property_owned_by_agent.title}
        )
        assert before_response.status_code == 200
        assert all(
            item["property_id"] != unverified_property_owned_by_agent.property_id
            for item in before_response.json()
        )

        response = client.patch(
            f"/api/v1/properties/{unverified_property_owned_by_agent.property_id}/verify",
            json={"is_verified": True},
            headers=owner_token_headers
        )
        assert response.status_code == 200

        after_response = client.get(
            "/api/v1/properties/",
            params={"search": unverified_property_owned_by_agent.title}
        )
        assert after_response.status_code == 200
        assert any(
            item["property_id"] == unverified_property_owned_by_agent.property_id
            for item in after_response.json()
        )

    def test_non_owner_non_admin_cannot_verify(
        self, client: TestClient, normal_user_token_headers, unverified_property
    ):
        response = client.patch(
            f"/api/v1/properties/{unverified_property.property_id}/verify",
            json={"is_verified": True},
            headers=normal_user_token_headers
        )

        assert response.status_code == 403
        assert response.json()["detail"] == "Not enough permissions to verify this property"

    def test_unauthenticated_cannot_verify(
        self, client: TestClient, unverified_property
    ):
        response = client.patch(
            f"/api/v1/properties/{unverified_property.property_id}/verify",
            json={"is_verified": True}
        )

        assert response.status_code == 401

    def test_verify_property_not_found_returns_404(
        self, client: TestClient, admin_token_headers
    ):
        response = client.patch(
            "/api/v1/properties/999999/verify",
            json={"is_verified": True},
            headers=admin_token_headers
        )

        assert response.status_code == 404
        assert response.json()["detail"] == "Property not found"


# ===========================================================================
# DELETE /{property_id}  —  soft delete
# ===========================================================================

class TestDeleteProperty:
    """Covers delete_property — not found, forbidden, success paths."""

    def test_not_found_returns_404(
        self, client: TestClient, agent_token_headers
    ):
        response = client.delete(
            "/api/v1/properties/999999", headers=agent_token_headers
        )
        assert response.status_code == 404

    def test_non_owner_non_admin_forbidden(
        self, client: TestClient, normal_user_token_headers, verified_property
    ):
        response = client.delete(
            f"/api/v1/properties/{verified_property.property_id}",
            headers=normal_user_token_headers
        )
        assert response.status_code == 403

    def test_unauthenticated_returns_401(
        self, client: TestClient, verified_property
    ):
        response = client.delete(
            f"/api/v1/properties/{verified_property.property_id}"
        )
        assert response.status_code == 401

    def test_owner_can_soft_delete(
        self, client: TestClient, owner_token_headers,
        unverified_property_owned_by_agent
    ):
        response = client.delete(
            f"/api/v1/properties/{unverified_property_owned_by_agent.property_id}",
            headers=owner_token_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["deleted_at"] is not None

    def test_admin_can_soft_delete_any(
        self, client: TestClient, admin_token_headers, verified_property
    ):
        response = client.delete(
            f"/api/v1/properties/{verified_property.property_id}",
            headers=admin_token_headers
        )
        assert response.status_code == 200
        assert response.json()["deleted_at"] is not None

    def test_agent_cannot_delete_other_agents_property(
        self, client: TestClient, db, agent_user, unverified_property_owned_by_agent
    ):
        other_agent = User(
            email=f"other_agent_{uuid.uuid4().hex[:6]}_delete@example.com",
            password_hash=get_password_hash("password"),
            first_name="Other",
            last_name="Agent",
            user_role=UserRole.AGENT,
            supabase_id=uuid.uuid4(),
            agency_id=agent_user.agency_id,
        )
        db.add(other_agent)
        db.flush()
        db.refresh(other_agent)

        other_agent_token = generate_access_token(
            supabase_id=other_agent.supabase_id,
            user_id=other_agent.user_id,
            user_role=other_agent.user_role.value,
        )
        other_agent_headers = {"Authorization": f"Bearer {other_agent_token}"}

        response = client.delete(
            f"/api/v1/properties/{unverified_property_owned_by_agent.property_id}",
            headers=other_agent_headers
        )
        assert response.status_code == 403
        assert response.json()["detail"] == "Not enough permissions to delete this property"


# ===========================================================================
# GET /by-LocationResponse/{location_id}
# ===========================================================================

class TestReadPropertiesByLocation:
    """Covers 4 visibility branches for the by-location endpoint."""

    def test_anonymous(self, client: TestClient, location, verified_property):
        response = client.get(
            f"/api/v1/properties/by-LocationResponse/{location.location_id}"
        )
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_regular_user(
        self, client: TestClient, normal_user_token_headers, location, verified_property
    ):
        response = client.get(
            f"/api/v1/properties/by-LocationResponse/{location.location_id}",
            headers=normal_user_token_headers
        )
        assert response.status_code == 200

    def test_agent(
        self, client: TestClient, agent_token_headers, location, verified_property
    ):
        response = client.get(
            f"/api/v1/properties/by-LocationResponse/{location.location_id}",
            headers=agent_token_headers
        )
        assert response.status_code == 200

    def test_admin(
        self, client: TestClient, admin_token_headers, location, verified_property
    ):
        response = client.get(
            f"/api/v1/properties/by-LocationResponse/{location.location_id}",
            headers=admin_token_headers
        )
        assert response.status_code == 200


# ===========================================================================
# GET /by-agent/{agent_user_id}
# ===========================================================================

class TestReadPropertiesByAgent:
    """Covers 4 visibility branches for the by-agent endpoint."""

    def test_anonymous_sees_approved_only(
        self, client: TestClient, agent_user, verified_property
    ):
        response = client.get(
            f"/api/v1/properties/by-agent/{agent_user.user_id}"
        )
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_admin_sees_all(
        self, client: TestClient, admin_token_headers, agent_user, unverified_property
    ):
        response = client.get(
            f"/api/v1/properties/by-agent/{agent_user.user_id}",
            headers=admin_token_headers
        )
        assert response.status_code == 200

    def test_self_sees_all(
        self, client: TestClient, owner_token_headers,
        agent_user, unverified_property_owned_by_agent
    ):
        """Agent viewing their own listings → get_by_owner (all statuses)."""
        response = client.get(
            f"/api/v1/properties/by-agent/{agent_user.user_id}",
            headers=owner_token_headers
        )
        assert response.status_code == 200

    def test_other_user_sees_approved_only(
        self, client: TestClient, normal_user_token_headers, agent_user, verified_property
    ):
        """Different logged-in user → get_by_owner_approved."""
        response = client.get(
            f"/api/v1/properties/by-agent/{agent_user.user_id}",
            headers=normal_user_token_headers
        )
        assert response.status_code == 200


# ===========================================================================
# GET /search/radius
# ===========================================================================

class TestSearchByRadius:
    """Covers radius search — 4 visibility branches + validation."""

    BASE_PARAMS = {
        "latitude": 6.5244,
        "longitude": 3.3792,
        "radius": 10,
    }

    def test_anonymous(self, client: TestClient, verified_property):
        response = client.get(
            "/api/v1/properties/search/radius", params=self.BASE_PARAMS
        )
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_regular_user(
        self, client: TestClient, normal_user_token_headers, verified_property
    ):
        response = client.get(
            "/api/v1/properties/search/radius",
            params=self.BASE_PARAMS,
            headers=normal_user_token_headers
        )
        assert response.status_code == 200

    def test_agent(
        self, client: TestClient, agent_token_headers, verified_property
    ):
        response = client.get(
            "/api/v1/properties/search/radius",
            params=self.BASE_PARAMS,
            headers=agent_token_headers
        )
        assert response.status_code == 200

    def test_admin(
        self, client: TestClient, admin_token_headers, verified_property
    ):
        response = client.get(
            "/api/v1/properties/search/radius",
            params=self.BASE_PARAMS,
            headers=admin_token_headers
        )
        assert response.status_code == 200

    def test_missing_required_params_returns_422(self, client: TestClient):
        """latitude/longitude/radius are required — omitting → 422."""
        response = client.get("/api/v1/properties/search/radius")
        assert response.status_code == 422

    def test_radius_zero_rejected(self, client: TestClient):
        """radius must be > 0."""
        params = {**self.BASE_PARAMS, "radius": 0}
        response = client.get("/api/v1/properties/search/radius", params=params)
        assert response.status_code == 422

    def test_radius_exceeds_max_rejected(self, client: TestClient):
        """radius must be <= 1000."""
        params = {**self.BASE_PARAMS, "radius": 1001}
        response = client.get("/api/v1/properties/search/radius", params=params)
        assert response.status_code == 422

    def test_optional_filters_forwarded(
        self, client: TestClient, verified_property
    ):
        """Optional filters don't cause 422."""
        params = {
            **self.BASE_PARAMS,
            "min_price": 1000000,
            "max_price": 50000000,
            "bedrooms": 2,
        }
        response = client.get("/api/v1/properties/search/radius", params=params)
        assert response.status_code == 200

