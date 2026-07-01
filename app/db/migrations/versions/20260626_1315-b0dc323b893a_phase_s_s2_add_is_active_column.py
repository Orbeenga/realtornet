"""phase_s_s2_add_is_active_column

Add is_active BOOLEAN column to users table for platform-level admin
deactivation. This is distinct from soft-delete (deleted_at).

The default is true for all existing users — no one is deactivated by
the migration.

Steps:
  1. Add is_active column with NOT NULL DEFAULT true
  2. Backfill to ensure no nulls exist in the column

Note: last_login column already exists in the users table (TIMESTAMPTZ NULL)
from an earlier migration — no additional migration needed for activity tracking.

Revision ID: b0dc323b893a
Revises: f7f8c6a12f4a
Create Date: 2026-06-26 13:15:02.562352

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'b0dc323b893a'
down_revision: Union[str, None] = 'f7f8c6a12f4a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add is_active column with default true."""
    op.execute("""
        ALTER TABLE users
        ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT true;
    """)

    # Ensure existing rows are active
    op.execute("""
        UPDATE users
        SET is_active = TRUE
        WHERE is_active IS NULL;
    """)

    # Ensure the default is present even if the column already existed
    op.execute("""
        ALTER TABLE users
        ALTER COLUMN is_active SET DEFAULT TRUE;
    """)

def downgrade() -> None:
    """Remove is_active column."""
    op.execute("""
        ALTER TABLE users
        DROP COLUMN IF EXISTS is_active;
    """)
