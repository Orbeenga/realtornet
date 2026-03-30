# app/crud/favorites.py

"""
CRUD operations for favorites table.
Canonical soft-delete pattern, no phantom fields, DB-first alignment.
"""

from typing import Any, List, Optional, cast
from sqlalchemy import select, func, and_
from sqlalchemy.orm import Session

from app.models.favorites import Favorite
from app.models.properties import Property
from app.schemas.favorites import FavoriteCreate


class FavoriteCRUD:
    """CRUD operations for user property favorites"""

    def get(
        self, 
        db: Session, 
        *, 
        user_id: int, 
        property_id: int
    ) -> Optional[Favorite]:
        """Get an active favorite by composite key"""
        stmt = select(Favorite).where(
            and_(
                Favorite.user_id == user_id,
                Favorite.property_id == property_id,
                Favorite.deleted_at.is_(None)
            )
        )
        return db.execute(stmt).scalar_one_or_none()

    def create(
        self, 
        db: Session, 
        *, 
        obj_in: FavoriteCreate,
        user_id: int
    ) -> Favorite:
        """
        Create a new favorite.
        If a soft-deleted record exists, return it unchanged and let the endpoint
        enforce restore flow.
        """
        # Check if soft-deleted record exists
        existing = db.execute(
            select(Favorite).where(
                and_(
                    Favorite.user_id == user_id,
                    Favorite.property_id == obj_in.property_id
                )
            )
        ).scalar_one_or_none()

        if existing:
            if existing.deleted_at is not None:
                # Return existing soft-deleted favorite without restoring.
                # Endpoint decides whether to raise or call restore endpoint.
                return existing
            # Already exists and active
            return existing

        # Create new favorite
        db_obj = Favorite(
            user_id=user_id,
            property_id=obj_in.property_id
        )
        db.add(db_obj)
        db.flush()
        db.refresh(db_obj)
        return db_obj

    def soft_delete(
        self, 
        db: Session, 
        *, 
        user_id: int, 
        property_id: int,
        deleted_by_supabase_id: Optional[str] = None
    ) -> Optional[Favorite]:
        """
        Soft delete a favorite.
        """
        obj = self.get(db=db, user_id=user_id, property_id=property_id)
        if obj:
            cast(Any, obj).deleted_at = func.now()  # Cast through Any so pyright accepts assigning the SQL timestamp expression to the ORM-backed field.
            # Standard 14: Track audit trail
            if deleted_by_supabase_id:
                obj.deleted_by = deleted_by_supabase_id
            
            db.add(obj)
            db.flush()
            db.refresh(obj)
        return obj

    def bulk_soft_delete(
        self,
        db: Session,
        *,
        user_id: int,
        property_ids: List[int],
        deleted_by_supabase_id: Optional[str] = None
    ) -> int:
        """Bulk soft-delete favorites. Single SQL UPDATE, atomic, canonical Standard 7."""
        from sqlalchemy import update
        stmt = (
            update(Favorite)
            .where(
                Favorite.user_id == user_id,
                Favorite.property_id.in_(property_ids),
                Favorite.deleted_at.is_(None)
            )
            .values(
                deleted_at=func.now(),
                deleted_by=deleted_by_supabase_id
            )
        )
        result = db.execute(stmt)
        db.flush()
        return int(cast(Any, result).rowcount or 0)  # Cast the SQLAlchemy result metadata to a concrete int row count before returning it.

    def get_user_favorites(
        self, 
        db: Session, 
        *, 
        user_id: int, 
        skip: int = 0, 
        limit: int = 100
    ) -> List[Favorite]:
        """
        Get all active favorites for a user with pagination.
        Deterministic ordering by created_at DESC.
        """
        stmt = (
            select(Favorite)
            .join(Property, Favorite.property_id == Property.property_id)
            .where(
                and_(
                    Favorite.user_id == user_id,
                    Favorite.deleted_at.is_(None),
                    Property.deleted_at.is_(None)
                )
            )
            .order_by(Favorite.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(db.execute(stmt).scalars().all())  # Normalize SQLAlchemy's sequence result to the declared list return type.

    def is_favorited(
        self, 
        db: Session, 
        *, 
        user_id: int, 
        property_id: int
    ) -> bool:
        """Check if a property is actively favorited by a user"""
        stmt = (
            select(func.count())
            .select_from(Favorite)
            .join(Property, Favorite.property_id == Property.property_id)
            .where(
            and_(
                Favorite.user_id == user_id,
                Favorite.property_id == property_id,
                Favorite.deleted_at.is_(None),
                Property.deleted_at.is_(None),
            )
        ))
        count = db.execute(stmt).scalar()
        return (count or 0) > 0  # Normalize the nullable aggregate into a concrete int before comparing it.

    def count_active_favorites(
        self, 
        db: Session, 
        *, 
        property_id: int
    ) -> int:
        """Count how many users have actively favorited a property"""
        stmt = select(func.count()).select_from(Favorite).where(
            and_(
                Favorite.property_id == property_id,
                Favorite.deleted_at.is_(None)
            )
        )
        return int(db.execute(stmt).scalar() or 0)  # Coerce the nullable aggregate scalar into the concrete int this API returns.

    def count_user_favorites(
        self,
        db: Session,
        *,
        user_id: int
    ) -> int:
        """Count total active favorites for a user"""
        stmt = (
            select(func.count())
            .select_from(Favorite)
            .join(Property, Favorite.property_id == Property.property_id)
            .where(
                and_(
                    Favorite.user_id == user_id,
                    Favorite.deleted_at.is_(None),
                    Property.deleted_at.is_(None),
                )
            )
        )
        return int(db.execute(stmt).scalar() or 0)  # Coerce the nullable aggregate scalar into the concrete int this API returns.


    def restore_favorite(
        self, 
        db: Session, 
        *, 
        user_id: int, 
        property_id: int
    ) -> Optional[Favorite]:
        """
        Restore a previously soft-deleted favorite.
        Clears deleted_at timestamp.
        """
        # Find soft-deleted favorite
        stmt = select(Favorite).where(
            and_(
                Favorite.user_id == user_id,
                Favorite.property_id == property_id,
                Favorite.deleted_at.is_not(None)
            )
        )
        obj = db.execute(stmt).scalar_one_or_none()
        
        if obj:
            cast(Any, obj).deleted_at = None  # Cast through Any so pyright accepts clearing the ORM-backed soft-delete field during restore.
            db.flush()
            db.refresh(obj)
        
        return obj


# Singleton instance
favorite = FavoriteCRUD()
