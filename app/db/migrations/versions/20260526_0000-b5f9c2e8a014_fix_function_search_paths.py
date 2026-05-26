"""Fix mutable search_path on all 5 custom PL/pgSQL functions

Revision ID: b5f9c2e8a014
Revises: 20260524_0000
Create Date: 2026-05-26 00:00:00.000000

Adds SET search_path = '' to each SECURITY DEFINER / stable helper function
to close the SQL injection vector where a caller could shadow system functions
by manipulating the search path.

Functions patched:
  - public.current_supabase_id()
  - public.current_request_role()
  - public.current_user_id()
  - public.is_current_user_admin()
  - public.prevent_agent_membership_audit_mutation()
"""
from alembic import op


# revision identifiers, used by Alembic.
revision = 'b5f9c2e8a014'
down_revision = '20260524_0000'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE OR REPLACE FUNCTION public.current_supabase_id()
        RETURNS uuid
        LANGUAGE plpgsql
        STABLE
        SET search_path = ''
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
        $function$
    """)

    op.execute("""
        CREATE OR REPLACE FUNCTION public.current_request_role()
        RETURNS text
        LANGUAGE plpgsql
        STABLE
        SET search_path = ''
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
        $function$
    """)

    op.execute("""
        CREATE OR REPLACE FUNCTION public.current_user_id()
        RETURNS bigint
        LANGUAGE plpgsql
        STABLE
        SET search_path = ''
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
        $function$
    """)

    op.execute("""
        CREATE OR REPLACE FUNCTION public.is_current_user_admin()
        RETURNS boolean
        LANGUAGE sql
        STABLE
        SET search_path = ''
        AS $function$
            SELECT COALESCE(public.current_request_role() = 'admin', false);
        $function$
    """)

    op.execute("""
        CREATE OR REPLACE FUNCTION public.prevent_agent_membership_audit_mutation()
        RETURNS trigger
        LANGUAGE plpgsql
        SET search_path = ''
        AS $$
        BEGIN
            RAISE EXCEPTION 'agent_membership_audit is append-only';
        END;
        $$
    """)


def downgrade() -> None:
    op.execute("""
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
        $function$
    """)

    op.execute("""
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
        $function$
    """)

    op.execute("""
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
        $function$
    """)

    op.execute("""
        CREATE OR REPLACE FUNCTION public.is_current_user_admin()
        RETURNS boolean
        LANGUAGE sql
        STABLE
        AS $function$
            SELECT COALESCE(public.current_request_role() = 'admin', false);
        $function$
    """)

    op.execute("""
        CREATE OR REPLACE FUNCTION public.prevent_agent_membership_audit_mutation()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            RAISE EXCEPTION 'agent_membership_audit is append-only';
        END;
        $$
    """)
