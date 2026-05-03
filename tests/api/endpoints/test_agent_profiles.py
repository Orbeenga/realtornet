# tests/api/endpoints/test_agent_profiles.py
"""
Surgical API-layer tests for /agent-profiles endpoints.
"""
from fastapi.testclient import TestClient
import uuid
from app.api.endpoints import agent_profiles as agent_profiles_api
from app.crud.users import user as user_crud


class TestReadAgentProfiles:

    def test_read_all_profiles_public(self, client: TestClient):
        response = client.get("/api/v1/agent-profiles/")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_filter_by_agency_id(self, client: TestClient, agency):
        response = client.get(
            "/api/v1/agent-profiles/",
            params={"agency_id": agency.agency_id}
        )
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_filter_by_location_id_uses_verified_listing_inventory(
        self, client: TestClient, db, agency, agent_user, location, location_lekki, property_type
    ):
        from geoalchemy2.elements import WKTElement
        from app.models.agent_profiles import AgentProfile
        from app.models.properties import Property, ListingType, ListingStatus

        profile = AgentProfile(
            user_id=agent_user.user_id,
            agency_id=agency.agency_id,
            license_number=f"LIC-LOC-{uuid.uuid4().hex[:6]}",
        )
        matching_property = Property(
            title="Location Matched Listing",
            description="Verified listing in requested location",
            user_id=agent_user.user_id,
            agency_id=agency.agency_id,
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
        db.add_all([profile, matching_property])
        db.flush()
        db.refresh(profile)

        matched_response = client.get(
            "/api/v1/agent-profiles/",
            params={"location_id": location.location_id},
        )
        unmatched_response = client.get(
            "/api/v1/agent-profiles/",
            params={"location_id": location_lekki.location_id},
        )

        assert matched_response.status_code == 200
        assert profile.profile_id in {item["profile_id"] for item in matched_response.json()}
        assert unmatched_response.status_code == 200
        assert profile.profile_id not in {item["profile_id"] for item in unmatched_response.json()}

    def test_filter_by_agency_and_location_must_match_both(
        self, client: TestClient, db, agency, other_agency, agent_user, location, property_type
    ):
        from geoalchemy2.elements import WKTElement
        from app.models.agent_profiles import AgentProfile
        from app.models.properties import Property, ListingType, ListingStatus

        profile = AgentProfile(
            user_id=agent_user.user_id,
            agency_id=agency.agency_id,
            license_number=f"LIC-AGLOC-{uuid.uuid4().hex[:6]}",
        )
        listing = Property(
            title="Agency Location Matched Listing",
            description="Verified listing in requested location and agency",
            user_id=agent_user.user_id,
            agency_id=agency.agency_id,
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
        db.add_all([profile, listing])
        db.flush()
        db.refresh(profile)

        response = client.get(
            "/api/v1/agent-profiles/",
            params={"agency_id": other_agency.agency_id, "location_id": location.location_id},
        )

        assert response.status_code == 200
        assert profile.profile_id not in {item["profile_id"] for item in response.json()}

    def test_pagination_params_accepted(self, client: TestClient):
        response = client.get(
            "/api/v1/agent-profiles/",
            params={"skip": 0, "limit": 5}
        )
        assert response.status_code == 200


class TestReadAgentProfile:

    def test_profile_not_found_returns_404(self, client: TestClient):
        response = client.get("/api/v1/agent-profiles/999999")
        assert response.status_code == 404

    def test_read_profile_success(self, client: TestClient, db, agency, agent_user):
        # Create a profile for agent_user
        from app.models.agent_profiles import AgentProfile
        profile = AgentProfile(
            user_id=agent_user.user_id,
            agency_id=agency.agency_id,
            license_number="LIC-TEST-001"
        )
        db.add(profile)
        db.flush()
        db.refresh(profile)

        response = client.get(f"/api/v1/agent-profiles/{profile.profile_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["user_id"] == agent_user.user_id


class TestReadAgentProfileByUser:

    def test_user_not_found_returns_404(self, client: TestClient):
        response = client.get("/api/v1/agent-profiles/by-user/999999")
        assert response.status_code == 404

    def test_read_profile_by_user_success(self, client: TestClient, db, agency, agent_user):
        from app.models.agent_profiles import AgentProfile
        profile = AgentProfile(
            user_id=agent_user.user_id,
            agency_id=agency.agency_id,
            license_number="LIC-TEST-002"
        )
        db.add(profile)
        db.flush()
        db.refresh(profile)

        response = client.get(f"/api/v1/agent-profiles/by-user/{agent_user.user_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["user_id"] == agent_user.user_id

    def test_read_profile_by_user_with_no_agency_success(self, client: TestClient, db):
        from app.models.agent_profiles import AgentProfile
        from app.models.users import User, UserRole

        agent_user = User(
            email=f"solo_agent_{uuid.uuid4().hex[:6]}@example.com",
            supabase_id=str(uuid.uuid4()),
            user_role=UserRole.AGENT,
            is_verified=True,
            password_hash="hashed_placeholder",
            first_name="Solo",
            last_name="Agent"
        )
        db.add(agent_user)
        db.flush()
        db.refresh(agent_user)

        profile = AgentProfile(
            user_id=agent_user.user_id,
            agency_id=None,
            license_number=f"LIC-SOLO-{uuid.uuid4().hex[:6]}"
        )
        db.add(profile)
        db.flush()
        db.refresh(profile)

        response = client.get(f"/api/v1/agent-profiles/by-user/{agent_user.user_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["user_id"] == agent_user.user_id
        assert data["agency_id"] is None


class TestCreateAgentProfile:

    def test_unauthenticated_returns_401(self, client: TestClient):
        response = client.post(
            "/api/v1/agent-profiles/",
            json={"user_id": 1, "agency_id": 1}
        )
        assert response.status_code == 401

    def test_non_admin_returns_403(
        self, client: TestClient, normal_user_token_headers, agent_user, agency
    ):
        response = client.post(
            "/api/v1/agent-profiles/",
            json={"user_id": agent_user.user_id, "agency_id": agency.agency_id},
            headers=normal_user_token_headers
        )
        assert response.status_code == 403

    def test_user_not_found_returns_404(
        self, client: TestClient, admin_token_headers, agency
    ):
        response = client.post(
            "/api/v1/agent-profiles/",
            json={"user_id": 999999, "agency_id": agency.agency_id},
            headers=admin_token_headers
        )
        assert response.status_code == 404

    def test_non_agent_user_returns_400(
        self, client: TestClient, admin_token_headers, normal_user, agency
    ):
        response = client.post(
            "/api/v1/agent-profiles/",
            json={"user_id": normal_user.user_id, "agency_id": agency.agency_id},
            headers=admin_token_headers
        )
        assert response.status_code == 400

    def test_agency_not_found_returns_404(
        self, client: TestClient, admin_token_headers, agent_user
    ):
        response = client.post(
            "/api/v1/agent-profiles/",
            json={"user_id": agent_user.user_id, "agency_id": 999999},
            headers=admin_token_headers
        )
        assert response.status_code == 404

    def test_cannot_create_agent_profile_for_deleted_user(
        self, client: TestClient, admin_token_headers, db, agent_user, agency
    ):
        user_crud.soft_delete(
            db,
            user_id=agent_user.user_id,
            deleted_by_supabase_id=str(uuid.uuid4())
        )
        response = client.post(
            "/api/v1/agent-profiles/",
            json={
                "user_id": agent_user.user_id,
                "agency_id": agency.agency_id,
                "license_number": f"LIC-TEST-{uuid.uuid4().hex[:6]}"
            },
            headers=admin_token_headers
        )
        assert response.status_code in (400, 404)

    def test_create_profile_success(
        self, client: TestClient, admin_token_headers, db, agency
    ):
        # Create a fresh agent user with no profile
        from app.models.users import User, UserRole
        import uuid
        fresh_agent = User(
            email=f"fresh_agent_{uuid.uuid4().hex[:6]}@example.com",
            supabase_id=str(uuid.uuid4()),
            user_role=UserRole.AGENT,
            is_verified=True,
            agency_id=agency.agency_id,
            password_hash="hashed_placeholder",
            first_name="Test",
            last_name="Agent"
        )
        db.add(fresh_agent)
        db.flush()
        db.refresh(fresh_agent)

        response = client.post(
            "/api/v1/agent-profiles/",
            json={
                "user_id": fresh_agent.user_id,
                "agency_id": agency.agency_id,
                "license_number": f"LIC-{uuid.uuid4().hex[:6]}"
            },
            headers=admin_token_headers
        )
        assert response.status_code == 201
        data = response.json()
        assert data["user_id"] == fresh_agent.user_id

    def test_duplicate_profile_returns_400(
        self, client: TestClient, admin_token_headers, db, agency, agent_user
    ):
        from app.models.agent_profiles import AgentProfile
        profile = AgentProfile(
            user_id=agent_user.user_id,
            agency_id=agency.agency_id,
            license_number="LIC-DUP-001"
        )
        db.add(profile)
        db.flush()
        db.refresh(profile)

        response = client.post(
            "/api/v1/agent-profiles/",
            json={
                "user_id": agent_user.user_id,
                "agency_id": agency.agency_id,
                "license_number": "LIC-DUP-001"
            },
            headers=admin_token_headers
        )
        assert response.status_code == 400

    def test_duplicate_license_returns_400(
        self, client: TestClient, admin_token_headers, db, agency, agent_user
    ):
        from app.models.agent_profiles import AgentProfile
        from app.models.users import User, UserRole
        import uuid
        existing_profile = AgentProfile(
            user_id=agent_user.user_id,
            agency_id=agency.agency_id,
            license_number="LIC-DUP-002"
        )
        db.add(existing_profile)
        db.flush()
        db.refresh(existing_profile)

        fresh_agent = User(
            email=f"fresh_agent_{uuid.uuid4().hex[:6]}@example.com",
            supabase_id=str(uuid.uuid4()),
            user_role=UserRole.AGENT,
            is_verified=True,
            agency_id=agency.agency_id,
            password_hash="hashed_placeholder",
            first_name="Test",
            last_name="Agent"
        )
        db.add(fresh_agent)
        db.flush()
        db.refresh(fresh_agent)

        response = client.post(
            "/api/v1/agent-profiles/",
            json={
                "user_id": fresh_agent.user_id,
                "agency_id": agency.agency_id,
                "license_number": "LIC-DUP-002"
            },
            headers=admin_token_headers
        )
        assert response.status_code == 400


class TestUpdateAgentProfile:

    def test_unauthenticated_returns_401(self, client: TestClient):
        response = client.put(
            "/api/v1/agent-profiles/1",
            json={"bio": "Updated bio"}
        )
        assert response.status_code == 401

    def test_profile_not_found_returns_404(
        self, client: TestClient, agent_token_headers
    ):
        response = client.put(
            "/api/v1/agent-profiles/999999",
            json={"bio": "Updated bio"},
            headers=agent_token_headers
        )
        assert response.status_code == 404

    def test_non_owner_returns_403(
        self, client: TestClient, normal_user_token_headers, db, agency, agent_user
    ):
        from app.models.agent_profiles import AgentProfile
        profile = AgentProfile(
            user_id=agent_user.user_id,
            agency_id=agency.agency_id,
            license_number="LIC-TEST-403"
        )
        db.add(profile)
        db.flush()
        db.refresh(profile)

        response = client.put(
            f"/api/v1/agent-profiles/{profile.profile_id}",
            json={"bio": "Unauthorized update"},
            headers=normal_user_token_headers
        )
        assert response.status_code == 403

    def test_update_own_profile_success(
        self, client: TestClient, agent_token_headers, db, agency, agent_user
    ):
        from app.models.agent_profiles import AgentProfile
        profile = AgentProfile(
            user_id=agent_user.user_id,
            agency_id=agency.agency_id,
            license_number="LIC-TEST-OWN"
        )
        db.add(profile)
        db.flush()
        db.refresh(profile)

        response = client.put(
            f"/api/v1/agent-profiles/{profile.profile_id}",
            json={"bio": "My updated bio"},
            headers=agent_token_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["bio"] == "My updated bio"

    def test_admin_can_update_any_profile(
        self, client: TestClient, admin_token_headers, db, agency, agent_user
    ):
        from app.models.agent_profiles import AgentProfile
        profile = AgentProfile(
            user_id=agent_user.user_id,
            agency_id=agency.agency_id,
            license_number="LIC-TEST-ADM"
        )
        db.add(profile)
        db.flush()
        db.refresh(profile)

        response = client.put(
            f"/api/v1/agent-profiles/{profile.profile_id}",
            json={"bio": "Admin updated bio"},
            headers=admin_token_headers
        )
        assert response.status_code == 200

    def test_duplicate_license_returns_400(
        self, client: TestClient, admin_token_headers, db, agency, agent_user
    ):
        from app.models.agent_profiles import AgentProfile
        from app.models.users import User, UserRole
        import uuid
        profile_one = AgentProfile(
            user_id=agent_user.user_id,
            agency_id=agency.agency_id,
            license_number="LIC-UNIQ-001"
        )
        db.add(profile_one)
        db.flush()
        db.refresh(profile_one)

        second_agent = User(
            email=f"second_agent_{uuid.uuid4().hex[:6]}@example.com",
            supabase_id=str(uuid.uuid4()),
            user_role=UserRole.AGENT,
            is_verified=True,
            agency_id=agency.agency_id,
            password_hash="hashed_placeholder",
            first_name="Second",
            last_name="Agent"
        )
        db.add(second_agent)
        db.flush()
        db.refresh(second_agent)

        profile_two = AgentProfile(
            user_id=second_agent.user_id,
            agency_id=agency.agency_id,
            license_number="LIC-UNIQ-002"
        )
        db.add(profile_two)
        db.flush()
        db.refresh(profile_two)

        response = client.put(
            f"/api/v1/agent-profiles/{profile_one.profile_id}",
            json={"license_number": "LIC-UNIQ-002"},
            headers=admin_token_headers
        )
        assert response.status_code == 400

    def test_update_agency_not_found_returns_404(
        self, client: TestClient, admin_token_headers, db, agency, agent_user
    ):
        from app.models.agent_profiles import AgentProfile
        profile = AgentProfile(
            user_id=agent_user.user_id,
            agency_id=agency.agency_id,
            license_number="LIC-NO-AGENCY"
        )
        db.add(profile)
        db.flush()
        db.refresh(profile)

        response = client.put(
            f"/api/v1/agent-profiles/{profile.profile_id}",
            json={"agency_id": 999999},
            headers=admin_token_headers
        )
        assert response.status_code == 404

    def test_cannot_change_agency_with_active_properties(
        self, client: TestClient, agent_token_headers, db, agency, agent_user, monkeypatch
    ):
        from app.models.agent_profiles import AgentProfile
        from app.models.agencies import Agency

        profile = AgentProfile(
            user_id=agent_user.user_id,
            agency_id=agency.agency_id,
            license_number=f"LIC-STATE-{uuid.uuid4().hex[:6]}"
        )
        db.add(profile)
        db.flush()
        db.refresh(profile)

        second_agency = Agency(name=f"Agency-{uuid.uuid4().hex[:6]}")
        db.add(second_agency)
        db.flush()
        db.refresh(second_agency)

        monkeypatch.setattr(
            agent_profiles_api.agent_profile_crud,
            "update",
            lambda *args, **kwargs: (_ for _ in ()).throw(
                ValueError("Cannot change agency while agent has active properties. Transfer or remove properties first.")
            )
        )

        response = client.put(
            f"/api/v1/agent-profiles/{profile.profile_id}",
            json={"agency_id": second_agency.agency_id},
            headers=agent_token_headers
        )
        assert response.status_code == 400
        assert "active properties" in response.json()["detail"]


class TestDeleteAgentProfile:

    def test_unauthenticated_returns_401(self, client: TestClient):
        response = client.delete("/api/v1/agent-profiles/1")
        assert response.status_code == 401

    def test_non_admin_returns_403(
        self, client: TestClient, agent_token_headers, db, agency, agent_user
    ):
        from app.models.agent_profiles import AgentProfile
        profile = AgentProfile(
            user_id=agent_user.user_id,
            agency_id=agency.agency_id,
            license_number="LIC-TEST-DEL403"
        )
        db.add(profile)
        db.flush()
        db.refresh(profile)

        response = client.delete(
            f"/api/v1/agent-profiles/{profile.profile_id}",
            headers=agent_token_headers
        )
        assert response.status_code == 403

    def test_profile_not_found_returns_404(
        self, client: TestClient, admin_token_headers
    ):
        response = client.delete(
            "/api/v1/agent-profiles/999999",
            headers=admin_token_headers
        )
        assert response.status_code == 404

    def test_delete_profile_success(
        self, client: TestClient, admin_token_headers, db, agency
    ):
        # Create fresh agent with no properties
        from app.models.users import User, UserRole
        from app.models.agent_profiles import AgentProfile
        import uuid
        fresh_agent = User(
            email=f"fresh_agent_{uuid.uuid4().hex[:6]}@example.com",
            supabase_id=str(uuid.uuid4()),
            user_role=UserRole.AGENT,
            is_verified=True,
            agency_id=agency.agency_id,
            password_hash="hashed_placeholder",
            first_name="Test",
            last_name="Agent"
        )
        db.add(fresh_agent)
        db.flush()
        db.refresh(fresh_agent)

        profile = AgentProfile(
            user_id=fresh_agent.user_id,
            agency_id=agency.agency_id,
            license_number=f"LIC-DEL-{uuid.uuid4().hex[:6]}"
        )
        db.add(profile)
        db.flush()
        db.refresh(profile)

        response = client.delete(
            f"/api/v1/agent-profiles/{profile.profile_id}",
            headers=admin_token_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["deleted_at"] is not None

    def test_cannot_delete_profile_with_active_properties_returns_400(
        self, client: TestClient, admin_token_headers, db, agency, agent_user, monkeypatch
    ):
        from app.models.agent_profiles import AgentProfile
        profile = AgentProfile(
            user_id=agent_user.user_id,
            agency_id=agency.agency_id,
            license_number="LIC-DEL-PROP"
        )
        db.add(profile)
        db.flush()
        db.refresh(profile)

        monkeypatch.setattr(agent_profiles_api.property_crud, "count_by_user", lambda *args, **kwargs: 1)
        response = client.delete(
            f"/api/v1/agent-profiles/{profile.profile_id}",
            headers=admin_token_headers
        )
        assert response.status_code == 400

    def test_delete_profile_soft_delete_returns_none(
        self, client: TestClient, admin_token_headers, db, agency, agent_user, monkeypatch
    ):
        from app.models.agent_profiles import AgentProfile
        profile = AgentProfile(
            user_id=agent_user.user_id,
            agency_id=agency.agency_id,
            license_number="LIC-DEL-NONE"
        )
        db.add(profile)
        db.flush()
        db.refresh(profile)

        monkeypatch.setattr(agent_profiles_api.property_crud, "count_by_user", lambda *args, **kwargs: 0)
        monkeypatch.setattr(agent_profiles_api.agent_profile_crud, "soft_delete", lambda *args, **kwargs: None)

        response = client.delete(
            f"/api/v1/agent-profiles/{profile.profile_id}",
            headers=admin_token_headers
        )
        assert response.status_code == 404


class TestReadAgentProperties:

    def test_profile_not_found_returns_404(self, client: TestClient):
        response = client.get("/api/v1/agent-profiles/999999/properties")
        assert response.status_code == 404

    def test_read_agent_properties_success(
        self, client: TestClient, db, agency, agent_user
    ):
        from app.models.agent_profiles import AgentProfile
        profile = AgentProfile(
            user_id=agent_user.user_id,
            agency_id=agency.agency_id,
            license_number="LIC-PROP-001"
        )
        db.add(profile)
        db.flush()
        db.refresh(profile)

        response = client.get(f"/api/v1/agent-profiles/{profile.profile_id}/properties")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_read_agent_properties_serializes_properties(
        self, client: TestClient, db, agency, agent_user, location, property_type
    ):
        from app.models.agent_profiles import AgentProfile
        from app.models.properties import Property, ListingType, ListingStatus
        from geoalchemy2.elements import WKTElement

        profile = AgentProfile(
            user_id=agent_user.user_id,
            agency_id=agency.agency_id,
            license_number="LIC-PROP-JSON-001"
        )
        db.add(profile)
        db.flush()
        db.refresh(profile)

        property_obj = Property(
            title="Serialized Agent Property",
            description="Agent-owned listing for serialization test",
            user_id=agent_user.user_id,
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
        db.add(property_obj)
        db.flush()
        db.refresh(property_obj)

        response = client.get(f"/api/v1/agent-profiles/{profile.profile_id}/properties")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        assert data[0]["property_id"] == property_obj.property_id
        assert data[0]["title"] == "Serialized Agent Property"
        assert data[0]["user_id"] == agent_user.user_id


class TestReadAgentReviews:

    def test_profile_not_found_returns_404(self, client: TestClient):
        response = client.get("/api/v1/agent-profiles/999999/reviews")
        assert response.status_code == 404

    def test_read_agent_reviews_success(
        self, client: TestClient, db, agency, agent_user
    ):
        from app.models.agent_profiles import AgentProfile
        profile = AgentProfile(
            user_id=agent_user.user_id,
            agency_id=agency.agency_id,
            license_number="LIC-REV-001"
        )
        db.add(profile)
        db.flush()
        db.refresh(profile)

        response = client.get(f"/api/v1/agent-profiles/{profile.profile_id}/reviews")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_read_agent_reviews_serializes_reviews(
        self, client: TestClient, db, agency, agent_user, normal_user
    ):
        from app.models.agent_profiles import AgentProfile
        from app.models.reviews import Review

        profile = AgentProfile(
            user_id=agent_user.user_id,
            agency_id=agency.agency_id,
            license_number="LIC-REV-JSON-001"
        )
        db.add(profile)
        db.flush()
        db.refresh(profile)

        review = Review(
            user_id=normal_user.user_id,
            agent_id=agent_user.user_id,
            rating=5,
            comment="Excellent agent support",
        )
        db.add(review)
        db.flush()
        db.refresh(review)

        response = client.get(f"/api/v1/agent-profiles/{profile.profile_id}/reviews")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        assert data[0]["review_id"] == review.review_id
        assert data[0]["agent_id"] == agent_user.user_id
        assert data[0]["rating"] == 5


class TestReadAgentStats:

    def test_profile_not_found_returns_404(self, client: TestClient):
        response = client.get("/api/v1/agent-profiles/999999/stats")
        assert response.status_code == 404

    def test_read_agent_stats_success(
        self, client: TestClient, db, agency, agent_user
    ):
        from app.models.agent_profiles import AgentProfile
        profile = AgentProfile(
            user_id=agent_user.user_id,
            agency_id=agency.agency_id,
            license_number="LIC-STAT-001"
        )
        db.add(profile)
        db.flush()
        db.refresh(profile)

        response = client.get(f"/api/v1/agent-profiles/{profile.profile_id}/stats")
        assert response.status_code == 200
        data = response.json()
        assert "property_count" in data
        assert "review_count" in data
