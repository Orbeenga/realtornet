# tests/crud/test_locations_v2.py
"""
Surgical tests for app/crud/locations.py - Targeting missing lines to push 76% → 85%+

Missing lines from coverage report:
- 37-45: get_multi with include_inactive filter
- 67: get_by_filters with None handling
- 149-152: get_states with empty results
- 161-169: get_cities with state filter
- 179-191: get_neighborhoods with state/city filters
- 312: deactivate with non-existent location
- 354-362: get_or_create "create" branch
"""

import pytest
from sqlalchemy.orm import Session
from app.crud.locations import location as location_crud
from app.schemas.locations import LocationCreate, LocationUpdate
import uuid


class TestLocationGetMultiVariations:
    """Target lines 37-45: include_inactive parameter"""
    
    def test_get_multi_excludes_inactive_by_default(self, db: Session):
        """Verify inactive locations are excluded by default"""
        # Create active location
        active = location_crud.create(
            db, 
            obj_in=LocationCreate(
                state="Lagos",
                city="Ikeja",
                latitude=6.5944,
                longitude=3.3393
            )
        )
        
        # Create and deactivate another location
        inactive = location_crud.create(
            db,
            obj_in=LocationCreate(
                state="Lagos", 
                city="Victoria Island",
                latitude=6.4281,
                longitude=3.4219
            )
        )
        location_crud.deactivate(db, location_id=inactive.location_id)
        
        # Default call should exclude inactive
        results = location_crud.get_multi(db, skip=0, limit=100)
        location_ids = [loc.location_id for loc in results]
        
        assert active.location_id in location_ids
        assert inactive.location_id not in location_ids
    
    def test_get_multi_includes_inactive_when_requested(self, db: Session):
        """Target line 43: include_inactive=True branch"""
        # Create and deactivate a location
        inactive = location_crud.create(
            db,
            obj_in=LocationCreate(
                state="Abuja",
                city="Wuse",
                latitude=9.0643,
                longitude=7.4892
            )
        )
        location_crud.deactivate(db, location_id=inactive.location_id)
        
        # Call with include_inactive=True
        results = location_crud.get_multi(db, skip=0, limit=100, include_inactive=True)
        location_ids = [loc.location_id for loc in results]
        
        assert inactive.location_id in location_ids


class TestLocationFilterEdgeCases:
    """Target line 67: get_by_filters with None/empty handling"""
    
    def test_get_by_filters_with_no_matches(self, db: Session):
        """Verify empty results when filters match nothing"""
        # Create a location
        location_crud.create(
            db,
            obj_in=LocationCreate(state="Rivers", city="Port Harcourt")
        )
        
        # Search for non-existent location
        results = location_crud.get_by_filters(
            db,
            state="NonExistentState",
            city="NonExistentCity"
        )
        
        assert len(results) == 0
    
    def test_get_by_filters_partial_match(self, db: Session):
        """Test filtering with only some parameters"""
        # Create locations in same state, different cities
        location_crud.create(
            db,
            obj_in=LocationCreate(state="Oyo", city="Ibadan")
        )
        location_crud.create(
            db,
            obj_in=LocationCreate(state="Oyo", city="Ogbomoso")
        )
        
        # Filter by state only
        results = location_crud.get_by_filters(db, state="Oyo")
        assert len(results) == 2
        
        # Filter by state and city
        results = location_crud.get_by_filters(db, state="Oyo", city="Ibadan")
        assert len(results) == 1
        assert results[0].city == "Ibadan"

    def test_get_by_filters_with_neighborhood(self, db: Session):
        """
        Neighborhood filter must narrow results.

        This targets the neighborhood branch in get_by_filters.
        """
        location_crud.create(
            db,
            obj_in=LocationCreate(
                state="Lagos",
                city="Lekki",
                neighborhood="Phase 1"
            )
        )
        location_crud.create(
            db,
            obj_in=LocationCreate(
                state="Lagos",
                city="Lekki",
                neighborhood="Phase 2"
            )
        )

        results = location_crud.get_by_filters(
            db,
            state="Lagos",
            city="Lekki",
            neighborhood="Phase 1"
        )
        assert len(results) == 1
        assert results[0].neighborhood == "Phase 1"


class TestLocationAggregationFunctions:
    """Target lines 149-152, 161-169, 179-191: Aggregation functions"""
    
    def test_get_states_returns_sorted_list(self, db: Session):
        """Target lines 149-152: get_states with distinct ordering"""
        # Create locations in different states
        location_crud.create(db, obj_in=LocationCreate(state="Zamfara", city="Gusau"))
        location_crud.create(db, obj_in=LocationCreate(state="Abia", city="Umuahia"))
        location_crud.create(db, obj_in=LocationCreate(state="Kano", city="Kano"))
        
        states = location_crud.get_states(db)
        
        assert "Zamfara" in states
        assert "Abia" in states
        assert "Kano" in states
        # Verify alphabetical ordering
        assert states == sorted(states)
    
    def test_get_cities_without_state_filter(self, db: Session):
        """Target line 161-169: get_cities with no state filter"""
        # Create locations
        location_crud.create(db, obj_in=LocationCreate(state="Enugu", city="Enugu"))
        location_crud.create(db, obj_in=LocationCreate(state="Enugu", city="Nsukka"))
        
        # Get all cities (no filter)
        cities = location_crud.get_cities(db)
        
        assert "Enugu" in cities
        assert "Nsukka" in cities
    
    def test_get_cities_with_state_filter(self, db: Session):
        """Target line 164: state filter branch in get_cities"""
        # Create locations in different states
        location_crud.create(db, obj_in=LocationCreate(state="Kaduna", city="Kaduna"))
        location_crud.create(db, obj_in=LocationCreate(state="Kaduna", city="Zaria"))
        location_crud.create(db, obj_in=LocationCreate(state="Katsina", city="Katsina"))
        
        # Filter by specific state
        kaduna_cities = location_crud.get_cities(db, state="Kaduna")
        
        assert len(kaduna_cities) == 2
        assert "Kaduna" in kaduna_cities
        assert "Zaria" in kaduna_cities
        assert "Katsina" not in kaduna_cities
    
    def test_get_neighborhoods_with_filters(self, db: Session):
        """Target lines 179-191: get_neighborhoods with state/city filters"""
        # Create locations with neighborhoods
        location_crud.create(
            db,
            obj_in=LocationCreate(
                state="Lagos",
                city="Lekki",
                neighborhood="Phase 1"
            )
        )
        location_crud.create(
            db,
            obj_in=LocationCreate(
                state="Lagos",
                city="Lekki",
                neighborhood="Phase 2"
            )
        )
        location_crud.create(
            db,
            obj_in=LocationCreate(
                state="Lagos",
                city="Ikoyi",
                neighborhood="Banana Island"
            )
        )
        
        # Test with state filter only
        lagos_hoods = location_crud.get_neighborhoods(db, state="Lagos")
        assert len(lagos_hoods) >= 3
        
        # Test with state and city filters (targets lines 187-188)
        lekki_hoods = location_crud.get_neighborhoods(db, state="Lagos", city="Lekki")
        assert len(lekki_hoods) == 2
        assert "Phase 1" in lekki_hoods
        assert "Phase 2" in lekki_hoods
        assert "Banana Island" not in lekki_hoods
    
    def test_get_neighborhoods_excludes_null(self, db: Session):
        """Verify neighborhoods=None are filtered out (line 177)"""
        # Create location without neighborhood
        location_crud.create(
            db,
            obj_in=LocationCreate(state="Sokoto", city="Sokoto")
        )
        
        hoods = location_crud.get_neighborhoods(db, state="Sokoto")
        # Should be empty since neighborhood is NULL
        assert len(hoods) == 0


class TestLocationDeactivateEdgeCases:
    """Target line 312: deactivate with non-existent location"""
    
    def test_deactivate_nonexistent_location(self, db: Session):
        """Verify deactivate returns None for non-existent ID"""
        result = location_crud.deactivate(db, location_id=999999)
        assert result is None
    
    def test_deactivate_already_inactive(self, db: Session):
        """Test soft-deleting an already soft-deleted location returns the object."""
        # Create and deactivate
        loc = location_crud.create(
            db,
            obj_in=LocationCreate(state="Bauchi", city="Bauchi")
        )
        deleted_by = str(uuid.uuid4())
        location_crud.soft_delete(
            db,
            location_id=loc.location_id,
            deleted_by_supabase_id=deleted_by
        )
        
        # Soft delete again (should return object, already deleted)
        result = location_crud.soft_delete(
            db,
            location_id=loc.location_id,
            deleted_by_supabase_id=deleted_by
        )
        assert result is not None
        assert result.deleted_at is not None


class TestLocationGetOrCreate:
    """Target lines 354-362: get_or_create 'create' branch"""
    
    def test_get_or_create_creates_new_location(self, db: Session):
        """Force the 'create' branch by using unique identifiers"""
        # Use random unique city name to ensure it doesn't exist
        unique_city = f"TestCity-{uuid.uuid4().hex[:8]}"
        
        result = location_crud.get_or_create(
            db,
            state="TestState",
            city=unique_city,
            neighborhood="TestHood",
            latitude=6.5,
            longitude=3.5
        )
        
        # Verify it was created
        assert result.location_id is not None
        assert result.city == unique_city
        assert result.state == "TestState"
        assert result.neighborhood == "TestHood"
    
    def test_get_or_create_returns_existing(self, db: Session):
        """Verify 'get' branch when location already exists"""
        # Create initial location
        first = location_crud.create(
            db,
            obj_in=LocationCreate(
                state="Ondo",
                city="Akure",
                neighborhood="Alagbaka"
            )
        )
        
        # Call get_or_create with same details (should return existing)
        second = location_crud.get_or_create(
            db,
            state="Ondo",
            city="Akure",
            neighborhood="Alagbaka"
        )
        
        # Should be the same object
        assert first.location_id == second.location_id
    
    def test_get_or_create_with_none_neighborhood(self, db: Session):
        """Test get_or_create with neighborhood=None"""
        unique_city = f"City-{uuid.uuid4().hex[:6]}"
        
        # Create with neighborhood=None
        result = location_crud.get_or_create(
            db,
            state="Delta",
            city=unique_city,
            neighborhood=None
        )
        
        assert result.neighborhood is None
        
        # Call again, should return same
        second = location_crud.get_or_create(
            db,
            state="Delta",
            city=unique_city,
            neighborhood=None
        )
        
        assert result.location_id == second.location_id


class TestLocationSearchFunction:
    """Additional coverage for search_locations"""
    
    def test_search_locations_case_insensitive(self, db: Session):
        """Verify ILIKE search works across all fields"""
        location_crud.create(
            db,
            obj_in=LocationCreate(
                state="Anambra",
                city="Awka",
                neighborhood="GRA"
            )
        )
        
        # Search by partial state name (case insensitive)
        results = location_crud.search_locations(db, search_term="anam")
        assert len(results) >= 1
        
        # Search by partial city name
        results = location_crud.search_locations(db, search_term="wk")
        assert len(results) >= 1
        
        # Search by neighborhood
        results = location_crud.search_locations(db, search_term="gra")
        assert len(results) >= 1


class TestLocationUpdateWithGeography:
    """Ensure update path with coordinates is covered"""
    
    def test_update_coordinates(self, db: Session):
        """Test updating location coordinates"""
        # Create location without coordinates
        loc = location_crud.create(
            db,
            obj_in=LocationCreate(state="Benue", city="Makurdi")
        )
        
        # Update with coordinates
        updated = location_crud.update(
            db,
            db_obj=loc,
            obj_in=LocationUpdate(latitude=7.7333, longitude=8.5333)
        )
        
        assert updated.geom is not None
    
    def test_update_text_fields_only(self, db: Session):
        """Test updating without touching coordinates"""
        loc = location_crud.create(
            db,
            obj_in=LocationCreate(
                state="Taraba",
                city="Jalingo",
                latitude=8.8833,
                longitude=11.3667
            )
        )
        
        # Update city name only
        updated = location_crud.update(
            db,
            db_obj=loc,
            obj_in=LocationUpdate(city="Jalingo City")
        )
        
        assert updated.city == "Jalingo City"
        assert updated.geom is not None  # Coordinates preserved
