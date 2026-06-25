"""fix_trigger_function_search_paths

Revision ID: 26727bd6578d
Revises: d4e5f6a7b8c9
Create Date: 2026-06-25 12:19:28.212333

Add SET search_path = '' to prevent_listing_instructions_mutation, 
prevent_notifications_delete, and prevent_inquiry_replies_mutation trigger 
functions to close SQL injection vector where a caller could shadow system 
functions by manipulating the search path. This follows PREFLIGHT.md canonical 
rule 17 and the pattern already applied to prevent_agent_membership_audit_mutation 
in migration b5f9c2e8a014.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '26727bd6578d'
down_revision: Union[str, None] = 'd4e5f6a7b8c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Deployment reminder: PR descriptions must name this migration file, and
# production deploy order is `alembic upgrade head` before application code.

def upgrade() -> None:
    """Upgrade schema."""
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


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("""
        CREATE OR REPLACE FUNCTION public.prevent_listing_instructions_mutation()
          RETURNS trigger
          LANGUAGE plpgsql
          SECURITY DEFINER
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
        AS $$
        BEGIN
            RAISE EXCEPTION 'inquiry_replies is append-only';
        END;
        $$
    """)
