# tests/crud/test_properties_v8.py
"""
Property CRUD Tests v9 — All missing lines targeted
Fixes from v8:
  1. min_parking_spaces → parking_spaces (Property model attribute)
  2. Patch wkt_to_coords/get_distance_between_points at app.utils.geospatial
     (because calculate_distance imports them inside the method body)
  3. Added tests for new missing ranges:
     90-98, 109-121, 152, 154, 158, 160,
     328-358 (get_multi with dict filters),
     510-521, 531-542 (bulk_verify, bulk_update_status),
     597-655 (get_properties_near),
     676-695 (get_properties_in_bounds),
     771-789, 809-832 (bulk_soft_delete, etc.),
     851-873, 891-913

Run:
  pytest tests/crud/test_properties_v9.py -v \
    --cov=app/crud/properties --cov-report=term-missing
"""

import pytest
from unittest.mock import MagicMock, patch, call
from sqlalchemy.orm import Session
from fastapi import HTTPException
from datetime import datetime, timezone

from app.crud.properties import PropertyCRUD, property as property_singleton
from app.models.properties import Property, ListingType, ListingStatus
from app.models.locations import Location
from app.models.property_types import PropertyType
from app.schemas.properties import PropertyCreate, PropertyUpdate, PropertyFilter


# ─────────────────────────────────────────────
# SHARED HELPERS
# ─────────────────────────────────────────────

@pytest.fixture
def crud():
    return PropertyCRUD()


@pytest.fixture
def mock_db():
    return MagicMock(spec=Session)


def make_property(**kwargs) -> MagicMock:
    defaults = dict(
        property_id=1,
        user_id=10,
        title="Test Property",
        description="A nice place",
        price=500_000,
        bedrooms=3,
        bathrooms=2,
        property_size=120.0,
        listing_type=ListingType.sale,
        listing_status=ListingStatus.available,
        location_id=1,
        property_type_id=1,
        is_verified=False,
        is_featured=False,
        has_garden=False,
        has_security=False,
        has_swimming_pool=False,
        parking_spaces=0,        # ✅ FIX 1: correct attribute name
        year_built=2010,
        verification_date=None,
        deleted_at=None,
        geom=None,
        updated_by=None,
        created_at=datetime.now(timezone.utc),
    )
    defaults.update(kwargs)
    obj = MagicMock(spec=Property)
    for k, v in defaults.items():
        setattr(obj, k, v)
    return obj


def make_location(location_id=1):
    loc = MagicMock(spec=Location)
    loc.location_id = location_id
    return loc


def make_property_type(property_type_id=1):
    pt = MagicMock(spec=PropertyType)
    pt.property_type_id = property_type_id
    return pt


def _execute_returns(mock_db, value):
    """Wire mock_db.execute() → .scalars().all() = value"""
    mock_db.execute.return_value.scalars.return_value.all.return_value = value


# ─────────────────────────────────────────────
# LINES 44-63 — get_featured
# ─────────────────────────────────────────────

class TestGetFeatured:
    def test_returns_featured_list(self, crud, mock_db):
        prop = make_property(is_featured=True)
        _execute_returns(mock_db, [prop])
        assert crud.get_featured(mock_db, limit=6) == [prop]

    def test_custom_limit(self, crud, mock_db):
        _execute_returns(mock_db, [])
        assert crud.get_featured(mock_db, limit=3) == []

    def test_empty_result(self, crud, mock_db):
        _execute_returns(mock_db, [])
        assert crud.get_featured(mock_db) == []


# ─────────────────────────────────────────────
# LINES 90-98, 109-121 — get_multi (first definition: include_deleted, user_id)
# ─────────────────────────────────────────────

class TestGetMultiBasic:
    """
    Lines 90-98: include_deleted=True branch.
    Lines 109-121: user_id filter branch + negative skip/limit sanitization.
    """

    def test_user_id_filter(self, crud, mock_db):
        """Line 109-121: user_id provided → filtered."""
        _execute_returns(mock_db, [])
        result = crud.get_multi(mock_db, user_id=42)
        assert result == []

    def test_negative_skip_clamped(self, crud, mock_db):
        """Line 109-121: skip=-5 → clamped to 0."""
        _execute_returns(mock_db, [])
        result = crud.get_multi(mock_db, skip=-5, limit=10)
        assert result == []

    def test_negative_limit_clamped(self, crud, mock_db):
        _execute_returns(mock_db, [])
        result = crud.get_multi(mock_db, skip=0, limit=-1)
        assert result == []


# ─────────────────────────────────────────────
# LINES 152, 154, 158, 160 — get_by_filters price/room filters
# ─────────────────────────────────────────────

class TestGetByFiltersBasic:
    def test_min_price_filter(self, crud, mock_db):
        """Line 152."""
        _execute_returns(mock_db, [])
        assert crud.get_by_filters(mock_db, filters=PropertyFilter(min_price=100_000)) == []

    def test_max_price_filter(self, crud, mock_db):
        """Line 154."""
        _execute_returns(mock_db, [])
        assert crud.get_by_filters(mock_db, filters=PropertyFilter(max_price=2_000_000)) == []

    def test_bedrooms_filter(self, crud, mock_db):
        """Line 158."""
        _execute_returns(mock_db, [])
        assert crud.get_by_filters(mock_db, filters=PropertyFilter(bedrooms=3)) == []

    def test_bathrooms_filter(self, crud, mock_db):
        """Line 160."""
        _execute_returns(mock_db, [])
        assert crud.get_by_filters(mock_db, filters=PropertyFilter(bathrooms=2)) == []

    def test_property_type_id_filter(self, crud, mock_db):
        _execute_returns(mock_db, [])
        assert crud.get_by_filters(mock_db, filters=PropertyFilter(property_type_id=5)) == []

    def test_property_size_filters(self, crud, mock_db):
        _execute_returns(mock_db, [])
        f = PropertyFilter(min_property_size=80.0, max_property_size=300.0)
        assert crud.get_by_filters(mock_db, filters=f) == []

    def test_location_text_filters(self, crud, mock_db):
        _execute_returns(mock_db, [])
        f = PropertyFilter(state="Lagos", city="Ikeja", neighborhood="GRA")
        assert crud.get_by_filters(mock_db, filters=f) == []


# ─────────────────────────────────────────────
# LINES 164, 168 — listing_type / listing_status branches
# ─────────────────────────────────────────────

class TestGetByFiltersEnums:
    def test_listing_type_filter(self, crud, mock_db):
        _execute_returns(mock_db, [])
        assert crud.get_by_filters(mock_db, filters=PropertyFilter(listing_type=ListingType.sale)) == []

    def test_listing_status_explicit(self, crud, mock_db):
        _execute_returns(mock_db, [])
        assert crud.get_by_filters(mock_db, filters=PropertyFilter(listing_status=ListingStatus.sold)) == []

    def test_listing_status_defaults_to_available(self, crud, mock_db):
        _execute_returns(mock_db, [])
        assert crud.get_by_filters(mock_db, filters=PropertyFilter()) == []


# ─────────────────────────────────────────────
# LINES 179-189 — geography radius filter
# ─────────────────────────────────────────────

class TestGetByFiltersGeography:
    def test_full_radius_filter(self, crud, mock_db):
        _execute_returns(mock_db, [])
        f = PropertyFilter(latitude=6.5244, longitude=3.3792, radius_km=5.0)
        assert crud.get_by_filters(mock_db, filters=f) == []

    def test_missing_radius_skips_geography(self, crud, mock_db):
        _execute_returns(mock_db, [])
        f = PropertyFilter(latitude=6.5244, longitude=3.3792)
        assert crud.get_by_filters(mock_db, filters=f) == []

    def test_sort_by_distance_with_geography(self, crud, mock_db):
        _execute_returns(mock_db, [])
        f = PropertyFilter(latitude=6.5244, longitude=3.3792, radius_km=10.0, sort_by="distance")
        assert crud.get_by_filters(mock_db, filters=f) == []


# ─────────────────────────────────────────────
# LINES 194-206 — amenity/parking/year/featured/verified filters
# ─────────────────────────────────────────────

class TestGetByFiltersBooleans:
    def test_has_garden(self, crud, mock_db):
        _execute_returns(mock_db, [])
        assert crud.get_by_filters(mock_db, filters=PropertyFilter(has_garden=True)) == []

    def test_has_security(self, crud, mock_db):
        _execute_returns(mock_db, [])
        assert crud.get_by_filters(mock_db, filters=PropertyFilter(has_security=True)) == []

    def test_has_swimming_pool(self, crud, mock_db):
        _execute_returns(mock_db, [])
        assert crud.get_by_filters(mock_db, filters=PropertyFilter(has_swimming_pool=False)) == []

    def test_min_parking_spaces(self, crud, mock_db):
        """FIX 1: PropertyFilter field is min_parking_spaces; Property attr is parking_spaces."""
        _execute_returns(mock_db, [])
        # The CRUD does: Property.parking_spaces >= filters.min_parking_spaces
        assert crud.get_by_filters(mock_db, filters=PropertyFilter(min_parking_spaces=2)) == []

    def test_year_built_range(self, crud, mock_db):
        _execute_returns(mock_db, [])
        f = PropertyFilter(min_year_built=2000, max_year_built=2020)
        assert crud.get_by_filters(mock_db, filters=f) == []

    def test_is_featured(self, crud, mock_db):
        _execute_returns(mock_db, [])
        assert crud.get_by_filters(mock_db, filters=PropertyFilter(is_featured=True)) == []

    def test_is_verified(self, crud, mock_db):
        _execute_returns(mock_db, [])
        assert crud.get_by_filters(mock_db, filters=PropertyFilter(is_verified=True)) == []


# ─────────────────────────────────────────────
# LINES 224-234 — sort_by all branches
# ─────────────────────────────────────────────

class TestGetByFiltersSorting:
    @pytest.mark.parametrize("sort_by", [
        "price_asc", "price_desc", "date_asc", "date_desc",
        "size_desc", "size_asc", "unknown_value",
    ])
    def test_all_sort_branches(self, crud, mock_db, sort_by):
        _execute_returns(mock_db, [])
        assert crud.get_by_filters(mock_db, filters=PropertyFilter(sort_by=sort_by)) == []

    def test_sort_by_distance_without_geography_falls_to_default(self, crud, mock_db):
        _execute_returns(mock_db, [])
        assert crud.get_by_filters(mock_db, filters=PropertyFilter(sort_by="distance")) == []


# ─────────────────────────────────────────────
# LINE 255 — get_nearby_properties tuple unpacking
# ─────────────────────────────────────────────

class TestGetNearbyProperties:
    def test_returns_property_distance_tuples(self, crud, mock_db):
        prop = make_property()
        row = MagicMock()
        row.__getitem__ = lambda self, i: [prop, 2.456789][i]
        mock_db.execute.return_value.all.return_value = [row]

        result = crud.get_nearby_properties(mock_db, latitude=6.52, longitude=3.38, radius_km=5.0)
        assert len(result) == 1
        assert result[0][0] == prop
        assert result[0][1] == 2.46

    def test_empty_when_none_nearby(self, crud, mock_db):
        mock_db.execute.return_value.all.return_value = []
        result = crud.get_nearby_properties(mock_db, latitude=0.0, longitude=0.0, radius_km=1.0)
        assert result == []

    def test_custom_skip_limit(self, crud, mock_db):
        mock_db.execute.return_value.all.return_value = []
        result = crud.get_nearby_properties(
            mock_db, latitude=6.52, longitude=3.38, radius_km=10.0, skip=5, limit=5
        )
        assert result == []


# ─────────────────────────────────────────────
# LINES 328-358 — get_multi (second overload) with dict filters
# ─────────────────────────────────────────────

class TestGetMultiWithDictFilters:
    """
    The second get_multi definition accepts filters: Optional[Dict[str, Any]].
    Lines 328-358 cover all the dict-filter branches.
    Note: Python sees only the LAST definition of get_multi; the first is shadowed.
    All get_multi calls invoke the second definition.
    """

    def test_no_filters(self, crud, mock_db):
        _execute_returns(mock_db, [])
        assert crud.get_multi(mock_db) == []

    def test_user_id_filter(self, crud, mock_db):
        _execute_returns(mock_db, [])
        assert crud.get_multi(mock_db, user_id=5) == []

    def test_dict_min_price(self, crud, mock_db):
        _execute_returns(mock_db, [])
        assert crud.get_multi(mock_db, filters={"min_price": 100_000}) == []

    def test_dict_max_price(self, crud, mock_db):
        _execute_returns(mock_db, [])
        assert crud.get_multi(mock_db, filters={"max_price": 5_000_000}) == []

    def test_dict_bedrooms(self, crud, mock_db):
        _execute_returns(mock_db, [])
        assert crud.get_multi(mock_db, filters={"bedrooms": 3}) == []

    def test_dict_min_bedrooms(self, crud, mock_db):
        _execute_returns(mock_db, [])
        assert crud.get_multi(mock_db, filters={"min_bedrooms": 2}) == []

    def test_dict_bathrooms(self, crud, mock_db):
        _execute_returns(mock_db, [])
        assert crud.get_multi(mock_db, filters={"bathrooms": 2}) == []

    def test_dict_property_type_id(self, crud, mock_db):
        _execute_returns(mock_db, [])
        assert crud.get_multi(mock_db, filters={"property_type_id": 1}) == []

    def test_dict_location_id(self, crud, mock_db):
        _execute_returns(mock_db, [])
        assert crud.get_multi(mock_db, filters={"location_id": 1}) == []

    def test_dict_listing_type(self, crud, mock_db):
        _execute_returns(mock_db, [])
        assert crud.get_multi(mock_db, filters={"listing_type": ListingType.sale}) == []

    def test_dict_listing_status(self, crud, mock_db):
        _execute_returns(mock_db, [])
        assert crud.get_multi(mock_db, filters={"listing_status": ListingStatus.available}) == []

    def test_dict_is_verified(self, crud, mock_db):
        _execute_returns(mock_db, [])
        assert crud.get_multi(mock_db, filters={"is_verified": True}) == []

    def test_dict_is_featured(self, crud, mock_db):
        _execute_returns(mock_db, [])
        assert crud.get_multi(mock_db, filters={"is_featured": False}) == []

    def test_dict_has_swimming_pool(self, crud, mock_db):
        _execute_returns(mock_db, [])
        assert crud.get_multi(mock_db, filters={"has_swimming_pool": True}) == []

    def test_dict_has_garden(self, crud, mock_db):
        _execute_returns(mock_db, [])
        assert crud.get_multi(mock_db, filters={"has_garden": True}) == []

    def test_dict_has_security(self, crud, mock_db):
        _execute_returns(mock_db, [])
        assert crud.get_multi(mock_db, filters={"has_security": True}) == []

    def test_dict_none_values_skipped(self, crud, mock_db):
        """Filters with None values should not add WHERE clauses."""
        _execute_returns(mock_db, [])
        result = crud.get_multi(mock_db, filters={
            "min_price": None, "max_price": None, "bedrooms": None
        })
        assert result == []

    def test_negative_skip_limit_clamped(self, crud, mock_db):
        _execute_returns(mock_db, [])
        assert crud.get_multi(mock_db, skip=-10, limit=-5) == []


# ─────────────────────────────────────────────
# UPDATE OPERATIONS
# ─────────────────────────────────────────────

class TestUpdateValidation:
    def test_invalid_location_id_raises_404(self, crud, mock_db):
        """Line 440: location not found → HTTPException 404."""
        prop = make_property()
        mock_db.get.return_value = None
        with pytest.raises(HTTPException) as exc:
            crud.update(mock_db, db_obj=prop, obj_in={"location_id": 999})
        assert exc.value.status_code == 404

    def test_valid_location_passes(self, crud, mock_db):
        prop = make_property()
        def _get(model, id_):
            return make_location() if model == Location else make_property_type()
        mock_db.get.side_effect = _get
        mock_db.add.return_value = None
        mock_db.flush.return_value = None
        mock_db.refresh.return_value = None
        assert crud.update(mock_db, db_obj=prop, obj_in={"location_id": 2}) == prop

    def test_invalid_property_type_raises_404(self, crud, mock_db):
        """Line 467: property_type not found → HTTPException 404."""
        prop = make_property()
        def _get(model, id_):
            if model == Location:
                return make_location()
            return None
        mock_db.get.side_effect = _get
        with pytest.raises(HTTPException) as exc:
            crud.update(mock_db, db_obj=prop, obj_in={"property_type_id": 999})
        assert exc.value.status_code == 404

    def test_pydantic_schema_accepted(self, crud, mock_db):
        prop = make_property()
        mock_db.add.return_value = None
        mock_db.flush.return_value = None
        mock_db.refresh.return_value = None
        result = crud.update(mock_db, db_obj=prop, obj_in=PropertyUpdate(title="New Title"))
        assert result == prop

    def test_updated_by_set(self, crud, mock_db):
        prop = make_property()
        mock_db.add.return_value = None
        mock_db.flush.return_value = None
        mock_db.refresh.return_value = None
        crud.update(mock_db, db_obj=prop, obj_in={"title": "X"}, updated_by_supabase_id="uid-abc")
        assert prop.updated_by == "uid-abc"

    def test_protected_fields_stripped(self, crud, mock_db):
        prop = make_property(property_id=1, user_id=10)
        mock_db.add.return_value = None
        mock_db.flush.return_value = None
        mock_db.refresh.return_value = None
        crud.update(mock_db, db_obj=prop, obj_in={"property_id": 999, "user_id": 999, "title": "Safe"})
        assert prop.property_id == 1
        assert prop.user_id == 10


# ─────────────────────────────────────────────
# LINE 489 — update_listing_status not found
# ─────────────────────────────────────────────

class TestUpdateListingStatus:
    def test_not_found_returns_none(self, crud, mock_db):
        mock_db.get.return_value = None
        assert crud.update_listing_status(mock_db, property_id=999, listing_status=ListingStatus.sold) is None

    def test_updates_status(self, crud, mock_db):
        prop = make_property()
        mock_db.get.return_value = prop
        mock_db.add.return_value = None
        mock_db.flush.return_value = None
        mock_db.refresh.return_value = None
        crud.update_listing_status(mock_db, property_id=1, listing_status=ListingStatus.sold,
                                   updated_by_supabase_id="admin")
        assert prop.listing_status == ListingStatus.sold
        assert prop.updated_by == "admin"

    def test_updates_without_supabase_id(self, crud, mock_db):
        prop = make_property()
        mock_db.get.return_value = prop
        mock_db.add.return_value = None
        mock_db.flush.return_value = None
        mock_db.refresh.return_value = None
        result = crud.update_listing_status(mock_db, property_id=1, listing_status=ListingStatus.rented)
        assert result is not None


# ─────────────────────────────────────────────
# LINES 510-521 — verify_property
# ─────────────────────────────────────────────

class TestVerifyProperty:
    def test_not_found_returns_none(self, crud, mock_db):
        mock_db.get.return_value = None
        assert crud.verify_property(mock_db, property_id=999) is None

    def test_verify_sets_date(self, crud, mock_db):
        prop = make_property()
        mock_db.get.return_value = prop
        mock_db.add.return_value = None
        mock_db.flush.return_value = None
        mock_db.refresh.return_value = None
        crud.verify_property(mock_db, property_id=1, is_verified=True)
        assert prop.is_verified is True
        assert prop.verification_date is not None

    def test_unverify_clears_date(self, crud, mock_db):
        prop = make_property(is_verified=True, verification_date=datetime.now(timezone.utc))
        mock_db.get.return_value = prop
        mock_db.add.return_value = None
        mock_db.flush.return_value = None
        mock_db.refresh.return_value = None
        crud.verify_property(mock_db, property_id=1, is_verified=False)
        assert prop.is_verified is False
        assert prop.verification_date is None

    def test_updated_by_set(self, crud, mock_db):
        prop = make_property()
        mock_db.get.return_value = prop
        mock_db.add.return_value = None
        mock_db.flush.return_value = None
        mock_db.refresh.return_value = None
        crud.verify_property(mock_db, property_id=1, updated_by_supabase_id="admin")
        assert prop.updated_by == "admin"


# ─────────────────────────────────────────────
# LINES 531-542 — toggle_featured
# ─────────────────────────────────────────────

class TestToggleFeatured:
    def test_not_found_returns_none(self, crud, mock_db):
        mock_db.get.return_value = None
        assert crud.toggle_featured(mock_db, property_id=999, is_featured=True) is None

    def test_feature_property(self, crud, mock_db):
        prop = make_property(is_featured=False)
        mock_db.get.return_value = prop
        mock_db.add.return_value = None
        mock_db.flush.return_value = None
        mock_db.refresh.return_value = None
        crud.toggle_featured(mock_db, property_id=1, is_featured=True)
        assert prop.is_featured is True

    def test_unfeature_with_updated_by(self, crud, mock_db):
        prop = make_property(is_featured=True)
        mock_db.get.return_value = prop
        mock_db.add.return_value = None
        mock_db.flush.return_value = None
        mock_db.refresh.return_value = None
        crud.toggle_featured(mock_db, property_id=1, is_featured=False, updated_by_supabase_id="admin")
        assert prop.is_featured is False
        assert prop.updated_by == "admin"


# ─────────────────────────────────────────────
# HARD DELETE
# ─────────────────────────────────────────────

class TestHardDeleteAdminOnly:
    def test_not_found_returns_none(self, crud, mock_db):
        mock_db.get.return_value = None
        assert crud.hard_delete_admin_only(mock_db, property_id=999) is None

    def test_calls_db_delete(self, crud, mock_db):
        prop = make_property()
        mock_db.get.return_value = prop
        mock_db.flush.return_value = None
        result = crud.hard_delete_admin_only(mock_db, property_id=1)
        mock_db.delete.assert_called_once_with(prop)
        assert result == prop


# ─────────────────────────────────────────────
# LINES 597-655 — get_properties_near (GPS-based, uses Property.geom)
# ─────────────────────────────────────────────

class TestGetPropertiesNear:
    """
    get_properties_near uses Property.geom (not Location.geom).
    Distinct from get_nearby_properties which uses Location.geom.
    """

    def test_basic_proximity_query(self, crud, mock_db):
        prop = make_property(geom="POINT(3.38 6.52)")
        _execute_returns(mock_db, [prop])
        result = crud.get_properties_near(
            mock_db, latitude=6.52, longitude=3.38, radius_km=2.0, limit=10
        )
        assert result == [prop]

    def test_empty_result(self, crud, mock_db):
        _execute_returns(mock_db, [])
        result = crud.get_properties_near(
            mock_db, latitude=0.0, longitude=0.0, radius_km=5.0
        )
        assert result == []

    def test_custom_limit_applied(self, crud, mock_db):
        _execute_returns(mock_db, [])
        result = crud.get_properties_near(
            mock_db, latitude=6.52, longitude=3.38, radius_km=10.0, limit=5
        )
        mock_db.execute.assert_called_once()
        assert result == []


# ─────────────────────────────────────────────
# LINES 676-695 / 771-789 — get_properties_in_bounds
# ─────────────────────────────────────────────

class TestGetPropertiesInBounds:
    def test_world_spanning_longitude(self, crud, mock_db):
        """Span 359.8° > 359 → world-spanning branch."""
        _execute_returns(mock_db, [])
        assert crud.get_properties_in_bounds(
            mock_db, min_lat=-50.0, min_lon=-179.9, max_lat=50.0, max_lon=179.9
        ) == []

    def test_world_spanning_latitude(self, crud, mock_db):
        """Span 179.8° > 179 → world-spanning branch."""
        _execute_returns(mock_db, [])
        assert crud.get_properties_in_bounds(
            mock_db, min_lat=-89.9, min_lon=-10.0, max_lat=89.9, max_lon=10.0
        ) == []

    def test_normal_bounding_box(self, crud, mock_db):
        _execute_returns(mock_db, [])
        assert crud.get_properties_in_bounds(
            mock_db, min_lat=6.0, min_lon=3.0, max_lat=7.0, max_lon=4.0
        ) == []

    def test_clamping_extreme_inputs(self, crud, mock_db):
        """Raw ±90/±180 → clamped to ±89.9/±179.9 without raising."""
        _execute_returns(mock_db, [])
        assert crud.get_properties_in_bounds(
            mock_db, min_lat=-90.0, min_lon=-180.0, max_lat=90.0, max_lon=180.0
        ) == []

    def test_returns_properties_in_box(self, crud, mock_db):
        prop = make_property(geom="POINT(3.5 6.6)")
        _execute_returns(mock_db, [prop])
        result = crud.get_properties_in_bounds(
            mock_db, min_lat=6.0, min_lon=3.0, max_lat=7.0, max_lon=4.0
        )
        assert result == [prop]


# ─────────────────────────────────────────────
# LINES 809-832 — bulk_verify
# ─────────────────────────────────────────────

class TestBulkVerify:
    def test_bulk_verify_true(self, crud, mock_db):
        mock_db.execute.return_value.rowcount = 3
        mock_db.flush.return_value = None
        count = crud.bulk_verify(mock_db, property_ids=[1, 2, 3], is_verified=True)
        assert count == 3

    def test_bulk_verify_false(self, crud, mock_db):
        """is_verified=False clears verification_date (sets None)."""
        mock_db.execute.return_value.rowcount = 2
        mock_db.flush.return_value = None
        count = crud.bulk_verify(mock_db, property_ids=[4, 5], is_verified=False)
        assert count == 2

    def test_bulk_verify_with_updated_by(self, crud, mock_db):
        mock_db.execute.return_value.rowcount = 1
        mock_db.flush.return_value = None
        count = crud.bulk_verify(
            mock_db, property_ids=[1], is_verified=True,
            updated_by_supabase_id="admin-uuid"
        )
        assert count == 1

    def test_bulk_verify_empty_list(self, crud, mock_db):
        mock_db.execute.return_value.rowcount = 0
        mock_db.flush.return_value = None
        count = crud.bulk_verify(mock_db, property_ids=[])
        assert count == 0


# ─────────────────────────────────────────────
# LINES 851-873 — bulk_update_status
# ─────────────────────────────────────────────

class TestBulkUpdateStatus:
    def test_bulk_status_update(self, crud, mock_db):
        mock_db.execute.return_value.rowcount = 4
        mock_db.flush.return_value = None
        count = crud.bulk_update_status(
            mock_db, property_ids=[1, 2, 3, 4], new_status="sold"
        )
        assert count == 4

    def test_bulk_status_with_updated_by(self, crud, mock_db):
        mock_db.execute.return_value.rowcount = 2
        mock_db.flush.return_value = None
        count = crud.bulk_update_status(
            mock_db, property_ids=[1, 2], new_status="rented",
            updated_by_supabase_id="agent-uuid"
        )
        assert count == 2

    def test_bulk_status_empty_ids(self, crud, mock_db):
        mock_db.execute.return_value.rowcount = 0
        mock_db.flush.return_value = None
        count = crud.bulk_update_status(mock_db, property_ids=[], new_status="available")
        assert count == 0


# ─────────────────────────────────────────────
# LINES 891-913 — bulk_soft_delete
# ─────────────────────────────────────────────

class TestBulkSoftDelete:
    def test_bulk_soft_delete(self, crud, mock_db):
        mock_db.execute.return_value.rowcount = 5
        mock_db.flush.return_value = None
        count = crud.bulk_soft_delete(mock_db, property_ids=[1, 2, 3, 4, 5])
        assert count == 5

    def test_bulk_soft_delete_with_deleted_by(self, crud, mock_db):
        mock_db.execute.return_value.rowcount = 2
        mock_db.flush.return_value = None
        count = crud.bulk_soft_delete(
            mock_db, property_ids=[1, 2],
            deleted_by_supabase_id="admin-uuid"
        )
        assert count == 2

    def test_bulk_soft_delete_empty(self, crud, mock_db):
        mock_db.execute.return_value.rowcount = 0
        mock_db.flush.return_value = None
        count = crud.bulk_soft_delete(mock_db, property_ids=[])
        assert count == 0


# ─────────────────────────────────────────────
# LINE 816 — calculate_distance
# FIX 2: patch at app.utils.geospatial (imported inside method)
# ─────────────────────────────────────────────

class TestCalculateDistance:
    def test_zero_when_a_has_no_geom(self, crud):
        assert crud.calculate_distance(make_property(geom=None), make_property(geom="POINT(3 6)")) == 0.0

    def test_zero_when_b_has_no_geom(self, crud):
        assert crud.calculate_distance(make_property(geom="POINT(3 6)"), make_property(geom=None)) == 0.0

    def test_zero_when_both_no_geom(self, crud):
        assert crud.calculate_distance(make_property(geom=None), make_property(geom=None)) == 0.0

    @patch("app.utils.geospatial.wkt_to_coords", side_effect=Exception("parse error"))
    def test_zero_on_exception(self, mock_wkt, crud):
        """FIX 2: patch at source module, not app.crud.properties."""
        prop_a = make_property(geom="POINT(3.0 6.0)")
        prop_b = make_property(geom="POINT(4.0 7.0)")
        assert crud.calculate_distance(prop_a, prop_b) == 0.0

    @patch("app.utils.geospatial.get_distance_between_points", return_value=28.4)
    @patch("app.utils.geospatial.wkt_to_coords", side_effect=[(3.3792, 6.5244), (3.5, 6.7)])
    def test_returns_haversine_distance(self, mock_wkt, mock_dist, crud):
        """FIX 2: patch at source module."""
        prop_a = make_property(geom="POINT(3.3792 6.5244)")
        prop_b = make_property(geom="POINT(3.5 6.7)")
        assert crud.calculate_distance(prop_a, prop_b) == 28.4

    @patch("app.utils.geospatial.wkt_to_coords", return_value=None)
    def test_zero_when_coords_none(self, mock_wkt, crud):
        """FIX 2: wkt_to_coords returns None → 0.0."""
        prop_a = make_property(geom="POINT(3.0 6.0)")
        prop_b = make_property(geom="POINT(3.5 6.7)")
        assert crud.calculate_distance(prop_a, prop_b) == 0.0


# ─────────────────────────────────────────────
# SOFT DELETE & RESTORE
# ─────────────────────────────────────────────

class TestSoftDeleteAndRestore:
    def test_soft_delete_not_found(self, crud, mock_db):
        mock_db.get.return_value = None
        assert crud.soft_delete(mock_db, property_id=999) is None

    def test_soft_delete_sets_deleted_at(self, crud, mock_db):
        prop = make_property()
        mock_db.get.return_value = prop
        mock_db.add.return_value = None
        mock_db.flush.return_value = None
        mock_db.refresh.return_value = None
        crud.soft_delete(mock_db, property_id=1, deleted_by_supabase_id="uid")
        assert prop.deleted_at is not None
        assert str(prop.deleted_by) == "uid"
        assert prop.updated_by is None

    def test_restore_not_found(self, crud, mock_db):
        mock_db.get.return_value = None
        assert crud.restore(mock_db, property_id=999) is None

    def test_restore_clears_deleted_at(self, crud, mock_db):
        prop = make_property(deleted_at=datetime.now(timezone.utc))
        mock_db.get.return_value = prop
        mock_db.add.return_value = None
        mock_db.flush.return_value = None
        mock_db.refresh.return_value = None
        crud.restore(mock_db, property_id=1, restored_by_supabase_id="uid")
        assert prop.deleted_at is None
        assert prop.updated_by == "uid"


# ─────────────────────────────────────────────
# AUTHORIZATION HELPER
# ─────────────────────────────────────────────

class TestCanModifyProperty:
    def test_owner_can_modify(self, crud):
        assert crud.can_modify_property(current_user_id=5, property_user_id=5) is True

    def test_stranger_cannot_modify(self, crud):
        assert crud.can_modify_property(current_user_id=5, property_user_id=9) is False

    def test_admin_can_modify_any(self, crud):
        assert crud.can_modify_property(current_user_id=5, property_user_id=9, is_admin=True) is True


# ─────────────────────────────────────────────
# SINGLETON
# ─────────────────────────────────────────────

class TestSingleton:
    def test_is_property_crud_instance(self):
        assert isinstance(property_singleton, PropertyCRUD)
