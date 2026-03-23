# tests/crud/test_property_types.py
"""
PropertyType CRUD Tests — Full coverage targeting 85%+
Missing lines: 28, 35, 49-51, 58, 74-83, 89, 95, 116-141,
               161-198, 212-264, 271, 282-299, 323-328, 347-388
"""

import pytest
from unittest.mock import MagicMock, patch
from sqlalchemy.orm import Session

from app.crud.property_types import PropertyTypeCRUD, property_type as pt_singleton
from app.models.property_types import PropertyType
from app.schemas.property_types import PropertyTypeCreate, PropertyTypeUpdate


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

@pytest.fixture
def crud():
    return PropertyTypeCRUD()


@pytest.fixture
def mock_db():
    return MagicMock(spec=Session)


def make_pt(**kwargs) -> MagicMock:
    defaults = dict(property_type_id=1, name="Apartment", description="Apartment type")
    defaults.update(kwargs)
    obj = MagicMock(spec=PropertyType)
    for k, v in defaults.items():
        setattr(obj, k, v)
    return obj


def scalar_result(mock_db, value):
    mock_db.execute.return_value.scalar_one_or_none.return_value = value


def scalars_all(mock_db, value):
    mock_db.execute.return_value.scalars.return_value.all.return_value = value


def scalar(mock_db, value):
    mock_db.execute.return_value.scalar.return_value = value


# ─────────────────────────────────────────────
# READ — get (line 28)
# ─────────────────────────────────────────────

class TestGet:
    def test_returns_property_type(self, crud, mock_db):
        obj = make_pt()
        mock_db.get.return_value = obj
        assert crud.get(mock_db, property_type_id=1) == obj

    def test_returns_none(self, crud, mock_db):
        mock_db.get.return_value = None
        assert crud.get(mock_db, property_type_id=999) is None


# ─────────────────────────────────────────────
# READ — get_by_name (line 35)
# ─────────────────────────────────────────────

class TestGetByName:
    def test_found(self, crud, mock_db):
        obj = make_pt()
        scalar_result(mock_db, obj)
        assert crud.get_by_name(mock_db, name="Apartment") == obj

    def test_not_found(self, crud, mock_db):
        scalar_result(mock_db, None)
        assert crud.get_by_name(mock_db, name="Spaceship") is None

    def test_case_insensitive(self, crud, mock_db):
        obj = make_pt(name="apartment")
        scalar_result(mock_db, obj)
        assert crud.get_by_name(mock_db, name="APARTMENT") == obj


# ─────────────────────────────────────────────
# READ — get_multi (lines 49-51)
# ─────────────────────────────────────────────

class TestGetMulti:
    def test_returns_list(self, crud, mock_db):
        items = [make_pt(property_type_id=i) for i in range(3)]
        scalars_all(mock_db, items)
        assert crud.get_multi(mock_db) == items

    def test_pagination(self, crud, mock_db):
        scalars_all(mock_db, [])
        assert crud.get_multi(mock_db, skip=5, limit=10) == []

    def test_empty(self, crud, mock_db):
        scalars_all(mock_db, [])
        assert crud.get_multi(mock_db) == []


# ─────────────────────────────────────────────
# READ — get_all (line 58)
# ─────────────────────────────────────────────

class TestGetAll:
    def test_returns_all(self, crud, mock_db):
        items = [make_pt(property_type_id=i) for i in range(5)]
        scalars_all(mock_db, items)
        assert crud.get_all(mock_db) == items

    def test_custom_limit(self, crud, mock_db):
        scalars_all(mock_db, [])
        assert crud.get_all(mock_db, limit=10) == []


# ─────────────────────────────────────────────
# READ — search (lines 74-83)
# ─────────────────────────────────────────────

class TestSearch:
    def test_matches_by_name(self, crud, mock_db):
        obj = make_pt(name="Studio Apartment")
        scalars_all(mock_db, [obj])
        result = crud.search(mock_db, search_term="studio")
        assert result == [obj]

    def test_no_matches(self, crud, mock_db):
        scalars_all(mock_db, [])
        assert crud.search(mock_db, search_term="zzznothing") == []

    def test_pagination(self, crud, mock_db):
        scalars_all(mock_db, [])
        assert crud.search(mock_db, search_term="house", skip=0, limit=5) == []

    def test_searches_description_too(self, crud, mock_db):
        """or_ clause: description.ilike also searched."""
        obj = make_pt(description="Single detached residential unit")
        scalars_all(mock_db, [obj])
        result = crud.search(mock_db, search_term="detached")
        assert result == [obj]


# ─────────────────────────────────────────────
# READ — count (line 89)
# ─────────────────────────────────────────────

class TestCount:
    def test_returns_count(self, crud, mock_db):
        scalar(mock_db, 12)
        assert crud.count(mock_db) == 12

    def test_zero(self, crud, mock_db):
        scalar(mock_db, 0)
        assert crud.count(mock_db) == 0


# ─────────────────────────────────────────────
# READ — exists (line 95)
# ─────────────────────────────────────────────

class TestExists:
    def test_exists_true(self, crud, mock_db):
        scalar(mock_db, 1)
        assert crud.exists(mock_db, property_type_id=1) is True

    def test_exists_false(self, crud, mock_db):
        scalar(mock_db, None)
        assert crud.exists(mock_db, property_type_id=999) is False


# ─────────────────────────────────────────────
# CREATE (lines 116-141)
# ─────────────────────────────────────────────

class TestCreate:
    def test_create_success(self, crud, mock_db):
        with patch.object(crud, "get_by_name", return_value=None):
            mock_db.add.return_value = None
            mock_db.flush.return_value = None
            mock_db.refresh.return_value = None
            crud.create(mock_db, obj_in=PropertyTypeCreate(name="Penthouse"))
        mock_db.flush.assert_called_once()

    def test_create_with_description(self, crud, mock_db):
        with patch.object(crud, "get_by_name", return_value=None):
            mock_db.add.return_value = None
            mock_db.flush.return_value = None
            mock_db.refresh.return_value = None
            crud.create(mock_db, obj_in=PropertyTypeCreate(
                name="Villa", description="Luxury standalone"
            ))
        mock_db.add.assert_called_once()

    def test_create_duplicate_raises(self, crud, mock_db):
        existing = make_pt(name="Apartment")
        with patch.object(crud, "get_by_name", return_value=existing):
            with pytest.raises(ValueError, match="already exists"):
                crud.create(mock_db, obj_in=PropertyTypeCreate(name="Apartment"))

    def test_create_logs_success(self, crud, mock_db):
        """Lines 133-141: logger.info called after create."""
        with patch.object(crud, "get_by_name", return_value=None):
            mock_db.add.return_value = None
            mock_db.flush.return_value = None
            new_obj = make_pt(property_type_id=5, name="Loft")
            mock_db.refresh.side_effect = lambda o: None

            with patch("app.crud.property_types.logger") as mock_logger:
                crud.create(mock_db, obj_in=PropertyTypeCreate(name="Loft"))
            mock_logger.info.assert_called_once()


# ─────────────────────────────────────────────
# UPDATE (lines 161-198)
# ─────────────────────────────────────────────

class TestUpdate:
    def test_update_description(self, crud, mock_db):
        obj = make_pt(name="Apartment", property_type_id=1)
        mock_db.add.return_value = None
        mock_db.flush.return_value = None
        mock_db.refresh.return_value = None

        crud.update(mock_db, db_obj=obj, obj_in=PropertyTypeUpdate(description="New desc"))
        assert obj.description == "New desc"
        mock_db.flush.assert_called_once()

    def test_update_name_same_case(self, crud, mock_db):
        """Same name (case-insensitive) → no uniqueness check."""
        obj = make_pt(name="Apartment", property_type_id=1)
        mock_db.add.return_value = None
        mock_db.flush.return_value = None
        mock_db.refresh.return_value = None

        with patch.object(crud, "get_by_name") as mock_gbn:
            crud.update(mock_db, db_obj=obj, obj_in=PropertyTypeUpdate(name="apartment"))
            mock_gbn.assert_not_called()

    def test_update_name_new_unique(self, crud, mock_db):
        obj = make_pt(name="Apartment", property_type_id=1)
        mock_db.add.return_value = None
        mock_db.flush.return_value = None
        mock_db.refresh.return_value = None

        with patch.object(crud, "get_by_name", return_value=None):
            crud.update(mock_db, db_obj=obj, obj_in=PropertyTypeUpdate(name="Studio"))
        mock_db.flush.assert_called_once()

    def test_update_name_duplicate_raises(self, crud, mock_db):
        obj = make_pt(name="Apartment", property_type_id=1)
        other = make_pt(name="Villa", property_type_id=2)

        with patch.object(crud, "get_by_name", return_value=other):
            with pytest.raises(ValueError, match="already exists"):
                crud.update(mock_db, db_obj=obj, obj_in=PropertyTypeUpdate(name="Villa"))

    def test_update_name_same_object_allowed(self, crud, mock_db):
        """Uniqueness check finds same object → update OK."""
        obj = make_pt(name="Apartment", property_type_id=1)
        mock_db.add.return_value = None
        mock_db.flush.return_value = None
        mock_db.refresh.return_value = None

        with patch.object(crud, "get_by_name", return_value=obj):
            crud.update(mock_db, db_obj=obj, obj_in=PropertyTypeUpdate(name="ApartmentPlus"))
        mock_db.flush.assert_called_once()

    def test_update_logs(self, crud, mock_db):
        """Lines 190-198: logger.info on successful update."""
        obj = make_pt(name="Apartment", property_type_id=1)
        mock_db.add.return_value = None
        mock_db.flush.return_value = None
        mock_db.refresh.return_value = None

        with patch("app.crud.property_types.logger") as mock_logger:
            crud.update(mock_db, db_obj=obj, obj_in=PropertyTypeUpdate(description="x"))
        mock_logger.info.assert_called_once()

    def test_update_strips_protected_fields(self, crud, mock_db):
        obj = make_pt(property_type_id=1)
        mock_db.add.return_value = None
        mock_db.flush.return_value = None
        mock_db.refresh.return_value = None
        crud.update(mock_db, db_obj=obj, obj_in=PropertyTypeUpdate(description="safe"))
        assert obj.property_type_id == 1


# ─────────────────────────────────────────────
# DELETE (lines 212-264)
# ─────────────────────────────────────────────

class TestDelete:
    def test_not_found_raises(self, crud, mock_db):
        """Lines 212-214: not found → ValueError."""
        with patch.object(crud, "get", return_value=None):
            with pytest.raises(ValueError, match="not found"):
                crud.delete(mock_db, property_type_id=999)

    def test_delete_unused_success(self, crud, mock_db):
        """Lines 212-250: unused type → deleted + logged."""
        obj = make_pt(property_type_id=1)
        scalar(mock_db, 0)  # usage_count = 0

        with patch.object(crud, "get", return_value=obj):
            mock_db.delete.return_value = None
            mock_db.flush.return_value = None
            with patch("app.crud.property_types.logger"):
                result = crud.delete(mock_db, property_type_id=1)
        mock_db.delete.assert_called_once_with(obj)
        assert result == obj

    def test_delete_in_use_raises(self, crud, mock_db):
        """Lines 232-241: usage_count > 0 → ValueError with usage count."""
        obj = make_pt(property_type_id=1)
        scalar(mock_db, 3)  # in use

        with patch.object(crud, "get", return_value=obj):
            with patch("app.crud.property_types.logger"):
                with pytest.raises(ValueError, match="3 properties"):
                    crud.delete(mock_db, property_type_id=1)

    def test_delete_unexpected_exception_wrapped(self, crud, mock_db):
        """Lines 253-264: unexpected exception → wrapped ValueError."""
        obj = make_pt(property_type_id=1)

        with patch.object(crud, "get", return_value=obj):
            mock_db.execute.side_effect = RuntimeError("DB exploded")
            with patch("app.crud.property_types.logger"):
                with pytest.raises(ValueError, match="Failed to delete"):
                    crud.delete(mock_db, property_type_id=1)

    def test_remove_delegates_to_delete(self, crud, mock_db):
        """Line 271: remove() is alias for delete()."""
        obj = make_pt()
        with patch.object(crud, "delete", return_value=obj) as mock_del:
            result = crud.remove(mock_db, property_type_id=1)
        mock_del.assert_called_once_with(mock_db, property_type_id=1)
        assert result == obj


# ─────────────────────────────────────────────
# ANALYTICS — get_usage_stats (lines 282-299)
# ─────────────────────────────────────────────

class TestGetUsageStats:
    def test_returns_dicts(self, crud, mock_db):
        """Lines 282-299: rows → list of dicts."""
        row = MagicMock()
        row.__getitem__ = lambda self, i: [1, "Apartment", 15][i]
        mock_db.execute.return_value.all.return_value = [row]

        result = crud.get_usage_stats(mock_db)
        assert len(result) == 1
        assert result[0]["property_type_id"] == 1
        assert result[0]["name"] == "Apartment"
        assert result[0]["property_count"] == 15

    def test_empty(self, crud, mock_db):
        mock_db.execute.return_value.all.return_value = []
        assert crud.get_usage_stats(mock_db) == []

    def test_includes_zero_usage_types(self, crud, mock_db):
        """OUTER JOIN means types with 0 properties are included."""
        row = MagicMock()
        row.__getitem__ = lambda self, i: [2, "Warehouse", 0][i]
        mock_db.execute.return_value.all.return_value = [row]

        result = crud.get_usage_stats(mock_db)
        assert result[0]["property_count"] == 0


# ─────────────────────────────────────────────
# UTILITY — get_or_create (lines 323-328)
# ─────────────────────────────────────────────

class TestGetOrCreate:
    def test_returns_existing(self, crud, mock_db):
        obj = make_pt(name="House")
        with patch.object(crud, "get_by_name", return_value=obj):
            result = crud.get_or_create(mock_db, name="House")
        assert result == obj

    def test_creates_when_missing(self, crud, mock_db):
        new_obj = make_pt(name="Bungalow")
        with patch.object(crud, "get_by_name", return_value=None):
            with patch.object(crud, "create", return_value=new_obj) as mock_create:
                result = crud.get_or_create(mock_db, name="Bungalow", description="desc")
        mock_create.assert_called_once()
        assert result == new_obj


# ─────────────────────────────────────────────
# UTILITY — bulk_create (lines 347-388)
# ─────────────────────────────────────────────

class TestBulkCreate:
    def test_creates_new(self, crud, mock_db):
        new_obj = make_pt(name="Duplex")
        with patch.object(crud, "get_by_name", return_value=None):
            with patch.object(crud, "create", return_value=new_obj):
                result = crud.bulk_create(mock_db, types_data=[
                    {"name": "Duplex", "description": "Two units"}
                ])
        assert len(result) == 1

    def test_skips_existing(self, crud, mock_db):
        existing = make_pt(name="Apartment")
        with patch.object(crud, "get_by_name", return_value=existing):
            result = crud.bulk_create(mock_db, types_data=[{"name": "Apartment"}])
        assert result == [existing]

    def test_empty_input(self, crud, mock_db):
        result = crud.bulk_create(mock_db, types_data=[])
        assert result == []

    def test_value_error_skipped_with_log(self, crud, mock_db):
        """Lines 363-371: ValueError during create → logged + skipped."""
        with patch.object(crud, "get_by_name", return_value=None):
            with patch.object(crud, "create", side_effect=ValueError("already exists")):
                with patch("app.crud.property_types.logger") as mock_logger:
                    result = crud.bulk_create(mock_db, types_data=[{"name": "Apartment"}])
        assert result == []
        mock_logger.warning.assert_called_once()

    def test_unexpected_exception_skipped_with_log(self, crud, mock_db):
        """Lines 372-381: unexpected Exception → logged + skipped."""
        with patch.object(crud, "get_by_name", return_value=None):
            with patch.object(crud, "create", side_effect=RuntimeError("DB error")):
                with patch("app.crud.property_types.logger") as mock_logger:
                    result = crud.bulk_create(mock_db, types_data=[{"name": "Apartment"}])
        assert result == []
        mock_logger.error.assert_called_once()

    def test_logs_completion(self, crud, mock_db):
        """Lines 383-388: logger.info called at end."""
        new_obj = make_pt(name="Studio")
        with patch.object(crud, "get_by_name", return_value=None):
            with patch.object(crud, "create", return_value=new_obj):
                with patch("app.crud.property_types.logger") as mock_logger:
                    crud.bulk_create(mock_db, types_data=[{"name": "Studio"}])
        mock_logger.info.assert_called()

    def test_mixed_create_and_skip(self, crud, mock_db):
        existing = make_pt(name="Apartment", property_type_id=1)
        new_obj = make_pt(name="Villa", property_type_id=2)

        def mock_gbn(db, name):
            return existing if name == "Apartment" else None

        with patch.object(crud, "get_by_name", side_effect=mock_gbn):
            with patch.object(crud, "create", return_value=new_obj):
                result = crud.bulk_create(mock_db, types_data=[
                    {"name": "Apartment"}, {"name": "Villa"}
                ])
        assert len(result) == 2


# ─────────────────────────────────────────────
# SINGLETON
# ─────────────────────────────────────────────

class TestSingleton:
    def test_is_property_type_crud(self):
        assert isinstance(pt_singleton, PropertyTypeCRUD)
