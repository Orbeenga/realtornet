# app/crud/saved_searches.py

"""
CRUD operations for saved_searches table.
Soft delete default, proper PK naming, DB-first alignment.
"""

from typing import Any, Dict, List, Optional, cast  # Include concrete mapping types for the JSONB-to-filter normalization path.
from sqlalchemy import select, func, and_
from sqlalchemy.orm import Session

from app.crud.properties import property as property_crud  # Reuse the canonical property filtering implementation instead of duplicating query logic here.
from app.models.saved_searches import SavedSearch
from app.schemas.properties import PropertyFilter, PropertyResponse  # Reuse the shared property filter/response schemas when executing stored searches.
from app.schemas.saved_searches import SavedSearchCreate, SavedSearchUpdate


class SavedSearchCRUD:
    """CRUD operations for user saved searches"""

    def create(
        self, 
        db: Session, 
        *, 
        obj_in: SavedSearchCreate,
        user_id: int
    ) -> SavedSearch:
        """Create a new saved search"""
        db_obj = SavedSearch(
            user_id=user_id,
            search_params=obj_in.search_params,
            name=obj_in.name
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
        search_id: int
    ) -> Optional[SavedSearch]:
        """Get an active saved search by ID"""
        stmt = select(SavedSearch).where(
            and_(
                SavedSearch.search_id == search_id,
                SavedSearch.deleted_at.is_(None)
            )
        )
        return db.execute(stmt).scalar_one_or_none()

    def get_user_saved_searches(
        self, 
        db: Session, 
        *, 
        user_id: int,
        skip: int = 0,
        limit: int = 100
    ) -> List[SavedSearch]:
        """
        Get all active saved searches for a user.
        Ordered by created_at DESC (newest first).
        """
        stmt = (
            select(SavedSearch)
            .where(
                and_(
                    SavedSearch.user_id == user_id,
                    SavedSearch.deleted_at.is_(None)
                )
            )
            .order_by(SavedSearch.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(db.execute(stmt).scalars().all())  # Normalize SQLAlchemy's sequence result to the declared list return type.

    def update(
        self, 
        db: Session, 
        *,
        db_obj: Optional[SavedSearch] = None,
        search_id: Optional[int] = None,
        obj_in: SavedSearchUpdate
    ) -> Optional[SavedSearch]:
        """
        Update a saved search.
        For search_params: performs MERGE (updates nested keys).
        updated_at handled by DB trigger automatically.
        """
        if db_obj is None and search_id is not None:
            db_obj = self.get(db=db, search_id=search_id)
        if not db_obj:
            return None

        update_data = obj_in.model_dump(exclude_unset=True)
        
        # Protect core fields from update
        protected_fields = {'search_id', 'user_id', 'created_at'}
        for field in protected_fields:
            update_data.pop(field, None)

        for field, value in update_data.items():
            if field == "search_params" and isinstance(value, dict):
                # Merge new params into existing (partial update)
                current_params = db_obj.search_params or {}
                current_params.update(value)
                setattr(db_obj, field, current_params)
            else:
                setattr(db_obj, field, value)

        # DB trigger handles updated_at
        db.flush()
        db.refresh(db_obj)
        return db_obj

    def soft_delete(
        self, 
        db: Session, 
        *, 
        search_id: int,
        deleted_by_supabase_id: Optional[str] = None
    ) -> Optional[SavedSearch]:
        """
        Soft delete a saved search.
        ORM sets deleted_at; DB trigger handles updated_at only.
        """
        db_obj = self.get(db=db, search_id=search_id)
        if not db_obj:
            return None

        cast(Any, db_obj).deleted_at = func.now()  # Narrow ORM instance attribute assignment to its runtime timestamp field while preserving the DB trigger behavior.
        db_obj.deleted_by = deleted_by_supabase_id
        db.flush()
        db.refresh(db_obj)
        return db_obj

    def count_user_saved_searches(
        self, 
        db: Session, 
        *, 
        user_id: int
    ) -> int:
        """Count active saved searches for a user"""
        stmt = select(func.count()).select_from(SavedSearch).where(
            and_(
                SavedSearch.user_id == user_id,
                SavedSearch.deleted_at.is_(None)
            )
        )
        return int(db.execute(stmt).scalar() or 0)  # Coerce nullable aggregate scalar into the concrete int this API returns.

    def get_by_name(
        self,
        db: Session,
        *,
        user_id: int,
        name: str
    ) -> Optional[SavedSearch]:
        """Get a saved search by name (case-insensitive) for a user"""
        stmt = select(SavedSearch).where(
            and_(
                SavedSearch.user_id == user_id,
                func.lower(SavedSearch.name) == func.lower(name),
                SavedSearch.deleted_at.is_(None)
            )
        )
        return db.execute(stmt).scalar_one_or_none()

    def search_by_name_pattern(
        self,
        db: Session,
        *,
        user_id: int,
        pattern: str,
        skip: int = 0,
        limit: int = 100
    ) -> List[SavedSearch]:
        """Search saved searches by name pattern (case-insensitive LIKE)"""
        stmt = (
            select(SavedSearch)
            .where(
                and_(
                    SavedSearch.user_id == user_id,
                    SavedSearch.name.ilike(f"%{pattern}%"),
                    SavedSearch.deleted_at.is_(None)
                )
            )
            .order_by(SavedSearch.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(db.execute(stmt).scalars().all())  # Normalize SQLAlchemy's sequence result to the declared list return type.

    def execute_search(
        self,
        db: Session,
        saved_search: SavedSearch,
        skip: int,
        limit: int,
    ) -> List[Dict[str, Any]]:
        """Execute a saved search by applying its stored JSONB parameters to property filtering."""
        raw_search_params: Dict[str, Any] = cast(Dict[str, Any], saved_search.search_params or {})  # Narrow the persisted JSONB payload to the dict shape this executor consumes.
        normalized_search_params: Dict[str, Any] = dict(raw_search_params)  # Copy the stored payload so alias normalization never mutates the ORM-backed JSONB field in place.

        if "price_min" in normalized_search_params and "min_price" not in normalized_search_params:  # Support legacy saved-search aliases while preserving the canonical filter field names.
            normalized_search_params["min_price"] = normalized_search_params["price_min"]  # Map the legacy minimum-price alias onto the property filter schema key.
        if "price_max" in normalized_search_params and "max_price" not in normalized_search_params:  # Support legacy saved-search aliases while preserving the canonical filter field names.
            normalized_search_params["max_price"] = normalized_search_params["price_max"]  # Map the legacy maximum-price alias onto the property filter schema key.

        property_filters: PropertyFilter = PropertyFilter(**normalized_search_params)  # Validate and coerce the stored JSONB payload through the shared property filter schema before querying.
        matching_properties = property_crud.get_by_filters(  # Reuse the canonical property filtering query so saved searches stay aligned with live property search behavior.
            db,
            filters=property_filters,
            skip=skip,
            limit=limit,
        )
        return [  # Serialize the ORM results through the shared response schema so the endpoint can return property-shaped dictionaries without reshaping its contract.
            PropertyResponse.model_validate(property_obj).model_dump(mode="json")
            for property_obj in matching_properties
        ]


# Singleton instance
saved_search = SavedSearchCRUD()
