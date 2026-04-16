"""enable public table rls

Revision ID: 9f2b7c1d4a10
Revises: 6c0087f609b4
Create Date: 2026-04-15 23:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "9f2b7c1d4a10"
down_revision: Union[str, None] = "6c0087f609b4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


UPGRADE_SQL = """
DO $$
DECLARE
    table_name text;
    policy_name text;
BEGIN
    FOREACH table_name IN ARRAY ARRAY[
        'agencies',
        'agent_profiles',
        'amenities',
        'favorites',
        'inquiries',
        'locations',
        'profiles',
        'properties',
        'property_amenities',
        'property_images',
        'property_types',
        'reviews',
        'saved_searches',
        'users'
    ]
    LOOP
        EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', table_name);

        FOR policy_name IN
            SELECT p.polname
            FROM pg_policy AS p
            JOIN pg_class AS c ON c.oid = p.polrelid
            JOIN pg_namespace AS n ON n.oid = c.relnamespace
            WHERE n.nspname = 'public'
              AND c.relname = table_name
        LOOP
            EXECUTE format('DROP POLICY IF EXISTS %I ON public.%I', policy_name, table_name);
        END LOOP;
    END LOOP;
END $$;

DROP FUNCTION IF EXISTS public.is_current_user_admin();
DROP FUNCTION IF EXISTS public.current_user_id();
DROP FUNCTION IF EXISTS public.current_request_role();
DROP FUNCTION IF EXISTS public.current_supabase_id();

CREATE OR REPLACE FUNCTION public.current_supabase_id()
RETURNS uuid
LANGUAGE plpgsql
STABLE
AS $function$
DECLARE
    raw_value text;
BEGIN
    raw_value := COALESCE(
        NULLIF(current_setting('app.current_supabase_id', true), ''),
        NULLIF(current_setting('request.jwt.claim.sub', true), '')
    );

    IF raw_value IS NULL THEN
        BEGIN
            raw_value := NULLIF((current_setting('request.jwt.claims', true)::jsonb ->> 'sub'), '');
        EXCEPTION
            WHEN OTHERS THEN
                raw_value := NULL;
        END;
    END IF;

    IF raw_value IS NULL THEN
        RETURN NULL;
    END IF;

    BEGIN
        RETURN raw_value::uuid;
    EXCEPTION
        WHEN OTHERS THEN
            RETURN NULL;
    END;
END;
$function$;

CREATE OR REPLACE FUNCTION public.current_request_role()
RETURNS text
LANGUAGE plpgsql
STABLE
AS $function$
DECLARE
    raw_value text;
BEGIN
    raw_value := COALESCE(
        NULLIF(current_setting('app.current_role', true), ''),
        NULLIF(current_setting('request.jwt.claim.role', true), '')
    );

    IF raw_value IS NULL THEN
        BEGIN
            raw_value := NULLIF((current_setting('request.jwt.claims', true)::jsonb ->> 'role'), '');
        EXCEPTION
            WHEN OTHERS THEN
                raw_value := NULL;
        END;
    END IF;

    RETURN raw_value;
END;
$function$;

CREATE OR REPLACE FUNCTION public.current_user_id()
RETURNS bigint
LANGUAGE plpgsql
STABLE
AS $function$
DECLARE
    raw_value text;
BEGIN
    raw_value := COALESCE(
        NULLIF(current_setting('app.current_user_id', true), ''),
        NULLIF(current_setting('request.jwt.claim.user_id', true), '')
    );

    IF raw_value IS NULL THEN
        BEGIN
            raw_value := NULLIF((current_setting('request.jwt.claims', true)::jsonb ->> 'user_id'), '');
        EXCEPTION
            WHEN OTHERS THEN
                raw_value := NULL;
        END;
    END IF;

    IF raw_value IS NULL THEN
        RETURN NULL;
    END IF;

    BEGIN
        RETURN raw_value::bigint;
    EXCEPTION
        WHEN OTHERS THEN
            RETURN NULL;
    END;
END;
$function$;

CREATE OR REPLACE FUNCTION public.is_current_user_admin()
RETURNS boolean
LANGUAGE sql
STABLE
AS $function$
    SELECT COALESCE(public.current_request_role() = 'admin', false);
$function$;

GRANT USAGE ON SCHEMA public TO anon, authenticated;
GRANT SELECT ON public.agencies, public.agent_profiles, public.amenities, public.locations, public.properties, public.property_amenities, public.property_images, public.property_types, public.reviews, public.users TO anon, authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.agencies, public.agent_profiles, public.amenities, public.favorites, public.inquiries, public.locations, public.profiles, public.properties, public.property_amenities, public.property_images, public.property_types, public.reviews, public.saved_searches, public.users TO authenticated;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO authenticated;

CREATE POLICY agencies_select_public
ON public.agencies
FOR SELECT
TO anon, authenticated
USING (deleted_at IS NULL);

CREATE POLICY agencies_insert_admin
ON public.agencies
FOR INSERT
TO authenticated
WITH CHECK (public.is_current_user_admin());

CREATE POLICY agencies_update_admin
ON public.agencies
FOR UPDATE
TO authenticated
USING (public.is_current_user_admin())
WITH CHECK (public.is_current_user_admin());

CREATE POLICY agencies_delete_admin
ON public.agencies
FOR DELETE
TO authenticated
USING (public.is_current_user_admin());

CREATE POLICY agent_profiles_select_public
ON public.agent_profiles
FOR SELECT
TO anon, authenticated
USING (deleted_at IS NULL);

CREATE POLICY agent_profiles_insert_admin
ON public.agent_profiles
FOR INSERT
TO authenticated
WITH CHECK (public.is_current_user_admin());

CREATE POLICY agent_profiles_update_owner_or_admin
ON public.agent_profiles
FOR UPDATE
TO authenticated
USING (
    user_id = public.current_user_id()
    OR public.is_current_user_admin()
)
WITH CHECK (
    user_id = public.current_user_id()
    OR public.is_current_user_admin()
);

CREATE POLICY agent_profiles_delete_admin
ON public.agent_profiles
FOR DELETE
TO authenticated
USING (public.is_current_user_admin());

CREATE POLICY amenities_select_public
ON public.amenities
FOR SELECT
TO anon, authenticated
USING (true);

CREATE POLICY amenities_insert_admin
ON public.amenities
FOR INSERT
TO authenticated
WITH CHECK (public.is_current_user_admin());

CREATE POLICY amenities_update_admin
ON public.amenities
FOR UPDATE
TO authenticated
USING (public.is_current_user_admin())
WITH CHECK (public.is_current_user_admin());

CREATE POLICY amenities_delete_admin
ON public.amenities
FOR DELETE
TO authenticated
USING (public.is_current_user_admin());

CREATE POLICY favorites_select_owner
ON public.favorites
FOR SELECT
TO authenticated
USING (
    deleted_at IS NULL
    AND user_id = public.current_user_id()
);

CREATE POLICY favorites_insert_owner
ON public.favorites
FOR INSERT
TO authenticated
WITH CHECK (user_id = public.current_user_id());

CREATE POLICY favorites_update_owner
ON public.favorites
FOR UPDATE
TO authenticated
USING (user_id = public.current_user_id())
WITH CHECK (user_id = public.current_user_id());

CREATE POLICY favorites_delete_owner
ON public.favorites
FOR DELETE
TO authenticated
USING (user_id = public.current_user_id());

CREATE POLICY inquiries_select_related
ON public.inquiries
FOR SELECT
TO authenticated
USING (
    deleted_at IS NULL
    AND (
        user_id = public.current_user_id()
        OR public.is_current_user_admin()
        OR EXISTS (
            SELECT 1
            FROM public.properties AS p
            WHERE p.property_id = inquiries.property_id
              AND p.user_id = public.current_user_id()
              AND p.deleted_at IS NULL
        )
    )
);

CREATE POLICY inquiries_insert_owner
ON public.inquiries
FOR INSERT
TO authenticated
WITH CHECK (user_id = public.current_user_id());

CREATE POLICY inquiries_update_related
ON public.inquiries
FOR UPDATE
TO authenticated
USING (
    user_id = public.current_user_id()
    OR public.is_current_user_admin()
    OR EXISTS (
        SELECT 1
        FROM public.properties AS p
        WHERE p.property_id = inquiries.property_id
          AND p.user_id = public.current_user_id()
          AND p.deleted_at IS NULL
    )
)
WITH CHECK (
    user_id = public.current_user_id()
    OR public.is_current_user_admin()
    OR EXISTS (
        SELECT 1
        FROM public.properties AS p
        WHERE p.property_id = inquiries.property_id
          AND p.user_id = public.current_user_id()
          AND p.deleted_at IS NULL
    )
);

CREATE POLICY inquiries_delete_owner_or_admin
ON public.inquiries
FOR DELETE
TO authenticated
USING (
    user_id = public.current_user_id()
    OR public.is_current_user_admin()
);

CREATE POLICY locations_select_public
ON public.locations
FOR SELECT
TO anon, authenticated
USING (deleted_at IS NULL);

CREATE POLICY locations_insert_admin
ON public.locations
FOR INSERT
TO authenticated
WITH CHECK (public.is_current_user_admin());

CREATE POLICY locations_update_admin
ON public.locations
FOR UPDATE
TO authenticated
USING (public.is_current_user_admin())
WITH CHECK (public.is_current_user_admin());

CREATE POLICY locations_delete_admin
ON public.locations
FOR DELETE
TO authenticated
USING (public.is_current_user_admin());

CREATE POLICY profiles_select_self_or_admin
ON public.profiles
FOR SELECT
TO authenticated
USING (
    user_id = public.current_user_id()
    OR public.is_current_user_admin()
);

CREATE POLICY profiles_insert_self_or_admin
ON public.profiles
FOR INSERT
TO authenticated
WITH CHECK (
    user_id = public.current_user_id()
    OR public.is_current_user_admin()
);

CREATE POLICY profiles_update_self_or_admin
ON public.profiles
FOR UPDATE
TO authenticated
USING (
    user_id = public.current_user_id()
    OR public.is_current_user_admin()
)
WITH CHECK (
    user_id = public.current_user_id()
    OR public.is_current_user_admin()
);

CREATE POLICY profiles_delete_admin
ON public.profiles
FOR DELETE
TO authenticated
USING (public.is_current_user_admin());

CREATE POLICY properties_select_visible
ON public.properties
FOR SELECT
TO anon, authenticated
USING (
    deleted_at IS NULL
    AND (
        is_verified IS TRUE
        OR user_id = public.current_user_id()
        OR public.is_current_user_admin()
    )
);

CREATE POLICY properties_insert_owner_or_admin
ON public.properties
FOR INSERT
TO authenticated
WITH CHECK (
    user_id = public.current_user_id()
    OR public.is_current_user_admin()
);

CREATE POLICY properties_update_owner_or_admin
ON public.properties
FOR UPDATE
TO authenticated
USING (
    user_id = public.current_user_id()
    OR public.is_current_user_admin()
)
WITH CHECK (
    user_id = public.current_user_id()
    OR public.is_current_user_admin()
);

CREATE POLICY properties_delete_owner_or_admin
ON public.properties
FOR DELETE
TO authenticated
USING (
    user_id = public.current_user_id()
    OR public.is_current_user_admin()
);

CREATE POLICY property_amenities_select_visible_property
ON public.property_amenities
FOR SELECT
TO anon, authenticated
USING (
    EXISTS (
        SELECT 1
        FROM public.properties AS p
        WHERE p.property_id = property_amenities.property_id
          AND p.deleted_at IS NULL
          AND (
              p.is_verified IS TRUE
              OR p.user_id = public.current_user_id()
              OR public.is_current_user_admin()
          )
    )
);

CREATE POLICY property_amenities_modify_owner_or_admin
ON public.property_amenities
FOR ALL
TO authenticated
USING (
    EXISTS (
        SELECT 1
        FROM public.properties AS p
        WHERE p.property_id = property_amenities.property_id
          AND (
              p.user_id = public.current_user_id()
              OR public.is_current_user_admin()
          )
    )
)
WITH CHECK (
    EXISTS (
        SELECT 1
        FROM public.properties AS p
        WHERE p.property_id = property_amenities.property_id
          AND (
              p.user_id = public.current_user_id()
              OR public.is_current_user_admin()
          )
    )
);

CREATE POLICY property_images_select_visible_property
ON public.property_images
FOR SELECT
TO anon, authenticated
USING (
    EXISTS (
        SELECT 1
        FROM public.properties AS p
        WHERE p.property_id = property_images.property_id
          AND p.deleted_at IS NULL
          AND (
              p.is_verified IS TRUE
              OR p.user_id = public.current_user_id()
              OR public.is_current_user_admin()
          )
    )
);

CREATE POLICY property_images_insert_owner_or_admin
ON public.property_images
FOR INSERT
TO authenticated
WITH CHECK (
    EXISTS (
        SELECT 1
        FROM public.properties AS p
        WHERE p.property_id = property_images.property_id
          AND (
              p.user_id = public.current_user_id()
              OR public.is_current_user_admin()
          )
    )
);

CREATE POLICY property_images_update_owner_or_admin
ON public.property_images
FOR UPDATE
TO authenticated
USING (
    EXISTS (
        SELECT 1
        FROM public.properties AS p
        WHERE p.property_id = property_images.property_id
          AND (
              p.user_id = public.current_user_id()
              OR public.is_current_user_admin()
          )
    )
)
WITH CHECK (
    EXISTS (
        SELECT 1
        FROM public.properties AS p
        WHERE p.property_id = property_images.property_id
          AND (
              p.user_id = public.current_user_id()
              OR public.is_current_user_admin()
          )
    )
);

CREATE POLICY property_images_delete_owner_or_admin
ON public.property_images
FOR DELETE
TO authenticated
USING (
    EXISTS (
        SELECT 1
        FROM public.properties AS p
        WHERE p.property_id = property_images.property_id
          AND (
              p.user_id = public.current_user_id()
              OR public.is_current_user_admin()
          )
    )
);

CREATE POLICY property_types_select_public
ON public.property_types
FOR SELECT
TO anon, authenticated
USING (true);

CREATE POLICY property_types_insert_admin
ON public.property_types
FOR INSERT
TO authenticated
WITH CHECK (public.is_current_user_admin());

CREATE POLICY property_types_update_admin
ON public.property_types
FOR UPDATE
TO authenticated
USING (public.is_current_user_admin())
WITH CHECK (public.is_current_user_admin());

CREATE POLICY property_types_delete_admin
ON public.property_types
FOR DELETE
TO authenticated
USING (public.is_current_user_admin());

CREATE POLICY reviews_select_public
ON public.reviews
FOR SELECT
TO anon, authenticated
USING (deleted_at IS NULL);

CREATE POLICY reviews_insert_owner
ON public.reviews
FOR INSERT
TO authenticated
WITH CHECK (user_id = public.current_user_id());

CREATE POLICY reviews_update_owner_or_admin
ON public.reviews
FOR UPDATE
TO authenticated
USING (
    user_id = public.current_user_id()
    OR public.is_current_user_admin()
)
WITH CHECK (
    user_id = public.current_user_id()
    OR public.is_current_user_admin()
);

CREATE POLICY reviews_delete_owner_or_admin
ON public.reviews
FOR DELETE
TO authenticated
USING (
    user_id = public.current_user_id()
    OR public.is_current_user_admin()
);

CREATE POLICY saved_searches_select_owner
ON public.saved_searches
FOR SELECT
TO authenticated
USING (
    deleted_at IS NULL
    AND user_id = public.current_user_id()
);

CREATE POLICY saved_searches_insert_owner
ON public.saved_searches
FOR INSERT
TO authenticated
WITH CHECK (user_id = public.current_user_id());

CREATE POLICY saved_searches_update_owner
ON public.saved_searches
FOR UPDATE
TO authenticated
USING (user_id = public.current_user_id())
WITH CHECK (user_id = public.current_user_id());

CREATE POLICY saved_searches_delete_owner
ON public.saved_searches
FOR DELETE
TO authenticated
USING (user_id = public.current_user_id());

CREATE POLICY users_select_public_realtors
ON public.users
FOR SELECT
TO anon, authenticated
USING (
    deleted_at IS NULL
    AND user_role = 'agent'
);

CREATE POLICY users_select_self_or_admin
ON public.users
FOR SELECT
TO authenticated
USING (
    user_id = public.current_user_id()
    OR public.is_current_user_admin()
);

CREATE POLICY users_insert_admin
ON public.users
FOR INSERT
TO authenticated
WITH CHECK (public.is_current_user_admin());

CREATE POLICY users_update_self_or_admin
ON public.users
FOR UPDATE
TO authenticated
USING (
    user_id = public.current_user_id()
    OR public.is_current_user_admin()
)
WITH CHECK (
    user_id = public.current_user_id()
    OR public.is_current_user_admin()
);

CREATE POLICY users_delete_admin
ON public.users
FOR DELETE
TO authenticated
USING (public.is_current_user_admin());
"""


DOWNGRADE_SQL = """
DO $$
DECLARE
    table_name text;
    policy_name text;
BEGIN
    FOREACH table_name IN ARRAY ARRAY[
        'agencies',
        'agent_profiles',
        'amenities',
        'favorites',
        'inquiries',
        'locations',
        'profiles',
        'properties',
        'property_amenities',
        'property_images',
        'property_types',
        'reviews',
        'saved_searches',
        'users'
    ]
    LOOP
        FOR policy_name IN
            SELECT p.polname
            FROM pg_policy AS p
            JOIN pg_class AS c ON c.oid = p.polrelid
            JOIN pg_namespace AS n ON n.oid = c.relnamespace
            WHERE n.nspname = 'public'
              AND c.relname = table_name
        LOOP
            EXECUTE format('DROP POLICY IF EXISTS %I ON public.%I', policy_name, table_name);
        END LOOP;

        EXECUTE format('ALTER TABLE public.%I DISABLE ROW LEVEL SECURITY', table_name);
    END LOOP;
END $$;

DROP FUNCTION IF EXISTS public.is_current_user_admin();
DROP FUNCTION IF EXISTS public.current_user_id();
DROP FUNCTION IF EXISTS public.current_request_role();
DROP FUNCTION IF EXISTS public.current_supabase_id();
"""


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    """Downgrade schema."""
    op.execute(DOWNGRADE_SQL)
