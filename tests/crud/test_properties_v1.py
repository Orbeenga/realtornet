# tests/crud/test_properties.py
"""
Property CRUD tests - Canonical compliant
Tests: create, read, update, filters, geography, soft delete
Coverage target: app/crud/properties.py (currently 14%)
"""

import pytest
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from app.crud.properties import property as property_crud
from app.models.properties import Property, ListingType, ListingStatus
from app.models.locations import Location
from app.models.property_types import PropertyType
from app.schemas.properties import PropertyCreate, PropertyUpdate, PropertyFilter


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def property_type(db: Session):
    """Create a property type for testing"""
    prop_type = PropertyType(
        name="Apartment",
        description="Modern apartment"
    )
    db.add(prop_type)
    db.commit()
    db.refresh(prop_type)
    return prop_type


@pytest.fixture
def location(db: Session):
    """Create a location for testing"""
    from geoalchemy2.elements import WKTElement
    
    loc = Location(
        state="Lagos",
        city="Ikeja",
        neighborhood="Allen",
        geom=WKTElement('POINT(3.3488 6.6018)', srid=4326),  # Lagos coordinates
        is_active=True
    )
    db.add(loc)
    db.commit()
    db.refresh(loc)
    return loc


@pytest.fixture
def sample_property(db: Session, normal_user, location, property_type):
    """Create a sample property for testing"""
    prop_in = PropertyCreate(
        title="Beautiful 3BR Apartment",
        description="Spacious apartment in prime location",
        price=50000000,
        price_currency="NGN",
        bedrooms=3,
        bathrooms=2,
        property_size=150.5,
        property_type_id=property_type.property_type_id,
        listing_type="sale",
        location_id=location.location_id,
        year_built=2020,
        parking_spaces=2,
        has_garden=True,
        has_security=True,
        has_swimming_pool=False
    )
    
    prop = property_crud.create(
        db,
        obj_in=prop_in,
        user_id=normal_user.user_id
    )
    return prop


# ============================================================================
# CREATE TESTS
# ============================================================================

class TestPropertyCreate:
    """Test property creation"""
    
    def test_create_property_success(self, db: Session, normal_user, location, property_type):
        """Test creating a new property"""
        prop_in = PropertyCreate(
            title="Luxury Villa",
            description="5-bedroom villa with pool",
            price=150000000,
            bedrooms=5,
            bathrooms=4,
            property_type_id=property_type.property_type_id,
            listing_type="sale",
            location_id=location.location_id
        )
        
        prop = property_crud.create(
            db,
            obj_in=prop_in,
            user_id=normal_user.user_id
        )
        
        assert prop.title == "Luxury Villa"
        assert prop.price == 150000000
        assert prop.user_id == normal_user.user_id
        assert prop.is_verified is False
        assert prop.deleted_at is None
        assert prop.listing_status == "available"
    
    def test_create_property_with_all_fields(self, db: Session, normal_user, location, property_type):
        """Test creating property with all optional fields"""
        prop_in = PropertyCreate(
            title="Complete Property",
            description="Property with all fields",
            price=75000000,
            price_currency="NGN",
            bedrooms=4,
            bathrooms=3,
            property_size=200.0,
            property_type_id=property_type.property_type_id,
            listing_type="rent",
            location_id=location.location_id,
            year_built=2022,
            parking_spaces=3,
            has_garden=True,
            has_security=True,
            has_swimming_pool=True
        )
        
        prop = property_crud.create(
            db,
            obj_in=prop_in,
            user_id=normal_user.user_id
        )
        
        assert prop.bedrooms == 4
        assert prop.bathrooms == 3
        assert prop.property_size == 200.0
        assert prop.year_built == 2022
        assert prop.parking_spaces == 3
        assert prop.has_garden is True
        assert prop.has_security is True
        assert prop.has_swimming_pool is True
    
    def test_create_property_invalid_location(self, db: Session, normal_user, property_type):
        """Test creating property with non-existent location fails"""
        from fastapi import HTTPException
        
        prop_in = PropertyCreate(
            title="Bad Location Property",
            description="This should fail",
            price=50000000,
            property_type_id=property_type.property_type_id,
            listing_type="sale",
            location_id=99999  # Non-existent
        )
        
        with pytest.raises(HTTPException) as exc_info:
            property_crud.create(
                db,
                obj_in=prop_in,
                user_id=normal_user.user_id
            )
        
        assert exc_info.value.status_code == 404
        assert "Location" in str(exc_info.value.detail)
    
    def test_create_property_invalid_property_type(self, db: Session, normal_user, location):
        """Test creating property with non-existent property type fails"""
        from fastapi import HTTPException
        
        prop_in = PropertyCreate(
            title="Bad Type Property",
            description="This should fail",
            price=50000000,
            property_type_id=99999,  # Non-existent
            listing_type="sale",
            location_id=location.location_id
        )
        
        with pytest.raises(HTTPException) as exc_info:
            property_crud.create(
                db,
                obj_in=prop_in,
                user_id=normal_user.user_id
            )
        
        assert exc_info.value.status_code == 404
        assert "Property type" in str(exc_info.value.detail)


# ============================================================================
# READ TESTS
# ============================================================================

class TestPropertyRead:
    """Test property retrieval operations"""
    
    def test_get_property_by_id(self, db: Session, sample_property):
        """Test getting property by ID"""
        prop = property_crud.get(db, property_id=sample_property.property_id)
        
        assert prop is not None
        assert prop.property_id == sample_property.property_id
        assert prop.title == sample_property.title
    
    def test_get_property_not_found(self, db: Session):
        """Test getting non-existent property returns None"""
        prop = property_crud.get(db, property_id=99999)
        
        assert prop is None
    
    def test_get_multi_properties(self, db: Session, sample_property):
        """Test getting multiple properties with pagination"""
        props = property_crud.get_multi(db, skip=0, limit=10)
        
        assert len(props) >= 1
        prop_ids = [p.property_id for p in props]
        assert sample_property.property_id in prop_ids
    
    def test_get_multi_by_user(self, db: Session, sample_property, normal_user):
        """Test getting properties filtered by user"""
        props = property_crud.get_multi(
            db,
            user_id=normal_user.user_id,
            skip=0,
            limit=10
        )
        
        assert len(props) >= 1
        assert all(p.user_id == normal_user.user_id for p in props)
    
    def test_get_multi_excludes_deleted(self, db: Session, sample_property):
        """Test get_multi excludes soft-deleted properties by default"""
        # Soft delete the property
        property_crud.soft_delete(
            db, property_id=sample_property.property_id, deleted_by_supabase_id="550e8400-e29b-41d4-a716-446655440001"
        )
        
        # Get all properties
        props = property_crud.get_multi(db, skip=0, limit=100)
        
        # Should not include deleted property
        prop_ids = [p.property_id for p in props]
        assert sample_property.property_id not in prop_ids
    
    def test_get_featured_properties(self, db: Session, sample_property):
        """Test getting featured properties"""
        # Mark property as featured
        sample_property.is_featured = True
        sample_property.listing_status = ListingStatus.available
        db.commit()
        
        featured = property_crud.get_featured(db, limit=10)
        
        assert len(featured) >= 1
        prop_ids = [p.property_id for p in featured]
        assert sample_property.property_id in prop_ids
        assert all(p.is_featured for p in featured)
    
    def test_count_properties(self, db: Session, sample_property):
        """Test counting properties"""
        count = property_crud.count(db)
        
        assert count >= 1
    
    def test_count_properties_by_user(self, db: Session, sample_property, normal_user):
        """Test counting properties for specific user"""
        count = property_crud.count(db, user_id=normal_user.user_id)
        
        assert count >= 1
    
    def test_search_properties(self, db: Session, sample_property):
        """Test searching properties by text"""
        results = property_crud.search(db, search_term="Beautiful", skip=0, limit=10)
        
        assert len(results) >= 1
        prop_ids = [p.property_id for p in results]
        assert sample_property.property_id in prop_ids


# ============================================================================
# UPDATE TESTS
# ============================================================================

class TestPropertyUpdate:
    """Test property update operations"""
    
    def test_update_property_basic_fields(self, db: Session, sample_property):
        """Test updating basic property fields"""
        update_data = PropertyUpdate(
            title="Updated Title",
            price=60000000,
            bedrooms=4
        )
        
        updated = property_crud.update(
            db,
            db_obj=sample_property,
            obj_in=update_data
        )
        
        assert updated.title == "Updated Title"
        assert updated.price == 60000000
        assert updated.bedrooms == 4
    
    def test_update_property_listing_status(self, db: Session, sample_property):
        """Test updating listing status"""
        updated = property_crud.update_listing_status(
            db,
            property_id=sample_property.property_id,
            listing_status=ListingStatus.sold
        )
        
        assert updated is not None
        assert updated.listing_status == ListingStatus.sold
    
    def test_verify_property(self, db: Session, sample_property):
        """Test verifying a property"""
        verified = property_crud.verify_property(
            db,
            property_id=sample_property.property_id,
            is_verified=True
        )
        
        assert verified is not None
        assert verified.is_verified is True
        assert verified.verification_date is not None
    
    def test_toggle_featured_on(self, db: Session, sample_property):
        """Test toggling featured status on"""
        updated = property_crud.toggle_featured(
            db,
            property_id=sample_property.property_id,
            is_featured=True
        )
        
        assert updated is not None
        assert updated.is_featured is True
    
    def test_toggle_featured_off(self, db: Session, sample_property):
        """Test toggling featured status off"""
        # First set it to True
        sample_property.is_featured = True
        db.commit()
        
        # Then toggle off
        updated = property_crud.toggle_featured(
            db,
            property_id=sample_property.property_id,
            is_featured=False
        )
        
        assert updated is not None
        assert updated.is_featured is False


# ============================================================================
# DELETE TESTS
# ============================================================================

class TestPropertyDelete:
    """Test property deletion operations"""
    
    def test_soft_delete_property(self, db: Session, sample_property):
        """Test soft deleting a property"""
        deleted = property_crud.soft_delete(
            db,
            property_id=sample_property.property_id,
            deleted_by_supabase_id="550e8400-e29b-41d4-a716-446655440001"
        )
        
        assert deleted is not None
        assert deleted.deleted_at is not None
    
    def test_soft_deleted_excluded_from_queries(self, db: Session, sample_property):
        """Test soft-deleted properties are excluded from get_multi"""
        # Soft delete
        property_crud.soft_delete(
            db, property_id=sample_property.property_id, deleted_by_supabase_id="550e8400-e29b-41d4-a716-446655440001"
        )
        
        # Try to get all properties
        props = property_crud.get_multi(db, skip=0, limit=100)
        
        # Should not find deleted property
        prop_ids = [p.property_id for p in props]
        assert sample_property.property_id not in prop_ids
    
    def test_restore_soft_deleted_property(self, db: Session, sample_property):
        """Test restoring a soft-deleted property"""
        # Soft delete first
        property_crud.soft_delete(
            db, property_id=sample_property.property_id, deleted_by_supabase_id="550e8400-e29b-41d4-a716-446655440001"
        )
        
        # Restore
        restored = property_crud.restore(
            db,
            property_id=sample_property.property_id
        )
        
        assert restored is not None
        assert restored.deleted_at is None


# ============================================================================
# AUTHORIZATION TESTS
# ============================================================================

class TestPropertyAuthorization:
    """Test property authorization helpers"""
    
    def test_can_modify_property_owner(self, db: Session, sample_property, normal_user):
        """Test owner can modify their property"""
        can_modify = property_crud.can_modify_property(
            current_user_id=normal_user.user_id,
            property_user_id=sample_property.user_id,
            is_admin=False
        )
        
        assert can_modify is True
    
    def test_can_modify_property_not_owner(self, db: Session, sample_property, agent_user):
        """Test non-owner cannot modify property"""
        can_modify = property_crud.can_modify_property(
            current_user_id=agent_user.user_id,
            property_user_id=sample_property.user_id,
            is_admin=False
        )
        
        assert can_modify is False
    
    def test_can_modify_property_admin(self, db: Session, sample_property, admin_user):
        """Test admin can modify any property"""
        can_modify = property_crud.can_modify_property(
            current_user_id=admin_user.user_id,
            property_user_id=sample_property.user_id,
            is_admin=True
        )
        
        assert can_modify is True

