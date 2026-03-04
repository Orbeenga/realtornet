# tests/crud/agent_profiles.py
"""
Surgical tests for app/crud/agent_profiles.py - Targeting 22% → 90%+

Canonical audit trail for agent_profiles:
- created_at, created_by (on create)
- updated_at, updated_by (on update - updated_by MANDATORY)
- deleted_at, deleted_by (on soft delete)

Missing lines from coverage report:
- 34-37: get() filtering soft-deleted
- 44, 56: get_by_user_id, get_by_license
- 74-80: get_multi pagination
- 94-101: get_by_agency filtering
- 116-140: search with NULL-safe fields
- 147: count_by_agency
- 162-169: _validate_user_is_agent
- 176-183: _validate_agency_exists
- 206-253: create with validation
- 278-336: update with business rules
- 352-377: soft_delete with audit
- 387-418: get_stats aggregation
"""

import pytest
from sqlalchemy.orm import Session
from app.crud.agent_profiles import agent_profile as agent_profile_crud
from app.crud.agencies import agency as agency_crud
from app.crud.users import user as user_crud
from app.schemas.agent_profiles import AgentProfileCreate, AgentProfileUpdate
from app.schemas.agencies import AgencyCreate
from app.schemas.users import UserCreate
from app.models.users import UserRole
from app.models.agent_profiles import AgentProfile
import uuid


class TestAgentProfileGet:
    """Target lines 34-37: get() filtering soft-deleted"""
    
    def test_get_excludes_soft_deleted(self, db: Session, normal_user, agency):
        """Verify soft-deleted profiles are excluded"""
        # Create agent user
        agent_user = user_crud.create(
            db,
            obj_in=UserCreate(
                email="agent.deleted@test.com",
                password="Test123!",
                first_name="Deleted",
                last_name="Agent",
                user_role=UserRole.AGENT
            ),
            supabase_id=str(uuid.uuid4())
        )
        
        profile = agent_profile_crud.create(
            db,
            obj_in=AgentProfileCreate(
                user_id=agent_user.user_id,
                agency_id=agency.agency_id,
                license_number="LIC001"
            ),
            created_by=str(uuid.uuid4())
        )
        
        # Soft delete
        agent_profile_crud.soft_delete(
            db,
            profile_id=profile.profile_id,
            deleted_by_supabase_id=str(uuid.uuid4())
        )
        
        # Should return None
        result = agent_profile_crud.get(db, profile_id=profile.profile_id)
        assert result is None


class TestAgentProfileLookups:
    """Target lines 44, 56: get_by_user_id, get_by_license"""
    
    def test_get_by_user_id(self, db: Session, agency):
        """Target line 44: get_by_user_id implementation"""
        agent_user = user_crud.create(
            db,
            obj_in=UserCreate(
                email="agent.lookup@test.com",
                password="Test123!",
                first_name="Lookup",
                last_name="Agent",
                user_role=UserRole.AGENT
            ),
            supabase_id=str(uuid.uuid4())
        )
        
        profile = agent_profile_crud.create(
            db,
            obj_in=AgentProfileCreate(
                user_id=agent_user.user_id,
                agency_id=agency.agency_id
            ),
            created_by=str(uuid.uuid4())
        )
        
        found = agent_profile_crud.get_by_user_id(db, user_id=agent_user.user_id)
        assert found is not None
        assert found.profile_id == profile.profile_id
    
    def test_get_by_license(self, db: Session, agency):
        """Target line 56: get_by_license implementation"""
        agent_user = user_crud.create(
            db,
            obj_in=UserCreate(
                email="agent.license@test.com",
                password="Test123!",
                first_name="Licensed",
                last_name="Agent",
                user_role=UserRole.AGENT
            ),
            supabase_id=str(uuid.uuid4())
        )
        
        profile = agent_profile_crud.create(
            db,
            obj_in=AgentProfileCreate(
                user_id=agent_user.user_id,
                agency_id=agency.agency_id,
                license_number="LIC-UNIQUE-123"
            ),
            created_by=str(uuid.uuid4())
        )
        
        found = agent_profile_crud.get_by_license(db, license_number="LIC-UNIQUE-123")
        assert found is not None
        assert found.profile_id == profile.profile_id


class TestAgentProfileGetMulti:
    """Target lines 74-80: get_multi with pagination"""
    
    def test_get_multi_pagination(self, db: Session, agency):
        """Test pagination and ordering"""
        # Create multiple agent profiles
        for i in range(5):
            agent_user = user_crud.create(
                db,
                obj_in=UserCreate(
                    email=f"agent{i}@test.com",
                    password="Test123!",
                    first_name=f"Agent{i}",
                    last_name="Test",
                    user_role=UserRole.AGENT
                ),
                supabase_id=str(uuid.uuid4())
            )
            
            agent_profile_crud.create(
                db,
                obj_in=AgentProfileCreate(
                    user_id=agent_user.user_id,
                    agency_id=agency.agency_id
                ),
                created_by=str(uuid.uuid4())
            )
        
        # Test pagination
        first_page = agent_profile_crud.get_multi(db, skip=0, limit=3)
        assert len(first_page) == 3
        
        second_page = agent_profile_crud.get_multi(db, skip=3, limit=3)
        assert len(second_page) >= 2


class TestAgentProfileGetByAgency:
    """Target lines 94-101: get_by_agency filtering"""
    
    def test_get_by_agency(self, db: Session):
        """Test filtering profiles by agency"""
        # Create two agencies
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
        
        # Create agents for each agency
        agent1 = user_crud.create(
            db,
            obj_in=UserCreate(
                email="agent1@test.com",
                password="Test123!",
                first_name="Agent1",
                last_name="One",
                user_role=UserRole.AGENT
            ),
            supabase_id=str(uuid.uuid4())
        )
        
        profile1 = agent_profile_crud.create(
            db,
            obj_in=AgentProfileCreate(
                user_id=agent1.user_id,
                agency_id=agency1.agency_id
            ),
            created_by=str(uuid.uuid4())
        )
        
        agent2 = user_crud.create(
            db,
            obj_in=UserCreate(
                email="agent2@test.com",
                password="Test123!",
                first_name="Agent2",
                last_name="Two",
                user_role=UserRole.AGENT
            ),
            supabase_id=str(uuid.uuid4())
        )
        
        profile2 = agent_profile_crud.create(
            db,
            obj_in=AgentProfileCreate(
                user_id=agent2.user_id,
                agency_id=agency2.agency_id
            ),
            created_by=str(uuid.uuid4())
        )
        
        # Get profiles for agency 1
        agency1_profiles = agent_profile_crud.get_by_agency(
            db,
            agency_id=agency1.agency_id
        )
        profile_ids = [p.profile_id for p in agency1_profiles]
        
        assert profile1.profile_id in profile_ids
        assert profile2.profile_id not in profile_ids


class TestAgentProfileSearch:
    """Target lines 116-140: search with NULL-safe fields"""
    
    def test_search_by_license(self, db: Session, agency):
        """Search by license number"""
        agent_user = user_crud.create(
            db,
            obj_in=UserCreate(
                email="search.license@test.com",
                password="Test123!",
                first_name="Search",
                last_name="Agent",
                user_role=UserRole.AGENT
            ),
            supabase_id=str(uuid.uuid4())
        )
        
        agent_profile_crud.create(
            db,
            obj_in=AgentProfileCreate(
                user_id=agent_user.user_id,
                agency_id=agency.agency_id,
                license_number="SEARCH-LIC-789"
            ),
            created_by=str(uuid.uuid4())
        )
        
        results = agent_profile_crud.search(db, search_term="SEARCH-LIC")
        assert len(results) >= 1
    
    def test_search_by_specialization(self, db: Session, agency):
        """Search by specialization"""
        agent_user = user_crud.create(
            db,
            obj_in=UserCreate(
                email="spec.agent@test.com",
                password="Test123!",
                first_name="Specialist",
                last_name="Agent",
                user_role=UserRole.AGENT
            ),
            supabase_id=str(uuid.uuid4())
        )
        
        agent_profile_crud.create(
            db,
            obj_in=AgentProfileCreate(
                user_id=agent_user.user_id,
                agency_id=agency.agency_id,
                specialization="Luxury Properties"
            ),
            created_by=str(uuid.uuid4())
        )
        
        results = agent_profile_crud.search(db, search_term="Luxury")
        assert len(results) >= 1
    
    def test_search_with_null_fields(self, db: Session, agency):
        """Verify search doesn't crash on NULL fields"""
        agent_user = user_crud.create(
            db,
            obj_in=UserCreate(
                email="minimal.agent@test.com",
                password="Test123!",
                first_name="Minimal",
                last_name="Agent",
                user_role=UserRole.AGENT
            ),
            supabase_id=str(uuid.uuid4())
        )
        
        # Create with minimal fields (NULLs)
        agent_profile_crud.create(
            db,
            obj_in=AgentProfileCreate(
                user_id=agent_user.user_id,
                agency_id=agency.agency_id
                # All optional fields omitted
            ),
            created_by=str(uuid.uuid4())
        )
        
        # Search shouldn't crash
        results = agent_profile_crud.search(db, search_term="anything")
        assert isinstance(results, list)


class TestAgentProfileCountByAgency:
    """Target line 147: count_by_agency"""
    
    def test_count_by_agency(self, db: Session, agency):
        """Count agents for a specific agency"""
        initial_count = agent_profile_crud.count_by_agency(
            db,
            agency_id=agency.agency_id
        )
        
        # Create agent profile
        agent_user = user_crud.create(
            db,
            obj_in=UserCreate(
                email="count.agent@test.com",
                password="Test123!",
                first_name="Count",
                last_name="Agent",
                user_role=UserRole.AGENT
            ),
            supabase_id=str(uuid.uuid4())
        )
        
        agent_profile_crud.create(
            db,
            obj_in=AgentProfileCreate(
                user_id=agent_user.user_id,
                agency_id=agency.agency_id
            ),
            created_by=str(uuid.uuid4())
        )
        
        new_count = agent_profile_crud.count_by_agency(
            db,
            agency_id=agency.agency_id
        )
        
        assert new_count == initial_count + 1


class TestAgentProfileValidation:
    """Target lines 162-169, 176-183: Validation helpers"""
    
    def test_validate_user_is_agent_fails_for_seeker(self, db: Session):
        """Target line 167: Non-agent user validation"""
        seeker = user_crud.create(
            db,
            obj_in=UserCreate(
                email="seeker@test.com",
                password="Test123!",
                first_name="Seeker",
                last_name="User",
                user_role=UserRole.SEEKER
            ),
            supabase_id=str(uuid.uuid4())
        )
        
        with pytest.raises(ValueError, match="must have agent role"):
            agent_profile_crud._validate_user_is_agent(db, user_id=seeker.user_id)
    
    def test_validate_user_nonexistent(self, db: Session):
        """Target line 165: User not found validation"""
        with pytest.raises(ValueError, match="not found"):
            agent_profile_crud._validate_user_is_agent(db, user_id=999999)
    
    def test_validate_agency_deleted(self, db: Session):
        """Target line 181: Deleted agency validation"""
        agency = agency_crud.create(
            db,
            obj_in=AgencyCreate(name="Deleted Agency", email="deleted@agency.com"),
            created_by=str(uuid.uuid4())
        )
        
        # Soft delete agency
        agency_crud.soft_delete(
            db,
            agency_id=agency.agency_id,
            deleted_by_supabase_id=str(uuid.uuid4())
        )
        
        with pytest.raises(ValueError, match="is deleted"):
            agent_profile_crud._validate_agency_exists(db, agency_id=agency.agency_id)


class TestAgentProfileCreate:
    """Target lines 206-253: create with validation"""
    
    def test_create_basic(self, db: Session, agency):
        """Basic agent profile creation"""
        agent_user = user_crud.create(
            db,
            obj_in=UserCreate(
                email="create.agent@test.com",
                password="Test123!",
                first_name="Create",
                last_name="Agent",
                user_role=UserRole.AGENT
            ),
            supabase_id=str(uuid.uuid4())
        )
        
        creator_id = str(uuid.uuid4())
        
        profile = agent_profile_crud.create(
            db,
            obj_in=AgentProfileCreate(
                user_id=agent_user.user_id,
                agency_id=agency.agency_id,
                license_number="LIC-CREATE-001",
                years_experience=5
            ),
            created_by=creator_id
        )
        
        assert profile.profile_id is not None
        assert profile.user_id == agent_user.user_id
        assert str(profile.created_by) == creator_id
    
    def test_create_duplicate_user_raises_error(self, db: Session, agency):
        """Target line 216: Duplicate user validation"""
        agent_user = user_crud.create(
            db,
            obj_in=UserCreate(
                email="duplicate.agent@test.com",
                password="Test123!",
                first_name="Duplicate",
                last_name="Agent",
                user_role=UserRole.AGENT
            ),
            supabase_id=str(uuid.uuid4())
        )
        
        # Create first profile
        agent_profile_crud.create(
            db,
            obj_in=AgentProfileCreate(
                user_id=agent_user.user_id,
                agency_id=agency.agency_id
            ),
            created_by=str(uuid.uuid4())
        )
        
        # Try to create second profile for same user
        with pytest.raises(ValueError, match="already exists"):
            agent_profile_crud.create(
                db,
                obj_in=AgentProfileCreate(
                    user_id=agent_user.user_id,
                    agency_id=agency.agency_id
                ),
                created_by=str(uuid.uuid4())
            )
    
    def test_create_duplicate_license_raises_error(self, db: Session, agency):
        """Target line 225: Duplicate license validation"""
        agent1 = user_crud.create(
            db,
            obj_in=UserCreate(
                email="agent1.lic@test.com",
                password="Test123!",
                first_name="Agent1",
                last_name="Lic",
                user_role=UserRole.AGENT
            ),
            supabase_id=str(uuid.uuid4())
        )
        
        agent_profile_crud.create(
            db,
            obj_in=AgentProfileCreate(
                user_id=agent1.user_id,
                agency_id=agency.agency_id,
                license_number="DUPLICATE-LIC"
            ),
            created_by=str(uuid.uuid4())
        )
        
        agent2 = user_crud.create(
            db,
            obj_in=UserCreate(
                email="agent2.lic@test.com",
                password="Test123!",
                first_name="Agent2",
                last_name="Lic",
                user_role=UserRole.AGENT
            ),
            supabase_id=str(uuid.uuid4())
        )
        
        # Try to create with same license
        with pytest.raises(ValueError, match="license number.*already exists"):
            agent_profile_crud.create(
                db,
                obj_in=AgentProfileCreate(
                    user_id=agent2.user_id,
                    agency_id=agency.agency_id,
                    license_number="DUPLICATE-LIC"
                ),
                created_by=str(uuid.uuid4())
            )


class TestAgentProfileUpdate:
    """Target lines 278-336: update with business rules"""
    
    def test_update_basic_fields(self, db: Session, agency):
        """Basic field updates"""
        agent_user = user_crud.create(
            db,
            obj_in=UserCreate(
                email="update.agent@test.com",
                password="Test123!",
                first_name="Update",
                last_name="Agent",
                user_role=UserRole.AGENT
            ),
            supabase_id=str(uuid.uuid4())
        )
        
        profile = agent_profile_crud.create(
            db,
            obj_in=AgentProfileCreate(
                user_id=agent_user.user_id,
                agency_id=agency.agency_id
            ),
            created_by=str(uuid.uuid4())
        )
        
        updater_id = str(uuid.uuid4())
        
        updated = agent_profile_crud.update(
            db,
            db_obj=profile,
            obj_in=AgentProfileUpdate(
                specialization="Commercial Real Estate",
                years_experience=10
            ),
            updated_by=updater_id
        )
        
        assert updated.specialization == "Commercial Real Estate"
        assert updated.years_experience == 10
        assert str(updated.updated_by) == updater_id
    
    def test_update_license_uniqueness_check(self, db: Session, agency):
        """Target line 319: License uniqueness on update"""
        agent1 = user_crud.create(
            db,
            obj_in=UserCreate(
                email="agent1.update@test.com",
                password="Test123!",
                first_name="Agent1",
                last_name="Update",
                user_role=UserRole.AGENT
            ),
            supabase_id=str(uuid.uuid4())
        )
        
        profile1 = agent_profile_crud.create(
            db,
            obj_in=AgentProfileCreate(
                user_id=agent1.user_id,
                agency_id=agency.agency_id,
                license_number="LIC-001"
            ),
            created_by=str(uuid.uuid4())
        )
        
        agent2 = user_crud.create(
            db,
            obj_in=UserCreate(
                email="agent2.update@test.com",
                password="Test123!",
                first_name="Agent2",
                last_name="Update",
                user_role=UserRole.AGENT
            ),
            supabase_id=str(uuid.uuid4())
        )
        
        profile2 = agent_profile_crud.create(
            db,
            obj_in=AgentProfileCreate(
                user_id=agent2.user_id,
                agency_id=agency.agency_id,
                license_number="LIC-002"
            ),
            created_by=str(uuid.uuid4())
        )
        
        # Try to update profile2 to use profile1's license
        with pytest.raises(ValueError, match="license number.*already exists"):
            agent_profile_crud.update(
                db,
                db_obj=profile2,
                obj_in=AgentProfileUpdate(license_number="LIC-001"),
                updated_by=str(uuid.uuid4())
            )
    
    def test_update_protected_fields_ignored(self, db: Session, agency):
        """Target line 325: Protected fields removal"""
        agent_user = user_crud.create(
            db,
            obj_in=UserCreate(
                email="protected.agent@test.com",
                password="Test123!",
                first_name="Protected",
                last_name="Agent",
                user_role=UserRole.AGENT
            ),
            supabase_id=str(uuid.uuid4())
        )
        
        profile = agent_profile_crud.create(
            db,
            obj_in=AgentProfileCreate(
                user_id=agent_user.user_id,
                agency_id=agency.agency_id
            ),
            created_by=str(uuid.uuid4())
        )
        
        original_profile_id = profile.profile_id
        original_user_id = profile.user_id
        
        # Try to update protected fields
        updated = agent_profile_crud.update(
            db,
            db_obj=profile,
            obj_in={
                "profile_id": 99999,
                "user_id": 88888,
                "specialization": "Updated"
            },
            updated_by=str(uuid.uuid4())
        )
        
        assert updated.profile_id == original_profile_id
        assert updated.user_id == original_user_id
        assert updated.specialization == "Updated"


class TestAgentProfileSoftDelete:
    """Target lines 352-377: soft_delete with audit"""
    
    def test_soft_delete_sets_timestamp(self, db: Session, agency):
        """Verify deleted_at is set"""
        agent_user = user_crud.create(
            db,
            obj_in=UserCreate(
                email="delete.agent@test.com",
                password="Test123!",
                first_name="Delete",
                last_name="Agent",
                user_role=UserRole.AGENT
            ),
            supabase_id=str(uuid.uuid4())
        )
        
        profile = agent_profile_crud.create(
            db,
            obj_in=AgentProfileCreate(
                user_id=agent_user.user_id,
                agency_id=agency.agency_id
            ),
            created_by=str(uuid.uuid4())
        )
        
        deleter_id = str(uuid.uuid4())
        
        deleted = agent_profile_crud.soft_delete(
            db,
            profile_id=profile.profile_id,
            deleted_by_supabase_id=deleter_id
        )
        
        assert deleted.deleted_at is not None
        assert str(deleted.deleted_by) == deleter_id
    
    def test_soft_delete_nonexistent_raises_error(self, db: Session):
        """Target line 358: Non-existent profile error"""
        with pytest.raises(ValueError, match="not found"):
            agent_profile_crud.soft_delete(db, profile_id=999999)
    
    def test_soft_delete_already_deleted_raises_error(self, db: Session, agency):
        """Target line 362: Already deleted error"""
        agent_user = user_crud.create(
            db,
            obj_in=UserCreate(
                email="double.delete@test.com",
                password="Test123!",
                first_name="Double",
                last_name="Delete",
                user_role=UserRole.AGENT
            ),
            supabase_id=str(uuid.uuid4())
        )
        
        profile = agent_profile_crud.create(
            db,
            obj_in=AgentProfileCreate(
                user_id=agent_user.user_id,
                agency_id=agency.agency_id
            ),
            created_by=str(uuid.uuid4())
        )
        
        # First delete
        agent_profile_crud.soft_delete(db, profile_id=profile.profile_id)
        
        # Second delete should raise error
        with pytest.raises(ValueError, match="already deleted"):
            agent_profile_crud.soft_delete(db, profile_id=profile.profile_id)


class TestAgentProfileStatistics:
    """Target lines 387-418: get_stats aggregation"""
    
    def test_get_stats_basic(self, db: Session, agency):
        """Test statistics aggregation"""
        agent_user = user_crud.create(
            db,
            obj_in=UserCreate(
                email="stats.agent@test.com",
                password="Test123!",
                first_name="Stats",
                last_name="Agent",
                user_role=UserRole.AGENT
            ),
            supabase_id=str(uuid.uuid4())
        )
        
        profile = agent_profile_crud.create(
            db,
            obj_in=AgentProfileCreate(
                user_id=agent_user.user_id,
                agency_id=agency.agency_id
            ),
            created_by=str(uuid.uuid4())
        )
        
        stats = agent_profile_crud.get_stats(db, profile_id=profile.profile_id)
        
        assert "property_count" in stats
        assert "review_count" in stats
        assert "average_rating" in stats
        assert isinstance(stats["property_count"], int)
        assert isinstance(stats["review_count"], int)
        assert isinstance(stats["average_rating"], float)
    
    def test_get_stats_nonexistent_profile(self, db: Session):
        """Target line 394: Non-existent profile error"""
        with pytest.raises(ValueError, match="not found"):
            agent_profile_crud.get_stats(db, profile_id=999999)


# Fixtures needed for tests
@pytest.fixture
def agency(db: Session):
    """Create a test agency"""
    return agency_crud.create(
        db,
        obj_in=AgencyCreate(
            name="Test Agency",
            email="test@agency.com"
        ),
        created_by=str(uuid.uuid4())
    )