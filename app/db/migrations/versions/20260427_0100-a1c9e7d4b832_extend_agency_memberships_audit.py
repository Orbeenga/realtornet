"""extend agency memberships and join request audit

Revision ID: a1c9e7d4b832
Revises: 4d9f7a2c6b31
Create Date: 2026-04-27 01:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a1c9e7d4b832"
down_revision: Union[str, None] = "4d9f7a2c6b31"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add join-request decision audit and explicit membership state."""
    op.add_column(
        "agency_join_requests",
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "agency_join_requests",
        sa.Column("decided_by", sa.BigInteger(), nullable=True),
    )
    op.create_foreign_key(
        op.f("fk_agency_join_requests_decided_by_users"),
        "agency_join_requests",
        "users",
        ["decided_by"],
        ["user_id"],
        ondelete="SET NULL",
    )

    op.add_column(
        "agency_agent_memberships",
        sa.Column("agent_profile_id", sa.BigInteger(), nullable=True),
    )
    op.add_column(
        "agency_agent_memberships",
        sa.Column("status", sa.String(), server_default=sa.text("'active'"), nullable=False),
    )
    op.create_foreign_key(
        op.f("fk_agency_agent_memberships_agent_profile_id_agent_profiles"),
        "agency_agent_memberships",
        "agent_profiles",
        ["agent_profile_id"],
        ["profile_id"],
        ondelete="SET NULL",
    )
    op.create_index(
        op.f("ix_agency_agent_memberships_agent_profile_id"),
        "agency_agent_memberships",
        ["agent_profile_id"],
        unique=False,
    )
    op.create_check_constraint(
        op.f("ck_agency_agent_memberships_agency_agent_memberships_status_check"),
        "agency_agent_memberships",
        "status IN ('active', 'inactive', 'suspended')",
    )
    op.execute(
        """
        UPDATE agency_agent_memberships AS aam
        SET agent_profile_id = ap.profile_id
        FROM agent_profiles AS ap
        WHERE ap.user_id = aam.user_id
          AND ap.deleted_at IS NULL
          AND aam.agent_profile_id IS NULL
        """
    )
    op.execute(
        """
        INSERT INTO agency_agent_memberships (
            agency_id,
            user_id,
            agent_profile_id,
            status,
            created_at,
            updated_at
        )
        SELECT
            u.agency_id,
            u.user_id,
            ap.profile_id,
            'active',
            now(),
            now()
        FROM users AS u
        LEFT JOIN agent_profiles AS ap
          ON ap.user_id = u.user_id
         AND ap.deleted_at IS NULL
        WHERE u.agency_id IS NOT NULL
          AND u.deleted_at IS NULL
          AND u.user_role::text IN ('agent', 'agency_owner')
        ON CONFLICT (agency_id, user_id) DO UPDATE
        SET status = 'active',
            agent_profile_id = COALESCE(
                agency_agent_memberships.agent_profile_id,
                EXCLUDED.agent_profile_id
            ),
            deleted_at = NULL,
            deleted_by = NULL,
            updated_at = now()
        """
    )


def downgrade() -> None:
    """Remove join-request decision audit and explicit membership state."""
    op.drop_constraint(
        op.f("ck_agency_agent_memberships_agency_agent_memberships_status_check"),
        "agency_agent_memberships",
        type_="check",
    )
    op.drop_index(
        op.f("ix_agency_agent_memberships_agent_profile_id"),
        table_name="agency_agent_memberships",
    )
    op.drop_constraint(
        op.f("fk_agency_agent_memberships_agent_profile_id_agent_profiles"),
        "agency_agent_memberships",
        type_="foreignkey",
    )
    op.drop_column("agency_agent_memberships", "status")
    op.drop_column("agency_agent_memberships", "agent_profile_id")

    op.drop_constraint(
        op.f("fk_agency_join_requests_decided_by_users"),
        "agency_join_requests",
        type_="foreignkey",
    )
    op.drop_column("agency_join_requests", "decided_by")
    op.drop_column("agency_join_requests", "decided_at")
