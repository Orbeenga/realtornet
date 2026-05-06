# app/crud/saved_searches.py

"""
CRUD operations for saved_searches table.
Soft delete default, proper PK naming, DB-first alignment.
"""

import logging
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional, cast  # Include concrete mapping types for the JSONB-to-filter normalization path.
from uuid import UUID
from sqlalchemy import select, func, and_
from sqlalchemy.orm import Session
from pydantic import ValidationError

from app.crud.properties import property as property_crud  # Reuse the canonical property filtering implementation instead of duplicating query logic here.
from app.models.locations import Location
from app.models.properties import Property
from app.models.saved_searches import SavedSearch
from app.models.users import User
from app.schemas.properties import PropertyFilter, PropertyResponse  # Reuse the shared property filter/response schemas when executing stored searches.
from app.schemas.saved_searches import SavedSearchCreate, SavedSearchUpdate


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SavedSearchMatch:
    """Email-ready saved-search match payload produced by one batch scan."""

    search_id: int
    user_id: int
    user_email: str
    search_name: str | None
    unsubscribe_token: UUID


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

    def get_by_unsubscribe_token(
        self,
        db: Session,
        *,
        unsubscribe_token: UUID | str,
    ) -> Optional[SavedSearch]:
        """Get an active saved search by its public unsubscribe token."""
        stmt = select(SavedSearch).where(
            and_(
                SavedSearch.unsubscribe_token == unsubscribe_token,
                SavedSearch.deleted_at.is_(None),
            )
        )
        return db.execute(stmt).scalar_one_or_none()

    def unsubscribe_by_token(
        self,
        db: Session,
        *,
        unsubscribe_token: UUID | str,
    ) -> Optional[SavedSearch]:
        """
        Deactivate a saved search from a public unsubscribe token.

        The table's lifecycle contract is soft delete, so unsubscribe uses the
        same deleted_at state as authenticated saved-search deletion.
        """
        db_obj = self.get_by_unsubscribe_token(db, unsubscribe_token=unsubscribe_token)
        if not db_obj:
            return None

        cast(Any, db_obj).deleted_at = func.now()
        db.flush()
        db.refresh(db_obj)
        return db_obj

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

    def _normalized_filter_params(self, search_params: Dict[str, Any]) -> Dict[str, Any]:
        normalized_search_params: Dict[str, Any] = dict(search_params)
        if "price_min" in normalized_search_params and "min_price" not in normalized_search_params:
            normalized_search_params["min_price"] = normalized_search_params["price_min"]
        if "price_max" in normalized_search_params and "max_price" not in normalized_search_params:
            normalized_search_params["max_price"] = normalized_search_params["price_max"]
        return normalized_search_params

    def _to_decimal(self, value: Any) -> Decimal | None:
        if value is None:
            return None
        try:
            return Decimal(str(value))
        except (InvalidOperation, ValueError):
            return None

    def _enum_value(self, value: Any) -> str | None:
        if value is None:
            return None
        return str(getattr(value, "value", value)).lower()

    def _matches_property_filter(
        self,
        *,
        property_obj: Property,
        property_location: Location | None,
        filters: PropertyFilter,
    ) -> bool:
        property_price = self._to_decimal(getattr(property_obj, "price", None))
        if filters.min_price is not None and (property_price is None or property_price < filters.min_price):
            return False
        if filters.max_price is not None and (property_price is None or property_price > filters.max_price):
            return False

        property_bedrooms: int | None = cast(int | None, getattr(property_obj, "bedrooms", None))
        if filters.bedrooms is not None and (property_bedrooms is None or property_bedrooms < filters.bedrooms):
            return False

        property_bathrooms: int | None = cast(int | None, getattr(property_obj, "bathrooms", None))
        if filters.bathrooms is not None and (property_bathrooms is None or property_bathrooms < filters.bathrooms):
            return False

        if filters.property_type_id is not None and getattr(property_obj, "property_type_id", None) != filters.property_type_id:
            return False
        if filters.location_id is not None and getattr(property_obj, "location_id", None) != filters.location_id:
            return False

        if filters.listing_type is not None and self._enum_value(getattr(property_obj, "listing_type", None)) != str(filters.listing_type).lower():
            return False
        if filters.listing_status is not None and self._enum_value(getattr(property_obj, "listing_status", None)) != str(filters.listing_status).lower():
            return False

        if filters.state is not None:
            if property_location is None or str(property_location.state or "").lower() != filters.state.lower():
                return False
        if filters.city is not None:
            if property_location is None or str(property_location.city or "").lower() != filters.city.lower():
                return False
        if filters.neighborhood is not None:
            if property_location is None or str(property_location.neighborhood or "").lower() != filters.neighborhood.lower():
                return False

        return True

    def find_matches_for_verified_property(
        self,
        db: Session,
        *,
        property_obj: Property,
    ) -> List[SavedSearchMatch]:
        """
        Find active saved searches matching a newly verified property.

        This intentionally scans saved searches in one joined query, then
        applies the existing PropertyFilter schema in memory so verification
        does not fan out into one property query per seeker.
        """
        location_id: int | None = cast(int | None, getattr(property_obj, "location_id", None))
        property_location = db.get(Location, location_id) if location_id is not None else None
        stmt = (
            select(SavedSearch, User)
            .join(User, SavedSearch.user_id == User.user_id)
            .where(
                SavedSearch.deleted_at.is_(None),
                User.deleted_at.is_(None),
            )
        )
        rows = db.execute(stmt).all()
        matches: list[SavedSearchMatch] = []
        for saved_search_obj, user_obj in rows:
            raw_params: Dict[str, Any] = cast(Dict[str, Any], saved_search_obj.search_params or {})
            try:
                filters = PropertyFilter(**self._normalized_filter_params(raw_params))
            except ValidationError:
                logger.warning(
                    "Skipping invalid saved search criteria during match detection",
                    extra={"search_id": saved_search_obj.search_id},
                    exc_info=True,
                )
                continue

            if not self._matches_property_filter(
                property_obj=property_obj,
                property_location=property_location,
                filters=filters,
            ):
                continue

            user_email = str(getattr(user_obj, "email", "") or "").strip()
            if not user_email:
                continue
            matches.append(
                SavedSearchMatch(
                    search_id=cast(int, saved_search_obj.search_id),
                    user_id=cast(int, saved_search_obj.user_id),
                    user_email=user_email,
                    search_name=cast(str | None, saved_search_obj.name),
                    unsubscribe_token=cast(UUID, saved_search_obj.unsubscribe_token),
                )
            )
        return matches


# Singleton instance
saved_search = SavedSearchCRUD()
