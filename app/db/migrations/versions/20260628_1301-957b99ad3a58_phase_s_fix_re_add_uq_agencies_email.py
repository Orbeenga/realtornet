"""phase_s_fix_re_add_uq_agencies_email

Revision ID: 957b99ad3a58
Revises: b0dc323b893a
Create Date: 2026-06-28 13:01:32.321537

Restores the unique constraint on agencies.email that was inadvertently
dropped by migration 6c0087f609b4. The SQLAlchemy model declares
unique=True on the email column, so the constraint must exist in the DB.
"""
from typing import Sequence, Union

from alembic import op

revision: str = '957b99ad3a58'
down_revision: Union[str, None] = 'b0dc323b893a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_unique_constraint(op.f('uq_agencies_email'), 'agencies', ['email'])


def downgrade() -> None:
    op.drop_constraint(op.f('uq_agencies_email'), 'agencies', type_='unique')
