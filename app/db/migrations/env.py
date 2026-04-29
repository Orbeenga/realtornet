# app/db/migrations/env.py
"""
Alembic migration environment for RealtorNet.
Handles both online and offline migrations with proper configuration.
"""

from logging.config import fileConfig
from sqlalchemy import create_engine, pool, text
from alembic import context
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

# Import project configuration and models
from app.core.config import settings
from app.models.base import Base

# Import all models to ensure they're registered with Base.metadata
from app.models.users import User
from app.models.profiles import Profile
from app.models.properties import Property
from app.models.locations import Location
from app.models.agencies import Agency
from app.models.agency_join_requests import AgencyAgentMembership, AgencyJoinRequest, AgencyMembershipReviewRequest
from app.models.agent_profiles import AgentProfile
from app.models.property_types import PropertyType
from app.models.property_images import PropertyImage
from app.models.amenities import Amenity
from app.models.property_amenities import property_amenities
from app.models.reviews import Review
from app.models.inquiries import Inquiry
from app.models.favorites import Favorite
from app.models.saved_searches import SavedSearch

# Import PostGIS types for custom rendering
from geoalchemy2 import Geography

# Optional: Import view models if they need migrations
# from app.models.analytics import ActivePropertiesView, AgentPerformanceView

# Alembic configuration object
config = context.config

# Apply logging configuration from alembic.ini
if config.config_file_name:
    fileConfig(config.config_file_name)

# Target metadata for autogeneration
target_metadata = Base.metadata


def render_item(type_, obj, autogen_context):
    """
    Custom renderer for types that Alembic doesn't recognize natively.
    
    Handles:
    - PostGIS Geography types (prevents "Did not recognize type 'extensions.geography'" warnings)
    """
    # Handle PostGIS Geography type
    if type_ == "type" and isinstance(obj, Geography):
        # Render as Geography with proper parameters
        geom_type = getattr(obj, 'geometry_type', 'POINT')
        srid = getattr(obj, 'srid', 4326)
        return f"Geography(geometry_type='{geom_type}', srid={srid})"
    
    # Return False for default rendering
    return False


def include_object(object, name, type_, reflected, compare_to):
    """
    Filter function to exclude objects from autogenerate.
    
    Excludes:
    - Tables in 'auth' schema (managed by Supabase)
    - Tables in 'storage' schema (managed by Supabase)
    - PostGIS spatial_ref_sys table (system table)
    - Foreign keys pointing to auth.users (cross-schema references)
    - Legacy Supabase index naming (idx_* and *_active_idx patterns)
    - Legacy Supabase FK naming (*_fkey pattern)
    - alembic_version table (managed by Alembic itself)
    
    This prevents cosmetic diffs between Supabase-managed schema and SQLAlchemy conventions.
    """
    # Skip alembic_version table (Alembic manages this internally)
    if type_ == "table" and name == "alembic_version":
        return False
    
    # Skip legacy Supabase index naming patterns
    # Supabase uses: idx_*, *_active_idx, *_unique_idx
    # SQLAlchemy uses: ix_*
    # These are functionally identical, just different naming conventions
    if type_ == "index" and name:
        if name.startswith("idx_") or name.endswith("_active_idx") or name.endswith("_unique_idx"):
            return False
    
    # Skip legacy Supabase FK naming pattern
    # Supabase uses: tablename_columnname_fkey
    # SQLAlchemy uses: fk_tablename_columnname_reftable (via naming_convention)
    # These are functionally identical, just different naming conventions
    if type_ == "foreign_key_constraint" and name:
        if name.endswith("_fkey"):
            return False
    
    # Skip unique constraints that are actually handled by unique indexes
    # Prevents duplicate constraint detection
    if type_ == "unique_constraint" and name:
        if name.endswith("_key"):
            return False
    
    # Skip any FK constraint pointing to auth schema (Supabase internal)
    if type_ == "foreign_key_constraint":
        if hasattr(object, 'elements') and len(object.elements) > 0:
            target_table = str(object.elements[0].column.table)
            if 'auth.users' in target_table or target_table.startswith('auth.'):
                return False
    
    # Exclude auth/storage schemas (Supabase internal)
    if hasattr(object, 'schema') and object.schema in ("auth", "storage"):
        return False
    
    # Exclude PostGIS system table
    if name == "spatial_ref_sys":
        return False
    
    return True


def run_migrations_offline() -> None:
    """
    Run migrations in 'offline' mode.
    
    This configures the context with just a URL and not an Engine.
    Used for generating SQL scripts without database connection.
    """
    url = os.getenv("DATABASE_URL") or settings.DATABASE_URI
    
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_object=include_object,
        render_item=render_item,           # Add custom type rendering
        compare_type=True,
        compare_server_default=True,
        include_schemas=False,
    )
    
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """
    Run migrations in 'online' mode.
    
    Creates an Engine and associates a connection with context.
    This is the standard mode for applying migrations to a live database.
    """
    url = os.getenv("DATABASE_URL") or settings.DATABASE_URI
    
    # Create engine with NullPool to avoid connection pooling during migrations
    connectable = create_engine(
        url,
        poolclass=pool.NullPool,
        connect_args={
             "connect_timeout": 30,
             "options": "-c timezone=utc -c search_path=public"
        }
    )
    
    with connectable.connect() as connection:
        # Explicitly set schema to public to prevent auth schema reflection
        connection.execute(text("SET search_path TO public"))
        connection.commit()
        
        context.configure(
            connection=connection,
            target_metadata=target_metadata,                                                      
            compare_type=True,
            compare_server_default=True,     # Detect default value changes
            include_schemas=False,           # Don't include schema in table names
            include_object=include_object,   # Tell Alembic to use your filter
            render_item=render_item,         # Add custom type rendering
            version_table_schema="public",
        )
        
        with context.begin_transaction():
            context.run_migrations()


# Determine migration mode and execute
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
