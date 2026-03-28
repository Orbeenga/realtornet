# app/db/migrations/script.py.mako
"""perf_drop_duplicate_indexes

Revision ID: 6c0087f609b4
Revises: ccf073c8b981
Create Date: 2026-03-28 03:08:30.519626

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6c0087f609b4'
down_revision: Union[str, None] = 'ccf073c8b981'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Sub-class A — duplicate UNIQUE constraints (same column, two constraint objects)
    # Keep: agencies_email_key, amenities_name_key, property_types_name_key
    # These were created twice: once by Postgres UNIQUE column def, once by our migration
    op.execute("ALTER TABLE public.agencies DROP CONSTRAINT IF EXISTS uq_agencies_email")
    op.execute("ALTER TABLE public.amenities DROP CONSTRAINT IF EXISTS uq_amenities_name")
    op.execute("ALTER TABLE public.property_types DROP CONSTRAINT IF EXISTS uq_property_types_name")

    # Sub-class A (cont.) — plain ix_ indexes on users (not constraints, safe DROP INDEX)
    op.drop_index("ix_users_email", table_name="users", if_exists=True)
    op.drop_index("ix_users_supabase_id", table_name="users", if_exists=True)

    # Sub-class B — plain ix_ / legacy indexes duplicating idx_ canonical indexes
    op.drop_index("ix_agent_profiles_agency_id", table_name="agent_profiles", if_exists=True)
    op.drop_index("ix_inquiries_property_id", table_name="inquiries", if_exists=True)
    op.drop_index("ix_inquiries_user_id", table_name="inquiries", if_exists=True)
    op.drop_index("locations_geom_idx", table_name="locations", if_exists=True)
    op.drop_index("idx_properties_not_deleted", table_name="properties", if_exists=True)
    op.drop_index("ix_users_agency_id", table_name="users", if_exists=True)


def downgrade() -> None:
    # Sub-class A — restore dropped constraints
    op.execute("ALTER TABLE public.agencies ADD CONSTRAINT uq_agencies_email UNIQUE (email)")
    op.execute("ALTER TABLE public.amenities ADD CONSTRAINT uq_amenities_name UNIQUE (name)")
    op.execute("ALTER TABLE public.property_types ADD CONSTRAINT uq_property_types_name UNIQUE (name)")

    # Sub-class A (cont.) — restore plain indexes on users
    op.create_index("ix_users_email", "users", ["email"], unique=False)
    op.create_index("ix_users_supabase_id", "users", ["supabase_id"], unique=False)

    # Sub-class B — restore plain indexes
    op.create_index("ix_agent_profiles_agency_id", "agent_profiles", ["agency_id"])
    op.create_index("ix_inquiries_property_id", "inquiries", ["property_id"])
    op.create_index("ix_inquiries_user_id", "inquiries", ["user_id"])
    op.create_index("locations_geom_idx", "locations", ["geom"], postgresql_using="gist")
    op.create_index("idx_properties_not_deleted", "properties", ["deleted_at"])
    op.create_index("ix_users_agency_id", "users", ["agency_id"])
