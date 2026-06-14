"""Tests for N.4 notification email wiring."""
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone

from app.models.properties import Property, ListingType, ListingStatus, ModerationStatus
from app.models.listing_events import ListingEvent
from app.models.listing_instructions import ListingInstruction
from app.models.users import User, UserRole
from app.tasks.email_tasks import (
    send_submission_notification_email,
    send_agency_approval_notification_email,
    send_instruction_notification_email,
    dispatch_email_task,
)


def _make_property(db, user, agency, location, property_type, status=ModerationStatus.draft):
    from geoalchemy2.elements import WKTElement
    prop = Property(
        title="N.4 Notification Test Property",
        description="Test listing for notification wiring",
        user_id=user.user_id,
        agency_id=agency.agency_id,
        property_type_id=property_type.property_type_id,
        location_id=location.location_id,
        geom=WKTElement("POINT(3.3488 6.6018)", srid=4326),
        price=50000000,
        bedrooms=3,
        bathrooms=2,
        property_size=120.0,
        listing_type=ListingType.sale,
        listing_status=ListingStatus.available,
        moderation_status=status,
    )
    db.add(prop)
    db.flush()
    db.refresh(prop)
    return prop


def _write_event(db, property_obj, actor_id, from_status, to_status, reason=None):
    event = ListingEvent(
        listing_id=property_obj.property_id,
        actor_id=actor_id,
        from_status=from_status,
        to_status=to_status,
        reason=reason,
    )
    db.add(event)
    db.flush()
    db.refresh(event)
    return event


# ===========================================================================
# Submission notification on PATCH /submit-for-review/
# ===========================================================================

class TestSubmissionNotification:
    """dispatch_email_task fires submission_notification to agency owner."""

    def test_submission_fires_email_to_agency_owner(
        self, client, db, agent_user, agent_token_headers,
        agency_owner_user, agency, location, property_type,
    ):
        """Agency owner receives email when agent submits for review."""
        prop = _make_property(db, agent_user, agency, location, property_type, ModerationStatus.draft)

        with patch("app.api.endpoints.properties.dispatch_email_task") as mock_dispatch:
            response = client.patch(
                f"/api/v1/properties/{prop.property_id}/submit-for-review",
                headers=agent_token_headers,
            )
            assert response.status_code == 200

            mock_dispatch.assert_called_once()
            args = mock_dispatch.call_args[0]
            task_fn = args[0]
            assert task_fn.__name__ == "send_submission_notification_email"
            assert args[1] == agency_owner_user.email  # to_email
            assert "agent" in args[2].lower()  # agent_name
            assert "N.4 Notification" in args[3]  # property_title
            assert isinstance(args[4], int)  # property_id
            assert "UTC" in args[5]  # submission_timestamp

    def test_submission_no_agency_still_succeeds(
        self, client, db, agent_user, agent_token_headers,
        location, property_type,
    ):
        """Submission succeeds when listing has no agency."""
        from geoalchemy2.elements import WKTElement
        prop = Property(
            title="No Agency Listing",
            description="Test",
            user_id=agent_user.user_id,
            agency_id=None,
            property_type_id=property_type.property_type_id,
            location_id=location.location_id,
            geom=WKTElement("POINT(3.3488 6.6018)", srid=4326),
            price=50000000, bedrooms=3, bathrooms=2, property_size=120.0,
            listing_type=ListingType.sale, listing_status=ListingStatus.available,
            moderation_status=ModerationStatus.draft,
        )
        db.add(prop); db.flush(); db.refresh(prop)

        with patch("app.api.endpoints.properties.dispatch_email_task") as mock_dispatch:
            response = client.patch(
                f"/api/v1/properties/{prop.property_id}/submit-for-review",
                headers=agent_token_headers,
            )
            assert response.status_code == 200
            mock_dispatch.assert_not_called()


# ===========================================================================
# Agency approval notification on PATCH /agency-approve/
# ===========================================================================

class TestAgencyApprovalNotification:
    """dispatch_email_task fires agency_approval_notification to admin."""

    def test_agency_approval_fires_email_to_admin(
        self, client, db, agent_user, agency_owner_user,
        agency_owner_token_headers, admin_user, agency, location, property_type,
    ):
        """Admin receives email when agency owner approves listing."""
        prop = _make_property(db, agent_user, agency, location, property_type, ModerationStatus.agency_review)
        _write_event(db, prop, agent_user.user_id, "draft", "agency_review")

        with patch("app.api.endpoints.properties.dispatch_email_task") as mock_dispatch:
            response = client.patch(
                f"/api/v1/properties/{prop.property_id}/agency-approve",
                headers=agency_owner_token_headers,
            )
            assert response.status_code == 200

            mock_dispatch.assert_called_once()
            args = mock_dispatch.call_args[0]
            task_fn = args[0]
            assert task_fn.__name__ == "send_agency_approval_notification_email"
            assert args[1] == admin_user.email  # to_email = admin
            assert "N.4 Notification" in args[3]  # property_title


# ===========================================================================
# Instruction notification on POST /instruct/
# ===========================================================================

class TestInstructionNotification:
    """dispatch_email_task fires instruction_notification to listing agent."""

    def test_instruction_fires_email_to_agent(
        self, client, db, agent_user, agency_owner_user,
        agency_owner_token_headers, agency, location, property_type,
    ):
        """Agent receives email when agency owner writes instruction."""
        prop = _make_property(db, agent_user, agency, location, property_type, ModerationStatus.revoked)
        _write_event(db, prop, agent_user.user_id, "live", "revoked", reason="Violation")

        with patch("app.api.endpoints.properties.dispatch_email_task") as mock_dispatch:
            response = client.patch(
                f"/api/v1/properties/{prop.property_id}/instruct",
                json={"instruction_text": "Edit and resubmit with corrections"},
                headers=agency_owner_token_headers,
            )
            assert response.status_code == 200

            mock_dispatch.assert_called_once()
            args = mock_dispatch.call_args[0]
            task_fn = args[0]
            assert task_fn.__name__ == "send_instruction_notification_email"
            assert args[1] == agent_user.email  # to_email = agent
            assert "N.4 Notification" in args[3]  # property_title
            assert "Edit and resubmit" in args[4]  # instruction_text


# ===========================================================================
# Phase M email wires still intact
# ===========================================================================

class TestPhaseMEmailWires:
    """Existing Phase M email notifications still fire."""

    def test_agency_reject_still_fires_to_agent(
        self, client, db, agent_user, agency_owner_user,
        agency_owner_token_headers, agency, location, property_type,
    ):
        """agency_rejected transition still sends email to agent."""
        prop = _make_property(db, agent_user, agency, location, property_type, ModerationStatus.agency_review)
        _write_event(db, prop, agent_user.user_id, "draft", "agency_review")

        with patch("app.api.endpoints.properties.dispatch_email_task") as mock_dispatch:
            response = client.patch(
                f"/api/v1/properties/{prop.property_id}/agency-reject",
                json={"moderation_reason": "Needs more photos"},
                headers=agency_owner_token_headers,
            )
            assert response.status_code == 200
            mock_dispatch.assert_called_once()
            args = mock_dispatch.call_args[0]
            assert args[1] == agent_user.email

    def test_admin_verify_fires_to_agent(
        self, client, db, agent_user, admin_user,
        admin_token_headers, agency, location, property_type,
    ):
        """admin approve (verify) still sends email to agent."""
        from geoalchemy2.elements import WKTElement
        prop = Property(
            title="M Wire Test", description="Test",
            user_id=agent_user.user_id, agency_id=agency.agency_id,
            property_type_id=property_type.property_type_id,
            location_id=location.location_id,
            geom=WKTElement("POINT(3.3488 6.6018)", srid=4326),
            price=50000000, bedrooms=3, bathrooms=2, property_size=120.0,
            listing_type=ListingType.sale, listing_status=ListingStatus.available,
            moderation_status=ModerationStatus.admin_review, is_verified=False,
        )
        db.add(prop); db.flush(); db.refresh(prop)
        _write_event(db, prop, agent_user.user_id, "agency_review", "admin_review")

        with patch("app.api.endpoints.properties.dispatch_email_task") as mock_dispatch:
            response = client.patch(
                f"/api/v1/properties/{prop.property_id}/verify",
                json={"moderation_reason": "Approved"},
                headers=admin_token_headers,
            )
            assert response.status_code == 200
            mock_dispatch.assert_called()
            # First call should be to agent
            first_call_args = mock_dispatch.call_args_list[0][0]
            assert first_call_args[1] == agent_user.email

    def test_admin_reject_fires_to_agent_and_agency_owner(
        self, client, db, agent_user, agency_owner_user,
        admin_token_headers, agency, location, property_type,
    ):
        """admin_rejected transition sends email to agent AND agency owner."""
        from geoalchemy2.elements import WKTElement
        prop = Property(
            title="M Wire Admin Reject", description="Test",
            user_id=agent_user.user_id, agency_id=agency.agency_id,
            property_type_id=property_type.property_type_id,
            location_id=location.location_id,
            geom=WKTElement("POINT(3.3488 6.6018)", srid=4326),
            price=50000000, bedrooms=3, bathrooms=2, property_size=120.0,
            listing_type=ListingType.sale, listing_status=ListingStatus.available,
            moderation_status=ModerationStatus.admin_review,
        )
        db.add(prop); db.flush(); db.refresh(prop)
        _write_event(db, prop, agent_user.user_id, "agency_review", "admin_review")

        with patch("app.api.endpoints.properties.dispatch_email_task") as mock_dispatch:
            response = client.patch(
                f"/api/v1/properties/{prop.property_id}/admin-reject",
                json={"moderation_reason": "Missing documentation"},
                headers=admin_token_headers,
            )
            assert response.status_code == 200
            # Should be called at least twice: once for agent, once for agency owner
            assert mock_dispatch.call_count >= 2
            recipient_emails = [call[0][1] for call in mock_dispatch.call_args_list]
            assert agent_user.email in recipient_emails
            assert agency_owner_user.email in recipient_emails

    def test_revoke_fires_to_agent_and_agency_owner(
        self, client, db, agent_user, agency_owner_user,
        admin_token_headers, agency, location, property_type,
    ):
        """revoke transition sends email to agent AND agency owner."""
        from geoalchemy2.elements import WKTElement
        prop = Property(
            title="M Wire Revoke", description="Test",
            user_id=agent_user.user_id, agency_id=agency.agency_id,
            property_type_id=property_type.property_type_id,
            location_id=location.location_id,
            geom=WKTElement("POINT(3.3488 6.6018)", srid=4326),
            price=50000000, bedrooms=3, bathrooms=2, property_size=120.0,
            listing_type=ListingType.sale, listing_status=ListingStatus.available,
            moderation_status=ModerationStatus.live, is_verified=True,
        )
        db.add(prop); db.flush(); db.refresh(prop)
        _write_event(db, prop, agent_user.user_id, "admin_review", "live")

        with patch("app.api.endpoints.properties.dispatch_email_task") as mock_dispatch:
            response = client.patch(
                f"/api/v1/properties/{prop.property_id}/revoke",
                json={"moderation_reason": "Policy violation"},
                headers=admin_token_headers,
            )
            assert response.status_code == 200
            assert mock_dispatch.call_count >= 2
            recipient_emails = [call[0][1] for call in mock_dispatch.call_args_list]
            assert agent_user.email in recipient_emails
            assert agency_owner_user.email in recipient_emails


# ===========================================================================
# Smoke tests: task functions dispatch correctly
# ===========================================================================

class TestEmailTaskDispatch:
    """dispatch_email_task correctly routes to the Celery task."""

    def test_dispatch_submission_notification_task(self):
        """send_submission_notification_email can be dispatched."""
        with patch("app.tasks.email_tasks.send_submission_notification_email.apply") as mock_apply:
            mock_apply.return_value = MagicMock(get=lambda **kw: "ok")
            dispatch_email_task(
                send_submission_notification_email,
                "test@example.com",
                "Agent Name",
                "Test Property",
                1,
                "2026-06-14 12:00 UTC",
            )
            mock_apply.assert_called_once()

    def test_dispatch_instruction_notification_task(self):
        """send_instruction_notification_email can be dispatched."""
        with patch("app.tasks.email_tasks.send_instruction_notification_email.apply") as mock_apply:
            mock_apply.return_value = MagicMock(get=lambda **kw: "ok")
            dispatch_email_task(
                send_instruction_notification_email,
                "agent@example.com",
                "Agency Owner",
                "Test Property",
                "Edit and resubmit",
                1,
            )
            mock_apply.assert_called_once()

    def test_dispatch_agency_approval_notification_task(self):
        """send_agency_approval_notification_email can be dispatched."""
        with patch("app.tasks.email_tasks.send_agency_approval_notification_email.apply") as mock_apply:
            mock_apply.return_value = MagicMock(get=lambda **kw: "ok")
            dispatch_email_task(
                send_agency_approval_notification_email,
                "admin@example.com",
                "Test Agency",
                "Test Property",
                1,
            )
            mock_apply.assert_called_once()
