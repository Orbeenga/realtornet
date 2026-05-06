"""add membership audit and role version

Revision ID: d3e7c5a1b9f2
Revises: b1f4a9c7e2d3
Create Date: 2026-05-06 16:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "d3e7c5a1b9f2"
down_revision: Union[str, None] = "b1f4a9c7e2d3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


user_role_enum = postgresql.ENUM(
    "seeker",
    "agent",
    "agency_owner",
    "admin",
    name="user_role_enum",
    create_type=False,
)


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("role_version", sa.Integer(), nullable=False, server_default=sa.text("1")),
    )

    op.create_table(
        "agent_membership_audit",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("agency_id", sa.BigInteger(), nullable=False),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("actor_id", sa.BigInteger(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("prior_role", user_role_enum, nullable=True),
        sa.Column("post_role", user_role_enum, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "action IN ('invited', 'joined', 'suspended', 'revoked', 'left', 'reinstated')",
            name="agent_membership_audit_action_check",
        ),
        sa.ForeignKeyConstraint(["actor_id"], ["users.user_id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["agency_id"], ["agencies.agency_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_agent_membership_audit_id", "agent_membership_audit", ["id"])
    op.create_index("ix_agent_membership_audit_user_id", "agent_membership_audit", ["user_id"])
    op.create_index("ix_agent_membership_audit_agency_id", "agent_membership_audit", ["agency_id"])
    op.create_index("ix_agent_membership_audit_actor_id", "agent_membership_audit", ["actor_id"])
    op.create_index("ix_agent_membership_audit_action", "agent_membership_audit", ["action"])
    op.create_index("ix_agent_membership_audit_created_at", "agent_membership_audit", ["created_at"])

    op.execute(
        """
        INSERT INTO agent_membership_audit (
            user_id,
            agency_id,
            action,
            actor_id,
            reason,
            prior_role,
            post_role,
            created_at
        )
        SELECT
            membership.user_id,
            membership.agency_id,
            'joined',
            NULL,
            'Backfilled from active membership during Phase I I.3',
            users.user_role,
            users.user_role,
            COALESCE(membership.created_at, now())
        FROM agency_agent_memberships membership
        JOIN users ON users.user_id = membership.user_id
        WHERE membership.status = 'active'
          AND membership.deleted_at IS NULL
          AND users.deleted_at IS NULL
        """
    )

    op.execute("ALTER TABLE agent_membership_audit ENABLE ROW LEVEL SECURITY")
    op.execute("GRANT SELECT, INSERT ON agent_membership_audit TO authenticated")
    op.execute("GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO authenticated")
    op.execute(
        """
        CREATE POLICY agent_membership_audit_select_policy
        ON agent_membership_audit
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
                  AND owner_user.agency_id = agent_membership_audit.agency_id
            )
        )
        """
    )
    op.execute(
        """
        CREATE POLICY agent_membership_audit_insert_policy
        ON agent_membership_audit
        FOR INSERT
        TO authenticated
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
                  AND owner_user.agency_id = agent_membership_audit.agency_id
            )
        )
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION prevent_agent_membership_audit_mutation()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            RAISE EXCEPTION 'agent_membership_audit is append-only';
        END;
        $$;
        """
    )
    op.execute(
        """
        CREATE TRIGGER prevent_agent_membership_audit_update
        BEFORE UPDATE ON agent_membership_audit
        FOR EACH ROW EXECUTE FUNCTION prevent_agent_membership_audit_mutation()
        """
    )
    op.execute(
        """
        CREATE TRIGGER prevent_agent_membership_audit_delete
        BEFORE DELETE ON agent_membership_audit
        FOR EACH ROW EXECUTE FUNCTION prevent_agent_membership_audit_mutation()
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS prevent_agent_membership_audit_delete ON agent_membership_audit")
    op.execute("DROP TRIGGER IF EXISTS prevent_agent_membership_audit_update ON agent_membership_audit")
    op.execute("DROP FUNCTION IF EXISTS prevent_agent_membership_audit_mutation()")
    op.drop_index("ix_agent_membership_audit_created_at", table_name="agent_membership_audit")
    op.drop_index("ix_agent_membership_audit_action", table_name="agent_membership_audit")
    op.drop_index("ix_agent_membership_audit_actor_id", table_name="agent_membership_audit")
    op.drop_index("ix_agent_membership_audit_agency_id", table_name="agent_membership_audit")
    op.drop_index("ix_agent_membership_audit_user_id", table_name="agent_membership_audit")
    op.drop_index("ix_agent_membership_audit_id", table_name="agent_membership_audit")
    op.drop_table("agent_membership_audit")
    op.drop_column("users", "role_version")
