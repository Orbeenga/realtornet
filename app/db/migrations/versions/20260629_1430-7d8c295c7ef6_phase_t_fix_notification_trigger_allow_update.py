"""Phase T: fix notification trigger to allow UPDATE for mark_as_read

The S.1 internal schema migration (f7f8c6a12f4a) changed the
prevent_notifications_delete trigger from BEFORE DELETE to BEFORE
UPDATE OR DELETE.  This blocked PATCH /notifications/{id}/read and
PATCH /notifications/read-all in production.

Following the same pattern as S.6 (6d8cfc3c18e7) for inquiry_replies:
the trigger function now allows UPDATE and blocks only DELETE.

Revision ID: 7d8c295c7ef6
Revises: 6d8cfc3c18e7
Create Date: 2026-06-29 14:30:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = '7d8c295c7ef6'
down_revision: Union[str, None] = '6d8cfc3c18e7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE OR REPLACE FUNCTION internal.prevent_notifications_delete()
          RETURNS trigger
          LANGUAGE plpgsql
          SECURITY DEFINER
          SET search_path = ''
        AS $$
        BEGIN
            IF TG_OP = 'DELETE' THEN
                RAISE EXCEPTION 'notifications is append-only; deletion is not allowed';
            END IF;
            RETURN NEW;
        END;
        $$;
    """)


def downgrade() -> None:
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
        $$;
    """)
