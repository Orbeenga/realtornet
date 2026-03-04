# app/utils/geospatial.py
"""
Geospatial utility functions for RealtorNet
Canonical compliant: Uses Geography(POINT, 4326) for all spatial operations
"""

from typing import Tuple, Dict, Optional
import math
import re
from shapely.geometry import Point, Polygon
from sqlalchemy import func
from sqlalchemy.orm import Query
from geoalchemy2.functions import ST_DWithin

# Constants
EARTH_RADIUS_KM = 6371.0  # Earth's radius in kilometers
MILES_TO_KM = 1.60934  # Conversion factor from miles to kilometers


def get_distance_between_points(
    lat1: float, lon1: float, lat2: float, lon2: float, unit: str = "km"
) -> float:
    """
    Calculate the distance between two points using the Haversine formula
    
    Args:
        lat1: Latitude of point 1
        lon1: Longitude of point 1
        lat2: Latitude of point 2
        lon2: Longitude of point 2
        unit: Unit of distance ('km' for kilometers, 'mi' for miles)
        
    Returns:
        Distance between the points in the specified unit
    """
    # Convert latitude and longitude from degrees to radians
    lat1_rad = math.radians(lat1)
    lon1_rad = math.radians(lon1)
    lat2_rad = math.radians(lat2)
    lon2_rad = math.radians(lon2)
    
    # Difference in coordinates
    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad
    
    # Haversine formula
    a = math.sin(dlat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    distance = EARTH_RADIUS_KM * c
    
    # Convert to miles if requested
    if unit.lower() == "mi":
        distance = distance / MILES_TO_KM
        
    return distance


def create_point_geometry(latitude: float, longitude: float) -> Point:
    """
    Create a Shapely Point geometry from coordinates
    Note: Shapely uses (lon, lat) order per GeoJSON spec
    """
    return Point(longitude, latitude)


def create_polygon_from_bounds(
    min_lat: float, min_lon: float, max_lat: float, max_lon: float
) -> Polygon:
    """
    Create a polygon from bounding box coordinates
    """
    return Polygon([
        (min_lon, min_lat),
        (max_lon, min_lat),
        (max_lon, max_lat),
        (min_lon, max_lat),
        (min_lon, min_lat)
    ])


def get_properties_within_radius(
    query: Query, 
    location_column, 
    latitude: float, 
    longitude: float, 
    radius_miles: float
) -> Query:
    """
    Filter SQLAlchemy query to find properties within a given radius
    
    Args:
        query: SQLAlchemy query object
        location_column: The geography column to filter on (e.g., Property.geom)
        latitude: Center point latitude
        longitude: Center point longitude
        radius_miles: Search radius in miles
        
    Returns:
        Filtered query object
    """
    # Convert miles to meters (PostgreSQL ST_DWithin uses meters)
    radius_meters = radius_miles * MILES_TO_KM * 1000
    
    # Create the point to search around
    # IMPORTANT: Geography uses (lon, lat) order
    point = func.ST_SetSRID(func.ST_MakePoint(longitude, latitude), 4326)
    
    # Add the distance filter to the query
    return query.filter(ST_DWithin(
        location_column, 
        point,
        radius_meters,
        use_spheroid=True  # Use spherical calculations for accuracy
    ))


def calculate_bounding_box(
    latitude: float, longitude: float, distance_km: float
) -> Dict[str, float]:
    """
    Calculate a bounding box given a center point and distance
    
    Args:
        latitude: Center point latitude
        longitude: Center point longitude
        distance_km: Distance from center in kilometers
        
    Returns:
        Dictionary with min/max lat/lon values
    """
    # Angular distance in radians on a great circle
    rad_dist = distance_km / EARTH_RADIUS_KM
    
    # Latitude bounds
    min_lat = latitude - math.degrees(rad_dist)
    max_lat = latitude + math.degrees(rad_dist)
    
    # Longitude bounds (handle poles specially)
    cos_lat = math.cos(math.radians(latitude))
    
    if abs(cos_lat) < 0.0001:  # At or very near poles
        delta_lon = 180.0  # Box spans all longitudes
    else:
        asin_arg = math.sin(rad_dist) / cos_lat
        
        if abs(asin_arg) >= 1.0:  # Box spans all longitudes at this latitude
            delta_lon = 180.0
        else:
            delta_lon = math.degrees(math.asin(asin_arg))
    
    min_lon = longitude - delta_lon
    max_lon = longitude + delta_lon
    
    # Clamp to valid coordinate ranges
    return {
        "min_lat": max(-90.0, min_lat),    # ✅ Clamp to >= -90
        "max_lat": min(90.0, max_lat),     # ✅ Clamp to <= 90
        "min_lon": max(-180.0, min_lon),   # ✅ Clamp to >= -180
        "max_lon": min(180.0, max_lon)     # ✅ Clamp to <= 180
    }


def coords_to_wkt(longitude: float, latitude: float) -> str:
    """
    Convert coordinates to WKT POINT string for database insertion.
    
    Args:
        longitude: Longitude value
        latitude: Latitude value
        
    Returns:
        WKT string in format "POINT(lon lat)"
        
    Example:
        >>> coords_to_wkt(3.3792, 6.5244)
        "POINT(3.3792 6.5244)"
    """
    return f"POINT({longitude} {latitude})"


def wkt_to_coords(wkt: str) -> Optional[Tuple[float, float]]:
    """
    Extract coordinates from WKT POINT string.
    
    Args:
        wkt: WKT string (e.g., "POINT(3.3792 6.5244)")
        
    Returns:
        Tuple of (longitude, latitude) or None if invalid
        
    Example:
        >>> wkt_to_coords("POINT(3.3792 6.5244)")
        (3.3792, 6.5244)
    """
    if not wkt:
        return None
        
    # Match "POINT(lon lat)" format with support for scientific notation
    # Pattern supports: 123, 123.456, -123.456, 1.23e2, 1.23E-2, etc.
    pattern = r'POINT\s*\(\s*([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)\s+([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)\s*\)'
    match = re.match(pattern, wkt, re.IGNORECASE)
    
    if match:
        longitude = float(match.group(1))
        latitude = float(match.group(2))
        return (longitude, latitude)
    
    return None


def validate_coordinates(latitude: float, longitude: float) -> bool:
    """
    Validate that coordinates are within valid ranges.
    
    Args:
        latitude: Latitude value
        longitude: Longitude value
        
    Returns:
        True if valid, False otherwise
    """
    return -90 <= latitude <= 90 and -180 <= longitude <= 180


def validate_wkt_point(wkt: str) -> bool:
    """
    Validate WKT POINT string format and coordinate ranges.
    
    Args:
        wkt: WKT string to validate
        
    Returns:
        True if valid, False otherwise
    """
    coords = wkt_to_coords(wkt)
    if coords is None:
        return False
    
    longitude, latitude = coords
    return validate_coordinates(latitude, longitude)


# Export all functions
__all__ = [
    "get_distance_between_points",
    "create_point_geometry",
    "create_polygon_from_bounds",
    "get_properties_within_radius",
    "calculate_bounding_box",
    "coords_to_wkt",
    "wkt_to_coords",
    "validate_coordinates",
    "validate_wkt_point",
]