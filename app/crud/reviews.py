# app/crud/reviews.py

"""
Unified CRUD operations for reviews table.
Single table with nullable property_id/agent_id for polymorphic reviews.
Soft delete default, no manual timestamps, DB-first canonical alignment.
"""

from typing import List, Optional, Dict, Any
from sqlalchemy import select, func, and_, or_
from sqlalchemy.orm import Session

from app.models.reviews import Review
from app.schemas.reviews import ReviewCreate, ReviewUpdate


class ReviewCRUD:
    """Unified CRUD operations for property and agent reviews"""

    def create(
        self, 
        db: Session, 
        *, 
        obj_in: ReviewCreate,
        user_id: int
    ) -> Review:
        """
        Create a new review (property or agent).
        Business rule: exactly one of property_id or agent_id must be set.
        """
        # Validate mutual exclusivity
        property_id = getattr(obj_in, 'property_id', None)
        agent_id = getattr(obj_in, 'agent_id', None)

        if (property_id is None and agent_id is None) or \
            (property_id is not None and agent_id is not None):
            raise ValueError("Exactly one of property_id or agent_id must be provided")

        db_obj = Review(
            user_id=user_id,
            property_id=property_id,
            agent_id=agent_id,
            rating=obj_in.rating,
            comment=obj_in.comment
            # created_at, updated_at handled by DB
        )
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def get(
        self, 
        db: Session, 
        *, 
        review_id: int
    ) -> Optional[Review]:
        """Get an active review by ID"""
        stmt = select(Review).where(
            and_(
                Review.review_id == review_id,
                Review.deleted_at.is_(None)
            )
        )
        return db.execute(stmt).scalar_one_or_none()

    def get_property_reviews(
        self, 
        db: Session, 
        *, 
        property_id: int,
        skip: int = 0,
        limit: int = 100,
        sort_by: str = "created_at",
        sort_desc: bool = True
    ) -> List[Review]:
        """Get active reviews for a specific property"""
        # Whitelist sortable columns
        allowed_sort_cols = {'created_at', 'updated_at', 'rating'}
        sort_col = sort_by if sort_by in allowed_sort_cols else 'created_at'
        
        order_column = getattr(Review, sort_col)
        order_expr = order_column.desc() if sort_desc else order_column.asc()

        stmt = (
            select(Review)
            .where(
                and_(
                    Review.property_id == property_id,
                    Review.deleted_at.is_(None)
                )
            )
            .order_by(order_expr)
            .offset(skip)
            .limit(limit)
        )
        return db.execute(stmt).scalars().all()

    def get_agent_reviews(
        self, 
        db: Session, 
        *, 
        agent_id: int,
        skip: int = 0,
        limit: int = 100,
        sort_by: str = "created_at",
        sort_desc: bool = True
    ) -> List[Review]:
        """Get active reviews for a specific agent"""
        allowed_sort_cols = {'created_at', 'updated_at', 'rating'}
        sort_col = sort_by if sort_by in allowed_sort_cols else 'created_at'
        
        order_column = getattr(Review, sort_col)
        order_expr = order_column.desc() if sort_desc else order_column.asc()

        stmt = (
            select(Review)
            .where(
                and_(
                    Review.agent_id == agent_id,
                    Review.deleted_at.is_(None)
                )
            )
            .order_by(order_expr)
            .offset(skip)
            .limit(limit)
        )
        return db.execute(stmt).scalars().all()

    def get_user_reviews(
        self, 
        db: Session, 
        *, 
        user_id: int,
        skip: int = 0,
        limit: int = 100
    ) -> List[Review]:
        """Get all active reviews created by a user (both property and agent)"""
        stmt = (
            select(Review)
            .where(
                and_(
                    Review.user_id == user_id,
                    Review.deleted_at.is_(None)
                )
            )
            .order_by(Review.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return db.execute(stmt).scalars().all()

    def get_user_property_review(
        self,
        db: Session,
        *,
        user_id: int,
        property_id: int
    ) -> Optional[Review]:
        """Check if user has already reviewed a specific property"""
        stmt = select(Review).where(
            and_(
                Review.user_id == user_id,
                Review.property_id == property_id,
                Review.deleted_at.is_(None)
            )
        )
        return db.execute(stmt).scalar_one_or_none()

    def get_user_agent_review(
        self,
        db: Session,
        *,
        user_id: int,
        agent_id: int
    ) -> Optional[Review]:
        """Check if user has already reviewed a specific agent"""
        stmt = select(Review).where(
            and_(
                Review.user_id == user_id,
                Review.agent_id == agent_id,
                Review.deleted_at.is_(None)
            )
        )
        return db.execute(stmt).scalar_one_or_none()

    # ------------------------------------------------------------------
    # Compatibility methods used by reviews API endpoints
    # ------------------------------------------------------------------
    def get_property_review_by_user_and_property(
        self,
        db: Session,
        *,
        user_id: int,
        property_id: int
    ) -> Optional[Review]:
        return self.get_user_property_review(
            db,
            user_id=user_id,
            property_id=property_id,
        )

    def get_agent_review_by_user_and_agent(
        self,
        db: Session,
        *,
        user_id: int,
        agent_id: int
    ) -> Optional[Review]:
        return self.get_user_agent_review(
            db,
            user_id=user_id,
            agent_id=agent_id,
        )

    def create_property_ReviewResponse(
        self,
        db: Session,
        *,
        obj_in: ReviewCreate,
        user_id: int
    ) -> Review:
        return self.create(db, obj_in=obj_in, user_id=user_id)

    def create_agent_ReviewResponse(
        self,
        db: Session,
        *,
        obj_in: Any,
        user_id: int
    ) -> Review:
        return self.create(db, obj_in=obj_in, user_id=user_id)

    def get_property_ReviewResponse(
        self,
        db: Session,
        *,
        review_id: int
    ) -> Optional[Review]:
        stmt = select(Review).where(
            and_(
                Review.review_id == review_id,
                Review.property_id.is_not(None),
                Review.deleted_at.is_(None),
            )
        )
        return db.execute(stmt).scalar_one_or_none()

    def get_agent_ReviewResponse(
        self,
        db: Session,
        *,
        review_id: int
    ) -> Optional[Review]:
        stmt = select(Review).where(
            and_(
                Review.review_id == review_id,
                Review.agent_id.is_not(None),
                Review.deleted_at.is_(None),
            )
        )
        return db.execute(stmt).scalar_one_or_none()

    def update_property_ReviewResponse(
        self,
        db: Session,
        *,
        db_obj: Review,
        obj_in: ReviewUpdate
    ) -> Review:
        update_data = obj_in.model_dump(exclude_unset=True)
        if "rating" in update_data:
            db_obj.rating = update_data["rating"]
        if "comment" in update_data:
            db_obj.comment = update_data["comment"]
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def update_agent_ReviewResponse(
        self,
        db: Session,
        *,
        db_obj: Review,
        obj_in: ReviewUpdate
    ) -> Review:
        return self.update_property_ReviewResponse(
            db,
            db_obj=db_obj,
            obj_in=obj_in,
        )

    def soft_delete_property_ReviewResponse(
        self,
        db: Session,
        *,
        review_id: int,
        deleted_by_supabase_id: Optional[str] = None
    ) -> Optional[Review]:
        db_obj = self.get_property_ReviewResponse(db=db, review_id=review_id)
        if not db_obj:
            return None
        db_obj.deleted_at = func.now()
        db_obj.deleted_by = deleted_by_supabase_id
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def soft_delete_agent_ReviewResponse(
        self,
        db: Session,
        *,
        review_id: int,
        deleted_by_supabase_id: Optional[str] = None
    ) -> Optional[Review]:
        db_obj = self.get_agent_ReviewResponse(db=db, review_id=review_id)
        if not db_obj:
            return None
        db_obj.deleted_at = func.now()
        db_obj.deleted_by = deleted_by_supabase_id
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def get_property_reviews_by_user(
        self,
        db: Session,
        *,
        user_id: int,
        skip: int = 0,
        limit: int = 100
    ) -> List[Review]:
        stmt = (
            select(Review)
            .where(
                and_(
                    Review.user_id == user_id,
                    Review.property_id.is_not(None),
                    Review.deleted_at.is_(None),
                )
            )
            .order_by(Review.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return db.execute(stmt).scalars().all()

    def get_agent_reviews_by_user(
        self,
        db: Session,
        *,
        user_id: int,
        skip: int = 0,
        limit: int = 100
    ) -> List[Review]:
        stmt = (
            select(Review)
            .where(
                and_(
                    Review.user_id == user_id,
                    Review.agent_id.is_not(None),
                    Review.deleted_at.is_(None),
                )
            )
            .order_by(Review.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return db.execute(stmt).scalars().all()

    def update(
        self, 
        db: Session, 
        *, 
        review_id: int,
        obj_in: ReviewUpdate
    ) -> Optional[Review]:
        """
        Update a review.
        updated_at handled by DB trigger automatically.
        """
        db_obj = self.get(db=db, review_id=review_id)
        if not db_obj:
            return None

        update_data = obj_in.model_dump(exclude_unset=True)
        
        # Protect core fields from update
        protected_fields = {
            'review_id', 'user_id', 'property_id', 
            'agent_id', 'created_at'
        }
        for field in protected_fields:
            update_data.pop(field, None)

        for field, value in update_data.items():
            setattr(db_obj, field, value)

        # DB trigger handles updated_at
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def soft_delete(
        self, 
        db: Session, 
        *, 
        review_id: int,
        deleted_by_supabase_id: Optional[str] = None
    ) -> Optional[Review]:
        """
        Soft delete a review.
        deleted_at set by DB trigger.
        """
        db_obj = self.get(db=db, review_id=review_id)
        if not db_obj:
            return None

        db_obj.deleted_at = func.now()  # Trigger handles timestamp
        db_obj.deleted_by = deleted_by_supabase_id
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def get_property_rating_stats(
        self, 
        db: Session, 
        *, 
        property_id: int
    ) -> Dict[str, Any]:
        """Get rating statistics for a property"""
        stmt = select(
            func.count(Review.review_id).label("total_reviews"),
            func.avg(Review.rating).label("average_rating"),
            func.min(Review.rating).label("min_rating"),
            func.max(Review.rating).label("max_rating")
        ).where(
            and_(
                Review.property_id == property_id,
                Review.deleted_at.is_(None)
            )
        )
        
        result = db.execute(stmt).first()
        
        return {
            "total_reviews": result.total_reviews or 0,
            "average_rating": float(result.average_rating) if result.average_rating else 0.0,
            "min_rating": result.min_rating,
            "max_rating": result.max_rating
        }

    def get_agent_rating_stats(
        self, 
        db: Session, 
        *, 
        agent_id: int
    ) -> Dict[str, Any]:
        """Get rating statistics for an agent"""
        stmt = select(
            func.count(Review.review_id).label("total_reviews"),
            func.avg(Review.rating).label("average_rating"),
            func.min(Review.rating).label("min_rating"),
            func.max(Review.rating).label("max_rating")
        ).where(
            and_(
                Review.agent_id == agent_id,
                Review.deleted_at.is_(None)
            )
        )
        
        result = db.execute(stmt).first()
        
        return {
            "total_reviews": result.total_reviews or 0,
            "average_rating": float(result.average_rating) if result.average_rating else 0.0,
            "min_rating": result.min_rating,
            "max_rating": result.max_rating
        }

    def get_rating_distribution(
        self,
        db: Session,
        *,
        property_id: Optional[int] = None,
        agent_id: Optional[int] = None
    ) -> Dict[int, int]:
        """
        Get distribution of ratings (1-5 stars count).
        Provide either property_id or agent_id.
        """
        conditions = [Review.deleted_at.is_(None)]
        
        if property_id:
            conditions.append(Review.property_id == property_id)
        elif agent_id:
            conditions.append(Review.agent_id == agent_id)
        else:
            raise ValueError("Either property_id or agent_id must be provided")

        stmt = select(
            Review.rating,
            func.count(Review.review_id).label("count")
        ).where(
            and_(*conditions)
        ).group_by(Review.rating)

        results = db.execute(stmt).all()
        
        # Initialize all ratings 1-5 with 0 count
        distribution = {i: 0 for i in range(1, 6)}
        for row in results:
            distribution[row.rating] = row.count

        return distribution


# Singleton instance
review = ReviewCRUD()
