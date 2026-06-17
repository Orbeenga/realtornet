"""Check what migrations have been applied on staging."""
import os
from sqlalchemy import create_engine, text

engine = create_engine(os.environ["DB_URL"])
with engine.connect() as conn:
    # Check applied migrations
    result = conn.execute(text("SELECT version_num FROM alembic_version"))
    row = result.fetchone()
    print(f"Alembic version: {row[0]}")

    # Check listing_events table
    result = conn.execute(
        text("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'listing_events')")
    )
    print(f"listing_events exists: {result.fetchone()[0]}")

    # Check listing_instructions table
    result = conn.execute(
        text("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'listing_instructions')")
    )
    print(f"listing_instructions exists: {result.fetchone()[0]}")

    # Check columns in properties table
    result = conn.execute(
        text("SELECT column_name FROM information_schema.columns WHERE table_name = 'properties' ORDER BY ordinal_position")
    )
    cols = [row[0] for row in result]
    print(f"Properties columns ({len(cols)}): {', '.join(cols)}")
