# app/db/migrations/script.py.mako
"""add_agency_id_to_reviews

Revision ID: d8a5015d8792
Revises: de5047adddbf
Create Date: 2026-05-31 00:05:27.420256

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd8a5015d8792'
down_revision: Union[str, None] = 'de5047adddbf'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Deployment reminder: PR descriptions must name this migration file, and
# production deploy order is `alembic upgrade head` before application code.

def upgrade() -> None:
    """Add agency_id column and FK to reviews table."""
    op.add_column(
        'reviews',
        sa.Column('agency_id', sa.BigInteger(), nullable=True)
    )
    op.create_foreign_key(
        'fk_reviews_agency_id_agencies',
        'reviews',
        'agencies',
        ['agency_id'],
        ['agency_id']
    )


def downgrade() -> None:
    """Remove agency_id column and FK from reviews table."""
    op.drop_constraint('fk_reviews_agency_id_agencies', 'reviews', type_='foreignkey')
    op.drop_column('reviews', 'agency_id')
