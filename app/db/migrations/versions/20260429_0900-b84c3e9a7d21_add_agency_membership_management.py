"""add agency membership management

Revision ID: b84c3e9a7d21
Revises: a1c9e7d4b832
Create Date: 2026-04-29 09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b84c3e9a7d21"
down_revision: Union[str, None] = "a1c9e7d4b832"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add auditable membership actions and agent review requests."""
    op.add_column("agency_agent_memberships", sa.Column("status_reason", sa.Text(), nullable=True))
    op.add_column(
        "agency_agent_memberships",
        sa.Column("status_decided_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column("agency_agent_memberships", sa.Column("status_decided_by", sa.BigInteger(), nullable=True))
    op.create_foreign_key(
        op.f("fk_agency_agent_memberships_status_decided_by_users"),
        "agency_agent_memberships",
        "users",
        ["status_decided_by"],
        ["user_id"],
        ondelete="SET NULL",
    )
    op.execute(
        """
        ALTER TABLE agency_agent_memberships
        DROP CONSTRAINT IF EXISTS agency_agent_memberships_status_check
        """
    )
    op.execute(
        """
        ALTER TABLE agency_agent_memberships
        DROP CONSTRAINT IF EXISTS ck_agency_agent_memberships_agency_agent_memberships_status_check
        """
    )
    op.execute(
        """
        ALTER TABLE agency_agent_memberships
        ADD CONSTRAINT agency_agent_memberships_status_check
        CHECK (status IN ('active', 'inactive', 'suspended', 'blocked'))
        """
    )

    op.create_table(
        "agency_membership_review_requests",
        sa.Column("review_request_id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("membership_id", sa.BigInteger(), nullable=False),
        sa.Column("agency_id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(), server_default=sa.text("'pending'"), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("response_reason", sa.Text(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decided_by", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("updated_by", sa.UUID(), nullable=True),
        sa.Column("deleted_by", sa.UUID(), nullable=True),
        sa.CheckConstraint(
            "status IN ('pending', 'reviewed', 'approved', 'rejected')",
            name="agency_membership_review_requests_status_check",
        ),
        sa.ForeignKeyConstraint(["agency_id"], ["agencies.agency_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["decided_by"], ["users.user_id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["membership_id"], ["agency_agent_memberships.membership_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("review_request_id"),
    )
    op.create_index(
        op.f("ix_agency_membership_review_requests_review_request_id"),
        "agency_membership_review_requests",
        ["review_request_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_agency_membership_review_requests_membership_id"),
        "agency_membership_review_requests",
        ["membership_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_agency_membership_review_requests_agency_id"),
        "agency_membership_review_requests",
        ["agency_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_agency_membership_review_requests_user_id"),
        "agency_membership_review_requests",
        ["user_id"],
        unique=False,
    )

    op.execute("ALTER TABLE agency_membership_review_requests ENABLE ROW LEVEL SECURITY")
    op.execute("GRANT SELECT, INSERT, UPDATE ON agency_membership_review_requests TO authenticated")
    op.execute(
        """
        CREATE POLICY agency_membership_review_requests_select_policy
        ON agency_membership_review_requests
        FOR SELECT
        TO authenticated
        USING (
            user_id = public.current_user_id()
            OR agency_id IN (
                SELECT users.agency_id
                FROM users
                WHERE users.supabase_id = auth.uid()
                  AND users.user_role::text IN ('agency_owner', 'admin')
                  AND users.deleted_at IS NULL
            )
        )
        """
    )
    op.execute(
        """
        CREATE POLICY agency_membership_review_requests_insert_policy
        ON agency_membership_review_requests
        FOR INSERT
        TO authenticated
        WITH CHECK (user_id = public.current_user_id())
        """
    )
    op.execute(
        """
        CREATE POLICY agency_membership_review_requests_update_policy
        ON agency_membership_review_requests
        FOR UPDATE
        TO authenticated
        USING (
            agency_id IN (
                SELECT users.agency_id
                FROM users
                WHERE users.supabase_id = auth.uid()
                  AND users.user_role::text IN ('agency_owner', 'admin')
                  AND users.deleted_at IS NULL
            )
        )
        WITH CHECK (
            agency_id IN (
                SELECT users.agency_id
                FROM users
                WHERE users.supabase_id = auth.uid()
                  AND users.user_role::text IN ('agency_owner', 'admin')
                  AND users.deleted_at IS NULL
            )
        )
        """
    )


def downgrade() -> None:
    """Remove auditable membership actions and agent review requests."""
    op.execute("DROP POLICY IF EXISTS agency_membership_review_requests_update_policy ON agency_membership_review_requests")
    op.execute("DROP POLICY IF EXISTS agency_membership_review_requests_insert_policy ON agency_membership_review_requests")
    op.execute("DROP POLICY IF EXISTS agency_membership_review_requests_select_policy ON agency_membership_review_requests")
    op.drop_index(
        op.f("ix_agency_membership_review_requests_user_id"),
        table_name="agency_membership_review_requests",
    )
    op.drop_index(
        op.f("ix_agency_membership_review_requests_agency_id"),
        table_name="agency_membership_review_requests",
    )
    op.drop_index(
        op.f("ix_agency_membership_review_requests_membership_id"),
        table_name="agency_membership_review_requests",
    )
    op.drop_index(
        op.f("ix_agency_membership_review_requests_review_request_id"),
        table_name="agency_membership_review_requests",
    )
    op.drop_table("agency_membership_review_requests")

    op.execute(
        """
        ALTER TABLE agency_agent_memberships
        DROP CONSTRAINT IF EXISTS agency_agent_memberships_status_check
        """
    )
    op.execute(
        """
        ALTER TABLE agency_agent_memberships
        ADD CONSTRAINT agency_agent_memberships_status_check
        CHECK (status IN ('active', 'inactive', 'suspended'))
        """
    )
    op.drop_constraint(
        op.f("fk_agency_agent_memberships_status_decided_by_users"),
        "agency_agent_memberships",
        type_="foreignkey",
    )
    op.drop_column("agency_agent_memberships", "status_decided_by")
    op.drop_column("agency_agent_memberships", "status_decided_at")
    op.drop_column("agency_agent_memberships", "status_reason")
