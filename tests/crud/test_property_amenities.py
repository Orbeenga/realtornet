# tests/crud/test_property_amenites.py
"""
PropertyAmenity CRUD Tests — Full coverage
property_amenities.py missing: 38-44, 56-63, 72, 85-89, 99-106, 115, 131,
    159-180, 193, 218-254, 264, 284-346, 360, 376-386, 400, 413-423, 433, 449-456, 482-491
"""

import pytest
from unittest.mock import MagicMock, patch, call
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from app.crud.property_amenities import PropertyAmenityCRUD, property_amenity as pa_singleton
from app.models.amenities import Amenity


# ─────────────────────────────────────────────
# SHARED HELPERS
# ─────────────────────────────────────────────

@pytest.fixture
def mock_db():
    return MagicMock(spec=Session)


def scalars_all(mock_db, value):
    mock_db.execute.return_value.scalars.return_value.all.return_value = value


def scalar(mock_db, value):
    mock_db.execute.return_value.scalar.return_value = value


def first_result(mock_db, value):
    mock_db.execute.return_value.first.return_value = value


# ═══════════════════════════════════════════════
# PROPERTY AMENITIES
# ═══════════════════════════════════════════════

@pytest.fixture
def pa_crud():
    return PropertyAmenityCRUD()


def make_amenity(**kwargs) -> MagicMock:
    defaults = dict(amenity_id=1, name="WiFi", category="Internet")
    defaults.update(kwargs)
    obj = MagicMock(spec=Amenity)
    for k, v in defaults.items():
        setattr(obj, k, v)
    return obj


# ─── get (lines 38-44) ───────────────────────

class TestPAGet:
    def test_exists(self, pa_crud, mock_db):
        first_result(mock_db, MagicMock())
        assert pa_crud.get(mock_db, property_id=1, amenity_id=1) is True

    def test_not_exists(self, pa_crud, mock_db):
        first_result(mock_db, None)
        assert pa_crud.get(mock_db, property_id=1, amenity_id=99) is False


# ─── get_property_amenities (lines 56-63) ────

class TestPAGetPropertyAmenities:
    def test_returns_amenities(self, pa_crud, mock_db):
        items = [make_amenity(), make_amenity(amenity_id=2, name="Pool")]
        scalars_all(mock_db, items)
        assert pa_crud.get_property_amenities(mock_db, property_id=1) == items

    def test_empty(self, pa_crud, mock_db):
        scalars_all(mock_db, [])
        assert pa_crud.get_property_amenities(mock_db, property_id=99) == []


# ─── get_amenities_for_property (line 72) ────

class TestPAGetAmenitiesForProperty:
    def test_delegates_to_get_property_amenities(self, pa_crud, mock_db):
        items = [make_amenity()]
        with patch.object(pa_crud, "get_property_amenities", return_value=items) as mock_gpa:
            result = pa_crud.get_amenities_for_property(mock_db, property_id=1)
        mock_gpa.assert_called_once_with(mock_db, property_id=1)
        assert result == items


# ─── get_property_amenity_ids (lines 85-89) ──

class TestPAGetPropertyAmenityIds:
    def test_returns_ids(self, pa_crud, mock_db):
        mock_db.execute.return_value.scalars.return_value.all.return_value = [1, 2, 3]
        assert pa_crud.get_property_amenity_ids(mock_db, property_id=1) == [1, 2, 3]

    def test_empty(self, pa_crud, mock_db):
        mock_db.execute.return_value.scalars.return_value.all.return_value = []
        assert pa_crud.get_property_amenity_ids(mock_db, property_id=99) == []


# ─── has_amenity (lines 99-106) ──────────────

class TestPAHasAmenity:
    def test_true(self, pa_crud, mock_db):
        first_result(mock_db, MagicMock())
        assert pa_crud.has_amenity(mock_db, property_id=1, amenity_id=1) is True

    def test_false(self, pa_crud, mock_db):
        first_result(mock_db, None)
        assert pa_crud.has_amenity(mock_db, property_id=1, amenity_id=99) is False


# ─── count_property_amenities (line 115) ─────

class TestPACountPropertyAmenities:
    def test_count(self, pa_crud, mock_db):
        scalar(mock_db, 3)
        assert pa_crud.count_property_amenities(mock_db, property_id=1) == 3

    def test_zero(self, pa_crud, mock_db):
        scalar(mock_db, 0)
        assert pa_crud.count_property_amenities(mock_db, property_id=99) == 0


# ─── count_by_amenity (line 131) ─────────────

class TestPACountByAmenity:
    def test_count(self, pa_crud, mock_db):
        scalar(mock_db, 7)
        assert pa_crud.count_by_amenity(mock_db, amenity_id=1) == 7

    def test_zero(self, pa_crud, mock_db):
        scalar(mock_db, 0)
        assert pa_crud.count_by_amenity(mock_db, amenity_id=99) == 0


# ─── add_amenity (lines 159-180) ─────────────

class TestPAAddAmenity:
    def test_add_new(self, pa_crud, mock_db):
        """Property + amenity exist, not yet linked → added."""
        from app.models.properties import Property
        mock_db.get.side_effect = lambda model, id_: MagicMock()
        with patch.object(pa_crud, "has_amenity", return_value=False):
            mock_db.execute.return_value = None
            mock_db.commit.return_value = None
            result = pa_crud.add_amenity(mock_db, property_id=1, amenity_id=1)
        assert result is True

    def test_already_exists_returns_false(self, pa_crud, mock_db):
        """Already linked → returns False without inserting."""
        mock_db.get.side_effect = lambda model, id_: MagicMock()
        with patch.object(pa_crud, "has_amenity", return_value=True):
            result = pa_crud.add_amenity(mock_db, property_id=1, amenity_id=1)
        assert result is False
        mock_db.commit.assert_not_called()

    def test_property_not_found_raises(self, pa_crud, mock_db):
        mock_db.get.side_effect = lambda model, id_: None
        with pytest.raises(ValueError, match="Property with id"):
            pa_crud.add_amenity(mock_db, property_id=999, amenity_id=1)

    def test_amenity_not_found_raises(self, pa_crud, mock_db):
        from app.models.properties import Property
        def _get(model, id_):
            return MagicMock() if model == Property else None
        mock_db.get.side_effect = _get
        with pytest.raises(ValueError, match="Amenity with id"):
            pa_crud.add_amenity(mock_db, property_id=1, amenity_id=999)


# ─── create (line 193) ───────────────────────

class TestPACreate:
    def test_delegates_to_add_amenity(self, pa_crud, mock_db):
        with patch.object(pa_crud, "add_amenity", return_value=True) as mock_aa:
            result = pa_crud.create(mock_db, property_id=1, amenity_id=2)
        mock_aa.assert_called_once_with(mock_db, property_id=1, amenity_id=2)
        assert result is True


# ─── add_amenities (lines 218-254) ───────────

class TestPAAddAmenities:
    def test_property_not_found_raises(self, pa_crud, mock_db):
        mock_db.get.return_value = None
        with pytest.raises(ValueError, match="Property with id"):
            pa_crud.add_amenities(mock_db, property_id=999, amenity_ids=[1, 2])

    def test_all_already_exist_returns_zero(self, pa_crud, mock_db):
        mock_db.get.return_value = MagicMock()
        with patch.object(pa_crud, "get_property_amenity_ids", return_value=[1, 2]):
            result = pa_crud.add_amenities(mock_db, property_id=1, amenity_ids=[1, 2])
        assert result == 0

    def test_adds_new_amenities(self, pa_crud, mock_db):
        mock_db.get.return_value = MagicMock()
        mock_db.commit.return_value = None
        # Do NOT set execute.return_value = None - keeps MagicMock for chaining
        mock_db.execute.return_value.scalars.return_value.all.return_value = [3, 4]
        with patch.object(pa_crud, "get_property_amenity_ids", return_value=[1, 2]):
            result = pa_crud.add_amenities(mock_db, property_id=1, amenity_ids=[1, 2, 3, 4])
        assert result == 2

    def test_invalid_amenity_ids_raises(self, pa_crud, mock_db):
        mock_db.get.return_value = MagicMock()
        with patch.object(pa_crud, "get_property_amenity_ids", return_value=[]):
            mock_db.execute.return_value.scalars.return_value.all.return_value = [1]  # only 1 found of 2
            with pytest.raises(ValueError, match="Amenities not found"):
                pa_crud.add_amenities(mock_db, property_id=1, amenity_ids=[1, 999])

    def test_commit_false_skips_commit(self, pa_crud, mock_db):
        mock_db.get.return_value = MagicMock()
        with patch.object(pa_crud, "get_property_amenity_ids", return_value=[]):
            mock_db.execute.return_value.scalars.return_value.all.return_value = [1]
            pa_crud.add_amenities(mock_db, property_id=1, amenity_ids=[1], commit=False)
        mock_db.commit.assert_not_called()


# ─── create_bulk (line 264) ──────────────────

class TestPACreateBulk:
    def test_delegates(self, pa_crud, mock_db):
        with patch.object(pa_crud, "add_amenities", return_value=2) as mock_aa:
            result = pa_crud.create_bulk(mock_db, property_id=1, amenity_ids=[1, 2])
        mock_aa.assert_called_once_with(mock_db, property_id=1, amenity_ids=[1, 2])
        assert result == 2


# ─── set_amenities (lines 284-346) ───────────

class TestPASetAmenities:
    def test_property_not_found_raises(self, pa_crud, mock_db):
        mock_db.get.return_value = None
        with pytest.raises(ValueError, match="Property with id"):
            pa_crud.set_amenities(mock_db, property_id=999, amenity_ids=[1])

    def test_adds_new_removes_old(self, pa_crud, mock_db):
        mock_db.get.return_value = MagicMock()
        amenity_list = [make_amenity(amenity_id=3)]
        with patch.object(pa_crud, "get_property_amenity_ids", return_value=[1, 2]):
            with patch.object(pa_crud, "add_amenities", return_value=1):
                with patch.object(pa_crud, "get_property_amenities", return_value=amenity_list):
                    mock_db.execute.return_value = None
                    mock_db.commit.return_value = None
                    result = pa_crud.set_amenities(mock_db, property_id=1, amenity_ids=[2, 3])
        assert result == amenity_list

    def test_no_changes(self, pa_crud, mock_db):
        """Same ids → no add, no remove."""
        mock_db.get.return_value = MagicMock()
        amenity_list = [make_amenity()]
        with patch.object(pa_crud, "get_property_amenity_ids", return_value=[1]):
            with patch.object(pa_crud, "get_property_amenities", return_value=amenity_list):
                mock_db.commit.return_value = None
                result = pa_crud.set_amenities(mock_db, property_id=1, amenity_ids=[1])
        assert result == amenity_list

    def test_sqlalchemy_error_raises_value_error(self, pa_crud, mock_db):
        from sqlalchemy.exc import SQLAlchemyError
        mock_db.get.return_value = MagicMock()
        with patch.object(pa_crud, "get_property_amenity_ids", return_value=[1]):
            mock_db.execute.side_effect = SQLAlchemyError("db error")
            mock_db.rollback.return_value = None
            with pytest.raises(ValueError, match="Failed to update amenities"):
                pa_crud.set_amenities(mock_db, property_id=1, amenity_ids=[2])

    def test_unexpected_error_raises_value_error(self, pa_crud, mock_db):
        mock_db.get.return_value = MagicMock()
        with patch.object(pa_crud, "get_property_amenity_ids", return_value=[1]):
            mock_db.execute.side_effect = RuntimeError("surprise")
            mock_db.rollback.return_value = None
            with pytest.raises(ValueError, match="unexpected error"):
                pa_crud.set_amenities(mock_db, property_id=1, amenity_ids=[2])


# ─── sync (line 360) ─────────────────────────

class TestPASync:
    def test_delegates_to_set_amenities(self, pa_crud, mock_db):
        with patch.object(pa_crud, "set_amenities", return_value=[]) as mock_sa:
            pa_crud.sync(mock_db, property_id=1, amenity_ids=[1, 2])
        mock_sa.assert_called_once_with(mock_db, property_id=1, amenity_ids=[1, 2])


# ─── remove_amenity (lines 376-386) ──────────

class TestPARemoveAmenity:
    def test_removed(self, pa_crud, mock_db):
        mock_db.execute.return_value.rowcount = 1
        mock_db.commit.return_value = None
        assert pa_crud.remove_amenity(mock_db, property_id=1, amenity_id=1) is True

    def test_not_found_returns_false(self, pa_crud, mock_db):
        mock_db.execute.return_value.rowcount = 0
        mock_db.commit.return_value = None
        assert pa_crud.remove_amenity(mock_db, property_id=1, amenity_id=99) is False


# ─── remove (line 400) ───────────────────────

class TestPARemove:
    def test_delegates(self, pa_crud, mock_db):
        with patch.object(pa_crud, "remove_amenity", return_value=True) as mock_ra:
            pa_crud.remove(mock_db, property_id=1, amenity_id=2)
        mock_ra.assert_called_once_with(mock_db, property_id=1, amenity_id=2)


# ─── remove_amenities (lines 413-423) ────────

class TestPARemoveAmenities:
    def test_removes_multiple(self, pa_crud, mock_db):
        mock_db.execute.return_value.rowcount = 2
        mock_db.commit.return_value = None
        assert pa_crud.remove_amenities(mock_db, property_id=1, amenity_ids=[1, 2]) == 2

    def test_none_found(self, pa_crud, mock_db):
        mock_db.execute.return_value.rowcount = 0
        mock_db.commit.return_value = None
        assert pa_crud.remove_amenities(mock_db, property_id=1, amenity_ids=[99]) == 0


# ─── remove_bulk (line 433) ──────────────────

class TestPARemoveBulk:
    def test_delegates(self, pa_crud, mock_db):
        with patch.object(pa_crud, "remove_amenities", return_value=3) as mock_ra:
            result = pa_crud.remove_bulk(mock_db, property_id=1, amenity_ids=[1, 2, 3])
        mock_ra.assert_called_once_with(mock_db, property_id=1, amenity_ids=[1, 2, 3])
        assert result == 3


# ─── clear_property_amenities (lines 449-456) ─

class TestPAClearPropertyAmenities:
    def test_clears_all(self, pa_crud, mock_db):
        mock_db.execute.return_value.rowcount = 5
        mock_db.commit.return_value = None
        assert pa_crud.clear_property_amenities(mock_db, property_id=1) == 5

    def test_none_to_clear(self, pa_crud, mock_db):
        mock_db.execute.return_value.rowcount = 0
        mock_db.commit.return_value = None
        assert pa_crud.clear_property_amenities(mock_db, property_id=99) == 0


# ─── copy_amenities (lines 482-491) ──────────

class TestPACopyAmenities:
    def test_copies_amenities(self, pa_crud, mock_db):
        with patch.object(pa_crud, "get_property_amenity_ids", return_value=[1, 2, 3]):
            with patch.object(pa_crud, "add_amenities", return_value=3) as mock_aa:
                result = pa_crud.copy_amenities(mock_db, from_property_id=1, to_property_id=2)
        mock_aa.assert_called_once_with(mock_db, property_id=2, amenity_ids=[1, 2, 3])
        assert result == 3

    def test_empty_source_returns_zero(self, pa_crud, mock_db):
        with patch.object(pa_crud, "get_property_amenity_ids", return_value=[]):
            result = pa_crud.copy_amenities(mock_db, from_property_id=1, to_property_id=2)
        assert result == 0


# ─── singleton ────────────────────────────────

class TestPASingleton:
    def test_is_instance(self):
        assert isinstance(pa_singleton, PropertyAmenityCRUD)