"""add agency invitations

Revision ID: c8f3b2a91e44
Revises: b84c3e9a7d21
Create Date: 2026-04-29 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c8f3b2a91e44"
down_revision: Union[str, None] = "b84c3e9a7d21"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create persistent agency invitation records."""
    op.create_table(
        "agency_invitations",
        sa.Column("invitation_id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("agency_id", sa.BigInteger(), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("invited_user_id", sa.BigInteger(), nullable=True),
        sa.Column("status", sa.String(), server_default=sa.text("'pending'"), nullable=False),
        sa.Column("token_hash", sa.String(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("updated_by", sa.UUID(), nullable=True),
        sa.Column("deleted_by", sa.UUID(), nullable=True),
        sa.CheckConstraint(
            "status IN ('pending', 'accepted', 'rejected', 'expired', 'revoked')",
            name="agency_invitations_status_check",
        ),
        sa.ForeignKeyConstraint(["agency_id"], ["agencies.agency_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["invited_user_id"], ["users.user_id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("invitation_id"),
    )
    op.create_index(op.f("ix_agency_invitations_invitation_id"), "agency_invitations", ["invitation_id"], unique=False)
    op.create_index(op.f("ix_agency_invitations_agency_id"), "agency_invitations", ["agency_id"], unique=False)
    op.create_index(op.f("ix_agency_invitations_email"), "agency_invitations", ["email"], unique=False)
    op.create_index(op.f("ix_agency_invitations_invited_user_id"), "agency_invitations", ["invited_user_id"], unique=False)
    op.create_index(op.f("ix_agency_invitations_token_hash"), "agency_invitations", ["token_hash"], unique=False)
    op.execute(
        """
        CREATE UNIQUE INDEX uq_agency_invitations_pending_agency_email
        ON agency_invitations (agency_id, lower(email))
        WHERE status = 'pending' AND deleted_at IS NULL
        """
    )

    op.execute("ALTER TABLE agency_invitations ENABLE ROW LEVEL SECURITY")
    op.execute("GRANT SELECT, INSERT, UPDATE ON agency_invitations TO authenticated")
    op.execute(
        """
        CREATE POLICY agency_invitations_select_relevant
        ON agency_invitations
        FOR SELECT
        TO authenticated
        USING (
            invited_user_id = public.current_user_id()
            OR lower(email) IN (
                SELECT lower(users.email)
                FROM users
                WHERE users.user_id = public.current_user_id()
                  AND users.deleted_at IS NULL
            )
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
        CREATE POLICY agency_invitations_insert_owner
        ON agency_invitations
        FOR INSERT
        TO authenticated
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
    op.execute(
        """
        CREATE POLICY agency_invitations_update_relevant
        ON agency_invitations
        FOR UPDATE
        TO authenticated
        USING (
            invited_user_id = public.current_user_id()
            OR lower(email) IN (
                SELECT lower(users.email)
                FROM users
                WHERE users.user_id = public.current_user_id()
                  AND users.deleted_at IS NULL
            )
            OR agency_id IN (
                SELECT users.agency_id
                FROM users
                WHERE users.supabase_id = auth.uid()
                  AND users.user_role::text IN ('agency_owner', 'admin')
                  AND users.deleted_at IS NULL
            )
        )
        WITH CHECK (
            invited_user_id = public.current_user_id()
            OR lower(email) IN (
                SELECT lower(users.email)
                FROM users
                WHERE users.user_id = public.current_user_id()
                  AND users.deleted_at IS NULL
            )
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


def downgrade() -> None:
    """Drop persistent agency invitation records."""
    op.execute("DROP POLICY IF EXISTS agency_invitations_update_relevant ON agency_invitations")
    op.execute("DROP POLICY IF EXISTS agency_invitations_insert_owner ON agency_invitations")
    op.execute("DROP POLICY IF EXISTS agency_invitations_select_relevant ON agency_invitations")
    op.execute("DROP INDEX IF EXISTS uq_agency_invitations_pending_agency_email")
    op.drop_index(op.f("ix_agency_invitations_token_hash"), table_name="agency_invitations")
    op.drop_index(op.f("ix_agency_invitations_invited_user_id"), table_name="agency_invitations")
    op.drop_index(op.f("ix_agency_invitations_email"), table_name="agency_invitations")
    op.drop_index(op.f("ix_agency_invitations_agency_id"), table_name="agency_invitations")
    op.drop_index(op.f("ix_agency_invitations_invitation_id"), table_name="agency_invitations")
    op.drop_table("agency_invitations")
