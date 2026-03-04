# tests/crud/test_agencies.py
"""
Surgical tests for app/crud/agencies.py - Targeting missing lines to push 21% → 85%+

Canonical audit trail for agencies:
- created_at, created_by (on create)
- updated_at, updated_by (on update - updated_by MANDATORY)
- deleted_at, deleted_by (on soft delete)

Missing lines from coverage report:
- 34-37: get() with include_deleted parameter
- 44, 56: get_by_email, get_by_name
- 75-87: get_multi with is_verified filter
- 102-116: search with NULL-safe description
- 120-127: count with verification filter
- 150-189: create with duplicate checking
- 212-259: update with uniqueness validation
- 275-299: soft_delete with audit trail
- 309-331: get_stats aggregation
"""

import pytest
from sqlalchemy.orm import Session
from app.crud.agencies import agency as agency_crud
from app.schemas.agencies import AgencyCreate, AgencyUpdate
from app.models.agencies import Agency
import uuid


class TestAgencyGetVariations:
    """Target lines 34-37: get() with include_deleted parameter"""
    
    def test_get_excludes_deleted_by_default(self, db: Session):
        """Verify deleted agencies are excluded by default"""
        # Create and delete an agency
        created = agency_crud.create(
            db,
            obj_in=AgencyCreate(
                name="Deleted Agency",
                email="deleted@agency.com"
            ),
            created_by=str(uuid.uuid4())
        )
        
        agency_crud.soft_delete(
            db,
            agency_id=created.agency_id,
            deleted_by_supabase_id=str(uuid.uuid4())
        )
        
        # Default get should return None
        result = agency_crud.get(db, agency_id=created.agency_id)
        assert result is None
    
    def test_get_includes_deleted_when_requested(self, db: Session):
        """Target line 35: include_deleted=True branch"""
        # Create and delete an agency
        created = agency_crud.create(
            db,
            obj_in=AgencyCreate(
                name="Soft Deleted Agency",
                email="softdeleted@agency.com"
            ),
            created_by=str(uuid.uuid4())
        )
        
        agency_crud.soft_delete(
            db,
            agency_id=created.agency_id,
            deleted_by_supabase_id=str(uuid.uuid4())
        )
        
        # With include_deleted=True, should return the agency
        result = agency_crud.get(db, agency_id=created.agency_id, include_deleted=True)
        assert result is not None
        assert result.agency_id == created.agency_id
        assert result.deleted_at is not None


class TestAgencyLookupMethods:
    """Target lines 44, 56: get_by_email, get_by_name"""
    
    def test_get_by_email(self, db: Session):
        """Target line 44: get_by_email implementation"""
        created = agency_crud.create(
            db,
            obj_in=AgencyCreate(
                name="Email Test Agency",
                email="email.test@agency.com"
            ),
            created_by=str(uuid.uuid4())
        )
        
        # Lookup by email
        found = agency_crud.get_by_email(db, email="email.test@agency.com")
        assert found is not None
        assert found.agency_id == created.agency_id
        
        # Case insensitive
        found_upper = agency_crud.get_by_email(db, email="EMAIL.TEST@AGENCY.COM")
        assert found_upper is not None
        assert found_upper.agency_id == created.agency_id
    
    def test_get_by_email_excludes_deleted(self, db: Session):
        """Verify deleted agencies don't show up in email lookup"""
        created = agency_crud.create(
            db,
            obj_in=AgencyCreate(
                name="Deleted Email Agency",
                email="deleted.email@agency.com"
            ),
            created_by=str(uuid.uuid4())
        )
        
        agency_crud.soft_delete(
            db,
            agency_id=created.agency_id,
            deleted_by_supabase_id=str(uuid.uuid4())
        )
        
        # Should not find deleted agency
        result = agency_crud.get_by_email(db, email="deleted.email@agency.com")
        assert result is None
    
    def test_get_by_name(self, db: Session):
        """Target line 56: get_by_name implementation"""
        created = agency_crud.create(
            db,
            obj_in=AgencyCreate(
                name="Unique Name Agency",
                email="uniquename@agency.com"
            ),
            created_by=str(uuid.uuid4())
        )
        
        # Lookup by name (case insensitive)
        found = agency_crud.get_by_name(db, name="Unique Name Agency")
        assert found is not None
        assert found.agency_id == created.agency_id
        
        # Case variations
        found_lower = agency_crud.get_by_name(db, name="unique name agency")
        assert found_lower is not None
        
        found_upper = agency_crud.get_by_name(db, name="UNIQUE NAME AGENCY")
        assert found_upper is not None


class TestAgencyGetMultiFilters:
    """Target lines 75-87: get_multi with is_verified filter"""
    
    def test_get_multi_all_agencies(self, db: Session):
        """Get all non-deleted agencies"""
        agency_crud.create(
            db,
            obj_in=AgencyCreate(name="Agency 1", email="a1@test.com"),
            created_by=str(uuid.uuid4())
        )
        agency_crud.create(
            db,
            obj_in=AgencyCreate(name="Agency 2", email="a2@test.com"),
            created_by=str(uuid.uuid4())
        )
        
        agencies = agency_crud.get_multi(db)
        assert len(agencies) >= 2
    
    def test_get_multi_with_verification_filter(self, db: Session):
        """Target lines 81-82: is_verified filter"""
        # Create verified agency
        verified = agency_crud.create(
            db,
            obj_in=AgencyCreate(
                name="Verified Agency",
                email="verified@agency.com"
            ),
            created_by=str(uuid.uuid4())
        )
        verified.is_verified = True
        db.add(verified)
        db.commit()
        
        # Create unverified agency
        unverified = agency_crud.create(
            db,
            obj_in=AgencyCreate(
                name="Unverified Agency",
                email="unverified@agency.com"
            ),
            created_by=str(uuid.uuid4())
        )
        
        # Filter for verified only
        verified_agencies = agency_crud.get_multi(db, is_verified=True)
        verified_ids = [a.agency_id for a in verified_agencies]
        
        assert verified.agency_id in verified_ids
        assert unverified.agency_id not in verified_ids
        
        # Filter for unverified only
        unverified_agencies = agency_crud.get_multi(db, is_verified=False)
        unverified_ids = [a.agency_id for a in unverified_agencies]
        
        assert unverified.agency_id in unverified_ids
        assert verified.agency_id not in unverified_ids
    
    def test_get_multi_excludes_deleted(self, db: Session):
        """Verify soft-deleted agencies are excluded"""
        active = agency_crud.create(
            db,
            obj_in=AgencyCreate(name="Active Agency", email="active@test.com"),
            created_by=str(uuid.uuid4())
        )
        
        deleted = agency_crud.create(
            db,
            obj_in=AgencyCreate(name="Deleted Agency", email="deleted@test.com"),
            created_by=str(uuid.uuid4())
        )
        agency_crud.soft_delete(
            db,
            agency_id=deleted.agency_id,
            deleted_by_supabase_id=str(uuid.uuid4())
        )
        
        agencies = agency_crud.get_multi(db)
        agency_ids = [a.agency_id for a in agencies]
        
        assert active.agency_id in agency_ids
        assert deleted.agency_id not in agency_ids


class TestAgencySearch:
    """Target lines 102-116: search with NULL-safe description"""
    
    def test_search_by_name(self, db: Session):
        """Search agencies by name"""
        agency_crud.create(
            db,
            obj_in=AgencyCreate(
                name="Premium Real Estate",
                email="premium@agency.com"
            ),
            created_by=str(uuid.uuid4())
        )
        
        results = agency_crud.search(db, search_term="Premium")
        assert len(results) >= 1
        assert any("Premium" in a.name for a in results)
    
    def test_search_by_email(self, db: Session):
        """Search agencies by email"""
        agency_crud.create(
            db,
            obj_in=AgencyCreate(
                name="Email Search Agency",
                email="searchable@agency.com"
            ),
            created_by=str(uuid.uuid4())
        )
        
        results = agency_crud.search(db, search_term="searchable")
        assert len(results) >= 1
    
    def test_search_by_description(self, db: Session):
        """Target lines 109-112: NULL-safe description search"""
        agency_crud.create(
            db,
            obj_in=AgencyCreate(
                name="Described Agency",
                email="described@agency.com",
                description="Leading property management firm specializing in luxury"
            ),
            created_by=str(uuid.uuid4())
        )
        
        # Search by description content
        results = agency_crud.search(db, search_term="luxury")
        assert len(results) >= 1
    
    def test_search_with_null_description(self, db: Session):
        """Verify search doesn't crash on NULL description"""
        agency_crud.create(
            db,
            obj_in=AgencyCreate(
                name="No Description Agency",
                email="nodesc@agency.com"
                # description intentionally omitted
            ),
            created_by=str(uuid.uuid4())
        )
        
        # Search shouldn't crash on NULL description
        results = agency_crud.search(db, search_term="No Description")
        assert len(results) >= 1
    
    def test_search_case_insensitive(self, db: Session):
        """Verify search is case insensitive"""
        agency_crud.create(
            db,
            obj_in=AgencyCreate(
                name="Case Test Agency",
                email="casetest@agency.com"
            ),
            created_by=str(uuid.uuid4())
        )
        
        results = agency_crud.search(db, search_term="CASE TEST")
        assert len(results) >= 1


class TestAgencyCount:
    """Target lines 120-127: count with verification filter"""
    
    def test_count_all_agencies(self, db: Session):
        """Count all non-deleted agencies"""
        initial_count = agency_crud.count(db)
        
        agency_crud.create(
            db,
            obj_in=AgencyCreate(name="Count Test 1", email="count1@test.com"),
            created_by=str(uuid.uuid4())
        )
        agency_crud.create(
            db,
            obj_in=AgencyCreate(name="Count Test 2", email="count2@test.com"),
            created_by=str(uuid.uuid4())
        )
        
        new_count = agency_crud.count(db)
        assert new_count == initial_count + 2
    
    def test_count_with_verification_filter(self, db: Session):
        """Target line 125: is_verified filter in count"""
        # Create verified agency
        verified = agency_crud.create(
            db,
            obj_in=AgencyCreate(name="Verified Count", email="vcount@test.com"),
            created_by=str(uuid.uuid4())
        )
        verified.is_verified = True
        db.add(verified)
        db.commit()
        
        # Create unverified
        agency_crud.create(
            db,
            obj_in=AgencyCreate(name="Unverified Count", email="ucount@test.com"),
            created_by=str(uuid.uuid4())
        )
        
        verified_count = agency_crud.count(db, is_verified=True)
        unverified_count = agency_crud.count(db, is_verified=False)
        
        assert verified_count >= 1
        assert unverified_count >= 1


class TestAgencyCreateValidation:
    """Target lines 150-189: create with duplicate checking"""
    
    def test_create_agency_basic(self, db: Session):
        """Basic agency creation"""
        creator_id = str(uuid.uuid4())
        
        agency = agency_crud.create(
            db,
            obj_in=AgencyCreate(
                name="Basic Agency",
                email="basic@agency.com",
                phone_number="+2348012345678"
            ),
            created_by=creator_id
        )
        
        assert agency.agency_id is not None
        assert agency.name == "Basic Agency"
        assert agency.email == "basic@agency.com"
        assert agency.is_verified is False
        assert str(agency.created_by) == creator_id
    
    def test_create_duplicate_email_raises_error(self, db: Session):
        """Target lines 154-156: Duplicate email validation"""
        agency_crud.create(
            db,
            obj_in=AgencyCreate(
                name="First Agency",
                email="duplicate@agency.com"
            ),
            created_by=str(uuid.uuid4())
        )
        
        # Attempt to create with same email
        with pytest.raises(ValueError, match="email.*already exists"):
            agency_crud.create(
                db,
                obj_in=AgencyCreate(
                    name="Second Agency",
                    email="duplicate@agency.com"
                ),
                created_by=str(uuid.uuid4())
            )
    
    def test_create_duplicate_name_raises_error(self, db: Session):
        """Target lines 159-161: Duplicate name validation"""
        agency_crud.create(
            db,
            obj_in=AgencyCreate(
                name="Unique Name",
                email="first@agency.com"
            ),
            created_by=str(uuid.uuid4())
        )
        
        # Attempt to create with same name
        with pytest.raises(ValueError, match="name.*already exists"):
            agency_crud.create(
                db,
                obj_in=AgencyCreate(
                    name="Unique Name",
                    email="second@agency.com"
                ),
                created_by=str(uuid.uuid4())
            )
    
    def test_create_with_optional_fields(self, db: Session):
        """Test creation with all optional fields"""
        agency = agency_crud.create(
            db,
            obj_in=AgencyCreate(
                name="Full Fields Agency",
                email="full@agency.com",
                phone_number="+2348098765432",
                address="123 Main Street, Lagos",
                description="Full service real estate agency",
                logo_url="https://example.com/logo.png",
                website_url="https://example.com"
            ),
            created_by=str(uuid.uuid4())
        )
        
        assert agency.phone_number == "+2348098765432"
        assert agency.address == "123 Main Street, Lagos"
        assert agency.description is not None
        assert agency.logo_url is not None
        assert agency.website_url is not None
    
    def test_create_email_lowercased(self, db: Session):
        """Verify email is stored in lowercase"""
        agency = agency_crud.create(
            db,
            obj_in=AgencyCreate(
                name="Lowercase Test",
                email="UPPERCASE@AGENCY.COM"
            ),
            created_by=str(uuid.uuid4())
        )
        
        assert agency.email == "uppercase@agency.com"


class TestAgencyUpdateValidation:
    """Target lines 212-259: update with uniqueness validation"""
    
    def test_update_basic_fields(self, db: Session):
        """Basic field updates"""
        agency = agency_crud.create(
            db,
            obj_in=AgencyCreate(
                name="Original Name",
                email="original@agency.com"
            ),
            created_by=str(uuid.uuid4())
        )
        
        updater_id = str(uuid.uuid4())
        
        updated = agency_crud.update(
            db,
            db_obj=agency,
            obj_in=AgencyUpdate(
                name="Updated Name",
                description="New description"
            ),
            updated_by=updater_id
        )
        
        assert updated.name == "Updated Name"
        assert updated.description == "New description"
        assert str(updated.updated_by) == updater_id
    
    def test_update_email_uniqueness_check(self, db: Session):
        """Target lines 223-228: Email uniqueness on update"""
        agency1 = agency_crud.create(
            db,
            obj_in=AgencyCreate(name="Agency 1", email="agency1@test.com"),
            created_by=str(uuid.uuid4())
        )
        
        agency2 = agency_crud.create(
            db,
            obj_in=AgencyCreate(name="Agency 2", email="agency2@test.com"),
            created_by=str(uuid.uuid4())
        )
        
        # Try to update agency2 to use agency1's email
        with pytest.raises(ValueError, match="email.*already exists"):
            agency_crud.update(
                db,
                db_obj=agency2,
                obj_in=AgencyUpdate(email="agency1@test.com"),
                updated_by=str(uuid.uuid4())
            )
    
    def test_update_name_uniqueness_check(self, db: Session):
        """Target lines 231-235: Name uniqueness on update"""
        agency1 = agency_crud.create(
            db,
            obj_in=AgencyCreate(name="First Name", email="first@test.com"),
            created_by=str(uuid.uuid4())
        )
        
        agency2 = agency_crud.create(
            db,
            obj_in=AgencyCreate(name="Second Name", email="second@test.com"),
            created_by=str(uuid.uuid4())
        )
        
        # Try to update agency2 to use agency1's name
        with pytest.raises(ValueError, match="name.*already exists"):
            agency_crud.update(
                db,
                db_obj=agency2,
                obj_in=AgencyUpdate(name="First Name"),
                updated_by=str(uuid.uuid4())
            )
    
    def test_update_same_email_allowed(self, db: Session):
        """Verify updating to same email doesn't trigger uniqueness error"""
        agency = agency_crud.create(
            db,
            obj_in=AgencyCreate(name="Same Email Test", email="same@test.com"),
            created_by=str(uuid.uuid4())
        )
        
        # Update other fields while keeping same email
        updated = agency_crud.update(
            db,
            db_obj=agency,
            obj_in=AgencyUpdate(email="same@test.com", description="Updated"),
            updated_by=str(uuid.uuid4())
        )
        
        assert updated.email == "same@test.com"
        assert updated.description == "Updated"
    
    def test_update_with_dict_input(self, db: Session):
        """Target line 217: dict input branch"""
        agency = agency_crud.create(
            db,
            obj_in=AgencyCreate(name="Dict Update", email="dict@test.com"),
            created_by=str(uuid.uuid4())
        )
        
        updated = agency_crud.update(
            db,
            db_obj=agency,
            obj_in={"description": "Updated via dict"},
            updated_by=str(uuid.uuid4())
        )
        
        assert updated.description == "Updated via dict"
    
    def test_update_protected_fields_ignored(self, db: Session):
        """Target lines 238-240: Protected fields removal"""
        agency = agency_crud.create(
            db,
            obj_in=AgencyCreate(name="Protected Test", email="protected@test.com"),
            created_by=str(uuid.uuid4())
        )
        
        original_id = agency.agency_id
        original_created_by = agency.created_by
        
        # Try to update protected fields
        updated = agency_crud.update(
            db,
            db_obj=agency,
            obj_in={
                "agency_id": 99999,
                "created_by": "fake-uuid",
                "description": "Allowed update"
            },
            updated_by=str(uuid.uuid4())
        )
        
        # Protected fields unchanged
        assert updated.agency_id == original_id
        assert updated.created_by == original_created_by
        # Non-protected field updated
        assert updated.description == "Allowed update"


class TestAgencySoftDelete:
    """Target lines 275-299: soft_delete with audit trail"""
    
    def test_soft_delete_sets_timestamps(self, db: Session):
        """Verify deleted_at is set"""
        agency = agency_crud.create(
            db,
            obj_in=AgencyCreate(name="Delete Test", email="delete@test.com"),
            created_by=str(uuid.uuid4())
        )
        
        deleter_id = str(uuid.uuid4())
        
        deleted = agency_crud.soft_delete(
            db,
            agency_id=agency.agency_id,
            deleted_by_supabase_id=deleter_id
        )
        
        assert deleted.deleted_at is not None
        assert str(deleted.deleted_by) == deleter_id
    
    def test_soft_delete_nonexistent_raises_error(self, db: Session):
        """Target line 280: Non-existent agency error"""
        with pytest.raises(ValueError, match="not found"):
            agency_crud.soft_delete(db, agency_id=999999)
    
    def test_soft_delete_already_deleted_raises_error(self, db: Session):
        """Target line 284: Already deleted error"""
        agency = agency_crud.create(
            db,
            obj_in=AgencyCreate(name="Double Delete", email="double@test.com"),
            created_by=str(uuid.uuid4())
        )
        
        # First delete
        agency_crud.soft_delete(db, agency_id=agency.agency_id)
        
        # Second delete should raise error
        with pytest.raises(ValueError, match="already deleted"):
            agency_crud.soft_delete(db, agency_id=agency.agency_id)


class TestAgencyStatistics:
    """Target lines 309-331: get_stats aggregation"""
    
    def test_get_stats_basic(self, db: Session):
        """Test statistics aggregation"""
        agency = agency_crud.create(
            db,
            obj_in=AgencyCreate(name="Stats Agency", email="stats@test.com"),
            created_by=str(uuid.uuid4())
        )
        
        stats = agency_crud.get_stats(db, agency_id=agency.agency_id)
        
        assert "agent_count" in stats
        assert "property_count" in stats
        assert isinstance(stats["agent_count"], int)
        assert isinstance(stats["property_count"], int)
    
    def test_get_stats_empty_agency(self, db: Session):
        """Stats for agency with no agents/properties"""
        agency = agency_crud.create(
            db,
            obj_in=AgencyCreate(name="Empty Stats", email="emptystats@test.com"),
            created_by=str(uuid.uuid4())
        )
        
        stats = agency_crud.get_stats(db, agency_id=agency.agency_id)
        
        assert stats["agent_count"] == 0
        assert stats["property_count"] == 0