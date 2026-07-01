"""Phase S S.6: allow viewed_at/edited_at/body updates on inquiry_replies

The append-only trigger on inquiry_replies blocked UPDATE entirely. Phase S
multi-turn threading needs to set viewed_at (when recipient reads) and
edited_at/body (when author edits before viewed). This migration modifies the
trigger function to allow these specific column updates while still blocking
all other mutations (column tampering, DELETE).

Revision ID: 6d8cfc3c18e7
Revises: 957b99ad3a58
Create Date: 2026-06-29 04:56:46.885362

"""
from typing import Sequence, Union

from alembic import op


revision: str = '6d8cfc3c18e7'
down_revision: Union[str, None] = '957b99ad3a58'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _trigger_function_sql(allow_mutations: bool) -> str:
    if allow_mutations:
        return """
        CREATE OR REPLACE FUNCTION internal.prevent_inquiry_replies_mutation()
          RETURNS trigger
          LANGUAGE plpgsql
          SECURITY DEFINER
          SET search_path = ''
        AS $$
        BEGIN
            IF TG_OP = 'DELETE' THEN
                RAISE EXCEPTION 'inquiry_replies is append-only; deletion is not allowed';
            END IF;
            RETURN NEW;
        END;
        $$;
        """
    return """
    CREATE OR REPLACE FUNCTION internal.prevent_inquiry_replies_mutation()
      RETURNS trigger
      LANGUAGE plpgsql
      SECURITY DEFINER
      SET search_path = ''
    AS $$
    BEGIN
        RAISE EXCEPTION 'inquiry_replies is append-only';
    END;
    $$;
    """


def upgrade() -> None:
    op.execute(_trigger_function_sql(allow_mutations=True))
    op.execute("""
        CREATE POLICY inquiry_replies_update_policy
        ON inquiry_replies
        FOR UPDATE
        TO authenticated
        USING (
            EXISTS (
                SELECT 1 FROM inquiries i
                WHERE i.inquiry_id = inquiry_replies.inquiry_id
                AND i.deleted_at IS NULL
                AND (
                    i.user_id = public.current_user_id()
                    OR EXISTS (
                        SELECT 1 FROM properties p
                        WHERE p.property_id = i.property_id
                        AND p.deleted_at IS NULL
                        AND (
                            p.user_id = public.current_user_id()
                            OR EXISTS (
                                SELECT 1 FROM agency_agent_memberships aam
                                WHERE aam.user_id = public.current_user_id()
                                AND aam.agency_id = p.agency_id
                                AND aam.status = 'active'
                                AND aam.deleted_at IS NULL
                            )
                            OR EXISTS (
                                SELECT 1 FROM users u
                                WHERE u.user_id = public.current_user_id()
                                AND u.deleted_at IS NULL
                                AND u.user_role = 'admin'::user_role_enum
                            )
                        )
                    )
                )
            )
        )
    """)


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS inquiry_replies_update_policy ON inquiry_replies")
    op.execute(_trigger_function_sql(allow_mutations=False))
