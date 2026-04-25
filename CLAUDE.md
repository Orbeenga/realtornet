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

## Current phase state
- Phase F is closed
- Phase G is open

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

## Phase G backlog
- `DEF-G-INQ-002` - inquiry property hydration / 204 investigation
- `DEF-G-TBT-001` - TBT < 100ms (RSC evaluation)
- `DEF-G-MOD-001` - full moderation status enum
- `DEF-G-AG-001` - agency name on property cards
- `DEF-G-POLYFILL-001` - residual core-js
- `DEF-002` - audit log retention
- `DEF-007` - psycopg3 dev restart
- Advanced map (Mapbox)
- Admin analytics
- Saved search notifications
- Custom domain

## Review priorities
1. DB to ORM alignment
2. Migration safety
3. Enum/value correctness
4. Auth/token consistency
5. Test coverage for changed behavior
6. RLS/security implications
7. Minimal, maintainable diffs

## Next session handover
- Start Phase G with `DEF-G-INQ-002`
- Keep production vs dev Supabase separation strict during all investigations
- Treat agency card branding as blocked on backend enrichment, not frontend fetch fan-out
- Use the backlog above as the opening queue for planning and execution
