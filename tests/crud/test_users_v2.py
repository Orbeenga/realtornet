# tests/crud/test_users_v2.py
"""
Surgical tests for app/crud/users.py - Targeting missing lines to push 69% → 85%+

Missing lines from coverage report:
- 56, 58, 74-79: get_multi with role/verification filters
- 92-102: get_agents with verification filter
- 161, 167-169: update with password and protected fields
- 183: update_verification_status edge case
- 199-210: soft_delete with audit trail
- 236, 240, 253-259: authenticate error handling
- 283-286, 310: Role check helper methods
- 339-341: can_modify_user authorization
"""

import pytest
from sqlalchemy.orm import Session
from app.crud.users import user as user_crud
from app.schemas.users import UserCreate, UserUpdate
from app.models.users import User, UserRole
from datetime import datetime, timezone
import uuid


class TestUserGetMultiFilters:
    """Target lines 56, 58, 74-79: get_multi with filters"""
    
    def test_get_multi_with_role_filter(self, db: Session):
        """Target lines 74-75: user_role filter"""
        # Create users with different roles
        agent = user_crud.create(
            db,
            obj_in=UserCreate(
                email="agent@test.com",
                password="Test123!",
                first_name="Agent",
                last_name="Smith",
                user_role=UserRole.AGENT
            ),
            supabase_id=str(uuid.uuid4())
        )
        
        seeker = user_crud.create(
            db,
            obj_in=UserCreate(
                email="seeker@test.com",
                password="Test123!",
                first_name="Seeker",
                last_name="Jones",
                user_role=UserRole.SEEKER
            ),
            supabase_id=str(uuid.uuid4())
        )
        
        # Filter by role
        agents = user_crud.get_multi(db, user_role=UserRole.AGENT)
        agent_ids = [u.user_id for u in agents]
        
        assert agent.user_id in agent_ids
        assert seeker.user_id not in agent_ids
    
    def test_get_multi_with_verification_filter(self, db: Session):
        """Target lines 76-77: is_verified filter"""
        # Create verified and unverified users
        verified_user = user_crud.create(
            db,
            obj_in=UserCreate(
                email="verified@test.com",
                password="Test123!",
                first_name="Verified",
                last_name="User",
                user_role=UserRole.SEEKER
            ),
            supabase_id=str(uuid.uuid4())
        )
        user_crud.update_verification_status(
            db,
            user_id=verified_user.user_id,
            is_verified=True
        )
        
        unverified_user = user_crud.create(
            db,
            obj_in=UserCreate(
                email="unverified@test.com",
                password="Test123!",
                first_name="Unverified",
                last_name="User",
                user_role=UserRole.SEEKER
            ),
            supabase_id=str(uuid.uuid4())
        )
        
        # Filter for verified only
        verified_users = user_crud.get_multi(db, is_verified=True)
        verified_ids = [u.user_id for u in verified_users]
        
        assert verified_user.user_id in verified_ids
        assert unverified_user.user_id not in verified_ids
        
        # Filter for unverified only
        unverified_users = user_crud.get_multi(db, is_verified=False)
        unverified_ids = [u.user_id for u in unverified_users]
        
        assert unverified_user.user_id in unverified_ids
        assert verified_user.user_id not in unverified_ids
    
    def test_get_multi_combined_filters(self, db: Session):
        """Test combining role and verification filters"""
        # Create verified agent
        verified_agent = user_crud.create(
            db,
            obj_in=UserCreate(
                email="verified.agent@test.com",
                password="Test123!",
                first_name="Verified",
                last_name="Agent",
                user_role=UserRole.AGENT
            ),
            supabase_id=str(uuid.uuid4())
        )
        user_crud.update_verification_status(
            db,
            user_id=verified_agent.user_id,
            is_verified=True
        )
        
        # Create unverified agent
        unverified_agent = user_crud.create(
            db,
            obj_in=UserCreate(
                email="unverified.agent@test.com",
                password="Test123!",
                first_name="Unverified",
                last_name="Agent",
                user_role=UserRole.AGENT
            ),
            supabase_id=str(uuid.uuid4())
        )
        
        # Filter for verified agents only
        verified_agents = user_crud.get_multi(
            db,
            user_role=UserRole.AGENT,
            is_verified=True
        )
        verified_agent_ids = [u.user_id for u in verified_agents]
        
        assert verified_agent.user_id in verified_agent_ids
        assert unverified_agent.user_id not in verified_agent_ids


class TestUserGetAgentsFilter:
    """Target lines 92-102: get_agents with verification filter"""
    
    def test_get_agents_all(self, db: Session):
        """Get all agents without filter"""
        agent1 = user_crud.create(
            db,
            obj_in=UserCreate(
                email="agent1@test.com",
                password="Test123!",
                first_name="Agent",
                last_name="One",
                user_role=UserRole.AGENT
            ),
            supabase_id=str(uuid.uuid4())
        )
        
        agents = user_crud.get_agents(db)
        agent_ids = [a.user_id for a in agents]
        
        assert agent1.user_id in agent_ids
    
    def test_get_agents_verified_only(self, db: Session):
        """Target line 99: is_verified filter in get_agents"""
        # Create verified agent
        verified_agent = user_crud.create(
            db,
            obj_in=UserCreate(
                email="verified.agent2@test.com",
                password="Test123!",
                first_name="Verified",
                last_name="Agent",
                user_role=UserRole.AGENT
            ),
            supabase_id=str(uuid.uuid4())
        )
        user_crud.update_verification_status(
            db,
            user_id=verified_agent.user_id,
            is_verified=True
        )
        
        # Create unverified agent
        unverified_agent = user_crud.create(
            db,
            obj_in=UserCreate(
                email="unverified.agent2@test.com",
                password="Test123!",
                first_name="Unverified",
                last_name="Agent",
                user_role=UserRole.AGENT
            ),
            supabase_id=str(uuid.uuid4())
        )
        
        # Get only verified agents
        verified_agents = user_crud.get_agents(db, is_verified=True)
        verified_ids = [a.user_id for a in verified_agents]
        
        assert verified_agent.user_id in verified_ids
        assert unverified_agent.user_id not in verified_ids


class TestUserUpdateEdgeCases:
    """Target lines 161, 167-169: update with password and protected fields"""
    
    def test_update_password(self, db: Session):
        """Target line 161: password update with hashing"""
        user = user_crud.create(
            db,
            obj_in=UserCreate(
                email="password.test@test.com",
                password="OldPassword123!",
                first_name="Test",
                last_name="User",
                user_role=UserRole.SEEKER
            ),
            supabase_id=str(uuid.uuid4())
        )
        
        old_hash = user.password_hash
        
        # Update password
        updated = user_crud.update(
            db,
            db_obj=user,
            obj_in=UserUpdate(password="NewPassword123!")
        )
        
        # Password hash should change
        assert updated.password_hash != old_hash
    
    def test_update_with_dict_input(self, db: Session):
        """Target line 153: dict input branch"""
        user = user_crud.create(
            db,
            obj_in=UserCreate(
                email="dict.test@test.com",
                password="Test123!",
                first_name="Dict",
                last_name="Test",
                user_role=UserRole.SEEKER
            ),
            supabase_id=str(uuid.uuid4())
        )
        
        # Update using dict
        updated = user_crud.update(
            db,
            db_obj=user,
            obj_in={"first_name": "Updated", "last_name": "Name"}
        )
        
        assert updated.first_name == "Updated"
        assert updated.last_name == "Name"
    
    def test_update_ignores_protected_fields(self, db: Session):
        """Target lines 167-169: protected fields removal"""
        user = user_crud.create(
            db,
            obj_in=UserCreate(
                email="protected.test@test.com",
                password="Test123!",
                first_name="Protected",
                last_name="Test",
                user_role=UserRole.SEEKER
            ),
            supabase_id=str(uuid.uuid4())
        )
        
        original_id = user.user_id
        original_supabase_id = user.supabase_id
        original_created_at = user.created_at
        
        # Try to update protected fields (should be ignored)
        updated = user_crud.update(
            db,
            db_obj=user,
            obj_in={
                "user_id": 99999,
                "supabase_id": "fake-uuid",
                "created_at": datetime(2020, 1, 1, tzinfo=timezone.utc),
                "first_name": "Updated"
            }
        )
        
        # Protected fields unchanged
        assert updated.user_id == original_id
        assert updated.supabase_id == original_supabase_id
        assert updated.created_at == original_created_at
        # Non-protected field changed
        assert updated.first_name == "Updated"


class TestUserVerificationStatus:
    """Target line 183: update_verification_status edge case"""
    
    def test_update_verification_nonexistent_user(self, db: Session):
        """Verify returns None for non-existent user"""
        result = user_crud.update_verification_status(
            db,
            user_id=999999,
            is_verified=True
        )
        
        assert result is None
    
    def test_update_verification_clears_code(self, db: Session):
        """Verify that verification_code is cleared when verified"""
        user = user_crud.create(
            db,
            obj_in=UserCreate(
                email="verify.test@test.com",
                password="Test123!",
                first_name="Verify",
                last_name="Test",
                user_role=UserRole.SEEKER
            ),
            supabase_id=str(uuid.uuid4())
        )
        
        # Set a verification code (simulating email verification flow)
        user.verification_code = "ABC123"
        db.add(user)
        db.commit()
        
        # Verify user
        verified = user_crud.update_verification_status(
            db,
            user_id=user.user_id,
            is_verified=True
        )
        
        assert verified.is_verified is True
        assert verified.verification_code is None


class TestUserSoftDelete:
    """Target lines 199-210: soft_delete with audit trail"""
    
    def test_soft_delete_sets_timestamp(self, db: Session):
        """Verify deleted_at is set"""
        user = user_crud.create(
            db,
            obj_in=UserCreate(
                email="delete.test@test.com",
                password="Test123!",
                first_name="Delete",
                last_name="Test",
                user_role=UserRole.SEEKER
            ),
            supabase_id=str(uuid.uuid4())
        )
        
        deleted = user_crud.soft_delete(db, user_id=user.user_id)
        
        assert deleted is not None
        assert deleted.deleted_at is not None
    
    def test_soft_delete_with_audit_trail(self, db: Session):
        """Target line 205: deleted_by_supabase_id tracking"""
        user = user_crud.create(
            db,
            obj_in=UserCreate(
                email="audit.delete@test.com",
                password="Test123!",
                first_name="Audit",
                last_name="Delete",
                user_role=UserRole.SEEKER
            ),
            supabase_id=str(uuid.uuid4())
        )
        
        admin_id = str(uuid.uuid4())
        
        deleted = user_crud.soft_delete(
            db,
            user_id=user.user_id,
            deleted_by_supabase_id=admin_id
        )
        
        assert deleted.deleted_at is not None
        assert str(deleted.deleted_by) == admin_id
        assert str(deleted.updated_by) == admin_id
    
    def test_soft_delete_nonexistent_user(self, db: Session):
        """Verify returns None for non-existent user"""
        result = user_crud.soft_delete(db, user_id=999999)
        assert result is None


class TestUserAuthentication:
    """Target lines 236, 240, 253-259: authenticate error handling"""
    
    def test_authenticate_nonexistent_email(self, db: Session):
        """Target line 236: user not found branch"""
        result = user_crud.authenticate(
            db,
            email="nonexistent@test.com",
            password="anything"
        )
        
        assert result is None
    
    def test_authenticate_wrong_password(self, db: Session):
        """Target line 240: password mismatch branch"""
        user_crud.create(
            db,
            obj_in=UserCreate(
                email="auth.test@test.com",
                password="CorrectPassword123!",
                first_name="Auth",
                last_name="Test",
                user_role=UserRole.SEEKER
            ),
            supabase_id=str(uuid.uuid4())
        )
        
        result = user_crud.authenticate(
            db,
            email="auth.test@test.com",
            password="WrongPassword123!"
        )
        
        assert result is None
    
    def test_authenticate_success_updates_last_login(self, db: Session):
        """Verify successful auth updates last_login"""
        user = user_crud.create(
            db,
            obj_in=UserCreate(
                email="login.test@test.com",
                password="Test123!",
                first_name="Login",
                last_name="Test",
                user_role=UserRole.SEEKER
            ),
            supabase_id=str(uuid.uuid4())
        )
        
        original_last_login = user.last_login
        
        authenticated = user_crud.authenticate(
            db,
            email="login.test@test.com",
            password="Test123!"
        )
        
        assert authenticated is not None
        assert authenticated.user_id == user.user_id
        # last_login should be updated
        db.refresh(user)
        assert user.last_login != original_last_login


class TestUserRoleChecks:
    """Target lines 283-286, 310: Role check helper methods"""
    
    def test_is_seeker(self, db: Session):
        """Target line 283: is_seeker check"""
        seeker = user_crud.create(
            db,
            obj_in=UserCreate(
                email="seeker.check@test.com",
                password="Test123!",
                first_name="Seeker",
                last_name="Check",
                user_role=UserRole.SEEKER
            ),
            supabase_id=str(uuid.uuid4())
        )
        
        assert user_crud.is_seeker(seeker) is True
        assert user_crud.is_agent(seeker) is False
    
    def test_is_agent(self, db: Session):
        """Target line 286: is_agent check"""
        agent = user_crud.create(
            db,
            obj_in=UserCreate(
                email="agent.check@test.com",
                password="Test123!",
                first_name="Agent",
                last_name="Check",
                user_role=UserRole.AGENT
            ),
            supabase_id=str(uuid.uuid4())
        )
        
        assert user_crud.is_agent(agent) is True
        assert user_crud.is_seeker(agent) is False
    
    def test_is_admin(self, db: Session):
        """Test admin role check"""
        user = user_crud.create(
            db,
            obj_in=UserCreate(
                email="admin.check@test.com",
                password="Test123!",
                first_name="Admin",
                last_name="Check",
                user_role=UserRole.SEEKER
            ),
            supabase_id=str(uuid.uuid4())
        )
        
        # Initially not admin
        assert user_crud.is_admin(user) is False
        
        # Make admin
        user.is_admin = True
        db.add(user)
        db.commit()
        
        assert user_crud.is_admin(user) is True
    
    def test_is_verified(self, db: Session):
        """Test verification check"""
        user = user_crud.create(
            db,
            obj_in=UserCreate(
                email="verified.check@test.com",
                password="Test123!",
                first_name="Verified",
                last_name="Check",
                user_role=UserRole.SEEKER
            ),
            supabase_id=str(uuid.uuid4())
        )
        
        assert user_crud.is_verified(user) is False
        
        user_crud.update_verification_status(
            db,
            user_id=user.user_id,
            is_verified=True
        )
        db.refresh(user)
        
        assert user_crud.is_verified(user) is True
    
    def test_is_active(self, db: Session):
        """Target line 310: is_active check"""
        user = user_crud.create(
            db,
            obj_in=UserCreate(
                email="active.check@test.com",
                password="Test123!",
                first_name="Active",
                last_name="Check",
                user_role=UserRole.SEEKER
            ),
            supabase_id=str(uuid.uuid4())
        )
        
        # Initially active
        assert user_crud.is_active(user) is True
        
        # Soft delete
        user_crud.soft_delete(db, user_id=user.user_id)
        db.refresh(user)
        
        assert user_crud.is_active(user) is False


class TestUserAuthorization:
    """Target lines 339-341: can_modify_user authorization"""
    
    def test_can_modify_user_self(self, db: Session):
        """User can modify themselves"""
        user = user_crud.create(
            db,
            obj_in=UserCreate(
                email="self.modify@test.com",
                password="Test123!",
                first_name="Self",
                last_name="Modify",
                user_role=UserRole.SEEKER
            ),
            supabase_id=str(uuid.uuid4())
        )
        
        assert user_crud.can_modify_user(user, user.user_id) is True
    
    def test_can_modify_user_other_non_admin(self, db: Session):
        """Non-admin cannot modify others"""
        user1 = user_crud.create(
            db,
            obj_in=UserCreate(
                email="user1@test.com",
                password="Test123!",
                first_name="User",
                last_name="One",
                user_role=UserRole.SEEKER
            ),
            supabase_id=str(uuid.uuid4())
        )
        
        user2 = user_crud.create(
            db,
            obj_in=UserCreate(
                email="user2@test.com",
                password="Test123!",
                first_name="User",
                last_name="Two",
                user_role=UserRole.SEEKER
            ),
            supabase_id=str(uuid.uuid4())
        )
        
        assert user_crud.can_modify_user(user1, user2.user_id) is False
    
    def test_can_modify_user_admin(self, db: Session):
        """Target line 338: Admin can modify anyone"""
        admin = user_crud.create(
            db,
            obj_in=UserCreate(
                email="admin@test.com",
                password="Test123!",
                first_name="Admin",
                last_name="User",
                user_role=UserRole.SEEKER
            ),
            supabase_id=str(uuid.uuid4())
        )
        admin.is_admin = True
        db.add(admin)
        db.commit()
        
        other_user = user_crud.create(
            db,
            obj_in=UserCreate(
                email="other@test.com",
                password="Test123!",
                first_name="Other",
                last_name="User",
                user_role=UserRole.SEEKER
            ),
            supabase_id=str(uuid.uuid4())
        )
        
        assert user_crud.can_modify_user(admin, other_user.user_id) is True


class TestUserRemoveAlias:
    """Test the remove() alias for backward compatibility"""
    
    def test_remove_calls_soft_delete(self, db: Session):
        """Verify remove is an alias for soft_delete"""
        user = user_crud.create(
            db,
            obj_in=UserCreate(
                email="remove.test@test.com",
                password="Test123!",
                first_name="Remove",
                last_name="Test",
                user_role=UserRole.SEEKER
            ),
            supabase_id=str(uuid.uuid4())
        )
        
        removed = user_crud.remove(db, user_id=user.user_id)
        
        assert removed is not None
        assert removed.deleted_at is not None
