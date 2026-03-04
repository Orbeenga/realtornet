# tests/crud/test_agent_profiles_v2.py
"""
Final coverage push — agent_profiles.py missing lines.
agent_profiles.py missing: 178, 285-294, 301
"""

import pytest
from unittest.mock import MagicMock, patch
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from app.crud.agent_profiles import AgentProfileCRUD, agent_profile as ap_singleton
from app.models.users import User, UserRole
from app.models.agent_profiles import AgentProfile
from app.schemas.agent_profiles import AgentProfileCreate, AgentProfileUpdate


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

@pytest.fixture
def mock_db():
    return MagicMock(spec=Session)


def make_user(**kwargs) -> MagicMock:
    defaults = dict(
        user_id=1, email="u@test.com", user_role=UserRole.SEEKER,
        is_admin=False, is_verified=True, deleted_at=None,
        supabase_id="uuid-1", agency_id=None,
    )
    defaults.update(kwargs)
    obj = MagicMock(spec=User)
    for k, v in defaults.items():
        setattr(obj, k, v)
    return obj


def make_profile(**kwargs) -> MagicMock:
    defaults = dict(
        profile_id=1, user_id=1, agency_id=1,
        license_number="LIC-001", deleted_at=None,
    )
    defaults.update(kwargs)
    obj = MagicMock(spec=AgentProfile)
    for k, v in defaults.items():
        setattr(obj, k, v)
    return obj


# ═══════════════════════════════════════════════
# AGENT PROFILES — missing lines
# ═══════════════════════════════════════════════

@pytest.fixture
def ap_crud():
    return AgentProfileCRUD()


# ─── update agency_id with active properties (line 178 — property_count > 0 branch) ─

class TestAgentProfileUpdateAgencyBlock:
    def test_agency_change_blocked_with_active_properties(self, ap_crud, mock_db):
        """Line 178: Cannot change agency if agent has active properties."""
        obj = make_profile(agency_id=1)
        mock_db.execute.return_value.scalar.return_value = 3  # 3 active properties

        with pytest.raises(ValueError, match="Cannot change agency"):
            ap_crud.update(
                mock_db,
                db_obj=obj,
                obj_in={"agency_id": 2},  # Changing agency
                updated_by="admin-uuid"
            )

    def test_agency_change_allowed_no_properties(self, ap_crud, mock_db):
        """Agency change allowed when agent has 0 properties."""
        obj = make_profile(agency_id=1)
        mock_db.execute.return_value.scalar.return_value = 0

        from app.models.agencies import Agency
        agency = MagicMock(spec=Agency)
        agency.deleted_at = None

        with patch.object(ap_crud, "_validate_agency_exists", return_value=agency):
            mock_db.add.return_value = None
            mock_db.commit.return_value = None
            mock_db.refresh.return_value = None
            result = ap_crud.update(
                mock_db,
                db_obj=obj,
                obj_in={"agency_id": 2},
                updated_by="admin-uuid"
            )
        assert obj.agency_id == 2


# ─── soft_delete — already deleted (lines 285-294) ────

class TestAgentProfileSoftDelete:
    def test_not_found_raises(self, ap_crud, mock_db):
        """Line 289-290: profile not found → ValueError."""
        mock_db.get.return_value = None
        with pytest.raises(ValueError, match="not found"):
            ap_crud.soft_delete(mock_db, profile_id=999)

    def test_already_deleted_raises(self, ap_crud, mock_db):
        """Lines 292-293: already deleted → ValueError."""
        obj = make_profile(deleted_at=datetime.now(timezone.utc))
        mock_db.get.return_value = obj
        with pytest.raises(ValueError, match="already deleted"):
            ap_crud.soft_delete(mock_db, profile_id=1)

    def test_soft_deletes_successfully(self, ap_crud, mock_db):
        """Lines 285-294: happy path sets deleted_at."""
        obj = make_profile(deleted_at=None)
        mock_db.get.return_value = obj
        mock_db.add.return_value = None
        mock_db.commit.return_value = None
        mock_db.refresh.return_value = None
        result = ap_crud.soft_delete(mock_db, profile_id=1,
                                     deleted_by_supabase_id="admin-uuid")
        assert result == obj
        assert obj.deleted_at is not None
        assert obj.deleted_by == "admin-uuid"


# ─── get_stats (line 301 — profile not found) ─

class TestAgentProfileGetStats:
    def test_profile_not_found_raises(self, ap_crud, mock_db):
        """Line 301: profile not found → ValueError."""
        with patch.object(ap_crud, "get", return_value=None):
            with pytest.raises(ValueError, match="not found"):
                ap_crud.get_stats(mock_db, profile_id=999)

    def test_returns_stats(self, ap_crud, mock_db):
        """Happy path: returns dict with counts and rating."""
        obj = make_profile()
        with patch.object(ap_crud, "get", return_value=obj):
            # Wire three scalar() calls: property_count, review_count, avg_rating
            mock_db.execute.return_value.scalar.side_effect = [5, 3, 4.2]
            result = ap_crud.get_stats(mock_db, profile_id=1)
        assert result["property_count"] == 5
        assert result["review_count"] == 3
        assert result["average_rating"] == 4.2

    def test_no_reviews_defaults_zero(self, ap_crud, mock_db):
        """avg_rating None → 0.0 default."""
        obj = make_profile()
        with patch.object(ap_crud, "get", return_value=obj):
            mock_db.execute.return_value.scalar.side_effect = [0, 0, None]
            result = ap_crud.get_stats(mock_db, profile_id=1)
        assert result["average_rating"] == 0.0


# ─── singleton ────────────────────────────────

class TestAgentProfileSingleton:
    def test_is_instance(self):
        assert isinstance(ap_singleton, AgentProfileCRUD)
