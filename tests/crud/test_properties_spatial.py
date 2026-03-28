"""
tests/crud/test_properties_spatial.py

Pagination-correctness tests for spatial CRUD methods.
Verifies that get_within_radius_approved applies is_verified filter
and skip/limit entirely in SQL - not via Python-side slicing.
"""
from geoalchemy2.elements import WKTElement

from app.crud.properties import property as property_crud


# Ikeja centroid - used as the search origin in all tests
IKEJA_LON = 3.3488
IKEJA_LAT = 6.6018

# Lekki centroid - ~27 km from Ikeja, used to place out-of-radius properties
LEKKI_LON = 3.4746
LEKKI_LAT = 6.4474


def _seed_verified(db, user_id, location, property_type, agency, title, lon, lat):
    """Seed a single verified property at explicit coordinates."""
    from app.schemas.properties import PropertyCreate
    obj_in = PropertyCreate(
        title=title,
        description="Spatial test property",
        price=5_000_000,
        bedrooms=2,
        bathrooms=1.0,
        location_id=location.location_id,
        property_type_id=property_type.property_type_id,
        listing_type="sale",
        listing_status="available",
        agency_id=agency.agency_id,
    )
    prop = property_crud.create_with_owner(db, obj_in=obj_in, user_id=user_id)
    prop.is_verified = True
    prop.geom = WKTElement(f"POINT({lon} {lat})", srid=4326)
    db.flush()
    db.refresh(prop)
    return prop


def _seed_unverified(db, user_id, location, property_type, agency, title, lon, lat):
    """Seed a single unverified property at explicit coordinates."""
    from app.schemas.properties import PropertyCreate
    obj_in = PropertyCreate(
        title=title,
        description="Spatial test property",
        price=5_000_000,
        bedrooms=2,
        bathrooms=1.0,
        location_id=location.location_id,
        property_type_id=property_type.property_type_id,
        listing_type="sale",
        listing_status="available",
        agency_id=agency.agency_id,
    )
    prop = property_crud.create_with_owner(db, obj_in=obj_in, user_id=user_id)
    prop.is_verified = False
    prop.geom = WKTElement(f"POINT({lon} {lat})", srid=4326)
    db.flush()
    db.refresh(prop)
    return prop


class TestGetWithinRadiusApprovedPagination:
    """
    Verifies get_within_radius_approved:
    - Only returns is_verified=True properties
    - skip/limit are applied in SQL, not Python
    - Out-of-radius properties are excluded regardless of verification status
    """

    def test_returns_only_verified(
        self, db, agent_user, location, property_type, agency
    ):
        """Unverified properties within radius must not appear."""
        _seed_verified(
            db, agent_user.user_id, location, property_type, agency,
            "Verified Near", IKEJA_LON, IKEJA_LAT
        )
        _seed_unverified(
            db, agent_user.user_id, location, property_type, agency,
            "Unverified Near", IKEJA_LON, IKEJA_LAT
        )

        results = property_crud.get_within_radius_approved(
            db, latitude=IKEJA_LAT, longitude=IKEJA_LON, radius=5.0,
            skip=0, limit=100,
        )

        titles = [p.title for p in results]
        assert "Verified Near" in titles
        assert "Unverified Near" not in titles

    def test_excludes_out_of_radius(
        self, db, agent_user, location, location_lekki, property_type, agency
    ):
        """Verified properties outside radius must not appear."""
        _seed_verified(
            db, agent_user.user_id, location, property_type, agency,
            "Verified Near", IKEJA_LON, IKEJA_LAT
        )
        _seed_verified(
            db, agent_user.user_id, location_lekki, property_type, agency,
            "Verified Far", LEKKI_LON, LEKKI_LAT
        )

        # 5 km radius from Ikeja - Lekki (~27 km) must be excluded
        results = property_crud.get_within_radius_approved(
            db, latitude=IKEJA_LAT, longitude=IKEJA_LON, radius=5.0,
            skip=0, limit=100,
        )

        titles = [p.title for p in results]
        assert "Verified Near" in titles
        assert "Verified Far" not in titles

    def test_pagination_skip(
        self, db, agent_user, location, property_type, agency
    ):
        """
        Pagination correctness - skip is applied in SQL.
        Seed 3 verified properties, fetch with skip=1 limit=2,
        must return exactly 2 and exclude the first by distance order.
        """
        p1 = _seed_verified(
            db, agent_user.user_id, location, property_type, agency,
            "Nearest", IKEJA_LON, IKEJA_LAT
        )
        p2 = _seed_verified(
            db, agent_user.user_id, location, property_type, agency,
            "Second", IKEJA_LON + 0.001, IKEJA_LAT
        )
        p3 = _seed_verified(
            db, agent_user.user_id, location, property_type, agency,
            "Third", IKEJA_LON + 0.002, IKEJA_LAT
        )

        page_one = property_crud.get_within_radius_approved(
            db, latitude=IKEJA_LAT, longitude=IKEJA_LON, radius=5.0,
            skip=0, limit=3,
        )
        page_two = property_crud.get_within_radius_approved(
            db, latitude=IKEJA_LAT, longitude=IKEJA_LON, radius=5.0,
            skip=1, limit=2,
        )

        assert len(page_one) == 3
        assert len(page_two) == 2
        # page_two must not contain the nearest property (skipped)
        page_two_ids = {p.property_id for p in page_two}
        assert p1.property_id not in page_two_ids
        assert p2.property_id in page_two_ids
        assert p3.property_id in page_two_ids

    def test_pagination_limit(
        self, db, agent_user, location, property_type, agency
    ):
        """limit is enforced in SQL - never returns more than requested."""
        for i in range(5):
            _seed_verified(
                db, agent_user.user_id, location, property_type, agency,
                f"Property {i}", IKEJA_LON + i * 0.001, IKEJA_LAT
            )

        results = property_crud.get_within_radius_approved(
            db, latitude=IKEJA_LAT, longitude=IKEJA_LON, radius=5.0,
            skip=0, limit=3,
        )
        assert len(results) == 3

    def test_unverified_bulk_does_not_corrupt_page(
        self, db, agent_user, location, property_type, agency
    ):
        """
        The old limit*2 heuristic broke when many unverified properties
        existed within radius. Seed 10 unverified + 3 verified, confirm
        verified page is still correct size.
        """
        for i in range(10):
            _seed_unverified(
                db, agent_user.user_id, location, property_type, agency,
                f"Unverified {i}", IKEJA_LON + i * 0.0001, IKEJA_LAT
            )
        for i in range(3):
            _seed_verified(
                db, agent_user.user_id, location, property_type, agency,
                f"Verified {i}", IKEJA_LON + i * 0.0002, IKEJA_LAT
            )

        results = property_crud.get_within_radius_approved(
            db, latitude=IKEJA_LAT, longitude=IKEJA_LON, radius=5.0,
            skip=0, limit=3,
        )

        assert len(results) == 3
        assert all(p.is_verified for p in results)
