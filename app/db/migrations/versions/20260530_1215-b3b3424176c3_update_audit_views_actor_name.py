# app/db/migrations/script.py.mako
"""update_audit_views_actor_name

Revision ID: b3b3424176c3
Revises: 439cf2f8f160
Create Date: 2026-05-30 12:15:33.028365

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'b3b3424176c3'
down_revision: Union[str, None] = '439cf2f8f160'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Deployment reminder: PR descriptions must name this migration file, and
# production deploy order is `alembic upgrade head` before application code.


def upgrade() -> None:
    """Update audit_recent_changes view to include actor_name."""
    op.execute("DROP VIEW IF EXISTS public.audit_recent_changes")

    op.execute("""
        CREATE VIEW public.audit_recent_changes AS
        WITH base AS (
            SELECT 'users'::text AS table_name,
                users.user_id AS record_id,
                users.created_at,
                users.created_by,
                users.updated_at,
                users.updated_by,
                users.deleted_at,
                users.deleted_by,
                COALESCE(users.deleted_by, users.updated_by, users.created_by) AS _actor_id
            FROM users
            WHERE (users.updated_at > (now() - '90 days'::interval))
            UNION ALL
            SELECT 'profiles'::text AS table_name,
                profiles.profile_id AS record_id,
                profiles.created_at,
                profiles.created_by,
                profiles.updated_at,
                profiles.updated_by,
                profiles.deleted_at,
                profiles.deleted_by,
                COALESCE(profiles.deleted_by, profiles.updated_by, profiles.created_by) AS _actor_id
            FROM profiles
            WHERE (profiles.updated_at > (now() - '90 days'::interval))
            UNION ALL
            SELECT 'properties'::text AS table_name,
                properties.property_id AS record_id,
                properties.created_at,
                properties.created_by,
                properties.updated_at,
                properties.updated_by,
                properties.deleted_at,
                properties.deleted_by,
                COALESCE(properties.deleted_by, properties.updated_by, properties.created_by) AS _actor_id
            FROM properties
            WHERE (properties.updated_at > (now() - '90 days'::interval))
            UNION ALL
            SELECT 'agencies'::text AS table_name,
                agencies.agency_id AS record_id,
                agencies.created_at,
                agencies.created_by,
                agencies.updated_at,
                agencies.updated_by,
                agencies.deleted_at,
                agencies.deleted_by,
                COALESCE(agencies.deleted_by, agencies.updated_by, agencies.created_by) AS _actor_id
            FROM agencies
            WHERE (agencies.updated_at > (now() - '90 days'::interval))
            UNION ALL
            SELECT 'agent_profiles'::text AS table_name,
                agent_profiles.profile_id AS record_id,
                agent_profiles.created_at,
                agent_profiles.created_by,
                agent_profiles.updated_at,
                agent_profiles.updated_by,
                agent_profiles.deleted_at,
                agent_profiles.deleted_by,
                COALESCE(agent_profiles.deleted_by, agent_profiles.updated_by, agent_profiles.created_by) AS _actor_id
            FROM agent_profiles
            WHERE (agent_profiles.updated_at > (now() - '90 days'::interval))
            UNION ALL
            SELECT 'inquiries'::text AS table_name,
                inquiries.inquiry_id AS record_id,
                inquiries.created_at,
                NULL::uuid AS created_by,
                inquiries.updated_at,
                NULL::uuid AS updated_by,
                inquiries.deleted_at,
                inquiries.deleted_by,
                COALESCE(inquiries.deleted_by, NULL::uuid, NULL::uuid) AS _actor_id
            FROM inquiries
            WHERE (inquiries.updated_at > (now() - '90 days'::interval))
            UNION ALL
            SELECT 'reviews'::text AS table_name,
                reviews.review_id AS record_id,
                reviews.created_at,
                NULL::uuid AS created_by,
                reviews.updated_at,
                NULL::uuid AS updated_by,
                reviews.deleted_at,
                reviews.deleted_by,
                COALESCE(reviews.deleted_by, NULL::uuid, NULL::uuid) AS _actor_id
            FROM reviews
            WHERE (reviews.updated_at > (now() - '90 days'::interval))
            UNION ALL
            SELECT 'saved_searches'::text AS table_name,
                saved_searches.search_id AS record_id,
                saved_searches.created_at,
                NULL::uuid AS created_by,
                saved_searches.updated_at,
                NULL::uuid AS updated_by,
                saved_searches.deleted_at,
                saved_searches.deleted_by,
                COALESCE(saved_searches.deleted_by, NULL::uuid, NULL::uuid) AS _actor_id
            FROM saved_searches
            WHERE (saved_searches.updated_at > (now() - '90 days'::interval))
            UNION ALL
            SELECT 'favorites'::text AS table_name,
                favorites.user_id AS record_id,
                favorites.created_at,
                NULL::uuid AS created_by,
                favorites.updated_at,
                NULL::uuid AS updated_by,
                favorites.deleted_at,
                favorites.deleted_by,
                COALESCE(favorites.deleted_by, NULL::uuid, NULL::uuid) AS _actor_id
            FROM favorites
            WHERE (favorites.updated_at > (now() - '90 days'::interval))
            UNION ALL
            SELECT 'locations'::text AS table_name,
                locations.location_id AS record_id,
                locations.created_at,
                NULL::uuid AS created_by,
                locations.updated_at,
                locations.updated_by,
                locations.deleted_at,
                locations.deleted_by,
                COALESCE(locations.deleted_by, locations.updated_by, NULL::uuid) AS _actor_id
            FROM locations
            WHERE (locations.updated_at > (now() - '90 days'::interval))
        )
        SELECT
            base.table_name,
            base.record_id,
            base.created_at,
            base.created_by,
            base.updated_at,
            base.updated_by,
            base.deleted_at,
            base.deleted_by,
            COALESCE(
                u.first_name || ' ' || u.last_name,
                CASE WHEN base._actor_id IS NULL THEN 'System'
                     ELSE LEFT(base._actor_id::text, 8) END
            ) AS actor_name
        FROM base
        LEFT JOIN users u ON u.supabase_id = base._actor_id
        ORDER BY base.updated_at DESC NULLS LAST
    """)

    op.execute(
        "REVOKE ALL ON public.audit_recent_changes FROM PUBLIC, anon, authenticated"
    )


def downgrade() -> None:
    """Restore original audit_recent_changes view without actor_name."""
    op.execute("DROP VIEW IF EXISTS public.audit_recent_changes")

    op.execute("""
        CREATE VIEW public.audit_recent_changes AS
        SELECT 'users'::text AS table_name,
            users.user_id AS record_id,
            users.created_at,
            users.created_by,
            users.updated_at,
            users.updated_by,
            users.deleted_at,
            users.deleted_by
        FROM users
        WHERE (users.updated_at > (now() - '90 days'::interval))
        UNION ALL
        SELECT 'profiles'::text AS table_name,
            profiles.profile_id AS record_id,
            profiles.created_at,
            profiles.created_by,
            profiles.updated_at,
            profiles.updated_by,
            profiles.deleted_at,
            profiles.deleted_by
        FROM profiles
        WHERE (profiles.updated_at > (now() - '90 days'::interval))
        UNION ALL
        SELECT 'properties'::text AS table_name,
            properties.property_id AS record_id,
            properties.created_at,
            properties.created_by,
            properties.updated_at,
            properties.updated_by,
            properties.deleted_at,
            properties.deleted_by
        FROM properties
        WHERE (properties.updated_at > (now() - '90 days'::interval))
        UNION ALL
        SELECT 'agencies'::text AS table_name,
            agencies.agency_id AS record_id,
            agencies.created_at,
            agencies.created_by,
            agencies.updated_at,
            agencies.updated_by,
            agencies.deleted_at,
            agencies.deleted_by
        FROM agencies
        WHERE (agencies.updated_at > (now() - '90 days'::interval))
        UNION ALL
        SELECT 'agent_profiles'::text AS table_name,
            agent_profiles.profile_id AS record_id,
            agent_profiles.created_at,
            agent_profiles.created_by,
            agent_profiles.updated_at,
            agent_profiles.updated_by,
            agent_profiles.deleted_at,
            agent_profiles.deleted_by
        FROM agent_profiles
        WHERE (agent_profiles.updated_at > (now() - '90 days'::interval))
        UNION ALL
        SELECT 'inquiries'::text AS table_name,
            inquiries.inquiry_id AS record_id,
            inquiries.created_at,
            NULL::uuid AS created_by,
            inquiries.updated_at,
            NULL::uuid AS updated_by,
            inquiries.deleted_at,
            inquiries.deleted_by
        FROM inquiries
        WHERE (inquiries.updated_at > (now() - '90 days'::interval))
        UNION ALL
        SELECT 'reviews'::text AS table_name,
            reviews.review_id AS record_id,
            reviews.created_at,
            NULL::uuid AS created_by,
            reviews.updated_at,
            NULL::uuid AS updated_by,
            reviews.deleted_at,
            reviews.deleted_by
        FROM reviews
        WHERE (reviews.updated_at > (now() - '90 days'::interval))
        UNION ALL
        SELECT 'saved_searches'::text AS table_name,
            saved_searches.search_id AS record_id,
            saved_searches.created_at,
            NULL::uuid AS created_by,
            saved_searches.updated_at,
            NULL::uuid AS updated_by,
            saved_searches.deleted_at,
            saved_searches.deleted_by
        FROM saved_searches
        WHERE (saved_searches.updated_at > (now() - '90 days'::interval))
        UNION ALL
        SELECT 'favorites'::text AS table_name,
            favorites.user_id AS record_id,
            favorites.created_at,
            NULL::uuid AS created_by,
            favorites.updated_at,
            NULL::uuid AS updated_by,
            favorites.deleted_at,
            favorites.deleted_by
        FROM favorites
        WHERE (favorites.updated_at > (now() - '90 days'::interval))
        UNION ALL
        SELECT 'locations'::text AS table_name,
            locations.location_id AS record_id,
            locations.created_at,
            NULL::uuid AS created_by,
            locations.updated_at,
            locations.updated_by,
            locations.deleted_at,
            locations.deleted_by
        FROM locations
        WHERE (locations.updated_at > (now() - '90 days'::interval))
        ORDER BY 5 DESC NULLS LAST
    """)

    op.execute(
        "REVOKE ALL ON public.audit_recent_changes FROM PUBLIC, anon, authenticated"
    )
