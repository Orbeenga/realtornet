# app/crud/property_images.py
"""
PropertyImage CRUD operations - 100% aligned to DB schema.
DB Table: property_images (PK: image_id, FK: property_id)
Canonical Rules: NO audit trail, hard delete, primary image enforcement
"""

from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select, and_, func, delete as sql_delete
import logging

from app.models.property_images import PropertyImage
from app.models.properties import Property
from app.schemas.property_images import PropertyImageCreate, PropertyImageUpdate


logger = logging.getLogger(__name__)


class PropertyImageCRUD:
    """CRUD operations for PropertyImage model - DB-first canonical implementation"""
    
    
    # READ OPERATIONS
        
    def get(self, db: Session, image_id: int) -> Optional[PropertyImage]:
        """Get a property image by image_id (PK)"""
        return db.get(PropertyImage, image_id)
    
    def get_by_property(
        self,
        db: Session,
        *,
        property_id: int
    ) -> List[PropertyImage]:
        """
        Get all images for a property.
        Ordered: primary first, then by display_order, then by created_at.
        """
        query = select(PropertyImage).where(
            PropertyImage.property_id == property_id
        ).order_by(
            PropertyImage.is_primary.desc(),
            PropertyImage.display_order.asc(),
            PropertyImage.created_at.asc()
        )
        
        return db.execute(query).scalars().all()
    
    def get_primary_image(
        self,
        db: Session,
        *,
        property_id: int
    ) -> Optional[PropertyImage]:
        """Get the primary image for a property"""
        query = select(PropertyImage).where(
            and_(
                PropertyImage.property_id == property_id,
                PropertyImage.is_primary == True
            )
        )
        
        return db.execute(query).scalar_one_or_none()
    
    def count_property_images(
        self,
        db: Session,
        *,
        property_id: int
    ) -> int:
        """Count images for a property"""
        return db.execute(
            select(func.count(PropertyImage.image_id)).where(
                PropertyImage.property_id == property_id
            )
        ).scalar()
    
    
    # CREATE OPERATIONS
        
    def create(
        self,
        db: Session,
        *,
        obj_in: PropertyImageCreate
    ) -> PropertyImage:
        """
        Create a new property image.
        
        CRITICAL:
        - Validates property exists
        - If is_primary=True, unsets other primaries
        - If first image, automatically sets as primary
        - NO audit trail (no created_by/updated_by)
        - Timestamps handled by DB DEFAULT now()
        """
        # Validate property exists
        property_obj = db.get(Property, obj_in.property_id)
        if not property_obj:
            raise ValueError(f"Property with id={obj_in.property_id} not found")
        
        create_data = obj_in.dict(exclude_unset=True)
        is_primary = create_data.get("is_primary", False)
        
        # If this is the first image, make it primary automatically
        if self.count_property_images(db, property_id=obj_in.property_id) == 0:
            is_primary = True
        
        # If setting as primary, unset current primary
        if is_primary:
            self.unset_primary(db, property_id=obj_in.property_id)
        
        # Get next display order
        next_order = self.get_next_order(db, property_id=obj_in.property_id)
        
        db_obj = PropertyImage(
            property_id=obj_in.property_id,
            image_url=create_data["image_url"],
            caption=create_data.get("caption"),
            is_primary=is_primary,
            display_order=next_order
            # Timestamps handled by DB DEFAULT now()
        )
        
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        
        logger.info(
            "Property image created",
            extra={
                "image_id": db_obj.image_id,
                "property_id": db_obj.property_id,
                "is_primary": db_obj.is_primary
            }
        )
        
        return db_obj
    
    
    # UPDATE OPERATIONS
        
    def update(
        self,
        db: Session,
        *,
        db_obj: PropertyImage,
        obj_in: PropertyImageUpdate
    ) -> PropertyImage:
        """
        Update a property image metadata.
        
        Rules:
        - Never update: image_id, property_id, created_at
        - If setting is_primary=True, unset other primary images
        - updated_at handled by DB trigger
        """
        update_data = obj_in.dict(exclude_unset=True)
        
        # If setting as primary, unset current primary
        if update_data.get("is_primary") == True and not db_obj.is_primary:
            self.unset_primary(db, property_id=db_obj.property_id)
        
        # Remove protected fields
        protected_fields = {"image_id", "property_id", "created_at"}
        for field in protected_fields:
            update_data.pop(field, None)
        
        # Apply updates
        for field, value in update_data.items():
            if hasattr(db_obj, field):
                setattr(db_obj, field, value)
        
        # updated_at handled by DB trigger automatically
        
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        
        logger.info(
            "Property image updated",
            extra={
                "image_id": db_obj.image_id,
                "property_id": db_obj.property_id,
                "is_primary": db_obj.is_primary
            }
        )
        
        return db_obj
    
    
    # DELETE OPERATIONS
        
    def remove(self, db: Session, *, image_id: int) -> None:
        """
        Hard delete a property image.
        
        If deleting primary image, automatically promotes another image.
        No return value (hard delete).
        """
        db_obj = self.get(db, image_id=image_id)
        if not db_obj:
            raise ValueError(f"Image with id={image_id} not found")
        
        was_primary = db_obj.is_primary
        property_id = db_obj.property_id
        
        # Delete the image
        db.delete(db_obj)
        db.commit()
        
        logger.info(
            "Property image deleted",
            extra={
                "image_id": image_id,
                "property_id": property_id,
                "was_primary": was_primary
            }
        )
        
        # If deleted image was primary, promote another
        if was_primary:
            remaining = self.get_by_property(db, property_id=property_id)
            if remaining:
                # Promote first remaining image to primary
                remaining[0].is_primary = True
                db.add(remaining[0])
                db.commit()
    
    
    # UTILITY METHODS
        
    def get_next_order(
        self,
        db: Session,
        *,
        property_id: int
    ) -> int:
        """
        Calculate next display_order for a property.
        Returns max(display_order) + 1, or 0 if no images exist.
        """
        max_order = db.execute(
            select(func.max(PropertyImage.display_order)).where(
                PropertyImage.property_id == property_id
            )
        ).scalar()
        
        return (max_order + 1) if max_order is not None else 0
    
    def unset_primary(
        self,
        db: Session,
        *,
        property_id: int
    ) -> None:
        """
        Unset primary flag for all images of a property.
        Used when setting a new primary image.
        Optimized: Single UPDATE query instead of loop.
        """
        from sqlalchemy import update as sql_update
        
        db.execute(
            sql_update(PropertyImage)
            .where(
                and_(
                    PropertyImage.property_id == property_id,
                    PropertyImage.is_primary == True
                )
            )
            .values(is_primary=False)
        )
        db.commit()
    
    def reorder(
        self,
        db: Session,
        *,
        property_id: int,
        image_order: List[int]
    ) -> None:
        """
        Reorder images for a property.
        image_order is a list of image_ids in desired display order.
        Updates display_order for each image accordingly.
        """
        # Validate all images belong to this property
        images = self.get_by_property(db, property_id=property_id)
        image_ids = {img.image_id for img in images}
        
        for provided_id in image_order:
            if provided_id not in image_ids:
                raise ValueError(f"Image {provided_id} does not belong to property {property_id}")
        
        # Update display_order for each image
        for order_index, image_id in enumerate(image_order):
            image = self.get(db, image_id=image_id)
            if image:
                image.display_order = order_index
                db.add(image)
        
        db.commit()
        
        logger.info(
            "Property images reordered",
            extra={
                "property_id": property_id,
                "new_order": image_order
            }
        )


# Singleton instance
property_image = PropertyImageCRUD()