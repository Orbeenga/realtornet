"""Add cancelled status to agency_join_requests CHECK constraint

Revision ID: c2d3e4f5a6b7
Revises: b1c2d3e4f5a6
Create Date: 2026-06-19 12:00:00.000000
"""

from typing import Sequence, Union

from alembic import op

revision: str = "c2d3e4f5a6b7"
down_revision: Union[str, None] = "b1c2d3e4f5a6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE agency_join_requests DROP CONSTRAINT IF EXISTS agency_join_requests_status_check"
    )
    op.execute(
        "ALTER TABLE agency_join_requests ADD CONSTRAINT agency_join_requests_status_check "
        "CHECK (status IN ('pending', 'approved', 'rejected', 'cancelled'))"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE agency_join_requests DROP CONSTRAINT IF EXISTS agency_join_requests_status_check"
    )
    op.execute(
        "ALTER TABLE agency_join_requests ADD CONSTRAINT agency_join_requests_status_check "
        "CHECK (status IN ('pending', 'approved', 'rejected'))"
    )
