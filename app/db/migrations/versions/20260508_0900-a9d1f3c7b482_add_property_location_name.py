"""add property location name

Revision ID: a9d1f3c7b482
Revises: f4a8c2d9e5b1
Create Date: 2026-05-08 09:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a9d1f3c7b482"
down_revision: Union[str, None] = "f4a8c2d9e5b1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("properties", sa.Column("location_name", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("properties", "location_name")
