"""phase_s_s1_internal_schema_migration

Move three append-only trigger enforcement functions from public to internal
schema, resolving the Supabase advisor EXECUTE warnings permanently. The
internal schema is invisible to the PostgREST REST API by design.

Functions moved:
  public.prevent_listing_instructions_mutation
    -> internal.prevent_listing_instructions_mutation
  public.prevent_notifications_delete
    -> internal.prevent_notifications_delete
  public.prevent_inquiry_replies_mutation
    -> internal.prevent_inquiry_replies_mutation

Triggers on the corresponding public tables are updated to reference the
internal schema functions. The public schema function versions are dropped.

See PREFLIGHT.md PostgREST Schema Topology Standard for the canonical pattern.

Revision ID: f7f8c6a12f4a
Revises: 3a7b9c1d2e4f
Create Date: 2026-06-26 12:29:12.134453

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'f7f8c6a12f4a'
down_revision: Union[str, None] = '3a7b9c1d2e4f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Move trigger enforcement functions from public to internal schema."""

    # 1. Create internal schema (idempotent)
    op.execute("CREATE SCHEMA IF NOT EXISTS internal;")

    # 2. Recreate each function in internal schema with SET search_path = ''
    op.execute("""
        CREATE OR REPLACE FUNCTION internal.prevent_listing_instructions_mutation()
          RETURNS trigger
          LANGUAGE plpgsql
          SECURITY DEFINER
          SET search_path = ''
        AS $$
        BEGIN
            RAISE EXCEPTION 'listing_instructions is append-only';
        END;
        $$
    """)

    op.execute("""
        CREATE OR REPLACE FUNCTION internal.prevent_notifications_delete()
          RETURNS trigger
          LANGUAGE plpgsql
          SECURITY DEFINER
          SET search_path = ''
        AS $$
        BEGIN
            RAISE EXCEPTION 'notifications is append-only; deletion is not allowed';
        END;
        $$
    """)

    op.execute("""
        CREATE OR REPLACE FUNCTION internal.prevent_inquiry_replies_mutation()
          RETURNS trigger
          LANGUAGE plpgsql
          SECURITY DEFINER
          SET search_path = ''
        AS $$
        BEGIN
            RAISE EXCEPTION 'inquiry_replies is append-only';
        END;
        $$
    """)

    # 3. Update triggers to reference internal schema functions
    op.execute("""
        CREATE OR REPLACE TRIGGER prevent_listing_instructions_mutation
          BEFORE UPDATE OR DELETE ON public.listing_instructions
          FOR EACH ROW EXECUTE FUNCTION internal.prevent_listing_instructions_mutation();
    """)

    op.execute("""
        CREATE OR REPLACE TRIGGER prevent_notifications_delete
          BEFORE UPDATE OR DELETE ON public.notifications
          FOR EACH ROW EXECUTE FUNCTION internal.prevent_notifications_delete();
    """)

    op.execute("""
        CREATE OR REPLACE TRIGGER prevent_inquiry_replies_mutation
          BEFORE UPDATE OR DELETE ON public.inquiry_replies
          FOR EACH ROW EXECUTE FUNCTION internal.prevent_inquiry_replies_mutation();
    """)

    # 4. Drop public schema versions (no longer needed)
    op.execute("DROP FUNCTION IF EXISTS public.prevent_listing_instructions_mutation();")
    op.execute("DROP FUNCTION IF EXISTS public.prevent_notifications_delete();")
    op.execute("DROP FUNCTION IF EXISTS public.prevent_inquiry_replies_mutation();")


def downgrade() -> None:
    """Restore trigger enforcement functions from internal back to public schema."""

    # 1. Recreate functions in public schema (restoring the state before this migration)
    op.execute("""
        CREATE OR REPLACE FUNCTION public.prevent_listing_instructions_mutation()
          RETURNS trigger
          LANGUAGE plpgsql
          SECURITY DEFINER
          SET search_path = ''
        AS $$
        BEGIN
            RAISE EXCEPTION 'listing_instructions is append-only';
        END;
        $$
    """)

    op.execute("""
        CREATE OR REPLACE FUNCTION public.prevent_notifications_delete()
          RETURNS trigger
          LANGUAGE plpgsql
          SECURITY DEFINER
          SET search_path = ''
        AS $$
        BEGIN
            RAISE EXCEPTION 'notifications is append-only; deletion is not allowed';
        END;
        $$
    """)

    op.execute("""
        CREATE OR REPLACE FUNCTION public.prevent_inquiry_replies_mutation()
          RETURNS trigger
          LANGUAGE plpgsql
          SECURITY DEFINER
          SET search_path = ''
        AS $$
        BEGIN
            RAISE EXCEPTION 'inquiry_replies is append-only';
        END;
        $$
    """)

    # 2. Update triggers to reference public schema functions
    op.execute("""
        CREATE OR REPLACE TRIGGER prevent_listing_instructions_mutation
          BEFORE UPDATE OR DELETE ON public.listing_instructions
          FOR EACH ROW EXECUTE FUNCTION public.prevent_listing_instructions_mutation();
    """)

    op.execute("""
        CREATE OR REPLACE TRIGGER prevent_notifications_delete
          BEFORE UPDATE OR DELETE ON public.notifications
          FOR EACH ROW EXECUTE FUNCTION public.prevent_notifications_delete();
    """)

    op.execute("""
        CREATE OR REPLACE TRIGGER prevent_inquiry_replies_mutation
          BEFORE UPDATE OR DELETE ON public.inquiry_replies
          FOR EACH ROW EXECUTE FUNCTION public.prevent_inquiry_replies_mutation();
    """)

    # 3. Drop internal schema function versions
    op.execute("DROP FUNCTION IF EXISTS internal.prevent_listing_instructions_mutation();")
    op.execute("DROP FUNCTION IF EXISTS internal.prevent_notifications_delete();")
    op.execute("DROP FUNCTION IF EXISTS internal.prevent_inquiry_replies_mutation();")
