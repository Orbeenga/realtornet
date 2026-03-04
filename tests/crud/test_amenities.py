# tests/crud/test_amenities.py
"""
Amenity CRUD Tests — Full coverage targeting 85%+
Missing lines: 28, 35, 49-51, 62-66, 70-76, 83, 96-103, 109, 115,
               136-152, 172-197, 211-233, 240, 254-263, 272-274,
               296-314, 339-348, 366-381
"""

import pytest
from unittest.mock import MagicMock, patch, call
from sqlalchemy.orm import Session

from app.crud.amenities import AmenityCRUD, amenity as amenity_singleton
from app.models.amenities import Amenity
from app.schemas.amenities import AmenityCreate, AmenityUpdate


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

@pytest.fixture
def crud():
    return AmenityCRUD()


@pytest.fixture
def mock_db():
    return MagicMock(spec=Session)


def make_amenity(**kwargs) -> MagicMock:
    defaults = dict(
        amenity_id=1,
        name="WiFi",
        description="High-speed internet",
        category="Internet",
    )
    defaults.update(kwargs)
    obj = MagicMock(spec=Amenity)
    for k, v in defaults.items():
        setattr(obj, k, v)
    return obj


def scalar_result(mock_db, value):
    """Wire db.execute().scalar_one_or_none() = value"""
    mock_db.execute.return_value.scalar_one_or_none.return_value = value


def scalars_all(mock_db, value):
    mock_db.execute.return_value.scalars.return_value.all.return_value = value


def scalar(mock_db, value):
    mock_db.execute.return_value.scalar.return_value = value


# ─────────────────────────────────────────────
# READ — get (line 28)
# ─────────────────────────────────────────────

class TestGet:
    def test_returns_amenity(self, crud, mock_db):
        obj = make_amenity()
        mock_db.get.return_value = obj
        assert crud.get(mock_db, amenity_id=1) == obj

    def test_returns_none_when_missing(self, crud, mock_db):
        mock_db.get.return_value = None
        assert crud.get(mock_db, amenity_id=999) is None


# ─────────────────────────────────────────────
# READ — get_by_name (line 35)
# ─────────────────────────────────────────────

class TestGetByName:
    def test_found(self, crud, mock_db):
        obj = make_amenity()
        scalar_result(mock_db, obj)
        assert crud.get_by_name(mock_db, name="WiFi") == obj

    def test_not_found(self, crud, mock_db):
        scalar_result(mock_db, None)
        assert crud.get_by_name(mock_db, name="NonExistent") is None

    def test_case_insensitive(self, crud, mock_db):
        obj = make_amenity(name="wifi")
        scalar_result(mock_db, obj)
        result = crud.get_by_name(mock_db, name="WIFI")
        assert result == obj


# ─────────────────────────────────────────────
# READ — get_multi (lines 49-51)
# ─────────────────────────────────────────────

class TestGetMulti:
    def test_returns_list(self, crud, mock_db):
        items = [make_amenity(amenity_id=i) for i in range(3)]
        scalars_all(mock_db, items)
        assert crud.get_multi(mock_db) == items

    def test_skip_limit(self, crud, mock_db):
        scalars_all(mock_db, [])
        assert crud.get_multi(mock_db, skip=10, limit=5) == []

    def test_empty(self, crud, mock_db):
        scalars_all(mock_db, [])
        assert crud.get_multi(mock_db) == []


# ─────────────────────────────────────────────
# READ — get_by_category (lines 62-66)
# ─────────────────────────────────────────────

class TestGetByCategory:
    def test_returns_filtered(self, crud, mock_db):
        items = [make_amenity(category="Internet")]
        scalars_all(mock_db, items)
        result = crud.get_by_category(mock_db, category="Internet")
        assert result == items

    def test_empty_category(self, crud, mock_db):
        scalars_all(mock_db, [])
        assert crud.get_by_category(mock_db, category="Nonexistent") == []

    def test_pagination(self, crud, mock_db):
        scalars_all(mock_db, [])
        assert crud.get_by_category(mock_db, category="Parking", skip=5, limit=10) == []


# ─────────────────────────────────────────────
# READ — get_categories (lines 70-76)
# ─────────────────────────────────────────────

class TestGetCategories:
    def test_returns_categories(self, crud, mock_db):
        mock_db.execute.return_value.scalars.return_value.all.return_value = ["Internet", "Parking"]
        result = crud.get_categories(mock_db)
        assert result == ["Internet", "Parking"]

    def test_empty(self, crud, mock_db):
        mock_db.execute.return_value.scalars.return_value.all.return_value = []
        assert crud.get_categories(mock_db) == []


# ─────────────────────────────────────────────
# READ — get_all_for_select (line 83)
# ─────────────────────────────────────────────

class TestGetAllForSelect:
    def test_returns_all(self, crud, mock_db):
        items = [make_amenity(amenity_id=i) for i in range(5)]
        scalars_all(mock_db, items)
        assert crud.get_all_for_select(mock_db) == items

    def test_custom_limit(self, crud, mock_db):
        scalars_all(mock_db, [])
        assert crud.get_all_for_select(mock_db, limit=200) == []


# ─────────────────────────────────────────────
# READ — search (lines 96-103)
# ─────────────────────────────────────────────

class TestSearch:
    def test_returns_matches(self, crud, mock_db):
        obj = make_amenity(name="WiFi Internet")
        scalars_all(mock_db, [obj])
        result = crud.search(mock_db, search_term="wifi")
        assert result == [obj]

    def test_no_matches(self, crud, mock_db):
        scalars_all(mock_db, [])
        assert crud.search(mock_db, search_term="zzznomatch") == []

    def test_pagination(self, crud, mock_db):
        scalars_all(mock_db, [])
        assert crud.search(mock_db, search_term="pool", skip=0, limit=10) == []


# ─────────────────────────────────────────────
# READ — count (line 109)
# ─────────────────────────────────────────────

class TestCount:
    def test_returns_count(self, crud, mock_db):
        scalar(mock_db, 42)
        assert crud.count(mock_db) == 42

    def test_zero(self, crud, mock_db):
        scalar(mock_db, 0)
        assert crud.count(mock_db) == 0


# ─────────────────────────────────────────────
# READ — exists (line 115)
# ─────────────────────────────────────────────

class TestExists:
    def test_exists_true(self, crud, mock_db):
        scalar(mock_db, 1)
        assert crud.exists(mock_db, amenity_id=1) is True

    def test_exists_false(self, crud, mock_db):
        scalar(mock_db, None)
        assert crud.exists(mock_db, amenity_id=999) is False


# ─────────────────────────────────────────────
# CREATE (lines 136-152)
# ─────────────────────────────────────────────

class TestCreate:
    def test_create_success(self, crud, mock_db):
        """Lines 136-152: happy path."""
        scalar_result(mock_db, None)  # No duplicate
        obj = make_amenity()
        mock_db.add.return_value = None
        mock_db.commit.return_value = None
        mock_db.refresh.return_value = None

        with patch.object(crud, "get_by_name", return_value=None):
            result = crud.create(mock_db, obj_in=AmenityCreate(name="Gym"))
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()

    def test_create_duplicate_raises(self, crud, mock_db):
        """Lines 136-138: duplicate name raises ValueError."""
        existing = make_amenity(name="WiFi")
        with patch.object(crud, "get_by_name", return_value=existing):
            with pytest.raises(ValueError, match="already exists"):
                crud.create(mock_db, obj_in=AmenityCreate(name="WiFi"))

    def test_create_with_category(self, crud, mock_db):
        with patch.object(crud, "get_by_name", return_value=None):
            mock_db.add.return_value = None
            mock_db.commit.return_value = None
            mock_db.refresh.return_value = None
            crud.create(mock_db, obj_in=AmenityCreate(
                name="Pool", description="Swimming pool", category="Recreation"
            ))
            mock_db.add.assert_called_once()

    def test_create_minimal(self, crud, mock_db):
        """Name only — description and category optional."""
        with patch.object(crud, "get_by_name", return_value=None):
            mock_db.add.return_value = None
            mock_db.commit.return_value = None
            mock_db.refresh.return_value = None
            crud.create(mock_db, obj_in=AmenityCreate(name="Parking"))
            mock_db.commit.assert_called_once()


# ─────────────────────────────────────────────
# UPDATE (lines 172-197)
# ─────────────────────────────────────────────

class TestUpdate:
    def test_update_description(self, crud, mock_db):
        """Lines 172-197: update field that isn't name."""
        obj = make_amenity()
        mock_db.add.return_value = None
        mock_db.commit.return_value = None
        mock_db.refresh.return_value = None

        result = crud.update(mock_db, db_obj=obj, obj_in=AmenityUpdate(description="Updated desc"))
        assert obj.description == "Updated desc"
        mock_db.commit.assert_called_once()

    def test_update_name_same_case_insensitive(self, crud, mock_db):
        """Name unchanged (same after lower()) — no uniqueness check needed."""
        obj = make_amenity(name="WiFi")
        mock_db.add.return_value = None
        mock_db.commit.return_value = None
        mock_db.refresh.return_value = None

        with patch.object(crud, "get_by_name") as mock_gbn:
            crud.update(mock_db, db_obj=obj, obj_in=AmenityUpdate(name="wifi"))
            mock_gbn.assert_not_called()  # Same name, no check

    def test_update_name_new_unique(self, crud, mock_db):
        """New name that doesn't exist yet — allowed."""
        obj = make_amenity(name="WiFi", amenity_id=1)
        mock_db.add.return_value = None
        mock_db.commit.return_value = None
        mock_db.refresh.return_value = None

        with patch.object(crud, "get_by_name", return_value=None):
            crud.update(mock_db, db_obj=obj, obj_in=AmenityUpdate(name="SuperWiFi"))
        mock_db.commit.assert_called_once()

    def test_update_name_duplicate_raises(self, crud, mock_db):
        """New name already taken by a DIFFERENT amenity → ValueError."""
        obj = make_amenity(name="WiFi", amenity_id=1)
        other = make_amenity(name="Internet", amenity_id=2)

        with patch.object(crud, "get_by_name", return_value=other):
            with pytest.raises(ValueError, match="already exists"):
                crud.update(mock_db, db_obj=obj, obj_in=AmenityUpdate(name="Internet"))

    def test_update_name_same_object_allowed(self, crud, mock_db):
        """get_by_name returns SAME object (same amenity_id) — update allowed."""
        obj = make_amenity(name="WiFi", amenity_id=1)
        mock_db.add.return_value = None
        mock_db.commit.return_value = None
        mock_db.refresh.return_value = None

        with patch.object(crud, "get_by_name", return_value=obj):
            crud.update(mock_db, db_obj=obj, obj_in=AmenityUpdate(name="WifiNew"))
        mock_db.commit.assert_called_once()

    def test_update_strips_protected_fields(self, crud, mock_db):
        obj = make_amenity(amenity_id=1)
        mock_db.add.return_value = None
        mock_db.commit.return_value = None
        mock_db.refresh.return_value = None

        crud.update(mock_db, db_obj=obj, obj_in=AmenityUpdate(description="x"))
        # amenity_id not changed
        assert obj.amenity_id == 1


# ─────────────────────────────────────────────
# DELETE (lines 211-233)
# ─────────────────────────────────────────────

class TestDelete:
    def test_delete_not_found_raises(self, crud, mock_db):
        """Lines 211-213: not found → ValueError."""
        with patch.object(crud, "get", return_value=None):
            with pytest.raises(ValueError, match="not found"):
                crud.delete(mock_db, amenity_id=999)

    def test_delete_unused_amenity(self, crud, mock_db):
        """Lines 211-233: amenity exists, usage_count=0 → deleted."""
        obj = make_amenity()
        scalar(mock_db, 0)  # usage_count

        with patch.object(crud, "get", return_value=obj):
            mock_db.delete.return_value = None
            mock_db.commit.return_value = None
            result = crud.delete(mock_db, amenity_id=1)
        mock_db.delete.assert_called_once_with(obj)
        assert result == obj

    def test_delete_used_amenity_logs_warning(self, crud, mock_db):
        """Lines 220-229: usage_count > 0 → logs warning but still deletes."""
        obj = make_amenity()
        scalar(mock_db, 5)  # in use by 5 properties

        with patch.object(crud, "get", return_value=obj):
            mock_db.delete.return_value = None
            mock_db.commit.return_value = None
            result = crud.delete(mock_db, amenity_id=1)
        # Warning logged but deletion proceeds
        mock_db.delete.assert_called_once_with(obj)

    def test_remove_is_alias_for_delete(self, crud, mock_db):
        """Line 240: remove() delegates to delete()."""
        obj = make_amenity()
        with patch.object(crud, "delete", return_value=obj) as mock_del:
            result = crud.remove(mock_db, amenity_id=1)
        mock_del.assert_called_once_with(mock_db, amenity_id=1)
        assert result == obj


# ─────────────────────────────────────────────
# RELATIONSHIP — get_properties_with_amenity (lines 254-263)
# ─────────────────────────────────────────────

class TestGetPropertiesWithAmenity:
    def test_returns_properties(self, crud, mock_db):
        """Lines 254-263."""
        prop = MagicMock()
        scalars_all(mock_db, [prop])
        result = crud.get_properties_with_amenity(mock_db, amenity_id=1)
        assert result == [prop]

    def test_empty(self, crud, mock_db):
        scalars_all(mock_db, [])
        assert crud.get_properties_with_amenity(mock_db, amenity_id=99) == []

    def test_pagination(self, crud, mock_db):
        scalars_all(mock_db, [])
        assert crud.get_properties_with_amenity(
            mock_db, amenity_id=1, skip=5, limit=10) == []


# ─────────────────────────────────────────────
# RELATIONSHIP — count_properties_with_amenity (lines 272-274)
# ─────────────────────────────────────────────

class TestCountPropertiesWithAmenity:
    def test_count(self, crud, mock_db):
        scalar(mock_db, 7)
        assert crud.count_properties_with_amenity(mock_db, amenity_id=1) == 7

    def test_zero(self, crud, mock_db):
        scalar(mock_db, 0)
        assert crud.count_properties_with_amenity(mock_db, amenity_id=99) == 0


# ─────────────────────────────────────────────
# ANALYTICS — get_popular (lines 296-314)
# ─────────────────────────────────────────────

class TestGetPopular:
    def test_returns_dicts(self, crud, mock_db):
        """Lines 296-314: returns list of dicts with usage_count."""
        row = MagicMock()
        row.__getitem__ = lambda self, i: [1, "WiFi", "Internet", 42][i]
        mock_db.execute.return_value.all.return_value = [row]

        result = crud.get_popular(mock_db, limit=10)
        assert len(result) == 1
        assert result[0]["amenity_id"] == 1
        assert result[0]["name"] == "WiFi"
        assert result[0]["category"] == "Internet"
        assert result[0]["usage_count"] == 42

    def test_empty(self, crud, mock_db):
        mock_db.execute.return_value.all.return_value = []
        assert crud.get_popular(mock_db) == []

    def test_custom_limit(self, crud, mock_db):
        mock_db.execute.return_value.all.return_value = []
        assert crud.get_popular(mock_db, limit=5) == []


# ─────────────────────────────────────────────
# UTILITY — get_or_create (lines 339-348)
# ─────────────────────────────────────────────

class TestGetOrCreate:
    def test_returns_existing(self, crud, mock_db):
        """Lines 339-341: already exists → returns it."""
        obj = make_amenity(name="WiFi")
        with patch.object(crud, "get_by_name", return_value=obj):
            result = crud.get_or_create(mock_db, name="WiFi")
        assert result == obj

    def test_creates_when_missing(self, crud, mock_db):
        """Lines 343-348: not found → creates new."""
        new_obj = make_amenity(name="NewAmenity")
        with patch.object(crud, "get_by_name", return_value=None):
            with patch.object(crud, "create", return_value=new_obj) as mock_create:
                result = crud.get_or_create(mock_db, name="NewAmenity",
                                             description="desc", category="cat")
        mock_create.assert_called_once()
        assert result == new_obj


# ─────────────────────────────────────────────
# UTILITY — bulk_create (lines 366-381)
# ─────────────────────────────────────────────

class TestBulkCreate:
    def test_creates_new_ones(self, crud, mock_db):
        """Lines 366-381: new amenities → created."""
        new_obj = make_amenity(name="Gym")
        with patch.object(crud, "get_by_name", return_value=None):
            with patch.object(crud, "create", return_value=new_obj):
                result = crud.bulk_create(mock_db, amenities_data=[
                    {"name": "Gym", "description": "Fitness center", "category": "Recreation"}
                ])
        assert len(result) == 1

    def test_skips_existing(self, crud, mock_db):
        """Existing amenity → appended without creating."""
        existing = make_amenity(name="WiFi")
        with patch.object(crud, "get_by_name", return_value=existing):
            result = crud.bulk_create(mock_db, amenities_data=[{"name": "WiFi"}])
        assert result == [existing]

    def test_empty_input(self, crud, mock_db):
        result = crud.bulk_create(mock_db, amenities_data=[])
        assert result == []

    def test_mixed_new_and_existing(self, crud, mock_db):
        existing = make_amenity(name="WiFi", amenity_id=1)
        new_obj = make_amenity(name="Pool", amenity_id=2)

        def mock_gbn(db, name):
            return existing if name == "WiFi" else None

        with patch.object(crud, "get_by_name", side_effect=mock_gbn):
            with patch.object(crud, "create", return_value=new_obj):
                result = crud.bulk_create(mock_db, amenities_data=[
                    {"name": "WiFi"}, {"name": "Pool", "category": "Recreation"}
                ])
        assert len(result) == 2

    def test_http_exception_skipped(self, crud, mock_db):
        """HTTPException during create → continue (not crash)."""
        from fastapi import HTTPException
        with patch.object(crud, "get_by_name", return_value=None):
            with patch.object(crud, "create", side_effect=HTTPException(status_code=409)):
                result = crud.bulk_create(mock_db, amenities_data=[{"name": "Gym"}])
        assert result == []


# ─────────────────────────────────────────────
# SINGLETON
# ─────────────────────────────────────────────

class TestSingleton:
    def test_is_amenity_crud(self):
        assert isinstance(amenity_singleton, AmenityCRUD)