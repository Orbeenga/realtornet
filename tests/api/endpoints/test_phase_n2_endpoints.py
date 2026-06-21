"""
API-layer tests for Phase N.2 endpoints:
- GET /api/v1/properties/agency-queue/
- GET /api/v1/properties/agency-inventory/
- GET /api/v1/properties/pending-admin/
- PATCH /api/v1/properties/{id}/reject-permanent/
"""
import pytest
from fastapi.testclient import TestClient

from app.models.listing_events import ListingEvent


# ===========================================================================
# GET /agency-queue/  —  agency_owner only
# ===========================================================================

class TestGetAgencyQueue:
    """GET /api/v1/properties/agency-queue/ — listings at agency_review for own agency."""

    def test_agency_owner_sees_own_queue(
        self, client: TestClient, db, agency_owner_token_headers, owner_token_headers,
        unverified_property_owned_by_agent,
    ):
        """Agency owner sees listings at agency_review in their agency."""
        listing_id = unverified_property_owned_by_agent.property_id
        # Move listing to agency_review
        client.patch(
            f"/api/v1/properties/{listing_id}/submit-for-review",
            headers=owner_token_headers,
        )

        response = client.get(
            "/api/v1/properties/agency-queue",
            headers=agency_owner_token_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert any(p["property_id"] == listing_id and p["moderation_status"] == "agency_review" for p in data)

    def test_agent_gets_403(
        self, client: TestClient, agent_token_headers,
    ):
        """Agent cannot access agency-queue."""
        response = client.get("/api/v1/properties/agency-queue", headers=agent_token_headers)
        assert response.status_code == 403
        assert "Agency owner privileges required" in response.json()["detail"]

    def test_admin_gets_403(
        self, client: TestClient, admin_token_headers,
    ):
        """Admin cannot access agency-queue."""
        response = client.get("/api/v1/properties/agency-queue", headers=admin_token_headers)
        assert response.status_code == 403
        assert "Agency owner privileges required" in response.json()["detail"]

    def test_pagination(
        self, client: TestClient, agency_owner_token_headers,
    ):
        """Pagination params are accepted."""
        response = client.get(
            "/api/v1/properties/agency-queue",
            headers=agency_owner_token_headers,
            params={"page": 1, "page_size": 10},
        )
        assert response.status_code == 200


# ===========================================================================
# GET /agency-inventory/  —  agent or agency_owner
# ===========================================================================

class TestGetAgencyInventory:
    """GET /api/v1/properties/agency-inventory/ — live listings for own agency."""

    def _walk_to_live(self, client, listing_id, owner_headers, agency_owner_headers, admin_headers):
        """Walk a listing through the full chain to live."""
        client.patch(f"/api/v1/properties/{listing_id}/submit-for-review", headers=owner_headers)
        client.patch(f"/api/v1/properties/{listing_id}/agency-approve", headers=agency_owner_headers)
        client.patch(
            f"/api/v1/properties/{listing_id}/verify",
            json={"moderation_status": "live"},
            headers=admin_headers,
        )

    def test_agency_owner_sees_own_live_inventory(
        self, client: TestClient, db, agency_owner_token_headers, owner_token_headers,
        admin_token_headers, unverified_property_owned_by_agent,
    ):
        """Agency owner sees live listings in their agency."""
        listing_id = unverified_property_owned_by_agent.property_id
        self._walk_to_live(client, listing_id, owner_token_headers, agency_owner_token_headers, admin_token_headers)

        response = client.get(
            "/api/v1/properties/agency-inventory",
            headers=agency_owner_token_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert any(p["property_id"] == listing_id and p["moderation_status"] == "live" for p in data)

    def test_agent_sees_own_agency_inventory(
        self, client: TestClient, db, owner_token_headers, agency_owner_token_headers,
        admin_token_headers, unverified_property_owned_by_agent,
    ):
        """Agent sees live listings in their agency."""
        listing_id = unverified_property_owned_by_agent.property_id
        self._walk_to_live(client, listing_id, owner_token_headers, agency_owner_token_headers, admin_token_headers)

        response = client.get(
            "/api/v1/properties/agency-inventory",
            headers=owner_token_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_normal_user_gets_403(
        self, client: TestClient, normal_user_token_headers,
    ):
        """Seeker cannot access agency-inventory."""
        response = client.get("/api/v1/properties/agency-inventory", headers=normal_user_token_headers)
        assert response.status_code == 403
        assert "Only agents and agency owners" in response.json()["detail"]

    def test_pagination(
        self, client: TestClient, agent_token_headers,
    ):
        """Pagination params are accepted."""
        response = client.get(
            "/api/v1/properties/agency-inventory",
            headers=agent_token_headers,
            params={"page": 1, "page_size": 10},
        )
        assert response.status_code == 200


# ===========================================================================
# GET /pending-admin/  —  agency_owner only
# ===========================================================================

class TestGetPendingAdmin:
    """GET /api/v1/properties/pending-admin/ — listings at admin_review for own agency."""

    def test_agency_owner_sees_pending_admin(
        self, client: TestClient, db, agency_owner_token_headers, owner_token_headers,
        unverified_property_owned_by_agent,
    ):
        """Agency owner sees listings at admin_review in their agency."""
        listing_id = unverified_property_owned_by_agent.property_id
        # Move listing to admin_review
        client.patch(f"/api/v1/properties/{listing_id}/submit-for-review", headers=owner_token_headers)
        client.patch(f"/api/v1/properties/{listing_id}/agency-approve", headers=agency_owner_token_headers)

        response = client.get(
            "/api/v1/properties/pending-admin",
            headers=agency_owner_token_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert any(p["property_id"] == listing_id and p["moderation_status"] == "admin_review" for p in data)

    def test_agent_gets_403(
        self, client: TestClient, agent_token_headers,
    ):
        """Agent cannot access pending-admin."""
        response = client.get("/api/v1/properties/pending-admin", headers=agent_token_headers)
        assert response.status_code == 403
        assert "Agency owner privileges required" in response.json()["detail"]

    def test_admin_gets_403(
        self, client: TestClient, admin_token_headers,
    ):
        """Admin cannot access pending-admin (agency_owner only)."""
        response = client.get("/api/v1/properties/pending-admin", headers=admin_token_headers)
        assert response.status_code == 403
        assert "Agency owner privileges required" in response.json()["detail"]

    def test_pagination(
        self, client: TestClient, agency_owner_token_headers,
    ):
        """Pagination params are accepted."""
        response = client.get(
            "/api/v1/properties/pending-admin",
            headers=agency_owner_token_headers,
            params={"page": 1, "page_size": 10},
        )
        assert response.status_code == 200


# ===========================================================================
# PATCH /{id}/reject-permanent/  —  admin only, revoked → admin_rejected
# ===========================================================================

class TestRejectPermanent:
    """PATCH /api/v1/properties/{id}/reject-permanent/ — revoked → admin_rejected."""

    def _walk_to_revoked(self, client, listing_id, owner_headers, agency_owner_headers, admin_headers):
        """Walk a listing to revoked state."""
        client.patch(f"/api/v1/properties/{listing_id}/submit-for-review", headers=owner_headers)
        client.patch(f"/api/v1/properties/{listing_id}/agency-approve", headers=agency_owner_headers)
        client.patch(
            f"/api/v1/properties/{listing_id}/verify",
            json={"moderation_status": "live"},
            headers=admin_headers,
        )
        client.patch(
            f"/api/v1/properties/{listing_id}/revoke",
            json={"moderation_reason": "Policy violation"},
            headers=admin_headers,
        )

    def test_admin_can_reject_permanent(
        self, client: TestClient, db, owner_token_headers, agency_owner_token_headers,
        admin_token_headers, unverified_property_owned_by_agent,
    ):
        """Admin transitions revoked → admin_rejected with reason."""
        listing_id = unverified_property_owned_by_agent.property_id
        self._walk_to_revoked(client, listing_id, owner_token_headers, agency_owner_token_headers, admin_token_headers)

        response = client.patch(
            f"/api/v1/properties/{listing_id}/reject-permanent",
            json={"moderation_reason": "Irreparable policy violation"},
            headers=admin_token_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["moderation_status"] == "admin_rejected"
        assert data["moderation_reason"] == "Irreparable policy violation"
        assert data["is_verified"] is False

    def test_reject_permanent_writes_listing_event(
        self, client: TestClient, db, owner_token_headers, agency_owner_token_headers,
        admin_token_headers, unverified_property_owned_by_agent,
    ):
        """reject-permanent appends a listing_events row."""
        listing_id = unverified_property_owned_by_agent.property_id
        self._walk_to_revoked(client, listing_id, owner_token_headers, agency_owner_token_headers, admin_token_headers)

        client.patch(
            f"/api/v1/properties/{listing_id}/reject-permanent",
            json={"moderation_reason": "Final rejection"},
            headers=admin_token_headers,
        )

        events = db.query(ListingEvent).filter(ListingEvent.listing_id == listing_id).all()
        reject_events = [e for e in events if e.to_status == "admin_rejected"]
        assert len(reject_events) == 1
        assert reject_events[0].reason == "Final rejection"

    def test_non_admin_gets_403(
        self, client: TestClient, owner_token_headers, agency_owner_token_headers,
        admin_token_headers, unverified_property_owned_by_agent,
    ):
        """Non-admin cannot reject-permanent."""
        listing_id = unverified_property_owned_by_agent.property_id
        self._walk_to_revoked(client, listing_id, owner_token_headers, agency_owner_token_headers, admin_token_headers)

        response = client.patch(
            f"/api/v1/properties/{listing_id}/reject-permanent",
            json={"moderation_reason": "Test"},
            headers=owner_token_headers,
        )
        assert response.status_code == 403
        assert "Admin role required" in response.json()["detail"]

    def test_wrong_state_returns_422(
        self, client: TestClient, db, owner_token_headers, agency_owner_token_headers,
        admin_token_headers, unverified_property_owned_by_agent,
    ):
        """Live listing cannot be reject-permanented (must be revoked first)."""
        listing_id = unverified_property_owned_by_agent.property_id
        # Walk to live only
        client.patch(f"/api/v1/properties/{listing_id}/submit-for-review", headers=owner_token_headers)
        client.patch(f"/api/v1/properties/{listing_id}/agency-approve", headers=agency_owner_token_headers)
        client.patch(
            f"/api/v1/properties/{listing_id}/verify",
            json={"moderation_status": "live"},
            headers=admin_token_headers,
        )

        response = client.patch(
            f"/api/v1/properties/{listing_id}/reject-permanent",
            json={"moderation_reason": "Test"},
            headers=admin_token_headers,
        )
        assert response.status_code == 422
        assert "Illegal moderation status transition" in response.json()["detail"]

    def test_empty_reason_returns_422(
        self, client: TestClient, db, owner_token_headers, agency_owner_token_headers,
        admin_token_headers, unverified_property_owned_by_agent,
    ):
        """Empty reason for reject-permanent returns 422."""
        listing_id = unverified_property_owned_by_agent.property_id
        self._walk_to_revoked(client, listing_id, owner_token_headers, agency_owner_token_headers, admin_token_headers)

        response = client.patch(
            f"/api/v1/properties/{listing_id}/reject-permanent",
            json={"moderation_reason": ""},
            headers=admin_token_headers,
        )
        assert response.status_code == 422

    def test_nonexistent_property_returns_404(
        self, client: TestClient, admin_token_headers,
    ):
        """Reject-permanent on a non-existent property returns 404."""
        response = client.patch(
            "/api/v1/properties/999999/reject-permanent",
            json={"moderation_reason": "Test"},
            headers=admin_token_headers,
        )
        assert response.status_code == 404
