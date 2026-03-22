# tests/crud/test_properties_v6.py
import pytest
from sqlalchemy.orm import Session
from fastapi import HTTPException
from geoalchemy2 import WKTElement

from app.crud.properties import property as property_crud
from app.schemas.properties import PropertyUpdate, PropertyFilter
from app.models.properties import Property, ListingStatus, ListingType
from app.models.locations import Location
from app.models.property_types import PropertyType

# --- 1. THE FOUNDATION (Fixes 'NoneType' Errors) ---

@pytest.fixture
def test_dependencies(db: Session):
    """Ensures a Location and PropertyType exist for foreign key constraints."""
    loc = db.query(Location).first()
    if not loc:
        loc = Location(city="Test City", state="Test State")
        db.add(loc)
    
    ptype = db.query(PropertyType).first()
    if not ptype:
        ptype = PropertyType(name="Apartment", description="2 Bedroom Apartment")
        db.add(ptype)
    
    db.commit()
    db.refresh(loc)
    db.refresh(ptype)
    return {"location_id": loc.location_id, "property_type_id": ptype.property_type_id}

@pytest.fixture
def geo_properties(db: Session, test_dependencies):
    """Creates specific properties with geometry for geospatial testing."""
    tid = test_dependencies["property_type_id"]
    
    props = []
    # Point A: Lagos Central, Point B: Close by, Point C: Further
    coords = [(6.5244, 3.3792), (6.5245, 3.3793), (6.6018, 3.3515)]
    
    for i, (lat, lon) in enumerate(coords):
        # 1. Create a specific location for THIS property's coordinates
        loc = Location(
            city="Lagos", 
            state="Lagos State",
            # SRID 4326 is the magic number for GPS/Latitude-Longitude
            geom=WKTElement(f"POINT({lon} {lat})", srid=4326) 
        )
        db.add(loc)
        db.flush() # Get the loc.location_id

        # 2. Create property linked to that location
        p = Property(
            title=f"Geo Prop {i}",
            description="Test Property",
            price=1000000,
            location_id=loc.location_id,
            property_type_id=tid,
            listing_type=ListingType.sale,
            listing_status=ListingStatus.available,
            geom=WKTElement(f"POINT({lon} {lat})", srid=4326)
        )
        db.add(p)
        props.append(p)

    db.flush()
    return props

# --- 2. THE ATTACK (Targeting Missing Lines) ---

class TestPropertyFinalConquest:
    
    def test_get_multi_sanitization(self, db: Session, multiple_properties):
        """Targets pagination edge cases (Lines 139+)."""
        results = property_crud.get_multi(db, skip=-1, limit=-1)
        assert isinstance(results, list)

    def test_filter_exhaustive_sorting(self, db: Session, multiple_properties):
        """Targets every sorting branch (Lines 160-175)."""
        # NOTE: This will fail until you fix line 175 in properties.py to use lowercase .available
        sort_keys = ["price_asc", "price_desc", "date_asc", "date_desc", "size_asc", "size_desc"]
        for key in sort_keys:
            filters = PropertyFilter(sort_by=key)
            results = property_crud.get_by_filters(db, filters=filters)
            assert isinstance(results, list)

    def test_geospatial_search_and_bounds(self, db: Session, geo_properties):
        """Targets geospatial logic (Lines 180-230)."""
        # Radius search
        nearby = property_crud.get_nearby_properties(
            db, latitude=6.5244, longitude=3.3792, radius_km=5.0
        )
        assert len(nearby) >= 2
        
        # Bounding box search
        in_bounds = property_crud.get_properties_in_bounds(
            db, min_lat=6.0, max_lat=7.0, min_lon=3.0, max_lon=4.0
        )
        assert len(in_bounds) >= 3

    def test_bulk_operations(self, db: Session, multiple_properties):
        """Targets bulk update/verify/delete (Lines 235-263)."""
        ids = [p.property_id for p in multiple_properties[:2]]
        
        assert property_crud.bulk_verify(db, property_ids=ids) == 2
        assert property_crud.bulk_update_status(db, property_ids=ids, new_status=ListingStatus.sold) == 2
        assert property_crud.bulk_soft_delete(db, property_ids=ids, deleted_by_supabase_id="550e8400-e29b-41d4-a716-446655440001") == 2

    def test_update_exception_handling(self, db: Session, sample_property):
        """Targets 404 error branches (Lines 280-305)."""
        # Invalid location check
        with pytest.raises(HTTPException) as exc:
            property_crud.update(db, db_obj=sample_property, obj_in={"location_id": 999999})
        assert exc.value.status_code == 404

        # Invalid type check
        with pytest.raises(HTTPException) as exc:
            property_crud.update(db, db_obj=sample_property, obj_in={"property_type_id": 999999})
        assert exc.value.status_code == 404

    def test_restore_and_hard_delete(self, db: Session, sample_property):
        """Targets cleanup logic."""
        pid = sample_property.property_id
        property_crud.soft_delete(db, property_id=pid, deleted_by_supabase_id="550e8400-e29b-41d4-a716-446655440001")
        
        # Restore logic
        restored = property_crud.restore(db, property_id=pid)
        assert restored.deleted_at is None
        
        # Hard delete logic
        property_crud.hard_delete_admin_only(db, property_id=pid)
        assert property_crud.get(db, pid) is None

