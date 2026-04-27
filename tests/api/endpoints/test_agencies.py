# tests/api/endpoints/test_agencies.py
"""
Surgical API-layer tests for /agencies endpoints.
"""
from fastapi.testclient import TestClient
from datetime import UTC, datetime
import uuid
from app.api.endpoints import agencies as agencies_api
from app.models.users import User, UserRole
from app.core.security import decode_token, generate_access_token


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


class TestAgencyApplication:

    def test_public_agency_application_creates_pending_agency(
        self, client: TestClient, db
    ):
        email = f"owner_{uuid.uuid4().hex[:6]}@example.com"
        response = client.post(
            "/api/v1/agencies/apply/",
            json={
                "name": f"Applicant Agency {uuid.uuid4().hex[:6]}",
                "description": "Pending application",
                "address": "Lagos",
                "website_url": "https://agency.example.com",
                "owner_email": email,
                "owner_name": "Applicant Owner",
                "owner_phone_number": "+234700000001",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["agency_id"] is not None
        assert data["status"] == "pending"

        detail_response = client.get(f"/api/v1/agencies/{data['agency_id']}")
        assert detail_response.status_code == 200
        assert detail_response.json()["website_url"] == "https://agency.example.com"

    def test_agency_owner_can_invite_to_own_agency(
        self, client: TestClient, agency, agency_owner_token_headers
    ):
        response = client.post(
            f"/api/v1/agencies/{agency.agency_id}/invite/",
            json={"email": "newagent@example.com"},
            headers=agency_owner_token_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["agency_id"] == agency.agency_id
        assert data["invite_token"]

    def test_agency_owner_cannot_invite_to_other_agency(
        self, client: TestClient, other_agency, agency_owner_token_headers
    ):
        response = client.post(
            f"/api/v1/agencies/{other_agency.agency_id}/invite/",
            json={"email": "newagent@example.com"},
            headers=agency_owner_token_headers,
        )

        assert response.status_code == 403

    def test_accept_invite_promotes_existing_user(
        self, client: TestClient, db, agency, agency_owner_token_headers, normal_user
    ):
        from app.models.agency_join_requests import AgencyAgentMembership

        invite_response = client.post(
            f"/api/v1/agencies/{agency.agency_id}/invite/",
            json={"email": normal_user.email},
            headers=agency_owner_token_headers,
        )
        assert invite_response.status_code == 200

        response = client.post(
            "/api/v1/agencies/accept-invite/",
            json={"invite_token": invite_response.json()["invite_token"]},
        )

        assert response.status_code == 200
        assert response.json()["status"] == "accepted"
        membership = db.query(AgencyAgentMembership).filter(
            AgencyAgentMembership.agency_id == agency.agency_id,
            AgencyAgentMembership.user_id == normal_user.user_id,
            AgencyAgentMembership.status == "active",
        ).one_or_none()
        assert membership is not None

    def test_accept_invite_for_missing_user_returns_register_redirect(
        self, client: TestClient, agency, agency_owner_token_headers
    ):
        invite_response = client.post(
            f"/api/v1/agencies/{agency.agency_id}/invite/",
            json={"email": f"missing_{uuid.uuid4().hex[:6]}@example.com"},
            headers=agency_owner_token_headers,
        )
        assert invite_response.status_code == 200

        response = client.post(
            "/api/v1/agencies/accept-invite/",
            json={"invite_token": invite_response.json()["invite_token"]},
        )

        assert response.status_code == 200
        assert response.json()["status"] == "registration_required"
        assert response.json()["redirect_url"].startswith("/register?invite_token=")

    def test_accept_invite_rejects_malformed_token(self, client: TestClient):
        response = client.post(
            "/api/v1/agencies/accept-invite/",
            json={"invite_token": "not-a-valid-token"},
        )

        assert response.status_code == 400
        assert response.json()["detail"] == "Invalid or expired invite token"

    def test_agency_owner_token_claim_passes_agent_gated_property_endpoint(
        self, client: TestClient, agency_owner_user
    ):
        from app.core.security import generate_access_token

        token = generate_access_token(
            supabase_id=agency_owner_user.supabase_id,
            user_id=agency_owner_user.user_id,
            user_role=agency_owner_user.user_role.value,
            agency_id=agency_owner_user.agency_id,
        )
        payload = decode_token(token)

        assert payload.role == "agency_owner"
        assert payload.agency_id == agency_owner_user.agency_id

        response = client.get(
            "/api/v1/properties/",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200


class TestAgencyJoinRequests:

    def test_seeker_creates_join_request(
        self, client: TestClient, agency, normal_user_token_headers
    ):
        response = client.post(
            f"/api/v1/agencies/{agency.agency_id}/join-request/",
            json={
                "cover_note": "I know Lekki and Ikeja well.",
                "portfolio_details": "Three years of rentals experience.",
            },
            headers=normal_user_token_headers,
        )

        assert response.status_code == 201
        data = response.json()
        assert data["agency_id"] == agency.agency_id
        assert data["status"] == "pending"

    def test_agent_can_create_join_request_for_another_agency(
        self, client: TestClient, other_agency, agent_token_headers
    ):
        response = client.post(
            f"/api/v1/agencies/{other_agency.agency_id}/join-request/",
            json={"cover_note": "I would like to affiliate with this agency too."},
            headers=agent_token_headers,
        )

        assert response.status_code == 201
        assert response.json()["agency_id"] == other_agency.agency_id

    def test_join_request_requires_approved_agency(
        self, client: TestClient, db, agency, normal_user_token_headers
    ):
        agency.status = "pending"
        db.add(agency)
        db.flush()

        response = client.post(
            f"/api/v1/agencies/{agency.agency_id}/join-request/",
            json={"cover_note": "Please consider me"},
            headers=normal_user_token_headers,
        )

        assert response.status_code == 404

    def test_duplicate_pending_join_request_returns_400(
        self, client: TestClient, agency, normal_user_token_headers
    ):
        payload = {"cover_note": "Please consider me"}
        first_response = client.post(
            f"/api/v1/agencies/{agency.agency_id}/join-request/",
            json=payload,
            headers=normal_user_token_headers,
        )
        second_response = client.post(
            f"/api/v1/agencies/{agency.agency_id}/join-request/",
            json=payload,
            headers=normal_user_token_headers,
        )

        assert first_response.status_code == 201
        assert second_response.status_code == 400

    def test_agency_owner_lists_pending_join_requests(
        self, client: TestClient, agency, normal_user_token_headers, agency_owner_token_headers
    ):
        create_response = client.post(
            f"/api/v1/agencies/{agency.agency_id}/join-request/",
            json={"cover_note": "Please review me"},
            headers=normal_user_token_headers,
        )
        assert create_response.status_code == 201

        response = client.get(
            f"/api/v1/agencies/{agency.agency_id}/join-requests/",
            headers=agency_owner_token_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        assert data[0]["seeker_email"] == "user@example.com"

    def test_agency_owner_all_status_join_requests_keeps_approved_audit_row(
        self, client: TestClient, agency, normal_user_token_headers, agency_owner_token_headers
    ):
        from unittest.mock import patch

        create_response = client.post(
            f"/api/v1/agencies/{agency.agency_id}/join-request/",
            json={"cover_note": "Please review me"},
            headers=normal_user_token_headers,
        )
        assert create_response.status_code == 201
        request_id = create_response.json()["join_request_id"]

        with patch("app.api.endpoints.agencies.sync_supabase_auth_user_metadata"):
            approve_response = client.patch(
                f"/api/v1/agencies/{agency.agency_id}/join-requests/{request_id}/approve/",
                headers=agency_owner_token_headers,
            )

        response = client.get(
            f"/api/v1/agencies/{agency.agency_id}/join-requests/",
            params={"status": "all"},
            headers=agency_owner_token_headers,
        )

        assert approve_response.status_code == 200
        assert response.status_code == 200
        approved_item = next(item for item in response.json() if item["join_request_id"] == request_id)
        assert approved_item["status"] == "approved"
        assert approved_item["decided_at"] is not None
        assert approved_item["decided_by"] is not None

    def test_agency_owner_join_request_status_filter_validates_value(
        self, client: TestClient, agency, agency_owner_token_headers
    ):
        response = client.get(
            f"/api/v1/agencies/{agency.agency_id}/join-requests/",
            params={"status": "accepted"},
            headers=agency_owner_token_headers,
        )

        assert response.status_code == 400

    def test_seeker_lists_their_own_join_requests(
        self, client: TestClient, db, agency, other_agency, normal_user, normal_user_token_headers
    ):
        from app.models.agency_join_requests import AgencyJoinRequest

        approved_request = AgencyJoinRequest(
            agency_id=other_agency.agency_id,
            user_id=normal_user.user_id,
            status="approved",
        )
        rejected_request = AgencyJoinRequest(
            agency_id=agency.agency_id,
            user_id=normal_user.user_id,
            status="rejected",
            rejection_reason="Need more portfolio detail",
        )
        db.add_all([approved_request, rejected_request])
        db.flush()

        response = client.get(
            "/api/v1/join-requests/mine/",
            headers=normal_user_token_headers,
        )

        assert response.status_code == 200
        data = response.json()
        statuses = {item["status"] for item in data}
        assert {"approved", "rejected"}.issubset(statuses)
        assert all(item["agency_name"] for item in data)
        assert all(item["submitted_at"] for item in data)
        rejected_item = next(item for item in data if item["status"] == "rejected")
        assert rejected_item["rejection_reason"] == "Need more portfolio detail"

    def test_promoted_agent_still_lists_their_approved_join_request(
        self, client: TestClient, db, agency, normal_user, normal_user_token_headers, agency_owner_token_headers
    ):
        from unittest.mock import patch

        create_response = client.post(
            f"/api/v1/agencies/{agency.agency_id}/join-request/",
            json={"cover_note": "Please review me"},
            headers=normal_user_token_headers,
        )
        request_id = create_response.json()["join_request_id"]
        with patch("app.api.endpoints.agencies.sync_supabase_auth_user_metadata"):
            approve_response = client.patch(
                f"/api/v1/agencies/{agency.agency_id}/join-requests/{request_id}/approve/",
                headers=agency_owner_token_headers,
            )
        db.refresh(normal_user)
        agent_token = generate_access_token(
            supabase_id=normal_user.supabase_id,
            user_id=normal_user.user_id,
            user_role=normal_user.user_role.value,
            agency_id=normal_user.agency_id,
        )

        response = client.get(
            "/api/v1/join-requests/mine/",
            headers={"Authorization": f"Bearer {agent_token}"},
        )

        assert approve_response.status_code == 200
        assert response.status_code == 200
        approved_item = next(item for item in response.json() if item["join_request_id"] == request_id)
        assert approved_item["status"] == "approved"

    def test_admin_cannot_read_personal_join_request_history(
        self, client: TestClient, admin_token_headers
    ):
        response = client.get(
            "/api/v1/join-requests/mine/",
            headers=admin_token_headers,
        )

        assert response.status_code == 403

    def test_other_agency_owner_cannot_list_join_requests(
        self, client: TestClient, other_agency, agency_owner_token_headers
    ):
        response = client.get(
            f"/api/v1/agencies/{other_agency.agency_id}/join-requests/",
            headers=agency_owner_token_headers,
        )

        assert response.status_code == 403

    def test_agency_owner_list_returns_404_for_missing_owned_agency(
        self, client: TestClient, db, agency, agency_owner_user
    ):
        agency.deleted_at = datetime.now(UTC)
        agency_owner_user.agency_id = agency.agency_id
        db.add(agency)
        db.add(agency_owner_user)
        db.flush()
        token = generate_access_token(
            supabase_id=agency_owner_user.supabase_id,
            user_id=agency_owner_user.user_id,
            user_role=agency_owner_user.user_role.value,
            agency_id=agency.agency_id,
        )

        response = client.get(
            f"/api/v1/agencies/{agency.agency_id}/join-requests/",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 404

    def test_agency_owner_approves_join_request(
        self, client: TestClient, db, agency, normal_user, normal_user_token_headers, agency_owner_token_headers
    ):
        from unittest.mock import patch
        from app.models.agency_join_requests import AgencyAgentMembership
        from app.models.users import UserRole

        create_response = client.post(
            f"/api/v1/agencies/{agency.agency_id}/join-request/",
            json={"portfolio_details": "Portfolio text"},
            headers=normal_user_token_headers,
        )
        assert create_response.status_code == 201
        request_id = create_response.json()["join_request_id"]

        with patch("app.api.endpoints.agencies.sync_supabase_auth_user_metadata"):
            response = client.patch(
                f"/api/v1/agencies/{agency.agency_id}/join-requests/{request_id}/approve/",
                headers=agency_owner_token_headers,
            )

        assert response.status_code == 200
        assert response.json()["status"] == "approved"
        db.refresh(normal_user)
        assert normal_user.user_role == UserRole.AGENT
        assert normal_user.agency_id == agency.agency_id
        membership = db.query(AgencyAgentMembership).filter(
            AgencyAgentMembership.agency_id == agency.agency_id,
            AgencyAgentMembership.user_id == normal_user.user_id,
        ).one_or_none()
        assert membership is not None
        assert membership.status == "active"

    def test_approve_join_request_reactivates_existing_membership(
        self, client: TestClient, db, agency, normal_user, normal_user_token_headers, agency_owner_token_headers
    ):
        from unittest.mock import patch
        from app.models.agency_join_requests import AgencyAgentMembership

        existing_membership = AgencyAgentMembership(
            agency_id=agency.agency_id,
            user_id=normal_user.user_id,
            status="inactive",
            deleted_at=datetime.now(UTC),
        )
        db.add(existing_membership)
        db.flush()

        create_response = client.post(
            f"/api/v1/agencies/{agency.agency_id}/join-request/",
            json={"portfolio_details": "Returning member"},
            headers=normal_user_token_headers,
        )
        request_id = create_response.json()["join_request_id"]

        with patch("app.api.endpoints.agencies.sync_supabase_auth_user_metadata"):
            response = client.patch(
                f"/api/v1/agencies/{agency.agency_id}/join-requests/{request_id}/approve/",
                headers=agency_owner_token_headers,
            )

        assert response.status_code == 200
        db.refresh(existing_membership)
        assert existing_membership.status == "active"
        assert existing_membership.deleted_at is None
        assert existing_membership.source_join_request_id == request_id

    def test_approved_join_request_agent_appears_in_agency_roster(
        self, client: TestClient, agency, normal_user, normal_user_token_headers, agency_owner_token_headers
    ):
        from unittest.mock import patch

        create_response = client.post(
            f"/api/v1/agencies/{agency.agency_id}/join-request/",
            json={"portfolio_details": "Portfolio text"},
            headers=normal_user_token_headers,
        )
        request_id = create_response.json()["join_request_id"]
        with patch("app.api.endpoints.agencies.sync_supabase_auth_user_metadata"):
            approve_response = client.patch(
                f"/api/v1/agencies/{agency.agency_id}/join-requests/{request_id}/approve/",
                headers=agency_owner_token_headers,
            )

        roster_response = client.get(f"/api/v1/agencies/{agency.agency_id}/agents")

        assert approve_response.status_code == 200
        assert roster_response.status_code == 200
        roster_item = next(item for item in roster_response.json() if item["user_id"] == normal_user.user_id)
        assert roster_item["email"] == normal_user.email
        assert roster_item["display_name"] == normal_user.full_name
        assert roster_item["membership_status"] == "active"

    def test_approve_join_request_returns_404_for_missing_request(
        self, client: TestClient, agency, agency_owner_token_headers
    ):
        response = client.patch(
            f"/api/v1/agencies/{agency.agency_id}/join-requests/999999/approve/",
            headers=agency_owner_token_headers,
        )

        assert response.status_code == 404

    def test_approve_reviewed_join_request_returns_400(
        self, client: TestClient, agency, normal_user_token_headers, agency_owner_token_headers
    ):
        create_response = client.post(
            f"/api/v1/agencies/{agency.agency_id}/join-request/",
            json={"cover_note": "Please consider me"},
            headers=normal_user_token_headers,
        )
        request_id = create_response.json()["join_request_id"]
        reject_response = client.patch(
            f"/api/v1/agencies/{agency.agency_id}/join-requests/{request_id}/reject/",
            headers=agency_owner_token_headers,
        )

        response = client.patch(
            f"/api/v1/agencies/{agency.agency_id}/join-requests/{request_id}/approve/",
            headers=agency_owner_token_headers,
        )

        assert reject_response.status_code == 200
        assert response.status_code == 400

    def test_approve_join_request_rolls_back_on_supabase_sync_failure(
        self, client: TestClient, db, agency, normal_user, normal_user_token_headers, agency_owner_token_headers
    ):
        from unittest.mock import patch

        create_response = client.post(
            f"/api/v1/agencies/{agency.agency_id}/join-request/",
            json={"cover_note": "Please consider me"},
            headers=normal_user_token_headers,
        )
        request_id = create_response.json()["join_request_id"]

        with patch(
            "app.api.endpoints.agencies.sync_supabase_auth_user_metadata",
            side_effect=agencies_api.SupabaseUserSyncError("sync failed"),
        ):
            response = client.patch(
                f"/api/v1/agencies/{agency.agency_id}/join-requests/{request_id}/approve/",
                headers=agency_owner_token_headers,
            )

        assert response.status_code == 502

    def test_agency_owner_rejects_join_request(
        self, client: TestClient, agency, normal_user_token_headers, agency_owner_token_headers
    ):
        create_response = client.post(
            f"/api/v1/agencies/{agency.agency_id}/join-request/",
            json={"cover_note": "Not yet ready"},
            headers=normal_user_token_headers,
        )
        assert create_response.status_code == 201
        request_id = create_response.json()["join_request_id"]

        response = client.patch(
            f"/api/v1/agencies/{agency.agency_id}/join-requests/{request_id}/reject/",
            json={"reason": "Need more details"},
            headers=agency_owner_token_headers,
        )

        assert response.status_code == 200
        assert response.json()["status"] == "rejected"
        assert response.json()["rejection_reason"] == "Need more details"

    def test_reject_join_request_returns_404_for_missing_request(
        self, client: TestClient, agency, agency_owner_token_headers
    ):
        response = client.patch(
            f"/api/v1/agencies/{agency.agency_id}/join-requests/999999/reject/",
            headers=agency_owner_token_headers,
        )

        assert response.status_code == 404

    def test_reject_reviewed_join_request_returns_400(
        self, client: TestClient, agency, normal_user_token_headers, agency_owner_token_headers
    ):
        from unittest.mock import patch

        create_response = client.post(
            f"/api/v1/agencies/{agency.agency_id}/join-request/",
            json={"cover_note": "Please consider me"},
            headers=normal_user_token_headers,
        )
        request_id = create_response.json()["join_request_id"]
        with patch("app.api.endpoints.agencies.sync_supabase_auth_user_metadata"):
            approve_response = client.patch(
                f"/api/v1/agencies/{agency.agency_id}/join-requests/{request_id}/approve/",
                headers=agency_owner_token_headers,
            )

        response = client.patch(
            f"/api/v1/agencies/{agency.agency_id}/join-requests/{request_id}/reject/",
            headers=agency_owner_token_headers,
        )

        assert approve_response.status_code == 200
        assert response.status_code == 400


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

    def test_soft_deleted_agency_not_returned_by_get(
        self, client: TestClient, admin_token_headers, db
    ):
        from app.models.agencies import Agency

        agency_obj = Agency(name="Agency Hidden After Delete")
        db.add(agency_obj)
        db.flush()
        db.refresh(agency_obj)

        delete_response = client.delete(
            f"/api/v1/agencies/{agency_obj.agency_id}",
            headers=admin_token_headers
        )
        assert delete_response.status_code == 200

        response = client.get(f"/api/v1/agencies/{agency_obj.agency_id}")
        assert response.status_code == 404
        assert response.json()["detail"] == "Agency not found"

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

    def test_read_agency_agents_serializes_agent_profiles(
        self, client: TestClient, db, agency
    ):
        from app.models.agent_profiles import AgentProfile
        from app.models.users import User, UserRole

        agent_user = User(
            email=f"agency_agent_{uuid.uuid4().hex[:6]}@example.com",
            password_hash="hashed_placeholder",
            first_name="Agency",
            last_name="Agent",
            user_role=UserRole.AGENT,
            supabase_id=uuid.uuid4(),
            agency_id=agency.agency_id,
        )
        db.add(agent_user)
        db.flush()
        db.refresh(agent_user)

        profile = AgentProfile(
            user_id=agent_user.user_id,
            agency_id=agency.agency_id,
            license_number="LIC-AGENCY-001",
            specialization="Residential Sales",
        )
        db.add(profile)
        db.flush()
        db.refresh(profile)
        from app.models.agency_join_requests import AgencyAgentMembership

        membership = AgencyAgentMembership(
            agency_id=agency.agency_id,
            user_id=agent_user.user_id,
            agent_profile_id=profile.profile_id,
            status="active",
        )
        db.add(membership)
        db.flush()

        response = client.get(f"/api/v1/agencies/{agency.agency_id}/agents")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        item = next(item for item in data if item["user_id"] == agent_user.user_id)
        assert item["profile_id"] == profile.profile_id
        assert item["agency_id"] == agency.agency_id
        assert item["license_number"] == "LIC-AGENCY-001"
        assert item["email"] == agent_user.email


class TestReadAgencyProperties:

    def test_agency_not_found_returns_404(self, client: TestClient):
        response = client.get("/api/v1/agencies/999999/properties")
        assert response.status_code == 404

    def test_read_agency_properties_success(self, client: TestClient, agency):
        response = client.get(f"/api/v1/agencies/{agency.agency_id}/properties")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_read_agency_properties_serializes_properties(
        self, client: TestClient, db, agency, agent_user, location, property_type
    ):
        from app.models.properties import Property, ListingType, ListingStatus
        from geoalchemy2.elements import WKTElement

        property_obj = Property(
            title="Serialized Agency Property",
            description="Agency listing for serialization test",
            user_id=agent_user.user_id,
            agency_id=agency.agency_id,
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
        db.add(property_obj)
        db.flush()
        db.refresh(property_obj)

        response = client.get(f"/api/v1/agencies/{agency.agency_id}/properties")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        assert data[0]["property_id"] == property_obj.property_id
        assert data[0]["title"] == "Serialized Agency Property"
        assert data[0]["user_id"] == agent_user.user_id


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

    def test_agency_stats_counts_users_not_profiles(
        self, client: TestClient, admin_token_headers, db, agency
    ):
        agent_without_profile = User(
            email=f"agency_stats_agent_{uuid.uuid4().hex[:6]}@example.com",
            password_hash="hashed_placeholder",
            first_name="NoProfile",
            last_name="Agent",
            user_role=UserRole.AGENT,
            supabase_id=uuid.uuid4(),
            agency_id=agency.agency_id,
        )
        db.add(agent_without_profile)
        db.flush()
        db.refresh(agent_without_profile)

        response = client.get(
            f"/api/v1/agencies/{agency.agency_id}/stats",
            headers=admin_token_headers
        )
        assert response.status_code == 200
        assert response.json()["agent_count"] >= 1
