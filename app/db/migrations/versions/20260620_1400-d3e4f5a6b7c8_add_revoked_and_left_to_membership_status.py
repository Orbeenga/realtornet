"""Add revoked and left to agency_agent_memberships status CHECK constraint

Revision ID: d3e4f5a6b7c8
Revises: c2d3e4f5a6b7
Create Date: 2026-06-20 14:00:00.000000
"""

from typing import Sequence, Union

from alembic import op


revision: str = "d3e4f5a6b7c8"
down_revision: Union[str, None] = "c2d3e4f5a6b7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Step 1: Drop the legacy duplicate constraint that excludes 'blocked'
    op.execute(
        "ALTER TABLE agency_agent_memberships "
        "DROP CONSTRAINT IF EXISTS "
        "ck_agency_agent_memberships_agency_agent_memberships_st_482a"
    )
    # Step 2: Drop and recreate the primary constraint with all six values
    op.execute(
        "ALTER TABLE agency_agent_memberships "
        "DROP CONSTRAINT IF EXISTS agency_agent_memberships_status_check"
    )
    op.execute(
        "ALTER TABLE agency_agent_memberships "
        "ADD CONSTRAINT agency_agent_memberships_status_check "
        "CHECK (status IN ('active', 'inactive', 'suspended', 'blocked', 'revoked', 'left'))"
    )


def downgrade() -> None:
    # Revert to the original constraint (active, inactive, suspended, blocked)
    op.execute(
        "ALTER TABLE agency_agent_memberships "
        "DROP CONSTRAINT IF EXISTS agency_agent_memberships_status_check"
    )
    op.execute(
        "ALTER TABLE agency_agent_memberships "
        "ADD CONSTRAINT agency_agent_memberships_status_check "
        "CHECK (status IN ('active', 'inactive', 'suspended', 'blocked'))"
    )
