# app/crud/users.py
"""
User CRUD operations - 100% aligned to DB schema.
DB Table: users (PK: user_id)
Canonical Rules: No manual timestamps, no phantom fields, RLS-aware
"""

from typing import List, Optional, Dict, Any, Union
from sqlalchemy.orm import Session
from sqlalchemy import select, or_
from datetime import datetime, timezone

from app.core.security import get_password_hash, verify_password
from app.models.users import User, UserRole
from app.schemas.users import UserCreate, UserUpdate


class UserCRUD:
    """CRUD operations for User model - DB-first canonical implementation"""
    
    
    # READ OPERATIONS
        
    def get(self, db: Session, user_id: int) -> Optional[User]:
        """Get a user by user_id (PK)"""
        return db.get(User, user_id)
    
    def get_by_email(self, db: Session, email: str) -> Optional[User]:
        """Get a user by email (unique field)"""
        return db.execute(
            select(User).where(User.email == email.lower())
        ).scalar_one_or_none()
    
    def get_by_supabase_id(self, db: Session, supabase_id: str) -> Optional[User]:
        """Get user by Supabase auth UUID (RLS context)"""
        return db.execute(
            select(User).where(User.supabase_id == supabase_id)
        ).scalar_one_or_none()
    
    def get_multi(
        self, 
        db: Session, 
        *, 
        skip: int = 0, 
        limit: int = 100,
        user_role: Optional[UserRole] = None,
        is_verified: Optional[bool] = None,
        query = select(User)
    ) -> List[User]:
        """Get multiple users with optional filters and pagination"""
        query = select(User)
        
        # Apply filters
        query = query.where(User.deleted_at.is_(None))
        if user_role:
            query = query.where(User.user_role == user_role)
        if is_verified is not None:
            query = query.where(User.is_verified == is_verified)
        
        # Pagination
        query = query.offset(skip).limit(limit)
        
        return db.execute(query).scalars().all()
    
    def get_agents(
        self, 
        db: Session, 
        *, 
        skip: int = 0, 
        limit: int = 100,
        is_verified: Optional[bool] = None
    ) -> List[User]:
        """Get all agents with optional verification filter"""
        query = select(User).where(User.user_role == UserRole.AGENT)
        
        if is_verified is not None:
            query = query.where(User.is_verified == is_verified)
        
        return db.execute(
            query.offset(skip).limit(limit)
        ).scalars().all()
    
    def search(
        self,
        db: Session,
        *,
        search_term: str,
        skip: int = 0,
        limit: int = 100
    ) -> List[User]:
        """Search users by email, first_name, or last_name"""
        search_pattern = f"%{search_term.lower()}%"
        
        query = select(User).where(
            or_(
                User.email.ilike(search_pattern),
                User.first_name.ilike(search_pattern),
                User.last_name.ilike(search_pattern)
            )
        )
        
        return db.execute(
            query.offset(skip).limit(limit)
        ).scalars().all()
    
    
    # CREATE OPERATIONS
        
    def create(self, db: Session, *, obj_in: UserCreate, supabase_id: str) -> User:
        """
        Create a new user.
        
        CRITICAL:
        - supabase_id from auth context (not from request body)
        - Password hashed before storage
        - NO manual timestamp setting (DB handles via DEFAULT now())
        - NO phantom fields (is_active, bio, address, etc.)
        """
        db_obj = User(
            supabase_id=supabase_id,
            email=obj_in.email.lower(),  # Enforce lowercase
            password_hash=get_password_hash(obj_in.password),
            first_name=obj_in.first_name,
            last_name=obj_in.last_name,
            phone_number=obj_in.phone_number.strip() if obj_in.phone_number else None,
            user_role=obj_in.user_role,
            is_verified=False,  # Always start unverified
            is_admin=False,  # Never allow admin creation via API
            profile_image_url=obj_in.profile_image_url
            # Timestamps handled by DB DEFAULT now()
            # created_at, updated_at auto-set by DB
        )
        
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj
    
    
    # UPDATE OPERATIONS
        
    def update(
        self, 
        db: Session, 
        *, 
        db_obj: User, 
        obj_in: Union[UserUpdate, Dict[str, Any]],
        updated_by_supabase_id: Optional[str] = None
    ) -> User:
        """
        Update a user.
        
        Rules:
        - Never update: user_id, supabase_id, created_at
        - Password updates handled separately via hash
        - updated_at auto-handled by DB trigger or manual set here
        - updated_by tracks who made the change (RLS context)
        """
        # Convert schema to dict
        if isinstance(obj_in, dict):
            update_data = obj_in
        else:
            update_data = obj_in.dict(exclude_unset=True)
        
        # Handle password separately
        if "password" in update_data and update_data["password"]:
            hashed_password = get_password_hash(update_data["password"])
            del update_data["password"]
            update_data["password_hash"] = hashed_password
        
        # Remove protected fields that should never be updated
        protected_fields = {"user_id", "supabase_id", "created_at"}
        for field in protected_fields:
            update_data.pop(field, None)
        
        # Apply updates
        for field, value in update_data.items():
            if hasattr(db_obj, field):
                setattr(db_obj, field, value)
        
        # Set audit fields
        if updated_by_supabase_id:
            db_obj.updated_by = updated_by_supabase_id
        # updated_at handled by DB trigger automatically
        
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj
    
    def update_verification_status(
        self, 
        db: Session, 
        *, 
        user_id: int, 
        is_verified: bool
    ) -> Optional[User]:
        """Update user verification status (admin operation)"""
        db_obj = self.get(db, user_id=user_id)
        if not db_obj:
            return None
        
        db_obj.is_verified = is_verified
        db_obj.verification_code = None  # Clear code once verified
        # updated_at handled by DB trigger automatically
        
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj
    
    def update_last_login(self, db: Session, *, user_id: int) -> None:
        """Update last login timestamp (called during authentication)"""
        db_obj = self.get(db, user_id=user_id)
        if db_obj:
            db_obj.last_login = datetime.now(timezone.utc)
            db.add(db_obj)
            db.commit()
    
    
    # DELETE OPERATIONS

    def soft_delete(
        self, 
        db: Session, 
        *, 
        user_id: int,
        deleted_by_supabase_id: Optional[str] = None
    ) -> Optional[User]:
        """
        Soft delete a user by setting deleted_at timestamp.
        User data preserved for audit trail, FK relationships intact.
        """
        db_obj = self.get(db, user_id=user_id)
        if not db_obj:
            return None
    
        db_obj.deleted_at = datetime.now(timezone.utc)
        if deleted_by_supabase_id:
            db_obj.updated_by = deleted_by_supabase_id
    
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    # Hard delete
    def hard_delete_admin_only(self, db: Session, *, user_id: int) -> Optional[User]:
        """
        DANGEROUS: Permanently delete user (admin only, use soft_delete instead).
        Only for GDPR/legal compliance requests.
        """
        db_obj = self.get(db, user_id=user_id)
        if not db_obj:
            return None
        
        db.delete(db_obj)
        db.commit()
        return db_obj
    
    
    # AUTHENTICATION OPERATIONS
        
    def authenticate(
        self, 
        db: Session, 
        *, 
        email: str, 
        password: str
    ) -> Optional[User]:
        """
        Authenticate a user by email and password.
        Returns User object if successful, None if failed.
        """
        user = self.get_by_email(db, email=email)
        if not user:
            return None
        
        try:
            # ADDED: Try-catch for bcrypt edge cases (72-byte limit)
            if not verify_password(password, user.password_hash):
                return None
        except (ValueError, TypeError):
            # Handles bcrypt 72-byte limit or malformed hash
            print(f"Password verification error")
            return None
        
        # Update last login timestamp
        self.update_last_login(db, user_id=user.user_id)
        
        return user
    
    
    # AUTHORIZATION HELPERS
       
    def is_agent(self, user: User) -> bool:
        """Check if user has agent role"""
        return user.user_role == UserRole.AGENT
    
    def is_admin(self, user: User) -> bool:
        """Check if user has admin privileges"""
        return user.is_admin or user.user_role == UserRole.ADMIN
    
    def is_verified(self, user: User) -> bool:
        """Check if user email is verified"""
        return user.is_verified
    
    def is_active(self, user: User) -> bool:
        """Check if user is active (not soft deleted)"""
        return user.deleted_at is None

    def can_modify_user(
        self, 
        current_user: User, 
        target_user_id: int
    ) -> bool:
        """
        Check if current_user can modify target_user.
        Rules: Users can modify themselves, admins can modify anyone.
        """
        if self.is_admin(current_user):
            return True
        return current_user.user_id == target_user_id


# Singleton instance
user = UserCRUD()