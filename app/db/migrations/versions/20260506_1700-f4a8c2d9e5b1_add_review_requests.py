"""Add generic agency review requests.

Revision ID: f4a8c2d9e5b1
Revises: d3e7c5a1b9f2
Create Date: 2026-05-06 17:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "f4a8c2d9e5b1"
down_revision = "d3e7c5a1b9f2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create agency-level review requests with pending uniqueness and RLS."""
    op.create_table(
        "review_requests",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("agency_id", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("actor_id", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "status IN ('pending', 'accepted', 'declined')",
            name="review_requests_status_check",
        ),
        sa.ForeignKeyConstraint(["actor_id"], ["users.user_id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["agency_id"], ["agencies.agency_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_review_requests_id", "review_requests", ["id"])
    op.create_index("ix_review_requests_user_id", "review_requests", ["user_id"])
    op.create_index("ix_review_requests_agency_id", "review_requests", ["agency_id"])
    op.create_index("ix_review_requests_status", "review_requests", ["status"])
    op.create_index("ix_review_requests_actor_id", "review_requests", ["actor_id"])
    op.execute(
        """
        CREATE UNIQUE INDEX uq_review_requests_pending_user_agency
        ON review_requests (user_id, agency_id)
        WHERE status = 'pending'
        """
    )

    op.execute("ALTER TABLE review_requests ENABLE ROW LEVEL SECURITY")
    op.execute("GRANT SELECT, INSERT, UPDATE ON review_requests TO authenticated")
    op.execute("GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO authenticated")
    op.execute(
        """
        CREATE POLICY review_requests_select_policy
        ON review_requests
        FOR SELECT
        TO authenticated
        USING (
            user_id = public.current_user_id()
            OR EXISTS (
                SELECT 1
                FROM users admin_user
                WHERE admin_user.user_id = public.current_user_id()
                  AND admin_user.deleted_at IS NULL
                  AND admin_user.is_admin = true
            )
            OR EXISTS (
                SELECT 1
                FROM users owner_user
                WHERE owner_user.user_id = public.current_user_id()
                  AND owner_user.deleted_at IS NULL
                  AND owner_user.user_role = 'agency_owner'::user_role_enum
                  AND owner_user.agency_id = review_requests.agency_id
            )
        )
        """
    )
    op.execute(
        """
        CREATE POLICY review_requests_insert_policy
        ON review_requests
        FOR INSERT
        TO authenticated
        WITH CHECK (user_id = public.current_user_id())
        """
    )
    op.execute(
        """
        CREATE POLICY review_requests_update_policy
        ON review_requests
        FOR UPDATE
        TO authenticated
        USING (
            EXISTS (
                SELECT 1
                FROM users admin_user
                WHERE admin_user.user_id = public.current_user_id()
                  AND admin_user.deleted_at IS NULL
                  AND admin_user.is_admin = true
            )
            OR EXISTS (
                SELECT 1
                FROM users owner_user
                WHERE owner_user.user_id = public.current_user_id()
                  AND owner_user.deleted_at IS NULL
                  AND owner_user.user_role = 'agency_owner'::user_role_enum
                  AND owner_user.agency_id = review_requests.agency_id
            )
        )
        WITH CHECK (
            EXISTS (
                SELECT 1
                FROM users admin_user
                WHERE admin_user.user_id = public.current_user_id()
                  AND admin_user.deleted_at IS NULL
                  AND admin_user.is_admin = true
            )
            OR EXISTS (
                SELECT 1
                FROM users owner_user
                WHERE owner_user.user_id = public.current_user_id()
                  AND owner_user.deleted_at IS NULL
                  AND owner_user.user_role = 'agency_owner'::user_role_enum
                  AND owner_user.agency_id = review_requests.agency_id
            )
        )
        """
    )


def downgrade() -> None:
    """Remove agency-level review requests."""
    op.execute("DROP POLICY IF EXISTS review_requests_update_policy ON review_requests")
    op.execute("DROP POLICY IF EXISTS review_requests_insert_policy ON review_requests")
    op.execute("DROP POLICY IF EXISTS review_requests_select_policy ON review_requests")
    op.execute("DROP INDEX IF EXISTS uq_review_requests_pending_user_agency")
    op.drop_index("ix_review_requests_actor_id", table_name="review_requests")
    op.drop_index("ix_review_requests_status", table_name="review_requests")
    op.drop_index("ix_review_requests_agency_id", table_name="review_requests")
    op.drop_index("ix_review_requests_user_id", table_name="review_requests")
    op.drop_index("ix_review_requests_id", table_name="review_requests")
    op.drop_table("review_requests")
