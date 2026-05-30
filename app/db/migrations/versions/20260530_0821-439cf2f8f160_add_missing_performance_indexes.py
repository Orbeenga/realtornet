# app/db/migrations/script.py.mako
"""add_missing_performance_indexes

Revision ID: 439cf2f8f160
Revises: 49e4e5adc1c7
Create Date: 2026-05-30 08:21:04.330079

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '439cf2f8f160'
down_revision: Union[str, None] = '49e4e5adc1c7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Deployment reminder: PR descriptions must name this migration file, and
# production deploy order is `alembic upgrade head` before application code.

def upgrade() -> None:
    """Add missing performance indexes."""
    # properties
    op.execute("CREATE INDEX IF NOT EXISTS idx_properties_price ON properties(price) WHERE deleted_at IS NULL")
    op.execute("CREATE INDEX IF NOT EXISTS idx_properties_bedrooms ON properties(bedrooms) WHERE deleted_at IS NULL")
    op.execute("CREATE INDEX IF NOT EXISTS idx_properties_listing_type ON properties(listing_type) WHERE deleted_at IS NULL")
    op.execute("CREATE INDEX IF NOT EXISTS idx_properties_listing_status ON properties(listing_status) WHERE deleted_at IS NULL")
    op.execute("CREATE INDEX IF NOT EXISTS idx_properties_location_id ON properties(location_id) WHERE deleted_at IS NULL")
    op.execute("CREATE INDEX IF NOT EXISTS idx_properties_user_id ON properties(user_id) WHERE deleted_at IS NULL")
    op.execute("CREATE INDEX IF NOT EXISTS idx_properties_created_at ON properties(created_at DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_properties_property_type_id ON properties(property_type_id) WHERE deleted_at IS NULL")

    # locations
    op.execute("CREATE INDEX IF NOT EXISTS idx_locations_city ON locations(city)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_locations_state ON locations(state)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_locations_state_city ON locations(state, city)")

    # reviews
    op.execute("CREATE INDEX IF NOT EXISTS idx_reviews_agent_id ON reviews(agent_id) WHERE deleted_at IS NULL")
    op.execute("CREATE INDEX IF NOT EXISTS idx_reviews_user_id ON reviews(user_id) WHERE deleted_at IS NULL")
    op.execute("CREATE INDEX IF NOT EXISTS idx_reviews_property_id ON reviews(property_id) WHERE deleted_at IS NULL")
    op.execute("CREATE INDEX IF NOT EXISTS idx_reviews_rating ON reviews(rating)")

    # favorites
    op.execute("CREATE INDEX IF NOT EXISTS idx_favorites_user_id ON favorites(user_id) WHERE deleted_at IS NULL")
    op.execute("CREATE INDEX IF NOT EXISTS idx_favorites_property_id ON favorites(property_id) WHERE deleted_at IS NULL")

    # inquiries
    op.execute("CREATE INDEX IF NOT EXISTS idx_inquiries_property_id ON inquiries(property_id) WHERE deleted_at IS NULL")
    op.execute("CREATE INDEX IF NOT EXISTS idx_inquiries_user_id ON inquiries(user_id) WHERE deleted_at IS NULL")

    # property_types
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS property_types_name_key ON property_types(name)")

    # property_images
    op.execute("CREATE INDEX IF NOT EXISTS idx_property_images_property_id ON property_images(property_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_property_images_is_primary ON property_images(property_id, is_primary)")


def downgrade() -> None:
    """Drop added performance indexes."""
    # property_images
    op.execute("DROP INDEX IF EXISTS idx_property_images_is_primary")
    op.execute("DROP INDEX IF EXISTS idx_property_images_property_id")

    # property_types
    op.execute("DROP INDEX IF EXISTS property_types_name_key")

    # inquiries
    op.execute("DROP INDEX IF EXISTS idx_inquiries_user_id")
    op.execute("DROP INDEX IF EXISTS idx_inquiries_property_id")

    # favorites
    op.execute("DROP INDEX IF EXISTS idx_favorites_property_id")
    op.execute("DROP INDEX IF EXISTS idx_favorites_user_id")

    # reviews
    op.execute("DROP INDEX IF EXISTS idx_reviews_rating")
    op.execute("DROP INDEX IF EXISTS idx_reviews_property_id")
    op.execute("DROP INDEX IF EXISTS idx_reviews_user_id")
    op.execute("DROP INDEX IF EXISTS idx_reviews_agent_id")

    # locations
    op.execute("DROP INDEX IF EXISTS idx_locations_state_city")
    op.execute("DROP INDEX IF EXISTS idx_locations_state")
    op.execute("DROP INDEX IF EXISTS idx_locations_city")

    # properties
    op.execute("DROP INDEX IF EXISTS idx_properties_property_type_id")
    op.execute("DROP INDEX IF EXISTS idx_properties_created_at")
    op.execute("DROP INDEX IF EXISTS idx_properties_user_id")
    op.execute("DROP INDEX IF EXISTS idx_properties_location_id")
    op.execute("DROP INDEX IF EXISTS idx_properties_listing_status")
    op.execute("DROP INDEX IF EXISTS idx_properties_listing_type")
    op.execute("DROP INDEX IF EXISTS idx_properties_bedrooms")
    op.execute("DROP INDEX IF EXISTS idx_properties_price")
