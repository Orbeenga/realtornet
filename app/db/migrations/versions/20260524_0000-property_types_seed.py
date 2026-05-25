"""Seed all 12 property types for Phase K

Revision ID: 20260524_0000
Revises: 20260508_0900-a9d1f3c7b482_add_property_location_name
Create Date: 2026-05-24 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20260524_0000'
down_revision = 'a9d1f3c7b482'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Seed all 12 property types"""
    # Create a table to hold the seed data
    connection = op.get_bind()

    property_types = [
        {"name": "Apartment", "description": "Multi-unit residential property or unit within a building"},
        {"name": "House", "description": "Single-family residential home"},
        {"name": "Bungalow", "description": "Single-story residential dwelling"},
        {"name": "Duplex", "description": "Two-unit residential property"},
        {"name": "Condo", "description": "Condominium unit with shared ownership"},
        {"name": "Townhouse", "description": "Multi-story residential unit in a row"},
        {"name": "Land", "description": "Vacant land or undeveloped property"},
        {"name": "Commercial", "description": "Commercial business property"},
        {"name": "Office", "description": "Office space or office building"},
        {"name": "Warehouse", "description": "Warehouse or industrial storage facility"},
        {"name": "Shop", "description": "Retail shop or storefront"},
        {"name": "Semi-detached", "description": "Two-unit residential property sharing one wall"},
    ]

    # Insert each property type if it doesn't already exist
    for prop_type in property_types:
        # Check if the property type already exists (case-insensitive)
        existing = connection.execute(
            sa.text(
                "SELECT property_type_id FROM property_types WHERE LOWER(name) = LOWER(:name)"
            ),
            {"name": prop_type["name"]}
        ).scalar()

        if not existing:
            connection.execute(
                sa.text(
                    "INSERT INTO property_types (name, description, created_at, updated_at) "
                    "VALUES (:name, :description, NOW(), NOW())"
                ),
                {
                    "name": prop_type["name"],
                    "description": prop_type["description"]
                }
            )

    connection.commit()


def downgrade() -> None:
    """Remove seeded property types (if they're not in use)"""
    # This is intentionally conservative: we only remove types if no properties use them
    connection = op.get_bind()

    property_types = [
        "Apartment", "House", "Bungalow", "Duplex", "Condo", "Townhouse",
        "Land", "Commercial", "Office", "Warehouse", "Shop", "Semi-detached"
    ]

    for prop_type_name in property_types:
        # Check if any properties use this type
        usage_count = connection.execute(
            sa.text(
                "SELECT COUNT(*) FROM properties WHERE property_type_id = "
                "(SELECT property_type_id FROM property_types WHERE LOWER(name) = LOWER(:name))"
            ),
            {"name": prop_type_name}
        ).scalar()

        if usage_count == 0:
            connection.execute(
                sa.text(
                    "DELETE FROM property_types WHERE LOWER(name) = LOWER(:name)"
                ),
                {"name": prop_type_name}
            )

    connection.commit()
