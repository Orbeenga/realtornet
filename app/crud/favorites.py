# app/crud/favorites.py

"""
CRUD operations for favorites table.
Canonical soft-delete pattern, no phantom fields, DB-first alignment.
"""

from typing import List, Optional
from sqlalchemy import select, func, and_
from sqlalchemy.orm import Session

from app.models.favorites import Favorite
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
        If previously soft-deleted, restore it instead.
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
                # Restore soft-deleted favorite
                existing.deleted_at = None
                db.commit()
                db.refresh(existing)
                return existing
            # Already exists and active
            return existing

        # Create new favorite
        db_obj = Favorite(
            user_id=user_id,
            property_id=obj_in.property_id
        )
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def soft_delete(
        self, 
        db: Session, 
        *, 
        user_id: int, 
        property_id: int
    ) -> Optional[Favorite]:
        """
        Soft delete a favorite.
        deleted_at set by DB trigger automatically.
        """
        obj = self.get(db=db, user_id=user_id, property_id=property_id)
        if obj:
            # DB trigger handles actual timestamp
            db.commit()
            db.refresh(obj)
        return obj

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
            .where(
                and_(
                    Favorite.user_id == user_id,
                    Favorite.deleted_at.is_(None)
                )
            )
            .order_by(Favorite.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return db.execute(stmt).scalars().all()

    def is_favorited(
        self, 
        db: Session, 
        *, 
        user_id: int, 
        property_id: int
    ) -> bool:
        """Check if a property is actively favorited by a user"""
        stmt = select(func.count()).select_from(Favorite).where(
            and_(
                Favorite.user_id == user_id,
                Favorite.property_id == property_id,
                Favorite.deleted_at.is_(None)
            )
        )
        count = db.execute(stmt).scalar()
        return count > 0

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
        return db.execute(stmt).scalar()

    def count_user_favorites(
        self,
        db: Session,
        *,
        user_id: int
    ) -> int:
        """Count total active favorites for a user"""
        stmt = select(func.count()).select_from(Favorite).where(
            and_(
                Favorite.user_id == user_id,
                Favorite.deleted_at.is_(None)
            )
        )
        return db.execute(stmt).scalar()


# Singleton instance
favorite = FavoriteCRUD()
