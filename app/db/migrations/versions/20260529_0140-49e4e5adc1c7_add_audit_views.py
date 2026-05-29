# app/db/migrations/script.py.mako
"""add_audit_views

Revision ID: 49e4e5adc1c7
Revises: b5f9c2e8a014
Create Date: 2026-05-29 01:40:01.432992

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '49e4e5adc1c7'
down_revision: Union[str, None] = 'b5f9c2e8a014'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Deployment reminder: PR descriptions must name this migration file, and
# production deploy order is `alembic upgrade head` before application code.

def upgrade() -> None:
    """Create operator-only audit views."""
    op.execute("DROP VIEW IF EXISTS public.audit_recent_changes")
    op.execute("DROP VIEW IF EXISTS public.audit_deletions")
    op.execute("DROP VIEW IF EXISTS public.audit_creations")

    op.execute("""
        CREATE VIEW public.audit_creations AS
        SELECT 'users'::text AS table_name,
            u.user_id AS record_id,
            u.created_at,
            u.created_by,
            ( SELECT users.email
                   FROM auth.users
                  WHERE (users.id = u.created_by)) AS created_by_email
           FROM users u
        UNION ALL
         SELECT 'profiles'::text AS table_name,
            p.profile_id AS record_id,
            p.created_at,
            p.created_by,
            ( SELECT users.email
                   FROM auth.users
                  WHERE (users.id = p.created_by)) AS created_by_email
           FROM profiles p
        UNION ALL
         SELECT 'properties'::text AS table_name,
            pr.property_id AS record_id,
            pr.created_at,
            pr.created_by,
            ( SELECT users.email
                   FROM auth.users
                  WHERE (users.id = pr.created_by)) AS created_by_email
           FROM properties pr
        UNION ALL
         SELECT 'agencies'::text AS table_name,
            a.agency_id AS record_id,
            a.created_at,
            a.created_by,
            ( SELECT users.email
                   FROM auth.users
                  WHERE (users.id = a.created_by)) AS created_by_email
           FROM agencies a
        UNION ALL
         SELECT 'agent_profiles'::text AS table_name,
            ap.profile_id AS record_id,
            ap.created_at,
            ap.created_by,
            ( SELECT users.email
                   FROM auth.users
                  WHERE (users.id = ap.created_by)) AS created_by_email
           FROM agent_profiles ap
          ORDER BY 3 DESC
    """)

    op.execute("""
        CREATE VIEW public.audit_deletions AS
        SELECT 'users'::text AS table_name,
            u.user_id AS record_id,
            u.deleted_at,
            u.deleted_by,
            ( SELECT users.email
                   FROM auth.users
                  WHERE (users.id = u.deleted_by)) AS deleted_by_email
           FROM users u
          WHERE (u.deleted_at IS NOT NULL)
        UNION ALL
         SELECT 'profiles'::text AS table_name,
            p.profile_id AS record_id,
            p.deleted_at,
            p.deleted_by,
            ( SELECT users.email
                   FROM auth.users
                  WHERE (users.id = p.deleted_by)) AS deleted_by_email
           FROM profiles p
          WHERE (p.deleted_at IS NOT NULL)
        UNION ALL
         SELECT 'properties'::text AS table_name,
            pr.property_id AS record_id,
            pr.deleted_at,
            pr.deleted_by,
            ( SELECT users.email
                   FROM auth.users
                  WHERE (users.id = pr.deleted_by)) AS deleted_by_email
           FROM properties pr
          WHERE (pr.deleted_at IS NOT NULL)
        UNION ALL
         SELECT 'agencies'::text AS table_name,
            a.agency_id AS record_id,
            a.deleted_at,
            a.deleted_by,
            ( SELECT users.email
                   FROM auth.users
                  WHERE (users.id = a.deleted_by)) AS deleted_by_email
           FROM agencies a
          WHERE (a.deleted_at IS NOT NULL)
        UNION ALL
         SELECT 'agent_profiles'::text AS table_name,
            ap.profile_id AS record_id,
            ap.deleted_at,
            ap.deleted_by,
            ( SELECT users.email
                   FROM auth.users
                  WHERE (users.id = ap.deleted_by)) AS deleted_by_email
           FROM agent_profiles ap
          WHERE (ap.deleted_at IS NOT NULL)
        UNION ALL
         SELECT 'inquiries'::text AS table_name,
            i.inquiry_id AS record_id,
            i.deleted_at,
            i.deleted_by,
            ( SELECT users.email
                   FROM auth.users
                  WHERE (users.id = i.deleted_by)) AS deleted_by_email
           FROM inquiries i
          WHERE (i.deleted_at IS NOT NULL)
        UNION ALL
         SELECT 'reviews'::text AS table_name,
            r.review_id AS record_id,
            r.deleted_at,
            r.deleted_by,
            ( SELECT users.email
                   FROM auth.users
                  WHERE (users.id = r.deleted_by)) AS deleted_by_email
           FROM reviews r
          WHERE (r.deleted_at IS NOT NULL)
        UNION ALL
         SELECT 'saved_searches'::text AS table_name,
            ss.search_id AS record_id,
            ss.deleted_at,
            ss.deleted_by,
            ( SELECT users.email
                   FROM auth.users
                  WHERE (users.id = ss.deleted_by)) AS deleted_by_email
           FROM saved_searches ss
          WHERE (ss.deleted_at IS NOT NULL)
        UNION ALL
         SELECT 'favorites'::text AS table_name,
            f.user_id AS record_id,
            f.deleted_at,
            f.deleted_by,
            ( SELECT users.email
                   FROM auth.users
                  WHERE (users.id = f.deleted_by)) AS deleted_by_email
           FROM favorites f
          WHERE (f.deleted_at IS NOT NULL)
        UNION ALL
         SELECT 'locations'::text AS table_name,
            l.location_id AS record_id,
            l.deleted_at,
            l.deleted_by,
            ( SELECT users.email
                   FROM auth.users
                  WHERE (users.id = l.deleted_by)) AS deleted_by_email
           FROM locations l
          WHERE (l.deleted_at IS NOT NULL)
          ORDER BY 3 DESC
    """)

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
          ORDER BY 5 DESC
    """)

    op.execute(
        "REVOKE ALL ON public.audit_creations, public.audit_deletions, "
        "public.audit_recent_changes FROM PUBLIC, anon, authenticated"
    )


def downgrade() -> None:
    """Drop operator-only audit views."""
    op.execute("DROP VIEW IF EXISTS public.audit_recent_changes")
    op.execute("DROP VIEW IF EXISTS public.audit_deletions")
    op.execute("DROP VIEW IF EXISTS public.audit_creations")
