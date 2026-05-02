"""add user role change reason

Revision ID: a6b2d9f4c801
Revises: d4a7c9b2e610
Create Date: 2026-05-02 03:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a6b2d9f4c801"
down_revision: Union[str, None] = "d4a7c9b2e610"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("role_change_reason", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "role_change_reason")
