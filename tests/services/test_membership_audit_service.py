"""Tests for membership_audit_service.py"""
from datetime import datetime, timezone
from typing import cast

import pytest
from app.services.membership_audit_service import (
    serialize_user_role,
    membership_audit_action_for_status,
    write_membership_audit,
    get_agency_all_member_history,
)
from app.models.users import UserRole


def _make_agency(db) -> int:
    """Create a minimal agency and return its agency_id."""
    from app.models.agencies import Agency
    agency = Agency(name="Test Audit Agency")
    db.add(agency)
    db.flush()
    return cast(int, agency.agency_id)


def _make_user(db, email: str, role: UserRole = UserRole.SEEKER) -> int:
    """Create a minimal user and return its user_id."""
    from app.models.users import User
    from app.core.security import get_password_hash
    import uuid
    user = User(
        email=email,
        password_hash=get_password_hash("password"),
        first_name="Test",
        last_name="User",
        phone_number="+2347000000100",
        user_role=role,
        supabase_id=uuid.uuid4(),
    )
    db.add(user)
    db.flush()
    return cast(int, user.user_id)


class TestSerializeUserRole:
    def test_returns_none_when_value_is_none(self):
        assert serialize_user_role(None) is None

    def test_extracts_value_from_enum(self):
        assert serialize_user_role(UserRole.AGENT) == "agent"

    def test_passes_through_string(self):
        assert serialize_user_role("admin") == "admin"


class TestWriteMembershipAudit:
    def test_with_custom_created_at(self, db):
        uid = _make_user(db, "audit_ts@example.com")
        aid = _make_agency(db)

        ts = datetime(2026, 1, 1, tzinfo=timezone.utc)
        audit = write_membership_audit(
            db=db,
            user_id=uid,
            agency_id=aid,
            action="joined",
            actor_id=uid,
            reason="test",
            prior_role=UserRole.SEEKER,
            post_role=UserRole.AGENT,
            created_at=ts,
        )
        assert str(audit.created_at) == str(ts)

    def test_raises_value_error_for_unsupported_status(self):
        with pytest.raises(ValueError, match="Unsupported membership status"):
            membership_audit_action_for_status("unknown_status")


class TestGetAgencyAllMemberHistory:
    def test_returns_empty_list_for_nonexistent_agency(self, db):
        result = get_agency_all_member_history(db=db, agency_id=99999, skip=0, limit=10)
        assert result == []

    def test_includes_display_name_in_results(self, db):
        from app.models.users import UserRole

        uid = _make_user(db, "audit_display@example.com", role=UserRole.AGENT)
        aid = _make_agency(db)

        audit = write_membership_audit(
            db=db,
            user_id=uid,
            agency_id=aid,
            action="joined",
            actor_id=uid,
            reason="welcome",
            prior_role=UserRole.SEEKER,
            post_role=UserRole.AGENT,
        )

        result = get_agency_all_member_history(db=db, agency_id=aid, skip=0, limit=10)
        matching = [r for r in result if r["id"] == audit.id]
        assert len(matching) == 1
        assert matching[0]["user_display_name"] == "Test User"
        assert matching[0]["action"] == "joined"
        assert matching[0]["agency_name"] == "Test Audit Agency"


class TestMembershipAuditActionForStatus:
    def test_reinstated_for_active(self):
        assert membership_audit_action_for_status("active") == "reinstated"

    def test_suspended_for_suspended(self):
        assert membership_audit_action_for_status("suspended") == "suspended"

    def test_revoked_for_inactive(self):
        assert membership_audit_action_for_status("inactive") == "revoked"

    def test_revoked_for_blocked(self):
        assert membership_audit_action_for_status("blocked") == "revoked"


class TestGetUserMembershipHistory:
    def test_returns_audit_records_for_user(self, db):
        uid = _make_user(db, "history_user@example.com")
        aid = _make_agency(db)

        write_membership_audit(
            db=db, user_id=uid, agency_id=aid, action="joined",
            actor_id=uid, reason="signed up",
            prior_role=UserRole.SEEKER, post_role=UserRole.AGENT,
        )

        from app.services.membership_audit_service import get_user_membership_history
        result = get_user_membership_history(db=db, user_id=uid, skip=0, limit=10)
        assert len(result) >= 1
        assert result[0]["agency_name"] is not None

    def test_returns_empty_for_unknown_user(self, db):
        from app.services.membership_audit_service import get_user_membership_history
        result = get_user_membership_history(db=db, user_id=99999, skip=0, limit=10)
        assert result == []


class TestGetAgencyMemberHistory:
    def test_returns_audit_records_for_user_in_agency(self, db):
        uid = _make_user(db, "agency_history@example.com")
        aid = _make_agency(db)

        write_membership_audit(
            db=db, user_id=uid, agency_id=aid, action="joined",
            actor_id=uid, reason="invited",
            prior_role=UserRole.SEEKER, post_role=UserRole.AGENT,
        )

        from app.services.membership_audit_service import get_agency_member_history
        result = get_agency_member_history(db=db, agency_id=aid, user_id=uid, skip=0, limit=10)
        assert len(result) >= 1
        assert result[0]["action"] == "joined"

    def test_returns_empty_for_nonexistent_pair(self, db):
        from app.services.membership_audit_service import get_agency_member_history
        result = get_agency_member_history(db=db, agency_id=99999, user_id=99999, skip=0, limit=10)
        assert result == []
