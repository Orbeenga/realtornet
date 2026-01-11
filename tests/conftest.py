# tests/conftest.py
"""
Pytest configuration and fixtures for RealtorNet tests.
Provides test database, client, and user fixtures.
"""

import pytest
import uuid
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.core.database import Base, get_db
from app.main import app
from app.models.users import User, UserRole
from app.core.security import get_password_hash


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


@pytest.fixture(scope="function")
def db():
    """
    Create a fresh PostgreSQL test database for each test.
    Uses create_all/drop_all for test isolation (acceptable for tests).
    """
    try:
        Base.metadata.create_all(bind=engine)
        db = TestingSessionLocal()
        yield db
    except Exception as e:
        print(f"Database connection error: {e}")
        raise
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db):
    """
    Create a test client with test database override.
    """
    def override_get_db():
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
    """
    Create a normal seeker user for testing.
    """
    user = User(
        email="user@example.com",
        password_hash=get_password_hash("password"),
        first_name="Test",
        last_name="User",
        phone_number="+1234567890",
        user_role=UserRole.SEEKER,  # Fixed: Use SEEKER instead of USER
        is_verified=False,
        supabase_id=uuid.uuid4(),  # Fixed: Added required field
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture(scope="function")
def agent_user(db):
    """
    Create an agent user for testing.
    """
    user = User(
        email="agent@example.com",
        password_hash=get_password_hash("password"),
        first_name="Test",
        last_name="Agent",
        phone_number="+1234567891",
        user_role=UserRole.AGENT,
        is_verified=True,
        supabase_id=uuid.uuid4(),  # Fixed: Added required field
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture(scope="function")
def admin_user(db):
    """
    Create an admin user for testing.
    """
    user = User(
        email="admin@example.com",
        password_hash=get_password_hash("password"),
        first_name="Test",
        last_name="Admin",
        phone_number="+1234567892",
        user_role=UserRole.ADMIN,
        is_verified=True,
        is_admin=True,
        supabase_id=uuid.uuid4(),  # Fixed: Added required field
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


# Export fixtures
__all__ = ["db", "client", "normal_user", "agent_user", "admin_user"]