# app/crud/users.py
"""
User CRUD operations - 100% aligned to DB schema.
DB Table: users (PK: user_id)
Canonical Rules: No manual timestamps, no phantom fields, RLS-aware
"""

from typing import List, Optional, Dict, Any, Union, cast
import logging
from sqlalchemy.orm import Session
from sqlalchemy import select, or_, func
from datetime import datetime, timezone

from app.core.security import get_password_hash, verify_password
from app.models.users import User, UserRole
from app.schemas.users import UserCreate, UserUpdate

logger = logging.getLogger(__name__)


class UserCRUD:
    """CRUD operations for User model - DB-first canonical implementation"""
    
    
    # READ OPERATIONS
        
    def get(self, db: Session, user_id: int) -> Optional[User]:
        """Get a user by user_id (PK)"""
        # FIX: Exclude soft-deleted users in default read path.
        if user_id is None:
            return None
        stmt = select(User).where(
            User.user_id == user_id,
            User.deleted_at.is_(None)
        )
        return db.execute(stmt).scalar_one_or_none()

    def get_including_deleted(self, db: Session, user_id: int) -> Optional[User]:
        # FIX: Bypass soft-delete filter for restore operations only.
        if user_id is None:
            return None
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
        is_verified: Optional[bool] = None
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
        
        return list(db.execute(query).scalars().all())  # Normalize SQLAlchemy's sequence result to the declared list return type.
    
    def get_agents(
        self, 
        db: Session, 
        *, 
        skip: int = 0, 
        limit: int = 100,
        is_verified: Optional[bool] = None
    ) -> List[User]:
        """Get all agents with optional verification filter"""
        query = select(User).where(
            User.user_role == UserRole.AGENT,
            User.deleted_at.is_(None)  # FIX: Hide soft-deleted users.
        )
        
        if is_verified is not None:
            query = query.where(User.is_verified == is_verified)
        
        return list(  # Normalize SQLAlchemy's sequence result to the declared list return type.
            db.execute(
            query.offset(skip).limit(limit)
            ).scalars().all()
        )
    
    def count_by_agency(self, db: Session, *, agency_id: int) -> int:
        """Count active users belonging to an agency."""
        stmt = select(func.count(User.user_id)).where(
            User.agency_id == agency_id,
            User.deleted_at.is_(None)
        )
        return int(db.execute(stmt).scalar() or 0)  # Coerce nullable aggregate scalar into the concrete int this API returns.

    def count_active(self, db: Session) -> int:
        """Count active (non-deleted) users."""
        stmt = select(func.count(User.user_id)).where(User.deleted_at.is_(None))
        return int(db.execute(stmt).scalar() or 0)  # Coerce nullable aggregate scalar into the concrete int this API returns.

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
            User.deleted_at.is_(None),  # FIX: Hide soft-deleted users from search.
            or_(
                User.email.ilike(search_pattern),
                User.first_name.ilike(search_pattern),
                User.last_name.ilike(search_pattern)
            )
        )
        
        return list(  # Normalize SQLAlchemy's sequence result to the declared list return type.
            db.execute(
            query.offset(skip).limit(limit)
            ).scalars().all()
        )
    
    
    # CREATE OPERATIONS
        
    def create(
        self,
        db: Session,
        *,
        obj_in: UserCreate,
        supabase_id: str,
        created_by: Optional[str] = None
    ) -> User:
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
            profile_image_url=obj_in.profile_image_url,
            created_by=created_by
            # Timestamps handled by DB DEFAULT now()
            # created_at, updated_at auto-set by DB
        )
        
        db.add(db_obj)
        db.flush()  # FIX: Preserve test transaction isolation.
        db.refresh(db_obj)
        return db_obj
    
    
    # UPDATE OPERATIONS
        
    def update(
        self, 
        db: Session, 
        *, 
        db_obj: User, 
        obj_in: Union[UserUpdate, Dict[str, Any]],
        updated_by_supabase_id: Optional[str] = None,
        updated_by: Optional[str] = None
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
        updater = updated_by_supabase_id or updated_by
        if updater:
            db_obj.updated_by = updater
        # updated_at handled by DB trigger automatically
        
        db.add(db_obj)
        db.flush()  # FIX: Preserve test transaction isolation.
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
        
        cast(Any, db_obj).is_verified = is_verified  # Narrow ORM instance attribute assignment to its runtime bool field.
        cast(Any, db_obj).verification_code = None  # Narrow ORM instance attribute assignment to its runtime nullable field and clear code once verified.
        # updated_at handled by DB trigger automatically
        
        db.add(db_obj)
        db.flush()  # FIX: Preserve test transaction isolation.
        db.refresh(db_obj)
        return db_obj
    
    def update_last_login(self, db: Session, *, user_id: int) -> None:
        """Update last login timestamp (called during authentication)"""
        db_obj = self.get(db, user_id=user_id)
        if db_obj:
            cast(Any, db_obj).last_login = datetime.now(timezone.utc)  # Narrow ORM instance attribute assignment to its runtime datetime field.
            db.add(db_obj)
            db.flush()  # FIX: Preserve test transaction isolation.

    def activate(
        self,
        db: Session,
        *,
        user_id: int,
        updated_by: Optional[str] = None
    ) -> Optional[User]:
        """Restore a soft-deleted user (reactivate account)."""
        # FIX: Restore must fetch including deleted users.
        db_obj = self.get_including_deleted(db, user_id=user_id)
        if not db_obj:
            return None

        cast(Any, db_obj).deleted_at = None  # Narrow ORM instance attribute assignment to its runtime nullable datetime field.
        # FIX: Preserve deleted_by history on restore (immutable delete audit event).
        if updated_by:
            db_obj.updated_by = updated_by

        db.add(db_obj)
        db.flush()  # FIX: Preserve test transaction isolation.
        db.refresh(db_obj)
        return db_obj

    def deactivate(
        self,
        db: Session,
        *,
        user_id: int,
        updated_by: Optional[str] = None
    ) -> Optional[User]:
        """Soft-deactivate a user by setting deleted_at and audit fields."""
        db_obj = self.get(db, user_id=user_id)
        if not db_obj:
            return None

        cast(Any, db_obj).deleted_at = datetime.now(timezone.utc)  # Narrow ORM instance attribute assignment to its runtime datetime field.
        db_obj.deleted_by = updated_by  # FIX: Always assign deleted_by for soft-delete event.
        if updated_by:
            db_obj.updated_by = updated_by

        db.add(db_obj)
        db.flush()  # FIX: Preserve test transaction isolation.
        db.refresh(db_obj)
        return db_obj
    
    
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
    
        cast(Any, db_obj).deleted_at = datetime.now(timezone.utc)  # Narrow ORM instance attribute assignment to its runtime datetime field.
        db_obj.deleted_by = deleted_by_supabase_id  # FIX: Always assign to make intent explicit.
        if deleted_by_supabase_id:
            db_obj.updated_by = deleted_by_supabase_id
    
        db.add(db_obj)
        db.flush()  # FIX: Preserve test transaction isolation.
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
        db.flush()  # FIX: Preserve test transaction isolation.
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
            if not verify_password(password, cast(str, user.password_hash)):  # Narrow ORM descriptor-backed field to the runtime password hash string.
                return None
        except (ValueError, TypeError):
            # Handles bcrypt 72-byte limit or malformed hash
            # FIX: Use structured logger, avoid print and user-identifying details.
            logger.warning("Password verification error during authentication")
            return None
        
        # Best effort only: a bookkeeping write should not block login.
        try:
            self.update_last_login(db, user_id=cast(int, user.user_id))  # Narrow ORM descriptor-backed primary key to the runtime int value.
        except Exception:
            logger.warning(
                "Failed to update last_login during authentication",
                extra={"user_id": cast(int, user.user_id)},
                exc_info=True,
            )
        
        return user
    
    
    # AUTHORIZATION HELPERS
       
    def is_seeker(self, user: User) -> bool:
        """Check if user has seeker role"""
        return cast(UserRole, user.user_role) == UserRole.SEEKER  # Narrow ORM descriptor-backed enum field to the runtime user role value.
    
    def is_agent(self, user: User) -> bool:
        """Check if user has agent role"""
        return cast(UserRole, user.user_role) == UserRole.AGENT  # Narrow ORM descriptor-backed enum field to the runtime user role value.
    
    def is_admin(self, user: User) -> bool:
        """Check if user has admin privileges"""
        return cast(bool, user.is_admin) or cast(UserRole, user.user_role) == UserRole.ADMIN  # Narrow ORM descriptor-backed auth flags to runtime values before boolean evaluation.
    
    def is_agent_or_admin(self, user: User) -> bool:
        """Check if user has agent or admin role"""
        return self.is_agent(user) or self.is_admin(user)
    
    def is_verified(self, user: User) -> bool:
        """Check if user email is verified"""
        return cast(bool, user.is_verified)  # Narrow ORM descriptor-backed verification flag to the runtime bool value.
    
    def is_active(self, user: User) -> bool:
        """Check if user is active (not soft deleted)"""
        return cast(Optional[datetime], user.deleted_at) is None  # Narrow ORM descriptor-backed timestamp to the runtime optional datetime value.

    def get_realtors(
        self,
        db: Session,
        *,
        skip: int = 0,
        limit: int = 100
    ) -> List[User]:
        """Public realtor list: active agent accounts."""
        query = (
            select(User)
            .where(
                User.user_role == UserRole.AGENT,
                User.deleted_at.is_(None)
            )
            .offset(skip)
            .limit(limit)
        )
        return list(db.execute(query).scalars().all())  # Normalize SQLAlchemy's sequence result to the declared list return type.

    def remove(
        self,
        db: Session, 
        *, 
        user_id: int, 
        deleted_by_supabase_id: Optional[str] = None
    ) -> Optional[User]:
        """Alias for soft_delete (backward compatibility with tests)"""
        return self.soft_delete(
            db, 
            user_id=user_id, 
            deleted_by_supabase_id=deleted_by_supabase_id
        )

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
        return cast(int, current_user.user_id) == target_user_id  # Narrow ORM descriptor-backed primary key to the runtime int value.


# Singleton instance
user = UserCRUD()
