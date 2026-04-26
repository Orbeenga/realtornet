"""
Surgical API-layer tests for app/api/endpoints/admin.py.

Admin endpoints have the widest blast radius:
- They bypass ownership checks
- They operate across all entities
- They are gated exclusively by admin privileges
"""
import uuid
from unittest.mock import patch
from fastapi.testclient import TestClient
from geoalchemy2.elements import WKTElement

from app.crud.users import user as user_crud
from app.crud.properties import property as property_crud
from app.crud.inquiries import inquiry as inquiry_crud
from app.schemas.properties import PropertyCreate
from app.schemas.inquiries import InquiryCreate
from app.schemas.users import UserCreate
from app.api.endpoints import admin as admin_api
from app.models.properties import Property, ListingType, ListingStatus


def _create_property(db, user_id, location, property_type, agency, title):
    """Create a minimal property for admin tests."""
    obj_in = PropertyCreate(
        title=title,
        description="Admin test property",
        price=5000000,
        bedrooms=2,
        bathrooms=1,
        location_id=location.location_id,
        property_type_id=property_type.property_type_id,
        listing_type="sale",
        listing_status="available",
        agency_id=agency.agency_id,
    )
    return property_crud.create(db, obj_in=obj_in, user_id=user_id)


class TestAdminGetUsers:
    def test_admin_can_list_all_users(
        self, client: TestClient, admin_token_headers, normal_user
    ):
        """
        Admin can list users across the system.

        This verifies admin visibility is unrestricted while still requiring auth.
        """
        response = client.get("/api/v1/admin/users", headers=admin_token_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data["items"], list)
        assert data["total"] >= 1

    def test_admin_list_users_non_admin_returns_403(
        self, client: TestClient, normal_user_token_headers
    ):
        """
        Non-admins must not access admin user lists.

        This prevents privilege escalation via read-only endpoints.
        """
        response = client.get("/api/v1/admin/users", headers=normal_user_token_headers)
        assert response.status_code == 403

    def test_admin_list_users_unauthenticated_returns_401(
        self, client: TestClient
    ):
        """
        Unauthenticated requests must be rejected.

        This enforces authentication on admin endpoints.
        """
        response = client.get("/api/v1/admin/users")
        assert response.status_code == 401


class TestAdminCreateUser:
    def test_admin_can_create_user(
        self, client: TestClient, admin_token_headers, db
    ):
        """
        Admin can create a new user with required fields.

        This ensures admin provisioning works and persists to the database.
        """
        email = f"admin_create_{uuid.uuid4().hex[:6]}@example.com"
        response = client.post(
            "/api/v1/admin/users",
            headers=admin_token_headers,
            json={
                "email": email,
                "password": "ValidPass123!",
                "first_name": "Admin",
                "last_name": "Created",
                "user_role": "seeker",
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == email
        assert data["created_by"] is not None
        assert user_crud.get_by_email(db, email=email) is not None

    def test_admin_create_user_with_deleted_email_returns_400(
        self, client: TestClient, admin_token_headers, admin_user, db
    ):
        """
        Creating a user with a previously deleted email must 400.

        This protects against silently reusing soft-deleted accounts.
        """
        email = f"deleted_{uuid.uuid4().hex[:6]}@example.com"
        deleted_user = user_crud.create(
            db,
            obj_in=UserCreate(
                email=email,
                password="ValidPass123!",
                first_name="Deleted",
                last_name="User",
                user_role="seeker",
            ),
            supabase_id=str(uuid.uuid4())
        )
        user_crud.soft_delete(
            db,
            user_id=deleted_user.user_id,
            deleted_by_supabase_id=admin_user.supabase_id
        )
        response = client.post(
            "/api/v1/admin/users",
            headers=admin_token_headers,
            json={
                "email": email,
                "password": "ValidPass123!",
                "first_name": "New",
                "last_name": "User",
                "user_role": "seeker",
            }
        )
        assert response.status_code == 400
        assert "previously deleted" in response.json()["detail"]

    def test_admin_create_user_non_admin_returns_403(
        self, client: TestClient, normal_user_token_headers
    ):
        """
        Non-admins must not create users.

        This prevents unauthorized account creation.
        """
        response = client.post(
            "/api/v1/admin/users",
            headers=normal_user_token_headers,
            json={
                "email": "blocked@example.com",
                "password": "ValidPass123!",
                "first_name": "No",
                "last_name": "Access",
                "user_role": "seeker",
            }
        )
        assert response.status_code == 403

    def test_admin_create_user_unauthenticated_returns_401(
        self, client: TestClient
    ):
        """
        Unauthenticated requests must be rejected.

        This keeps user creation behind admin auth.
        """
        response = client.post(
            "/api/v1/admin/users",
            json={
                "email": "noauth@example.com",
                "password": "ValidPass123!",
                "first_name": "No",
                "last_name": "Auth",
                "user_role": "seeker",
            }
        )
        assert response.status_code == 401


class TestAdminGetUser:
    def test_admin_can_get_any_user_by_id(
        self, client: TestClient, admin_token_headers, normal_user
    ):
        """
        Admin can fetch any user by ID.

        This validates global visibility for admin support workflows.
        """
        response = client.get(
            f"/api/v1/admin/users/{normal_user.user_id}",
            headers=admin_token_headers
        )
        assert response.status_code == 200
        assert response.json()["user_id"] == normal_user.user_id

    def test_admin_get_nonexistent_user_returns_404(
        self, client: TestClient, admin_token_headers
    ):
        """
        Nonexistent user IDs must return 404.

        This prevents silent failures or misleading success responses.
        """
        response = client.get(
            "/api/v1/admin/users/999999",
            headers=admin_token_headers
        )
        assert response.status_code == 404

    def test_admin_get_user_non_admin_returns_403(
        self, client: TestClient, normal_user_token_headers, normal_user
    ):
        """
        Non-admins must not access admin user lookups.

        This prevents privilege escalation via targeted user reads.
        """
        response = client.get(
            f"/api/v1/admin/users/{normal_user.user_id}",
            headers=normal_user_token_headers
        )
        assert response.status_code == 403

    def test_admin_get_user_unauthenticated_returns_401(
        self, client: TestClient, normal_user
    ):
        """
        Unauthenticated requests must be rejected.

        This enforces authentication on admin endpoints.
        """
        response = client.get(f"/api/v1/admin/users/{normal_user.user_id}")
        assert response.status_code == 401


class TestAdminUpdateUser:
    def test_admin_updates_user_and_sets_updated_by(
        self, client: TestClient, admin_token_headers, normal_user, db
    ):
        """
        Admin can update any user and audit is captured.

        This ensures admin actions leave a traceable audit trail.
        """
        response = client.put(
            f"/api/v1/admin/users/{normal_user.user_id}",
            headers=admin_token_headers,
            json={"first_name": "UpdatedByAdmin"}
        )
        assert response.status_code == 200
        db.refresh(normal_user)
        assert normal_user.first_name == "UpdatedByAdmin"
        assert normal_user.updated_by is not None

    def test_admin_update_nonexistent_user_returns_404(
        self, client: TestClient, admin_token_headers
    ):
        """
        Updating a nonexistent user must 404.

        This prevents ghost updates that appear successful.
        """
        response = client.put(
            "/api/v1/admin/users/999999",
            headers=admin_token_headers,
            json={"first_name": "Nope"}
        )
        assert response.status_code == 404

    def test_admin_update_non_admin_returns_403(
        self, client: TestClient, normal_user_token_headers, normal_user
    ):
        """
        Non-admins must not update users via admin endpoints.

        This blocks privilege escalation.
        """
        response = client.put(
            f"/api/v1/admin/users/{normal_user.user_id}",
            headers=normal_user_token_headers,
            json={"first_name": "Nope"}
        )
        assert response.status_code == 403

    def test_admin_update_unauthenticated_returns_401(
        self, client: TestClient, normal_user
    ):
        """
        Unauthenticated requests must be rejected.

        This enforces authentication on admin endpoints.
        """
        response = client.put(
            f"/api/v1/admin/users/{normal_user.user_id}",
            json={"first_name": "Nope"}
        )
        assert response.status_code == 401


class TestAdminAgencyApplications:
    def test_admin_lists_agencies_with_status_filter(
        self, client: TestClient, admin_token_headers, db
    ):
        from app.models.agencies import Agency

        pending_agency = Agency(
            name=f"Pending Agency {uuid.uuid4().hex[:6]}",
            status="pending",
            owner_email=f"pending_owner_{uuid.uuid4().hex[:6]}@example.com",
            owner_name="Pending Owner",
        )
        db.add(pending_agency)
        db.flush()
        db.refresh(pending_agency)

        response = client.get(
            "/api/v1/admin/agencies/",
            params={"status": "pending"},
            headers=admin_token_headers,
        )

        assert response.status_code == 200
        assert any(item["agency_id"] == pending_agency.agency_id for item in response.json())
        assert all(item["status"] == "pending" for item in response.json())

    def test_admin_approves_agency_and_promotes_owner(
        self, client: TestClient, admin_token_headers, normal_user, db
    ):
        from app.models.agencies import Agency

        pending_agency = Agency(
            name=f"Approval Agency {uuid.uuid4().hex[:6]}",
            status="pending",
            owner_email=normal_user.email,
            owner_name="Owner Name",
        )
        db.add(pending_agency)
        db.flush()
        db.refresh(pending_agency)

        with patch("app.api.endpoints.admin.sync_supabase_auth_user_metadata") as mock_sync:
            response = client.patch(
                f"/api/v1/admin/agencies/{pending_agency.agency_id}/approve/",
                headers=admin_token_headers,
            )

        assert response.status_code == 200
        assert response.json()["status"] == "approved"
        db.refresh(normal_user)
        assert getattr(normal_user.user_role, "value", normal_user.user_role) == "agency_owner"
        assert normal_user.agency_id == pending_agency.agency_id
        mock_sync.assert_called_once()

    def test_admin_rejects_agency_with_reason(
        self, client: TestClient, admin_token_headers, db
    ):
        from app.models.agencies import Agency

        pending_agency = Agency(
            name=f"Rejected Agency {uuid.uuid4().hex[:6]}",
            status="pending",
            owner_email=f"reject_owner_{uuid.uuid4().hex[:6]}@example.com",
            owner_name="Reject Owner",
        )
        db.add(pending_agency)
        db.flush()
        db.refresh(pending_agency)

        response = client.patch(
            f"/api/v1/admin/agencies/{pending_agency.agency_id}/reject/",
            headers=admin_token_headers,
            json={"reason": "Incomplete documentation"},
        )

        assert response.status_code == 200
        assert response.json()["status"] == "rejected"
        assert response.json()["rejection_reason"] == "Incomplete documentation"

    def test_admin_revokes_approved_agency(
        self, client: TestClient, admin_token_headers, agency
    ):
        response = client.patch(
            f"/api/v1/admin/agencies/{agency.agency_id}/revoke/",
            headers=admin_token_headers,
        )

        assert response.status_code == 200
        assert response.json()["status"] == "pending"
        assert response.json()["is_verified"] is False

    def test_admin_suspends_agency(
        self, client: TestClient, admin_token_headers, agency
    ):
        response = client.patch(
            f"/api/v1/admin/agencies/{agency.agency_id}/suspend/",
            headers=admin_token_headers,
        )

        assert response.status_code == 200
        assert response.json()["status"] == "suspended"
        assert response.json()["is_verified"] is False

    def test_admin_role_promotion_syncs_supabase_auth_metadata(
        self, client: TestClient, admin_token_headers, normal_user, db
    ):
        """
        Role promotions must update both the local user row and Supabase Auth.
        """
        with patch(
            "app.api.endpoints.admin.sync_supabase_auth_user_metadata"
        ) as mock_sync:
            response = client.put(
                f"/api/v1/admin/users/{normal_user.user_id}",
                headers=admin_token_headers,
                json={"user_role": "agent"}
            )

        assert response.status_code == 200
        db.refresh(normal_user)
        assert getattr(normal_user.user_role, "value", normal_user.user_role) == "agent"
        mock_sync.assert_called_once()
        synced_user = mock_sync.call_args.args[0]
        assert synced_user.user_id == normal_user.user_id

    def test_admin_role_promotion_rolls_back_when_supabase_sync_fails(
        self, client: TestClient, admin_token_headers, normal_user
    ):
        """
        A DB-only promotion is not allowed; failed auth sync must roll back.
        """
        with patch(
            "app.api.endpoints.admin.sync_supabase_auth_user_metadata",
            side_effect=admin_api.SupabaseUserSyncError("User has no linked Supabase Auth identity to sync."),
        ):
            response = client.put(
                f"/api/v1/admin/users/{normal_user.user_id}",
                headers=admin_token_headers,
                json={"user_role": "agent"}
        )

        assert response.status_code == 502
        assert "no linked Supabase Auth identity" in response.json()["detail"]


class TestAdminDeleteUser:
    def test_admin_soft_deletes_user(
        self, client: TestClient, admin_token_headers, normal_user, db
    ):
        """
        Admin can soft-delete any user with audit trail.

        This ensures deletions are reversible and traceable.
        """
        response = client.delete(
            f"/api/v1/admin/users/{normal_user.user_id}",
            headers=admin_token_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["deleted_at"] is not None
        assert data["deleted_by"] is not None
        db.refresh(normal_user)
        assert normal_user.deleted_at is not None

    def test_admin_delete_nonexistent_user_returns_404(
        self, client: TestClient, admin_token_headers
    ):
        """
        Deleting a nonexistent user must 404.

        This avoids false positives on destructive actions.
        """
        response = client.delete(
            "/api/v1/admin/users/999999",
            headers=admin_token_headers
        )
        assert response.status_code == 404

    def test_admin_delete_non_admin_returns_403(
        self, client: TestClient, normal_user_token_headers, normal_user
    ):
        """
        Non-admins must not delete users.

        This protects accounts from unauthorized deletion.
        """
        response = client.delete(
            f"/api/v1/admin/users/{normal_user.user_id}",
            headers=normal_user_token_headers
        )
        assert response.status_code == 403

    def test_admin_delete_unauthenticated_returns_401(
        self, client: TestClient, normal_user
    ):
        """
        Unauthenticated requests must be rejected.

        This enforces authentication on admin endpoints.
        """
        response = client.delete(f"/api/v1/admin/users/{normal_user.user_id}")
        assert response.status_code == 401

    def test_admin_cannot_delete_self(
        self, client: TestClient, admin_token_headers, admin_user
    ):
        """
        Admins must not delete their own account.

        This prevents accidental lockout of admin access.
        """
        response = client.delete(
            f"/api/v1/admin/users/{admin_user.user_id}",
            headers=admin_token_headers
        )
        assert response.status_code == 400
        assert "cannot delete themselves" in response.json()["detail"]


class TestAdminActivateUser:
    def test_admin_can_activate_user(
        self, client: TestClient, admin_token_headers, normal_user, db
    ):
        """
        Admin can reactivate a soft-deleted user.

        This validates restore behavior for account recovery.
        """
        user_crud.soft_delete(
            db,
            user_id=normal_user.user_id,
            deleted_by_supabase_id=normal_user.supabase_id
        )
        response = client.post(
            f"/api/v1/admin/users/{normal_user.user_id}/activate",
            headers=admin_token_headers
        )
        assert response.status_code == 200
        db.refresh(normal_user)
        assert normal_user.deleted_at is None

    def test_admin_activate_nonexistent_user_returns_404(
        self, client: TestClient, admin_token_headers
    ):
        """
        Activating a nonexistent user must 404.

        This avoids false positives on recovery actions.
        """
        response = client.post(
            "/api/v1/admin/users/999999/activate",
            headers=admin_token_headers
        )
        assert response.status_code == 404

    def test_admin_activate_non_admin_returns_403(
        self, client: TestClient, normal_user_token_headers, normal_user
    ):
        """
        Non-admins must not activate users.

        This prevents privilege escalation via restore operations.
        """
        response = client.post(
            f"/api/v1/admin/users/{normal_user.user_id}/activate",
            headers=normal_user_token_headers
        )
        assert response.status_code == 403

    def test_admin_activate_unauthenticated_returns_401(
        self, client: TestClient, normal_user
    ):
        """
        Unauthenticated requests must be rejected.

        This enforces authentication on admin endpoints.
        """
        response = client.post(f"/api/v1/admin/users/{normal_user.user_id}/activate")
        assert response.status_code == 401


class TestAdminDeactivateUser:
    def test_admin_can_deactivate_user(
        self, client: TestClient, admin_token_headers, normal_user, db
    ):
        """
        Admin can deactivate a user and set audit fields.

        This ensures deactivation is traceable and persisted.
        """
        response = client.post(
            f"/api/v1/admin/users/{normal_user.user_id}/deactivate",
            headers=admin_token_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["deleted_at"] is not None
        assert data["deleted_by"] is not None
        db.refresh(normal_user)
        assert normal_user.deleted_at is not None

    def test_admin_deactivate_nonexistent_user_returns_404(
        self, client: TestClient, admin_token_headers
    ):
        """
        Deactivating a nonexistent user must 404.

        This avoids false positives on account disable actions.
        """
        response = client.post(
            "/api/v1/admin/users/999999/deactivate",
            headers=admin_token_headers
        )
        assert response.status_code == 404

    def test_admin_deactivate_non_admin_returns_403(
        self, client: TestClient, normal_user_token_headers, normal_user
    ):
        """
        Non-admins must not deactivate users.

        This prevents unauthorized account disables.
        """
        response = client.post(
            f"/api/v1/admin/users/{normal_user.user_id}/deactivate",
            headers=normal_user_token_headers
        )
        assert response.status_code == 403

    def test_admin_deactivate_unauthenticated_returns_401(
        self, client: TestClient, normal_user
    ):
        """
        Unauthenticated requests must be rejected.

        This enforces authentication on admin endpoints.
        """
        response = client.post(f"/api/v1/admin/users/{normal_user.user_id}/deactivate")
        assert response.status_code == 401

    def test_admin_cannot_deactivate_self(
        self, client: TestClient, admin_token_headers, admin_user
    ):
        """
        Admins must not deactivate themselves.

        This prevents self-lockout of admin privileges.
        """
        response = client.post(
            f"/api/v1/admin/users/{admin_user.user_id}/deactivate",
            headers=admin_token_headers
        )
        assert response.status_code == 400
        assert "cannot deactivate themselves" in response.json()["detail"]


class TestAdminGetProperties:
    def test_property_serializer_drops_geom_from_json_payload(
        self, db, normal_user, location, property_type
    ):
        """
        The admin property list must stay JSON-safe even when geom is present.

        Production stores PostGIS geometry as a WKBElement. This test mirrors
        that shape directly so we do not regress back to the `WKBElement`
        serialization crash on the admin moderation screen.
        """
        property_obj = Property(
            title="Admin Geometry Property",
            description="Property used to prove admin serialization ignores geom.",
            user_id=normal_user.user_id,
            property_type_id=property_type.property_type_id,
            location_id=location.location_id,
            geom=WKTElement("POINT(3.3488 6.6018)", srid=4326),
            price=21000000,
            bedrooms=3,
            bathrooms=2,
            property_size=110.0,
            listing_type=ListingType.sale,
            listing_status=ListingStatus.available,
            is_verified=False,
        )
        db.add(property_obj)
        db.flush()
        db.refresh(property_obj)

        serialized = admin_api._serialize_property_item(property_obj)

        assert serialized["property_id"] == property_obj.property_id
        assert "geom" not in serialized
        assert "location" not in serialized

    def test_admin_can_list_all_properties(
        self, client: TestClient, admin_token_headers,
        db, normal_user, location, property_type, agency
    ):
        """
        Admin can list all properties regardless of ownership.

        This validates system-wide visibility for moderation.
        """
        _create_property(
            db, normal_user.user_id, location, property_type, agency, "Admin List Property"
        )
        response = client.get("/api/v1/admin/properties", headers=admin_token_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data["items"], list)
        assert data["total"] >= 1
        assert "geom" not in data["items"][0]

    def test_admin_list_properties_non_admin_returns_403(
        self, client: TestClient, normal_user_token_headers
    ):
        """
        Non-admins must not list all properties via admin endpoints.

        This prevents unauthorized access to full inventories.
        """
        response = client.get(
            "/api/v1/admin/properties",
            headers=normal_user_token_headers
        )
        assert response.status_code == 403

    def test_admin_list_properties_unauthenticated_returns_401(
        self, client: TestClient
    ):
        """
        Unauthenticated requests must be rejected.

        This enforces authentication on admin endpoints.
        """
        response = client.get("/api/v1/admin/properties")
        assert response.status_code == 401


class TestAdminDeleteProperty:
    def test_admin_soft_deletes_any_property(
        self, client: TestClient, admin_token_headers,
        db, normal_user, location, property_type, agency
    ):
        """
        Admin can delete any property, regardless of ownership.

        This validates admin override and audit persistence.
        """
        prop = _create_property(
            db, normal_user.user_id, location, property_type, agency, "Admin Delete Property"
        )
        response = client.delete(
            f"/api/v1/admin/properties/{prop.property_id}",
            headers=admin_token_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["deleted_at"] is not None
        assert data["deleted_by"] is not None
        db.refresh(prop)
        assert prop.deleted_at is not None

    def test_admin_delete_nonexistent_property_returns_404(
        self, client: TestClient, admin_token_headers
    ):
        """
        Deleting a nonexistent property must 404.

        This avoids silent failures on destructive actions.
        """
        response = client.delete(
            "/api/v1/admin/properties/999999",
            headers=admin_token_headers
        )
        assert response.status_code == 404

    def test_admin_delete_property_non_admin_returns_403(
        self, client: TestClient, normal_user_token_headers
    ):
        """
        Non-admins must not delete properties via admin endpoints.

        This prevents privilege escalation.
        """
        response = client.delete(
            "/api/v1/admin/properties/999999",
            headers=normal_user_token_headers
        )
        assert response.status_code == 403

    def test_admin_delete_property_unauthenticated_returns_401(
        self, client: TestClient
    ):
        """
        Unauthenticated requests must be rejected.

        This enforces authentication on admin endpoints.
        """
        response = client.delete("/api/v1/admin/properties/999999")
        assert response.status_code == 401


class TestAdminVerifyProperty:
    def test_admin_verifies_property_sets_flag(
        self, client: TestClient, admin_token_headers,
        db, normal_user, location, property_type, agency
    ):
        """
        Admin can verify a property and set is_verified.

        This ensures verification is persisted and audited.
        """
        prop = _create_property(
            db, normal_user.user_id, location, property_type, agency, "Admin Verify Property"
        )
        response = client.post(
            f"/api/v1/admin/properties/{prop.property_id}/verify",
            headers=admin_token_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["is_verified"] is True
        db.refresh(prop)
        assert prop.is_verified is True

        response2 = client.post(
            f"/api/v1/admin/properties/{prop.property_id}/verify",
            headers=admin_token_headers
        )
        assert response2.status_code == 200
        assert response2.json()["is_verified"] is True

    def test_admin_verify_nonexistent_property_returns_404(
        self, client: TestClient, admin_token_headers
    ):
        """
        Verifying a nonexistent property must 404.

        This prevents false positives in moderation workflows.
        """
        response = client.post(
            "/api/v1/admin/properties/999999/verify",
            headers=admin_token_headers
        )
        assert response.status_code == 404

    def test_admin_verify_property_non_admin_returns_403(
        self, client: TestClient, normal_user_token_headers
    ):
        """
        Non-admins must not verify properties.

        This prevents unauthorized listing approvals.
        """
        response = client.post(
            "/api/v1/admin/properties/999999/verify",
            headers=normal_user_token_headers
        )
        assert response.status_code == 403

    def test_admin_verify_property_unauthenticated_returns_401(
        self, client: TestClient
    ):
        """
        Unauthenticated requests must be rejected.

        This enforces authentication on admin endpoints.
        """
        response = client.post("/api/v1/admin/properties/999999/verify")
        assert response.status_code == 401


class TestAdminApproveProperty:
    def test_admin_approves_property_sets_status(
        self, client: TestClient, admin_token_headers,
        db, normal_user, location, property_type, agency
    ):
        """
        Admin can approve a property and set listing_status to active.

        This ensures approval changes listing state in the database.
        """
        prop = _create_property(
            db, normal_user.user_id, location, property_type, agency, "Admin Approve Property"
        )
        response = client.put(
            f"/api/v1/admin/properties/{prop.property_id}/approve",
            headers=admin_token_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["listing_status"] == "active"
        db.refresh(prop)
        assert prop.listing_status.value == "active"

    def test_admin_approve_nonexistent_property_returns_404(
        self, client: TestClient, admin_token_headers
    ):
        """
        Approving a nonexistent property must 404.

        This avoids false positives on approvals.
        """
        response = client.put(
            "/api/v1/admin/properties/999999/approve",
            headers=admin_token_headers
        )
        assert response.status_code == 404

    def test_admin_approve_property_non_admin_returns_403(
        self, client: TestClient, normal_user_token_headers
    ):
        """
        Non-admins must not approve properties.

        This prevents unauthorized listing activation.
        """
        response = client.put(
            "/api/v1/admin/properties/999999/approve",
            headers=normal_user_token_headers
        )
        assert response.status_code == 403

    def test_admin_approve_property_unauthenticated_returns_401(
        self, client: TestClient
    ):
        """
        Unauthenticated requests must be rejected.

        This enforces authentication on admin endpoints.
        """
        response = client.put("/api/v1/admin/properties/999999/approve")
        assert response.status_code == 401


class TestAdminGetInquiries:
    def test_admin_can_list_inquiries(
        self, client: TestClient, admin_token_headers,
        db, normal_user, location, property_type, agency
    ):
        """
        Admin can list inquiries across all properties.

        This supports moderation and support workflows.
        """
        prop = _create_property(
            db, normal_user.user_id, location, property_type, agency, "Admin Inquiry Property"
        )
        inquiry_crud.create(
            db,
            obj_in=InquiryCreate(property_id=prop.property_id, message="Test inquiry"),
            user_id=normal_user.user_id
        )
        response = client.get("/api/v1/admin/inquiries", headers=admin_token_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data["items"], list)
        assert data["total"] >= 1

    def test_admin_list_inquiries_non_admin_returns_403(
        self, client: TestClient, normal_user_token_headers
    ):
        """
        Non-admins must not list inquiries via admin endpoints.

        This prevents unauthorized access to private messages.
        """
        response = client.get(
            "/api/v1/admin/inquiries",
            headers=normal_user_token_headers
        )
        assert response.status_code == 403

    def test_admin_list_inquiries_unauthenticated_returns_401(
        self, client: TestClient
    ):
        """
        Unauthenticated requests must be rejected.

        This enforces authentication on admin endpoints.
        """
        response = client.get("/api/v1/admin/inquiries")
        assert response.status_code == 401


class TestAdminGetStats:
    def test_admin_gets_system_stats(
        self, client: TestClient, admin_token_headers
    ):
        """
        Admin can retrieve system-wide stats.

        This enables platform monitoring and dashboards.
        """
        response = client.get("/api/v1/admin/stats", headers=admin_token_headers)
        assert response.status_code == 200
        data = response.json()
        assert "users" in data
        assert "properties" in data
        assert "inquiries" in data

    def test_admin_stats_non_admin_returns_403(
        self, client: TestClient, normal_user_token_headers
    ):
        """
        Non-admins must not access system stats.

        This protects sensitive platform metrics.
        """
        response = client.get("/api/v1/admin/stats", headers=normal_user_token_headers)
        assert response.status_code == 403

    def test_admin_stats_unauthenticated_returns_401(
        self, client: TestClient
    ):
        """
        Unauthenticated requests must be rejected.

        This enforces authentication on admin endpoints.
        """
        response = client.get("/api/v1/admin/stats")
        assert response.status_code == 401


class TestAdminGetStatsOverview:
    def test_admin_gets_stats_overview(
        self, client: TestClient, admin_token_headers
    ):
        """
        Admin can retrieve overview stats.

        This validates the aggregate counts are accessible to admins.
        """
        response = client.get(
            "/api/v1/admin/stats/overview",
            headers=admin_token_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "total_users" in data
        assert "total_properties" in data
        assert "approved_properties" in data
        assert "pending_properties" in data

    def test_admin_stats_overview_non_admin_returns_403(
        self, client: TestClient, normal_user_token_headers
    ):
        """
        Non-admins must not access overview stats.

        This protects sensitive platform metrics.
        """
        response = client.get(
            "/api/v1/admin/stats/overview",
            headers=normal_user_token_headers
        )
        assert response.status_code == 403

    def test_admin_stats_overview_unauthenticated_returns_401(
        self, client: TestClient
    ):
        """
        Unauthenticated requests must be rejected.

        This enforces authentication on admin endpoints.
        """
        response = client.get("/api/v1/admin/stats/overview")
        assert response.status_code == 401

    def test_admin_stats_overview_handles_exception(
        self, client: TestClient, admin_token_headers, monkeypatch
    ):
        """
        Stats overview should return 500 on unexpected errors.

        This verifies the exception handler branch.
        """
        def boom(*args, **kwargs):
            raise Exception("boom")

        monkeypatch.setattr(admin_api.property_crud, "count_pending", boom)
        response = client.get(
            "/api/v1/admin/stats/overview",
            headers=admin_token_headers
        )
        assert response.status_code == 500
        assert "Unable to generate statistics" in response.json()["detail"]


class TestAdminBootstrapDemoData:
    def test_admin_bootstrap_demo_data_creates_minimum_chain(
        self, client: TestClient, admin_token_headers, agent_user, db
    ):
        response = client.post(
            "/api/v1/admin/bootstrap/demo-data",
            headers=admin_token_headers,
            json={"agent_user_id": agent_user.user_id}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["agent_user_id"] == agent_user.user_id
        assert data["location_id"] is not None
        assert data["property_type_id"] is not None
        assert data["agency_id"] is not None
        assert data["agent_profile_id"] is not None
        assert data["property_id"] is not None
        assert data["verified_property_id"] is not None
        assert data["pending_property_id"] is not None

        profile = admin_api.agent_profile_crud.get_by_user_id(db, user_id=agent_user.user_id)
        assert profile is not None
        assert profile.user_id == agent_user.user_id
        assert admin_api.property_crud.count(db, user_id=agent_user.user_id) >= 2

        verified_prop = admin_api.property_crud.get(db, property_id=data["verified_property_id"])
        assert verified_prop is not None
        assert verified_prop.is_verified is True
        assert str(getattr(verified_prop.listing_status, "value", verified_prop.listing_status)) == "available"

        pending_prop = admin_api.property_crud.get(db, property_id=data["pending_property_id"])
        assert pending_prop is not None
        assert pending_prop.is_verified is False

        public_props = admin_api.property_crud.get_multi_by_params_approved(db, skip=0, limit=100)
        assert any(p.property_id == data["verified_property_id"] for p in public_props)
        assert all(p.property_id != data["pending_property_id"] for p in public_props)
