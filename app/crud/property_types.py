# app/crud/property_types.py
"""
PropertyType CRUD operations - 100% aligned to DB schema.
DB Table: property_types (PK: property_type_id)
Canonical Rules: Lookup table pattern, no soft delete needed
"""

from typing import List, Optional, Dict, Any, cast
from sqlalchemy.orm import Session
from sqlalchemy import select, func, or_
import logging

from app.models.property_types import PropertyType
from app.schemas.property_types import PropertyTypeCreate, PropertyTypeUpdate


logger = logging.getLogger(__name__)


class PropertyTypeCRUD:
    """CRUD operations for PropertyType model - DB-first canonical implementation"""
    
    
    # READ OPERATIONS
        
    def get(self, db: Session, property_type_id: int) -> Optional[PropertyType]:
        """Get a property type by property_type_id (PK)"""
        return db.get(PropertyType, property_type_id)
    
    def get_by_name(self, db: Session, name: str) -> Optional[PropertyType]:
        """
        Get property type by name (unique field).
        Case-insensitive lookup for better UX.
        """
        return db.execute(
            select(PropertyType).where(
                func.lower(PropertyType.name) == func.lower(name)
            )
        ).scalar_one_or_none()
    
    def get_multi(
        self, 
        db: Session, 
        *, 
        skip: int = 0, 
        limit: int = 100
    ) -> List[PropertyType]:
        """Get multiple property types with pagination and deterministic ordering"""
        query = select(PropertyType).order_by(PropertyType.name.asc())
        query = query.offset(skip).limit(limit)
        return list(db.execute(query).scalars().all())  # Normalize SQLAlchemy's sequence result to the declared list return type.
    
    def get_all(self, db: Session, limit: int = 500) -> List[PropertyType]:
        """
        Get all property types for dropdown/select options.
        Hard-capped at 500 for safety - lookup tables should stay small.
        """
        return list(  # Normalize SQLAlchemy's sequence result to the declared list return type.
            db.execute(
            select(PropertyType).order_by(PropertyType.name.asc()).limit(limit)
            ).scalars().all()
        )
    
    def search(
        self,
        db: Session,
        *,
        search_term: str,
        skip: int = 0,
        limit: int = 100
    ) -> List[PropertyType]:
        """
        Search property types by name or description.
        Handles nullable description field safely.
        """
        search_pattern = f"%{search_term}%"
        
        query = select(PropertyType).where(
            or_(
                PropertyType.name.ilike(search_pattern),
                PropertyType.description.ilike(search_pattern)
            )
        ).order_by(PropertyType.name.asc())
        
        return list(  # Normalize SQLAlchemy's sequence result to the declared list return type.
            db.execute(
            query.offset(skip).limit(limit)
            ).scalars().all()
        )
    
    def count(self, db: Session) -> int:
        """Count total property types"""
        return int(  # Coerce nullable aggregate scalar into the concrete int this API returns.
            db.execute(
            select(func.count(PropertyType.property_type_id))
            ).scalar() or 0
        )
    
    def exists(self, db: Session, *, property_type_id: int) -> bool:
        """Check if property type exists (optimized)"""
        return db.execute(
            select(1).where(PropertyType.property_type_id == property_type_id)
        ).scalar() is not None
    
    
    # CREATE OPERATIONS
        
    def create(
        self, 
        db: Session, 
        *, 
        obj_in: PropertyTypeCreate
    ) -> PropertyType:
        """
        Create a new property type.
        
        CRITICAL:
        - Name must be unique (enforced by DB constraint)
        - NO manual timestamp setting (DB handles via DEFAULT now())
        """
        # Check for duplicate name (case-insensitive) - DRY approach
        existing = self.get_by_name(db, name=obj_in.name)
        
        if existing:
            raise ValueError(f"Property type with name '{obj_in.name}' already exists")
        
        create_data = obj_in.dict(exclude_unset=True)
        
        db_obj = PropertyType(
            name=create_data["name"],
            description=create_data.get("description")
            # Timestamps handled by DB DEFAULT now()
        )
        
        db.add(db_obj)
        db.flush()
        db.refresh(db_obj)
        
        logger.info(
            "Property type created",
            extra={
                "property_type_id": db_obj.property_type_id,
                "name": db_obj.name
            }
        )
        
        return db_obj
    
    
    # UPDATE OPERATIONS
        
    def update(
        self, 
        db: Session, 
        *, 
        db_obj: PropertyType, 
        obj_in: PropertyTypeUpdate
    ) -> PropertyType:
        """
        Update a property type.
        
        Rules:
        - Never update: property_type_id, created_at
        - Check name uniqueness if being changed
        - updated_at handled by DB trigger
        """
        update_data = obj_in.dict(exclude_unset=True)
        
        # Check name uniqueness if being updated - DRY approach
        if "name" in update_data and update_data["name"]:
            new_name = update_data["name"]
            if new_name.lower() != db_obj.name.lower():
                # Check if another type has this name
                existing = self.get_by_name(db, name=new_name)
                
                existing_property_type_id = (  # Cast the loaded ORM ID to a concrete int so pyright doesn't keep SQLAlchemy's descriptor type in the comparison.
                    cast(int, existing.property_type_id) if existing is not None else None
                )
                current_property_type_id = cast(int, db_obj.property_type_id)  # Cast the current ORM ID to the concrete int stored on the instance before comparing.
                if existing_property_type_id is not None and existing_property_type_id != current_property_type_id:
                    raise ValueError(f"Property type with name '{new_name}' already exists")
        
        # Remove protected fields
        protected_fields = {"property_type_id", "created_at"}
        for field in protected_fields:
            update_data.pop(field, None)
        
        # Apply updates
        for field, value in update_data.items():
            if hasattr(db_obj, field):
                setattr(db_obj, field, value)
        
        # updated_at handled by DB trigger automatically
        
        db.add(db_obj)
        db.flush()
        db.refresh(db_obj)
        
        logger.info(
            "Property type updated",
            extra={
                "property_type_id": db_obj.property_type_id,
                "name": db_obj.name,
                "updated_fields": list(update_data.keys())
            }
        )
        
        return db_obj
    
    
    # DELETE OPERATIONS
        
    def delete(self, db: Session, *, property_type_id: int) -> Optional[PropertyType]:
        """
        Hard delete a property type (admin only).
        
        WARNING:
        - Will fail if type is referenced by properties (FK constraint)
        - Consider making type 'inactive' via description instead
        - Only use for cleanup of unused types
        """
        db_obj = self.get(db, property_type_id=property_type_id)
        if not db_obj:
            raise ValueError(f"Property type with id={property_type_id} not found")
        
        try:
            # Check if type is in use
            from app.models.properties import Property
            
            usage_count = db.execute(
                select(func.count(Property.property_id)).where(
                    Property.property_type_id == property_type_id
                )
            ).scalar()
            
            if (usage_count or 0) > 0:
                logger.warning(
                    "Attempted deletion of in-use property type",
                    extra={
                        "property_type_id": property_type_id,
                        "property_type_name": db_obj.name,
                        "usage_count": usage_count
                    }
                )
                raise ValueError(
                    f"Cannot delete property type: {usage_count} properties still using it"
                )
            
            db.delete(db_obj)
            db.flush()
            
            logger.info(
                "Property type deleted",
                extra={
                    "property_type_id": property_type_id,
                    "property_type_name": db_obj.name
                }
            )
            
            return db_obj
            
        except ValueError:
            # Re-raise domain errors as-is
            raise
        except Exception as e:
            logger.error(
                "Unexpected error deleting property type",
                extra={
                    "property_type_id": property_type_id,
                    "error_type": type(e).__name__
                },
                exc_info=True
            )
            raise ValueError("Failed to delete property type. Please try again.")
    
    def remove(self, db: Session, *, property_type_id: int) -> Optional[PropertyType]:
        """
        Alias for delete() to match endpoint naming convention.
        Hard delete a property type.
        """
        return self.delete(db, property_type_id=property_type_id)
    
    
    # STATISTICS AND ANALYTICS
    
    def get_usage_stats(self, db: Session) -> List[Dict[str, Any]]:
        """
        Get usage statistics for all property types.
        Returns count of properties per type.
        Uses OUTER JOIN to include zero-usage types.
        """
        from app.models.properties import Property
        
        query = select(
            PropertyType.property_type_id,
            PropertyType.name,
            func.count(Property.property_id).label('property_count')
        ).outerjoin(
            Property,
            PropertyType.property_type_id == Property.property_type_id
        ).group_by(
            PropertyType.property_type_id
        ).order_by(
            func.count(Property.property_id).desc()
        )
        
        results = db.execute(query).all()
        
        return [
            {
                "property_type_id": row[0],
                "name": row[1],
                "property_count": row[2]
            }
            for row in results
        ]
    
    
    # UTILITY METHODS
        
    def get_or_create(
        self,
        db: Session,
        *,
        name: str,
        description: Optional[str] = None
    ) -> PropertyType:
        """
        Get existing property type or create if doesn't exist.
        Useful for data import/seeding.
        Idempotent operation.
        """
        existing = self.get_by_name(db, name=name)
        if existing:
            return existing
        
        type_data = PropertyTypeCreate(name=name, description=description)
        return self.create(db, obj_in=type_data)
    
    def bulk_create(
        self,
        db: Session,
        *,
        types_data: List[Dict[str, str]]
    ) -> List[PropertyType]:
        """
        Bulk create property types (for seeding).
        Skips duplicates, returns all created types.
        Uses proper error handling with structured logging.
        
        Example:
        types_data = [
            {"name": "Apartment", "description": "..."},
            {"name": "House", "description": "..."}
        ]
        """
        created_types = []
        
        for type_dict in types_data:
            try:
                existing = self.get_by_name(db, name=type_dict["name"])
                if not existing:
                    type_obj = PropertyTypeCreate(**type_dict)
                    created = self.create(db, obj_in=type_obj)
                    created_types.append(created)
                else:
                    created_types.append(existing)
            except ValueError as e:
                # Log domain errors but continue seeding
                logger.warning(
                    f"Skipped property type during bulk create",
                    extra={
                        "name": type_dict.get("name"),
                        "reason": str(e)
                    }
                )
                continue
            except Exception as e:
                # Log unexpected errors but don't crash seed operation
                logger.error(
                    f"Error creating property type during bulk operation",
                    extra={
                        "name": type_dict.get("name"),
                        "error_type": type(e).__name__
                    },
                    exc_info=True
                )
                continue
        
        logger.info(
            "Bulk property type creation completed",
            extra={
                "total_requested": len(types_data),
                "successfully_created": len(created_types)
            }
        )
        
        return created_types


# Singleton instance
property_type = PropertyTypeCRUD()
