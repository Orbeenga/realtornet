# RealtorNet Repository Guidance

## Core architecture
- Database-first architecture: the database is the source of truth
- FastAPI backend
- SQLAlchemy 2.x ORM
- Pydantic v2
- Alembic migrations
- Supabase/Postgres
- RLS aligned to Supabase Auth via users.supabase_id bridge patterns

## Non-negotiable rules
- Do not invent fields not present in the DB schema
- Preserve PK/FK type parity exactly
- Use timezone-aware datetime handling for timestamptz fields
- Respect existing enum values exactly as stored in Postgres
- Avoid broad rewrites when a narrow fix is sufficient
- No create_all in production code
- Prefer migration-safe, dependency-ordered changes
- Flag any ORM/schema/router drift from DB truth

## Locked environment decisions
- Production Supabase project ref: `avkhpachzsbgmbnkfnhu`
- Dev Supabase project ref: `umhtnqxdvffpifqbdtjs`
- Local backend env had been pointed at dev during investigation; verify target project before any destructive or verification action
- Never mix production and dev Supabase projects during cleanup, verification, migrations, or auth debugging

## Locked product decisions
- Agency branding is pre-launch scope on property detail only for now
- Property-card agency branding stays deferred until the property list response includes agency branding fields; do not introduce N+1 card fetches
- Agency-wide inquiry rollup is deferred to Phase G; do not aggregate per-property inquiry calls in the frontend
- Public signup remains seeker-only; admin and agent are backend-authoritative roles

## Review priorities
1. DB to ORM alignment
2. Migration safety
3. Enum/value correctness
4. Auth/token consistency
5. Test coverage for changed behavior
6. RLS/security implications
7. Minimal, maintainable diffs

## Next session handover
- Verify production cleanup removed test accounts and seed-owned noise safely
- Close OPEN-001 and OPEN-002 with live retests
- Run the Phase F exit checklist end to end
- Declare Phase F closed only after those checks pass
- Open Phase G immediately after closure
