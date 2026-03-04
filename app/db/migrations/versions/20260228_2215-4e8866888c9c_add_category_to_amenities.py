# app/db/migrations/script.py.mako
"""add_category_to_amenities

Revision ID: 4e8866888c9c
Revises: 68aeff120f1f
Create Date: 2026-02-28 22:15:17.154426

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4e8866888c9c'
down_revision: Union[str, None] = '68aeff120f1f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'amenities',
        sa.Column('category', sa.String(), nullable=True)
    )
    op.create_index(
        op.f('ix_amenities_category'),
        'amenities',
        ['category'],
        unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_amenities_category'), table_name='amenities')
    op.drop_column('amenities', 'category')
