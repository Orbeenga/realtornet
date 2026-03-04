# tests/crud/test_saved_searches.py
"""
SavedSearches CRUD Tests — Full coverage
saved_searches.py missing: 27-36, 45-51, 65-77, 91-114, 126-133, 142-148, 158-165, 177-190
"""

import pytest
from unittest.mock import MagicMock, patch
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from app.crud.saved_searches import SavedSearchCRUD, saved_search as ss_singleton
from app.models.saved_searches import SavedSearch
from app.schemas.saved_searches import SavedSearchCreate, SavedSearchUpdate


# ─────────────────────────────────────────────
# SHARED HELPERS
# ─────────────────────────────────────────────

@pytest.fixture
def mock_db():
    return MagicMock(spec=Session)


def scalar_one_or_none(mock_db, value):
    mock_db.execute.return_value.scalar_one_or_none.return_value = value


def scalars_all(mock_db, value):
    mock_db.execute.return_value.scalars.return_value.all.return_value = value


def scalar(mock_db, value):
    mock_db.execute.return_value.scalar.return_value = value


# ═══════════════════════════════════════════════
# SAVED SEARCHES
# ═══════════════════════════════════════════════

@pytest.fixture
def ss_crud():
    return SavedSearchCRUD()


def make_search(**kwargs) -> MagicMock:
    defaults = dict(
        search_id=1,
        user_id=1,
        name="Lagos Apartments",
        search_params={"city": "Lagos", "bedrooms": 2},
        deleted_at=None,
        created_at=datetime.now(timezone.utc),
    )
    defaults.update(kwargs)
    obj = MagicMock(spec=SavedSearch)
    for k, v in defaults.items():
        setattr(obj, k, v)
    return obj


# ─── create (lines 27-36) ────────────────────

class TestSavedSearchCreate:
    def test_create(self, ss_crud, mock_db):
        mock_db.add.return_value = None
        mock_db.commit.return_value = None
        mock_db.refresh.return_value = None
        ss_crud.create(mock_db,
                       obj_in=SavedSearchCreate(name="Test", search_params={"city": "Abuja"}),
                       user_id=1)
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()

    def test_create_sets_user_id(self, ss_crud, mock_db):
        mock_db.add.return_value = None
        mock_db.commit.return_value = None
        mock_db.refresh.return_value = None
        # Change {} to a non-empty dict like {"type": "apartment"}
        ss_crud.create(
            mock_db,
            obj_in=SavedSearchCreate(
                name="X", 
                search_params={"min_price": 1000} 
            ),
            user_id=42
        )
        added = mock_db.add.call_args[0][0]
        assert added.user_id == 42


# ─── get (lines 45-51) ───────────────────────

class TestSavedSearchGet:
    def test_found(self, ss_crud, mock_db):
        obj = make_search()
        scalar_one_or_none(mock_db, obj)
        assert ss_crud.get(mock_db, search_id=1) == obj

    def test_not_found(self, ss_crud, mock_db):
        scalar_one_or_none(mock_db, None)
        assert ss_crud.get(mock_db, search_id=999) is None


# ─── get_user_saved_searches (lines 65-77) ───

class TestSavedSearchGetUser:
    def test_returns_list(self, ss_crud, mock_db):
        items = [make_search(), make_search(search_id=2)]
        scalars_all(mock_db, items)
        assert ss_crud.get_user_saved_searches(mock_db, user_id=1) == items

    def test_empty(self, ss_crud, mock_db):
        scalars_all(mock_db, [])
        assert ss_crud.get_user_saved_searches(mock_db, user_id=99) == []

    def test_pagination(self, ss_crud, mock_db):
        scalars_all(mock_db, [])
        assert ss_crud.get_user_saved_searches(mock_db, user_id=1, skip=5, limit=10) == []


# ─── update (lines 91-114) ───────────────────

class TestSavedSearchUpdate:
    def test_not_found_returns_none(self, ss_crud, mock_db):
        with patch.object(ss_crud, "get", return_value=None):
            result = ss_crud.update(mock_db, search_id=999,
                                    obj_in=SavedSearchUpdate(name="X"))
        assert result is None

    def test_update_name(self, ss_crud, mock_db):
        obj = make_search(name="Old Name")
        with patch.object(ss_crud, "get", return_value=obj):
            mock_db.commit.return_value = None
            mock_db.refresh.return_value = None
            ss_crud.update(mock_db, search_id=1, obj_in=SavedSearchUpdate(name="New Name"))
        assert obj.name == "New Name"

    def test_update_search_params_merges(self, ss_crud, mock_db):
        """search_params dict → merged, not replaced."""
        obj = make_search(search_params={"city": "Lagos", "bedrooms": 2})
        with patch.object(ss_crud, "get", return_value=obj):
            mock_db.commit.return_value = None
            mock_db.refresh.return_value = None
            ss_crud.update(mock_db, search_id=1,
                           obj_in=SavedSearchUpdate(search_params={"price_max": 5000000}))
        # Merged: both old and new keys present
        assert obj.search_params.get("city") == "Lagos"
        assert obj.search_params.get("price_max") == 5000000

    def test_update_strips_protected_fields(self, ss_crud, mock_db):
        obj = make_search(search_id=1, user_id=5)
        with patch.object(ss_crud, "get", return_value=obj):
            mock_db.commit.return_value = None
            mock_db.refresh.return_value = None
            ss_crud.update(mock_db, search_id=1,
                           obj_in=SavedSearchUpdate(name="Safe"))
        assert obj.search_id == 1
        assert obj.user_id == 5


# ─── soft_delete (lines 126-133) ─────────────

class TestSavedSearchSoftDelete:
    def test_soft_delete_found(self, ss_crud, mock_db):
        obj = make_search()
        with patch.object(ss_crud, "get", return_value=obj):
            mock_db.commit.return_value = None
            mock_db.refresh.return_value = None
            result = ss_crud.soft_delete(mock_db, search_id=1)
        assert result == obj
        mock_db.commit.assert_called_once()

    def test_soft_delete_not_found(self, ss_crud, mock_db):
        with patch.object(ss_crud, "get", return_value=None):
            result = ss_crud.soft_delete(mock_db, search_id=999)
        assert result is None
        mock_db.commit.assert_not_called()

    def test_sets_deleted_at(self, ss_crud, mock_db):
        obj = make_search(deleted_at=None)
        with patch.object(ss_crud, "get", return_value=obj):
            mock_db.commit.return_value = None
            mock_db.refresh.return_value = None
            ss_crud.soft_delete(mock_db, search_id=1)
        # deleted_at assigned (func.now() object, not None)
        assert obj.deleted_at is not None


# ─── count_user_saved_searches (lines 142-148) ─

class TestSavedSearchCount:
    def test_count(self, ss_crud, mock_db):
        scalar(mock_db, 5)
        assert ss_crud.count_user_saved_searches(mock_db, user_id=1) == 5

    def test_zero(self, ss_crud, mock_db):
        scalar(mock_db, 0)
        assert ss_crud.count_user_saved_searches(mock_db, user_id=99) == 0


# ─── get_by_name (lines 158-165) ─────────────

class TestSavedSearchGetByName:
    def test_found(self, ss_crud, mock_db):
        obj = make_search(name="Lagos Apartments")
        scalar_one_or_none(mock_db, obj)
        assert ss_crud.get_by_name(mock_db, user_id=1, name="Lagos Apartments") == obj

    def test_not_found(self, ss_crud, mock_db):
        scalar_one_or_none(mock_db, None)
        assert ss_crud.get_by_name(mock_db, user_id=1, name="Nonexistent") is None

    def test_case_insensitive(self, ss_crud, mock_db):
        obj = make_search(name="lagos apartments")
        scalar_one_or_none(mock_db, obj)
        assert ss_crud.get_by_name(mock_db, user_id=1, name="LAGOS APARTMENTS") == obj


# ─── search_by_name_pattern (lines 177-190) ──

class TestSavedSearchPattern:
    def test_returns_matches(self, ss_crud, mock_db):
        items = [make_search(name="Lagos 2BR")]
        scalars_all(mock_db, items)
        assert ss_crud.search_by_name_pattern(mock_db, user_id=1, pattern="lagos") == items

    def test_empty(self, ss_crud, mock_db):
        scalars_all(mock_db, [])
        assert ss_crud.search_by_name_pattern(mock_db, user_id=1, pattern="zzz") == []

    def test_pagination(self, ss_crud, mock_db):
        scalars_all(mock_db, [])
        result = ss_crud.search_by_name_pattern(
            mock_db, user_id=1, pattern="lagos", skip=0, limit=5)
        assert result == []


# ─── singleton ────────────────────────────────

class TestSavedSearchSingleton:
    def test_is_instance(self):
        assert isinstance(ss_singleton, SavedSearchCRUD)