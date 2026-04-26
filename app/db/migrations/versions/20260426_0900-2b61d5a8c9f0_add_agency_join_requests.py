"""add agency join requests

Revision ID: 2b61d5a8c9f0
Revises: 7b5e6d3a01c2
Create Date: 2026-04-26 09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "2b61d5a8c9f0"
down_revision: Union[str, None] = "7b5e6d3a01c2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add join-request workflow and suspended agency status."""
    op.execute("ALTER TABLE agencies DROP CONSTRAINT IF EXISTS agencies_status_check")
    op.execute("ALTER TABLE agencies DROP CONSTRAINT IF EXISTS ck_agencies_agencies_status_check")
    op.execute(
        """
        ALTER TABLE agencies
        ADD CONSTRAINT agencies_status_check
        CHECK (status IN ('pending', 'approved', 'rejected', 'suspended'))
        """
    )

    op.create_table(
        "agency_join_requests",
        sa.Column("join_request_id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("agency_id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("cover_note", sa.Text(), nullable=True),
        sa.Column("portfolio_details", sa.Text(), nullable=True),
        sa.Column("status", sa.String(), server_default=sa.text("'pending'"), nullable=False),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('pending', 'approved', 'rejected')",
            name=op.f("ck_agency_join_requests_agency_join_requests_status_check"),
        ),
        sa.ForeignKeyConstraint(["agency_id"], ["agencies.agency_id"], name=op.f("fk_agency_join_requests_agency_id_agencies"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"], name=op.f("fk_agency_join_requests_user_id_users"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("join_request_id", name=op.f("pk_agency_join_requests")),
    )
    op.create_index(op.f("ix_agency_join_requests_join_request_id"), "agency_join_requests", ["join_request_id"], unique=False)
    op.create_index(op.f("ix_agency_join_requests_agency_id"), "agency_join_requests", ["agency_id"], unique=False)
    op.create_index(op.f("ix_agency_join_requests_user_id"), "agency_join_requests", ["user_id"], unique=False)

    op.create_table(
        "agency_agent_memberships",
        sa.Column("membership_id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("agency_id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("source_join_request_id", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(["agency_id"], ["agencies.agency_id"], name=op.f("fk_agency_agent_memberships_agency_id_agencies"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_join_request_id"], ["agency_join_requests.join_request_id"], name=op.f("fk_agency_agent_memberships_source_join_request_id_agency_join_requests"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"], name=op.f("fk_agency_agent_memberships_user_id_users"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("membership_id", name=op.f("pk_agency_agent_memberships")),
        sa.UniqueConstraint("agency_id", "user_id", name="agency_agent_memberships_agency_user_key"),
    )
    op.create_index(op.f("ix_agency_agent_memberships_membership_id"), "agency_agent_memberships", ["membership_id"], unique=False)
    op.create_index(op.f("ix_agency_agent_memberships_agency_id"), "agency_agent_memberships", ["agency_id"], unique=False)
    op.create_index(op.f("ix_agency_agent_memberships_user_id"), "agency_agent_memberships", ["user_id"], unique=False)
    op.create_index(op.f("ix_agency_agent_memberships_source_join_request_id"), "agency_agent_memberships", ["source_join_request_id"], unique=False)
    op.execute(
        """
        ALTER TABLE public.agency_join_requests ENABLE ROW LEVEL SECURITY;
        ALTER TABLE public.agency_agent_memberships ENABLE ROW LEVEL SECURITY;

        GRANT SELECT, INSERT, UPDATE, DELETE
        ON public.agency_join_requests, public.agency_agent_memberships
        TO authenticated;

        GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO authenticated;

        CREATE POLICY agency_join_requests_select_relevant
        ON public.agency_join_requests
        FOR SELECT
        TO authenticated
        USING (
            deleted_at IS NULL
            AND (
                user_id = public.current_user_id()
                OR public.is_current_user_admin()
                OR EXISTS (
                    SELECT 1
                    FROM public.users AS u
                    WHERE u.user_id = public.current_user_id()
                      AND u.user_role::text = 'agency_owner'
                      AND u.agency_id = agency_join_requests.agency_id
                      AND u.deleted_at IS NULL
                )
            )
        );

        CREATE POLICY agency_join_requests_insert_self
        ON public.agency_join_requests
        FOR INSERT
        TO authenticated
        WITH CHECK (
            public.current_request_role() = 'seeker'
            AND user_id = public.current_user_id()
            AND EXISTS (
                SELECT 1
                FROM public.agencies AS a
                WHERE a.agency_id = agency_join_requests.agency_id
                  AND a.status = 'approved'
                  AND a.deleted_at IS NULL
            )
        );

        CREATE POLICY agency_join_requests_update_owner_or_admin
        ON public.agency_join_requests
        FOR UPDATE
        TO authenticated
        USING (
            deleted_at IS NULL
            AND (
                public.is_current_user_admin()
                OR EXISTS (
                    SELECT 1
                    FROM public.users AS u
                    WHERE u.user_id = public.current_user_id()
                      AND u.user_role::text = 'agency_owner'
                      AND u.agency_id = agency_join_requests.agency_id
                      AND u.deleted_at IS NULL
                )
            )
        )
        WITH CHECK (
            public.is_current_user_admin()
            OR EXISTS (
                SELECT 1
                FROM public.users AS u
                WHERE u.user_id = public.current_user_id()
                  AND u.user_role::text = 'agency_owner'
                  AND u.agency_id = agency_join_requests.agency_id
                  AND u.deleted_at IS NULL
            )
        );

        CREATE POLICY agency_agent_memberships_select_relevant
        ON public.agency_agent_memberships
        FOR SELECT
        TO authenticated
        USING (
            deleted_at IS NULL
            AND (
                user_id = public.current_user_id()
                OR public.is_current_user_admin()
                OR EXISTS (
                    SELECT 1
                    FROM public.users AS u
                    WHERE u.user_id = public.current_user_id()
                      AND u.user_role::text = 'agency_owner'
                      AND u.agency_id = agency_agent_memberships.agency_id
                      AND u.deleted_at IS NULL
                )
            )
        );

        CREATE POLICY agency_agent_memberships_insert_owner_or_admin
        ON public.agency_agent_memberships
        FOR INSERT
        TO authenticated
        WITH CHECK (
            public.is_current_user_admin()
            OR EXISTS (
                SELECT 1
                FROM public.users AS u
                WHERE u.user_id = public.current_user_id()
                  AND u.user_role::text = 'agency_owner'
                  AND u.agency_id = agency_agent_memberships.agency_id
                  AND u.deleted_at IS NULL
            )
        );

        CREATE POLICY agency_agent_memberships_update_owner_or_admin
        ON public.agency_agent_memberships
        FOR UPDATE
        TO authenticated
        USING (
            deleted_at IS NULL
            AND (
                public.is_current_user_admin()
                OR EXISTS (
                    SELECT 1
                    FROM public.users AS u
                    WHERE u.user_id = public.current_user_id()
                      AND u.user_role::text = 'agency_owner'
                      AND u.agency_id = agency_agent_memberships.agency_id
                      AND u.deleted_at IS NULL
                )
            )
        )
        WITH CHECK (
            public.is_current_user_admin()
            OR EXISTS (
                SELECT 1
                FROM public.users AS u
                WHERE u.user_id = public.current_user_id()
                  AND u.user_role::text = 'agency_owner'
                  AND u.agency_id = agency_agent_memberships.agency_id
                  AND u.deleted_at IS NULL
            )
        );

        CREATE POLICY agency_agent_memberships_delete_admin
        ON public.agency_agent_memberships
        FOR DELETE
        TO authenticated
        USING (public.is_current_user_admin());
        """
    )


def downgrade() -> None:
    """Remove join-request workflow and suspended agency status."""
    op.drop_index(op.f("ix_agency_agent_memberships_source_join_request_id"), table_name="agency_agent_memberships")
    op.drop_index(op.f("ix_agency_agent_memberships_user_id"), table_name="agency_agent_memberships")
    op.drop_index(op.f("ix_agency_agent_memberships_agency_id"), table_name="agency_agent_memberships")
    op.drop_index(op.f("ix_agency_agent_memberships_membership_id"), table_name="agency_agent_memberships")
    op.drop_table("agency_agent_memberships")

    op.drop_index(op.f("ix_agency_join_requests_user_id"), table_name="agency_join_requests")
    op.drop_index(op.f("ix_agency_join_requests_agency_id"), table_name="agency_join_requests")
    op.drop_index(op.f("ix_agency_join_requests_join_request_id"), table_name="agency_join_requests")
    op.drop_table("agency_join_requests")

    op.execute("ALTER TABLE agencies DROP CONSTRAINT IF EXISTS agencies_status_check")
    op.execute("ALTER TABLE agencies DROP CONSTRAINT IF EXISTS ck_agencies_agencies_status_check")
    op.execute(
        """
        ALTER TABLE agencies
        ADD CONSTRAINT agencies_status_check
        CHECK (status IN ('pending', 'approved', 'rejected'))
        """
    )
