# tests/conftest_no_mock.py
# tests/conftest_no_mock.py
"""
Conftest WITHOUT OAuth2 mock - to see the real error.
Copy this to tests/conftest.py temporarily to diagnose.
"""

import pytest
import uuid
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import os
os.environ["ENV"] = "test"  # Force test environment

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
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture(scope="function")
def agent_user(db):
    """
    Create an agent user for testing.
    """
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
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture(scope="function")
def admin_user(db):
    """
    Create an admin user for testing.
    """
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
    db.commit()
    db.refresh(user)
    return user


# Export fixtures
__all__ = ["db", "client", "normal_user", "agent_user", "admin_user"]