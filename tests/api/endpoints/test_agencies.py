# tests/api/endpoints/test_agencies.py
"""
Surgical API-layer tests for /agencies endpoints.
"""
from fastapi.testclient import TestClient
from datetime import UTC, datetime, timedelta, timezone
import uuid
from unittest.mock import patch
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
        with patch("app.api.endpoints.agencies.dispatch_email_task") as mock_email:
            response = client.post(
                f"/api/v1/agencies/{agency.agency_id}/invite/",
                json={"email": "newagent@example.com"},
                headers=agency_owner_token_headers,
            )

        assert response.status_code == 200
        data = response.json()
        assert data["agency_id"] == agency.agency_id
        assert data["invite_token"]
        assert data["invitation_id"]
        assert data["status"] == "pending"
        mock_email.assert_called_once()

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
        from unittest.mock import patch
        from app.models.agency_join_requests import AgencyAgentMembership

        invite_response = client.post(
            f"/api/v1/agencies/{agency.agency_id}/invite/",
            json={"email": normal_user.email},
            headers=agency_owner_token_headers,
        )
        assert invite_response.status_code == 200

        with patch("app.api.endpoints.agencies.sync_supabase_auth_user_metadata"):
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

    def test_invited_user_can_view_pending_invitation_inbox(
        self, client: TestClient, agency, agency_owner_token_headers, normal_user, normal_user_token_headers
    ):
        invite_response = client.post(
            f"/api/v1/agencies/{agency.agency_id}/invite/",
            json={"email": normal_user.email},
            headers=agency_owner_token_headers,
        )
        invitation_id = invite_response.json()["invitation_id"]

        response = client.get(
            "/api/v1/agency-invitations/mine/",
            headers=normal_user_token_headers,
        )

        assert response.status_code == 200
        invitation = next(item for item in response.json() if item["invitation_id"] == invitation_id)
        assert invitation["agency_id"] == agency.agency_id
        assert invitation["agency_name"] == agency.name
        assert invitation["status"] == "pending"

    def test_invitation_inbox_rejects_invalid_status_filter(
        self, client: TestClient, normal_user_token_headers
    ):
        response = client.get(
            "/api/v1/agency-invitations/mine/",
            params={"status": "unknown"},
            headers=normal_user_token_headers,
        )

        assert response.status_code == 400
        assert response.json()["detail"] == "Invalid invitation status filter"

    def test_invitation_inbox_marks_expired_pending_invitations(
        self, client: TestClient, db, agency, normal_user, normal_user_token_headers
    ):
        from app.models.agency_join_requests import AgencyInvitation

        invitation = AgencyInvitation(
            agency_id=agency.agency_id,
            email=normal_user.email,
            invited_user_id=normal_user.user_id,
            status="pending",
            expires_at=datetime.now(timezone.utc) - timedelta(days=1),
        )
        db.add(invitation)
        db.flush()
        db.refresh(invitation)

        response = client.get(
            "/api/v1/agency-invitations/mine/",
            params={"status": "all"},
            headers=normal_user_token_headers,
        )

        assert response.status_code == 200
        item = next(row for row in response.json() if row["invitation_id"] == invitation.invitation_id)
        assert item["status"] == "expired"

    def test_invited_user_accepts_invitation_by_id(
        self, client: TestClient, db, agency, agency_owner_token_headers, normal_user, normal_user_token_headers
    ):
        from unittest.mock import patch
        from app.models.agency_join_requests import AgencyAgentMembership, AgencyInvitation
        from app.models.users import UserRole

        invite_response = client.post(
            f"/api/v1/agencies/{agency.agency_id}/invite/",
            json={"email": normal_user.email},
            headers=agency_owner_token_headers,
        )
        invitation_id = invite_response.json()["invitation_id"]

        with patch("app.api.endpoints.agencies.sync_supabase_auth_user_metadata") as sync_mock:
            response = client.patch(
                f"/api/v1/agency-invitations/{invitation_id}/accept/",
                headers=normal_user_token_headers,
            )

        assert response.status_code == 200
        assert response.json()["status"] == "accepted"
        db.refresh(normal_user)
        assert normal_user.user_role == UserRole.AGENT
        membership = db.query(AgencyAgentMembership).filter(
            AgencyAgentMembership.agency_id == agency.agency_id,
            AgencyAgentMembership.user_id == normal_user.user_id,
            AgencyAgentMembership.status == "active",
        ).one_or_none()
        invitation = db.query(AgencyInvitation).filter(
            AgencyInvitation.invitation_id == invitation_id,
        ).one()
        assert membership is not None
        assert invitation.status == "accepted"
        assert invitation.accepted_at is not None
        sync_mock.assert_called_once()

    def test_invited_user_rejects_invitation_by_id(
        self, client: TestClient, db, agency, agency_owner_token_headers, normal_user, normal_user_token_headers
    ):
        from app.models.agency_join_requests import AgencyInvitation

        invite_response = client.post(
            f"/api/v1/agencies/{agency.agency_id}/invite/",
            json={"email": normal_user.email},
            headers=agency_owner_token_headers,
        )
        invitation_id = invite_response.json()["invitation_id"]

        response = client.patch(
            f"/api/v1/agency-invitations/{invitation_id}/reject/",
            headers=normal_user_token_headers,
        )

        assert response.status_code == 200
        assert response.json()["status"] == "rejected"
        invitation = db.query(AgencyInvitation).filter(
            AgencyInvitation.invitation_id == invitation_id,
        ).one()
        assert invitation.rejected_at is not None

    def test_agency_owner_can_list_sent_invitations(
        self, client: TestClient, agency, agency_owner_token_headers, normal_user
    ):
        invite_response = client.post(
            f"/api/v1/agencies/{agency.agency_id}/invite/",
            json={"email": normal_user.email},
            headers=agency_owner_token_headers,
        )
        invitation_id = invite_response.json()["invitation_id"]

        response = client.get(
            f"/api/v1/agencies/{agency.agency_id}/invitations/",
            headers=agency_owner_token_headers,
        )

        assert response.status_code == 200
        invitation = next(item for item in response.json() if item["invitation_id"] == invitation_id)
        assert invitation["email"] == normal_user.email
        assert invitation["status"] == "pending"

    def test_agency_owner_invitation_list_rejects_invalid_status_filter(
        self, client: TestClient, agency, agency_owner_token_headers
    ):
        response = client.get(
            f"/api/v1/agencies/{agency.agency_id}/invitations/",
            params={"status": "unknown"},
            headers=agency_owner_token_headers,
        )

        assert response.status_code == 400
        assert response.json()["detail"] == "Invalid invitation status filter"

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

    def test_join_request_for_existing_active_membership_returns_409(
        self, client: TestClient, db, agency, normal_user, normal_user_token_headers
    ):
        from app.models.agency_join_requests import AgencyAgentMembership

        membership = AgencyAgentMembership(
            agency_id=agency.agency_id,
            user_id=normal_user.user_id,
            status="active",
        )
        db.add(membership)
        db.flush()

        response = client.post(
            f"/api/v1/agencies/{agency.agency_id}/join-request/",
            json={"cover_note": "Please consider me again"},
            headers=normal_user_token_headers,
        )

        assert response.status_code == 409
        assert response.json()["detail"] == "User is already affiliated with this agency"

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

        with patch("app.api.endpoints.agencies.sync_supabase_auth_user_metadata"), \
             patch("app.api.endpoints.agencies.dispatch_email_task") as mock_email:
            response = client.patch(
                f"/api/v1/agencies/{agency.agency_id}/join-requests/{request_id}/approve/",
                headers=agency_owner_token_headers,
            )

        assert response.status_code == 200
        assert response.json()["status"] == "approved"
        mock_email.assert_called_once()
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

        with patch("app.api.endpoints.agencies.dispatch_email_task") as mock_email:
            response = client.patch(
                f"/api/v1/agencies/{agency.agency_id}/join-requests/{request_id}/reject/",
                json={"reason": "Need more details"},
                headers=agency_owner_token_headers,
            )

        assert response.status_code == 200
        assert response.json()["status"] == "rejected"
        assert response.json()["rejection_reason"] == "Need more details"
        mock_email.assert_called_once()

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

    def test_agency_owner_can_view_all_membership_statuses(
        self, client: TestClient, db, agency, agent_user, agency_owner_token_headers
    ):
        from app.models.agency_join_requests import AgencyAgentMembership

        membership = AgencyAgentMembership(
            agency_id=agency.agency_id,
            user_id=agent_user.user_id,
            status="suspended",
            status_reason="Compliance review",
        )
        db.add(membership)
        db.flush()

        public_response = client.get(f"/api/v1/agencies/{agency.agency_id}/agents")
        owner_response = client.get(
            f"/api/v1/agencies/{agency.agency_id}/agents",
            params={"status": "all"},
            headers=agency_owner_token_headers,
        )

        assert public_response.status_code == 200
        assert all(item["user_id"] != agent_user.user_id for item in public_response.json())
        assert owner_response.status_code == 200
        item = next(item for item in owner_response.json() if item["user_id"] == agent_user.user_id)
        assert item["membership_status"] == "suspended"
        assert item["status_reason"] == "Compliance review"

    def test_public_cannot_view_non_active_membership_statuses(
        self, client: TestClient, agency
    ):
        response = client.get(
            f"/api/v1/agencies/{agency.agency_id}/agents",
            params={"status": "all"},
        )

        assert response.status_code == 403


class TestAgencyAgentMembershipManagement:

    def test_agency_owner_suspends_revokes_and_blocks_membership(
        self, client: TestClient, db, agency, agent_user, agency_owner_user, agency_owner_token_headers
    ):
        from unittest.mock import patch
        from app.models.agency_join_requests import AgencyAgentMembership

        membership = AgencyAgentMembership(
            agency_id=agency.agency_id,
            user_id=agent_user.user_id,
            status="active",
        )
        db.add(membership)
        db.flush()
        db.refresh(membership)

        with patch("app.api.endpoints.agencies.sync_supabase_auth_user_metadata"):
            suspend_response = client.patch(
                f"/api/v1/agencies/{agency.agency_id}/agents/{membership.membership_id}/suspend/",
                json={"reason": "License needs review"},
                headers=agency_owner_token_headers,
            )
            revoke_response = client.patch(
                f"/api/v1/agencies/{agency.agency_id}/agents/{membership.membership_id}/revoke/",
                json={"reason": "Contract ended"},
                headers=agency_owner_token_headers,
            )
            block_response = client.patch(
                f"/api/v1/agencies/{agency.agency_id}/agents/{membership.membership_id}/block/",
                json={"reason": "Policy violation"},
                headers=agency_owner_token_headers,
            )

        assert suspend_response.status_code == 200
        assert suspend_response.json()["status"] == "suspended"
        assert suspend_response.json()["status_reason"] == "License needs review"
        assert suspend_response.json()["status_decided_by"] == agency_owner_user.user_id
        assert suspend_response.json()["status_decided_at"] is not None
        assert revoke_response.status_code == 200
        assert revoke_response.json()["status"] == "inactive"
        assert block_response.status_code == 200
        assert block_response.json()["status"] == "blocked"

    def test_revoking_last_active_membership_demotes_agent_to_seeker(
        self, client: TestClient, db, agency, agent_user, agency_owner_token_headers
    ):
        from unittest.mock import patch
        from app.models.agency_join_requests import AgencyAgentMembership
        from app.models.users import UserRole

        membership = AgencyAgentMembership(
            agency_id=agency.agency_id,
            user_id=agent_user.user_id,
            status="active",
        )
        db.add(membership)
        db.flush()
        db.refresh(membership)

        with patch("app.api.endpoints.agencies.sync_supabase_auth_user_metadata") as sync_mock:
            response = client.patch(
                f"/api/v1/agencies/{agency.agency_id}/agents/{membership.membership_id}/revoke/",
                json={"reason": "Contract ended"},
                headers=agency_owner_token_headers,
            )

        assert response.status_code == 200
        db.refresh(agent_user)
        assert agent_user.user_role == UserRole.SEEKER
        assert agent_user.agency_id is None
        sync_mock.assert_called_once()

    def test_revoking_one_of_multiple_active_memberships_keeps_agent_role(
        self, client: TestClient, db, agency, other_agency, agent_user, agency_owner_token_headers
    ):
        from unittest.mock import patch
        from app.models.agency_join_requests import AgencyAgentMembership
        from app.models.users import UserRole

        owned_membership = AgencyAgentMembership(
            agency_id=agency.agency_id,
            user_id=agent_user.user_id,
            status="active",
        )
        other_membership = AgencyAgentMembership(
            agency_id=other_agency.agency_id,
            user_id=agent_user.user_id,
            status="active",
        )
        db.add_all([owned_membership, other_membership])
        db.flush()
        db.refresh(owned_membership)

        with patch("app.api.endpoints.agencies.sync_supabase_auth_user_metadata"):
            response = client.patch(
                f"/api/v1/agencies/{agency.agency_id}/agents/{owned_membership.membership_id}/revoke/",
                json={"reason": "Left this branch"},
                headers=agency_owner_token_headers,
            )

        assert response.status_code == 200
        db.refresh(agent_user)
        assert agent_user.user_role == UserRole.AGENT
        assert agent_user.agency_id == other_agency.agency_id

    def test_restore_membership_promotes_seeker_back_to_agent(
        self, client: TestClient, db, agency, normal_user, agency_owner_token_headers
    ):
        from unittest.mock import patch
        from app.models.agency_join_requests import AgencyAgentMembership
        from app.models.users import UserRole

        membership = AgencyAgentMembership(
            agency_id=agency.agency_id,
            user_id=normal_user.user_id,
            status="inactive",
            status_reason="Contract ended",
        )
        db.add(membership)
        db.flush()
        db.refresh(membership)

        with patch("app.api.endpoints.agencies.sync_supabase_auth_user_metadata") as sync_mock:
            response = client.patch(
                f"/api/v1/agencies/{agency.agency_id}/agents/{membership.membership_id}/restore/",
                json={"reason": "Review approved"},
                headers=agency_owner_token_headers,
            )

        assert response.status_code == 200
        assert response.json()["status"] == "active"
        db.refresh(normal_user)
        assert normal_user.user_role == UserRole.AGENT
        assert normal_user.agency_id == agency.agency_id
        sync_mock.assert_called_once()

    def test_approve_review_request_restores_membership(
        self, client: TestClient, db, agency, normal_user, normal_user_token_headers, agency_owner_token_headers
    ):
        from unittest.mock import patch
        from app.models.agency_join_requests import AgencyAgentMembership

        membership = AgencyAgentMembership(
            agency_id=agency.agency_id,
            user_id=normal_user.user_id,
            status="inactive",
            status_reason="Contract ended",
        )
        db.add(membership)
        db.flush()
        db.refresh(membership)

        review_response = client.post(
            f"/api/v1/agencies/{agency.agency_id}/agents/{membership.membership_id}/review-request/",
            json={"reason": "I have updated my paperwork."},
            headers=normal_user_token_headers,
        )
        review_request_id = review_response.json()["review_request_id"]

        with patch("app.api.endpoints.agencies.sync_supabase_auth_user_metadata"):
            approve_response = client.patch(
                f"/api/v1/agencies/{agency.agency_id}/agents/{membership.membership_id}/review-requests/{review_request_id}/approve/",
                json={"reason": "Paperwork accepted"},
                headers=agency_owner_token_headers,
            )

        assert review_response.status_code == 201
        assert approve_response.status_code == 200
        assert approve_response.json()["status"] == "approved"
        db.refresh(membership)
        assert membership.status == "active"

    def test_reject_review_request_keeps_membership_inactive(
        self, client: TestClient, db, agency, normal_user, normal_user_token_headers, agency_owner_token_headers
    ):
        from app.models.agency_join_requests import AgencyAgentMembership

        membership = AgencyAgentMembership(
            agency_id=agency.agency_id,
            user_id=normal_user.user_id,
            status="inactive",
        )
        db.add(membership)
        db.flush()
        db.refresh(membership)
        review_response = client.post(
            f"/api/v1/agencies/{agency.agency_id}/agents/{membership.membership_id}/review-request/",
            json={"reason": "Please reconsider."},
            headers=normal_user_token_headers,
        )
        review_request_id = review_response.json()["review_request_id"]

        reject_response = client.patch(
            f"/api/v1/agencies/{agency.agency_id}/agents/{membership.membership_id}/review-requests/{review_request_id}/reject/",
            json={"reason": "Still missing documents"},
            headers=agency_owner_token_headers,
        )

        assert reject_response.status_code == 200
        assert reject_response.json()["status"] == "rejected"
        assert reject_response.json()["response_reason"] == "Still missing documents"
        db.refresh(membership)
        assert membership.status == "inactive"

    def test_agency_roster_includes_pending_review_metadata(
        self, client: TestClient, db, agency, normal_user, normal_user_token_headers, agency_owner_token_headers
    ):
        from app.models.agency_join_requests import AgencyAgentMembership

        membership = AgencyAgentMembership(
            agency_id=agency.agency_id,
            user_id=normal_user.user_id,
            status="inactive",
        )
        db.add(membership)
        db.flush()
        db.refresh(membership)

        review_response = client.post(
            f"/api/v1/agencies/{agency.agency_id}/agents/{membership.membership_id}/review-request/",
            json={"reason": "I have completed the required update."},
            headers=normal_user_token_headers,
        )
        assert review_response.status_code == 201

        roster_response = client.get(
            f"/api/v1/agencies/{agency.agency_id}/agents",
            params={"status": "all"},
            headers=agency_owner_token_headers,
        )

        assert roster_response.status_code == 200
        roster_item = next(
            item for item in roster_response.json()
            if item["membership_id"] == membership.membership_id
        )
        assert roster_item["pending_review_request_id"] == review_response.json()["review_request_id"]
        assert roster_item["pending_review_reason"] == "I have completed the required update."
        assert roster_item["pending_review_submitted_at"] is not None

    def test_other_agency_owner_cannot_manage_membership(
        self, client: TestClient, db, agency, other_agency, agent_user
    ):
        from app.models.agency_join_requests import AgencyAgentMembership

        other_owner = User(
            email=f"other_owner_{uuid.uuid4().hex[:6]}@example.com",
            password_hash="hashed_placeholder",
            first_name="Other",
            last_name="Owner",
            user_role=UserRole.AGENCY_OWNER,
            supabase_id=uuid.uuid4(),
            agency_id=other_agency.agency_id,
        )
        db.add(other_owner)
        membership = AgencyAgentMembership(
            agency_id=agency.agency_id,
            user_id=agent_user.user_id,
            status="active",
        )
        db.add(membership)
        db.flush()
        token = generate_access_token(
            supabase_id=other_owner.supabase_id,
            user_id=other_owner.user_id,
            user_role=other_owner.user_role.value,
            agency_id=other_owner.agency_id,
        )

        response = client.patch(
            f"/api/v1/agencies/{agency.agency_id}/agents/{membership.membership_id}/suspend/",
            json={"reason": "No permission"},
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 403

    def test_agent_can_request_review_for_suspended_membership(
        self, client: TestClient, db, agency, agent_user, agent_token_headers
    ):
        from app.models.agency_join_requests import AgencyAgentMembership

        membership = AgencyAgentMembership(
            agency_id=agency.agency_id,
            user_id=agent_user.user_id,
            status="suspended",
            status_reason="License needs review",
        )
        db.add(membership)
        db.flush()
        db.refresh(membership)

        response = client.post(
            f"/api/v1/agencies/{agency.agency_id}/agents/{membership.membership_id}/review-request/",
            json={"reason": "My license has been renewed."},
            headers=agent_token_headers,
        )

        assert response.status_code == 201
        assert response.json()["membership_id"] == membership.membership_id
        assert response.json()["status"] == "pending"
        assert response.json()["reason"] == "My license has been renewed."

    def test_agent_cannot_request_review_for_active_membership(
        self, client: TestClient, db, agency, agent_user, agent_token_headers
    ):
        from app.models.agency_join_requests import AgencyAgentMembership

        membership = AgencyAgentMembership(
            agency_id=agency.agency_id,
            user_id=agent_user.user_id,
            status="active",
        )
        db.add(membership)
        db.flush()

        response = client.post(
            f"/api/v1/agencies/{agency.agency_id}/agents/{membership.membership_id}/review-request/",
            json={"reason": "Please review"},
            headers=agent_token_headers,
        )

        assert response.status_code == 400


class TestMyAgencyMemberships:

    def test_agent_lists_own_non_active_membership_statuses(
        self, client: TestClient, db, agency, other_agency, agent_user, agent_token_headers
    ):
        from app.models.agency_join_requests import AgencyAgentMembership, AgencyMembershipReviewRequest

        suspended_membership = AgencyAgentMembership(
            agency_id=agency.agency_id,
            user_id=agent_user.user_id,
            status="suspended",
            status_reason="License needs review",
        )
        blocked_membership = AgencyAgentMembership(
            agency_id=other_agency.agency_id,
            user_id=agent_user.user_id,
            status="blocked",
            status_reason="Policy violation",
        )
        db.add_all([suspended_membership, blocked_membership])
        db.flush()
        db.refresh(suspended_membership)

        review_request = AgencyMembershipReviewRequest(
            membership_id=suspended_membership.membership_id,
            agency_id=agency.agency_id,
            user_id=agent_user.user_id,
            status="pending",
            reason="My license has been renewed.",
        )
        db.add(review_request)
        db.flush()

        response = client.get(
            "/api/v1/agency-memberships/mine/",
            headers=agent_token_headers,
        )

        assert response.status_code == 200
        data = response.json()
        statuses_by_agency = {item["agency_id"]: item for item in data}
        assert statuses_by_agency[agency.agency_id]["status"] == "suspended"
        assert statuses_by_agency[agency.agency_id]["status_reason"] == "License needs review"
        assert statuses_by_agency[agency.agency_id]["pending_review_request_id"] == review_request.review_request_id
        assert statuses_by_agency[agency.agency_id]["pending_review_reason"] == "My license has been renewed."
        assert statuses_by_agency[other_agency.agency_id]["status"] == "blocked"

    def test_seeker_without_memberships_gets_empty_membership_status_list(
        self, client: TestClient, normal_user_token_headers
    ):
        response = client.get(
            "/api/v1/agency-memberships/mine/",
            headers=normal_user_token_headers,
        )

        assert response.status_code == 200
        assert response.json() == []

    def test_admin_cannot_read_personal_membership_status_list(
        self, client: TestClient, admin_token_headers
    ):
        response = client.get(
            "/api/v1/agency-memberships/mine/",
            headers=admin_token_headers,
        )

        assert response.status_code == 403

    def test_agent_membership_status_returns_most_restrictive_state(
        self, client: TestClient, db, agency, other_agency, agent_user, agent_token_headers
    ):
        from app.models.agency_join_requests import AgencyAgentMembership

        active_membership = AgencyAgentMembership(
            agency_id=agency.agency_id,
            user_id=agent_user.user_id,
            status="active",
        )
        blocked_membership = AgencyAgentMembership(
            agency_id=other_agency.agency_id,
            user_id=agent_user.user_id,
            status="blocked",
            status_reason="Policy violation",
        )
        db.add_all([active_membership, blocked_membership])
        db.flush()

        response = client.get(
            "/api/v1/membership/me/status",
            headers=agent_token_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["agent_id"] == str(agent_user.supabase_id)
        assert data["status"] == "blocked"
        assert data["reason"] == "Policy violation"
        assert data["agency_id"] == other_agency.agency_id
        assert data["updated_at"] is not None

    def test_agent_membership_status_maps_inactive_to_revoked(
        self, client: TestClient, db, agency, agent_user, agent_token_headers
    ):
        from app.models.agency_join_requests import AgencyAgentMembership

        membership = AgencyAgentMembership(
            agency_id=agency.agency_id,
            user_id=agent_user.user_id,
            status="inactive",
            status_reason="Contract ended",
        )
        db.add(membership)
        db.flush()

        response = client.get(
            "/api/v1/membership/me/status",
            headers=agent_token_headers,
        )

        assert response.status_code == 200
        assert response.json()["status"] == "revoked"
        assert response.json()["reason"] == "Contract ended"

    def test_seeker_cannot_read_agent_membership_status(
        self, client: TestClient, normal_user_token_headers
    ):
        response = client.get(
            "/api/v1/membership/me/status",
            headers=normal_user_token_headers,
        )

        assert response.status_code == 403


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
