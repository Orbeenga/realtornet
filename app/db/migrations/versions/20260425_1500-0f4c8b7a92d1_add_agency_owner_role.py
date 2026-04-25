"""add agency owner role

Revision ID: 0f4c8b7a92d1
Revises: a84d7e2c5b91
Create Date: 2026-04-25 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "0f4c8b7a92d1"
down_revision: Union[str, None] = "a84d7e2c5b91"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add agency_owner to user_role_enum and matching constraints/views."""
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE user_role_enum ADD VALUE IF NOT EXISTS 'agency_owner'")
    op.execute(
        """
        ALTER TABLE users
        DROP CONSTRAINT IF EXISTS users_user_role_check
        """
    )
    op.execute(
        """
        ALTER TABLE users
        DROP CONSTRAINT IF EXISTS ck_users_users_user_role_check
        """
    )
    op.execute(
        """
        ALTER TABLE users
        ADD CONSTRAINT users_user_role_check
        CHECK (
            user_role::text = ANY (
                ARRAY[
                    'seeker'::text,
                    'agent'::text,
                    'agency_owner'::text,
                    'admin'::text
                ]
            )
        )
        """
    )
    op.execute(
        """
        CREATE OR REPLACE VIEW public.agent_public_profiles AS
        SELECT
            user_id,
            concat_ws(' ', first_name, last_name) AS full_name,
            profile_image_url AS avatar_url,
            agency_id
        FROM public.users
        WHERE user_role::text IN ('agent', 'agency_owner')
          AND deleted_at IS NULL
        """
    )
    op.execute("GRANT SELECT ON public.agent_public_profiles TO anon, authenticated")


def downgrade() -> None:
    """Restore the pre-Phase-G user role check/view shape."""
    op.execute(
        """
        ALTER TABLE users
        DROP CONSTRAINT IF EXISTS users_user_role_check
        """
    )
    op.execute(
        """
        ALTER TABLE users
        DROP CONSTRAINT IF EXISTS ck_users_users_user_role_check
        """
    )
    op.execute(
        """
        ALTER TABLE users
        ADD CONSTRAINT users_user_role_check
        CHECK (
            user_role::text = ANY (
                ARRAY['seeker'::text, 'agent'::text, 'admin'::text]
            )
        )
        """
    )
    op.execute(
        """
        CREATE OR REPLACE VIEW public.agent_public_profiles AS
        SELECT
            user_id,
            concat_ws(' ', first_name, last_name) AS full_name,
            profile_image_url AS avatar_url,
            agency_id
        FROM public.users
        WHERE user_role = 'agent'::user_role_enum
          AND deleted_at IS NULL
        """
    )
    op.execute("GRANT SELECT ON public.agent_public_profiles TO anon, authenticated")
