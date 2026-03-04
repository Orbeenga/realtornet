# app/db/migrations/script.py.mako
"""manual_fix_inquiry_and_images

Revision ID: 388601679a8b
Revises: 4e8866888c9c
Create Date: 2026-03-03 03:54:13.501368

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '388601679a8b'
down_revision: Union[str, None] = '4e8866888c9c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Fix Property Images table
    op.add_column('property_images', sa.Column('caption', sa.String(), nullable=True))
    op.add_column('property_images', sa.Column('display_order', sa.Integer(), server_default='0', nullable=False))
    
    # Force the Inquiry Status Enum default (Bypasses the "UndefinedFunction" error)
    op.execute("ALTER TABLE inquiries ALTER COLUMN inquiry_status SET DEFAULT 'new'::inquiry_status_enum")

def downgrade() -> None:
    op.execute("ALTER TABLE inquiries ALTER COLUMN inquiry_status DROP DEFAULT")
    op.drop_column('property_images', 'display_order')
    op.drop_column('property_images', 'caption')
