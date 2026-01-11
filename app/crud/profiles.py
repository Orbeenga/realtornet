# app/crud/profiles.py
"""
Profile CRUD operations - 100% aligned to DB schema.
DB Table: profiles (PK: profile_id, FK: user_id)
Canonical Rules: No manual timestamps, RLS-aware, user_id from auth context
"""

from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select
from fastapi import HTTPException

from app.models.profiles import Profile, ProfileStatus
from app.schemas.profiles import ProfileCreate, ProfileUpdate


class CRUDProfile:
    """CRUD operations for Profile model - DB-first canonical implementation"""
    
    
    # READ OPERATIONS
        
    def get(self, db: Session, profile_id: int) -> Optional[Profile]:
        """Get a profile by profile_id (PK)"""
        return db.get(Profile, profile_id)
    
    def get_by_user_id(self, db: Session, user_id: int) -> Optional[Profile]:
        """
        Get profile by user_id (unique FK - one-to-one relationship).
        This is the primary lookup method for profiles.
        """
        return db.execute(
            select(Profile).where(Profile.user_id == user_id)
        ).scalar_one_or_none()
    
    def get_multi(
        self, 
        db: Session, 
        *, 
        skip: int = 0, 
        limit: int = 100,
        status: Optional[ProfileStatus] = None
    ) -> List[Profile]:
        """Get multiple profiles with optional status filter and pagination"""
        query = select(Profile)
        
        # Apply status filter
        if status:
            query = query.where(Profile.status == status)
        
        # Pagination
        query = query.offset(skip).limit(limit)
        
        return db.execute(query).scalars().all()
    
    def get_active_profiles(
        self,
        db: Session,
        *,
        skip: int = 0,
        limit: int = 100
    ) -> List[Profile]:
        """Get all active profiles (convenience method)"""
        return self.get_multi(
            db, 
            skip=skip, 
            limit=limit, 
            status=ProfileStatus.ACTIVE
        )
    
    def exists_for_user(self, db: Session, user_id: int) -> bool:
        """Check if profile exists for given user_id"""
        return self.get_by_user_id(db, user_id=user_id) is not None
    
    
    # CREATE OPERATIONS
        
    def create(
        self, 
        db: Session, 
        *, 
        obj_in: ProfileCreate, 
        user_id: int
    ) -> Profile:
        """
        Create a new profile.
        
        CRITICAL:
        - user_id MUST come from RLS/auth context (not request body)
        - One profile per user (enforced by unique constraint on user_id)
        - NO manual timestamp setting (DB handles via DEFAULT now())
        - Default status should be 'active' unless specified
        """
        # Check if profile already exists for this user
        existing_profile = self.get_by_user_id(db, user_id=user_id)
        if existing_profile:
            raise HTTPException(
                status_code=400,
                detail=f"Profile already exists for user_id={user_id}"
            )
        
        # Create profile with data from schema
        create_data = obj_in.dict(exclude_unset=True)
        
        db_obj = Profile(
            user_id=user_id,  # From auth context, NOT from request
            full_name=create_data.get("full_name"),
            phone_number=create_data.get("phone_number"),
            address=create_data.get("address"),
            profile_picture=create_data.get("profile_picture"),
            bio=create_data.get("bio"),
            status=create_data.get("status", ProfileStatus.ACTIVE)  # Default to active
            # Timestamps handled by DB DEFAULT now()
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
        db_obj: Profile, 
        obj_in: ProfileUpdate
    ) -> Profile:
        """
        Update a profile.
        
        Rules:
        - Never update: profile_id, user_id, created_at
        - updated_at auto-handled by DB trigger or manual set
        - Only update fields present in obj_in (exclude_unset=True)
        """
        update_data = obj_in.dict(exclude_unset=True)
        
        # Remove protected fields
        protected_fields = {"profile_id", "user_id", "created_at", "status"}
        for field in protected_fields:
            update_data.pop(field, None)
        
        # Apply updates
        for field, value in update_data.items():
            if hasattr(db_obj, field):
                setattr(db_obj, field, value)
        
        # Note: updated_at handled by DB trigger (if exists) or application logic
        # If no trigger, add: db_obj.updated_at = datetime.now(timezone.utc)
        
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj
    
    def update_status(
        self, 
        db: Session, 
        *, 
        profile_id: int, 
        status: ProfileStatus
    ) -> Optional[Profile]:
        """
        Update profile status (active/inactive/suspended).
        This is the preferred soft-delete method instead of hard delete.
        """
        db_obj = self.get(db, profile_id=profile_id)
        if not db_obj:
            return None
        
        db_obj.status = status
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj
    
    def deactivate(self, db: Session, *, profile_id: int) -> Optional[Profile]:
        """Soft delete by setting status to INACTIVE"""
        return self.update_status(
            db, 
            profile_id=profile_id, 
            status=ProfileStatus.INACTIVE
        )
    
    def reactivate(self, db: Session, *, profile_id: int) -> Optional[Profile]:
        """Reactivate an inactive profile"""
        return self.update_status(
            db, 
            profile_id=profile_id, 
            status=ProfileStatus.ACTIVE
        )
    
    
    # DELETE OPERATIONS

    def deactivate(self, db: Session, *, profile_id: int) -> Optional[Profile]:
        """Soft delete by setting status to INACTIVE"""
        db_obj = self.get(db, profile_id=profile_id)
        if not db_obj:
            raise HTTPException(
            status_code=404, 
            detail=f"Profile with id={profile_id} not found"
        )
    
        db_obj.status = ProfileStatus.INACTIVE
    # updated_at handled by trigger
    
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

     # Hard delete   
    def delete(self, db: Session, *, profile_id: int) -> Optional[Profile]:
        """
        Hard delete a profile (use with caution).
        
        RECOMMENDED: Use deactivate() instead for soft delete.
        Hard delete should only be used for GDPR/data removal requests.
        """
        db_obj = self.get(db, profile_id=profile_id)
        if not db_obj:
            raise HTTPException(
                status_code=404, 
                detail=f"Profile with id={profile_id} not found"
            )
        
        db.delete(db_obj)
        db.commit()
        return db_obj
    
    
    # AUTHORIZATION HELPERS
    
    
    def can_modify_profile(
        self, 
        current_user_id: int, 
        profile_user_id: int,
        is_admin: bool = False
    ) -> bool:
        """
        Check if current user can modify a profile.
        Rules: Users can modify their own profile, admins can modify any.
        """
        if is_admin:
            return True
        return current_user_id == profile_user_id
    
    def get_or_create_for_user(
        self, 
        db: Session, 
        *, 
        user_id: int,
        default_full_name: str
    ) -> Profile:
        """
        Get existing profile or create default one if doesn't exist.
        Useful for onboarding flows.
        """
        existing = self.get_by_user_id(db, user_id=user_id)
        if existing:
            return existing
        
        # Create minimal profile
        default_profile = ProfileCreate(
            full_name=default_full_name,
            status=ProfileStatus.ACTIVE
        )
        return self.create(db, obj_in=default_profile, user_id=user_id)


# Singleton instance
profile = CRUDProfile()