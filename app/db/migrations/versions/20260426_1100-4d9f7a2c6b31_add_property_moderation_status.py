"""add property moderation status

Revision ID: 4d9f7a2c6b31
Revises: 2b61d5a8c9f0
Create Date: 2026-04-26 11:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "4d9f7a2c6b31"
down_revision: Union[str, None] = "2b61d5a8c9f0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


moderation_status_enum = postgresql.ENUM(
    "pending_review",
    "verified",
    "rejected",
    "revoked",
    name="moderation_status_enum",
    create_type=False,
)


def upgrade() -> None:
    """Add explicit moderation lifecycle fields to properties."""
    op.execute(
        """
        DO $$ BEGIN
            CREATE TYPE moderation_status_enum AS ENUM (
                'pending_review',
                'verified',
                'rejected',
                'revoked'
            );
        EXCEPTION WHEN duplicate_object THEN null;
        END $$;
        """
    )
    op.add_column(
        "properties",
        sa.Column(
            "moderation_status",
            moderation_status_enum,
            server_default=sa.text("'pending_review'::moderation_status_enum"),
            nullable=False,
        ),
    )
    op.add_column("properties", sa.Column("moderation_reason", sa.Text(), nullable=True))
    op.execute(
        """
        UPDATE properties
           SET moderation_status = CASE
                   WHEN is_verified IS TRUE THEN 'verified'::moderation_status_enum
                   ELSE 'pending_review'::moderation_status_enum
               END
         WHERE moderation_status IS DISTINCT FROM CASE
                   WHEN is_verified IS TRUE THEN 'verified'::moderation_status_enum
                   ELSE 'pending_review'::moderation_status_enum
               END;
        """
    )
    op.create_index(
        op.f("ix_properties_moderation_status"),
        "properties",
        ["moderation_status"],
        unique=False,
    )


def downgrade() -> None:
    """Remove explicit property moderation lifecycle fields."""
    op.drop_index(op.f("ix_properties_moderation_status"), table_name="properties")
    op.drop_column("properties", "moderation_reason")
    op.drop_column("properties", "moderation_status")
    op.execute("DROP TYPE IF EXISTS moderation_status_enum")
