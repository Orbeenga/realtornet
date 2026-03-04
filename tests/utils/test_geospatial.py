# tests\utils\test_geospatial.py
"""
Geospatial utility tests - Canonical compliant
Tests all functions in app/utils/geospatial.py
Coverage target: app/utils/geospatial.py (currently 0%)
"""

import pytest
import math
from typing import Tuple
from shapely.geometry import Point, Polygon
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.utils.geospatial import (
    get_distance_between_points,
    create_point_geometry,
    create_polygon_from_bounds,
    get_properties_within_radius,
    calculate_bounding_box,
    coords_to_wkt,
    wkt_to_coords,
    validate_coordinates,
    validate_wkt_point,
    EARTH_RADIUS_KM,
    MILES_TO_KM
)
from app.models.properties import Property
from app.models.locations import Location
from app.models.property_types import PropertyType


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def property_type(db: Session):
    """Create a property type for testing"""
    prop_type = PropertyType(
        name="Test Apartment",
        description="Test property type for geospatial tests"
    )
    db.add(prop_type)
    db.commit()
    db.refresh(prop_type)
    return prop_type


# ============================================================================
# DISTANCE CALCULATION TESTS
# ============================================================================

class TestDistanceCalculations:
    """Test distance calculation functions"""
    
    def test_distance_same_point(self):
        """Test distance between same point is zero"""
        distance = get_distance_between_points(
            lat1=6.5244, lon1=3.3792,  # Lagos
            lat2=6.5244, lon2=3.3792,  # Same point
            unit="km"
        )
        
        assert distance == pytest.approx(0.0, abs=0.01)
    
    def test_distance_lagos_to_abuja_km(self):
        """Test distance from Lagos to Abuja in kilometers"""
        # Lagos: 6.5244°N, 3.3792°E
        # Abuja: 9.0765°N, 7.3986°E
        # Expected: ~526 km (great circle distance, not road distance)
        
        distance = get_distance_between_points(
            lat1=6.5244, lon1=3.3792,  # Lagos
            lat2=9.0765, lon2=7.3986,  # Abuja
            unit="km"
        )
        
        assert 500 < distance < 550
    
    def test_distance_lagos_to_abuja_miles(self):
        """Test distance from Lagos to Abuja in miles"""
        distance = get_distance_between_points(
            lat1=6.5244, lon1=3.3792,  # Lagos
            lat2=9.0765, lon2=7.3986,  # Abuja
            unit="mi"
        )
        
        # Should be ~327 miles (great circle)
        assert 310 < distance < 350
    
    def test_distance_across_equator(self):
        """Test distance calculation across equator"""
        distance = get_distance_between_points(
            lat1=-10.0, lon1=0.0,
            lat2=10.0, lon2=0.0,
            unit="km"
        )
        
        # ~20 degrees latitude = ~2220 km
        assert 2100 < distance < 2300
    
    def test_distance_small_values(self):
        """Test distance calculation with very small differences"""
        distance = get_distance_between_points(
            lat1=6.5244, lon1=3.3792,
            lat2=6.5245, lon2=3.3793,  # Very close
            unit="km"
        )
        
        assert distance < 0.2  # Less than 200 meters
    
    def test_distance_default_unit_km(self):
        """Test default unit is kilometers"""
        distance_km = get_distance_between_points(
            lat1=6.5244, lon1=3.3792,
            lat2=9.0765, lon2=7.3986
        )
        
        distance_default = get_distance_between_points(
            lat1=6.5244, lon1=3.3792,
            lat2=9.0765, lon2=7.3986,
            unit="km"
        )
        
        assert distance_km == distance_default
    
    def test_distance_case_insensitive_unit(self):
        """Test unit parameter is case-insensitive"""
        distance_km = get_distance_between_points(
            lat1=6.5244, lon1=3.3792,
            lat2=9.0765, lon2=7.3986,
            unit="KM"
        )
        
        distance_mi = get_distance_between_points(
            lat1=6.5244, lon1=3.3792,
            lat2=9.0765, lon2=7.3986,
            unit="MI"
        )
        
        assert distance_km > distance_mi  # km > miles for same distance


# ============================================================================
# GEOMETRY CREATION TESTS
# ============================================================================

class TestGeometryCreation:
    """Test geometry object creation"""
    
    def test_create_point_geometry(self):
        """Test creating a Shapely Point"""
        point = create_point_geometry(latitude=6.5244, longitude=3.3792)
        
        assert isinstance(point, Point)
        assert point.x == 3.3792  # longitude
        assert point.y == 6.5244  # latitude
    
    def test_create_point_negative_coords(self):
        """Test creating point with negative coordinates"""
        point = create_point_geometry(latitude=-33.8688, longitude=-151.2093)
        
        assert point.x == -151.2093
        assert point.y == -33.8688
    
    def test_create_point_zero_coords(self):
        """Test creating point at (0, 0)"""
        point = create_point_geometry(latitude=0.0, longitude=0.0)
        
        assert point.x == 0.0
        assert point.y == 0.0
    
    def test_create_polygon_from_bounds(self):
        """Test creating polygon from bounding box"""
        polygon = create_polygon_from_bounds(
            min_lat=6.4, min_lon=3.2,
            max_lat=6.6, max_lon=3.5
        )
        
        assert isinstance(polygon, Polygon)
        
        # Check bounds
        bounds = polygon.bounds  # (minx, miny, maxx, maxy)
        assert bounds[0] == 3.2   # min lon
        assert bounds[1] == 6.4   # min lat
        assert bounds[2] == 3.5   # max lon
        assert bounds[3] == 6.6   # max lat
    
    def test_create_polygon_vertices(self):
        """Test polygon has correct vertices"""
        polygon = create_polygon_from_bounds(
            min_lat=0.0, min_lon=0.0,
            max_lat=10.0, max_lon=10.0
        )
        
        # Should have 5 vertices (closed polygon)
        coords = list(polygon.exterior.coords)
        assert len(coords) == 5
        
        # First and last should be same (closed)
        assert coords[0] == coords[4]


# ============================================================================
# WKT CONVERSION TESTS
# ============================================================================

class TestWKTConversion:
    """Test WKT string conversion functions"""
    
    def test_coords_to_wkt_basic(self):
        """Test converting coordinates to WKT"""
        wkt = coords_to_wkt(longitude=3.3792, latitude=6.5244)
        
        assert wkt == "POINT(3.3792 6.5244)"
    
    def test_coords_to_wkt_negative(self):
        """Test WKT with negative coordinates"""
        wkt = coords_to_wkt(longitude=-122.4194, latitude=37.7749)
        
        assert wkt == "POINT(-122.4194 37.7749)"
    
    def test_coords_to_wkt_zero(self):
        """Test WKT at origin"""
        wkt = coords_to_wkt(longitude=0.0, latitude=0.0)
        
        assert wkt == "POINT(0.0 0.0)"
    
    def test_coords_to_wkt_integer_values(self):
        """Test WKT with integer coordinates"""
        wkt = coords_to_wkt(longitude=5, latitude=10)
        
        assert wkt == "POINT(5 10)"
    
    def test_wkt_to_coords_basic(self):
        """Test extracting coordinates from WKT"""
        coords = wkt_to_coords("POINT(3.3792 6.5244)")
        
        assert coords is not None
        assert coords[0] == pytest.approx(3.3792)
        assert coords[1] == pytest.approx(6.5244)
    
    def test_wkt_to_coords_negative(self):
        """Test WKT extraction with negative values"""
        coords = wkt_to_coords("POINT(-122.4194 37.7749)")
        
        assert coords == (-122.4194, 37.7749)
    
    def test_wkt_to_coords_extra_spaces(self):
        """Test WKT extraction handles extra spaces"""
        coords = wkt_to_coords("POINT(  3.3792   6.5244  )")
        
        assert coords == (3.3792, 6.5244)
    
    def test_wkt_to_coords_case_insensitive(self):
        """Test WKT extraction is case-insensitive"""
        coords1 = wkt_to_coords("POINT(3.3792 6.5244)")
        coords2 = wkt_to_coords("point(3.3792 6.5244)")
        coords3 = wkt_to_coords("Point(3.3792 6.5244)")
        
        assert coords1 == coords2 == coords3
    
    def test_wkt_to_coords_invalid_format(self):
        """Test WKT extraction returns None for invalid format"""
        assert wkt_to_coords("INVALID") is None
        assert wkt_to_coords("POINT(3.3792)") is None
        assert wkt_to_coords("LINE(3.3792 6.5244)") is None
        assert wkt_to_coords("") is None
    
    def test_wkt_to_coords_none_input(self):
        """Test WKT extraction handles None input"""
        assert wkt_to_coords(None) is None
    
    def test_wkt_to_coords_integer_values(self):
        """Test WKT extraction with integer coordinates"""
        coords = wkt_to_coords("POINT(5 10)")
        
        assert coords == (5.0, 10.0)
    
    def test_wkt_roundtrip(self):
        """Test converting coords to WKT and back"""
        original_lon, original_lat = 3.3792, 6.5244
        
        wkt = coords_to_wkt(longitude=original_lon, latitude=original_lat)
        lon, lat = wkt_to_coords(wkt)
        
        assert lon == pytest.approx(original_lon)
        assert lat == pytest.approx(original_lat)


# ============================================================================
# COORDINATE VALIDATION TESTS
# ============================================================================

class TestCoordinateValidation:
    """Test coordinate validation functions"""
    
    def test_validate_coordinates_valid(self):
        """Test valid coordinates pass validation"""
        assert validate_coordinates(latitude=6.5244, longitude=3.3792) is True
        assert validate_coordinates(latitude=0.0, longitude=0.0) is True
        assert validate_coordinates(latitude=90.0, longitude=180.0) is True
        assert validate_coordinates(latitude=-90.0, longitude=-180.0) is True
    
    def test_validate_coordinates_latitude_too_high(self):
        """Test latitude above 90 fails"""
        assert validate_coordinates(latitude=91.0, longitude=0.0) is False
        assert validate_coordinates(latitude=100.0, longitude=0.0) is False
    
    def test_validate_coordinates_latitude_too_low(self):
        """Test latitude below -90 fails"""
        assert validate_coordinates(latitude=-91.0, longitude=0.0) is False
        assert validate_coordinates(latitude=-100.0, longitude=0.0) is False
    
    def test_validate_coordinates_longitude_too_high(self):
        """Test longitude above 180 fails"""
        assert validate_coordinates(latitude=0.0, longitude=181.0) is False
        assert validate_coordinates(latitude=0.0, longitude=200.0) is False
    
    def test_validate_coordinates_longitude_too_low(self):
        """Test longitude below -180 fails"""
        assert validate_coordinates(latitude=0.0, longitude=-181.0) is False
        assert validate_coordinates(latitude=0.0, longitude=-200.0) is False
    
    def test_validate_coordinates_both_invalid(self):
        """Test both coordinates invalid"""
        assert validate_coordinates(latitude=100.0, longitude=200.0) is False
    
    def test_validate_wkt_point_valid(self):
        """Test valid WKT points pass validation"""
        assert validate_wkt_point("POINT(3.3792 6.5244)") is True
        assert validate_wkt_point("POINT(0 0)") is True
        assert validate_wkt_point("POINT(-180 -90)") is True
        assert validate_wkt_point("POINT(180 90)") is True
    
    def test_validate_wkt_point_invalid_coords(self):
        """Test WKT with invalid coordinates fails"""
        assert validate_wkt_point("POINT(200 100)") is False
        assert validate_wkt_point("POINT(0 100)") is False
        assert validate_wkt_point("POINT(200 0)") is False
    
    def test_validate_wkt_point_invalid_format(self):
        """Test invalid WKT format fails"""
        assert validate_wkt_point("INVALID") is False
        assert validate_wkt_point("POINT(3.3792)") is False
        assert validate_wkt_point("") is False


# ============================================================================
# BOUNDING BOX TESTS
# ============================================================================

class TestBoundingBox:
    """Test bounding box calculation"""
    
    def test_calculate_bounding_box_basic(self):
        """Test calculating bounding box"""
        bbox = calculate_bounding_box(
            latitude=6.5244,
            longitude=3.3792,
            distance_km=10.0
        )
        
        assert "min_lat" in bbox
        assert "max_lat" in bbox
        assert "min_lon" in bbox
        assert "max_lon" in bbox
        
        # Center should be within bounds
        assert bbox["min_lat"] < 6.5244 < bbox["max_lat"]
        assert bbox["min_lon"] < 3.3792 < bbox["max_lon"]
    
    def test_calculate_bounding_box_symmetry(self):
        """Test bounding box is roughly symmetric around center"""
        bbox = calculate_bounding_box(
            latitude=0.0,
            longitude=0.0,
            distance_km=10.0
        )
        
        # At equator, should be symmetric
        lat_delta = bbox["max_lat"] - 0.0
        assert abs(lat_delta - (0.0 - bbox["min_lat"])) < 0.01
    
    def test_calculate_bounding_box_near_pole(self):
        """Test bounding box near north pole is clamped"""
        bbox = calculate_bounding_box(
            latitude=89.0,
            longitude=0.0,
            distance_km=150.0  # ✅ Distance crosses pole boundary
        )
        
        # Max lat should be clamped at 90
        assert bbox["max_lat"] == 90.0
    
    def test_calculate_bounding_box_near_south_pole(self):
        """Test bounding box near south pole is clamped"""
        bbox = calculate_bounding_box(
            latitude=-89.0,
            longitude=0.0,
            distance_km=150.0  # ✅ Distance crosses pole boundary
        )
        
        # Min lat should be clamped at -90
        assert bbox["min_lat"] == -90.0
    
    def test_calculate_bounding_box_longitude_wraparound(self):
        """Test bounding box near dateline is clamped"""
        bbox = calculate_bounding_box(
            latitude=0.0,
            longitude=179.0,
            distance_km=150.0  # ✅ Distance crosses dateline
        )
        
        # Max lon should be clamped at 180
        assert bbox["max_lon"] == 180.0
    
    def test_calculate_bounding_box_small_distance(self):
        """Test bounding box with very small distance"""
        bbox = calculate_bounding_box(
            latitude=6.5244,
            longitude=3.3792,
            distance_km=1.0
        )
        
        # Bounds should be close to center
        assert abs(bbox["max_lat"] - 6.5244) < 0.1
        assert abs(bbox["min_lat"] - 6.5244) < 0.1
    
    def test_calculate_bounding_box_large_distance(self):
        """Test bounding box with large distance"""
        bbox = calculate_bounding_box(
            latitude=0.0,
            longitude=0.0,
            distance_km=1000.0
        )
        
        # Bounds should be far from center
        assert abs(bbox["max_lat"] - 0.0) > 5.0
        assert abs(bbox["min_lat"] - 0.0) > 5.0

# ============================================================================
# CONSTANTS TESTS
# ============================================================================

class TestConstants:
    """Test module constants are correctly defined"""
    
    def test_earth_radius_constant(self):
        """Test Earth radius constant is reasonable"""
        assert 6300 < EARTH_RADIUS_KM < 6400
        assert EARTH_RADIUS_KM == 6371.0
    
    def test_miles_to_km_constant(self):
        """Test miles to km conversion constant"""
        assert 1.6 < MILES_TO_KM < 1.65
        assert MILES_TO_KM == 1.60934
    
    def test_conversion_consistency(self):
        """Test conversion constant is used correctly"""
        km_distance = 100.0
        mi_distance = km_distance / MILES_TO_KM
        
        assert 60 < mi_distance < 65  # ~62 miles


# ============================================================================
# INTEGRATION TEST (requires database)
# ============================================================================

class TestPropertiesWithinRadius:
    """Test spatial query function (integration test)"""
    
    @pytest.fixture
    def sample_location(self, db: Session):
        """Create a test location"""
        from geoalchemy2.elements import WKTElement
        
        loc = Location(
            state="Lagos",
            city="Ikeja",
            neighborhood="Test",
            geom=WKTElement('POINT(3.3488 6.6018)', srid=4326),
            is_active=True
        )
        db.add(loc)
        db.commit()
        db.refresh(loc)
        return loc
    
    @pytest.fixture
    def nearby_property(self, db: Session, normal_user, sample_location, property_type):
        """Create a property at known location"""
        from geoalchemy2.elements import WKTElement
        from app.models.properties import ListingType, ListingStatus
        
        prop = Property(
            title="Nearby Property",
            description="Test property",
            user_id=normal_user.user_id,
            property_type_id=property_type.property_type_id,
            location_id=sample_location.location_id,
            price=50000000,
            listing_type=ListingType.sale,
            listing_status=ListingStatus.available,
            geom=WKTElement('POINT(3.3500 6.6020)', srid=4326)  # ~1 km away
        )
        db.add(prop)
        db.commit()
        db.refresh(prop)
        return prop
    
    def test_get_properties_within_radius_basic(
        self, db: Session, nearby_property, sample_location
    ):
        """Test finding properties within radius"""
        from sqlalchemy import select
        
        # Start with base query
        query = select(Property).where(Property.deleted_at.is_(None))
        
        # Add radius filter (5 miles should include nearby_property)
        filtered_query = get_properties_within_radius(
            query=query,
            location_column=Property.geom,
            latitude=6.6018,  # Center point
            longitude=3.3488,
            radius_miles=5.0
        )
        
        # Execute
        results = db.execute(filtered_query).scalars().all()
        
        # Should find the nearby property
        prop_ids = [p.property_id for p in results]
        assert nearby_property.property_id in prop_ids
    
    def test_get_properties_within_radius_exclude_far(
        self, db: Session, nearby_property
    ):
        """Test properties outside radius are excluded"""
        from sqlalchemy import select
        
        query = select(Property).where(Property.deleted_at.is_(None))
        
        # Use very small radius (0.1 miles) from far away point
        filtered_query = get_properties_within_radius(
            query=query,
            location_column=Property.geom,
            latitude=9.0765,  # Abuja (far away)
            longitude=7.3986,
            radius_miles=0.1
        )
        
        results = db.execute(filtered_query).scalars().all()
        
        # Should NOT find the Lagos property
        prop_ids = [p.property_id for p in results]
        assert nearby_property.property_id not in prop_ids


# ============================================================================
# EDGE CASES & ERROR HANDLING
# ============================================================================

class TestEdgeCases:
    """Test edge cases and boundary conditions"""
    
    def test_distance_antipodal_points(self):
        """Test distance between antipodal points (opposite sides of Earth)"""
        # Should be close to half Earth's circumference
        distance = get_distance_between_points(
            lat1=0.0, lon1=0.0,
            lat2=0.0, lon2=180.0,
            unit="km"
        )
        
        # Half circumference at equator ≈ 20,037 km
        assert 19000 < distance < 21000
    
    def test_wkt_with_scientific_notation(self):
        """Test WKT extraction handles scientific notation"""
        coords = wkt_to_coords("POINT(1.23e2 4.56e1)")
        
        assert coords == (123.0, 45.6)
    
    def test_validate_coordinates_boundary_values(self):
        """Test validation at exact boundaries"""
        assert validate_coordinates(90.0, 180.0) is True
        assert validate_coordinates(-90.0, -180.0) is True
        assert validate_coordinates(90.0, -180.0) is True
        assert validate_coordinates(-90.0, 180.0) is True
    
    def test_coords_to_wkt_high_precision(self):
        """Test WKT creation preserves precision"""
        wkt = coords_to_wkt(
            longitude=3.379234567890123,
            latitude=6.524456789012345
        )
        
        assert "3.379234567890123" in wkt
        assert "6.524456789012345" in wkt