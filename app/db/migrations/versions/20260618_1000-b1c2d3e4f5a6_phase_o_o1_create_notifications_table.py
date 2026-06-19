"""Phase O O.1: create notifications table

Revision ID: b1c2d3e4f5a6
Revises: a1b2c3d4e5f6
Create Date: 2026-06-18 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b1c2d3e4f5a6"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "notifications",
        sa.Column("notification_id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("listing_id", sa.BigInteger(), nullable=True),
        sa.Column("body_text", sa.Text(), nullable=False),
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["listing_id"], ["properties.property_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("notification_id"),
    )
    op.create_index("ix_notifications_user_id", "notifications", ["user_id"])
    op.create_index("ix_notifications_created_at", "notifications", ["created_at"])
    op.create_index("ix_notifications_listing_id", "notifications", ["listing_id"])

    op.execute("ALTER TABLE notifications ENABLE ROW LEVEL SECURITY")
    op.execute("GRANT SELECT, INSERT, UPDATE ON notifications TO authenticated")
    op.execute("GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO authenticated")

    op.execute(
        """
        CREATE POLICY notifications_select_policy
        ON notifications
        FOR SELECT
        TO authenticated
        USING (user_id = public.current_user_id())
        """
    )
    op.execute(
        """
        CREATE POLICY notifications_insert_policy
        ON notifications
        FOR INSERT
        TO authenticated
        WITH CHECK (user_id = public.current_user_id())
        """
    )
    op.execute(
        """
        CREATE POLICY notifications_update_policy
        ON notifications
        FOR UPDATE
        TO authenticated
        USING (user_id = public.current_user_id())
        WITH CHECK (user_id = public.current_user_id())
        """
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION prevent_notifications_delete()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            RAISE EXCEPTION 'notifications is append-only; deletion is not allowed';
        END;
        $$;
        """
    )
    op.execute(
        """
        CREATE TRIGGER prevent_notifications_delete
        BEFORE DELETE ON notifications
        FOR EACH ROW EXECUTE FUNCTION prevent_notifications_delete()
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS prevent_notifications_delete ON notifications")
    op.execute("DROP FUNCTION IF EXISTS prevent_notifications_delete()")
    op.drop_index("ix_notifications_user_id", table_name="notifications")
    op.drop_index("ix_notifications_created_at", table_name="notifications")
    op.drop_index("ix_notifications_listing_id", table_name="notifications")
    op.drop_table("notifications")
