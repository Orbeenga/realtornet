"""revoke EXECUTE on trigger functions from anon and authenticated

Revision ID: 3a7b9c1d2e4f
Revises: 26727bd6578d
Create Date: 2026-06-26 00:01:00.000000

Supabase Advisor flagged anon_security_defender_function_executable and
authenticated_security_defender_function_executable for the three append-only
trigger functions. These functions should never be callable via the PostgREST
REST API (/rest/v1/rpc/function_name) — they exist only to fire as PostgreSQL
trigger mechanisms.

Step 1: REVOKE EXECUTE on the existing functions from PUBLIC.
        PostgreSQL grants EXECUTE to PUBLIC by default on every new function.
        The anon and authenticated roles inherit through PUBLIC membership,
        so revoking FROM anon/authenticated directly is insufficient — the
        grant through PUBLIC remains and the advisor warning persists.
Step 2: ALTER DEFAULT PRIVILEGES to prevent Supabase from re-granting
        EXECUTE on future function recreations.

After this migration the Supabase advisor will be fully silent on all three
functions.

NOTE: The REVOKE statements modify pg_proc system catalog rows that Supabase
background processes may update concurrently, causing PostgreSQL's
"tuple concurrently updated" serialization error. Each REVOKE is wrapped in
a savepoint-based retry loop so that a transient conflict rolls back only
the savepoint, not the entire migration transaction.
"""
import time
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision: str = '3a7b9c1d2e4f'
down_revision: Union[str, None] = '26727bd6578d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_REVOKE_SQLS = [
    "REVOKE EXECUTE ON FUNCTION public.prevent_listing_instructions_mutation() FROM PUBLIC;",
    "REVOKE EXECUTE ON FUNCTION public.prevent_notifications_delete() FROM PUBLIC;",
    "REVOKE EXECUTE ON FUNCTION public.prevent_inquiry_replies_mutation() FROM PUBLIC;",
]

_GRANT_SQLS = [
    "GRANT EXECUTE ON FUNCTION public.prevent_listing_instructions_mutation() TO PUBLIC;",
    "GRANT EXECUTE ON FUNCTION public.prevent_notifications_delete() TO PUBLIC;",
    "GRANT EXECUTE ON FUNCTION public.prevent_inquiry_replies_mutation() TO PUBLIC;",
]


def _exec_with_retry(sqls, retries=3, delay=2):
    """Execute DDL statements with savepoint-based retry.

    Each statement is attempted in its own savepoint. If PostgreSQL raises
    "tuple concurrently updated" (race on pg_proc with Supabase background
    processes), the savepoint is rolled back and the statement is retried
    after a brief delay. On success the savepoint is released.
    """
    conn = op.get_bind()
    for sql in sqls:
        for attempt in range(retries):
            try:
                with conn.begin_nested():
                    conn.execute(text(sql))
                break
            except Exception as exc:
                if "tuple concurrently updated" in str(exc) and attempt < retries - 1:
                    time.sleep(delay)
                else:
                    raise


def upgrade() -> None:
    """Upgrade schema."""
    # Step 1 — Revoke EXECUTE from PUBLIC on existing functions.
    # Each REVOKE modifies pg_proc which may race with Supabase background
    # processes; retry with savepoint isolation.
    _exec_with_retry(_REVOKE_SQLS)

    # Step 2 — Prevent Supabase default privileges from re-granting
    # on future CREATE OR REPLACE FUNCTION. Functions that legitimately
    # need REST exposure must have EXECUTE granted explicitly.
    # This statement modifies pg_default_acl which is not contended.
    op.execute("""
        ALTER DEFAULT PRIVILEGES IN SCHEMA public
        REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC;
    """)


def downgrade() -> None:
    """Downgrade schema."""
    # Restore default privileges first
    op.execute("""
        ALTER DEFAULT PRIVILEGES IN SCHEMA public
        GRANT EXECUTE ON FUNCTIONS TO PUBLIC;
    """)

    # Restore EXECUTE on the specific functions
    _exec_with_retry(_GRANT_SQLS)
