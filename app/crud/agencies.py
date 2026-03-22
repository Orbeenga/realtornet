# app/crud/agencies.py
"""
Agency CRUD operations - 100% aligned to DB schema.
DB Table: agencies (PK: agency_id)
Canonical Rules: Full audit trail (created_by, updated_by, deleted_by), soft delete
"""

from typing import List, Optional, Dict, Any, Union
from sqlalchemy.orm import Session
from sqlalchemy import select, or_, func, and_
from datetime import datetime, timezone
import logging

from app.models.agencies import Agency
from app.schemas.agencies import AgencyCreate, AgencyUpdate


logger = logging.getLogger(__name__)


class AgencyCRUD:
    """CRUD operations for Agency model - DB-first canonical implementation"""
    
    
    # READ OPERATIONS
        
    def get(self, db: Session, agency_id: int, *, include_deleted: bool = False) -> Optional[Agency]:
        """
        Get an agency by agency_id (PK).
        
        Args:
            include_deleted: If True, returns even soft-deleted agencies (admin use)
        """
        agency = db.get(Agency, agency_id)
        if not include_deleted and agency and agency.deleted_at is not None:
            return None
        return agency
    
    def get_by_email(self, db: Session, email: str) -> Optional[Agency]:
        """
        Get agency by email (unique field).
        Filters out soft-deleted agencies.
        """
        return db.execute(
            select(Agency).where(
                Agency.email == email.lower(),
                Agency.deleted_at.is_(None)
            )
        ).scalar_one_or_none()
    
    def get_by_name(self, db: Session, name: str) -> Optional[Agency]:
        """
        Get agency by exact name match (case-insensitive).
        Filters out soft-deleted agencies.
        """
        return db.execute(
            select(Agency).where(
                func.lower(Agency.name) == name.lower(),
                Agency.deleted_at.is_(None)
            )
        ).scalar_one_or_none()
    
    def get_multi(
        self, 
        db: Session, 
        *, 
        skip: int = 0, 
        limit: int = 100,
        is_verified: Optional[bool] = None
    ) -> List[Agency]:
        """
        Get multiple agencies with optional verification filter and pagination.
        Filters out soft-deleted agencies.
        """
        query = select(Agency).where(Agency.deleted_at.is_(None))
        
        # Apply verification filter
        if is_verified is not None:
            query = query.where(Agency.is_verified == is_verified)
        
        # Order by name alphabetically
        query = query.order_by(Agency.name.asc())
        
        # Pagination
        query = query.offset(skip).limit(limit)
        
        return db.execute(query).scalars().all()
    
    def search(
        self,
        db: Session,
        *,
        search_term: str,
        skip: int = 0,
        limit: int = 100
    ) -> List[Agency]:
        """
        Search agencies by name, email, or description.
        Filters out soft-deleted agencies.
        NULL-safe for optional description field.
        """
        search_pattern = f"%{search_term}%"
        
        query = select(Agency).where(
            Agency.deleted_at.is_(None),
            or_(
                Agency.name.ilike(search_pattern),
                Agency.email.ilike(search_pattern),
                and_(
                    Agency.description.isnot(None),
                    Agency.description.ilike(search_pattern)
                )
            )
        ).order_by(Agency.name).offset(skip).limit(limit)
        
        return db.execute(query).scalars().all()
    
    def count(self, db: Session, *, is_verified: Optional[bool] = None) -> int:
        """Count non-deleted agencies with optional verification filter"""
        query = select(func.count(Agency.agency_id)).where(
            Agency.deleted_at.is_(None)
        )
        
        if is_verified is not None:
            query = query.where(Agency.is_verified == is_verified)
        
        return db.execute(query).scalar()
    
    
    # CREATE OPERATIONS
        
    def create(
        self, 
        db: Session, 
        *, 
        obj_in: AgencyCreate,
        created_by: Optional[str] = None
    ) -> Agency:
        """
        Create a new agency.
        
        CRITICAL:
        - Email must be unique and lowercase
        - Name must be unique
        - created_by tracks who created (Supabase UUID)
        - is_verified defaults to False
        - Timestamps handled by DB DEFAULT now()
        """
        # Create agency object
        create_data = obj_in.dict(exclude_unset=True)
        
        db_obj = Agency(
            name=create_data["name"],
            email=create_data.get("email").lower() if create_data.get("email") else None,
            phone_number=create_data.get("phone_number"),
            address=create_data.get("address"),
            description=create_data.get("description"),
            logo_url=create_data.get("logo_url"),
            website_url=create_data.get("website_url"),
            is_verified=False,
            created_by=created_by
            # Timestamps handled by DB DEFAULT now()
        )
        
        db.add(db_obj)
        db.flush()
        db.refresh(db_obj)
        
        logger.info(
            "Agency created",
            extra={
                "agency_id": db_obj.agency_id,
                "name": db_obj.name,
                "created_by": created_by
            }
        )
        
        return db_obj
    
    
    # UPDATE OPERATIONS
        
    def update(
        self, 
        db: Session, 
        *, 
        db_obj: Agency, 
        obj_in: Union[AgencyUpdate, Dict[str, Any]],
        updated_by: str  # MANDATORY for audit trail
    ) -> Agency:
        """
        Update an agency.
        
        Rules:
        - Never update: agency_id, created_at, created_by
        - Email uniqueness check if being changed
        - updated_by REQUIRED (Supabase UUID)
        - updated_at handled by DB trigger
        """
        # Convert schema to dict
        if isinstance(obj_in, dict):
            update_data = obj_in
        else:
            update_data = obj_in.dict(exclude_unset=True)
        
        # Check for email uniqueness if email is being updated
        if "email" in update_data and update_data["email"]:
            new_email = update_data["email"].lower()
            if new_email != db_obj.email:
                existing = self.get_by_email(db, email=new_email)
                if existing and existing.agency_id != db_obj.agency_id:
                    raise ValueError(f"Agency with email '{new_email}' already exists")
            update_data["email"] = new_email
        
        # Check name uniqueness if being changed
        if "name" in update_data and update_data["name"]:
            if update_data["name"].lower() != db_obj.name.lower():
                existing = self.get_by_name(db, name=update_data["name"])
                if existing and existing.agency_id != db_obj.agency_id:
                    raise ValueError(f"Agency with name '{update_data['name']}' already exists")
        
        # Remove protected fields
        protected_fields = {"agency_id", "created_at", "created_by"}
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
            "Agency updated",
            extra={
                "agency_id": db_obj.agency_id,
                "updated_by": updated_by
            }
        )
        
        return db_obj
    
    
    # DELETE OPERATIONS
        
    def soft_delete(
        self, 
        db: Session, 
        *, 
        agency_id: int,
        deleted_by_supabase_id: str
    ) -> Optional[Agency]:
        """
        Soft delete an agency by setting deleted_at timestamp.
        Agency data preserved for audit trail, agent relationships intact.
        """
        db_obj = self.get(db, agency_id=agency_id)
        if not db_obj:
            return None
    
        db_obj.deleted_at = datetime.now(timezone.utc)
        db_obj.deleted_by = deleted_by_supabase_id
        db_obj.updated_by = deleted_by_supabase_id
        
        db.add(db_obj)
        db.flush()
        db.refresh(db_obj)
        
        logger.warning(
            "Agency soft deleted",
            extra={
                "agency_id": agency_id,
                "agency_name": db_obj.name,
                "deleted_by": deleted_by_supabase_id
            }
        )
        
        return db_obj
    
    
    # STATISTICS OPERATIONS
    
    def get_stats(self, db: Session, agency_id: int) -> Dict[str, Any]:
        """
        Get statistics for an agency.
        Returns agent count, property count, active listings, etc.
        """
        from app.models.agent_profiles import AgentProfile
        from app.models.properties import Property
        from app.models.users import User
        
        # Count agents
        agent_count = db.execute(
            select(func.count(User.user_id)).where(
                User.agency_id == agency_id,
                User.deleted_at.is_(None)
            )
        ).scalar()
        
        # Count properties (via agents)
        property_count = db.execute(
            select(func.count(Property.property_id.distinct())).join(
                AgentProfile,
                Property.user_id == AgentProfile.user_id
            ).where(
                AgentProfile.agency_id == agency_id,
                Property.deleted_at.is_(None)
            )
        ).scalar()
        
        return {
            "agent_count": agent_count,
            "property_count": property_count
        }


# Singleton instance
agency = AgencyCRUD()
