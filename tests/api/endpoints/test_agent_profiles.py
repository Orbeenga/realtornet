# tests/api/endpoints/test_agent_profiles.py
"""
Surgical API-layer tests for /agent-profiles endpoints.
"""
from fastapi.testclient import TestClient
from app.api.endpoints import agent_profiles as agent_profiles_api


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
