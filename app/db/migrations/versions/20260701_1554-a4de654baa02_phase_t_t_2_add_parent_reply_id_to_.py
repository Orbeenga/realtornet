"""Phase T T.2: add parent_reply_id to inquiry_replies

Adds self-referential FK for conversational reply threading.
Existing replies have parent_reply_id = NULL — no backfill needed.

Revision ID: a4de654baa02
Revises: 7d8c295c7ef6
Create Date: 2026-07-01 15:54:12.777206

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a4de654baa02'
down_revision: Union[str, None] = '7d8c295c7ef6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('inquiry_replies', sa.Column('parent_reply_id', sa.BigInteger(), nullable=True))
    op.create_index(
        op.f('ix_inquiry_replies_parent_reply_id'),
        'inquiry_replies',
        ['parent_reply_id'],
        unique=False,
    )
    op.create_foreign_key(
        op.f('fk_inquiry_replies_parent_reply_id_inquiry_replies'),
        'inquiry_replies',
        'inquiry_replies',
        ['parent_reply_id'],
        ['reply_id'],
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f('fk_inquiry_replies_parent_reply_id_inquiry_replies'),
        'inquiry_replies',
        type_='foreignkey',
    )
    op.drop_index(op.f('ix_inquiry_replies_parent_reply_id'), table_name='inquiry_replies')
    op.drop_column('inquiry_replies', 'parent_reply_id')
