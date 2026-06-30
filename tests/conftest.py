# tests/conftest.py
"""
Test configuration - Full conftest with property API fixtures.
"""

import pytest
import uuid
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import cast
from uuid import UUID

import os
os.environ["ENV"] = "test"
os.environ["SENTRY_DSN"] = ""  # Disable Sentry during tests to prevent test errors leaking to production
os.environ["ADMIN_NOTIFICATION_EMAIL"] = "admin_test@realtornet.test"

from app.core.config import settings
from app.core.database import get_db
from app.main import app
from app.models.users import User, UserRole
from app.core.security import get_password_hash, generate_access_token
from app.models.properties import Property, ListingType, ListingStatus, ModerationStatus
from app.models.listing_events import ListingEvent
from app.models.property_types import PropertyType
from app.models.locations import Location
from app.models.agencies import Agency
from app.models.agency_join_requests import AgencyAgentMembership, AgencyJoinRequest, AgencyMembershipReviewRequest
from app.models.agent_membership_audit import AgentMembershipAudit
from app.models.listing_instructions import ListingInstruction
from app.models.notifications import Notification
from app.models.review_requests import ReviewRequest
from app.crud.properties import property as property_crud
from app.schemas.properties import PropertyCreate


# ---------------------------------------------------------------------------
# Engine setup
# ---------------------------------------------------------------------------

TEST_SQLALCHEMY_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://postgres:postgres@localhost:5432/testdb"
)

engine = create_engine(
    TEST_SQLALCHEMY_DATABASE_URL,
    pool_pre_ping=True,
    echo=False
)

with engine.connect() as conn:
    conn.execute(text("SELECT 1"))  # verify connectivity only

# ---------------------------------------------------------------------------
# Schema setup (session-scoped — runs once before all tests)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session", autouse=True)
def setup_test_schema():
    """Schema is managed by Alembic migrations. This fixture is intentionally
    a no-op when running against a pre-migrated database."""
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))



# ---------------------------------------------------------------------------
# Core fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="function")
def db():
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture(scope="function")
def client(db):
    def override_get_db():
        db.flush()
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# User fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="function")
def normal_user(db):
    user = User(
        email="user@example.com",
        password_hash=get_password_hash("password"),
        first_name="Test",
        last_name="User",
        phone_number="+1234567890",
        user_role=UserRole.SEEKER,
        is_verified=False,
        supabase_id=uuid.uuid4(),
    )
    db.add(user)
    db.flush()
    db.refresh(user)
    return user


@pytest.fixture(scope="function")
def agent_user(db, agency):
    """Agent user — belongs to the default agency."""
    user = User(
        email="agent@example.com",
        password_hash=get_password_hash("password"),
        first_name="Test",
        last_name="Agent",
        phone_number="+1234567891",
        user_role=UserRole.AGENT,
        is_verified=True,
        supabase_id=uuid.uuid4(),
        agency_id=agency.agency_id,
    )
    db.add(user)
    db.flush()
    db.refresh(user)
    return user


@pytest.fixture(scope="function")
def agency_owner_user(db, agency):
    """Agency owner user — belongs to the default agency."""
    user = User(
        email="agency_owner@example.com",
        password_hash=get_password_hash("password"),
        first_name="Agency",
        last_name="Owner",
        phone_number="+1234567893",
        user_role=UserRole.AGENCY_OWNER,
        is_verified=True,
        supabase_id=uuid.uuid4(),
        agency_id=agency.agency_id,
    )
    db.add(user)
    db.flush()
    db.refresh(user)
    return user


@pytest.fixture(scope="function")
def admin_user(db):
    user = User(
        email="admin@example.com",
        password_hash=get_password_hash("password"),
        first_name="Test",
        last_name="Admin",
        phone_number="+1234567892",
        user_role=UserRole.ADMIN,
        is_verified=True,
        is_admin=True,
        supabase_id=uuid.uuid4(),
    )
    db.add(user)
    db.flush()
    db.refresh(user)
    return user


# ---------------------------------------------------------------------------
# Token header fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def normal_user_token_headers(normal_user):
    token = generate_access_token(
        supabase_id=normal_user.supabase_id,
        user_id=normal_user.user_id,
        user_role=normal_user.user_role.value,
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def agent_token_headers(agent_user):
    token = generate_access_token(
        supabase_id=agent_user.supabase_id,
        user_id=agent_user.user_id,
        user_role=agent_user.user_role.value,
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def agency_owner_token_headers(agency_owner_user):
    token = generate_access_token(
        supabase_id=agency_owner_user.supabase_id,
        user_id=agency_owner_user.user_id,
        user_role=agency_owner_user.user_role.value,
        agency_id=agency_owner_user.agency_id,
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def owner_token_headers(agent_user):
    """Same user as agent_user — used in ownership checks."""
    token = generate_access_token(
        supabase_id=agent_user.supabase_id,
        user_id=agent_user.user_id,
        user_role=agent_user.user_role.value,
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def admin_token_headers(admin_user):
    token = generate_access_token(
        supabase_id=admin_user.supabase_id,
        user_id=admin_user.user_id,
        user_role=admin_user.user_role.value,
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def agent_no_agency_token_headers(db, client):
    """Agent whose agency_id is None — triggers the 400 branch in create_property."""
    user = User(
        email="agent_no_agency@example.com",
        password_hash=get_password_hash("password"),
        first_name="NoAgency",
        last_name="Agent",
        phone_number="+9990000001",
        user_role=UserRole.AGENT,
        is_verified=True,
        supabase_id=uuid.uuid4(),
        agency_id=None,
    )
    db.add(user)
    db.flush()
    db.refresh(user)
    token = generate_access_token(
        user_id=cast(int, user.user_id),
        supabase_id=cast(UUID, user.supabase_id),
        user_role=user.user_role.value,
    )
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Agency fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def agency(db):
    ag = Agency(name="Test Agency")
    db.add(ag)
    db.flush()
    db.refresh(ag)
    return ag


@pytest.fixture
def other_agency(db):
    ag = Agency(name="Other Agency")
    db.add(ag)
    db.flush()
    db.refresh(ag)
    return ag


# ---------------------------------------------------------------------------
# Location fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def location(db):
    from geoalchemy2.elements import WKTElement
    loc = Location(
        state="Lagos",
        city="Ikeja",
        neighborhood="Allen",
        geom=WKTElement('POINT(3.3488 6.6018)', srid=4326),
        is_active=True,
    )
    db.add(loc)
    db.flush()
    db.refresh(loc)
    return loc


@pytest.fixture
def location_lekki(db):
    from geoalchemy2.elements import WKTElement
    loc = Location(
        state="Lagos",
        city="Lekki",
        neighborhood="Phase 1",
        geom=WKTElement('POINT(3.4746 6.4474)', srid=4326),
        is_active=True,
    )
    db.add(loc)
    db.flush()
    db.refresh(loc)
    return loc


# ---------------------------------------------------------------------------
# Property type fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def property_type(db):
    from app.models.property_types import PropertyType
    return db.query(PropertyType).filter_by(name="Apartment").first()


@pytest.fixture
def property_type_villa(db):
    pt = PropertyType(name="Test Villa Type", description="Luxury villa")
    db.add(pt)
    db.flush()
    db.refresh(pt)
    return pt


# ---------------------------------------------------------------------------
# Property payload fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def property_create_payload(location, property_type, agency):
    return {
        "title": "Test Property",
        "description": "A test listing",
        "price": 5000000,
        "bedrooms": 3,
        "bathrooms": 2.0,
        "location_id": location.location_id,
        "property_type_id": property_type.property_type_id,
        "listing_type": "sale",
        "listing_status": "available",
        "agency_id": agency.agency_id,
    }


@pytest.fixture
def property_create_payload_other_agency(property_create_payload, other_agency):
    return {**property_create_payload, "agency_id": other_agency.agency_id}


@pytest.fixture
def property_update_payload():
    return {"title": "Updated Title", "price": 6000000}


# ---------------------------------------------------------------------------
# Property object fixtures
# ---------------------------------------------------------------------------

def _make_property(db, user_id, location, property_type, agency, title, is_verified):
    """Internal helper — avoids repeating PropertyCreate boilerplate."""
    obj_in = PropertyCreate(
        title=title,
        description="Auto-generated test property",
        price=5000000,
        bedrooms=3,
        bathrooms=2.0,
        location_id=location.location_id,
        property_type_id=property_type.property_type_id,
        listing_type="sale",
        listing_status="available",
        agency_id=agency.agency_id,
    )
    prop = property_crud.create_with_owner(db, obj_in=obj_in, user_id=user_id)
    prop.is_verified = is_verified
    db.flush()
    db.refresh(prop)
    return prop


@pytest.fixture
def verified_property(db, agent_user, location, property_type, agency):
    return _make_property(db, agent_user.user_id, location, property_type, agency,
                          title="Verified Property", is_verified=True)


@pytest.fixture
def unverified_property(db, agent_user, location, property_type, agency):
    return _make_property(db, agent_user.user_id, location, property_type, agency,
                          title="Unverified Property", is_verified=False)


@pytest.fixture
def unverified_property_owned_by_agent(db, agent_user, location, property_type, agency):
    """Owned by agent_user — same principal as owner_token_headers."""
    return _make_property(db, agent_user.user_id, location, property_type, agency,
                          title="Agent Owned Unverified", is_verified=False)


@pytest.fixture
def agency_approved_property(db, agent_user, location, property_type, agency):
    """Listing at agency_approved status — ready for admin verification."""
    prop = _make_property(db, agent_user.user_id, location, property_type, agency,
                          title="Agency Approved Property", is_verified=False)
    prop.moderation_status = ModerationStatus.agency_approved
    db.flush()
    db.refresh(prop)
    return prop


@pytest.fixture
def unverified_property_owned_by_agency_owner(db, agency_owner_user, location, property_type, agency):
    """Owned by agency_owner_user — for testing owner-specific agency transitions."""
    return _make_property(db, agency_owner_user.user_id, location, property_type, agency,
                          title="Agency Owner Owned Unverified", is_verified=False)


# ---------------------------------------------------------------------------
# sample_property + multiple_properties (existing, preserved)
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_property(db, normal_user, location, property_type):
    from app.schemas.properties import PropertyCreate as PC
    prop_in = PC(
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
        has_swimming_pool=False,
    )
    return property_crud.create(db, obj_in=prop_in, user_id=normal_user.user_id)


@pytest.fixture
def multiple_properties(db, normal_user, agent_user, location, location_lekki,
                        property_type, property_type_villa):
    from geoalchemy2.elements import WKTElement

    props = []

    prop1 = Property(
        title="Affordable 2BR Apartment",
        description="Budget-friendly apartment",
        user_id=normal_user.user_id,
        property_type_id=property_type.property_type_id,
        location_id=location.location_id,
        geom=WKTElement('POINT(3.3488 6.6018)', srid=4326),
        price=25000000, bedrooms=2, bathrooms=1, property_size=80.0,
        listing_type=ListingType.sale, listing_status=ListingStatus.available,
        is_featured=False, year_built=2018,
    )
    prop2 = Property(
        title="Modern 3BR for Rent",
        description="Well-furnished apartment",
        user_id=normal_user.user_id,
        property_type_id=property_type.property_type_id,
        location_id=location.location_id,
        geom=WKTElement('POINT(3.3488 6.6018)', srid=4326),
        price=45000000, bedrooms=3, bathrooms=2, property_size=120.0,
        listing_type=ListingType.rent, listing_status=ListingStatus.available,
        is_featured=True, year_built=2021,
    )
    prop3 = Property(
        title="Luxury 5BR Villa",
        description="Premium villa with pool",
        user_id=agent_user.user_id,
        property_type_id=property_type_villa.property_type_id,
        location_id=location_lekki.location_id,
        geom=WKTElement('POINT(3.4746 6.4474)', srid=4326),
        price=150000000, bedrooms=5, bathrooms=4, property_size=350.0,
        listing_type=ListingType.sale, listing_status=ListingStatus.available,
        is_featured=True, is_verified=True, year_built=2022, has_swimming_pool=True,
    )
    prop4 = Property(
        title="Sold 4BR House",
        description="Recently sold property",
        user_id=agent_user.user_id,
        property_type_id=property_type.property_type_id,
        location_id=location.location_id,
        geom=WKTElement('POINT(3.3488 6.6018)', srid=4326),
        price=80000000, bedrooms=4, bathrooms=3, property_size=200.0,
        listing_type=ListingType.sale, listing_status=ListingStatus.sold,
        year_built=2019,
    )

    for p in [prop1, prop2, prop3, prop4]:
        db.add(p)
    db.flush()
    for p in [prop1, prop2, prop3, prop4]:
        db.refresh(p)
    props = [prop1, prop2, prop3, prop4]
    return props

from app.crud.property_images import property_image as property_image_crud
from app.schemas.property_images import PropertyImageCreate

@pytest.fixture
def sample_property_image(db, unverified_property_owned_by_agent):
    image_in = PropertyImageCreate(
        property_id=unverified_property_owned_by_agent.property_id,
        image_url="https://example.com/image1.jpg",
        caption="Test image", is_primary=True, display_order=1,
    )
    img = property_image_crud.create(db, obj_in=image_in)
    db.flush(); db.refresh(img)
    return img

@pytest.fixture
def second_property_image(db, unverified_property_owned_by_agent):
    image_in = PropertyImageCreate(
        property_id=unverified_property_owned_by_agent.property_id,
        image_url="https://example.com/image2.jpg",
        caption="Second image", is_primary=False, display_order=2,
    )
    img = property_image_crud.create(db, obj_in=image_in)
    db.flush(); db.refresh(img)
    return img

# ─── Amenity fixtures ──────────────────────────────────────────────────────

@pytest.fixture
def sample_amenity(db):
    from app.models.amenities import Amenity
    return db.query(Amenity).filter_by(name="Swimming Pool").first()


@pytest.fixture
def second_amenity(db):
    from app.models.amenities import Amenity
    return db.query(Amenity).filter_by(name="Gym").first()


@pytest.fixture
def property_with_amenity(db, unverified_property_owned_by_agent, sample_amenity):
    """
    Property that already has sample_amenity associated.
    Uses Table.insert() directly — property_amenities is a Table, not a Model.
    """
    from app.models.property_amenities import property_amenities as pa_table
    db.execute(
        pa_table.insert().values(
            property_id=unverified_property_owned_by_agent.property_id,
            amenity_id=sample_amenity.amenity_id,
        )
    )
    db.flush()
    return unverified_property_owned_by_agent


# ─── Property type fixtures ────────────────────────────────────────────────

@pytest.fixture
def sample_property_type(db):
    """
    A fresh PropertyType not used by any property.
    Safe to query, update. Do NOT use for delete tests — use unused_property_type.
    """
    from app.models.property_types import PropertyType
    pt = PropertyType(name="Studio Flat", description="Compact studio unit")
    db.add(pt)
    db.flush()
    db.refresh(pt)
    return pt


@pytest.fixture
def second_property_type(db):
    """Second PropertyType for duplicate-name conflict tests."""
    from app.models.property_types import PropertyType
    pt = PropertyType(name="Test Duplex B", description="Two-floor connected unit")
    db.add(pt)
    db.flush()
    db.refresh(pt)
    return pt


@pytest.fixture
def unused_property_type(db):
    """
    PropertyType with zero properties — safe to hard-delete in tests.
    Always use this (not sample_property_type) for delete endpoint tests.
    """
    from app.models.property_types import PropertyType
    pt = PropertyType(name="Temporary Test Type", description="Created for delete test")
    db.add(pt)
    db.flush()
    db.refresh(pt)
    return pt
