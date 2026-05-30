# app/db/migrations/script.py.mako
"""add agency_approved to moderation_status_enum

Revision ID: de5047adddbf
Revises: b3b3424176c3
Create Date: 2026-05-30 15:20:45.261375

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'de5047adddbf'
down_revision: Union[str, None] = 'b3b3424176c3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Deployment reminder: PR descriptions must name this migration file, and
# production deploy order is `alembic upgrade head` before application code.

def upgrade() -> None:
    """Add agency_approved to moderation_status_enum."""
    # Postgres doesn't allow ALTER TYPE ... ADD VALUE inside a transaction block
    # We use 'COMMIT' to close the current transaction, then run the alter.
    op.execute("COMMIT")
    op.execute("ALTER TYPE moderation_status_enum ADD VALUE 'agency_approved'")


def downgrade() -> None:
    """Postgres does not support removing values from an ENUM."""
    # We leave this as 'pass' to avoid breaking the migration chain.
    pass
