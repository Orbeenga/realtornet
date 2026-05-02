"""add decision reason fields

Revision ID: d4a7c9b2e610
Revises: c8f3b2a91e44
Create Date: 2026-05-02 01:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d4a7c9b2e610"
down_revision: Union[str, None] = "c8f3b2a91e44"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Persist explicit operational decision reasons."""
    op.add_column("agencies", sa.Column("status_reason", sa.Text(), nullable=True))
    op.add_column("users", sa.Column("deactivation_reason", sa.Text(), nullable=True))


def downgrade() -> None:
    """Remove operational decision reason fields."""
    op.drop_column("users", "deactivation_reason")
    op.drop_column("agencies", "status_reason")
