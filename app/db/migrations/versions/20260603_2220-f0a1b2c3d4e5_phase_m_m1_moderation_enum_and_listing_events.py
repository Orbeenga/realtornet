"""Phase M M.1: expand moderation_status_enum and add listing_events.

Revision ID: f0a1b2c3d4e5
Revises: d8a5015d8792
Create Date: 2026-06-03 22:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "f0a1b2c3d4e5"
down_revision: Union[str, None] = "d8a5015d8792"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Expand moderation_status_enum for Phase M and create listing_events.

    Notes:
    - ALTER TYPE ... ADD VALUE cannot run inside a transaction block, so this
      migration uses an explicit COMMIT before altering the enum.
    - Existing enum values (pending_review, agency_approved, verified, rejected,
      revoked) are preserved for backward-compatible reads and data migrations.
    """

    # Commit the current transaction so ALTER TYPE can run.
    op.execute("COMMIT")

    # Add new Phase M moderation states.
    op.execute("ALTER TYPE moderation_status_enum ADD VALUE IF NOT EXISTS 'draft' BEFORE 'pending_review'")
    op.execute("ALTER TYPE moderation_status_enum ADD VALUE IF NOT EXISTS 'agency_review' AFTER 'draft'")
    op.execute("ALTER TYPE moderation_status_enum ADD VALUE IF NOT EXISTS 'agency_rejected' AFTER 'agency_review'")
    op.execute("ALTER TYPE moderation_status_enum ADD VALUE IF NOT EXISTS 'admin_review' AFTER 'agency_rejected'")
    op.execute("ALTER TYPE moderation_status_enum ADD VALUE IF NOT EXISTS 'admin_rejected' AFTER 'admin_review'")
    op.execute("ALTER TYPE moderation_status_enum ADD VALUE IF NOT EXISTS 'live'")

    # Change default moderation_status for new properties to draft.
    op.execute(
        "ALTER TABLE properties ALTER COLUMN moderation_status SET DEFAULT 'draft'::moderation_status_enum"
    )

    # Create listing_events append-only audit table for listing state transitions.
    op.create_table(
        "listing_events",
        sa.Column("event_id", sa.BigInteger(), sa.Identity(always=False), primary_key=True),
        sa.Column("listing_id", sa.BigInteger(), nullable=False),
        sa.Column("actor_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "from_status",
            postgresql.ENUM(
                "draft",
                "agency_review",
                "agency_rejected",
                "admin_review",
                "admin_rejected",
                "live",
                "pending_review",
                "agency_approved",
                "verified",
                "rejected",
                "revoked",
                name="moderation_status_enum",
                create_type=False,
            ),
            nullable=True,
        ),
        sa.Column(
            "to_status",
            postgresql.ENUM(
                "draft",
                "agency_review",
                "agency_rejected",
                "admin_review",
                "admin_rejected",
                "live",
                "pending_review",
                "agency_approved",
                "verified",
                "rejected",
                "revoked",
                name="moderation_status_enum",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["listing_id"], ["properties.property_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["actor_id"], ["users.user_id"], ondelete="SET NULL"),
    )

    op.create_index("ix_listing_events_listing_id", "listing_events", ["listing_id"])
    op.create_index("ix_listing_events_actor_id", "listing_events", ["actor_id"])
    op.create_index("ix_listing_events_created_at", "listing_events", ["created_at"])

    # Enable RLS and grant read access; table is append-only from the application side.
    op.execute("ALTER TABLE listing_events ENABLE ROW LEVEL SECURITY")
    op.execute("GRANT SELECT ON listing_events TO authenticated")
    op.execute("GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO authenticated")

    # RLS policy: agents see their own listing events; agency owners see events
    # for listings in their agency; admins see all.
    op.execute(
        """
        CREATE POLICY listing_events_select_policy
        ON listing_events
        FOR SELECT
        TO authenticated
        USING (
            EXISTS (
                SELECT 1
                FROM properties p
                WHERE p.property_id = listing_events.listing_id
                  AND p.deleted_at IS NULL
                  AND (
                      p.user_id = public.current_user_id()
                      OR public.is_current_user_admin()
                      OR EXISTS (
                          SELECT 1
                          FROM users owner_user
                          WHERE owner_user.user_id = public.current_user_id()
                            AND owner_user.deleted_at IS NULL
                            AND owner_user.user_role = 'agency_owner'::user_role_enum
                            AND owner_user.agency_id = p.agency_id
                      )
                  )
            )
        );
        """
    )


def downgrade() -> None:
    """Best-effort downgrade.

    - Drops listing_events and associated indexes and RLS policy.
    - Does NOT attempt to remove values from moderation_status_enum, since
      Postgres does not support removing enum values.
    - Leaves the properties.moderation_status default as-is.
    """

    # Drop RLS policy and table.
    op.execute("DROP POLICY IF EXISTS listing_events_select_policy ON listing_events")
    op.drop_index("ix_listing_events_created_at", table_name="listing_events")
    op.drop_index("ix_listing_events_actor_id", table_name="listing_events")
    op.drop_index("ix_listing_events_listing_id", table_name="listing_events")
    op.drop_table("listing_events")
