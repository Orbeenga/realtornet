# app/core/database.py
"""
RealtorNet Database Module - SQLAlchemy Engine & Session Management
Phase 2 Aligned: Psycopg 3, production connection pooling, edge-optimized
"""

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool

from app.core.config import settings
from app.models.base import Base


# Create production-ready SQLAlchemy engine optimized for international latency
engine = create_engine(
    settings.DATABASE_URI,  # Fixed: Use primary property name
    poolclass=QueuePool,
    pool_size=settings.DB_POOL_SIZE,  # Max persistent connections
    max_overflow=settings.DB_MAX_OVERFLOW,  # Max temporary connections
    pool_timeout=settings.DB_POOL_TIMEOUT,  # Seconds to wait for connection
    pool_recycle=settings.DB_POOL_RECYCLE,  # Recycle connections after 1 hour
    pool_pre_ping=True,  # Verify connections before using (edge-critical)
    echo=settings.DEBUG,  # SQL logging in debug mode
    # ✅ CONNECTION FIXES FOR NIGERIA -> US WEST
    connect_args={
        "connect_timeout": 30,  # 30s handshake allowance
        "keepalives": 1,
        "keepalives_idle": 30,
        "keepalives_interval": 10,
        "keepalives_count": 5,
        # Disable psycopg prepared statements so Supabase/Railway poolers
        # running in transaction mode don't trip DuplicatePreparedStatement.
        "prepare_threshold": None,
    }
)

# Create session factory (sync only - async removed per Option A)
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    class_=Session,
    expire_on_commit=False  # Prevent detached instance errors
)

# Register PostgreSQL session parameters for edge optimization
@event.listens_for(engine, "connect")
def set_pg_session_params(dbapi_conn, connection_record):
    """
    Set PostgreSQL session parameters for optimal performance.
    Called once per new connection.
    """
    with dbapi_conn.cursor() as cursor:
        # Set statement timeout to prevent long-running queries (30 seconds)
        cursor.execute("SET statement_timeout = '30s'")
        # Set timezone to UTC for consistency
        cursor.execute("SET TIME ZONE 'UTC'")
        # Cursor automatically closed by context manager


def get_db():
    """
    FastAPI dependency for database session management.
    
    Usage:
        @app.get("/users")
        def get_users(db: Session = Depends(get_db)):
            return db.query(User).all()
    
    Note: This is a SYNC generator (not async).
    All endpoint dependencies must be sync functions.
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def init_db() -> None:
    """
    Initialize database tables.
    
    WARNING: This should NEVER be used in production.
    Use Alembic migrations instead (Canonical Rule #7).
    
    This function exists only for testing purposes.
    """
    if settings.TESTING:
        Base.metadata.create_all(bind=engine)
    else:
        raise RuntimeError(
            "init_db() should not be called in production. "
            "Use Alembic migrations: 'alembic upgrade head'"
        )


def drop_db() -> None:
    """
    Drop all database tables.
    
    WARNING: Destructive operation. Only for testing.
    """
    if settings.TESTING:
        Base.metadata.drop_all(bind=engine)
    else:
        raise RuntimeError(
            "drop_db() should not be called in production. "
            "This operation is irreversible."
        )


# Export for convenience
__all__ = ["engine", "SessionLocal", "get_db", "init_db", "drop_db"]
