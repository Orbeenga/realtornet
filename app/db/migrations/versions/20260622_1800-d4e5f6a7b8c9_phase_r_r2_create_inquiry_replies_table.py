"""Phase R R.2: create inquiry_replies table

Revision ID: d4e5f6a7b8c9
Revises: d3e4f5a6b7c8
Create Date: 2026-06-22 18:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, None] = "d3e4f5a6b7c8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "inquiry_replies",
        sa.Column("reply_id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("inquiry_id", sa.BigInteger(), nullable=False),
        sa.Column("author_id", sa.BigInteger(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("viewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("edited_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["inquiry_id"], ["inquiries.inquiry_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["author_id"], ["users.user_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("reply_id"),
    )
    op.create_index("ix_inquiry_replies_inquiry_id", "inquiry_replies", ["inquiry_id"])
    op.create_index("ix_inquiry_replies_author_id", "inquiry_replies", ["author_id"])

    op.execute("ALTER TABLE inquiry_replies ENABLE ROW LEVEL SECURITY")
    op.execute("GRANT SELECT, INSERT ON inquiry_replies TO authenticated")
    op.execute("GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO authenticated")

    op.execute(
        """
        CREATE POLICY inquiry_replies_select_policy
        ON inquiry_replies
        FOR SELECT
        TO authenticated
        USING (
            EXISTS (
                SELECT 1 FROM inquiries i
                WHERE i.inquiry_id = inquiry_replies.inquiry_id
                AND (
                    i.user_id = public.current_user_id()
                    OR EXISTS (
                        SELECT 1 FROM properties p
                        WHERE p.property_id = i.property_id
                        AND p.deleted_at IS NULL
                        AND (
                            p.user_id = public.current_user_id()
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
        """
    )
    op.execute(
        """
        CREATE POLICY inquiry_replies_insert_policy
        ON inquiry_replies
        FOR INSERT
        TO authenticated
        WITH CHECK (
            EXISTS (
                SELECT 1 FROM inquiries i
                JOIN properties p ON p.property_id = i.property_id
                WHERE i.inquiry_id = inquiry_replies.inquiry_id
                AND i.deleted_at IS NULL
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
        """
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION prevent_inquiry_replies_mutation()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            RAISE EXCEPTION 'inquiry_replies is append-only';
        END;
        $$;
        """
    )
    op.execute(
        """
        CREATE TRIGGER prevent_inquiry_replies_update
        BEFORE UPDATE ON inquiry_replies
        FOR EACH ROW EXECUTE FUNCTION prevent_inquiry_replies_mutation()
        """
    )
    op.execute(
        """
        CREATE TRIGGER prevent_inquiry_replies_delete
        BEFORE DELETE ON inquiry_replies
        FOR EACH ROW EXECUTE FUNCTION prevent_inquiry_replies_mutation()
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS prevent_inquiry_replies_delete ON inquiry_replies")
    op.execute("DROP TRIGGER IF EXISTS prevent_inquiry_replies_update ON inquiry_replies")
    op.execute("DROP FUNCTION IF EXISTS prevent_inquiry_replies_mutation()")
    op.drop_index("ix_inquiry_replies_inquiry_id", table_name="inquiry_replies")
    op.drop_index("ix_inquiry_replies_author_id", table_name="inquiry_replies")
    op.drop_table("inquiry_replies")
