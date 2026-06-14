"""Tests for Phase N N.1 listing_instructions endpoints and mediation gates."""
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from app.models.properties import Property, ListingType, ListingStatus, ModerationStatus
from app.models.listing_events import ListingEvent
from app.models.users import User, UserRole
from app.crud.properties import property as property_crud


def _make_property(db, user, agency, location, property_type, status=ModerationStatus.draft):
    """Helper to create a property and return it."""
    from geoalchemy2.elements import WKTElement
    prop = Property(
        title="Instruction Test Property",
        description="Test listing for instruction mediation",
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
    """Write a listing_events row."""
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
# POST /{property_id}/instruct
# ===========================================================================

class TestInstructEndpoint:
    """Agency owner writes instruction for revoked/admin_rejected listing."""

    def test_instruct_requires_agency_owner_role(
        self, client: TestClient, db, agent_user, agent_token_headers,
        agency, location, property_type,
    ):
        """Agent cannot write instructions — only agency_owner."""
        prop = _make_property(db, agent_user, agency, location, property_type, ModerationStatus.revoked)
        _write_event(db, prop, agent_user.user_id, "live", "revoked", reason="Policy violation")
        response = client.patch(
            f"/api/v1/properties/{prop.property_id}/instruct",
            json={"instruction_text": "Edit and resubmit"},
            headers=agent_token_headers,
        )
        assert response.status_code == 403

    def test_instruct_requires_listings_agency(
        self, client: TestClient, db, agent_user, agency_owner_user,
        agency_owner_token_headers, other_agency, location, property_type,
    ):
        """Agency owner from a different agency cannot instruct."""
        prop = _make_property(db, agent_user, other_agency, location, property_type, ModerationStatus.revoked)
        _write_event(db, prop, agent_user.user_id, "live", "revoked", reason="Policy violation")
        response = client.patch(
            f"/api/v1/properties/{prop.property_id}/instruct",
            json={"instruction_text": "Edit and resubmit"},
            headers=agency_owner_token_headers,
        )
        assert response.status_code == 403

    def test_instruct_only_on_revoked_or_admin_rejected(
        self, client: TestClient, db, agent_user, agency_owner_user,
        agency_owner_token_headers, agency, location, property_type,
    ):
        """422 if listing is not revoked or admin_rejected."""
        prop = _make_property(db, agent_user, agency, location, property_type, ModerationStatus.live)
        response = client.patch(
            f"/api/v1/properties/{prop.property_id}/instruct",
            json={"instruction_text": "Edit and resubmit"},
            headers=agency_owner_token_headers,
        )
        assert response.status_code == 422

    def test_instruct_writes_instruction_and_event(
        self, client: TestClient, db, agent_user, agency_owner_user,
        agency_owner_token_headers, agency, location, property_type,
    ):
        """Happy path: instruction written, listing_events row added."""
        prop = _make_property(db, agent_user, agency, location, property_type, ModerationStatus.revoked)
        event = _write_event(db, prop, agent_user.user_id, "live", "revoked", reason="Policy violation")

        response = client.patch(
            f"/api/v1/properties/{prop.property_id}/instruct",
            json={"instruction_text": "Edit and resubmit with corrections"},
            headers=agency_owner_token_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["has_instruction"] is True
        assert data["instruction_text"] == "Edit and resubmit with corrections"
        assert data["latest_event_reason"] == "Policy violation"

        # Verify instruction row exists in DB
        from app.models.listing_instructions import ListingInstruction
        instruction = db.query(ListingInstruction).filter(
            ListingInstruction.listing_id == prop.property_id
        ).first()
        assert instruction is not None
        assert instruction.instruction_text == "Edit and resubmit with corrections"
        assert instruction.triggered_by_event_id == event.event_id

    def test_instruct_on_admin_rejected(
        self, client: TestClient, db, agent_user, agency_owner_user,
        agency_owner_token_headers, agency, location, property_type,
    ):
        """Instruct works on admin_rejected listings too."""
        prop = _make_property(db, agent_user, agency, location, property_type, ModerationStatus.admin_rejected)
        event = _write_event(db, prop, agent_user.user_id, "admin_review", "admin_rejected", reason="Missing docs")

        response = client.patch(
            f"/api/v1/properties/{prop.property_id}/instruct",
            json={"instruction_text": "Provide the missing documents and resubmit"},
            headers=agency_owner_token_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["has_instruction"] is True
        assert data["instruction_text"] == "Provide the missing documents and resubmit"

    def test_instruct_requires_non_empty_text(
        self, client: TestClient, db, agent_user, agency_owner_user,
        agency_owner_token_headers, agency, location, property_type,
    ):
        """422 for empty instruction text."""
        prop = _make_property(db, agent_user, agency, location, property_type, ModerationStatus.revoked)
        _write_event(db, prop, agent_user.user_id, "live", "revoked", reason="Test")
        response = client.patch(
            f"/api/v1/properties/{prop.property_id}/instruct",
            json={"instruction_text": ""},
            headers=agency_owner_token_headers,
        )
        assert response.status_code == 422

    def test_instruct_404_for_missing_property(
        self, client: TestClient, agency_owner_token_headers,
    ):
        """404 for non-existent property."""
        response = client.patch(
            "/api/v1/properties/99999/instruct",
            json={"instruction_text": "Edit and resubmit"},
            headers=agency_owner_token_headers,
        )
        assert response.status_code == 404

    def test_instruct_not_found_no_rejection_event(
        self, client: TestClient, db, agent_user, agency_owner_user,
        agency_owner_token_headers, agency, location, property_type,
    ):
        """422 if no revocation/rejection event exists."""
        prop = _make_property(db, agent_user, agency, location, property_type, ModerationStatus.revoked)
        # No listing_events row for this listing
        response = client.patch(
            f"/api/v1/properties/{prop.property_id}/instruct",
            json={"instruction_text": "Edit and resubmit"},
            headers=agency_owner_token_headers,
        )
        assert response.status_code == 422


# ===========================================================================
# GET /{property_id}/instructions
# ===========================================================================

class TestGetInstructionsEndpoint:
    """Read instructions for a listing."""

    def test_creator_can_read_instructions(
        self, client: TestClient, db, agent_user, agency_owner_user,
        agent_token_headers, agency, location, property_type,
    ):
        """Listing creator (agent) can read instructions."""
        from app.models.listing_instructions import ListingInstruction
        prop = _make_property(db, agent_user, agency, location, property_type, ModerationStatus.revoked)
        event = _write_event(db, prop, agent_user.user_id, "live", "revoked", reason="Test")
        db.add(ListingInstruction(
            listing_id=prop.property_id,
            agency_id=agency.agency_id,
            actor_id=agency_owner_user.user_id,
            triggered_by_event_id=event.event_id,
            instruction_text="Fix the listing",
        ))
        db.flush()

        response = client.get(
            f"/api/v1/properties/{prop.property_id}/instructions",
            headers=agent_token_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["instruction_text"] == "Fix the listing"

    def test_agency_owner_can_read_instructions(
        self, client: TestClient, db, agent_user, agency_owner_user,
        agency_owner_token_headers, agency, location, property_type,
    ):
        """Agency owner can read instructions for their agency's listings."""
        from app.models.listing_instructions import ListingInstruction
        prop = _make_property(db, agent_user, agency, location, property_type, ModerationStatus.revoked)
        event = _write_event(db, prop, agent_user.user_id, "live", "revoked", reason="Test")
        db.add(ListingInstruction(
            listing_id=prop.property_id,
            agency_id=agency.agency_id,
            actor_id=agency_owner_user.user_id,
            triggered_by_event_id=event.event_id,
            instruction_text="Fix the listing",
        ))
        db.flush()

        response = client.get(
            f"/api/v1/properties/{prop.property_id}/instructions",
            headers=agency_owner_token_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1

    def test_admin_can_read_any_instructions(
        self, client: TestClient, db, agent_user, agency_owner_user,
        admin_token_headers, agency, location, property_type,
    ):
        """Admin can read instructions for any listing."""
        from app.models.listing_instructions import ListingInstruction
        prop = _make_property(db, agent_user, agency, location, property_type, ModerationStatus.revoked)
        event = _write_event(db, prop, agent_user.user_id, "live", "revoked", reason="Test")
        db.add(ListingInstruction(
            listing_id=prop.property_id,
            agency_id=agency.agency_id,
            actor_id=agency_owner_user.user_id,
            triggered_by_event_id=event.event_id,
            instruction_text="Admin view test",
        ))
        db.flush()

        response = client.get(
            f"/api/v1/properties/{prop.property_id}/instructions",
            headers=admin_token_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1

    def test_non_creator_cannot_read_instructions(
        self, client: TestClient, db, agent_user, agency_owner_user,
        normal_user, normal_user_token_headers, agency, location, property_type,
    ):
        """A seeker (non-creator) cannot read instructions for another agent's listing."""
        from app.models.listing_instructions import ListingInstruction
        prop = _make_property(db, agent_user, agency, location, property_type, ModerationStatus.revoked)
        event = _write_event(db, prop, agent_user.user_id, "live", "revoked", reason="Test")
        db.add(ListingInstruction(
            listing_id=prop.property_id,
            agency_id=agency.agency_id,
            actor_id=agency_owner_user.user_id,
            triggered_by_event_id=event.event_id,
            instruction_text="Fix the listing",
        ))
        db.flush()

        response = client.get(
            f"/api/v1/properties/{prop.property_id}/instructions",
            headers=normal_user_token_headers,
        )
        assert response.status_code == 403

    def test_instructions_returned_ordered(
        self, client: TestClient, db, agent_user, agency_owner_user,
        agent_token_headers, agency, location, property_type,
    ):
        """Multiple instructions returned in created_at ascending order."""
        from app.models.listing_instructions import ListingInstruction
        from datetime import datetime, timezone, timedelta
        prop = _make_property(db, agent_user, agency, location, property_type, ModerationStatus.revoked)
        event = _write_event(db, prop, agent_user.user_id, "live", "revoked", reason="Test")

        inst1 = ListingInstruction(
            listing_id=prop.property_id, agency_id=agency.agency_id,
            actor_id=agency_owner_user.user_id, triggered_by_event_id=event.event_id,
            instruction_text="First instruction",
        )
        db.add(inst1)
        db.flush()

        inst2 = ListingInstruction(
            listing_id=prop.property_id, agency_id=agency.agency_id,
            actor_id=agency_owner_user.user_id, triggered_by_event_id=event.event_id,
            instruction_text="Second instruction",
        )
        db.add(inst2)
        db.flush()

        response = client.get(
            f"/api/v1/properties/{prop.property_id}/instructions",
            headers=agent_token_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["instruction_text"] == "First instruction"
        assert data[1]["instruction_text"] == "Second instruction"


# ===========================================================================
# Instruction Gating on Edit
# ===========================================================================

class TestEditGate:
    """PUT /{property_id} enforces instruction gate on revoked/admin_rejected."""

    def test_edit_revoked_without_instruction_returns_422(
        self, client: TestClient, db, agent_user, agent_token_headers,
        agency, location, property_type,
    ):
        """Agent cannot edit a revoked listing without an instruction."""
        prop = _make_property(db, agent_user, agency, location, property_type, ModerationStatus.revoked)
        _write_event(db, prop, agent_user.user_id, "live", "revoked", reason="Policy violation")

        response = client.put(
            f"/api/v1/properties/{prop.property_id}",
            json={"title": "Edited Title"},
            headers=agent_token_headers,
        )
        assert response.status_code == 422
        assert "await agency instruction" in response.json()["detail"].lower()

    def test_edit_revoked_with_instruction_proceeds(
        self, client: TestClient, db, agent_user, agency_owner_user,
        agent_token_headers, agency, location, property_type,
    ):
        """Agent can edit a revoked listing after instruction is written."""
        from app.models.listing_instructions import ListingInstruction
        prop = _make_property(db, agent_user, agency, location, property_type, ModerationStatus.revoked)
        event = _write_event(db, prop, agent_user.user_id, "live", "revoked", reason="Policy violation")
        db.add(ListingInstruction(
            listing_id=prop.property_id, agency_id=agency.agency_id,
            actor_id=agency_owner_user.user_id, triggered_by_event_id=event.event_id,
            instruction_text="Edit and resubmit",
        ))
        db.flush()

        response = client.put(
            f"/api/v1/properties/{prop.property_id}",
            json={"title": "Edited After Instruction"},
            headers=agent_token_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "Edited After Instruction"

    def test_edit_admin_rejected_without_instruction_returns_422(
        self, client: TestClient, db, agent_user, agent_token_headers,
        agency, location, property_type,
    ):
        """Agent cannot edit an admin_rejected listing without an instruction."""
        prop = _make_property(db, agent_user, agency, location, property_type, ModerationStatus.admin_rejected)
        _write_event(db, prop, agent_user.user_id, "admin_review", "admin_rejected", reason="Missing docs")

        response = client.put(
            f"/api/v1/properties/{prop.property_id}",
            json={"title": "Edited Title"},
            headers=agent_token_headers,
        )
        assert response.status_code == 422
        assert "await agency instruction" in response.json()["detail"].lower()

    def test_edit_live_listing_not_blocked(
        self, client: TestClient, db, agent_user, agent_token_headers,
        agency, location, property_type,
    ):
        """Edit on a live listing is not blocked by instruction gate."""
        prop = _make_property(db, agent_user, agency, location, property_type, ModerationStatus.live)

        response = client.put(
            f"/api/v1/properties/{prop.property_id}",
            json={"title": "Edited Live Title"},
            headers=agent_token_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "Edited Live Title"


# ===========================================================================
# Instruction Gating on Pull-back
# ===========================================================================

class TestPullBackGate:
    """PATCH /{property_id}/pull-back enforces instruction gate."""

    def test_pull_back_revoked_without_instruction_returns_422(
        self, client: TestClient, db, agent_user, agent_token_headers,
        agency, location, property_type,
    ):
        """Agent cannot pull back a revoked listing without instruction."""
        prop = _make_property(db, agent_user, agency, location, property_type, ModerationStatus.revoked)
        _write_event(db, prop, agent_user.user_id, "live", "revoked", reason="Test")

        response = client.patch(
            f"/api/v1/properties/{prop.property_id}/pull-back",
            headers=agent_token_headers,
        )
        assert response.status_code == 422
        assert "await agency instruction" in response.json()["detail"].lower()

    def test_pull_back_revoked_with_instruction_proceeds(
        self, client: TestClient, db, agent_user, agency_owner_user,
        agent_token_headers, agency, location, property_type,
    ):
        """Agent can pull back a revoked listing after instruction."""
        from app.models.listing_instructions import ListingInstruction
        prop = _make_property(db, agent_user, agency, location, property_type, ModerationStatus.revoked)
        event = _write_event(db, prop, agent_user.user_id, "live", "revoked", reason="Test")
        db.add(ListingInstruction(
            listing_id=prop.property_id, agency_id=agency.agency_id,
            actor_id=agency_owner_user.user_id, triggered_by_event_id=event.event_id,
            instruction_text="Edit and resubmit",
        ))
        db.flush()

        response = client.patch(
            f"/api/v1/properties/{prop.property_id}/pull-back",
            headers=agent_token_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["moderation_status"] == "draft"


# ===========================================================================
# Enrichment on GET /{property_id}
# ===========================================================================

class TestPropertyResponseEnrichment:
    """PropertyResponse includes has_instruction and instruction_text for creator."""

    def test_creator_sees_instruction_fields(
        self, client: TestClient, db, agent_user, agency_owner_user,
        agent_token_headers, agency, location, property_type,
    ):
        """Listing creator sees has_instruction and instruction_text in response."""
        from app.models.listing_instructions import ListingInstruction
        prop = _make_property(db, agent_user, agency, location, property_type, ModerationStatus.revoked)
        event = _write_event(db, prop, agent_user.user_id, "live", "revoked", reason="Test reason")
        db.add(ListingInstruction(
            listing_id=prop.property_id, agency_id=agency.agency_id,
            actor_id=agency_owner_user.user_id, triggered_by_event_id=event.event_id,
            instruction_text="Fix it",
        ))
        db.flush()

        response = client.get(
            f"/api/v1/properties/{prop.property_id}",
            headers=agent_token_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["has_instruction"] is True
        assert data["instruction_text"] == "Fix it"
        assert data["latest_event_reason"] == "Test reason"

    def test_non_creator_does_not_see_instruction_fields(
        self, client: TestClient, db, agent_user, agency_owner_user,
        normal_user, normal_user_token_headers, agency, location, property_type,
    ):
        """Non-creator (seeker) gets 403 for non-published listing — instruction fields not relevant."""
        from app.models.listing_instructions import ListingInstruction
        prop = _make_property(db, agent_user, agency, location, property_type, ModerationStatus.revoked)
        event = _write_event(db, prop, agent_user.user_id, "live", "revoked", reason="Test")
        db.add(ListingInstruction(
            listing_id=prop.property_id, agency_id=agency.agency_id,
            actor_id=agency_owner_user.user_id, triggered_by_event_id=event.event_id,
            instruction_text="Fix it",
        ))
        db.flush()

        response = client.get(
            f"/api/v1/properties/{prop.property_id}",
            headers=normal_user_token_headers,
        )
        # Seeker cannot view a non-published listing — 403 is expected
        assert response.status_code == 403

    def test_agency_owner_sees_latest_event_reason(
        self, client: TestClient, db, agent_user, agency_owner_user,
        agency_owner_token_headers, agency, location, property_type,
    ):
        """Agency owner sees latest_event_reason on live listing with revocation history."""
        from geoalchemy2.elements import WKTElement
        # Create a currently-live listing that was previously revoked
        prop = Property(
            title="Live With History", description="Was revoked, now restored",
            user_id=agent_user.user_id, agency_id=agency.agency_id,
            property_type_id=property_type.property_type_id,
            location_id=location.location_id,
            geom=WKTElement("POINT(3.3488 6.6018)", srid=4326),
            price=50000000, bedrooms=3, bathrooms=2, property_size=120.0,
            listing_type=ListingType.sale, listing_status=ListingStatus.available,
            moderation_status=ModerationStatus.live, is_verified=True,
        )
        db.add(prop); db.flush(); db.refresh(prop)
        # Write a revocation event in the listing's history
        _write_event(db, prop, agent_user.user_id, "live", "revoked", reason="Admin revocation reason")
        # Write a restore event so the most recent relevant event is the revocation
        _write_event(db, prop, agent_user.user_id, "revoked", "live", reason="Restored")

        response = client.get(
            f"/api/v1/properties/{prop.property_id}",
            headers=agency_owner_token_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["latest_event_reason"] == "Admin revocation reason"

    def test_admin_sees_latest_event_reason(
        self, client: TestClient, db, agent_user, admin_token_headers,
        agency, location, property_type,
    ):
        """Admin sees latest_event_reason on live listing with revocation history."""
        from geoalchemy2.elements import WKTElement
        prop = Property(
            title="Live With History Admin", description="Was revoked, now restored",
            user_id=agent_user.user_id, agency_id=agency.agency_id,
            property_type_id=property_type.property_type_id,
            location_id=location.location_id,
            geom=WKTElement("POINT(3.3488 6.6018)", srid=4326),
            price=50000000, bedrooms=3, bathrooms=2, property_size=120.0,
            listing_type=ListingType.sale, listing_status=ListingStatus.available,
            moderation_status=ModerationStatus.live, is_verified=True,
        )
        db.add(prop); db.flush(); db.refresh(prop)
        _write_event(db, prop, agent_user.user_id, "live", "revoked", reason="Admin revocation")

        response = client.get(
            f"/api/v1/properties/{prop.property_id}",
            headers=admin_token_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["latest_event_reason"] == "Admin revocation"

    def test_no_recent_event_returns_null_fields(
        self, client: TestClient, db, agent_user, agent_token_headers,
        agency, location, property_type,
    ):
        """No revocation events means null instruction fields."""
        prop = _make_property(db, agent_user, agency, location, property_type, ModerationStatus.draft)

        response = client.get(
            f"/api/v1/properties/{prop.property_id}",
            headers=agent_token_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["has_instruction"] is False
        assert data["instruction_text"] is None
        assert data["latest_event_reason"] is None


# ===========================================================================
# Multiple lifecycle cycles — instruction from prior cycle does not unlock
# ===========================================================================

class TestMultipleLifecycleCycles:
    """An instruction from a prior revocation cycle must not unlock CTAs in a new cycle."""

    def test_old_instruction_does_not_unlock_new_revocation(
        self, client: TestClient, db, agent_user, agency_owner_user,
        agent_token_headers, agency, location, property_type,
    ):
        """After restore → revoke again, old instruction doesn't unlock the new revocation."""
        from app.models.listing_instructions import ListingInstruction

        prop = _make_property(db, agent_user, agency, location, property_type, ModerationStatus.revoked)

        # First cycle: revoke, instruct, pull back (listing goes to draft)
        event1 = _write_event(db, prop, agent_user.user_id, "live", "revoked", reason="First revocation")
        inst1 = ListingInstruction(
            listing_id=prop.property_id, agency_id=agency.agency_id,
            actor_id=agency_owner_user.user_id, triggered_by_event_id=event1.event_id,
            instruction_text="Fix it first time",
        )
        db.add(inst1)

        # Simulate pull-back (moderation_status → draft)
        prop.moderation_status = ModerationStatus.draft
        db.flush()

        # Second cycle: new revocation (different event, no new instruction)
        _write_event(db, prop, agent_user.user_id, "draft", "revoked", reason="Second revocation")
        prop.moderation_status = ModerationStatus.revoked
        db.flush()

        # Old instruction exists but is tied to event1, not the new revocation
        response = client.put(
            f"/api/v1/properties/{prop.property_id}",
            json={"title": "Should be blocked"},
            headers=agent_token_headers,
        )
        # Should be blocked because the instruction is tied to the first event, not the new revocation
        assert response.status_code == 422
        assert "await agency instruction" in response.json()["detail"].lower()
