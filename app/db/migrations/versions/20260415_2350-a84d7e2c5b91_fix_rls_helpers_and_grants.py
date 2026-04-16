"""fix rls helpers and grants

Revision ID: a84d7e2c5b91
Revises: 9f2b7c1d4a10
Create Date: 2026-04-15 23:50:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "a84d7e2c5b91"
down_revision: Union[str, None] = "9f2b7c1d4a10"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


UPGRADE_SQL = """
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

GRANT USAGE ON SCHEMA public TO anon, authenticated;
GRANT SELECT ON public.agencies, public.agent_profiles, public.amenities, public.locations, public.properties, public.property_amenities, public.property_images, public.property_types, public.reviews, public.users TO anon, authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.agencies, public.agent_profiles, public.amenities, public.favorites, public.inquiries, public.locations, public.profiles, public.properties, public.property_amenities, public.property_images, public.property_types, public.reviews, public.saved_searches, public.users TO authenticated;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO authenticated;
"""


DOWNGRADE_SQL = """
REVOKE USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public FROM authenticated;
REVOKE SELECT, INSERT, UPDATE, DELETE ON public.agencies, public.agent_profiles, public.amenities, public.favorites, public.inquiries, public.locations, public.profiles, public.properties, public.property_amenities, public.property_images, public.property_types, public.reviews, public.saved_searches, public.users FROM authenticated;
REVOKE SELECT ON public.agencies, public.agent_profiles, public.amenities, public.locations, public.properties, public.property_amenities, public.property_images, public.property_types, public.reviews, public.users FROM anon, authenticated;
REVOKE USAGE ON SCHEMA public FROM anon, authenticated;
"""


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    """Downgrade schema."""
    op.execute(DOWNGRADE_SQL)
