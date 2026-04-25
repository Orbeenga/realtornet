# app/crud/agent_profiles.py
"""
AgentProfile CRUD operations - 100% aligned to DB schema.
DB Table: agent_profiles (PK: profile_id, FKs: user_id, agency_id)
Canonical Rules: Full audit trail (created_by, updated_by, deleted_by), soft delete
"""

from typing import List, Optional, Dict, Any, Union, cast
from sqlalchemy.orm import Session
from sqlalchemy import select, or_, and_, func
from datetime import datetime, timezone
import logging

from app.models.agent_profiles import AgentProfile
from app.models.users import User, UserRole
from app.models.agencies import Agency
from app.schemas.agent_profiles import AgentProfileCreate, AgentProfileUpdate


logger = logging.getLogger(__name__)


class AgentProfileCRUD:
    """CRUD operations for AgentProfile model - DB-first canonical implementation"""
    
    
    # READ OPERATIONS
        
    def get(self, db: Session, profile_id: int) -> Optional[AgentProfile]:
        """
        Get an agent profile by profile_id (PK).
        Filters out soft-deleted profiles.
        """
        profile = db.get(AgentProfile, profile_id)
        if profile and profile.deleted_at is None:
            return profile
        return None
    
    def get_by_user_id(self, db: Session, user_id: int) -> Optional[AgentProfile]:
        """
        Get agent profile by user_id (1:1 relationship).
        Filters out soft-deleted profiles.
        """
        return db.execute(
            select(AgentProfile).where(
                AgentProfile.user_id == user_id,
                AgentProfile.deleted_at.is_(None)
            )
        ).scalar_one_or_none()
    
    def get_by_license(self, db: Session, license_number: str) -> Optional[AgentProfile]:
        """
        Get agent profile by license number (unique field).
        Filters out soft-deleted profiles.
        """
        return db.execute(
            select(AgentProfile).where(
                AgentProfile.license_number == license_number,
                AgentProfile.deleted_at.is_(None)
            )
        ).scalar_one_or_none()
    
    def get_multi(
        self, 
        db: Session, 
        *, 
        skip: int = 0, 
        limit: int = 100
    ) -> List[AgentProfile]:
        """
        Get multiple agent profiles with pagination.
        Filters out soft-deleted profiles.
        """
        query = select(AgentProfile).where(
            AgentProfile.deleted_at.is_(None)
        ).order_by(
            AgentProfile.profile_id.desc()
        ).offset(skip).limit(limit)
        
        return list(db.execute(query).scalars().all())  # Normalize SQLAlchemy's sequence result to the declared list return type.
    
    def get_by_agency(
        self,
        db: Session,
        *,
        agency_id: int,
        skip: int = 0,
        limit: int = 100
    ) -> List[AgentProfile]:
        """
        Get all agent profiles for a specific agency.
        Filters out soft-deleted profiles.
        """
        query = select(AgentProfile).where(
            AgentProfile.agency_id == agency_id,
            AgentProfile.deleted_at.is_(None)
        ).order_by(
            AgentProfile.profile_id.desc()
        ).offset(skip).limit(limit)
        
        return list(db.execute(query).scalars().all())  # Normalize SQLAlchemy's sequence result to the declared list return type.
    
    def search(
        self,
        db: Session,
        *,
        search_term: str,
        skip: int = 0,
        limit: int = 100
    ) -> List[AgentProfile]:
        """
        Search agent profiles by license, specialization, bio, or company name.
        Filters out soft-deleted profiles.
        NULL-safe for optional fields.
        """
        search_pattern = f"%{search_term}%"
        
        query = select(AgentProfile).where(
            AgentProfile.deleted_at.is_(None),
            or_(
                and_(
                    AgentProfile.license_number.isnot(None),
                    AgentProfile.license_number.ilike(search_pattern)
                ),
                and_(
                    AgentProfile.specialization.isnot(None),
                    AgentProfile.specialization.ilike(search_pattern)
                ),
                and_(
                    AgentProfile.bio.isnot(None),
                    AgentProfile.bio.ilike(search_pattern)
                ),
                and_(
                    AgentProfile.company_name.isnot(None),
                    AgentProfile.company_name.ilike(search_pattern)
                )
            )
        ).offset(skip).limit(limit)
        
        return list(db.execute(query).scalars().all())  # Normalize SQLAlchemy's sequence result to the declared list return type.
    
    def count_by_agency(self, db: Session, *, agency_id: int) -> int:
        """
        Count non-deleted agent profiles for an agency.
        Used for business rule validation.
        """
        return int(  # Coerce the nullable aggregate scalar into the concrete int this API returns.
            db.execute(
                select(func.count(AgentProfile.profile_id)).where(
                    AgentProfile.agency_id == agency_id,
                    AgentProfile.deleted_at.is_(None)
                )
            ).scalar() or 0
        )
    
    
    # VALIDATION HELPERS
        
    def _validate_user_is_agent(self, db: Session, user_id: int) -> User:
        """
        Validate that user exists and has agent role.
        Raises ValueError if validation fails.
        """
        user = db.execute(
            select(User).where(
                User.user_id == user_id,
                User.deleted_at.is_(None)
            )
        ).scalar_one_or_none()
        if not user:
            raise ValueError("User not found or is inactive")
        
        user_role = cast(UserRole, user.user_role)  # Cast the loaded ORM enum value to the concrete runtime role before comparing it.
        if user_role not in {UserRole.AGENT, UserRole.AGENCY_OWNER}:
            raise ValueError(f"User must have agent role (current role: {user_role})")
        
        return user
    
    def _validate_agency_exists(self, db: Session, agency_id: int) -> Agency:
        """
        Validate that agency exists and is not deleted.
        Raises ValueError if validation fails.
        """
        agency = db.get(Agency, agency_id)
        if not agency:
            raise ValueError("Agency not found")
        
        if agency.deleted_at is not None:
            raise ValueError("Agency is inactive")
        
        return agency
    
    
    # CREATE OPERATIONS
        
    def create(
        self, 
        db: Session, 
        *, 
        obj_in: AgentProfileCreate,
        created_by: Optional[str] = None
    ) -> AgentProfile:
        """
        Create a new agent profile.
        
        CRITICAL:
        - Validates user_id exists and has agent role
        - Validates agency_id exists (if provided)
        - One profile per user (1:1 constraint)
        - created_by tracks who created (Supabase UUID)
        - Timestamps handled by DB DEFAULT now()
        """
        # Validate user exists and is an agent
        self._validate_user_is_agent(db, user_id=obj_in.user_id)
        
        # Check if agent profile already exists for this user
        existing_profile = self.get_by_user_id(db, user_id=obj_in.user_id)
        if existing_profile:
            raise ValueError(f"Agent profile already exists for user_id={obj_in.user_id}")
        
        # Validate agency if provided
        if obj_in.agency_id is not None:
            self._validate_agency_exists(db, agency_id=obj_in.agency_id)
        
        # Validate license uniqueness if provided
        if obj_in.license_number:
            existing_license = self.get_by_license(db, license_number=obj_in.license_number)
            if existing_license:
                raise ValueError(f"Agent with license number '{obj_in.license_number}' already exists")
        
        # Create agent profile
        create_data = obj_in.dict(exclude_unset=True)
        
        db_obj = AgentProfile(
            user_id=create_data["user_id"],
            agency_id=create_data.get("agency_id"),
            license_number=create_data.get("license_number"),
            years_experience=create_data.get("years_experience"),
            specialization=create_data.get("specialization"),
            bio=create_data.get("bio"),
            website=create_data.get("website"),
            company_name=create_data.get("company_name"),
            created_by=created_by
            # Timestamps handled by DB DEFAULT now()
        )
        
        db.add(db_obj)
        db.flush()
        db.refresh(db_obj)
        
        logger.info(
            "Agent profile created",
            extra={
                "profile_id": db_obj.profile_id,
                "user_id": db_obj.user_id,
                "agency_id": db_obj.agency_id,
                "created_by": created_by
            }
        )
        
        return db_obj
    
    
    # UPDATE OPERATIONS
        
    def update(
        self, 
        db: Session, 
        *, 
        db_obj: AgentProfile, 
        obj_in: Union[AgentProfileUpdate, Dict[str, Any]],
        updated_by: str  # MANDATORY for audit trail
    ) -> AgentProfile:
        """
        Update an agent profile.
        
        Rules:
        - Never update: profile_id, user_id, created_at, created_by
        - Validate agency_id if being changed
        - Validate license uniqueness if being changed
        - Prevent agency change if agent has active properties (business rule)
        - updated_by REQUIRED (Supabase UUID)
        - updated_at handled by DB trigger
        """
        # Convert schema to dict
        if isinstance(obj_in, dict):
            update_data = obj_in
        else:
            update_data = obj_in.dict(exclude_unset=True)
        
        # Business rule: Prevent agency change if agent has active properties
        if "agency_id" in update_data and update_data["agency_id"] != db_obj.agency_id:
            from app.models.properties import Property
            property_count = db.execute(
                select(func.count(Property.property_id)).where(
                    Property.user_id == db_obj.user_id,
                    Property.deleted_at.is_(None)
                )
            ).scalar()
            
            if (property_count or 0) > 0:  # Normalize the nullable aggregate into a concrete int before comparing it.
                raise ValueError(
                    "Cannot change agency while agent has active properties. "
                    "Transfer or remove properties first."
                )
        
        # Validate agency if being updated
        if "agency_id" in update_data and update_data["agency_id"]:
            self._validate_agency_exists(db, agency_id=update_data["agency_id"])
        
        # Validate license uniqueness if being changed
        if "license_number" in update_data and update_data["license_number"]:
            if update_data["license_number"] != db_obj.license_number:
                existing = self.get_by_license(db, license_number=update_data["license_number"])
                existing_profile_id = (  # Cast the loaded ORM ID to a concrete int so pyright doesn't keep SQLAlchemy's descriptor type in the comparison.
                    cast(int, existing.profile_id) if existing is not None else None
                )
                current_profile_id = cast(int, db_obj.profile_id)  # Cast the current ORM ID to a concrete int before comparing it with another loaded record.
                if existing_profile_id is not None and existing_profile_id != current_profile_id:
                    raise ValueError(f"Agent with license number '{update_data['license_number']}' already exists")
        
        # Remove protected fields
        protected_fields = {"profile_id", "user_id", "created_at", "created_by"}
        for field in protected_fields:
            update_data.pop(field, None)
        
        # Apply updates
        for field, value in update_data.items():
            if hasattr(db_obj, field):
                setattr(db_obj, field, value)
        
        # Audit field - REQUIRED
        db_obj.updated_by = updated_by
        # updated_at handled by DB trigger automatically
        
        db.add(db_obj)
        db.flush()
        db.refresh(db_obj)
        
        logger.info(
            "Agent profile updated",
            extra={
                "profile_id": db_obj.profile_id,
                "updated_by": updated_by
            }
        )
        
        return db_obj
    
    
    # DELETE OPERATIONS
        
    def soft_delete(
        self, 
        db: Session, 
        *, 
        profile_id: int,
        deleted_by_supabase_id: Optional[str] = None
    ) -> AgentProfile:
        """
        Soft delete an agent profile by setting deleted_at timestamp.
        Profile data preserved for commission history, review attribution.
        Bypasses default CRUD filters to properly handle 'already deleted' states.
        """
        # Bypass self.get() to see deleted records
        db_obj = db.get(AgentProfile, profile_id)  # Direct lookup, no filters
        
        if not db_obj:
            raise ValueError(f"Agent profile with id={profile_id} not found")
        
        if db_obj.deleted_at is not None:
            raise ValueError(f"Agent profile with id={profile_id} is already deleted")

        cast(Any, db_obj).deleted_at = datetime.now(timezone.utc)  # Cast through Any so pyright accepts assigning the runtime timestamp to the ORM-backed soft-delete field.
        db_obj.deleted_by = deleted_by_supabase_id

        db.add(db_obj)
        db.flush()
        db.refresh(db_obj)
        
        logger.warning(
            "Agent profile soft deleted",
            extra={
                "profile_id": profile_id,
                "user_id": db_obj.user_id,
                "agency_id": db_obj.agency_id,
                "deleted_by": deleted_by_supabase_id
            }
        )
        
        return db_obj
    
    
    # STATISTICS OPERATIONS
    
    def get_stats(self, db: Session, profile_id: int) -> Dict[str, Any]:
        """
        Get statistics for an agent profile.
        Returns total properties, active listings, avg rating, total reviews, etc.
        """
        from app.models.properties import Property
        from app.models.reviews import Review
        
        profile = self.get(db, profile_id=profile_id)
        if not profile:
            raise ValueError(f"Agent profile with id={profile_id} not found")
        
        # Count properties
        property_count = db.execute(
            select(func.count(Property.property_id)).where(
                Property.user_id == profile.user_id,
                Property.deleted_at.is_(None)
            )
        ).scalar()
        
        # Count reviews (if reviews table has agent_id field)
        review_count = db.execute(
            select(func.count(Review.review_id)).where(
                Review.agent_id == profile.user_id,
                Review.deleted_at.is_(None)
            )
        ).scalar()
        
        # Average rating (if reviews have rating field)
        avg_rating = db.execute(
            select(func.avg(Review.rating)).where(
                Review.agent_id == profile.user_id,
                Review.deleted_at.is_(None)
            )
        ).scalar() or 0.0
        
        return {
            "property_count": property_count,
            "review_count": review_count,
            "average_rating": round(float(avg_rating), 2)
        }


# Singleton instance
agent_profile = AgentProfileCRUD()
