"""Phase N N.1: create listing_instructions table

Revision ID: a1b2c3d4e5f6
Revises: f0a1b2c3d4e5
Create Date: 2026-06-14 14:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "f0a1b2c3d4e5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "listing_instructions",
        sa.Column("instruction_id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("listing_id", sa.BigInteger(), nullable=False),
        sa.Column("agency_id", sa.BigInteger(), nullable=False),
        sa.Column("actor_id", sa.BigInteger(), nullable=False),
        sa.Column("triggered_by_event_id", sa.BigInteger(), nullable=False),
        sa.Column("instruction_text", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["listing_id"], ["properties.property_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["agency_id"], ["agencies.agency_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["actor_id"], ["users.user_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["triggered_by_event_id"], ["listing_events.event_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("instruction_id"),
    )
    op.create_index("ix_listing_instructions_listing_id", "listing_instructions", ["listing_id"])
    op.create_index("ix_listing_instructions_agency_id", "listing_instructions", ["agency_id"])
    op.create_index("ix_listing_instructions_actor_id", "listing_instructions", ["actor_id"])
    op.create_index("ix_listing_instructions_triggered_by_event_id", "listing_instructions", ["triggered_by_event_id"])

    op.execute("ALTER TABLE listing_instructions ENABLE ROW LEVEL SECURITY")
    op.execute("GRANT SELECT, INSERT ON listing_instructions TO authenticated")
    op.execute("GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO authenticated")

    op.execute(
        """
        CREATE POLICY listing_instructions_select_policy
        ON listing_instructions
        FOR SELECT
        TO authenticated
        USING (
            EXISTS (
                SELECT 1 FROM properties p
                WHERE p.property_id = listing_instructions.listing_id
                AND (
                    p.user_id = public.current_user_id()
                    OR EXISTS (
                        SELECT 1 FROM users u
                        WHERE u.user_id = public.current_user_id()
                        AND u.deleted_at IS NULL
                        AND u.user_role = 'admin'::user_role_enum
                    )
                    OR (
                        EXISTS (
                            SELECT 1 FROM users u
                            WHERE u.user_id = public.current_user_id()
                            AND u.deleted_at IS NULL
                            AND u.user_role = 'agency_owner'::user_role_enum
                            AND u.agency_id = listing_instructions.agency_id
                        )
                    )
                )
            )
        )
        """
    )
    op.execute(
        """
        CREATE POLICY listing_instructions_insert_policy
        ON listing_instructions
        FOR INSERT
        TO authenticated
        WITH CHECK (
            EXISTS (
                SELECT 1 FROM users u
                WHERE u.user_id = public.current_user_id()
                AND u.deleted_at IS NULL
                AND u.user_role = 'agency_owner'::user_role_enum
                AND u.agency_id = listing_instructions.agency_id
            )
        )
        """
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION prevent_listing_instructions_mutation()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            RAISE EXCEPTION 'listing_instructions is append-only';
        END;
        $$;
        """
    )
    op.execute(
        """
        CREATE TRIGGER prevent_listing_instructions_update
        BEFORE UPDATE ON listing_instructions
        FOR EACH ROW EXECUTE FUNCTION prevent_listing_instructions_mutation()
        """
    )
    op.execute(
        """
        CREATE TRIGGER prevent_listing_instructions_delete
        BEFORE DELETE ON listing_instructions
        FOR EACH ROW EXECUTE FUNCTION prevent_listing_instructions_mutation()
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS prevent_listing_instructions_delete ON listing_instructions")
    op.execute("DROP TRIGGER IF EXISTS prevent_listing_instructions_update ON listing_instructions")
    op.execute("DROP FUNCTION IF EXISTS prevent_listing_instructions_mutation()")
    op.drop_index("ix_listing_instructions_listing_id", table_name="listing_instructions")
    op.drop_index("ix_listing_instructions_agency_id", table_name="listing_instructions")
    op.drop_index("ix_listing_instructions_actor_id", table_name="listing_instructions")
    op.drop_index("ix_listing_instructions_triggered_by_event_id", table_name="listing_instructions")
    op.drop_table("listing_instructions")
