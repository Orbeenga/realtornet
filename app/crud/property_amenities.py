# app/crud/property_amenities.py
"""
PropertyAmenity CRUD operations - 100% aligned to DB schema.
DB Table: property_amenities (Composite PK: property_id, amenity_id)
Canonical Rules: Junction table pattern, many-to-many relationship
"""

from typing import List, Optional, cast
from sqlalchemy.orm import Session
from sqlalchemy import select, delete, and_, func
from sqlalchemy.engine import CursorResult
from sqlalchemy.exc import SQLAlchemyError
import logging
import json

#from app.models.property_amenities import property_amenities
from app.models.property_amenities import property_amenities as property_amenities_table
from app.models.amenities import Amenity


logger = logging.getLogger(__name__)


class PropertyAmenityCRUD:
    """
    CRUD operations for PropertyAmenity junction table.
    Manages many-to-many relationship between properties and amenities.
    """
    
    
    # READ OPERATIONS
        
    def get(
        self,
        db: Session,
        *,
        property_id: int,
        amenity_id: int
    ) -> bool:
        """Check if a specific property-amenity association exists"""
        query = select(property_amenities_table).where(
            and_(
                property_amenities_table.c.property_id == property_id,
                property_amenities_table.c.amenity_id == amenity_id
            )
        )
        return db.execute(query).first() is not None
    
    def get_property_amenities(
        self,
        db: Session,
        *,
        property_id: int
    ) -> List[Amenity]:
        """
        Get all amenities for a property.
        Returns list of Amenity objects.
        """
        query = select(Amenity).join(
            property_amenities_table,
            Amenity.amenity_id == property_amenities_table.c.amenity_id
        ).where(
            property_amenities_table.c.property_id == property_id
        ).order_by(Amenity.name.asc())
        
        return list(db.execute(query).scalars().all())  # Normalize SQLAlchemy Sequence[...] to concrete list return type.
    
    def get_amenities_for_property(
        self,
        db: Session,
        *,
        property_id: int
    ) -> List[Amenity]:
        """Alias for get_property_amenities() - matches endpoint naming"""
        return self.get_property_amenities(db, property_id=property_id)
    
    def get_property_amenity_ids(
        self,
        db: Session,
        *,
        property_id: int
    ) -> List[int]:
        """
        Get amenity IDs for a property (lightweight, deterministic).
        Useful for comparison/checking without loading full objects.
        Ordered by amenity_id for consistency.
        """
        query = select(property_amenities_table.c.amenity_id).where(
            property_amenities_table.c.property_id == property_id
        ).order_by(property_amenities_table.c.amenity_id.asc())
        
        return list(db.execute(query).scalars().all())  # Normalize SQLAlchemy Sequence[...] to concrete list return type.
    
    def has_amenity(
        self,
        db: Session,
        *,
        property_id: int,
        amenity_id: int
    ) -> bool:
        """Check if property has specific amenity"""
        query = select(property_amenities_table).where(
            and_(
                property_amenities_table.c.property_id == property_id,
                property_amenities_table.c.amenity_id == amenity_id
            )
        )
        
        return db.execute(query).first() is not None
    
    def count_property_amenities(
        self,
        db: Session,
        *,
        property_id: int
    ) -> int:
        """Count amenities for a property"""
        return db.execute(
            select(func.count(property_amenities_table.c.amenity_id)).where(
                property_amenities_table.c.property_id == property_id
            )
        ).scalar() or 0  # COUNT is expected non-null; provide typed fallback for strict checkers.
    
    def count_by_amenity(
        self,
        db: Session,
        *,
        amenity_id: int
    ) -> int:
        """
        Count how many properties use a specific amenity.
        Used by endpoint to check if amenity can be deleted.
        """
        return db.execute(
            select(func.count(property_amenities_table.c.property_id)).where(
                property_amenities_table.c.amenity_id == amenity_id
            )
        ).scalar() or 0  # COUNT is expected non-null; provide typed fallback for strict checkers.
    
    
    # CREATE OPERATIONS (Add Amenities)
        
    def add_amenity(
        self,
        db: Session,
        *,
        property_id: int,
        amenity_id: int
    ) -> bool:
        """
        Add a single amenity to a property.
        Idempotent - silently succeeds if already exists.
        
        Validates:
        - Property exists
        - Amenity exists
        
        Returns:
        - True if added, False if already existed
        """
        # Validate property exists
        from app.models.properties import Property
        property_obj = db.get(Property, property_id)
        if not property_obj:
            raise ValueError(f"Property with id={property_id} not found")
        
        # Validate amenity exists
        amenity_obj = db.get(Amenity, amenity_id)
        if not amenity_obj:
            raise ValueError(f"Amenity with id={amenity_id} not found")
        
        # Check if already exists
        if self.has_amenity(db, property_id=property_id, amenity_id=amenity_id):
            return False  # Already exists - idempotent
        
        # Create junction record using insert
        stmt = property_amenities_table.insert().values(
            property_id=property_id,
            amenity_id=amenity_id
        )
        db.execute(stmt)
        db.flush()
        return True
    
    def create(
        self,
        db: Session,
        *,
        property_id: int,
        amenity_id: int
    ) -> bool:
        """
        Create single property-amenity association.
        Alias for add_amenity() - matches endpoint naming.
        """
        return self.add_amenity(
            db,
            property_id=property_id,
            amenity_id=amenity_id
        )
    
    def add_amenities(
        self,
        db: Session,
        *,
        property_id: int,
        amenity_ids: List[int],
        commit: bool = True
    ) -> int:
        """
        Add multiple amenities to a property.
        Skips duplicates, validates all amenity IDs exist.
        
        Args:
            commit: If False, caller is responsible for commit (for atomic operations)
        
        Returns:
            Count of amenities actually added (excludes duplicates)
        """
        # Validate property exists
        from app.models.properties import Property
        property_obj = db.get(Property, property_id)
        if not property_obj:
            raise ValueError(f"Property with id={property_id} not found")
        
        # Get existing amenity IDs for this property
        existing_ids = set(self.get_property_amenity_ids(db, property_id=property_id))
        
        # Filter out already existing
        new_amenity_ids = [aid for aid in amenity_ids if aid not in existing_ids]
        
        if not new_amenity_ids:
            return 0  # All already exist
        
        # Validate all new amenities exist
        existing_amenities = db.execute(
            select(Amenity.amenity_id).where(
                Amenity.amenity_id.in_(new_amenity_ids)
            )
        ).scalars().all()
        
        if len(existing_amenities) != len(new_amenity_ids):
            invalid_ids = set(new_amenity_ids) - set(existing_amenities)
            raise ValueError(f"Amenities not found: {invalid_ids}")
        
        # Bulk insert junction records
        if new_amenity_ids:
            values = [
                {"property_id": property_id, "amenity_id": amenity_id}
                for amenity_id in new_amenity_ids
            ]
            db.execute(property_amenities_table.insert(), values)
        
        if commit:
            db.flush()
        
        return len(new_amenity_ids)
    
    def create_bulk(
        self,
        db: Session,
        *,
        property_id: int,
        amenity_ids: List[int]
    ) -> int:
        """Alias for add_amenities() - matches endpoint naming"""
        return self.add_amenities(
            db,
            property_id=property_id,
            amenity_ids=amenity_ids
        )
    
    def set_amenities(
        self,
        db: Session,
        *,
        property_id: int,
        amenity_ids: List[int]
    ) -> List[Amenity]:
        """
        Set exact amenities for a property (replaces all).
        Removes old, adds new - atomic operation.
        
        This is the canonical "update amenities" operation.
        """
        # Validate property exists
        from app.models.properties import Property
        property_obj = db.get(Property, property_id)
        if not property_obj:
            raise ValueError(f"Property with id={property_id} not found")
        
        # Get current amenity IDs
        current_ids = set(self.get_property_amenity_ids(db, property_id=property_id))
        new_ids = set(amenity_ids)
        
        # Calculate diff
        to_remove = current_ids - new_ids
        to_add = new_ids - current_ids
        
        try:
            # Atomic operation
            # Remove old amenities
            if to_remove:
                db.execute(
                    delete(property_amenities_table).where(
                        and_(
                            property_amenities_table.c.property_id == property_id,
                            property_amenities_table.c.amenity_id.in_(to_remove)
                        )
                    )
                )
            
            # Add new amenities (validates existence inside)
            if to_add:
                self.add_amenities(
                    db, 
                    property_id=property_id, 
                    amenity_ids=list(to_add),
                    commit=False  # Defer commit to outer transaction
                )
            
            db.flush()
            
        except SQLAlchemyError as e:
            db.rollback()
            logger.error(
                "Failed to sync property amenities",
                extra={
                    "property_id": property_id,
                    "requested_amenities": amenity_ids,
                    "error": str(e)
                },
                exc_info=True
            )
            raise ValueError("Failed to update amenities. Please try again.")
        except Exception as e:
            db.rollback()
            logger.error(
                "Unexpected error syncing property amenities",
                extra={
                    "property_id": property_id,
                    "error_type": type(e).__name__
                },
                exc_info=True
            )
            raise ValueError("An unexpected error occurred. Please contact support.")
        
        # Return final amenity list
        return self.get_property_amenities(db, property_id=property_id)
    
    def sync(
        self,
        db: Session,
        *,
        property_id: int,
        amenity_ids: List[int]
    ) -> None:
        """
        Sync property amenities to exact list.
        Alias for set_amenities() - matches endpoint naming.
        Returns None (endpoint gets amenities separately).
        """
        self.set_amenities(db, property_id=property_id, amenity_ids=amenity_ids)
    
    
    # DELETE OPERATIONS (Remove Amenities)
        
    def remove_amenity(
        self,
        db: Session,
        *,
        property_id: int,
        amenity_id: int
    ) -> bool:
        """
        Remove a single amenity from a property.
        Returns True if removed, False if didn't exist.
        """
        result = cast(CursorResult, db.execute(
            delete(property_amenities_table).where(
                and_(
                    property_amenities_table.c.property_id == property_id,
                    property_amenities_table.c.amenity_id == amenity_id
                )
            )
        ))  # Delete returns a cursor-style result at runtime; cast keeps rowcount access typed.
        
        db.flush()
        return result.rowcount > 0
    
    def remove(
        self,
        db: Session,
        *,
        property_id: int,
        amenity_id: int
    ) -> None:
        """
        Remove single property-amenity association.
        Alias for remove_amenity() - matches endpoint naming.
        Returns None (endpoint doesn't need return value).
        """
        self.remove_amenity(db, property_id=property_id, amenity_id=amenity_id)
    
    def remove_amenities(
        self,
        db: Session,
        *,
        property_id: int,
        amenity_ids: List[int]
    ) -> int:
        """
        Remove multiple amenities from a property.
        Returns count of removed records.
        """
        result = cast(CursorResult, db.execute(
            delete(property_amenities_table).where(
                and_(
                    property_amenities_table.c.property_id == property_id,
                    property_amenities_table.c.amenity_id.in_(amenity_ids)
                )
            )
        ))  # Delete returns a cursor-style result at runtime; cast keeps rowcount access typed.
        
        db.flush()
        return result.rowcount
    
    def remove_bulk(
        self,
        db: Session,
        *,
        property_id: int,
        amenity_ids: List[int]
    ) -> int:
        """Alias for remove_amenities() - matches endpoint naming"""
        return self.remove_amenities(
            db,
            property_id=property_id,
            amenity_ids=amenity_ids
        )
    
    def clear_property_amenities(
        self,
        db: Session,
        *,
        property_id: int
    ) -> int:
        """
        Remove all amenities from a property.
        Returns count of removed records.
        """
        result = cast(CursorResult, db.execute(
            delete(property_amenities_table).where(
                property_amenities_table.c.property_id == property_id
            )
        ))  # Delete returns a cursor-style result at runtime; cast keeps rowcount access typed.
        
        db.flush()
        return result.rowcount
    
    
    # UTILITY METHODS
        
    def copy_amenities(
        self,
        db: Session,
        *,
        from_property_id: int,
        to_property_id: int
    ) -> int:
        """
        Copy amenities from one property to another.
        Useful for cloning/duplicating properties.
        
        IMPORTANT: No ownership validation performed at CRUD layer.
        Caller (endpoint) MUST verify current user has permission to:
        - Read amenities from source property
        - Write amenities to target property
        This is critical when RLS policies are enabled.
        
        Returns:
            Count of amenities copied
        """
        # Get source amenities
        source_amenity_ids = self.get_property_amenity_ids(
            db,
            property_id=from_property_id
        )
        
        if not source_amenity_ids:
            return 0
        
        # Add to target property
        return self.add_amenities(
            db,
            property_id=to_property_id,
            amenity_ids=source_amenity_ids
        )


# Singleton instance
property_amenities = PropertyAmenityCRUD()

# Backward compatibility alias
property_amenity = property_amenities
