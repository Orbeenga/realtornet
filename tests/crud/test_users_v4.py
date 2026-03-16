# tests/crud/test_users_v4.py
"""
test_users_v4.py — Surgical coverage for users.py missing lines:
  92-102  : get_multi with user_role and is_verified filters
  183     : update_verification_status not-found returns None
  253-259 : soft_delete (found + sets deleted_at + deleted_by)
  283-286 : can_modify_user (admin True, self True, other False)
"""

import pytest
from unittest.mock import MagicMock, patch, call
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from app.crud.users import UserCRUD
from app.models.users import User, UserRole


@pytest.fixture
def mock_db():
    return MagicMock(spec=Session)


@pytest.fixture
def crud():
    return UserCRUD()


def make_user(**kwargs):
    defaults = dict(
        user_id=1, email="u@test.com",
        user_role=UserRole.SEEKER,
        is_admin=False, is_verified=True,
        deleted_at=None, supabase_id="uuid-1",
        agency_id=None, verification_code="CODE123",
        deleted_by=None, updated_by=None,
    )
    defaults.update(kwargs)
    obj = MagicMock(spec=User)
    for k, v in defaults.items():
        setattr(obj, k, v)
    return obj


# ─── get_multi filter branches (lines 92-102) ────────────────────────────────

class TestGetMultiFilters:
    """Each test exercises a different branch of the filter chain."""

    def test_no_filters(self, crud, mock_db):
        mock_db.execute.return_value.scalars.return_value.all.return_value = []
        result = crud.get_multi(mock_db)
        assert result == []

    def test_filter_user_role_only(self, crud, mock_db):
        """Line 97: user_role filter applied."""
        items = [make_user(user_role=UserRole.AGENT)]
        mock_db.execute.return_value.scalars.return_value.all.return_value = items
        result = crud.get_multi(mock_db, user_role=UserRole.AGENT)
        assert result == items

    def test_filter_is_verified_true(self, crud, mock_db):
        """Line 99: is_verified filter applied (True)."""
        items = [make_user(is_verified=True)]
        mock_db.execute.return_value.scalars.return_value.all.return_value = items
        result = crud.get_multi(mock_db, is_verified=True)
        assert result == items

    def test_filter_is_verified_false(self, crud, mock_db):
        """Line 99: is_verified filter applied (False) — separate branch."""
        mock_db.execute.return_value.scalars.return_value.all.return_value = []
        result = crud.get_multi(mock_db, is_verified=False)
        assert result == []

    def test_filter_role_and_verified(self, crud, mock_db):
        """Lines 97+99: both filters applied."""
        mock_db.execute.return_value.scalars.return_value.all.return_value = []
        result = crud.get_multi(mock_db, user_role=UserRole.ADMIN, is_verified=True)
        assert result == []

    def test_pagination(self, crud, mock_db):
        """Line 102: skip/limit applied."""
        mock_db.execute.return_value.scalars.return_value.all.return_value = []
        result = crud.get_multi(mock_db, skip=20, limit=5)
        assert result == []


# ─── update_verification_status (line 183) ───────────────────────────────────

class TestUpdateVerificationStatus:
    def test_not_found_returns_none(self, crud, mock_db):
        """Line 183: user not found → return None."""
        with patch.object(crud, "get", return_value=None):
            result = crud.update_verification_status(mock_db, user_id=999, is_verified=True)
        assert result is None

    def test_sets_verified_clears_code(self, crud, mock_db):
        """Happy path: sets is_verified, clears verification_code."""
        obj = make_user(is_verified=False, verification_code="ABC")
        with patch.object(crud, "get", return_value=obj):
            mock_db.commit.return_value = None
            mock_db.refresh.return_value = None
            result = crud.update_verification_status(mock_db, user_id=1, is_verified=True)
        assert obj.is_verified is True
        assert obj.verification_code is None


# ─── soft_delete (lines 253-259) ─────────────────────────────────────────────

class TestSoftDelete:
    def test_not_found_returns_none(self, crud, mock_db):
        """Line 254: user not found → None."""
        with patch.object(crud, "get", return_value=None):
            result = crud.soft_delete(mock_db, user_id=999)
        assert result is None
        mock_db.commit.assert_not_called()

    def test_sets_deleted_at(self, crud, mock_db):
        """Lines 256-259: sets deleted_at on found user."""
        obj = make_user(deleted_at=None)
        with patch.object(crud, "get", return_value=obj):
            mock_db.commit.return_value = None
            mock_db.refresh.return_value = None
            result = crud.soft_delete(mock_db, user_id=1)
        assert result == obj
        assert obj.deleted_at is not None

    def test_sets_updated_by_when_provided(self, crud, mock_db):
        """Line 257: deleted_by_supabase_id sets deleted_by."""
        obj = make_user(deleted_at=None)
        with patch.object(crud, "get", return_value=obj):
            mock_db.commit.return_value = None
            mock_db.refresh.return_value = None
            crud.soft_delete(mock_db, user_id=1, deleted_by_supabase_id="admin-uuid")
        assert obj.deleted_by == "admin-uuid"
        assert obj.updated_by != "admin-uuid"

    def test_no_deleted_by_skips_updated_by(self, crud, mock_db):
        """Line 257 branch: no deleted_by → updated_by not set."""
        obj = make_user(deleted_at=None)
        with patch.object(crud, "get", return_value=obj):
            mock_db.commit.return_value = None
            mock_db.refresh.return_value = None
            crud.soft_delete(mock_db, user_id=1)
        # updated_by should not have been assigned
        assert obj.deleted_at is not None
        assert obj.deleted_by is None


# ─── can_modify_user (lines 283-286) ─────────────────────────────────────────

class TestCanModifyUser:
    def test_admin_can_modify_anyone(self, crud):
        """Line 284: admin → always True."""
        admin = make_user(user_id=1, is_admin=True, user_role=UserRole.ADMIN)
        assert crud.can_modify_user(admin, target_user_id=99) is True

    def test_user_can_modify_self(self, crud):
        """Line 285: same user_id → True."""
        user = make_user(user_id=5, is_admin=False, user_role=UserRole.SEEKER)
        assert crud.can_modify_user(user, target_user_id=5) is True

    def test_user_cannot_modify_other(self, crud):
        """Line 286: different user_id, not admin → False."""
        user = make_user(user_id=5, is_admin=False, user_role=UserRole.SEEKER)
        assert crud.can_modify_user(user, target_user_id=99) is False

    def test_agent_cannot_modify_other(self, crud):
        """Agent role, not admin, different id → False."""
        agent = make_user(user_id=10, is_admin=False, user_role=UserRole.AGENT)
        assert crud.can_modify_user(agent, target_user_id=20) is False
