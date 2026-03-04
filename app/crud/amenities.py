# app/crud/amenities.py
"""
Amenity CRUD operations - 100% aligned to DB schema.
DB Table: amenities (PK: amenity_id)
Canonical Rules: Lookup table pattern, no soft delete needed
"""

from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from fastapi import HTTPException
import logging

from app.models.amenities import Amenity
from app.models.property_amenities import property_amenities  # ✅ Table object, not class
from app.schemas.amenities import AmenityCreate, AmenityUpdate
from app.models.properties import Property


logger = logging.getLogger(__name__)


class AmenityCRUD:
    """CRUD operations for Amenity model - DB-first canonical implementation"""
    
    
    # READ OPERATIONS
        
    def get(self, db: Session, amenity_id: int) -> Optional[Amenity]:
        """Get an amenity by amenity_id (PK)"""
        return db.get(Amenity, amenity_id)
    
    def get_by_name(self, db: Session, name: str) -> Optional[Amenity]:
        """
        Get amenity by name (unique field).
        Case-insensitive lookup for better UX.
        """
        return db.execute(
            select(Amenity).where(
                func.lower(Amenity.name) == name.lower()
            )
        ).scalar_one_or_none()
    
    def get_multi(
        self, 
        db: Session, 
        *, 
        skip: int = 0, 
        limit: int = 100
    ) -> List[Amenity]:
        """Get multiple amenities with pagination and deterministic ordering"""
        query = select(Amenity).order_by(Amenity.name.asc())
        query = query.offset(skip).limit(limit)
        return db.execute(query).scalars().all()
    
    def get_by_category(
        self,
        db: Session,
        *,
        category: str,
        skip: int = 0,
        limit: int = 100
    ) -> List[Amenity]:
        """Get amenities filtered by category"""
        query = select(Amenity).where(
            Amenity.category == category
        ).order_by(Amenity.name.asc()).offset(skip).limit(limit)
        
        return db.execute(query).scalars().all()
    
    def get_categories(self, db: Session) -> List[str]:
        """Get all unique amenity categories"""
        result = db.execute(
            select(Amenity.category).distinct().where(
                Amenity.category.isnot(None)
            ).order_by(Amenity.category.asc())
        ).scalars().all()
        
        return list(result)
    
    def get_all_for_select(self, db: Session, limit: int = 500) -> List[Amenity]:
        """
        Get all amenities for form select/checkbox options.
        Hard-capped at 500 for safety - lookup tables should stay small.
        """
        return db.execute(
            select(Amenity).order_by(Amenity.name.asc()).limit(limit)
        ).scalars().all()
    
    def search(
        self,
        db: Session,
        *,
        search_term: str,
        skip: int = 0,
        limit: int = 100
    ) -> List[Amenity]:
        """Search amenities by name or description"""
        search_pattern = f"%{search_term}%"
        
        query = select(Amenity).where(
            Amenity.name.ilike(search_pattern) |
            Amenity.description.ilike(search_pattern)
        ).order_by(Amenity.name.asc())
        
        return db.execute(
            query.offset(skip).limit(limit)
        ).scalars().all()
    
    def count(self, db: Session) -> int:
        """Count total amenities"""
        return db.execute(
            select(func.count(Amenity.amenity_id))
        ).scalar()
    
    def exists(self, db: Session, *, amenity_id: int) -> bool:
        """Check if amenity exists (optimized)"""
        return db.execute(
            select(1).where(Amenity.amenity_id == amenity_id)
        ).scalar() is not None
    
    
    # CREATE OPERATIONS
        
    def create(
        self, 
        db: Session, 
        *, 
        obj_in: AmenityCreate
    ) -> Amenity:
        """
        Create a new amenity.
        Name must be unique (enforced by DB constraint).
        NO manual timestamp setting (DB handles via DEFAULT now()).
        """
        existing = self.get_by_name(db, name=obj_in.name)
        if existing:
            raise ValueError(f"Amenity with name '{obj_in.name}' already exists")
        
        create_data = obj_in.dict(exclude_unset=True)
        
        db_obj = Amenity(
            name=create_data["name"],
            description=create_data.get("description"),
            category=create_data.get("category")
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
        db_obj: Amenity, 
        obj_in: AmenityUpdate
    ) -> Amenity:
        """
        Update an amenity.
        Never update: amenity_id, created_at.
        updated_at handled by DB trigger.
        """
        update_data = obj_in.dict(exclude_unset=True)
        
        if "name" in update_data and update_data["name"]:
            new_name = update_data["name"]
            if new_name.lower() != db_obj.name.lower():
                existing = self.get_by_name(db, name=new_name)
                if existing and existing.amenity_id != db_obj.amenity_id:
                    raise ValueError(f"Amenity with name '{new_name}' already exists")
        
        protected_fields = {"amenity_id", "created_at"}
        for field in protected_fields:
            update_data.pop(field, None)
        
        for field, value in update_data.items():
            if hasattr(db_obj, field):
                setattr(db_obj, field, value)
        
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj
    
    
    # DELETE OPERATIONS
        
    def delete(self, db: Session, *, amenity_id: int) -> Optional[Amenity]:
        """
        Hard delete an amenity (admin only).
        WARNING: Will cascade to property_amenities junction table (ON DELETE CASCADE).
        """
        db_obj = self.get(db, amenity_id=amenity_id)
        if not db_obj:
            raise ValueError(f"Amenity with id={amenity_id} not found")
        
        # Check usage count via junction table (informational)
        usage_count = db.execute(
            select(func.count()).select_from(property_amenities).where(
                property_amenities.c.amenity_id == amenity_id
            )
        ).scalar()
        
        if usage_count > 0:
            logger.warning(
                f"Deleting amenity used by {usage_count} properties (will cascade)",
                extra={"amenity_id": amenity_id, "usage_count": usage_count}
            )
        
        db.delete(db_obj)
        db.commit()
        return db_obj
    
    def remove(self, db: Session, *, amenity_id: int) -> Optional[Amenity]:
        """Alias for delete() to match endpoint naming convention."""
        return self.delete(db, amenity_id=amenity_id)
    
    
    # RELATIONSHIP OPERATIONS
        
    def get_properties_with_amenity(
        self,
        db: Session,
        *,
        amenity_id: int,
        skip: int = 0,
        limit: int = 100
    ) -> List:
        """Get all properties that have this amenity"""
        
        query = select(Property).join(
            property_amenities,
            Property.property_id == property_amenities.c.property_id
        ).where(
            property_amenities.c.amenity_id == amenity_id
        ).offset(skip).limit(limit)
        
        return db.execute(query).scalars().all()
    
    def count_properties_with_amenity(
        self,
        db: Session,
        *,
        amenity_id: int
    ) -> int:
        """Count how many properties have this amenity"""
        return db.execute(
            select(func.count()).select_from(property_amenities).where(
                property_amenities.c.amenity_id == amenity_id
            )
        ).scalar()
    
    
    # STATISTICS AND ANALYTICS
    
    def get_popular(
        self,
        db: Session,
        *,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get most popular amenities based on usage in properties.
        Returns list of dicts with amenity info and usage count.
        """
        query = select(
            Amenity.amenity_id,
            Amenity.name,
            Amenity.category,
            func.count(property_amenities.c.property_id).label('usage_count')
        ).join(
            property_amenities,
            Amenity.amenity_id == property_amenities.c.amenity_id
        ).group_by(
            Amenity.amenity_id
        ).order_by(
            func.count(property_amenities.c.property_id).desc()
        ).limit(limit)
        
        results = db.execute(query).all()
        
        return [
            {
                "amenity_id": row[0],
                "name": row[1],
                "category": row[2],
                "usage_count": row[3]
            }
            for row in results
        ]
    
    
    # UTILITY METHODS
        
    def get_or_create(
        self,
        db: Session,
        *,
        name: str,
        description: Optional[str] = None,
        category: Optional[str] = None
    ) -> Amenity:
        """Get existing amenity or create if doesn't exist. Useful for seeding."""
        existing = self.get_by_name(db, name=name)
        if existing:
            return existing
        
        amenity_data = AmenityCreate(
            name=name,
            description=description,
            category=category
        )
        return self.create(db, obj_in=amenity_data)
    
    def bulk_create(
        self,
        db: Session,
        *,
        amenities_data: List[Dict[str, str]]
    ) -> List[Amenity]:
        """
        Bulk create amenities (for seeding).
        Skips duplicates, returns all created/existing amenities.
        """
        created_amenities = []
        
        for amenity_dict in amenities_data:
            try:
                existing = self.get_by_name(db, name=amenity_dict["name"])
                if not existing:
                    amenity_obj = AmenityCreate(**amenity_dict)
                    created = self.create(db, obj_in=amenity_obj)
                    created_amenities.append(created)
                else:
                    created_amenities.append(existing)
            except HTTPException:
                continue
        
        return created_amenities


# Singleton instance
amenity = AmenityCRUD()