# app/db/migrations/env.py
"""
Alembic migration environment for RealtorNet.
Handles both online and offline migrations with proper configuration.
"""

from logging.config import fileConfig
from sqlalchemy import create_engine, pool
from alembic import context
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

# Import project configuration and models
from app.core.config import settings
from app.models.base import Base  # Fixed: Correct import path

# Import all models to ensure they're registered with Base.metadata
# This is critical for autogenerate to detect all tables
from app.models.users import User
from app.models.profiles import Profile
from app.models.properties import Property
from app.models.locations import Location
from app.models.agencies import Agency
from app.models.agent_profiles import AgentProfile
from app.models.property_types import PropertyType
from app.models.property_images import PropertyImage
from app.models.amenities import Amenity
from app.models.property_amenities import property_amenities
from app.models.reviews import Review
from app.models.inquiries import Inquiry
from app.models.favorites import Favorite
from app.models.saved_searches import SavedSearch

# Optional: Import view models if they need migrations
# from app.models.analytics import ActivePropertiesView, AgentPerformanceView

# Alembic configuration object
config = context.config

# Apply logging configuration from alembic.ini
if config.config_file_name:
    fileConfig(config.config_file_name)

# Target metadata for autogeneration
# This contains all table definitions from imported models
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """
    Run migrations in 'offline' mode.
    
    This configures the context with just a URL and not an Engine.
    Calls to context.execute() emit the given string to the script output.
    
    Used for generating SQL scripts without database connection.
    """
    # Use DATABASE_URL from environment or fall back to settings
    url = os.getenv("DATABASE_URL") or settings.DATABASE_URI
    
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        # Enhanced autogenerate configuration
        compare_type=True,              # Detect column type changes
        compare_server_default=True,    # Detect default value changes
        include_schemas=False,          # Don't include schema in table names
    )
    
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """
    Run migrations in 'online' mode.
    
    In this scenario we create an Engine and associate a connection with context.
    This is the standard mode for applying migrations to a live database.
    """
    # Use DATABASE_URL from environment or fall back to settings
    url = os.getenv("DATABASE_URL") or settings.DATABASE_URI
    
    # Create engine with NullPool to avoid connection pooling issues during migrations
    # NullPool closes connections immediately after use
    connectable = create_engine(
        url,
        poolclass=pool.NullPool,
        # Optional: Add connection arguments for Supabase if needed
        # connect_args={
        #     "connect_timeout": 30,
        #     "options": "-c timezone=utc"
        # }
    )
    
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            # Enhanced autogenerate configuration
            compare_type=True,              # Detect column type changes
            compare_server_default=True,    # Detect default value changes
            include_schemas=False,          # Don't include schema in table names
            # Optional: Add render_item function for custom rendering
            # render_as_batch=False,        # Not needed for PostgreSQL
        )
        
        with context.begin_transaction():
            context.run_migrations()


# Determine migration mode and execute
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
