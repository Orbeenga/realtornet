"""Soft-delete Phase G.7 production smoke data."""

from __future__ import annotations

from pathlib import Path
import sys

from sqlalchemy import create_engine, text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import settings


SMOKE_USER_IDS = (86, 87, 88)
REAL_ACCOUNT_EMAILS = (
    "apineorbeenga@gmail.com",
    "apineorbeenga@outlook.com",
    "apineorbeenga@yahoo.com",
    "godwinemagun@gmail.com",
)


def main() -> None:
    engine = create_engine(settings.DATABASE_URI)
    with engine.begin() as conn:
        admin_supabase_id = conn.execute(
            text(
                """
                select supabase_id
                from users
                where email = 'apineorbeenga@gmail.com'
                  and deleted_at is null
                """
            )
        ).scalar_one()
        params = {"deleted_by": admin_supabase_id}

        updates = [
            (
                "inquiries",
                text(
                    """
                    update inquiries
                    set deleted_at = now(), deleted_by = :deleted_by, updated_at = now()
                    where inquiry_id = 5 and deleted_at is null
                    """
                ),
                1,
            ),
            (
                "agency_invitations",
                text(
                    """
                    update agency_invitations
                    set deleted_at = now(), deleted_by = :deleted_by,
                        updated_at = now(), updated_by = :deleted_by
                    where (agency_id = 8 or invited_user_id in (86, 87, 88))
                      and deleted_at is null
                    """
                ),
                1,
            ),
            (
                "agency_agent_memberships",
                text(
                    """
                    update agency_agent_memberships
                    set deleted_at = now(), deleted_by = :deleted_by,
                        updated_at = now(), updated_by = :deleted_by
                    where (agency_id = 8 or user_id in (86, 87, 88))
                      and deleted_at is null
                    """
                ),
                1,
            ),
            (
                "properties",
                text(
                    """
                    update properties
                    set deleted_at = now(), deleted_by = :deleted_by,
                        updated_at = now(), updated_by = :deleted_by
                    where property_id = 5 and deleted_at is null
                    """
                ),
                1,
            ),
            (
                "agencies",
                text(
                    """
                    update agencies
                    set deleted_at = now(), deleted_by = :deleted_by,
                        updated_at = now(), updated_by = :deleted_by
                    where agency_id = 8 and deleted_at is null
                    """
                ),
                1,
            ),
            (
                "users",
                text(
                    """
                    update users
                    set deleted_at = now(), deleted_by = :deleted_by,
                        updated_at = now(), updated_by = :deleted_by
                    where user_id in (86, 87, 88)
                      and email like 'phaseg7.%@smoke.realtornetapp.com'
                      and deleted_at is null
                    """
                ),
                3,
            ),
        ]

        for name, statement, expected in updates:
            rowcount = conn.execute(statement, params).rowcount
            print(f"{name}: {rowcount}")
            if rowcount not in {0, expected}:
                raise RuntimeError(f"{name} expected 0 or {expected}, got {rowcount}")

        real_accounts_active = conn.execute(
            text(
                """
                select count(*)
                from users
                where email = any(:emails)
                  and deleted_at is null
                """
            ),
            {"emails": list(REAL_ACCOUNT_EMAILS)},
        ).scalar_one()
        if real_accounts_active != 4:
            raise RuntimeError(f"expected 4 real accounts active, got {real_accounts_active}")

    print("Phase G.7 smoke cleanup complete; 4 real accounts remain active.")


if __name__ == "__main__":
    main()
