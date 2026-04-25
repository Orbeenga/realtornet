"""add agency applications and property agency

Revision ID: 7b5e6d3a01c2
Revises: 0f4c8b7a92d1
Create Date: 2026-04-25 15:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "7b5e6d3a01c2"
down_revision: Union[str, None] = "0f4c8b7a92d1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add agency application fields and denormalized property agency FK."""
    op.add_column(
        "agencies",
        sa.Column("status", sa.String(), nullable=False, server_default=sa.text("'approved'")),
    )
    op.add_column("agencies", sa.Column("owner_email", sa.String(), nullable=True))
    op.add_column("agencies", sa.Column("owner_name", sa.String(), nullable=True))
    op.add_column("agencies", sa.Column("owner_phone_number", sa.String(), nullable=True))
    op.add_column("agencies", sa.Column("rejection_reason", sa.Text(), nullable=True))
    op.execute(
        """
        ALTER TABLE agencies
        ADD CONSTRAINT agencies_status_check
        CHECK (status IN ('pending', 'approved', 'rejected'))
        """
    )

    op.add_column("properties", sa.Column("agency_id", sa.BigInteger(), nullable=True))
    op.create_index("ix_properties_agency_id", "properties", ["agency_id"], unique=False)
    op.create_foreign_key(
        "properties_agency_id_fkey",
        "properties",
        "agencies",
        ["agency_id"],
        ["agency_id"],
    )

    op.execute(
        """
        DO $$
        DECLARE
            before_missing bigint;
            after_missing bigint;
        BEGIN
            SELECT count(*)
              INTO before_missing
              FROM properties
             WHERE deleted_at IS NULL
               AND agency_id IS NULL;

            RAISE NOTICE 'properties.agency_id missing before backfill: %', before_missing;

            UPDATE properties AS p
               SET agency_id = u.agency_id
              FROM users AS u
             WHERE p.user_id = u.user_id
               AND p.deleted_at IS NULL
               AND p.agency_id IS NULL
               AND u.agency_id IS NOT NULL;

            SELECT count(*)
              INTO after_missing
              FROM properties
             WHERE deleted_at IS NULL
               AND agency_id IS NULL;

            RAISE NOTICE 'properties.agency_id missing after backfill: %', after_missing;

            IF after_missing > 0 THEN
                RAISE EXCEPTION
                    'properties.agency_id backfill incomplete for % non-deleted rows',
                    after_missing;
            END IF;
        END $$;
        """
    )


def downgrade() -> None:
    """Remove Phase G agency application/property agency fields."""
    op.drop_constraint("properties_agency_id_fkey", "properties", type_="foreignkey")
    op.drop_index("ix_properties_agency_id", table_name="properties")
    op.drop_column("properties", "agency_id")

    op.execute("ALTER TABLE agencies DROP CONSTRAINT IF EXISTS agencies_status_check")
    op.execute("ALTER TABLE agencies DROP CONSTRAINT IF EXISTS ck_agencies_agencies_status_check")
    op.drop_column("agencies", "rejection_reason")
    op.drop_column("agencies", "owner_phone_number")
    op.drop_column("agencies", "owner_name")
    op.drop_column("agencies", "owner_email")
    op.drop_column("agencies", "status")
