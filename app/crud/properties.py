# app/crud/properties.py
"""
Property CRUD operations - 100% aligned to DB schema.
DB Table: properties (PK: property_id)
Canonical Rules: Main entity with geography, enums, soft delete
"""

from typing import List, Optional, Dict, Any, Tuple, Union
from sqlalchemy.orm import Session
from sqlalchemy import select, func, and_, or_, cast, Float, String, update, delete
from datetime import datetime, timezone
from fastapi import HTTPException
from geoalchemy2.functions import ST_DWithin, ST_Distance, ST_MakeEnvelope, ST_SetSRID, ST_MakePoint
from geoalchemy2.elements import WKTElement

from app.models.properties import Property, ListingType, ListingStatus
from app.models.locations import Location
from app.schemas.properties import PropertyCreate, PropertyUpdate, PropertyFilter
from app.models.property_types import PropertyType


class PropertyCRUD:
    """CRUD operations for Property model - DB-first canonical implementation"""
    
    
    # READ OPERATIONS
        
    def get(self, db: Session, property_id: int) -> Optional[Property]:
        """Get a property by property_id (PK)"""
        # CHANGE 1: Guard against None PK — fixes SAWarning on line 30
        if property_id is None:
            return None
        return db.get(Property, property_id)
    
    # CHANGE 2: Single consolidated get_multi (removed duplicate second definition)
    # Merges: include_deleted from first + dict filters from second + ENUM cast fix
    def get_multi(
        self,
        db: Session,
        *,
        skip: int = 0,
        limit: int = 100,
        user_id: Optional[int] = None,
        include_deleted: bool = False,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Property]:
        """
        Get multiple properties with optional filtering.

        CANONICAL: Input sanitization prevents DataError.
        Supports include_deleted and dict-based advanced filters.
        ENUM filters use case-insensitive cast to prevent PG type mismatch.
        """
        skip = max(0, skip)
        limit = max(0, limit)

        query = select(Property)

        if filters:
            # Normalize: accept both Pydantic models and plain dicts
            if hasattr(filters, 'model_dump'):
                filters = filters.model_dump(exclude_unset=True)
            elif hasattr(filters, 'dict'):
                filters = filters.dict(exclude_unset=True)

        if not include_deleted:
            query = query.where(Property.deleted_at.is_(None))

        if user_id:
            query = query.where(Property.user_id == user_id)

        if filters:
            # Price range
            if filters.get("min_price") is not None:
                query = query.where(Property.price >= filters["min_price"])
            if filters.get("max_price") is not None:
                query = query.where(Property.price <= filters["max_price"])

            # Bedrooms/bathrooms
            if filters.get("bedrooms") is not None:
                query = query.where(Property.bedrooms == filters["bedrooms"])
            if filters.get("min_bedrooms") is not None:
                query = query.where(Property.bedrooms >= filters["min_bedrooms"])
            if filters.get("bathrooms") is not None:
                query = query.where(Property.bathrooms == filters["bathrooms"])

            # Property type & location
            if filters.get("property_type_id") is not None:
                query = query.where(Property.property_type_id == filters["property_type_id"])
            if filters.get("location_id") is not None:
                query = query.where(Property.location_id == filters["location_id"])

            # CHANGE 3: ENUM filters — case-insensitive cast prevents PG type mismatch
            if filters.get("listing_type") is not None:
                type_val = str(filters["listing_type"]).lower()
                query = query.where(
                    func.lower(cast(Property.listing_type, String)) == type_val
                )
            if filters.get("listing_status") is not None:
                status_val = str(filters["listing_status"]).lower()
                query = query.where(
                    func.lower(cast(Property.listing_status, String)) == status_val
                )

            # Boolean filters
            if filters.get("is_verified") is not None:
                query = query.where(Property.is_verified == filters["is_verified"])
            if filters.get("is_featured") is not None:
                query = query.where(Property.is_featured == filters["is_featured"])

            # Amenity filters
            if filters.get("has_swimming_pool") is not None:
                query = query.where(Property.has_swimming_pool == filters["has_swimming_pool"])
            if filters.get("has_garden") is not None:
                query = query.where(Property.has_garden == filters["has_garden"])
            if filters.get("has_security") is not None:
                query = query.where(Property.has_security == filters["has_security"])

        query = query.order_by(Property.created_at.desc()).offset(skip).limit(limit)
        return db.execute(query).scalars().all()
    
    def get_featured(
        self, 
        db: Session, 
        *, 
        limit: int = 6
    ) -> List[Property]:
        """Get featured properties (verified and featured flag)"""
        query = select(Property).where(
            and_(
                Property.is_featured == True,
                Property.listing_status == ListingStatus.available,
                Property.deleted_at.is_(None)
            )
        ).order_by(Property.created_at.desc()).limit(limit)
        
        return db.execute(query).scalars().all()
    
    def count(
        self, 
        db: Session, 
        *, 
        user_id: Optional[int] = None,
        include_deleted: bool = False
    ) -> int:
        """Count properties with optional filters"""
        query = select(func.count(Property.property_id))
        
        if not include_deleted:
            query = query.where(Property.deleted_at.is_(None))
        
        if user_id is not None:
            query = query.where(Property.user_id == user_id)
        
        return db.execute(query).scalar()
    
    def search(
        self, 
        db: Session, 
        *, 
        search_term: str, 
        skip: int = 0, 
        limit: int = 100
    ) -> List[Property]:
        """Search properties by text in title or description"""
        search_pattern = f"%{search_term}%"
        
        query = select(Property).where(
            and_(
                Property.deleted_at.is_(None),
                or_(
                    Property.title.ilike(search_pattern),
                    Property.description.ilike(search_pattern)
                )
            )
        ).order_by(Property.created_at.desc()).offset(skip).limit(limit)
        
        return db.execute(query).scalars().all()
    
    
    # ADVANCED FILTERING
        
    def get_by_filters(
        self, 
        db: Session, 
        *, 
        filters: PropertyFilter, 
        skip: int = 0, 
        limit: int = 100
    ) -> List[Property]:
        """
        Advanced filtering with geography support.
        Returns properties matching all specified filters.
        """
        query = select(Property).join(
            Location, 
            Property.location_id == Location.location_id
        )
    
        query = query.where(Property.deleted_at.is_(None))
        
        distance_column = None
        
        # Price filters
        if filters.min_price is not None:
            query = query.where(Property.price >= filters.min_price)
        if filters.max_price is not None:
            query = query.where(Property.price <= filters.max_price)
        
        # Room filters
        if filters.bedrooms is not None:
            query = query.where(Property.bedrooms >= filters.bedrooms)
        if filters.bathrooms is not None:
            query = query.where(Property.bathrooms >= filters.bathrooms)
        
        # Property type filter
        if filters.property_type_id is not None:
            query = query.where(Property.property_type_id == filters.property_type_id)
        
        # CHANGE 3 (continued): ENUM filters in get_by_filters — case-insensitive cast
        if filters.listing_type is not None:
            query = query.where(
                func.lower(cast(Property.listing_type, String)) == str(filters.listing_type).lower()
            )
        
        if filters.listing_status is not None:
            query = query.where(
                func.lower(cast(Property.listing_status, String)) == str(filters.listing_status).lower()
            )
        else:
            # Default: only show available properties
            query = query.where(
                func.lower(cast(Property.listing_status, String)) == "available"
            )
        
        # Property size filter
        if filters.min_property_size is not None:
            query = query.where(Property.property_size >= filters.min_property_size)
        if filters.max_property_size is not None:
            query = query.where(Property.property_size <= filters.max_property_size)
        
        # Location filters
        if filters.state is not None:
            query = query.where(Location.state.ilike(filters.state))
        if filters.city is not None:
            query = query.where(Location.city.ilike(filters.city))
        if filters.neighborhood is not None:
            query = query.where(Location.neighborhood.ilike(filters.neighborhood))
        
        # Geography filter (radius search)
        if all([filters.latitude, filters.longitude, filters.radius_km]):
            point = WKTElement(
                f'POINT({filters.longitude} {filters.latitude})', 
                srid=4326
            )
            
            distance_column = cast(
                ST_Distance(Location.geom, point) / 1000, 
                Float
            ).label('distance_km')
            
            query = query.where(
                ST_DWithin(
                    Location.geom,
                    point,
                    filters.radius_km * 1000
                )
            )
        
        # Boolean amenity filters
        if filters.has_garden is not None:
            query = query.where(Property.has_garden == filters.has_garden)
        if filters.has_security is not None:
            query = query.where(Property.has_security == filters.has_security)
        if filters.has_swimming_pool is not None:
            query = query.where(Property.has_swimming_pool == filters.has_swimming_pool)
        
        # CHANGE 4: parking_spaces (correct column name, was min_parking_spaces)
        if filters.min_parking_spaces is not None:
            query = query.where(Property.parking_spaces >= filters.min_parking_spaces)
        
        # Year built filter
        if filters.min_year_built is not None:
            query = query.where(Property.year_built >= filters.min_year_built)
        if filters.max_year_built is not None:
            query = query.where(Property.year_built <= filters.max_year_built)
        
        # Featured filter
        if filters.is_featured is not None:
            query = query.where(Property.is_featured == filters.is_featured)
        
        # Verified filter
        if filters.is_verified is not None:
            query = query.where(Property.is_verified == filters.is_verified)
        
        # Sorting
        if filters.sort_by == "price_asc":
            query = query.order_by(Property.price.asc())
        elif filters.sort_by == "price_desc":
            query = query.order_by(Property.price.desc())
        elif filters.sort_by == "date_desc":
            query = query.order_by(Property.created_at.desc())
        elif filters.sort_by == "date_asc":
            query = query.order_by(Property.created_at.asc())
        elif filters.sort_by == "size_desc":
            query = query.order_by(Property.property_size.desc())
        elif filters.sort_by == "size_asc":
            query = query.order_by(Property.property_size.asc())
        elif filters.sort_by == "distance" and distance_column is not None:
            query = query.order_by(distance_column)
        else:
            query = query.order_by(Property.created_at.desc())
        
        query = query.offset(skip).limit(limit)
        
        return db.execute(query).scalars().all()
    
    def get_nearby_properties(
        self,
        db: Session,
        *,
        latitude: float,
        longitude: float,
        radius_km: float = 5.0,
        skip: int = 0,
        limit: int = 20
    ) -> List[Tuple[Property, float]]:
        """
        Get properties near coordinates with distance.
        Returns list of (Property, distance_km) tuples sorted by distance.
        """
        point = WKTElement(f'POINT({longitude} {latitude})', srid=4326)
        
        query = select(
            Property,
            cast(
                ST_Distance(Location.geom, point) / 1000, 
                Float
            ).label('distance_km')
        ).join(
            Location,
            Property.location_id == Location.location_id
        ).where(
            and_(
                Property.deleted_at.is_(None),
                Property.listing_status == ListingStatus.available,
                ST_DWithin(
                    Location.geom,
                    point,
                    radius_km * 1000
                )
            )
        ).order_by('distance_km').offset(skip).limit(limit)
        
        results = db.execute(query).all()
        return [(row[0], round(row[1], 2)) for row in results]
    
    
    # CREATE OPERATIONS
    
    def create(
        self, 
        db: Session, 
        *, 
        obj_in: PropertyCreate, 
        user_id: int,
        created_by_supabase_id: Optional[str] = None
    ) -> Property:
        """
        Create a new property listing.
        
        CRITICAL:
        - user_id from auth context (not request body)
        - Validates location_id and property_type_id exist
        - NO manual timestamp setting (DB handles via DEFAULT now())
        """
        location_obj = db.get(Location, obj_in.location_id)
        if not location_obj:
            raise HTTPException(
                status_code=404,
                detail=f"Location with id={obj_in.location_id} not found"
            )
        
        property_type_obj = db.get(PropertyType, obj_in.property_type_id)
        if not property_type_obj:
            raise HTTPException(
                status_code=404,
                detail=f"Property type with id={obj_in.property_type_id} not found"
            )
        
        create_data = obj_in.model_dump(mode='python', exclude_unset=True)
        
        db_obj = Property(
            **create_data,
            user_id=user_id,
            is_verified=False,
            updated_by=created_by_supabase_id
        )
        
        db.add(db_obj)
        db.flush()
        db.refresh(db_obj)
        return db_obj
    
    
    # UPDATE OPERATIONS
        
    def update(
        self, 
        db: Session, 
        *, 
        db_obj: Property, 
        obj_in: Union[PropertyUpdate, Dict[str, Any]],
        updated_by_supabase_id: Optional[str] = None
    ) -> Property:
        """
        Update a property.
        
        Rules:
        - Never update: property_id, user_id, created_at
        - Validate location_id and property_type_id if being changed
        - updated_at handled by DB trigger
        """
        update_data = obj_in.dict(exclude_unset=True) if not isinstance(obj_in, dict) else obj_in
        
        if "location_id" in update_data and update_data["location_id"]:
            location_obj = db.get(Location, update_data["location_id"])
            if not location_obj:
                raise HTTPException(
                    status_code=404,
                    detail=f"Location with id={update_data['location_id']} not found"
                )
        
        if "property_type_id" in update_data and update_data["property_type_id"]:
            property_type_obj = db.get(PropertyType, update_data["property_type_id"])
            if not property_type_obj:
                raise HTTPException(
                    status_code=404,
                    detail=f"Property type with id={update_data['property_type_id']} not found"
                )
        
        protected_fields = {"property_id", "user_id", "created_at", "deleted_at"}
        for field in protected_fields:
            update_data.pop(field, None)
        
        for field, value in update_data.items():
            if hasattr(db_obj, field):
                setattr(db_obj, field, value)
        
        if updated_by_supabase_id:
            db_obj.updated_by = updated_by_supabase_id
        
        db.add(db_obj)
        db.flush()
        db.refresh(db_obj)
        return db_obj
    
    def update_listing_status(
        self,
        db: Session,
        *,
        property_id: int,
        listing_status: ListingStatus,
        updated_by_supabase_id: Optional[str] = None
    ) -> Optional[Property]:
        """Update property listing status (e.g., available → sold)."""
        db_obj = self.get(db, property_id=property_id)
        if not db_obj:
            return None
        
        db_obj.listing_status = listing_status
        if updated_by_supabase_id:
            db_obj.updated_by = updated_by_supabase_id
        
        db.add(db_obj)
        db.flush()
        db.refresh(db_obj)
        return db_obj
    
    def verify_property(
        self,
        db: Session,
        *,
        property_id: int,
        is_verified: bool = True,
        updated_by_supabase_id: Optional[str] = None
    ) -> Optional[Property]:
        """Verify property (admin operation)"""
        db_obj = self.get(db, property_id=property_id)
        if not db_obj:
            return None
        
        db_obj.is_verified = is_verified
        if is_verified:
            db_obj.verification_date = datetime.now(timezone.utc)
        else:
            db_obj.verification_date = None
        
        if updated_by_supabase_id:
            db_obj.updated_by = updated_by_supabase_id
        
        db.add(db_obj)
        db.flush()
        db.refresh(db_obj)
        return db_obj
    
    def toggle_featured(
        self,
        db: Session,
        *,
        property_id: int,
        is_featured: bool,
        updated_by_supabase_id: Optional[str] = None
    ) -> Optional[Property]:
        """Toggle featured status (admin operation)"""
        db_obj = self.get(db, property_id=property_id)
        if not db_obj:
            return None
        
        db_obj.is_featured = is_featured
        if updated_by_supabase_id:
            db_obj.updated_by = updated_by_supabase_id
        
        db.add(db_obj)
        db.flush()
        db.refresh(db_obj)
        return db_obj
    
    
    # DELETE OPERATIONS
        
    def soft_delete(
        self,
        db: Session,
        *,
        property_id: int,
        deleted_by_supabase_id: Optional[str] = None
    ) -> Optional[Property]:
        """Soft delete a property by setting deleted_at timestamp."""
        db_obj = self.get(db, property_id=property_id)
        if not db_obj:
            return None
        
        db_obj.deleted_at = datetime.now(timezone.utc)
        if deleted_by_supabase_id:
            db_obj.updated_by = deleted_by_supabase_id
        
        db.add(db_obj)
        db.flush()
        db.refresh(db_obj)
        return db_obj
    
    def restore(
        self,
        db: Session,
        *,
        property_id: int,
        restored_by_supabase_id: Optional[str] = None
    ) -> Optional[Property]:
        """Restore a soft-deleted property"""
        db_obj = self.get(db, property_id=property_id)
        if not db_obj:
            return None
        
        db_obj.deleted_at = None
        if restored_by_supabase_id:
            db_obj.updated_by = restored_by_supabase_id
        
        db.add(db_obj)
        db.flush()
        db.refresh(db_obj)
        return db_obj
    
    def hard_delete_admin_only(
        self,
        db: Session,
        *,
        property_id: int
    ) -> Optional[Property]:
        """
        DANGEROUS: Permanently delete property (admin only).
        Only for GDPR/legal compliance requests.
        WARNING: Cascades to images, amenities, favorites, reviews, inquiries.
        """
        db_obj = self.get(db, property_id=property_id)
        if not db_obj:
            return None
        
        db.delete(db_obj)
        db.flush()
        return db_obj
    
    
    # AUTHORIZATION HELPERS
        
    def can_modify_property(
        self,
        current_user_id: int,
        property_user_id: int,
        is_admin: bool = False
    ) -> bool:
        """Owners can modify their properties, admins can modify any."""
        if is_admin:
            return True
        return current_user_id == property_user_id


    # GEOSPATIAL SEARCH: PROXIMITY (GPS-BASED)
    
    def get_properties_near(
        self,
        db: Session,
        *,
        latitude: float,
        longitude: float,
        radius_km: float,
        limit: int = 20
    ) -> List[Property]:
        """
        Find properties within radius of a point (GPS proximity search).
        CANONICAL: Uses Geography(POINT, 4326) with meters.
        """
        point = ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)
        radius_meters = radius_km * 1000
        
        query = (
            select(Property)
            .where(
                and_(
                    Property.deleted_at.is_(None),
                    Property.geom.isnot(None),
                    ST_DWithin(Property.geom, point, radius_meters)
                )
            )
            .order_by(ST_Distance(Property.geom, point))
            .limit(limit)
        )
        
        return db.execute(query).scalars().all()
    
    
    # GEOSPATIAL SEARCH: BOUNDING BOX (MAP-BASED)
    
    def get_properties_in_bounds(
        self,
        db: Session,
        *,
        min_lat: float,
        min_lon: float,
        max_lat: float,
        max_lon: float,
        limit: int = 100
    ) -> List[Property]:
        """
        Find properties within map bounding box.
        CANONICAL: Handles antipodal edge cases (world-spanning boxes).
        """
        # Clamp to valid ranges (prevent antipodal edges)
        min_lat = max(-89.9, min(89.9, min_lat))
        max_lat = max(-89.9, min(89.9, max_lat))
        min_lon = max(-179.9, min(179.9, min_lon))
        max_lon = max(-179.9, min(179.9, max_lon))
        
        if (max_lon - min_lon) > 359.0 or (max_lat - min_lat) > 179.0:
            query = (
                select(Property)
                .where(
                    and_(
                        Property.deleted_at.is_(None),
                        Property.geom.isnot(None)
                    )
                )
                .limit(limit)
            )
        else:
            envelope = ST_MakeEnvelope(min_lon, min_lat, max_lon, max_lat, 4326)
            query = (
                select(Property)
                .where(
                    and_(
                        Property.deleted_at.is_(None),
                        Property.geom.isnot(None),
                        Property.geom.ST_Intersects(envelope)
                    )
                )
                .limit(limit)
            )
        
        return db.execute(query).scalars().all()
    
    
    # UTILITY: DISTANCE CALCULATION
    
    def calculate_distance(
        self,
        property_a: Property,
        property_b: Property
    ) -> float:
        """
        Calculate distance in kilometers between two properties.
        Returns 0.0 if either property lacks coordinates.
        """
        if not property_a.geom or not property_b.geom:
            return 0.0
        
        from app.utils.geospatial import wkt_to_coords, get_distance_between_points
        
        try:
            coords_a = wkt_to_coords(str(property_a.geom))
            coords_b = wkt_to_coords(str(property_b.geom))
            
            if not coords_a or not coords_b:
                return 0.0
            
            lon_a, lat_a = coords_a
            lon_b, lat_b = coords_b
            
            return get_distance_between_points(lat_a, lon_a, lat_b, lon_b, unit="km")
        except Exception:
            return 0.0
    
    
    # BULK OPERATIONS: VERIFICATION
    
    def bulk_verify(
        self,
        db: Session,
        *,
        property_ids: List[int],
        is_verified: bool = True,
        updated_by_supabase_id: Optional[str] = None
    ) -> int:
        """Bulk verify/unverify properties."""
        values = {
            "is_verified": is_verified,
            "verification_date": func.now() if is_verified else None,
            "updated_at": func.now()
        }
        
        if updated_by_supabase_id:
            values["updated_by"] = updated_by_supabase_id
        
        stmt = (
            update(Property)
            .where(
                and_(
                    Property.property_id.in_(property_ids),
                    Property.deleted_at.is_(None)
                )
            )
            .values(**values)
        )
        
        result = db.execute(stmt)
        db.flush()
        
        return result.rowcount
    
    
    # BULK OPERATIONS: STATUS UPDATE
    
    def bulk_update_status(
        self,
        db: Session,
        *,
        property_ids: List[int],
        new_status: str,
        updated_by_supabase_id: Optional[str] = None
    ) -> int:
        """Bulk update listing status."""
        values = {
            "listing_status": new_status,
            "updated_at": func.now()
        }
        
        if updated_by_supabase_id:
            values["updated_by"] = updated_by_supabase_id
        
        stmt = (
            update(Property)
            .where(
                and_(
                    Property.property_id.in_(property_ids),
                    Property.deleted_at.is_(None)
                )
            )
            .values(**values)
        )
        
        result = db.execute(stmt)
        db.flush()
        
        return result.rowcount
    
    
    # BULK OPERATIONS: SOFT DELETE
    
    def bulk_soft_delete(
        self,
        db: Session,
        *,
        property_ids: List[int],
        deleted_by_supabase_id: Optional[str] = None
    ) -> int:
        """Bulk soft delete properties."""
        values = {
            "deleted_at": func.now(),
            "updated_at": func.now()
        }
        
        if deleted_by_supabase_id:
            values["deleted_by"] = deleted_by_supabase_id
        
        stmt = (
            update(Property)
            .where(
                and_(
                    Property.property_id.in_(property_ids),
                    Property.deleted_at.is_(None)
                )
            )
            .values(**values)
        )
        
        result = db.execute(stmt)
        db.flush()
        
        return result.rowcount


# Singleton instance
property = PropertyCRUD()