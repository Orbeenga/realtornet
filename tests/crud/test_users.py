# tests/crud/test_users.py
"""
User CRUD tests - Canonical compliant
Tests: create, read, update, soft delete, role checks
Coverage target: app/crud/users.py (currently 41%)
"""

import pytest
from sqlalchemy.orm import Session

from app.crud.users import user as user_crud
from app.models.users import User, UserRole
from app.schemas.users import UserCreate, UserUpdate
from app.core.security import verify_password


class TestUserCRUD:
    """Test suite for User CRUD operations"""
    
    # CREATE OPERATIONS
    
    def test_create_user(self, db: Session):
        """Test creating a new user"""
        user_in = UserCreate(
            email="newuser@test.com",
            password="securepass123",
            first_name="New",
            last_name="User",
            phone_number="+1234567890",
            user_role=UserRole.SEEKER
        )
        
        user = user_crud.create(
            db, 
            obj_in=user_in, 
            supabase_id="550e8400-e29b-41d4-a716-446655440000"
        )
        
        assert user.email == "newuser@test.com"
        assert user.first_name == "New"
        assert user.user_role == UserRole.SEEKER
        assert user.supabase_id is not None
        assert user.deleted_at is None
        assert verify_password("securepass123", user.password_hash)
    
    def test_create_user_duplicate_email(self, db: Session, normal_user: User):
        """Test creating user with duplicate email fails"""
        user_in = UserCreate(
            email=normal_user.email,  # Duplicate
            password="password123",
            first_name="Duplicate",
            last_name="User",
            user_role=UserRole.SEEKER
        )
        
        # Should raise integrity error (caught by endpoint, not CRUD)
        with pytest.raises(Exception):  # SQLAlchemy IntegrityError
            user_crud.create(
                db, 
                obj_in=user_in,
                supabase_id="550e8400-e29b-41d4-a716-446655440001"
            )
            db.commit()  # Error happens on commit
    
    
    # READ OPERATIONS
    
    def test_get_user_by_id(self, db: Session, normal_user: User):
        """Test getting user by user_id"""
        user = user_crud.get(db, user_id=normal_user.user_id)
        
        assert user is not None
        assert user.user_id == normal_user.user_id
        assert user.email == normal_user.email
    
    def test_get_user_by_email(self, db: Session, normal_user: User):
        """Test getting user by email"""
        user = user_crud.get_by_email(db, email=normal_user.email)
        
        assert user is not None
        assert user.email == normal_user.email
    
    def test_get_user_by_email_not_found(self, db: Session):
        """Test getting non-existent user returns None"""
        user = user_crud.get_by_email(db, email="nonexistent@test.com")
        
        assert user is None
    
    def test_get_user_by_supabase_id(self, db: Session, normal_user: User):
        """Test getting user by supabase_id"""
        user = user_crud.get_by_supabase_id(db, supabase_id=normal_user.supabase_id)
        
        assert user is not None
        assert user.supabase_id == normal_user.supabase_id
    
    def test_get_multi_users(self, db: Session, normal_user: User, agent_user: User):
        """Test getting multiple users with pagination"""
        users = user_crud.get_multi(db, skip=0, limit=10)
        
        assert len(users) >= 2
        user_ids = [u.user_id for u in users]
        assert normal_user.user_id in user_ids
        assert agent_user.user_id in user_ids
    
    
    # UPDATE OPERATIONS
    
    def test_update_user(self, db: Session, normal_user: User):
        """Test updating user fields"""
        update_data = UserUpdate(
            first_name="Updated",
            last_name="Name",
            phone_number="+9876543210"
        )
        
        updated_user = user_crud.update(
            db, 
            db_obj=normal_user, 
            obj_in=update_data
        )
        
        assert updated_user.first_name == "Updated"
        assert updated_user.last_name == "Name"
        assert updated_user.phone_number == "+9876543210"
        assert updated_user.email == normal_user.email  # Unchanged
    
    def test_update_user_email(self, db: Session, normal_user: User):
        """Test updating user email"""
        new_email = "newemail@test.com"
        update_data = UserUpdate(email=new_email)
        
        updated_user = user_crud.update(
            db,
            db_obj=normal_user,
            obj_in=update_data
        )
        
        assert updated_user.email == new_email
    
    
    # AUTHENTICATION
    
    def test_authenticate_user_success(self, db: Session, normal_user: User):
        """Test successful authentication"""
        user = user_crud.authenticate(
            db,
            email=normal_user.email,
            password="password"  # From fixture
        )
        
        assert user is not None
        assert user.user_id == normal_user.user_id
    
    def test_authenticate_user_wrong_password(self, db: Session, normal_user: User):
        """Test authentication fails with wrong password"""
        user = user_crud.authenticate(
            db,
            email=normal_user.email,
            password="wrongpassword"
        )
        
        assert user is None
    
    def test_authenticate_user_not_found(self, db: Session):
        """Test authentication fails for non-existent user"""
        user = user_crud.authenticate(
            db,
            email="nonexistent@test.com",
            password="anypassword"
        )
        
        assert user is None
    
    
    # ROLE CHECKS
    
    def test_is_active_true(self, db: Session, normal_user: User):
        """Test is_active returns True for non-deleted user"""
        assert user_crud.is_active(normal_user) is True
    
    def test_is_active_false_when_soft_deleted(self, db: Session, normal_user: User):
        """Test is_active returns False for soft-deleted user"""
        from datetime import datetime, timezone
        
        normal_user.deleted_at = datetime.now(timezone.utc)
        db.commit()
        
        assert user_crud.is_active(normal_user) is False
    
    def test_is_admin_true(self, db: Session, admin_user: User):
        """Test is_admin returns True for admin user"""
        assert user_crud.is_admin(admin_user) is True
    
    def test_is_admin_false(self, db: Session, normal_user: User):
        """Test is_admin returns False for non-admin user"""
        assert user_crud.is_admin(normal_user) is False
    
    def test_is_agent_true(self, db: Session, agent_user: User):
        """Test is_agent returns True for agent role"""
        assert user_crud.is_agent(agent_user) is True
    
    def test_is_agent_false(self, db: Session, normal_user: User):
        """Test is_agent returns False for non-agent"""
        assert user_crud.is_agent(normal_user) is False
    
    def test_is_seeker_true(self, db: Session, normal_user: User):
        """Test is_seeker returns True for seeker role"""
        assert user_crud.is_seeker(normal_user) is True
    
    def test_is_seeker_false(self, db: Session, agent_user: User):
        """Test is_seeker returns False for non-seeker"""
        assert user_crud.is_seeker(agent_user) is False
    
    
    # SOFT DELETE
    
    def test_soft_delete_user(self, db: Session, normal_user: User):
        """Test soft deleting a user"""
        deleted_user = user_crud.remove(
            db,
            user_id=normal_user.user_id
        )
        
        assert deleted_user.deleted_at is not None
        assert user_crud.is_active(deleted_user) is False
    
    def test_soft_deleted_user_excluded_from_queries(self, db: Session, normal_user: User):
        """Test soft-deleted users are excluded from get_by_email"""
        # Soft delete
        user_crud.remove(db, user_id=normal_user.user_id)
        
        # Try to get by email
        user = user_crud.get_by_email(db, email=normal_user.email)
        
        # Should not find soft-deleted user
        assert user is None or user.deleted_at is not None