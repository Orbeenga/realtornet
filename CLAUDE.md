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
- Phase F closed April 25 2026
- Phase G closed April 29 2026
- Phase H closed May 6 2026
- Phase I is opening
- Backend G.7 exit sweep passed: pyright 0 errors; pytest passed with 92.99% coverage; production smoke 12/12; new agency journey passed end to end
- Frontend G.7 closed in commit `d74806f`: tsc 0 errors, production build clean, Lighthouse mobile LCP 1.5s, accessibility 1.00, production routes 200
- Backend Phase H B1/B2/B3 completed in May 2026: membership alias clarified, `property_type_id` property filter live, storage service tests raised, endpoint maps documented, agency-owner profile edit live, public agent directory filters live, location hierarchy documented, and saved-search owner detail/update confirmed
- Phase H close gate: Resend email delivery confirmed, production smoke passed, backend pyright 0 errors, pytest 1856 passed, total coverage 94.54%

## Locked environment decisions
- Production Supabase project ref: `avkhpachzsbgmbnkfnhu`
- Dev Supabase project ref: `umhtnqxdvffpifqbdtjs`
- Local backend env had been pointed at dev during investigation; verify target project before any destructive or verification action
- Never mix production and dev Supabase projects during cleanup, verification, migrations, or auth debugging
- Railway backend service `imaginative-peace` must run with `ENV=production`
- Railway backend service `imaginative-peace` must include `RESEND_API_KEY` for transactional email delivery

## Locked product decisions
- Agency-first public hierarchy is locked: Agencies -> Listings -> Agents
- `agency_owner` role is active in the user role enum; all four roles are active: seeker, agent, agency_owner, admin
- Multi-agency membership is represented by the `agency_agent_memberships` table; `users.agency_id` remains the legacy primary agency pointer
- Property moderation status enum is active: pending_review / verified / rejected / revoked
- Seeker join-request flow is live
- Agent invitation flow is live
- Agency application and admin approval flow is live
- Featured properties endpoint is live
- Agency branding is pre-launch scope on property detail only for now
- Property-card agency branding stays deferred until the property list response includes agency branding fields; do not introduce N+1 card fetches
- Agency-wide inquiry rollup is live; do not aggregate per-property inquiry calls in the frontend
- Public signup remains seeker-only; admin and agent are backend-authoritative roles
- Resend is the live transactional email provider; `onboarding@resend.dev` is the temporary sender until a custom sender domain is registered
- Public `/agents` directory is live
- `/account/reviews` is live
- Public frontend hooks should use the `authMode: omit` pattern for public API surfaces
- Mobile total blocking time and location hierarchy/geocoding work are deferred to Phase I

## Phase I opening backlog
- `DEF-H4-MOBILE-TBT` - mobile total blocking time frontend performance work
- `DEF-I-LOC-001` - location hierarchy and geocoding architecture
- `DEF-G-POLYFILL-001` - residual third-party `core-js`
- `DEF-002` - audit log retention
- `DEF-007` - psycopg3 dev restart
- Advanced map (Mapbox)
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
- Phase G is closed; do not reopen Phase G unless investigating a regression from the closed state
- Phase H is closed; do not reopen Phase H unless investigating a regression from the closed state
- Phase I is opening from the closed Phase H baseline
- Keep production vs dev Supabase separation strict during all investigations
- Treat agency card branding as blocked on backend enrichment, not frontend fetch fan-out
- Use the backlog above as the opening queue for planning and execution
