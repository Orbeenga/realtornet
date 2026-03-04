# app/db/migrations/script.py.mako
"""add_suspended_to_profile_status

Revision ID: 68aeff120f1f
Revises: 5624fddb4ef8
Create Date: 2026-02-25 22:06:51.297750

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '68aeff120f1f'
down_revision: Union[str, None] = '5624fddb4ef8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Postgres doesn't allow ALTER TYPE ... ADD VALUE inside a transaction block
    # We use 'COMMIT' to close the current transaction, then run the alter.
    op.execute("COMMIT")
    op.execute("ALTER TYPE profile_status_enum ADD VALUE 'suspended'")

def downgrade() -> None:
    # Postgres does not support removing values from an ENUM.
    # We leave this as 'pass' to avoid breaking the migration chain.
    pass
