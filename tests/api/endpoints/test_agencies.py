# tests/api/endpoints/test_agencies.py
"""
Surgical API-layer tests for /agencies endpoints.
"""
from fastapi.testclient import TestClient
from app.api.endpoints import agencies as agencies_api


class TestReadAgencies:

    def test_read_agencies_public_no_auth_required(self, client: TestClient):
        response = client.get("/api/v1/agencies/")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_pagination_params_accepted(self, client: TestClient):
        response = client.get("/api/v1/agencies/", params={"skip": 0, "limit": 5})
        assert response.status_code == 200


class TestReadAgency:

    def test_agency_not_found_returns_404(self, client: TestClient):
        response = client.get("/api/v1/agencies/999999")
        assert response.status_code == 404

    def test_read_agency_success(self, client: TestClient, agency):
        response = client.get(f"/api/v1/agencies/{agency.agency_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["agency_id"] == agency.agency_id
        assert data["name"] == agency.name


class TestCreateAgency:

    def test_unauthenticated_returns_401(self, client: TestClient):
        response = client.post("/api/v1/agencies/", json={"name": "Test Agency"})
        assert response.status_code == 401

    def test_non_admin_returns_403(
        self, client: TestClient, normal_user_token_headers
    ):
        response = client.post(
            "/api/v1/agencies/",
            json={"name": "Test Agency"},
            headers=normal_user_token_headers
        )
        assert response.status_code == 403

    def test_agent_returns_403(
        self, client: TestClient, agent_token_headers
    ):
        response = client.post(
            "/api/v1/agencies/",
            json={"name": "Test Agency"},
            headers=agent_token_headers
        )
        assert response.status_code == 403

    def test_duplicate_name_returns_400(
        self, client: TestClient, admin_token_headers, agency
    ):
        response = client.post(
            "/api/v1/agencies/",
            json={"name": agency.name},
            headers=admin_token_headers
        )
        assert response.status_code == 400

    def test_duplicate_email_returns_400(
        self, client: TestClient, admin_token_headers, db
    ):
        from app.models.agencies import Agency
        import uuid
        email = f"dup_{uuid.uuid4().hex[:6]}@example.com"
        existing = Agency(name="Email Agency", email=email)
        db.add(existing)
        db.flush()
        db.refresh(existing)
        response = client.post(
            "/api/v1/agencies/",
            json={"name": "Brand New Agency", "email": email},
            headers=admin_token_headers
        )
        assert response.status_code == 400

    def test_create_agency_success(
        self, client: TestClient, admin_token_headers
    ):
        response = client.post(
            "/api/v1/agencies/",
            json={"name": "Fresh Test Agency XYZ"},
            headers=admin_token_headers
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Fresh Test Agency XYZ"
        assert data["is_verified"] is False


class TestUpdateAgency:

    def test_unauthenticated_returns_401(self, client: TestClient, agency):
        response = client.put(
            f"/api/v1/agencies/{agency.agency_id}",
            json={"name": "Updated"}
        )
        assert response.status_code == 401

    def test_non_admin_returns_403(
        self, client: TestClient, normal_user_token_headers, agency
    ):
        response = client.put(
            f"/api/v1/agencies/{agency.agency_id}",
            json={"name": "Updated"},
            headers=normal_user_token_headers
        )
        assert response.status_code == 403

    def test_agency_not_found_returns_404(
        self, client: TestClient, admin_token_headers
    ):
        response = client.put(
            "/api/v1/agencies/999999",
            json={"name": "Updated"},
            headers=admin_token_headers
        )
        assert response.status_code == 404

    def test_duplicate_name_returns_400(
        self, client: TestClient, admin_token_headers, agency, other_agency
    ):
        response = client.put(
            f"/api/v1/agencies/{agency.agency_id}",
            json={"name": other_agency.name},
            headers=admin_token_headers
        )
        assert response.status_code == 400

    def test_update_agency_success(
        self, client: TestClient, admin_token_headers, agency
    ):
        response = client.put(
            f"/api/v1/agencies/{agency.agency_id}",
            json={"name": "Updated Agency Name ABC"},
            headers=admin_token_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Agency Name ABC"

    def test_duplicate_email_returns_400(
        self, client: TestClient, admin_token_headers, db
    ):
        from app.models.agencies import Agency
        import uuid
        agency_one = Agency(
            name=f"Email Agency A {uuid.uuid4().hex[:6]}",
            email=f"agency_a_{uuid.uuid4().hex[:6]}@example.com"
        )
        agency_two = Agency(
            name=f"Email Agency B {uuid.uuid4().hex[:6]}",
            email=f"agency_b_{uuid.uuid4().hex[:6]}@example.com"
        )
        db.add(agency_one)
        db.add(agency_two)
        db.flush()
        db.refresh(agency_one)
        db.refresh(agency_two)

        response = client.put(
            f"/api/v1/agencies/{agency_one.agency_id}",
            json={"email": agency_two.email},
            headers=admin_token_headers
        )
        assert response.status_code == 400


class TestDeleteAgency:

    def test_unauthenticated_returns_401(self, client: TestClient, agency):
        response = client.delete(f"/api/v1/agencies/{agency.agency_id}")
        assert response.status_code == 401

    def test_non_admin_returns_403(
        self, client: TestClient, normal_user_token_headers, agency
    ):
        response = client.delete(
            f"/api/v1/agencies/{agency.agency_id}",
            headers=normal_user_token_headers
        )
        assert response.status_code == 403

    def test_agency_not_found_returns_404(
        self, client: TestClient, admin_token_headers
    ):
        response = client.delete(
            "/api/v1/agencies/999999",
            headers=admin_token_headers
        )
        assert response.status_code == 404

    def test_cannot_delete_agency_with_active_agents_returns_400(
        self, client: TestClient, admin_token_headers, agency, agent_user
    ):
        # agent_user fixture already belongs to agency
        response = client.delete(
            f"/api/v1/agencies/{agency.agency_id}",
            headers=admin_token_headers
        )
        assert response.status_code == 400
        assert response.json()["detail"] == "Cannot delete agency with active agents. Reassign or remove agents first."

    def test_delete_empty_agency_success(
        self, client: TestClient, admin_token_headers, db
    ):
        # Create a fresh agency with no agents or properties
        from app.models.agencies import Agency
        empty_agency = Agency(name="Empty Agency For Delete Test")
        db.add(empty_agency)
        db.flush()
        db.refresh(empty_agency)

        response = client.delete(
            f"/api/v1/agencies/{empty_agency.agency_id}",
            headers=admin_token_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["deleted_at"] is not None
        assert data["deleted_by"] is not None

    def test_cannot_delete_agency_with_active_properties_returns_400(
        self, client: TestClient, admin_token_headers, agency, monkeypatch
    ):
        monkeypatch.setattr(agencies_api.user_crud, "count_by_agency", lambda *args, **kwargs: 0)
        monkeypatch.setattr(agencies_api.property_crud, "count_by_agency", lambda *args, **kwargs: 2)

        response = client.delete(
            f"/api/v1/agencies/{agency.agency_id}",
            headers=admin_token_headers
        )
        assert response.status_code == 400
        assert response.json()["detail"] == "Cannot delete agency with active properties. Remove properties first."

    def test_delete_agency_soft_delete_returns_none(
        self, client: TestClient, admin_token_headers, agency, monkeypatch
    ):
        monkeypatch.setattr(agencies_api.user_crud, "count_by_agency", lambda *args, **kwargs: 0)
        monkeypatch.setattr(agencies_api.property_crud, "count_by_agency", lambda *args, **kwargs: 0)
        monkeypatch.setattr(agencies_api.agency_crud, "soft_delete", lambda *args, **kwargs: None)

        response = client.delete(
            f"/api/v1/agencies/{agency.agency_id}",
            headers=admin_token_headers
        )
        assert response.status_code == 404


class TestReadAgencyAgents:

    def test_agency_not_found_returns_404(self, client: TestClient):
        response = client.get("/api/v1/agencies/999999/agents")
        assert response.status_code == 404

    def test_read_agency_agents_success(self, client: TestClient, agency):
        response = client.get(f"/api/v1/agencies/{agency.agency_id}/agents")
        assert response.status_code == 200
        assert isinstance(response.json(), list)


class TestReadAgencyProperties:

    def test_agency_not_found_returns_404(self, client: TestClient):
        response = client.get("/api/v1/agencies/999999/properties")
        assert response.status_code == 404

    def test_read_agency_properties_success(self, client: TestClient, agency):
        response = client.get(f"/api/v1/agencies/{agency.agency_id}/properties")
        assert response.status_code == 200
        assert isinstance(response.json(), list)


class TestReadAgencyStats:

    def test_unauthenticated_returns_401(self, client: TestClient, agency):
        response = client.get(f"/api/v1/agencies/{agency.agency_id}/stats")
        assert response.status_code == 401

    def test_agency_not_found_returns_404(
        self, client: TestClient, admin_token_headers
    ):
        response = client.get(
            "/api/v1/agencies/999999/stats",
            headers=admin_token_headers
        )
        assert response.status_code == 404

    def test_non_member_agent_returns_403(
        self, client: TestClient, agent_token_headers, other_agency
    ):
        # agent_user belongs to agency, not other_agency
        response = client.get(
            f"/api/v1/agencies/{other_agency.agency_id}/stats",
            headers=agent_token_headers
        )
        assert response.status_code == 403

    def test_admin_can_read_any_agency_stats(
        self, client: TestClient, admin_token_headers, agency
    ):
        response = client.get(
            f"/api/v1/agencies/{agency.agency_id}/stats",
            headers=admin_token_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "agent_count" in data
        assert "property_count" in data
