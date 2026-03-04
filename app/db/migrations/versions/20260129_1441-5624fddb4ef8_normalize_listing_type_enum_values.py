# app/db/migrations/script.py.mako
"""normalize_listing_type_enum_values

Revision ID: 5624fddb4ef8
Revises: d1ba4e701ce3
Create Date: 2026-01-29 14:41:47.619221

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5624fddb4ef8'
down_revision: Union[str, None] = 'd1ba4e701ce3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Normalize listing_type_enum values to industry standard.
    Old values: 'for sale', 'for rent', 'lease'
    New values: 'sale', 'rent', 'lease'
    """

    # 1. Create new enum with normalized values
    op.execute("""
        CREATE TYPE listing_type_enum_new AS ENUM ('sale', 'rent', 'lease');
    """)

    # 2. Alter properties.listing_type to use new enum
    # Table is empty, so this cast is safe
    op.execute("""
        ALTER TABLE properties
        ALTER COLUMN listing_type
        TYPE listing_type_enum_new
        USING listing_type::text::listing_type_enum_new;
    """)

    # 3. Drop old enum
    op.execute("""
        DROP TYPE listing_type_enum;
    """)

    # 4. Rename new enum to canonical name
    op.execute("""
        ALTER TYPE listing_type_enum_new RENAME TO listing_type_enum;
    """)


def downgrade() -> None:
    """
    Revert listing_type_enum values to legacy format.
    """

    # 1. Recreate old enum values
    op.execute("""
        CREATE TYPE listing_type_enum_old AS ENUM ('for sale', 'for rent', 'lease');
    """)

    # 2. Revert column to old enum
    op.execute("""
        ALTER TABLE properties
        ALTER COLUMN listing_type
        TYPE listing_type_enum_old
        USING listing_type::text::listing_type_enum_old;
    """)

    # 3. Drop normalized enum
    op.execute("""
        DROP TYPE listing_type_enum;
    """)

    # 4. Rename old enum back to canonical name
    op.execute("""
        ALTER TYPE listing_type_enum_old RENAME TO listing_type_enum;
    """)
