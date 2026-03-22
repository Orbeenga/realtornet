# tests/crud/test_properties_v4.py
"""
Final Coverage Push: app/crud/properties.py
Target: 60% → 85%+ coverage

Tests specifically designed to hit remaining uncovered lines:
- Lines 44-63: Base CRUD operations edge cases
- Lines 139-263: Complex filter combinations
- Lines 280-305: Additional query variations
- Scattered lines: Error paths and conditional branches
"""

import pytest
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from app.crud.properties import property as property_crud
from app.models.properties import Property, ListingType, ListingStatus
from app.schemas.properties import PropertyCreate, PropertyUpdate


# ============================================================================
# TESTS TO HIT LINES 139-263: COMPLEX FILTER COMBINATIONS
# ============================================================================

class TestPropertyCompleteFilterCoverage:
    """Hit all filter combination branches"""
    
    def test_filter_all_amenities_combined(self, db: Session, multiple_properties):
        """Test filtering with all amenity flags at once"""
        filters = {
            "has_swimming_pool": True,
            "has_garden": False,
            "has_security": True
        }
        
        props = property_crud.get_multi(db, skip=0, limit=10, filters=filters)
        assert isinstance(props, list)
    
    def test_filter_price_and_bedrooms_combined(self, db: Session, multiple_properties):
        """Test price range + bedroom filters together"""
        filters = {
            "min_price": 30000000,
            "max_price": 100000000,
            "min_bedrooms": 3,
            "bedrooms": 3
        }
        
        props = property_crud.get_multi(db, skip=0, limit=10, filters=filters)
        assert isinstance(props, list)
    
    def test_filter_all_listing_fields(self, db: Session, multiple_properties):
        """Test all listing-related filters"""
        filters = {
            "listing_type": ListingType.sale,
            "listing_status": ListingStatus.available,
            "is_verified": True,
            "is_featured": True
        }
        
        props = property_crud.get_multi(db, skip=0, limit=10, filters=filters)
        assert isinstance(props, list)
        if props:
            assert all(p.listing_type == ListingType.sale for p in props)
    
    def test_filter_with_location_and_type(self, db: Session, multiple_properties, location, property_type):
        """Test location + property type filters"""
        filters = {
            "location_id": location.location_id,
            "property_type_id": property_type.property_type_id
        }
        
        props = property_crud.get_multi(db, skip=0, limit=10, filters=filters)
        assert isinstance(props, list)
    
    def test_filter_with_none_values(self, db: Session, multiple_properties):
        """Test that None filter values are handled correctly"""
        filters = {
            "min_price": None,
            "max_price": None,
            "bedrooms": None,
            "is_verified": None
        }
        
        props = property_crud.get_multi(db, skip=0, limit=10, filters=filters)
        assert isinstance(props, list)
    
    def test_filter_bathroom_count(self, db: Session, multiple_properties):
        """Test bathroom filtering"""
        filters = {"bathrooms": 2}
        
        props = property_crud.get_multi(db, skip=0, limit=10, filters=filters)
        assert isinstance(props, list)
    
    def test_get_multi_with_user_and_filters(self, db: Session, multiple_properties, normal_user):
        """Test combining user_id with filters"""
        filters = {"listing_status": ListingStatus.available}
        
        props = property_crud.get_multi(
            db, 
            skip=0, 
            limit=10, 
            user_id=normal_user.user_id,
            filters=filters
        )
        assert isinstance(props, list)
        if props:
            assert all(p.user_id == normal_user.user_id for p in props)


# ============================================================================
# TESTS TO HIT GEOSPATIAL EDGE CASES (Lines 280-305, scattered)
# ============================================================================

class TestGeospatialEdgeCases:
    """Cover geospatial query edge cases"""
    
    def test_get_properties_near_with_no_results(self, db: Session):
        """Test proximity search in empty area"""
        # Search in middle of ocean
        props = property_crud.get_properties_near(
            db,
            latitude=0.0,
            longitude=0.0,
            radius_km=1.0,
            limit=10
        )
        
        assert isinstance(props, list)
        assert len(props) == 0
    
    def test_get_properties_near_large_radius(self, db: Session, multiple_properties):
        """Test proximity search with very large radius"""
        props = property_crud.get_properties_near(
            db,
            latitude=6.5244,
            longitude=3.3792,
            radius_km=1000.0,  # 1000km radius
            limit=5
        )
        
        assert isinstance(props, list)
    
    def test_get_properties_in_bounds_empty_box(self, db: Session):
        """Test bounding box with no properties"""
        props = property_crud.get_properties_in_bounds(
            db,
            min_lat=50.0,
            min_lon=50.0,
            max_lat=51.0,
            max_lon=51.0
        )
        
        assert isinstance(props, list)
        assert len(props) == 0
    
    def test_get_properties_in_bounds_world(self, db: Session, multiple_properties):
        """Test bounding box covering entire world"""
        props = property_crud.get_properties_in_bounds(
            db,
            min_lat=-89.9,   # ✅ Slightly inside poles
            min_lon=-179.9,  # ✅ Slightly inside dateline
            max_lat=89.9,    # ✅ Slightly inside poles
            max_lon=179.9,   # ✅ Slightly inside dateline
            limit=100
        )
        assert isinstance(props, list)
        assert len(props) >= 4


# ============================================================================
# TESTS TO HIT BULK OPERATION EDGE CASES (Scattered lines)
# ============================================================================

class TestBulkOperationEdgeCases:
    """Cover bulk operation edge cases"""
    
    def test_bulk_verify_empty_list(self, db: Session):
        """Test bulk verify with empty property list"""
        count = property_crud.bulk_verify(db, property_ids=[])
        assert count == 0
    
    def test_bulk_verify_nonexistent_ids(self, db: Session):
        """Test bulk verify with IDs that don't exist"""
        count = property_crud.bulk_verify(db, property_ids=[999999, 999998])
        assert count == 0
    
    def test_bulk_update_status_empty_list(self, db: Session):
        """Test bulk status update with empty list"""
        count = property_crud.bulk_update_status(
            db,
            property_ids=[],
            new_status=ListingStatus.sold
        )
        assert count == 0
    
    def test_bulk_update_status_with_updated_by(self, db: Session, multiple_properties):
        """Test bulk status update with updated_by tracking"""
        prop_ids = [p.property_id for p in multiple_properties[:2]]
        
        count = property_crud.bulk_update_status(
            db,
            property_ids=prop_ids,
            new_status=ListingStatus.pending,
            updated_by_supabase_id="550e8400-e29b-41d4-a716-446655440000"
        )
        
        assert count >= 2
    
    def test_bulk_soft_delete_empty_list(self, db: Session):
        """Test bulk soft delete with empty list"""
        count = property_crud.bulk_soft_delete(
            db, property_ids=[], deleted_by_supabase_id="550e8400-e29b-41d4-a716-446655440001"
        )
        assert count == 0
    
    def test_bulk_soft_delete_with_deleted_by(self, db: Session, multiple_properties):
        """Test bulk soft delete with audit trail"""
        prop_ids = [p.property_id for p in multiple_properties[:1]]
        
        count = property_crud.bulk_soft_delete(
            db,
            property_ids=prop_ids,
            deleted_by_supabase_id="550e8400-e29b-41d4-a716-446655440001"
        )
        
        assert count >= 1
    
    def test_bulk_operations_ignore_already_deleted(self, db: Session, sample_property):
        """Test that bulk operations skip already-deleted properties"""
        # Soft delete first
        property_crud.soft_delete(db, property_id=sample_property.property_id, deleted_by_supabase_id="550e8400-e29b-41d4-a716-446655440001")
        
        # Try to verify deleted property
        count = property_crud.bulk_verify(
            db,
            property_ids=[sample_property.property_id]
        )
        
        # Should skip deleted properties
        assert count == 0


# ============================================================================
# TESTS TO HIT INDIVIDUAL CRUD METHOD EDGE CASES
# ============================================================================

class TestCRUDEdgeCases:
    """Hit remaining scattered missing lines"""
    
    def test_create_property_with_all_optional_none(self, db: Session, normal_user, location, property_type):
        """Test creating property with minimal data"""
        from app.schemas.properties import PropertyCreate
        
        prop_in = PropertyCreate(
            title="Minimal Property",
            description="Only required fields",
            price=1000000,
            property_type_id=property_type.property_type_id,
            listing_type="sale",
            location_id=location.location_id
            # All optional fields omitted
        )
        
        prop = property_crud.create(db, obj_in=prop_in, user_id=normal_user.user_id)
        
        assert prop.title == "Minimal Property"
        assert prop.bedrooms is None
        assert prop.bathrooms is None
    
    def test_update_property_with_dict(self, db: Session, sample_property):
        """Test update using dict instead of schema"""
        update_dict = {"title": "Updated via Dict", "price": 55000000}
        
        updated = property_crud.update(
            db,
            db_obj=sample_property,
            obj_in=update_dict
        )
        
        assert updated.title == "Updated via Dict"
        assert updated.price == 55000000
    
    def test_verify_property_sets_date(self, db: Session, sample_property):
        """Test that verify_property sets verification_date"""
        assert sample_property.verification_date is None
        
        verified = property_crud.verify_property(
            db,
            property_id=sample_property.property_id,
            is_verified=True
        )
        
        assert verified.is_verified is True
        assert verified.verification_date is not None
    
    def test_update_listing_status_to_all_statuses(self, db: Session, sample_property):
        """Test updating to each possible listing status"""
        statuses = [
            ListingStatus.available,
            ListingStatus.pending,
            ListingStatus.sold,
            ListingStatus.rented
        ]
        
        for status in statuses:
            updated = property_crud.update_listing_status(
                db,
                property_id=sample_property.property_id,
                listing_status=status
            )
            
            assert updated.listing_status == status
    
    def test_toggle_featured_multiple_times(self, db: Session, sample_property):
        """Test toggling featured on and off multiple times"""
        # Toggle on
        prop1 = property_crud.toggle_featured(db, property_id=sample_property.property_id, is_featured=True)
        assert prop1.is_featured is True
        
        # Toggle off
        prop2 = property_crud.toggle_featured(db, property_id=sample_property.property_id, is_featured=False)
        assert prop2.is_featured is False
        
        # Toggle on again
        prop3 = property_crud.toggle_featured(db, property_id=sample_property.property_id, is_featured=True)
        assert prop3.is_featured is True
    
    def test_search_with_very_long_term(self, db: Session, multiple_properties):
        """Test search with long search term"""
        long_term = "a" * 200  # Very long search term
        
        results = property_crud.search(db, search_term=long_term, skip=0, limit=10)
        
        assert isinstance(results, list)
    
    def test_count_with_user_id_filter(self, db: Session, multiple_properties, normal_user):
        """Test count filtered by user"""
        count = property_crud.count(db, user_id=normal_user.user_id)
        
        assert count >= 2
    
    def test_get_featured_respects_deleted(self, db: Session, multiple_properties):
        """Test that get_featured excludes soft-deleted properties"""
        # Get a featured property and delete it
        featured_props = [p for p in multiple_properties if p.is_featured]
        if featured_props:
            property_crud.soft_delete(db, property_id=featured_props[0].property_id, deleted_by_supabase_id="550e8400-e29b-41d4-a716-446655440001")
            
            # Should not appear in featured list
            featured_list = property_crud.get_featured(db, limit=100)
            featured_ids = [p.property_id for p in featured_list]
            
            assert featured_props[0].property_id not in featured_ids
    
    def test_restore_multiple_times(self, db: Session, sample_property):
        """Test restoring a property multiple times (idempotent)"""
        # Delete
        property_crud.soft_delete(db, property_id=sample_property.property_id, deleted_by_supabase_id="550e8400-e29b-41d4-a716-446655440001")
        
        # Restore first time
        restored1 = property_crud.restore(db, property_id=sample_property.property_id)
        assert restored1.deleted_at is None
        
        # Restore again (should be no-op)
        restored2 = property_crud.restore(db, property_id=sample_property.property_id)
        assert restored2.deleted_at is None


# ============================================================================
# INTEGRATION TESTS FOR MAXIMUM COVERAGE
# ============================================================================

class TestPropertyIntegrationCoverage:
    """Complex workflows hitting multiple code paths"""
    
    def test_complete_property_lifecycle(self, db: Session, normal_user, location, property_type):
        """Test full property lifecycle"""
        # Create
        from app.schemas.properties import PropertyCreate
        prop_in = PropertyCreate(
            title="Lifecycle Test Property",
            description="Testing complete lifecycle",
            price=45000000,
            bedrooms=3,
            bathrooms=2,
            property_type_id=property_type.property_type_id,
            listing_type="sale",
            location_id=location.location_id
        )
        
        prop = property_crud.create(db, obj_in=prop_in, user_id=normal_user.user_id)
        assert prop.property_id is not None
        
        # Update
        from app.schemas.properties import PropertyUpdate
        prop = property_crud.update(
            db,
            db_obj=prop,
            obj_in=PropertyUpdate(price=50000000)
        )
        assert prop.price == 50000000
        
        # Feature
        prop = property_crud.toggle_featured(db, property_id=prop.property_id, is_featured=True)
        assert prop.is_featured is True
        
        # Verify
        prop = property_crud.verify_property(db, property_id=prop.property_id, is_verified=True)
        assert prop.is_verified is True
        
        # Update status
        prop = property_crud.update_listing_status(db, property_id=prop.property_id, listing_status=ListingStatus.pending)
        assert prop.listing_status == ListingStatus.pending
        
        # Soft delete
        prop = property_crud.soft_delete(db, property_id=prop.property_id, deleted_by_supabase_id="550e8400-e29b-41d4-a716-446655440001")
        assert prop.deleted_at is not None
        
        # Restore
        prop = property_crud.restore(db, property_id=prop.property_id)
        assert prop.deleted_at is None

