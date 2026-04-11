"""bootstrap_full_schema

Revision ID: b7d2a4c9e1f0
Revises: d1ba4e701ce3
Create Date: 2026-04-11 00:00:00.000000

Bootstrap migration for a clean Supabase project.

This migration intentionally creates the pre-normalization schema that the
existing revision chain expects, so later revisions can still apply in order:

- 5624fddb4ef8 normalizes listing_type_enum values
- 68aeff120f1f adds suspended to profile_status_enum
- 4e8866888c9c adds amenities.category
- 388601679a8b adds property_images.caption/display_order
- 3cf0979df4e8 creates analytics views
- ccf073c8b981 aligns constraints/indexes/comments
- 6c0087f609b4 drops duplicate indexes

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from geoalchemy2 import Geography
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "b7d2a4c9e1f0"
down_revision: Union[str, None] = "d1ba4e701ce3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create the bootstrap schema for a clean Supabase database."""
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")
    op.execute("CREATE TYPE user_role_enum AS ENUM ('seeker', 'agent', 'admin')")
    op.execute("CREATE TYPE listing_type_enum AS ENUM ('for sale', 'for rent', 'lease')")
    op.execute(
        "CREATE TYPE listing_status_enum AS ENUM "
        "('available', 'active', 'pending', 'sold', 'rented', 'unavailable')"
    )
    op.execute("CREATE TYPE profile_status_enum AS ENUM ('active', 'inactive')")
    op.execute("CREATE TYPE inquiry_status_enum AS ENUM ('new', 'viewed', 'responded')")

    op.create_table(
        "users",
        sa.Column("user_id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("supabase_id", sa.UUID(), nullable=False, unique=True),
        sa.Column("agency_id", sa.BigInteger(), nullable=True),
        sa.Column("email", sa.String(), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(), nullable=False),
        sa.Column("first_name", sa.String(), nullable=False),
        sa.Column("last_name", sa.String(), nullable=False),
        sa.Column("phone_number", sa.String(), nullable=True),
        sa.Column(
            "user_role",
            postgresql.ENUM(
                "seeker",
                "agent",
                "admin",
                name="user_role_enum",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("is_verified", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("verification_code", sa.String(), nullable=True),
        sa.Column("is_admin", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("profile_image_url", sa.String(), nullable=True),
        sa.Column("last_login", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True, server_default=sa.text("now()")),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("updated_by", sa.UUID(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", sa.UUID(), nullable=True),
        sa.CheckConstraint("email = lower(email)", name="users_email_lowercase_check"),
        sa.CheckConstraint(
            "phone_number IS NULL OR length(trim(phone_number)) > 0",
            name="users_phone_number_not_empty_check",
        ),
        sa.CheckConstraint(
            "user_role::text = ANY (ARRAY['seeker'::text, 'agent'::text, 'admin'::text])",
            name="users_user_role_check",
        ),
    )

    op.create_table(
        "agencies",
        sa.Column("agency_id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("email", sa.String(), nullable=True),
        sa.Column("phone_number", sa.String(), nullable=True),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("logo_url", sa.String(), nullable=True),
        sa.Column("website_url", sa.String(), nullable=True),
        sa.Column("is_verified", sa.Boolean(), nullable=True, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True, server_default=sa.text("now()")),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("updated_by", sa.UUID(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", sa.UUID(), nullable=True),
        sa.CheckConstraint("email = lower(email)", name="agencies_email_lowercase_check"),
        sa.CheckConstraint(
            "phone_number IS NULL OR length(trim(phone_number)) > 0",
            name="agencies_phone_number_not_empty_check",
        ),
    )

    op.create_table(
        "profiles",
        sa.Column("profile_id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("user_id", sa.BigInteger(), nullable=True),
        sa.Column("full_name", sa.Text(), nullable=False),
        sa.Column("phone_number", sa.Text(), nullable=True),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("profile_picture", sa.Text(), nullable=True),
        sa.Column("bio", sa.Text(), nullable=True),
        sa.Column(
            "status",
            postgresql.ENUM(
                "active",
                "inactive",
                name="profile_status_enum",
                create_type=False,
            ),
            nullable=False,
            server_default=sa.text("'active'::profile_status_enum"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True, server_default=sa.text("now()")),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("updated_by", sa.UUID(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", sa.UUID(), nullable=True),
    )
    # This named unique constraint is referenced by ccf073c8b981 and must exist
    # exactly once in the bootstrap path for the later chain to drop cleanly.
    op.create_unique_constraint("profiles_user_id_unique", "profiles", ["user_id"])

    op.create_table(
        "agent_profiles",
        sa.Column("profile_id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("user_id", sa.BigInteger(), nullable=False, unique=True),
        sa.Column("agency_id", sa.BigInteger(), nullable=True),
        sa.Column("license_number", sa.String(length=50), nullable=True),
        sa.Column("specialization", sa.String(length=255), nullable=True),
        sa.Column("bio", sa.Text(), nullable=True),
        sa.Column("years_experience", sa.Integer(), nullable=True),
        sa.Column("website", sa.String(), nullable=True),
        sa.Column("company_name", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True, server_default=sa.text("now()")),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("updated_by", sa.UUID(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", sa.UUID(), nullable=True),
    )

    op.create_table(
        "property_types",
        sa.Column("property_type_id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True, server_default=sa.text("now()")),
    )

    op.create_table(
        "amenities",
        sa.Column("amenity_id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True, server_default=sa.text("now()")),
    )

    op.create_table(
        "locations",
        sa.Column("location_id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("state", sa.String(), nullable=False),
        sa.Column("city", sa.String(), nullable=False),
        sa.Column("neighborhood", sa.String(), nullable=True),
        sa.Column("geom", Geography(geometry_type="POINT", srid=4326), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("updated_by", sa.UUID(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True, server_default=sa.text("now()")),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", sa.UUID(), nullable=True),
    )

    op.create_table(
        "properties",
        sa.Column("property_id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=True),
        sa.Column("property_type_id", sa.BigInteger(), nullable=True),
        sa.Column("location_id", sa.BigInteger(), nullable=True),
        sa.Column("geom", Geography(geometry_type="POINT", srid=4326), nullable=True),
        sa.Column("price", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("price_currency", sa.String(), nullable=True, server_default=sa.text("'NGN'")),
        sa.Column("bedrooms", sa.Integer(), nullable=True),
        sa.Column("bathrooms", sa.Integer(), nullable=True),
        sa.Column("property_size", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("is_featured", sa.Boolean(), nullable=True, server_default=sa.text("false")),
        sa.Column(
            "listing_type",
            postgresql.ENUM(
                "for sale",
                "for rent",
                "lease",
                name="listing_type_enum",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "listing_status",
            postgresql.ENUM(
                "available",
                "active",
                "pending",
                "sold",
                "rented",
                "unavailable",
                name="listing_status_enum",
                create_type=False,
            ),
            nullable=False,
            server_default=sa.text("'available'::listing_status_enum"),
        ),
        sa.Column("is_verified", sa.Boolean(), nullable=True, server_default=sa.text("false")),
        sa.Column("verification_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("year_built", sa.Integer(), nullable=True),
        sa.Column("parking_spaces", sa.Integer(), nullable=True),
        sa.Column("has_garden", sa.Boolean(), nullable=True, server_default=sa.text("false")),
        sa.Column("has_security", sa.Boolean(), nullable=True, server_default=sa.text("false")),
        sa.Column("has_swimming_pool", sa.Boolean(), nullable=True, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True, server_default=sa.text("now()")),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("updated_by", sa.UUID(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", sa.UUID(), nullable=True),
        sa.CheckConstraint("price > 0::numeric", name="properties_price_check"),
        sa.CheckConstraint("bedrooms IS NULL OR bedrooms >= 0", name="properties_bedrooms_check"),
        sa.CheckConstraint("bathrooms IS NULL OR bathrooms >= 0", name="properties_bathrooms_check"),
        sa.CheckConstraint(
            "property_size IS NULL OR property_size > 0::numeric",
            name="properties_property_size_check",
        ),
        sa.CheckConstraint(
            "year_built IS NULL OR (year_built >= 1950 AND year_built <= EXTRACT(YEAR FROM CURRENT_DATE) + 2)",
            name="properties_year_built_check",
        ),
        sa.CheckConstraint(
            "parking_spaces IS NULL OR parking_spaces >= 0",
            name="properties_parking_spaces_check",
        ),
    )

    op.create_table(
        "property_images",
        sa.Column("image_id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("property_id", sa.BigInteger(), nullable=False),
        sa.Column("image_url", sa.String(), nullable=False),
        sa.Column("is_primary", sa.Boolean(), nullable=True, server_default=sa.text("false")),
        sa.Column("is_verified", sa.Boolean(), nullable=True, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True, server_default=sa.text("now()")),
    )

    op.create_table(
        "property_amenities",
        sa.Column("property_id", sa.BigInteger(), primary_key=True, nullable=False),
        sa.Column("amenity_id", sa.BigInteger(), primary_key=True, nullable=False),
    )

    op.create_table(
        "reviews",
        sa.Column("review_id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("user_id", sa.BigInteger(), nullable=True),
        sa.Column("property_id", sa.BigInteger(), nullable=True),
        sa.Column("agent_id", sa.BigInteger(), nullable=True),
        sa.Column("rating", sa.Integer(), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True, server_default=sa.text("now()")),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", sa.UUID(), nullable=True),
        sa.CheckConstraint("rating >= 1 AND rating <= 5", name="reviews_rating_check"),
    )

    op.create_table(
        "inquiries",
        sa.Column("inquiry_id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("user_id", sa.BigInteger(), nullable=True),
        sa.Column("property_id", sa.BigInteger(), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column(
            "inquiry_status",
            postgresql.ENUM(
                "new", "viewed", "responded",
                name="inquiry_status_enum",
                create_type=False,
            ),
            nullable=False,
            server_default=sa.text("'new'::inquiry_status_enum"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True, server_default=sa.text("now()")),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", sa.UUID(), nullable=True),
        sa.CheckConstraint(
            "inquiry_status = ANY (ARRAY['new'::inquiry_status_enum, 'viewed'::inquiry_status_enum, 'responded'::inquiry_status_enum])",
            name="ck_inquiries_inquiries_inquiry_status_check",
        ),
    )

    op.create_table(
        "favorites",
        sa.Column("user_id", sa.BigInteger(), primary_key=True, nullable=False),
        sa.Column("property_id", sa.BigInteger(), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True, server_default=sa.text("now()")),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", sa.UUID(), nullable=True),
    )

    op.create_table(
        "saved_searches",
        sa.Column("search_id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("user_id", sa.BigInteger(), nullable=True),
        sa.Column("search_params", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("name", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True, server_default=sa.text("now()")),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", sa.UUID(), nullable=True),
    )

    op.create_index("locations_geom_idx", "locations", ["geom"], unique=False, postgresql_using="gist")
    op.create_index("idx_properties_not_deleted", "properties", ["deleted_at"], unique=False)

    # FK names below are intentionally distinct from the later named-fk migration
    # (ccf073c8b981) so that the existing chain can still apply cleanly.
    op.create_foreign_key("users_agency_id_fkey", "users", "agencies", ["agency_id"], ["agency_id"], ondelete="SET NULL")
    op.create_foreign_key("profiles_user_id_fkey", "profiles", "users", ["user_id"], ["user_id"])
    op.create_foreign_key("agent_profiles_user_id_fkey", "agent_profiles", "users", ["user_id"], ["user_id"], ondelete="CASCADE")
    op.create_foreign_key("agent_profiles_agency_id_fkey", "agent_profiles", "agencies", ["agency_id"], ["agency_id"], ondelete="SET NULL")
    op.create_foreign_key("properties_user_id_fkey", "properties", "users", ["user_id"], ["user_id"])
    op.create_foreign_key(
        "properties_property_type_id_fkey",
        "properties",
        "property_types",
        ["property_type_id"],
        ["property_type_id"],
    )
    op.create_foreign_key(
        "properties_location_id_fkey",
        "properties",
        "locations",
        ["location_id"],
        ["location_id"],
    )
    op.create_foreign_key(
        "property_images_property_id_fkey",
        "property_images",
        "properties",
        ["property_id"],
        ["property_id"],
    )
    op.create_foreign_key(
        "property_amenities_property_id_fkey",
        "property_amenities",
        "properties",
        ["property_id"],
        ["property_id"],
    )
    op.create_foreign_key(
        "property_amenities_amenity_id_fkey",
        "property_amenities",
        "amenities",
        ["amenity_id"],
        ["amenity_id"],
    )
    op.create_foreign_key("reviews_user_id_fkey", "reviews", "users", ["user_id"], ["user_id"])
    op.create_foreign_key("reviews_property_id_fkey", "reviews", "properties", ["property_id"], ["property_id"])
    # ASSUMPTION: agent-specific reviews are optional, so agent_id remains nullable.
    op.create_foreign_key("reviews_agent_id_fkey", "reviews", "users", ["agent_id"], ["user_id"])
    op.create_foreign_key("inquiries_user_id_fkey", "inquiries", "users", ["user_id"], ["user_id"], ondelete="CASCADE")
    op.create_foreign_key(
        "inquiries_property_id_fkey",
        "inquiries",
        "properties",
        ["property_id"],
        ["property_id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key("favorites_user_id_fkey", "favorites", "users", ["user_id"], ["user_id"])
    op.create_foreign_key("favorites_property_id_fkey", "favorites", "properties", ["property_id"], ["property_id"])
    op.create_foreign_key("saved_searches_user_id_fkey", "saved_searches", "users", ["user_id"], ["user_id"])


def downgrade() -> None:
    """Remove the bootstrap schema in reverse order."""
    op.drop_index("idx_properties_not_deleted", table_name="properties", if_exists=True)
    op.drop_index("locations_geom_idx", table_name="locations", if_exists=True)

    op.drop_table("saved_searches")
    op.drop_table("favorites")
    op.drop_table("inquiries")
    op.drop_table("reviews")
    op.drop_table("property_amenities")
    op.drop_table("property_images")
    op.drop_table("properties")
    op.drop_table("locations")
    op.drop_table("amenities")
    op.drop_table("property_types")
    op.drop_table("agent_profiles")
    op.drop_table("profiles")
    op.drop_table("agencies")
    op.drop_table("users")

    op.execute("DROP TYPE IF EXISTS inquiry_status_enum")
    op.execute("DROP TYPE IF EXISTS profile_status_enum")
    op.execute("DROP TYPE IF EXISTS listing_status_enum")
    op.execute("DROP TYPE IF EXISTS listing_type_enum")
    op.execute("DROP TYPE IF EXISTS user_role_enum")
