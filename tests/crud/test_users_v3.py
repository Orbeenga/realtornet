# tests/crud/test_users_v3.py
"""
Final coverage push — users.py missing lines.
users.py missing:    92-102, 183, 253-259, 283-286
"""

import pytest
from unittest.mock import MagicMock, patch
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from app.crud.users import UserCRUD, user as user_singleton
from app.models.users import User, UserRole
from app.models.agent_profiles import AgentProfile
from app.schemas.users import UserCreate, UserUpdate

# Import the actual singleton from the app
from app.crud.users import user as user_singleton


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
# USERS — missing lines
# ═══════════════════════════════════════════════

# @pytest.fixture
# def u_crud():
    # return UserCRUD()

@pytest.fixture
def u_crud():
    # Return the REAL singleton, not a new class instance
    return user_singleton


# ─── get_multi with filters (lines 92-102) ───

class TestUserGetMulti:
    def test_no_filters(self, u_crud, mock_db):
        items = [make_user()]
        mock_db.execute.return_value.scalars.return_value.all.return_value = items
        assert u_crud.get_multi(mock_db) == items

    def test_filter_by_role(self, u_crud, mock_db):
        items = [make_user(user_role=UserRole.AGENT)]
        mock_db.execute.return_value.scalars.return_value.all.return_value = items
        result = u_crud.get_multi(mock_db, user_role=UserRole.AGENT)
        assert result == items

    def test_filter_by_verified(self, u_crud, mock_db):
        items = [make_user(is_verified=True)]
        mock_db.execute.return_value.scalars.return_value.all.return_value = items
        result = u_crud.get_multi(mock_db, is_verified=True)
        assert result == items

    def test_filter_by_role_and_verified(self, u_crud, mock_db):
        mock_db.execute.return_value.scalars.return_value.all.return_value = []
        result = u_crud.get_multi(mock_db, user_role=UserRole.ADMIN, is_verified=False)
        assert result == []

    def test_pagination(self, u_crud, mock_db):
        mock_db.execute.return_value.scalars.return_value.all.return_value = []
        assert u_crud.get_multi(mock_db, skip=10, limit=5) == []


# ─── update_verification_status (line 183) ───

class TestUserUpdateVerification:
    def test_sets_verified_true(self, u_crud, mock_db):
        obj = make_user(is_verified=False)
        with patch.object(u_crud, "get", return_value=obj):
            mock_db.commit.return_value = None
            mock_db.refresh.return_value = None
            u_crud.update_verification_status(mock_db, user_id=1, is_verified=True)
        assert obj.is_verified is True
        assert obj.verification_code is None

    def test_not_found_returns_none(self, u_crud, mock_db):
        with patch.object(u_crud, "get", return_value=None):
            result = u_crud.update_verification_status(mock_db, user_id=999, is_verified=True)
        assert result is None


# ─── soft_delete (lines 253-259) ─────────────

class TestUserSoftDelete:
    def test_sets_deleted_at(self, u_crud, mock_db):
        obj = make_user()
        with patch.object(u_crud, "get", return_value=obj):
            mock_db.commit.return_value = None
            mock_db.refresh.return_value = None
            result = u_crud.soft_delete(mock_db, user_id=1,
                                        deleted_by_supabase_id="admin-uuid")
        assert result == obj
        assert obj.deleted_at is not None
        assert obj.updated_by == "admin-uuid"

    def test_not_found_returns_none(self, u_crud, mock_db):
        with patch.object(u_crud, "get", return_value=None):
            result = u_crud.soft_delete(mock_db, user_id=999)
        assert result is None

    def test_without_deleted_by(self, u_crud, mock_db):
        obj = make_user()
        with patch.object(u_crud, "get", return_value=obj):
            mock_db.commit.return_value = None
            mock_db.refresh.return_value = None
            u_crud.soft_delete(mock_db, user_id=1)
        assert obj.deleted_at is not None


# ─── can_modify_user (lines 283-286) ─────────

class TestUserCanModify:
    def test_admin_can_modify_anyone(self, u_crud):
        admin = make_user(user_id=1, is_admin=True, user_role=UserRole.ADMIN)
        assert u_crud.can_modify_user(admin, target_user_id=99) is True

    def test_user_can_modify_self(self, u_crud):
        user = make_user(user_id=5, is_admin=False, user_role=UserRole.SEEKER)
        assert u_crud.can_modify_user(user, target_user_id=5) is True

    def test_user_cannot_modify_other(self, u_crud):
        user = make_user(user_id=5, is_admin=False, user_role=UserRole.SEEKER)
        assert u_crud.can_modify_user(user, target_user_id=99) is False


# ─── singleton ────────────────────────────────

class TestUserSingleton:
    def test_is_instance(self):
        assert isinstance(user_singleton, UserCRUD)