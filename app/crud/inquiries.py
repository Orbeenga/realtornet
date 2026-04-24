# app/crud/inquiries.py

"""
CRUD operations for inquiries table.
Soft delete default, no manual timestamps, proper FK joins.
"""

from typing import Any, List, Optional, cast
from sqlalchemy import select, and_, func
from sqlalchemy.orm import Session, joinedload

from app.models.inquiries import Inquiry
from app.models.properties import Property
from app.schemas.inquiries import InquiryCreate, InquiryUpdate


class InquiryCRUD:
    """CRUD operations for property inquiries"""

    def create(
        self, 
        db: Session, 
        *, 
        obj_in: InquiryCreate,
        user_id: int  # Explicit user_id parameter
    ) -> Inquiry:
        """Create a new inquiry with default 'new' status"""
        db_obj = Inquiry(
            user_id=user_id, # ✅ Use passed user_id
            property_id=obj_in.property_id,
            message=obj_in.message
            # inquiry_status defaults to 'new' in DB
            # created_at, updated_at handled by DB
        )
        db.add(db_obj)
        db.flush()
        db.refresh(db_obj)
        return db_obj

    def get(
        self, 
        db: Session, 
        *, 
        inquiry_id: int
    ) -> Optional[Inquiry]:
        """Get an active inquiry by ID"""
        stmt = select(Inquiry).where(
            and_(
                Inquiry.inquiry_id == inquiry_id,
                Inquiry.deleted_at.is_(None)
            )
        )
        return db.execute(stmt).scalar_one_or_none()

    def get_multi(
        self, 
        db: Session, 
        *, 
        skip: int = 0, 
        limit: int = 100
    ) -> List[Inquiry]:
        """
        Get multiple active inquiries with pagination.
        Ordered by created_at DESC (newest first).
        """
        stmt = (
            select(Inquiry)
            .where(Inquiry.deleted_at.is_(None))
            .order_by(Inquiry.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(db.execute(stmt).scalars().all())  # Normalize SQLAlchemy's sequence result to the declared list return type.

    def update(
        self, 
        db: Session, 
        *, 
        db_obj: Optional[Inquiry] = None, # Made optional
        inquiry_id: Optional[int] = None,  # Added to fix Failures 2-4
        obj_in: InquiryUpdate
    ) -> Optional[Inquiry]:
        """
        Update an inquiry. Supports update by object or inquiry_id for test compliance.
        """
        # If the test passed an ID instead of an object, fetch it
        if inquiry_id and not db_obj:
            db_obj = self.get(db=db, inquiry_id=inquiry_id)

        if not db_obj:
            return None

        update_data = obj_in.model_dump(exclude_unset=True)
        
        # Protect core fields from update (Standard 15)
        # Added 'inquiry_id' to protected_fields to satisfy test_strips_protected_fields
        protected_fields = {'id', 'user_id', 'property_id', 'inquiry_id', 'created_at'}
        for field in protected_fields:
            update_data.pop(field, None)

        for field, value in update_data.items():
            setattr(db_obj, field, value)

        db.flush()
        db.refresh(db_obj)
        return db_obj

    def soft_delete(
        self, 
        db: Session, 
        *, 
        inquiry_id: int,
        deleted_by_supabase_id: Optional[str] = None
    ) -> Optional[Inquiry]:
        """
        Soft delete an inquiry.
        ORM sets deleted_at; DB trigger handles updated_at only.
        """
        db_obj = self.get(db=db, inquiry_id=inquiry_id)
        if not db_obj:
            return None

        cast(Any, db_obj).deleted_at = func.now()  # Cast through Any so pyright accepts assigning the SQL timestamp expression to the ORM-backed field.
        db_obj.deleted_by = deleted_by_supabase_id
        db.flush()
        db.refresh(db_obj)
        return db_obj

    def get_by_property(
        self, 
        db: Session, 
        *, 
        property_id: int, 
        skip: int = 0, 
        limit: int = 100
    ) -> List[Inquiry]:
        """Get active inquiries for a specific property"""
        stmt = (
            select(Inquiry)
            .where(
                and_(
                    Inquiry.property_id == property_id,
                    Inquiry.deleted_at.is_(None)
                )
            )
            .order_by(Inquiry.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(db.execute(stmt).scalars().all())  # Normalize SQLAlchemy's sequence result to the declared list return type.

    def get_by_user(
        self, 
        db: Session, 
        *, 
        user_id: int, 
        skip: int = 0, 
        limit: int = 100
    ) -> List[Inquiry]:
        """Get active inquiries made by a specific user"""
        stmt = (
            select(Inquiry)
            .where(
                and_(
                    Inquiry.user_id == user_id,
                    Inquiry.deleted_at.is_(None)
                )
            )
            .order_by(Inquiry.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(db.execute(stmt).scalars().all())  # Normalize SQLAlchemy's sequence result to the declared list return type.

    def get_by_property_owner(
        self, 
        db: Session, 
        *, 
        owner_user_id: int, 
        skip: int = 0, 
        limit: int = 100
    ) -> List[Inquiry]:
        """
        Get active inquiries for properties owned by a specific user.
        Joins through Property table to filter by owner.
        """
        stmt = (
            select(Inquiry)
            .options(joinedload(Inquiry.user))
            .join(Property, Inquiry.property_id == Property.property_id)
            .where(
                and_(
                    Property.user_id == owner_user_id,
                    Inquiry.deleted_at.is_(None),
                    Property.deleted_at.is_(None)
                )
            )
            .order_by(Inquiry.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(db.execute(stmt).scalars().all())  # Normalize SQLAlchemy's sequence result to the declared list return type.

    def update_status(
        self, 
        db: Session, 
        *, 
        inquiry_id: int, 
        new_status: str
    ) -> Optional[Inquiry]:
        """
        Update inquiry status.
        Valid statuses: 'new', 'viewed', 'responded' (DB CHECK constraint).
        """
        db_obj = self.get(db=db, inquiry_id=inquiry_id)
        if not db_obj:
            return None

        cast(Any, db_obj).inquiry_status = new_status  # Cast through Any so pyright accepts assigning the validated runtime status string to the ORM-backed field.
        # DB trigger handles updated_at
        db.flush()
        db.refresh(db_obj)
        return db_obj

    def mark_as_viewed(
        self, 
        db: Session, 
        *, 
        inquiry_id: int
    ) -> Optional[Inquiry]:
        """Convenience method to mark inquiry as viewed"""
        return self.update_status(db=db, inquiry_id=inquiry_id, new_status='viewed')

    def mark_as_responded(
        self, 
        db: Session, 
        *, 
        inquiry_id: int
    ) -> Optional[Inquiry]:
        """Convenience method to mark inquiry as responded"""
        return self.update_status(db=db, inquiry_id=inquiry_id, new_status='responded')

    def count_by_property(
        self,
        db: Session,
        *,
        property_id: int
    ) -> int:
        """Count active inquiries for a property"""
        stmt = select(func.count()).select_from(Inquiry).where(
            and_(
                Inquiry.property_id == property_id,
                Inquiry.deleted_at.is_(None)
            )
        )
        return int(db.execute(stmt).scalar() or 0)  # Coerce the nullable aggregate scalar into the concrete int this API returns.

    def count_active(self, db: Session) -> int:
        """Count active (non-deleted) inquiries."""
        stmt = select(func.count()).select_from(Inquiry).where(
            Inquiry.deleted_at.is_(None)
        )
        return int(db.execute(stmt).scalar() or 0)  # Coerce the nullable aggregate scalar into the concrete int this API returns.

    def count_by_status(
        self,
        db: Session,
        *,
        property_id: int,
        status: str
    ) -> int:
        """Count inquiries by status for a property"""
        stmt = select(func.count()).select_from(Inquiry).where(
            and_(
                Inquiry.property_id == property_id,
                Inquiry.inquiry_status == status,
                Inquiry.deleted_at.is_(None)
            )
        )
        return int(db.execute(stmt).scalar() or 0)  # Coerce the nullable aggregate scalar into the concrete int this API returns.


# Singleton instance
inquiry = InquiryCRUD()
