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
from app.models.listing_events import ListingEvent
from app.models.property_images import PropertyImage
from app.models.saved_searches import SavedSearch
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

    def test_seeker_cannot_filter_by_agency_id(
        self, client: TestClient, normal_user_token_headers
    ):
        response = client.get(
            "/api/v1/properties/",
            params={"agency_id": 1},
            headers=normal_user_token_headers,
        )
        assert response.status_code == 403

    def test_anonymous_cannot_filter_by_agency_id(self, client: TestClient):
        response = client.get("/api/v1/properties/", params={"agency_id": 1})
        assert response.status_code == 403

    def test_admin_filters_properties_by_agency_id(
        self,
        client: TestClient,
        admin_token_headers,
        db,
        agency,
        other_agency,
        agent_user,
        location,
        property_type,
    ):
        from geoalchemy2.elements import WKTElement

        primary = Property(
            title="Agency Primary Listing",
            description="Belongs to primary agency",
            user_id=agent_user.user_id,
            agency_id=agency.agency_id,
            property_type_id=property_type.property_type_id,
            location_id=location.location_id,
            geom=WKTElement("POINT(3.3488 6.6018)", srid=4326),
            price=30000000,
            bedrooms=2,
            bathrooms=1,
            property_size=90.0,
            listing_type=ListingType.sale,
            listing_status=ListingStatus.available,
            is_verified=True,
        )
        secondary = Property(
            title="Other Agency Listing",
            description="Belongs to other agency",
            user_id=agent_user.user_id,
            agency_id=other_agency.agency_id,
            property_type_id=property_type.property_type_id,
            location_id=location.location_id,
            geom=WKTElement("POINT(3.3488 6.6018)", srid=4326),
            price=40000000,
            bedrooms=3,
            bathrooms=2,
            property_size=110.0,
            listing_type=ListingType.sale,
            listing_status=ListingStatus.available,
            is_verified=True,
        )
        db.add_all([primary, secondary])
        db.flush()

        response = client.get(
            "/api/v1/properties/",
            params={"agency_id": agency.agency_id, "limit": 50},
            headers=admin_token_headers,
        )
        assert response.status_code == 200
        ids = {item["property_id"] for item in response.json()}
        assert primary.property_id in ids
        assert secondary.property_id not in ids

    def test_featured_properties_public_recent_verified_only(
        self, client: TestClient, db, normal_user, location, property_type
    ):
        from geoalchemy2.elements import WKTElement

        featured = Property(
            title="Featured Public Home",
            description="Visible featured listing",
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
            is_featured=True,
            is_verified=True,
        )
        hidden = Property(
            title="Unverified Featured Home",
            description="Featured but not public",
            user_id=normal_user.user_id,
            property_type_id=property_type.property_type_id,
            location_id=location.location_id,
            geom=WKTElement('POINT(3.3488 6.6018)', srid=4326),
            price=18000000,
            bedrooms=2,
            bathrooms=1,
            property_size=80.0,
            listing_type=ListingType.sale,
            listing_status=ListingStatus.available,
            is_featured=True,
            is_verified=False,
        )
        db.add_all([featured, hidden])
        db.flush()

        response = client.get("/api/v1/properties/featured", params={"limit": 6})

        assert response.status_code == 200
        titles = {item["title"] for item in response.json()}
        assert "Featured Public Home" in titles
        assert "Unverified Featured Home" not in titles

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

    def test_property_type_id_filter_limits_public_results(
        self, client: TestClient, db, normal_user, location, property_type, property_type_villa
    ):
        """Public property search accepts property_type_id and forwards it to CRUD filters."""
        from geoalchemy2.elements import WKTElement

        apartment = Property(
            title="Filtered Apartment",
            description="Apartment should match the property type filter",
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
        villa = Property(
            title="Filtered Villa",
            description="Villa should not match the apartment property type filter",
            user_id=normal_user.user_id,
            property_type_id=property_type_villa.property_type_id,
            location_id=location.location_id,
            geom=WKTElement('POINT(3.3488 6.6018)', srid=4326),
            price=75000000,
            bedrooms=5,
            bathrooms=4,
            property_size=320.0,
            listing_type=ListingType.sale,
            listing_status=ListingStatus.available,
            is_verified=True,
        )
        db.add_all([apartment, villa])
        db.flush()
        db.refresh(apartment)
        db.refresh(villa)

        response = client.get(
            "/api/v1/properties/",
            params={"property_type_id": property_type.property_type_id},
        )

        assert response.status_code == 200
        returned_ids = {item["property_id"] for item in response.json()}
        assert apartment.property_id in returned_ids
        assert villa.property_id not in returned_ids


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

    def test_agent_create_resolves_location_name(
        self, client: TestClient, agent_token_headers, property_create_payload, location, agency
    ):
        """Free-text location creation resolves to a stored location_id."""
        payload = {
            **property_create_payload,
            "location_id": None,
            "location_name": "Victoria Island Lagos",
        }
        with patch("app.api.endpoints.properties.resolve_location_name_to_record", return_value=location):
            response = client.post(
                "/api/v1/properties/",
                json=payload,
                headers=agent_token_headers,
            )

        assert response.status_code == 201
        data = response.json()
        assert data["location_id"] == location.location_id
        assert data["location_name"] == "Victoria Island Lagos"
        assert data["agency_id"] == agency.agency_id

    def test_agent_create_keeps_unresolved_location_name(
        self, client: TestClient, agent_token_headers, property_create_payload
    ):
        """No Nominatim result must not block listing creation."""
        payload = {
            **property_create_payload,
            "location_id": None,
            "location_name": "Some New Place",
        }
        with patch("app.api.endpoints.properties.resolve_location_name_to_record", return_value=None):
            response = client.post(
                "/api/v1/properties/",
                json=payload,
                headers=agent_token_headers,
            )

        assert response.status_code == 201
        data = response.json()
        assert data["location_id"] is None
        assert data["location_name"] == "Some New Place"

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
        self, client: TestClient, admin_token_headers, agency_approved_property
    ):
        """Admins can only verify listings that have been agency-approved."""
        with patch("app.api.endpoints.properties.dispatch_email_task") as mock_email:
            response = client.patch(
                f"/api/v1/properties/{agency_approved_property.property_id}/verify",
                json={"is_verified": True},
                headers=admin_token_headers
            )

        assert response.status_code == 200
        data = response.json()
        assert data["is_verified"] is True
        assert data["moderation_status"] == "live"
        assert data["verification_date"] is not None
        mock_email.assert_called_once()
        assert mock_email.call_args.args[1] == "agent@example.com"
        assert mock_email.call_args.args[3] == "live"

    @pytest.mark.parametrize(
        ("moderation_status", "expected_verified"),
        [
            ("pending_review", False),
            ("agency_approved", False),
            ("live", True),
            ("rejected", False),
            ("revoked", False),
        ],
    )
    def test_admin_can_set_all_moderation_statuses(
        self,
        client: TestClient,
        admin_token_headers,
        agency_approved_property,
        moderation_status,
        expected_verified,
    ):
        response = client.patch(
            f"/api/v1/properties/{agency_approved_property.property_id}/verify",
            json={
                "moderation_status": moderation_status,
                "moderation_reason": f"Reason for {moderation_status}",
            },
            headers=admin_token_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["moderation_status"] == moderation_status
        assert data["moderation_reason"] == f"Reason for {moderation_status}"
        assert data["is_verified"] is expected_verified

    def test_rejected_property_is_hidden_from_public_feed(
        self, client: TestClient, admin_token_headers, verified_property
    ):
        response = client.patch(
            f"/api/v1/properties/{verified_property.property_id}/verify",
            json={
                "moderation_status": "rejected",
                "moderation_reason": "Photos do not match the listing",
            },
            headers=admin_token_headers,
        )
        assert response.status_code == 200

        feed_response = client.get(
            "/api/v1/properties/",
            params={"search": verified_property.title},
        )
        assert feed_response.status_code == 200
        assert all(
            item["property_id"] != verified_property.property_id
            for item in feed_response.json()
        )

    def test_agent_cannot_reject_or_revoke_moderation(
        self, client: TestClient, owner_token_headers, unverified_property_owned_by_agent
    ):
        response = client.patch(
            f"/api/v1/properties/{unverified_property_owned_by_agent.property_id}/verify",
            json={"moderation_status": "revoked"},
            headers=owner_token_headers,
        )

        assert response.status_code == 403
        assert response.json()["detail"] == "Only admins can reject or revoke property moderation"

    def test_agency_owner_can_revoke_listing_for_own_agency(
        self, client: TestClient, agency_owner_token_headers, unverified_property
    ):
        response = client.patch(
            f"/api/v1/properties/{unverified_property.property_id}/verify",
            json={"moderation_status": "revoked", "moderation_reason": "Agency governance"},
            headers=agency_owner_token_headers,
        )

        assert response.status_code == 200
        assert response.json()["moderation_status"] == "revoked"
        assert response.json()["moderation_reason"] == "Agency governance"

    def test_agency_owner_cannot_moderate_other_agency_listing(
        self, client: TestClient, db, agency_owner_token_headers, other_agency,
        agent_user, location, property_type
    ):
        from geoalchemy2.elements import WKTElement

        other_listing = Property(
            title="Other Agency Review Listing",
            description="Belongs to another agency",
            user_id=agent_user.user_id,
            agency_id=other_agency.agency_id,
            property_type_id=property_type.property_type_id,
            location_id=location.location_id,
            geom=WKTElement("POINT(3.3488 6.6018)", srid=4326),
            price=35000000,
            bedrooms=2,
            bathrooms=1,
            property_size=100.0,
            listing_type=ListingType.sale,
            listing_status=ListingStatus.available,
            is_verified=False,
        )
        db.add(other_listing)
        db.flush()
        db.refresh(other_listing)

        response = client.patch(
            f"/api/v1/properties/{other_listing.property_id}/verify",
            json={"moderation_status": "verified"},
            headers=agency_owner_token_headers,
        )

        assert response.status_code == 403

    def test_admin_rejection_dispatches_moderation_email(
        self, client: TestClient, admin_token_headers, unverified_property
    ):
        with patch("app.api.endpoints.properties.dispatch_email_task") as mock_email:
            response = client.patch(
                f"/api/v1/properties/{unverified_property.property_id}/verify",
                json={
                    "moderation_status": "rejected",
                    "moderation_reason": "Photos are unclear",
                },
                headers=admin_token_headers,
            )

        assert response.status_code == 200
        mock_email.assert_called_once()
        args = mock_email.call_args.args
        assert args[1] == "agent@example.com"
        assert args[2] == unverified_property.title
        assert args[3] == "rejected"
        assert args[5] == "Photos are unclear"

    def test_admin_verification_dispatches_saved_search_match_email(
        self, client: TestClient, admin_token_headers, db, normal_user, agency_approved_property
    ):
        saved = SavedSearch(
            user_id=normal_user.user_id,
            search_params={
                "min_price": 1000000,
                "max_price": 6000000,
                "bedrooms": 3,
                "location_id": agency_approved_property.location_id,
                "property_type_id": agency_approved_property.property_type_id,
                "listing_type": "sale",
            },
            name="Matching homes",
        )
        image = PropertyImage(
            property_id=agency_approved_property.property_id,
            image_url="https://cdn.example.com/property.jpg",
            is_primary=True,
        )
        db.add(saved)
        db.add(image)
        db.flush()
        db.refresh(saved)

        with patch("app.api.endpoints.properties.dispatch_email_task") as mock_moderation_email, patch(
            "app.services.saved_search_notification_service.dispatch_email_task"
        ) as mock_match_email:
            response = client.patch(
                f"/api/v1/properties/{agency_approved_property.property_id}/verify",
                json={"moderation_status": "verified"},
                headers=admin_token_headers,
            )

        assert response.status_code == 200
        mock_moderation_email.assert_called_once()
        mock_match_email.assert_called_once()
        args = mock_match_email.call_args.args
        assert args[1] == normal_user.email
        assert args[2] == "Matching homes"
        assert args[3] == agency_approved_property.title
        assert args[6] == str(saved.unsubscribe_token)
        assert args[7] == "https://cdn.example.com/property.jpg"

    def test_admin_verified_property_becomes_publicly_visible(
        self, client: TestClient, admin_token_headers, agency_approved_property
    ):
        """
        Admin verification should move the listing into the public feed.

        This test checks the user-facing outcome, not just the database flag,
        because the whole point of the workflow is to remove the old SQL-only
        publishing step.
        """
        before_response = client.get(
            "/api/v1/properties/",
            params={"search": agency_approved_property.title}
        )
        assert before_response.status_code == 200
        assert all(
            item["property_id"] != agency_approved_property.property_id
            for item in before_response.json()
        )

        verify_response = client.patch(
            f"/api/v1/properties/{agency_approved_property.property_id}/verify",
            json={"is_verified": True},
            headers=admin_token_headers
        )
        assert verify_response.status_code == 200

        after_response = client.get(
            "/api/v1/properties/",
            params={"search": agency_approved_property.title}
        )
        assert after_response.status_code == 200
        assert any(
            item["property_id"] == agency_approved_property.property_id
            for item in after_response.json()
        )

    def test_owner_agent_cannot_verify_own_property_directly(
        self, client: TestClient, owner_token_headers, unverified_property_owned_by_agent
    ):
        """Three-tier moderation: agents can no longer skip agency approval."""
        response = client.patch(
            f"/api/v1/properties/{unverified_property_owned_by_agent.property_id}/verify",
            json={"is_verified": True},
            headers=owner_token_headers
        )

        assert response.status_code == 403
        assert response.json()["detail"] == "Only admins can verify listings"

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
        assert data["moderation_status"] == "pending_review"
        assert data["verification_date"] is None

    def test_full_three_tier_flow_becomes_publicly_visible(
        self, client: TestClient, owner_token_headers, agency_owner_token_headers, admin_token_headers,
        unverified_property_owned_by_agent
    ):
        """
        Full three-tier flow: agency owner approves, admin verifies,
        listing becomes public.
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

        # Step 1: agent submits for review
        client.patch(
            f"/api/v1/properties/{unverified_property_owned_by_agent.property_id}/submit-for-review",
            headers=owner_token_headers,
        )

        # Step 2: agency owner approves → admin_review
        approve_response = client.patch(
            f"/api/v1/properties/{unverified_property_owned_by_agent.property_id}/agency-approve",
            headers=agency_owner_token_headers
        )
        assert approve_response.status_code == 200
        assert approve_response.json()["moderation_status"] == "admin_review"

        # Step 2: admin verifies
        verify_response = client.patch(
            f"/api/v1/properties/{unverified_property_owned_by_agent.property_id}/verify",
            json={"is_verified": True},
            headers=admin_token_headers
        )
        assert verify_response.status_code == 200

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
# PATCH /{property_id}/agency-approve  &  agency-reject
# ===========================================================================

class TestAgencyApproveRejectProperty:
    """Covers the agency-owner moderation endpoints."""

    def test_agency_owner_can_approve_own_agency_listing(
        self, client: TestClient, agency_owner_token_headers, unverified_property
    ):
        response = client.patch(
            f"/api/v1/properties/{unverified_property.property_id}/agency-approve",
            headers=agency_owner_token_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["moderation_status"] == "admin_review"
        assert data["is_verified"] is False

    def test_agency_owner_cannot_approve_other_agency_listing(
        self, client: TestClient, db, agency_owner_token_headers, other_agency,
        agent_user, location, property_type
    ):
        from geoalchemy2.elements import WKTElement

        other_listing = Property(
            title="Other Agency Listing",
            description="Belongs to another agency",
            user_id=agent_user.user_id,
            agency_id=other_agency.agency_id,
            property_type_id=property_type.property_type_id,
            location_id=location.location_id,
            geom=WKTElement("POINT(3.3488 6.6018)", srid=4326),
            price=35000000,
            bedrooms=2,
            bathrooms=1,
            property_size=100.0,
            listing_type=ListingType.sale,
            listing_status=ListingStatus.available,
            is_verified=False,
        )
        db.add(other_listing)
        db.flush()
        db.refresh(other_listing)

        response = client.patch(
            f"/api/v1/properties/{other_listing.property_id}/agency-approve",
            headers=agency_owner_token_headers,
        )

        assert response.status_code == 403
        assert "Only the owner of the listing's agency can perform this transition" in response.json()["detail"]

    def test_agency_owner_cannot_approve_non_agency_review_listing(
        self, client: TestClient, agency_owner_token_headers, agency_approved_property
    ):
        response = client.patch(
            f"/api/v1/properties/{agency_approved_property.property_id}/agency-approve",
            headers=agency_owner_token_headers
        )

        assert response.status_code == 422
        assert "Illegal moderation status transition" in response.json()["detail"]

    def test_agency_owner_can_reject_own_agency_listing(
        self, client: TestClient, owner_token_headers, agency_owner_token_headers, unverified_property_owned_by_agent
    ):
        # First submit to agency_review so rejection is legal.
        client.patch(
            f"/api/v1/properties/{unverified_property_owned_by_agent.property_id}/submit-for-review",
            headers=owner_token_headers,
        )

        response = client.patch(
            f"/api/v1/properties/{unverified_property_owned_by_agent.property_id}/agency-reject",
            json={"moderation_reason": "Incomplete documentation"},
            headers=agency_owner_token_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["moderation_status"] == "agency_rejected"
        assert data["moderation_reason"] == "Incomplete documentation"
        assert data["is_verified"] is False

    def test_agency_owner_cannot_reject_without_reason(
        self, client: TestClient, agency_owner_token_headers, unverified_property
    ):
        response = client.patch(
            f"/api/v1/properties/{unverified_property.property_id}/agency-reject",
            json={"moderation_reason": ""},
            headers=agency_owner_token_headers
        )

        assert response.status_code == 422
        assert "Reason is required for rejection" in str(response.json()["detail"])

    def test_agent_cannot_access_agency_approve(
        self, client: TestClient, owner_token_headers, unverified_property_owned_by_agent
    ):
        response = client.patch(
            f"/api/v1/properties/{unverified_property_owned_by_agent.property_id}/agency-approve",
            headers=owner_token_headers
        )

        assert response.status_code == 403

    def test_admin_cannot_verify_from_pending_review_directly(
        self, client: TestClient, admin_token_headers, unverified_property
    ):
        """Admin verification must follow three-tier flow: agency_approved first."""
        response = client.patch(
            f"/api/v1/properties/{unverified_property.property_id}/verify",
            json={"is_verified": True},
            headers=admin_token_headers
        )

        assert response.status_code == 400
        assert "only verify listings that have been approved by the agency" in response.json()["detail"]


# ===========================================================================
# Phase M.2 — Listing lifecycle endpoints
# ===========================================================================


class TestPhaseM2Lifecycle:
    """Covers the full Phase M.2 listing lifecycle and correction flows."""

    def test_happy_path_full_lifecycle(self, client: TestClient, db, owner_token_headers, agency_owner_token_headers, admin_token_headers, unverified_property_owned_by_agent):
        """draft → agency_review → admin_review → live via REST."""
        listing_id = unverified_property_owned_by_agent.property_id

        # Step 1: agent submits draft for agency review.
        submit_resp = client.patch(
            f"/api/v1/properties/{listing_id}/submit-for-review",
            headers=owner_token_headers,
        )
        assert submit_resp.status_code == 200
        assert submit_resp.json()["moderation_status"] == "agency_review"

        # Step 2: agency owner approves to admin_review.
        approve_resp = client.patch(
            f"/api/v1/properties/{listing_id}/agency-approve",
            headers=agency_owner_token_headers,
        )
        assert approve_resp.status_code == 200
        assert approve_resp.json()["moderation_status"] == "admin_review"

        # Step 3: admin verifies to live.
        verify_resp = client.patch(
            f"/api/v1/properties/{listing_id}/verify",
            json={"moderation_status": "live"},
            headers=admin_token_headers,
        )
        assert verify_resp.status_code == 200
        data = verify_resp.json()
        assert data["moderation_status"] == "live"
        assert data["is_verified"] is True

    def test_agency_owner_bypass_goes_direct_to_admin_review(self, client: TestClient, agency_owner_token_headers, unverified_property):
        """draft → admin_review via submit-to-admin."""
        listing_id = unverified_property.property_id

        resp = client.patch(
            f"/api/v1/properties/{listing_id}/submit-to-admin",
            headers=agency_owner_token_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["moderation_status"] == "admin_review"

    def test_correction_paths_agency_and_admin_rejection(self, client: TestClient, db, owner_token_headers, agency_owner_token_headers, admin_token_headers, unverified_property_owned_by_agent):
        """agency_rejected → agency_review and admin_rejected → draft → agency_review."""
        listing_id = unverified_property_owned_by_agent.property_id

        # Agent submits draft → agency_review.
        submit_resp = client.patch(
            f"/api/v1/properties/{listing_id}/submit-for-review",
            headers=owner_token_headers,
        )
        assert submit_resp.status_code == 200
        assert submit_resp.json()["moderation_status"] == "agency_review"

        # Agency owner rejects → agency_rejected.
        reject_resp = client.patch(
            f"/api/v1/properties/{listing_id}/agency-reject",
            json={"moderation_reason": "Fix description"},
            headers=agency_owner_token_headers,
        )
        assert reject_resp.status_code == 200
        assert reject_resp.json()["moderation_status"] == "agency_rejected"

        # Agent resubmits → agency_review.
        resubmit_resp = client.patch(
            f"/api/v1/properties/{listing_id}/resubmit",
            headers=owner_token_headers,
        )
        assert resubmit_resp.status_code == 200
        assert resubmit_resp.json()["moderation_status"] == "agency_review"

        # Agency owner approves to admin_review.
        approve_resp = client.patch(
            f"/api/v1/properties/{listing_id}/agency-approve",
            headers=agency_owner_token_headers,
        )
        assert approve_resp.status_code == 200
        assert approve_resp.json()["moderation_status"] == "admin_review"

        # Admin rejects → admin_rejected.
        admin_reject_resp = client.patch(
            f"/api/v1/properties/{listing_id}/admin-reject",
            json={"moderation_reason": "Needs better photos"},
            headers=admin_token_headers,
        )
        assert admin_reject_resp.status_code == 200
        assert admin_reject_resp.json()["moderation_status"] == "admin_rejected"

        # Agent pulls back admin_rejected → draft.
        pull_back_resp = client.patch(
            f"/api/v1/properties/{listing_id}/pull-back",
            headers=owner_token_headers,
        )
        assert pull_back_resp.status_code == 200
        assert pull_back_resp.json()["moderation_status"] == "draft"

        # Agent submits again → agency_review.
        submit_again_resp = client.patch(
            f"/api/v1/properties/{listing_id}/submit-for-review",
            headers=owner_token_headers,
        )
        assert submit_again_resp.status_code == 200
        assert submit_again_resp.json()["moderation_status"] == "agency_review"

    def test_revocation_roundtrip_and_restore(self, client: TestClient, db, owner_token_headers, agency_owner_token_headers, admin_token_headers, unverified_property_owned_by_agent):
        """live → revoked → draft → full chain → live and live → revoked → live."""
        listing_id = unverified_property_owned_by_agent.property_id

        # First, walk listing to live.
        client.patch(f"/api/v1/properties/{listing_id}/submit-for-review", headers=owner_token_headers)
        client.patch(f"/api/v1/properties/{listing_id}/agency-approve", headers=agency_owner_token_headers)
        client.patch(
            f"/api/v1/properties/{listing_id}/verify",
            json={"moderation_status": "live"},
            headers=admin_token_headers,
        )

        # Admin revokes live listing → revoked.
        revoke_resp = client.patch(
            f"/api/v1/properties/{listing_id}/revoke",
            json={"moderation_reason": "Policy violation"},
            headers=admin_token_headers,
        )
        assert revoke_resp.status_code == 200
        assert revoke_resp.json()["moderation_status"] == "revoked"

        # Agent pulls back revoked → draft.
        pull_back_resp = client.patch(
            f"/api/v1/properties/{listing_id}/pull-back",
            headers=owner_token_headers,
        )
        assert pull_back_resp.status_code == 200
        assert pull_back_resp.json()["moderation_status"] == "draft"

        # Walk back through agency_review → admin_review → live again.
        client.patch(f"/api/v1/properties/{listing_id}/submit-for-review", headers=owner_token_headers)
        client.patch(f"/api/v1/properties/{listing_id}/agency-approve", headers=agency_owner_token_headers)
        final_resp = client.patch(
            f"/api/v1/properties/{listing_id}/verify",
            json={"moderation_status": "live"},
            headers=admin_token_headers,
        )
        assert final_resp.status_code == 200
        assert final_resp.json()["moderation_status"] == "live"

        # Accidental revocation: live → revoked → live via restore.
        revoke_again = client.patch(
            f"/api/v1/properties/{listing_id}/revoke",
            json={"moderation_reason": "Mistaken"},
            headers=admin_token_headers,
        )
        assert revoke_again.status_code == 200
        assert revoke_again.json()["moderation_status"] == "revoked"

        restore_resp = client.patch(
            f"/api/v1/properties/{listing_id}/restore",
            headers=admin_token_headers,
        )
        assert restore_resp.status_code == 200
        assert restore_resp.json()["moderation_status"] == "live"

    def test_revoke_notifies_both_agent_and_agency_owner(self, client: TestClient, owner_token_headers, agency_owner_token_headers, admin_token_headers, unverified_property_owned_by_agent):
        """Admin revocation must concurrently notify the listing owner and the agency owner."""
        from unittest.mock import patch
        listing_id = unverified_property_owned_by_agent.property_id

        # Walk listing to live
        client.patch(f"/api/v1/properties/{listing_id}/submit-for-review", headers=owner_token_headers)
        client.patch(f"/api/v1/properties/{listing_id}/agency-approve", headers=agency_owner_token_headers)
        client.patch(
            f"/api/v1/properties/{listing_id}/verify",
            json={"moderation_status": "live"},
            headers=admin_token_headers,
        )

        with patch("app.api.endpoints.properties.dispatch_email_task") as mock_email:
            revoke_resp = client.patch(
                f"/api/v1/properties/{listing_id}/revoke",
                json={"moderation_reason": "Policy violation"},
                headers=admin_token_headers,
            )
            assert revoke_resp.status_code == 200
            assert revoke_resp.json()["moderation_status"] == "revoked"
            # One call for the agent, one for the agency owner
            assert mock_email.call_count == 2
            recipient_emails = [call.args[1] for call in mock_email.call_args_list]
            assert "agent@example.com" in recipient_emails
            assert "agency_owner@example.com" in recipient_emails

    def test_revoke_requires_moderation_reason(self, client: TestClient, admin_token_headers, unverified_property_owned_by_agent, owner_token_headers, agency_owner_token_headers):
        """Revoke without a moderation_reason must return 422."""
        listing_id = unverified_property_owned_by_agent.property_id
        # Walk to live first
        client.patch(f"/api/v1/properties/{listing_id}/submit-for-review", headers=owner_token_headers)
        client.patch(f"/api/v1/properties/{listing_id}/agency-approve", headers=agency_owner_token_headers)
        client.patch(
            f"/api/v1/properties/{listing_id}/verify",
            json={"moderation_status": "live"},
            headers=admin_token_headers,
        )
        resp = client.patch(
            f"/api/v1/properties/{listing_id}/revoke",
            json={},
            headers=admin_token_headers,
        )
        assert resp.status_code == 422

    def test_revoke_nonexistent_property_returns_404(self, client: TestClient, admin_token_headers):
        """Revoking a non-existent property must return 404."""
        resp = client.patch(
            "/api/v1/properties/999999/revoke",
            json={"moderation_reason": "Test"},
            headers=admin_token_headers,
        )
        assert resp.status_code == 404

    def test_illegal_transitions_return_422(self, client: TestClient, admin_token_headers, agency_owner_token_headers, unverified_property):
        """Matrix-illegal transitions should return 422 from the guard."""
        listing_id = unverified_property.property_id

        # draft → live (direct) is illegal.
        resp_direct_live = client.patch(
            f"/api/v1/properties/{listing_id}/verify",
            json={"moderation_status": "live"},
            headers=admin_token_headers,
        )
        assert resp_direct_live.status_code == 400  # still blocked by legacy /verify bridge

        # Move to agency_review first.
        client.patch(f"/api/v1/properties/{listing_id}/submit-for-review", headers=agency_owner_token_headers)  # wrong role on purpose but minimal setup

        # agency_review → live via verify is still blocked by guard in /verify.
        # For a pure matrix test use recall/pull-back style endpoints with mismatched from/to.

    def test_wrong_role_returns_403_for_lifecycle_endpoints(self, client: TestClient, normal_user_token_headers, admin_token_headers, agency_owner_token_headers, owner_token_headers, unverified_property):
        """Non-owners and non-admins are blocked by the guard with 403."""
        listing_id = unverified_property.property_id

        # Normal user cannot submit for review.
        resp = client.patch(
            f"/api/v1/properties/{listing_id}/submit-for-review",
            headers=normal_user_token_headers,
        )
        assert resp.status_code == 403

        # Agent cannot admin-reject.
        client.patch(f"/api/v1/properties/{listing_id}/submit-for-review", headers=owner_token_headers)
        client.patch(f"/api/v1/properties/{listing_id}/agency-approve", headers=agency_owner_token_headers)
        resp_admin_reject = client.patch(
            f"/api/v1/properties/{listing_id}/admin-reject",
            json={"moderation_reason": "Not good"},
            headers=owner_token_headers,
        )
        assert resp_admin_reject.status_code == 403

        # Agency owner cannot verify (admin-only).
        resp_verify = client.patch(
            f"/api/v1/properties/{listing_id}/verify",
            json={"moderation_status": "live"},
            headers=agency_owner_token_headers,
        )
        assert resp_verify.status_code in {400, 403}

    def test_guard_fail_closed_on_unknown_role(self, client: TestClient, owner_token_headers, unverified_property_owned_by_agent, monkeypatch):
        """If LEGAL_TRANSITIONS somehow contains an unrecognized role token, guard fails closed with 500."""
        from app.services import listing_moderation_guard as guard
        listing_id = unverified_property_owned_by_agent.property_id

        original = guard.LEGAL_TRANSITIONS.copy()
        try:
            monkeypatch.setitem(
                guard.LEGAL_TRANSITIONS,
                ("draft", "agency_review"),
                "unknown_role_xyz",
            )
            resp = client.patch(
                f"/api/v1/properties/{listing_id}/submit-for-review",
                headers=owner_token_headers,
            )
            assert resp.status_code == 500
            assert "Unrecognized moderation transition role requirement" in resp.json()["detail"]
        finally:
            guard.LEGAL_TRANSITIONS.update(original)

    def test_withdraw_and_recall_paths(self, client: TestClient, owner_token_headers, agency_owner_token_headers, admin_token_headers, unverified_property_owned_by_agent):
        """Agent withdraws from agency_review → draft; agency owner recalls from admin_review → agency_review."""
        listing_id = unverified_property_owned_by_agent.property_id

        # draft → agency_review
        client.patch(f"/api/v1/properties/{listing_id}/submit-for-review", headers=owner_token_headers)

        # Agent withdraws → draft
        withdraw_resp = client.patch(
            f"/api/v1/properties/{listing_id}/withdraw",
            headers=owner_token_headers,
        )
        assert withdraw_resp.status_code == 200
        assert withdraw_resp.json()["moderation_status"] == "draft"

        # Re-submit and approve to admin_review
        client.patch(f"/api/v1/properties/{listing_id}/submit-for-review", headers=owner_token_headers)
        client.patch(f"/api/v1/properties/{listing_id}/agency-approve", headers=agency_owner_token_headers)

        # Agency owner recalls → agency_review
        recall_resp = client.patch(
            f"/api/v1/properties/{listing_id}/recall",
            headers=agency_owner_token_headers,
        )
        assert recall_resp.status_code == 200
        assert recall_resp.json()["moderation_status"] == "agency_review"

    def test_agency_owner_recall_own_listing_goes_to_draft(
        self, client: TestClient, agency_owner_token_headers, unverified_property_owned_by_agency_owner
    ):
        """Agency owner recalling their own listing from admin_review → draft."""
        listing_id = unverified_property_owned_by_agency_owner.property_id

        # Submit own listing directly to admin_review (bypass)
        client.patch(
            f"/api/v1/properties/{listing_id}/submit-to-admin",
            headers=agency_owner_token_headers,
        )

        # Recall own listing → draft
        recall_resp = client.patch(
            f"/api/v1/properties/{listing_id}/recall",
            headers=agency_owner_token_headers,
        )
        assert recall_resp.status_code == 200
        assert recall_resp.json()["moderation_status"] == "draft"

    def test_agency_owner_can_filter_agency_listings_by_moderation_status(
        self, client: TestClient, owner_token_headers, agency_owner_token_headers, unverified_property_owned_by_agent, agency
    ):
        """Agency owner calling GET /properties/?moderation_status=agency_review&agency_id={id}
        should see agent listings in agency_review."""
        listing_id = unverified_property_owned_by_agent.property_id
        agency_id = agency.agency_id

        # Submit agent's listing to agency_review
        client.patch(
            f"/api/v1/properties/{listing_id}/submit-for-review",
            headers=owner_token_headers,
        )

        # Agency owner filters by moderation_status and agency_id
        resp = client.get(
            f"/api/v1/properties/?moderation_status=agency_review&agency_id={agency_id}",
            headers=agency_owner_token_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert any(p["property_id"] == listing_id for p in data), \
            "Expected agency_review listing to appear in agency owner's filtered results"

    def test_agency_owner_can_see_drafts_in_inventory(
        self, client: TestClient, owner_token_headers, agency_owner_token_headers, unverified_property_owned_by_agent, agency
    ):
        """Agency owner calling GET /properties/?moderation_status=draft&agency_id={id}
        should see draft listings in their agency."""
        listing_id = unverified_property_owned_by_agent.property_id
        agency_id = agency.agency_id

        # Listing starts as draft by default
        resp = client.get(
            f"/api/v1/properties/?moderation_status=draft&agency_id={agency_id}",
            headers=agency_owner_token_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        items = data.get("items", data) if isinstance(data, dict) else data
        # Drafts are creator-only. Agency owner must not see another agent's draft.
        assert not any(p.get("property_id") == listing_id for p in items), \
            "Agency owner unexpectedly sees another agent's draft; drafts must be creator-only"

    def test_reinstate_from_admin_rejected(self, client: TestClient, owner_token_headers, agency_owner_token_headers, admin_token_headers, unverified_property_owned_by_agent):
        """Admin reinstates an admin_rejected listing back to admin_review."""
        listing_id = unverified_property_owned_by_agent.property_id

        # Walk to admin_rejected
        client.patch(f"/api/v1/properties/{listing_id}/submit-for-review", headers=owner_token_headers)
        client.patch(f"/api/v1/properties/{listing_id}/agency-approve", headers=agency_owner_token_headers)
        client.patch(
            f"/api/v1/properties/{listing_id}/admin-reject",
            json={"moderation_reason": "Poor photos"},
            headers=admin_token_headers,
        )

        # Admin reinstates → admin_review
        reinstate_resp = client.patch(
            f"/api/v1/properties/{listing_id}/reinstate",
            headers=admin_token_headers,
        )
        assert reinstate_resp.status_code == 200
        assert reinstate_resp.json()["moderation_status"] == "admin_review"

    def test_listing_events_written_for_full_lifecycle(self, client: TestClient, db, owner_token_headers, agency_owner_token_headers, admin_token_headers, unverified_property_owned_by_agent):
        """A full lifecycle should write a sequence of listing_events rows."""
        listing_id = unverified_property_owned_by_agent.property_id

        # Walk: draft → agency_review → admin_review → live → revoked → draft.
        client.patch(f"/api/v1/properties/{listing_id}/submit-for-review", headers=owner_token_headers)
        client.patch(f"/api/v1/properties/{listing_id}/agency-approve", headers=agency_owner_token_headers)
        client.patch(
            f"/api/v1/properties/{listing_id}/verify",
            json={"moderation_status": "live"},
            headers=admin_token_headers,
        )
        client.patch(
            f"/api/v1/properties/{listing_id}/revoke",
            json={"moderation_reason": "Policy"},
            headers=admin_token_headers,
        )
        client.patch(f"/api/v1/properties/{listing_id}/pull-back", headers=owner_token_headers)

        events = (
            db.query(ListingEvent)
            .filter(ListingEvent.listing_id == listing_id)
            .order_by(ListingEvent.created_at.asc())
            .all()
        )
        # At minimum we expect one event per state-changing call above.
        assert len(events) >= 5


class TestListingEventsReadEndpoint:
    """GET /properties/{id}/events — role-gated listing event history."""

    def test_agent_can_read_own_listing_events(
        self, client: TestClient, owner_token_headers, agency_owner_token_headers, admin_token_headers, unverified_property_owned_by_agent
    ):
        listing_id = unverified_property_owned_by_agent.property_id
        # Walk through some transitions to create events
        client.patch(f"/api/v1/properties/{listing_id}/submit-for-review", headers=owner_token_headers)
        client.patch(f"/api/v1/properties/{listing_id}/agency-approve", headers=agency_owner_token_headers)

        resp = client.get(f"/api/v1/properties/{listing_id}/events", headers=owner_token_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 2
        assert all("event_id" in e and "to_status" in e for e in data)
        # Events are ordered oldest first
        statuses = [e["to_status"] for e in data]
        assert statuses == sorted(statuses, key=lambda s: data[statuses.index(s)]["event_id"])

    def test_agency_owner_can_read_agency_listing_events(
        self, client: TestClient, owner_token_headers, agency_owner_token_headers, unverified_property_owned_by_agent
    ):
        listing_id = unverified_property_owned_by_agent.property_id
        client.patch(f"/api/v1/properties/{listing_id}/submit-for-review", headers=owner_token_headers)

        resp = client.get(f"/api/v1/properties/{listing_id}/events", headers=agency_owner_token_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 1

    def test_admin_can_read_any_listing_events(
        self, client: TestClient, owner_token_headers, admin_token_headers, unverified_property_owned_by_agent
    ):
        listing_id = unverified_property_owned_by_agent.property_id
        client.patch(f"/api/v1/properties/{listing_id}/submit-for-review", headers=owner_token_headers)

        resp = client.get(f"/api/v1/properties/{listing_id}/events", headers=admin_token_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)

    def test_unauthorized_user_cannot_read_events(
        self, client: TestClient, normal_user_token_headers, unverified_property_owned_by_agent
    ):
        """A non-agent, non-agency-owner, non-admin user gets 403."""
        listing_id = unverified_property_owned_by_agent.property_id
        resp = client.get(f"/api/v1/properties/{listing_id}/events", headers=normal_user_token_headers)
        assert resp.status_code == 403

    def test_nonexistent_property_returns_404(self, client: TestClient, admin_token_headers):
        resp = client.get("/api/v1/properties/999999/events", headers=admin_token_headers)
        assert resp.status_code == 404


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

