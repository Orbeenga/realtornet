# app/db/migrations/script.py.mako
"""add_application_analytics_views

Revision ID: 3cf0979df4e8
Revises: 388601679a8b
Create Date: 2026-03-15 13:45:42.251961

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '3cf0979df4e8'
down_revision: Union[str, None] = '388601679a8b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(
        """
        CREATE OR REPLACE VIEW active_properties AS
        SELECT p.property_id, p.title, p.description, p.user_id,
               p.property_type_id, p.location_id, p.geom, p.price,
               p.price_currency, p.bedrooms, p.bathrooms, p.property_size,
               p.is_featured, p.listing_type, p.listing_status,
               p.is_verified, p.verification_date, p.created_at,
               p.updated_at, p.updated_by, p.deleted_at,
               l.state, l.city, l.neighborhood,
               pt.name AS property_type_name,
               (u.first_name::text || ' ' || u.last_name::text) AS owner_name,
               u.email AS owner_email,
               (SELECT count(*) FROM property_images pi
                WHERE pi.property_id = p.property_id) AS image_count,
               (SELECT count(*) FROM property_amenities pa
                WHERE pa.property_id = p.property_id) AS amenity_count,
               (SELECT count(*) FROM reviews r
                WHERE r.property_id = p.property_id
                AND r.deleted_at IS NULL) AS review_count,
               (SELECT avg(r.rating) FROM reviews r
                WHERE r.property_id = p.property_id
                AND r.deleted_at IS NULL) AS avg_rating
        FROM properties p
        LEFT JOIN locations l ON p.location_id = l.location_id
        LEFT JOIN property_types pt ON p.property_type_id = pt.property_type_id
        LEFT JOIN users u ON p.user_id = u.user_id
        WHERE p.deleted_at IS NULL
        """
    )

    op.execute(
        """
        CREATE OR REPLACE VIEW agent_performance AS
        SELECT u.user_id,
               (u.first_name::text || ' ' || u.last_name::text) AS agent_name,
               ap.license_number,
               a.name AS agency_name,
               (SELECT count(*) FROM properties p
                WHERE p.user_id = u.user_id
                AND p.deleted_at IS NULL) AS total_listings,
               (SELECT count(*) FROM properties p
                WHERE p.user_id = u.user_id
                AND p.listing_status IN ('available', 'active')
                AND p.deleted_at IS NULL) AS active_listings,
               (SELECT count(*) FROM properties p
                WHERE p.user_id = u.user_id
                AND p.listing_status = 'sold'
                AND p.deleted_at IS NULL) AS sold_count,
               (SELECT avg(r.rating) FROM reviews r
                WHERE r.agent_id = u.user_id
                AND r.deleted_at IS NULL) AS avg_rating,
               (SELECT count(*) FROM reviews r
                WHERE r.agent_id = u.user_id
                AND r.deleted_at IS NULL) AS review_count
        FROM users u
        JOIN agent_profiles ap ON u.user_id = ap.user_id
        LEFT JOIN agencies a ON ap.agency_id = a.agency_id
        WHERE u.user_role = 'agent'
        """
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP VIEW IF EXISTS agent_performance;")
    op.execute("DROP VIEW IF EXISTS active_properties;")
