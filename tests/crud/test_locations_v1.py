# tests/crud/test_locations_v1.py
import pytest
from sqlalchemy.orm import Session
from app.crud.locations import location as location_crud
from app.schemas.locations import LocationCreate, LocationUpdate
import uuid

@pytest.fixture
def valid_uuid():
    return str(uuid.uuid4())

@pytest.fixture
def sample_location_in():
    return LocationCreate(
        state="Lagos",
        city="Lekki",
        neighborhood="Phase 1",
        latitude=6.4474,
        longitude=3.4723
    )

def test_locations_lifecycle_master(db: Session, sample_location_in: LocationCreate, valid_uuid: str):
    # 1. Create - Using valid UUID for database integrity
    db_obj = location_crud.create(db, obj_in=sample_location_in, updated_by_supabase_id=valid_uuid)
    assert db_obj.city == "Lekki"
    assert str(db_obj.updated_by) == valid_uuid
    
    # 2. Update - Passing Pydantic object
    update_data = LocationUpdate(city="Lekki Updated", latitude=6.45, longitude=3.48)
    updated_obj = location_crud.update(db, db_obj=db_obj, obj_in=update_data, updated_by_supabase_id=valid_uuid)
    assert updated_obj.city == "Lekki Updated"

    # 3. Get or Create (Triggering the "Get" branch)
    existing = location_crud.get_or_create(db, state="Lagos", city="Lekki Updated", neighborhood="Phase 1")
    assert existing.location_id == updated_obj.location_id

    # 4. Deactivate
    location_crud.deactivate(db, location_id=db_obj.location_id)
    
    # 5. Search & Filters (Hits lines 37-45)
    filtered = location_crud.get_by_filters(db, state="Lagos", city="Lekki Updated")
    assert len(filtered) >= 1
    
    search = location_crud.search_locations(db, search_term="Lekki")
    assert len(search) >= 1

def test_geospatial_details(db: Session):
    # Hits the nearest and coordinates logic
    loc_in = LocationCreate(state="Abuja", city="Wuse", latitude=9.06, longitude=7.48)
    location_crud.create(db, obj_in=loc_in)
    
    nearest = location_crud.get_nearest(db, latitude=9.06, longitude=7.48, limit=1)
    assert len(nearest) > 0
    
    coords = location_crud.get_by_coordinates(db, latitude=9.06, longitude=7.48, radius_km=10)
    assert len(coords) > 0