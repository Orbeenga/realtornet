# app/crud/properties.py
"""
Property CRUD operations - 100% aligned to DB schema.
DB Table: properties (PK: property_id)
Canonical Rules: Main entity with geography, enums, soft delete
"""

from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import select, func, and_, or_, cast, Float
from datetime import datetime, timezone
from fastapi import HTTPException
from geoalchemy2.functions import ST_DWithin, ST_Distance
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
        return db.get(Property, property_id)
    
    def get_multi(
        self, 
        db: Session, 
        *, 
        skip: int = 0, 
        limit: int = 100,
        user_id: Optional[int] = None,
        include_deleted: bool = False
    ) -> List[Property]:
        """Get multiple properties with pagination"""
        query = select(Property)
        
        # Exclude soft-deleted by default
        if not include_deleted:
            query = query.where(Property.deleted_at.is_(None))
        
        # Filter by user if provided
        if user_id is not None:
            query = query.where(Property.user_id == user_id)
        
        # Order by recent first
        query = query.order_by(Property.created_at.desc())
        
        # Pagination
        query = query.offset(skip).limit(limit)
        
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
        # Base query
        query = select(Property).join(
            Location, 
            Property.location_id == Location.location_id
        )
    
        # Exclude soft-deleted
        query = query.where(Property.deleted_at.is_(None))
        
        # Variable to store distance column (only created if geography filter used)
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
        
        # Listing type filter
        if filters.listing_type is not None:
            query = query.where(Property.listing_type == filters.listing_type)
        
        # Listing status filter
        if filters.listing_status is not None:
            query = query.where(Property.listing_status == filters.listing_status)
        else:
            # Default: only show available properties
            query = query.where(Property.listing_status == ListingStatus.AVAILABLE)
        
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
            # Create point using WKTElement
            point = WKTElement(
                f'POINT({filters.longitude} {filters.latitude})', 
                srid=4326
            )
            
            # Create distance column for sorting
            distance_column = cast(
                ST_Distance(Location.geom, point) / 1000, 
                Float
            ).label('distance_km')
            
            # Filter within radius (ST_DWithin uses meters for Geography)
            query = query.where(
                ST_DWithin(
                    Location.geom,
                    point,
                    filters.radius_km * 1000  # Convert km to meters
                )
            )
        
        # Boolean amenity filters
        if filters.has_garden is not None:
            query = query.where(Property.has_garden == filters.has_garden)
        if filters.has_security is not None:
            query = query.where(Property.has_security == filters.has_security)
        if filters.has_swimming_pool is not None:
            query = query.where(Property.has_swimming_pool == filters.has_swimming_pool)
        
        # Parking filter
        if filters.parking_spaces is not None:
            query = query.where(Property.parking_spaces >= filters.parking_spaces)
        
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
            # Use column object (canonical), not string
            query = query.order_by(distance_column)
        else:
            # Default: recent first
            query = query.order_by(Property.created_at.desc())
        
        # Pagination
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
    ) -> List[Tuple[Property, float]]:  # More explicit type hint
        """
        Get properties near coordinates with distance.
        Returns list of (Property, distance_km) tuples sorted by distance.
        """
        # Create point using WKTElement
        point = WKTElement(f'POINT({longitude} {latitude})', srid=4326)
        
        # Query with distance calculation
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
        - NO phantom fields (is_published, square_meters don't exist)
        """
        # Validate location exists
        location_obj = db.get(Location, obj_in.location_id)
        if not location_obj:
            raise HTTPException(
                status_code=404,
                detail=f"Location with id={obj_in.location_id} not found"
            )
        
        # Validate property type exists
        property_type_obj = db.get(PropertyType, obj_in.property_type_id)
        if not property_type_obj:
            raise HTTPException(
                status_code=404,
                detail=f"Property type with id={obj_in.property_type_id} not found"
            )
        
        # Get clean data from Pydantic schema
        create_data = obj_in.model_dump(mode='python', exclude_unset=True)
        
        # Create property instance with validated data
        db_obj = Property(
            **create_data,  # Unpack all validated fields from schema
            user_id=user_id,  # From auth context (not from request body)
            is_verified=False,  # Must be verified by admin
            updated_by=created_by_supabase_id
            # Timestamps handled by DB DEFAULT now()
        )
        
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj
    
    
    # UPDATE OPERATIONS
        
    def update(
        self, 
        db: Session, 
        *, 
        db_obj: Property, 
        obj_in: PropertyUpdate,
        updated_by_supabase_id: Optional[str] = None
    ) -> Property:
        """
        Update a property.
        
        Rules:
        - Never update: property_id, user_id, created_at
        - Validate location_id and property_type_id if being changed
        - updated_at handled by DB trigger
        """
        update_data = obj_in.dict(exclude_unset=True)
        
        # Validate location if being changed
        if "location_id" in update_data and update_data["location_id"]:
            location_obj = db.get(Location, update_data["location_id"])
            if not location_obj:
                raise HTTPException(
                    status_code=404,
                    detail=f"Location with id={update_data['location_id']} not found"
                )
        
        # Validate property type if being changed
        if "property_type_id" in update_data and update_data["property_type_id"]:
            property_type_obj = db.get(PropertyType, update_data["property_type_id"])
            if not property_type_obj:
                raise HTTPException(
                    status_code=404,
                    detail=f"Property type with id={update_data['property_type_id']} not found"
                )
        
        # Remove protected fields
        protected_fields = {"property_id", "user_id", "created_at", "deleted_at"}
        for field in protected_fields:
            update_data.pop(field, None)
        
        # Apply updates
        for field, value in update_data.items():
            if hasattr(db_obj, field):
                setattr(db_obj, field, value)
        
        # Audit field
        if updated_by_supabase_id:
            db_obj.updated_by = updated_by_supabase_id
        # updated_at handled by DB trigger automatically
        
        db.add(db_obj)
        db.commit()
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
        """Update property listing status (e.g., available → sold).

        Returns:
        Property if found and updated, None if not found.
        Router should convert None to 404 HTTPException.
        """
        db_obj = self.get(db, property_id=property_id)
        if not db_obj:
            return None
        
        db_obj.listing_status = listing_status
        if updated_by_supabase_id:
            db_obj.updated_by = updated_by_supabase_id
        
        db.add(db_obj)
        db.commit()
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
        db.commit()
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
        db.commit()
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
        """
        Soft delete a property by setting deleted_at timestamp.
        Property data preserved for audit trail, relationships intact.
        """
        db_obj = self.get(db, property_id=property_id)
        if not db_obj:
            return None
        
        db_obj.deleted_at = datetime.now(timezone.utc)
        if deleted_by_supabase_id:
            db_obj.updated_by = deleted_by_supabase_id
        
        db.add(db_obj)
        db.commit()
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
        db.commit()
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
        db.commit()
        return db_obj
    
    
    # AUTHORIZATION HELPERS
        
    def can_modify_property(
        self,
        current_user_id: int,
        property_user_id: int,
        is_admin: bool = False
    ) -> bool:
        """
        Check if current user can modify a property.
        Rules: Owners can modify their properties, admins can modify any.
        """
        if is_admin:
            return True
        return current_user_id == property_user_id


# Singleton instance
property = PropertyCRUD()