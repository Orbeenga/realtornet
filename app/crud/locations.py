# app/crud/locations.py
"""
Location CRUD operations - 100% aligned to DB schema with PostGIS.
DB Table: locations (PK: location_id)
Canonical Rules: Geography(POINT, 4326), no manual timestamps, proper WKT handling
"""

from typing import List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import select, func, and_, update
from geoalchemy2.functions import ST_DWithin, ST_Distance
from geoalchemy2.elements import WKTElement

from app.models.locations import Location
from app.schemas.locations import LocationCreate, LocationUpdate


class LocationCRUD:
    """CRUD operations for Location model - DB-first canonical implementation"""
    
    
    # READ OPERATIONS
        
    def get(self, db: Session, location_id: int) -> Optional[Location]:
        """Get a location by location_id (PK)"""
        return db.get(Location, location_id)
    
    def get_multi(
        self, 
        db: Session, 
        *, 
        skip: int = 0, 
        limit: int = 100,
        include_inactive: bool = False
    ) -> List[Location]:
        """Get multiple locations with pagination and optional deleted filter"""
        query = select(Location)

        # Apply deleted filter
        if not include_inactive:
            query = query.where(Location.deleted_at.is_(None))

        # Pagination
        query = query.offset(skip).limit(limit)
        return db.execute(query).scalars().all()


    def get_by_filters(
        self, 
        db: Session, 
        *, 
        state: Optional[str] = None, 
        city: Optional[str] = None, 
        neighborhood: Optional[str] = None, 
        skip: int = 0, 
        limit: int = 100
    ) -> List[Location]:
        """Get locations filtered by geographic attributes"""
        query = select(Location)
    
        # Location filters only
        if state:
            query = query.where(Location.state == state)
        if city:
            query = query.where(Location.city == city)
        if neighborhood:
            query = query.where(Location.neighborhood == neighborhood)
    
        query = query.offset(skip).limit(limit)
        return db.execute(query).scalars().all()
    
    def get_by_coordinates(
        self, 
        db: Session, 
        *, 
        latitude: float, 
        longitude: float, 
        radius_km: float = 1.0,
        skip: int = 0,
        limit: int = 100
    ) -> List[Location]:
        """
        Get locations within radius of coordinates using PostGIS Geography.
        
        Args:
            latitude: Latitude in decimal degrees
            longitude: Longitude in decimal degrees
            radius_km: Search radius in kilometers
            
        Returns:
            List of locations within radius, ordered by distance
        """
        # Create point using WKTElement for Geography type
        # CRITICAL: WKTElement with srid=4326 and type_=Geography
        point = WKTElement(f'POINT({longitude} {latitude})', srid=4326)
        
        # Query using ST_DWithin (Geography version - uses meters)
        query = select(Location).where(
            and_(
                Location.geom.isnot(None),
                ST_DWithin(
                    Location.geom,
                    point,
                    radius_km * 1000  # Convert km to meters
                )
            )
        ).order_by(
            ST_Distance(Location.geom, point)  # Order by distance
        ).offset(skip).limit(limit)
        
        return db.execute(query).scalars().all()
    
    def get_nearest(
        self,
        db: Session,
        *,
        latitude: float,
        longitude: float,
        limit: int = 10
    ) -> List[Tuple[Location, float]]:
        """
        Get nearest locations to coordinates with distance in km.
        
        Returns:
            List of tuples: (Location, distance_km)
        """
        point = WKTElement(f'POINT({longitude} {latitude})', srid=4326)
        
        # Query with distance calculation
        query = select(
            Location,
            ST_Distance(Location.geom, point).label('distance')
        ).where(
            Location.geom.isnot(None)
        ).order_by(
            'distance'
        ).limit(limit)
        
        results = db.execute(query).all()
        
        # Convert distance from meters to km and return as tuples
        return [(location, distance / 1000.0) for location, distance in results]
    
    
    # LOOKUP / AGGREGATION OPERATIONS
        
    def get_states(self, db: Session) -> List[str]:
        """Get all unique states (sorted alphabetically)"""
        results = db.execute(
            select(Location.state).distinct().order_by(Location.state)
        ).scalars().all()
        return list(results)
    
    def get_cities(
        self, 
        db: Session, 
        *, 
        state: Optional[str] = None
    ) -> List[str]:
        """Get all unique cities, optionally filtered by state"""
        query = select(Location.city).distinct()
        
        if state:
            query = query.where(Location.state == state)
        
        query = query.order_by(Location.city)
        
        results = db.execute(query).scalars().all()
        return list(results)
    
    def get_neighborhoods(
        self, 
        db: Session, 
        *, 
        state: Optional[str] = None, 
        city: Optional[str] = None
    ) -> List[str]:
        """Get all unique neighborhoods, optionally filtered by state/city"""
        query = select(Location.neighborhood).distinct().where(
            Location.neighborhood.isnot(None)
        )
        
        if state:
            query = query.where(Location.state == state)
        if city:
            query = query.where(Location.city == city)
        
        query = query.order_by(Location.neighborhood)
        
        results = db.execute(query).scalars().all()
        return list(results)
    
    def search_locations(
        self,
        db: Session,
        *,
        search_term: str,
        skip: int = 0,
        limit: int = 100
    ) -> List[Location]:
        """Search locations by state, city, or neighborhood"""
        search_pattern = f"%{search_term}%"
        
        query = select(Location).where(
            Location.state.ilike(search_pattern) |
            Location.city.ilike(search_pattern) |
            Location.neighborhood.ilike(search_pattern)
        ).offset(skip).limit(limit)
        
        return db.execute(query).scalars().all()
    
    
    # CREATE OPERATIONS
        
    def create(
        self, 
        db: Session, 
        *, 
        obj_in: LocationCreate
    ) -> Location:
        """
        Create a new location.
        
        CRITICAL:
        - If lat/lon provided, create Geography point using WKTElement
        - NO manual timestamp setting (DB handles via DEFAULT now())
        - Geography type uses POINT(longitude latitude) order (X Y)
        """
        create_data = obj_in.dict(exclude_unset=True, exclude={'latitude', 'longitude'})
        
        # Create location object
        db_obj = Location(
            state=create_data["state"],
            city=create_data["city"],
            neighborhood=create_data.get("neighborhood"),
        )
        
        # Handle geography point if coordinates provided
        if obj_in.latitude is not None and obj_in.longitude is not None:
            # CRITICAL: Use WKTElement with Geography type
            # Format: POINT(longitude latitude) - note X Y order!
            wkt_point = f'POINT({obj_in.longitude} {obj_in.latitude})'
            db_obj.geom = WKTElement(wkt_point, srid=4326)
        
        db.add(db_obj)
        db.flush()
        db.refresh(db_obj)
        return db_obj
    
    
    # UPDATE OPERATIONS
        
    def update(
        self, 
        db: Session, 
        *, 
        db_obj: Location, 
        obj_in: LocationUpdate,
        updated_by: Optional[str] = None
    ) -> Location:
        """
        Update a location.
        
        Rules:
        - Never update: location_id, created_at
        - Handle geography updates properly via WKTElement
        - updated_at and updated_by handled here (no DB trigger assumed)
        """
        update_data = obj_in.dict(exclude_unset=True)
        
        # Extract lat/lon for geography handling
        latitude = update_data.pop("latitude", None)
        longitude = update_data.pop("longitude", None)
        
        # Remove protected fields
        protected_fields = {"location_id", "created_at", "is_active"}
        for field in protected_fields:
            update_data.pop(field, None)
        
        # Apply text field updates
        for field, value in update_data.items():
            if hasattr(db_obj, field) and field != "geom":
                setattr(db_obj, field, value)
        
        # Handle geography update if coordinates provided
        if latitude is not None and longitude is not None:
            wkt_point = f'POINT({longitude} {latitude})'
            db_obj.geom = WKTElement(wkt_point, srid=4326)
        
        # Audit fields
        if updated_by:
            db_obj.updated_by = updated_by
        # updated_at handled by DB trigger automatically
        
        db.add(db_obj)
        db.flush()
        db.refresh(db_obj)
        return db_obj
    
    
    # DELETE OPERATIONS
    
    def soft_delete(
        self,
        db: Session,
        *,
        location_id: int,
        deleted_by_supabase_id: Optional[str] = None
    ) -> Optional[Location]:
        """
        Soft delete a location.
        Sets deleted_at and deleted_by.
        """
        stmt = (
            update(Location)
            .where(
                Location.location_id == location_id,
                Location.deleted_at.is_(None)
            )
            .values(
                deleted_at=func.now(),
                deleted_by=deleted_by_supabase_id
            )
        )
        db.execute(stmt)
        db.flush()
        return db.get(Location, location_id)

    def deactivate(self, db: Session, *, location_id: int) -> Optional[Location]:
        """Deprecated alias for soft_delete()."""
        return self.soft_delete(db, location_id=location_id)
    
    
    # UTILITY METHODS
        
    def get_or_create(
        self,
        db: Session,
        *,
        state: str,
        city: str,
        neighborhood: Optional[str] = None,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None
    ) -> Location:
        """
        Get existing location or create if doesn't exist.
        Useful for property creation workflows to avoid duplicate locations.
        """
        # Try to find existing location
        query = select(Location).where(
            and_(
                Location.state == state,
                Location.city == city,
                Location.neighborhood == neighborhood if neighborhood else Location.neighborhood.is_(None)
            )
        )
        
        existing = db.execute(query).scalar_one_or_none()
        if existing:
            return existing
        
        # Create new location
        location_data = LocationCreate(
            state=state,
            city=city,
            neighborhood=neighborhood,
            latitude=latitude,
            longitude=longitude
        )
        
        return self.create(
            db, 
            obj_in=location_data
        )


# Singleton instance
location = LocationCRUD()
