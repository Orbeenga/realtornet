"""add saved search unsubscribe token

Revision ID: b1f4a9c7e2d3
Revises: a6b2d9f4c801
Create Date: 2026-05-06 15:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "b1f4a9c7e2d3"
down_revision: Union[str, None] = "a6b2d9f4c801"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    op.add_column(
        "saved_searches",
        sa.Column(
            "unsubscribe_token",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
    )
    op.create_index(
        "ix_saved_searches_unsubscribe_token",
        "saved_searches",
        ["unsubscribe_token"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_saved_searches_unsubscribe_token", table_name="saved_searches")
    op.drop_column("saved_searches", "unsubscribe_token")
