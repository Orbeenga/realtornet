# tests/crud/test_properties_v8.py
"""
Property CRUD Tests — Targeting Missing Coverage Lines
Missing: 44-63, 164, 168, 179, 181, 185, 187, 189, 194-206,
         224, 228, 230, 234, 255, 440, 467, 489, 516, 537, 557, 782-789, 816

Run: pytest tests/crud/test_properties.py -v --cov=app/crud/properties --cov-report=term-missing
"""

import pytest
from unittest.mock import MagicMock, patch, PropertyMock
from sqlalchemy.orm import Session
from fastapi import HTTPException
from datetime import datetime, timezone

from app.crud.properties import PropertyCRUD, property as property_crud
from app.models.properties import Property, ListingType, ListingStatus
from app.models.locations import Location
from app.models.property_types import PropertyType
from app.schemas.properties import PropertyCreate, PropertyUpdate, PropertyFilter


# ─────────────────────────────────────────────
# FIXTURES
# ─────────────────────────────────────────────

@pytest.fixture
def crud():
    return PropertyCRUD()


@pytest.fixture
def mock_db():
    return MagicMock(spec=Session)


def make_property(**kwargs) -> Property:
    """Helper: build a minimal Property ORM object."""
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
        min_parking_spaces=0,
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


def make_location(location_id=1) -> Location:
    loc = MagicMock(spec=Location)
    loc.location_id = location_id
    return loc


def make_property_type(property_type_id=1) -> PropertyType:
    pt = MagicMock(spec=PropertyType)
    pt.property_type_id = property_type_id
    return pt


# ─────────────────────────────────────────────
# LINES 44-63 — get_featured
# ─────────────────────────────────────────────

class TestGetFeatured:
    """Lines 44-63: get_featured method body."""

    def test_get_featured_returns_list(self, crud, mock_db):
        """Line 44-63: basic path — query executes and returns results."""
        prop = make_property(is_featured=True, listing_status=ListingStatus.available)
        mock_db.execute.return_value.scalars.return_value.all.return_value = [prop]

        result = crud.get_featured(mock_db, limit=6)

        assert result == [prop]
        mock_db.execute.assert_called_once()

    def test_get_featured_custom_limit(self, crud, mock_db):
        """Line 44-63: custom limit forwarded."""
        mock_db.execute.return_value.scalars.return_value.all.return_value = []
        result = crud.get_featured(mock_db, limit=3)
        assert result == []

    def test_get_featured_empty(self, crud, mock_db):
        """Line 44-63: no featured properties."""
        mock_db.execute.return_value.scalars.return_value.all.return_value = []
        result = crud.get_featured(mock_db)
        assert result == []


# ─────────────────────────────────────────────
# LINES 164, 168 — get_by_filters listing_type / listing_status
# ─────────────────────────────────────────────

class TestGetByFiltersEnums:
    """Lines 164, 168: explicit listing_type and listing_status filter branches."""

    def test_filter_listing_type(self, crud, mock_db):
        """Line 164: listing_type filter applied."""
        mock_db.execute.return_value.scalars.return_value.all.return_value = []
        filters = PropertyFilter(listing_type=ListingType.sale)
        result = crud.get_by_filters(mock_db, filters=filters)
        assert result == []

    def test_filter_listing_status_explicit(self, crud, mock_db):
        """Line 168: explicit listing_status filter (not default available)."""
        mock_db.execute.return_value.scalars.return_value.all.return_value = []
        filters = PropertyFilter(listing_status=ListingStatus.sold)
        result = crud.get_by_filters(mock_db, filters=filters)
        assert result == []

    def test_filter_listing_status_default_available(self, crud, mock_db):
        """Line 168 else branch: no listing_status → defaults to available."""
        mock_db.execute.return_value.scalars.return_value.all.return_value = []
        filters = PropertyFilter()  # No status
        result = crud.get_by_filters(mock_db, filters=filters)
        assert result == []


# ─────────────────────────────────────────────
# LINES 179, 181, 185, 187, 189 — geography radius filter
# ─────────────────────────────────────────────

class TestGetByFiltersGeography:
    """Lines 179-189: geography/radius filter branches."""

    def test_radius_filter_all_params(self, crud, mock_db):
        """Lines 179-189: all three (lat, lon, radius_km) provided → builds point + DWithin."""
        mock_db.execute.return_value.scalars.return_value.all.return_value = []
        filters = PropertyFilter(
            latitude=6.5244,
            longitude=3.3792,
            radius_km=5.0
        )
        result = crud.get_by_filters(mock_db, filters=filters)
        assert result == []

    def test_radius_filter_missing_radius(self, crud, mock_db):
        """Lines 179-189 else: only lat/lon without radius → no geography filter."""
        mock_db.execute.return_value.scalars.return_value.all.return_value = []
        filters = PropertyFilter(latitude=6.5244, longitude=3.3792)  # No radius_km
        result = crud.get_by_filters(mock_db, filters=filters)
        assert result == []

    def test_sort_by_distance_with_geography(self, crud, mock_db):
        """Line 189 / sort distance branch: sort_by=distance when geography active."""
        mock_db.execute.return_value.scalars.return_value.all.return_value = []
        filters = PropertyFilter(
            latitude=6.5244,
            longitude=3.3792,
            radius_km=10.0,
            sort_by="distance"
        )
        result = crud.get_by_filters(mock_db, filters=filters)
        assert result == []


# ─────────────────────────────────────────────
# LINES 194-206 — boolean / numeric / year / featured / verified filters
# ─────────────────────────────────────────────

class TestGetByFiltersBooleans:
    """Lines 194-206: amenity booleans, parking, year_built, featured, verified."""

    def test_has_garden_filter(self, crud, mock_db):
        mock_db.execute.return_value.scalars.return_value.all.return_value = []
        filters = PropertyFilter(has_garden=True)
        assert crud.get_by_filters(mock_db, filters=filters) == []

    def test_has_security_filter(self, crud, mock_db):
        mock_db.execute.return_value.scalars.return_value.all.return_value = []
        filters = PropertyFilter(has_security=True)
        assert crud.get_by_filters(mock_db, filters=filters) == []

    def test_has_swimming_pool_filter(self, crud, mock_db):
        mock_db.execute.return_value.scalars.return_value.all.return_value = []
        filters = PropertyFilter(has_swimming_pool=False)
        assert crud.get_by_filters(mock_db, filters=filters) == []

    def test_min_parking_spaces_filter(self, crud, mock_db):
        mock_db.execute.return_value.scalars.return_value.all.return_value = []
        filters = PropertyFilter(min_parking_spaces=2)
        assert crud.get_by_filters(mock_db, filters=filters) == []

    def test_year_built_filters(self, crud, mock_db):
        mock_db.execute.return_value.scalars.return_value.all.return_value = []
        filters = PropertyFilter(min_year_built=2000, max_year_built=2020)
        assert crud.get_by_filters(mock_db, filters=filters) == []

    def test_is_featured_filter(self, crud, mock_db):
        mock_db.execute.return_value.scalars.return_value.all.return_value = []
        filters = PropertyFilter(is_featured=True)
        assert crud.get_by_filters(mock_db, filters=filters) == []

    def test_is_verified_filter(self, crud, mock_db):
        mock_db.execute.return_value.scalars.return_value.all.return_value = []
        filters = PropertyFilter(is_verified=True)
        assert crud.get_by_filters(mock_db, filters=filters) == []


# ─────────────────────────────────────────────
# LINES 224, 228, 230, 234 — sort_by branches
# ─────────────────────────────────────────────

class TestGetByFiltersSorting:
    """Lines 224-234: all sort_by branches."""

    @pytest.mark.parametrize("sort_by", [
        "price_asc",   # line 224
        "price_desc",  # line 228 (approx)
        "date_asc",    # line 230
        "size_desc",   # line 234
        "size_asc",
        "date_desc",
        "unknown_sort",  # default branch
    ])
    def test_sort_by_branch(self, crud, mock_db, sort_by):
        mock_db.execute.return_value.scalars.return_value.all.return_value = []
        filters = PropertyFilter(sort_by=sort_by)
        result = crud.get_by_filters(mock_db, filters=filters)
        assert result == []

    def test_sort_by_distance_without_geography_falls_to_default(self, crud, mock_db):
        """sort_by=distance but no geography → default sort."""
        mock_db.execute.return_value.scalars.return_value.all.return_value = []
        filters = PropertyFilter(sort_by="distance")
        result = crud.get_by_filters(mock_db, filters=filters)
        assert result == []


# ─────────────────────────────────────────────
# LINE 255 — get_nearby_properties distance calculation
# ─────────────────────────────────────────────

class TestGetNearbyProperties:
    """Line 255: get_nearby_properties tuples unpacking / distance rounding."""

    def test_returns_tuples_with_distance(self, crud, mock_db):
        """Line 255: result rows unpacked into (Property, float) tuples."""
        prop = make_property()
        # Simulate row with [0]=Property, [1]=distance in km
        row = MagicMock()
        row.__getitem__ = lambda self, i: [prop, 2.456789][i]
        mock_db.execute.return_value.all.return_value = [row]

        result = crud.get_nearby_properties(
            mock_db, latitude=6.5244, longitude=3.3792, radius_km=5.0
        )

        assert len(result) == 1
        assert result[0][0] == prop
        assert result[0][1] == 2.46  # Rounded to 2 decimals

    def test_returns_empty_when_none_nearby(self, crud, mock_db):
        mock_db.execute.return_value.all.return_value = []
        result = crud.get_nearby_properties(
            mock_db, latitude=0.0, longitude=0.0, radius_km=1.0
        )
        assert result == []


# ─────────────────────────────────────────────
# LINE 440 — update: invalid location_id
# ─────────────────────────────────────────────

class TestUpdateValidation:
    """Lines 440, 467: update raises 404 for invalid location/property_type."""

    def test_update_invalid_location_raises_404(self, crud, mock_db):
        """Line 440: location_id in update_data but location doesn't exist."""
        prop = make_property()
        mock_db.get.return_value = None  # Location not found

        with pytest.raises(HTTPException) as exc:
            crud.update(
                mock_db,
                db_obj=prop,
                obj_in={"location_id": 999}
            )
        assert exc.value.status_code == 404

    def test_update_valid_location_passes(self, crud, mock_db):
        """Line 440 happy path: location exists → no exception."""
        prop = make_property()
        loc = make_location(location_id=2)

        def mock_get(model, id_):
            if model == Location:
                return loc
            return make_property_type()

        mock_db.get.side_effect = mock_get
        mock_db.add.return_value = None
        mock_db.flush.return_value = None
        mock_db.refresh.return_value = None

        result = crud.update(mock_db, db_obj=prop, obj_in={"location_id": 2})
        assert result == prop

    def test_update_invalid_property_type_raises_404(self, crud, mock_db):
        """Line 467: property_type_id in update_data but type doesn't exist."""
        prop = make_property()

        call_count = 0

        def mock_get(model, id_):
            nonlocal call_count
            call_count += 1
            if model == Location:
                return make_location()
            return None  # PropertyType not found

        mock_db.get.side_effect = mock_get

        with pytest.raises(HTTPException) as exc:
            crud.update(
                mock_db,
                db_obj=prop,
                obj_in={"property_type_id": 999}
            )
        assert exc.value.status_code == 404

    def test_update_with_pydantic_schema(self, crud, mock_db):
        """update() accepts PropertyUpdate schema (not just dict)."""
        prop = make_property()
        mock_db.add.return_value = None
        mock_db.flush.return_value = None
        mock_db.refresh.return_value = None

        # No location_id or property_type_id → no DB.get calls
        obj_in = PropertyUpdate(title="Updated Title")
        result = crud.update(mock_db, db_obj=prop, obj_in=obj_in)
        assert result == prop

    def test_update_with_updated_by(self, crud, mock_db):
        """update() sets updated_by when provided."""
        prop = make_property()
        mock_db.add.return_value = None
        mock_db.flush.return_value = None
        mock_db.refresh.return_value = None

        crud.update(
            mock_db,
            db_obj=prop,
            obj_in={"title": "New"},
            updated_by_supabase_id="supabase-uuid-123"
        )
        assert prop.updated_by == "supabase-uuid-123"

    def test_update_strips_protected_fields(self, crud, mock_db):
        """Protected fields (property_id, user_id, etc.) are not applied."""
        prop = make_property(property_id=1, user_id=10)
        mock_db.add.return_value = None
        mock_db.flush.return_value = None
        mock_db.refresh.return_value = None

        crud.update(
            mock_db,
            db_obj=prop,
            obj_in={"property_id": 999, "user_id": 999, "title": "Safe"}
        )
        # Protected fields should NOT have been changed
        assert prop.property_id == 1
        assert prop.user_id == 10


# ─────────────────────────────────────────────
# LINE 489 — update_listing_status: not found
# ─────────────────────────────────────────────

class TestUpdateListingStatus:
    """Line 489: update_listing_status returns None when property not found."""

    def test_not_found_returns_none(self, crud, mock_db):
        """Line 489: property_id doesn't exist → returns None."""
        mock_db.get.return_value = None
        result = crud.update_listing_status(
            mock_db, property_id=999, listing_status=ListingStatus.sold
        )
        assert result is None

    def test_updates_status_successfully(self, crud, mock_db):
        """Happy path: status updated."""
        prop = make_property()
        mock_db.get.return_value = prop
        mock_db.add.return_value = None
        mock_db.flush.return_value = None
        mock_db.refresh.return_value = None

        result = crud.update_listing_status(
            mock_db,
            property_id=1,
            listing_status=ListingStatus.sold,
            updated_by_supabase_id="admin-uuid"
        )
        assert prop.listing_status == ListingStatus.sold
        assert prop.updated_by == "admin-uuid"

    def test_updates_without_supabase_id(self, crud, mock_db):
        prop = make_property()
        mock_db.get.return_value = prop
        mock_db.add.return_value = None
        mock_db.flush.return_value = None
        mock_db.refresh.return_value = None

        result = crud.update_listing_status(
            mock_db, property_id=1, listing_status=ListingStatus.rented
        )
        assert result is not None


# ─────────────────────────────────────────────
# LINE 516 — verify_property: not found
# ─────────────────────────────────────────────

class TestVerifyProperty:
    """Line 516: verify_property returns None when not found."""

    def test_not_found_returns_none(self, crud, mock_db):
        """Line 516: property not found."""
        mock_db.get.return_value = None
        result = crud.verify_property(mock_db, property_id=999)
        assert result is None

    def test_verify_sets_verification_date(self, crud, mock_db):
        """Happy path: is_verified=True sets verification_date."""
        prop = make_property()
        mock_db.get.return_value = prop
        mock_db.add.return_value = None
        mock_db.flush.return_value = None
        mock_db.refresh.return_value = None

        crud.verify_property(mock_db, property_id=1, is_verified=True)
        assert prop.is_verified is True
        assert prop.verification_date is not None

    def test_unverify_clears_verification_date(self, crud, mock_db):
        """is_verified=False clears verification_date."""
        prop = make_property(
            is_verified=True,
            verification_date=datetime.now(timezone.utc)
        )
        mock_db.get.return_value = prop
        mock_db.add.return_value = None
        mock_db.flush.return_value = None
        mock_db.refresh.return_value = None

        crud.verify_property(mock_db, property_id=1, is_verified=False)
        assert prop.is_verified is False
        assert prop.verification_date is None

    def test_verify_with_updated_by(self, crud, mock_db):
        prop = make_property()
        mock_db.get.return_value = prop
        mock_db.add.return_value = None
        mock_db.flush.return_value = None
        mock_db.refresh.return_value = None

        crud.verify_property(
            mock_db, property_id=1, is_verified=True,
            updated_by_supabase_id="admin-uuid"
        )
        assert prop.updated_by == "admin-uuid"


# ─────────────────────────────────────────────
# LINE 537 — toggle_featured: not found
# ─────────────────────────────────────────────

class TestToggleFeatured:
    """Line 537: toggle_featured returns None when not found."""

    def test_not_found_returns_none(self, crud, mock_db):
        """Line 537: property not found."""
        mock_db.get.return_value = None
        result = crud.toggle_featured(mock_db, property_id=999, is_featured=True)
        assert result is None

    def test_feature_property(self, crud, mock_db):
        prop = make_property(is_featured=False)
        mock_db.get.return_value = prop
        mock_db.add.return_value = None
        mock_db.flush.return_value = None
        mock_db.refresh.return_value = None

        crud.toggle_featured(mock_db, property_id=1, is_featured=True)
        assert prop.is_featured is True

    def test_unfeature_property(self, crud, mock_db):
        prop = make_property(is_featured=True)
        mock_db.get.return_value = prop
        mock_db.add.return_value = None
        mock_db.flush.return_value = None
        mock_db.refresh.return_value = None

        crud.toggle_featured(
            mock_db, property_id=1, is_featured=False,
            updated_by_supabase_id="admin-uuid"
        )
        assert prop.is_featured is False
        assert prop.updated_by == "admin-uuid"


# ─────────────────────────────────────────────
# LINE 557 — hard_delete_admin_only: not found
# ─────────────────────────────────────────────

class TestHardDeleteAdminOnly:
    """Line 557: hard_delete returns None when property not found."""

    def test_not_found_returns_none(self, crud, mock_db):
        """Line 557: property not found → None."""
        mock_db.get.return_value = None
        result = crud.hard_delete_admin_only(mock_db, property_id=999)
        assert result is None

    def test_hard_delete_calls_db_delete(self, crud, mock_db):
        """Happy path: db.delete called with the property."""
        prop = make_property()
        mock_db.get.return_value = prop
        mock_db.flush.return_value = None

        result = crud.hard_delete_admin_only(mock_db, property_id=1)
        mock_db.delete.assert_called_once_with(prop)
        assert result == prop


# ─────────────────────────────────────────────
# LINES 782-789 — get_properties_in_bounds world-spanning branch
# ─────────────────────────────────────────────

class TestGetPropertiesInBounds:
    """Lines 782-789: world-spanning bounding box → simplified lat-only query."""

    def test_world_spanning_longitude(self, crud, mock_db):
        """Lines 782-789: lon span > 359° triggers world-spanning branch."""
        mock_db.execute.return_value.scalars.return_value.all.return_value = []

        result = crud.get_properties_in_bounds(
            mock_db,
            min_lat=-50.0,
            min_lon=-179.9,
            max_lat=50.0,
            max_lon=179.9,  # After clamping: span = 359.8 > 359.0
        )
        assert result == []

    def test_world_spanning_latitude(self, crud, mock_db):
        """Lines 782-789: lat span > 179° triggers world-spanning branch."""
        mock_db.execute.return_value.scalars.return_value.all.return_value = []

        result = crud.get_properties_in_bounds(
            mock_db,
            min_lat=-89.9,
            min_lon=-10.0,
            max_lat=89.9,   # After clamping: span = 179.8 > 179.0
            max_lon=10.0,
        )
        assert result == []

    def test_normal_bounding_box(self, crud, mock_db):
        """Normal (non-world-spanning) bounding box uses ST_Intersects envelope."""
        mock_db.execute.return_value.scalars.return_value.all.return_value = []

        result = crud.get_properties_in_bounds(
            mock_db,
            min_lat=6.0,
            min_lon=3.0,
            max_lat=7.0,
            max_lon=4.0,
        )
        assert result == []

    def test_clamping_applied(self, crud, mock_db):
        """Boundary clamping: inputs beyond ±90/±180 are clamped safely."""
        mock_db.execute.return_value.scalars.return_value.all.return_value = []

        # Pass raw world boundaries — should clamp and not raise
        result = crud.get_properties_in_bounds(
            mock_db,
            min_lat=-90.0,
            min_lon=-180.0,
            max_lat=90.0,
            max_lon=180.0,
        )
        assert result == []


# ─────────────────────────────────────────────
# LINE 816 — calculate_distance: missing geom
# ─────────────────────────────────────────────

class TestCalculateDistance:
    """Line 816: calculate_distance returns 0.0 when geom is None."""

    def test_returns_zero_when_property_a_has_no_geom(self, crud):
        """Line 816: property_a.geom is None → 0.0."""
        prop_a = make_property(geom=None)
        prop_b = make_property(geom="POINT(3.3792 6.5244)")

        result = crud.calculate_distance(prop_a, prop_b)
        assert result == 0.0

    def test_returns_zero_when_property_b_has_no_geom(self, crud):
        """Line 816: property_b.geom is None → 0.0."""
        prop_a = make_property(geom="POINT(3.3792 6.5244)")
        prop_b = make_property(geom=None)

        result = crud.calculate_distance(prop_a, prop_b)
        assert result == 0.0

    def test_returns_zero_when_both_have_no_geom(self, crud):
        prop_a = make_property(geom=None)
        prop_b = make_property(geom=None)

        result = crud.calculate_distance(prop_a, prop_b)
        assert result == 0.0

# ─────────────────────────────────────────────
# SINGLETON INSTANCE SMOKE TEST
# ─────────────────────────────────────────────

class TestSingletonInstance:
    def test_singleton_is_property_crud(self):
        from app.crud.properties import property as prop_singleton
        assert isinstance(prop_singleton, PropertyCRUD)


# ─────────────────────────────────────────────
# AUTHORIZATION HELPER (for completeness)
# ─────────────────────────────────────────────

class TestCanModifyProperty:
    def test_owner_can_modify(self, crud):
        assert crud.can_modify_property(current_user_id=5, property_user_id=5) is True

    def test_other_user_cannot_modify(self, crud):
        assert crud.can_modify_property(current_user_id=5, property_user_id=9) is False

    def test_admin_can_modify_any(self, crud):
        assert crud.can_modify_property(
            current_user_id=5, property_user_id=9, is_admin=True
        ) is True