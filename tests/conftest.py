# tests/conftest_no_mock.py
"""
Conftest WITHOUT OAuth2 mock - to see the real error.
Copy this to tests/conftest.py temporarily to diagnose.
"""

import pytest
import uuid
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from sqlalchemy import text

import os
os.environ["ENV"] = "test"  # Force test environment

from app.core.config import settings
from app.core.database import Base, get_db
from app.main import app
from app.models.users import User, UserRole
from app.core.security import get_password_hash
from app.models.properties import Property
from app.models.property_types import PropertyType  # Is it in property_types.py?
from app.models.locations import Location
from app.models.users import User


# ✅ FORCE LOCAL POSTGRESQL FOR TESTS
TEST_SQLALCHEMY_DATABASE_URL = "postgresql+psycopg://postgres:postgres@localhost:5432/testdb"
print(f"Using test database URL: {TEST_SQLALCHEMY_DATABASE_URL}")

# Create engine with local PostgreSQL (simpler config)
engine = create_engine(
    TEST_SQLALCHEMY_DATABASE_URL,
    pool_pre_ping=True,
    echo=False  # Set to True to see SQL queries
)

# Inside your db fixture, before Base.metadata.create_all:
with engine.connect() as conn:
    conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis;"))

# 2. Create the Listing Type Enum if it doesn't exist
    conn.execute(text("""
        DO $$ BEGIN
            CREATE TYPE listing_type_enum AS ENUM ('sale', 'rent', 'lease');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """))
    
# 3. Create the Listing Status Enum if it doesn't exist
    conn.execute(text("""
        DO $$ BEGIN
            CREATE TYPE listing_status_enum AS ENUM ('available', 'active', 'pending', 'sold', 'rented', 'unavailable');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """))

# 4. Create the Profile Status Enum
    conn.execute(text("""
        DO $$ BEGIN
            CREATE TYPE profile_status_enum AS ENUM ('active', 'inactive', 'pending');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """))

    conn.commit()


TestingSessionLocal = sessionmaker(autocommit=False, autoflush=True, bind=engine)

"""
# Create test database
TEST_SQLALCHEMY_DATABASE_URL = settings.TEST_DATABASE_URI
print(f"Using test database URL: {TEST_SQLALCHEMY_DATABASE_URL}")

# Create engine with connection optimizations for Supabase
engine = create_engine(
    TEST_SQLALCHEMY_DATABASE_URL,
    connect_args={
        "connect_timeout": 30,
        "keepalives": 1,
        "keepalives_idle": 30,
        "keepalives_interval": 10,
        "keepalives_count": 5
    }
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
"""

@pytest.fixture(scope="function")
def db():
    """
    Create a fresh PostgreSQL test database for each test.
    Uses transactions for proper isolation without dropping tables.
    """
    # Create tables once at module level (not per test)
    Base.metadata.create_all(bind=engine)
    
    connection = engine.connect()
    transaction = connection.begin()
    db = TestingSessionLocal(bind=connection)
    
    try:
        yield db
    except Exception as e:
        print(f"Test error: {e}")
        raise
    finally:
        db.close()
        transaction.rollback()  # Rolls back all changes from this test
        connection.close()


@pytest.fixture(scope="function")
def client(db):
    """
    Create a test client with test database override.
    """
    def override_get_db():
        db.flush()  # Ensure fixture data is visible before app queries
        try:
            yield db
        finally:
            pass
    
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def normal_user(db):
    """Create a normal seeker user for testing."""
    password_hash = get_password_hash("password")
    user = User(
        email="user@example.com",
        password_hash=password_hash,
        first_name="Test",
        last_name="User",
        phone_number="+1234567890",
        user_role=UserRole.SEEKER,
        is_verified=False,
        supabase_id=uuid.uuid4(),
    )
    db.add(user)
    db.flush()    # ✅ CHANGED from db.commit()
    db.refresh(user)
    return user

@pytest.fixture(scope="function")
def agent_user(db):
    """Create an agent user for testing."""
    password_hash = get_password_hash("password")
    user = User(
        email="agent@example.com",
        password_hash=password_hash,
        first_name="Test",
        last_name="Agent",
        phone_number="+1234567891",
        user_role=UserRole.AGENT,
        is_verified=True,
        supabase_id=uuid.uuid4(),
    )
    db.add(user)
    db.flush()    # ✅ CHANGED from db.commit()
    db.refresh(user)
    return user

@pytest.fixture(scope="function")
def admin_user(db):
    """Create an admin user for testing."""
    password_hash = get_password_hash("password")
    user = User(
        email="admin@example.com",
        password_hash=password_hash,
        first_name="Test",
        last_name="Admin",
        phone_number="+1234567892",
        user_role=UserRole.ADMIN,
        is_verified=True,
        is_admin=True,
        supabase_id=uuid.uuid4(),
    )
    db.add(user)
    db.flush()    # ✅ CHANGED from db.commit()
    db.refresh(user)
    return user

@pytest.fixture
def property_type(db: Session):
    """Property type for tests"""
    from app.models.property_types import PropertyType
    prop_type = PropertyType(name="Apartment", description="Modern apartment")
    db.add(prop_type)
    db.flush()
    db.refresh(prop_type)
    return prop_type

@pytest.fixture
def location(db: Session):
    """Location for tests"""
    from app.models.locations import Location
    from geoalchemy2.elements import WKTElement
    
    loc = Location(
        state="Lagos",
        city="Ikeja", 
        neighborhood="Allen",
        geom=WKTElement('POINT(3.3488 6.6018)', srid=4326),
        is_active=True
    )
    db.add(loc)
    db.flush()
    db.refresh(loc)
    return loc

@pytest.fixture
def location_lekki(db: Session):
    """Alternative location"""
    from app.models.locations import Location
    from geoalchemy2.elements import WKTElement
    
    loc = Location(
        state="Lagos",
        city="Lekki",
        neighborhood="Phase 1", 
        geom=WKTElement('POINT(3.4746 6.4474)', srid=4326),
        is_active=True
    )
    db.add(loc)
    db.flush()
    db.refresh(loc)
    return loc

@pytest.fixture
def property_type_villa(db: Session):
    """Villa property type"""
    from app.models.property_types import PropertyType
    prop_type = PropertyType(name="Villa", description="Luxury villa")
    db.add(prop_type)
    db.flush()
    db.refresh(prop_type)
    return prop_type

@pytest.fixture
def sample_property(db: Session, normal_user, location, property_type):
    """Single property for basic tests"""
    from app.crud.properties import property as property_crud
    from app.schemas.properties import PropertyCreate
    
    prop_in = PropertyCreate(
        title="Beautiful 3BR Apartment",
        description="Spacious apartment in prime location",
        price=50000000,
        price_currency="NGN",
        bedrooms=3,
        bathrooms=2,
        property_size=150.5,
        property_type_id=property_type.property_type_id,
        listing_type="sale",
        location_id=location.location_id,
        year_built=2020,
        parking_spaces=2,
        has_garden=True,
        has_security=True,
        has_swimming_pool=False
    )
    
    return property_crud.create(db, obj_in=prop_in, user_id=normal_user.user_id)

@pytest.fixture
def multiple_properties(db: Session, normal_user, agent_user, location, location_lekki, property_type, property_type_villa):
    """Multiple properties for filter/search tests"""
    from app.models.properties import Property, ListingType, ListingStatus
    from geoalchemy2.elements import WKTElement
    
    properties = []
    
    # Property 1: Cheap apartment for sale
    prop1 = Property(
        title="Affordable 2BR Apartment",
        description="Budget-friendly apartment",
        user_id=normal_user.user_id,
        property_type_id=property_type.property_type_id,
        location_id=location.location_id,
        geom=WKTElement('POINT(3.3488 6.6018)', srid=4326),
        price=25000000,
        bedrooms=2,
        bathrooms=1,
        property_size=80.0,
        listing_type=ListingType.sale,
        listing_status=ListingStatus.available,
        is_featured=False,
        year_built=2018
    )
    db.add(prop1)
    properties.append(prop1)
    
    # Property 2: Mid-range apartment for rent
    prop2 = Property(
        title="Modern 3BR for Rent",
        description="Well-furnished apartment",
        user_id=normal_user.user_id,
        property_type_id=property_type.property_type_id,
        location_id=location.location_id,
        geom=WKTElement('POINT(3.3488 6.6018)', srid=4326),
        price=45000000,
        bedrooms=3,
        bathrooms=2,
        property_size=120.0,
        listing_type=ListingType.rent,
        listing_status=ListingStatus.available,
        is_featured=True,
        year_built=2021
    )
    db.add(prop2)
    properties.append(prop2)
    
    # Property 3: Luxury villa for sale
    prop3 = Property(
        title="Luxury 5BR Villa",
        description="Premium villa with pool",
        user_id=agent_user.user_id,
        property_type_id=property_type_villa.property_type_id,
        location_id=location_lekki.location_id,
        geom=WKTElement('POINT(3.4746 6.4474)', srid=4326),
        price=150000000,
        bedrooms=5,
        bathrooms=4,
        property_size=350.0,
        listing_type=ListingType.sale,
        listing_status=ListingStatus.available,
        is_featured=True,
        is_verified=True,
        year_built=2022,
        has_swimming_pool=True
    )
    db.add(prop3)
    properties.append(prop3)
    
    # Property 4: Sold property
    prop4 = Property(
        title="Sold 4BR House",
        description="Recently sold property",
        user_id=agent_user.user_id,
        property_type_id=property_type.property_type_id,
        location_id=location.location_id,
        geom=WKTElement('POINT(3.3488 6.6018)', srid=4326),
        price=80000000,
        bedrooms=4,
        bathrooms=3,
        property_size=200.0,
        listing_type=ListingType.sale,
        listing_status=ListingStatus.sold,
        year_built=2019
    )
    db.add(prop4)
    properties.append(prop4)
    
    db.flush()
    for prop in properties:
        db.refresh(prop)
    
    return properties


# Export fixtures
__all__ = [
    "db", 
    "client", 
    "normal_user", 
    "agent_user", 
    "admin_user",
    "property_type",
    "location",
    "location_lekki",
    "property_type_villa",
    "sample_property",
    "multiple_properties"
]