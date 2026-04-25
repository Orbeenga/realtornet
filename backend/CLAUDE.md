# RealtorNet - Backend CLAUDE.md

## Entry State

FastAPI backend deployed on Railway. Sentry is instrumented.
Phase F is closed. Phase G is now open.

Use the root [CLAUDE.md](C:/Users/Apine/realtornet/CLAUDE.md) first, then this file for backend-specific state.

## Deployment

- Platform: Railway
- Health check: `GET /healthz`
- `/healthz` must return `200` even in degraded mode
- Storage bootstrap is fail-open during startup, so storage issues must not block process health

## Database And Auth

- Database: Supabase PostgreSQL
- Auth source of truth: Supabase Auth
- Production Supabase project ref: `avkhpachzsbgmbnkfnhu`
- Dev Supabase project ref: `umhtnqxdvffpifqbdtjs`
- Public registration creates a Supabase Auth identity first, then mirrors that UUID into the local `users` row
- Registration rollback deletes the Supabase Auth user if the local DB write fails
- Runtime auth is still based on backend-issued JWTs after login, not direct validation of raw Supabase access tokens
- Legacy account reconciliation is still an open backend concern
- Never mix production and dev Supabase projects during cleanup, verification, or auth debugging

## RLS State

- RLS is enabled on all 14 public tables
- `scripts/check_rls.sql` is the canonical verification query for future restores, clones, and manual dashboard edits

## Storage Buckets

- Required buckets: `property-images`, `profile-images`, `agency-logos`
- Buckets are auto-provisioned and validated at deploy/startup time
- Storage bootstrap must never take Railway health down with it

## Endpoint Contracts

- `/api/v1/admin/properties` is admin-only and must serialize safely without leaking raw PostGIS objects
- `/api/v1/property-types/` is the source of truth for property type dropdowns
- `PATCH /api/v1/properties/{property_id}/verify` exists and is the backend verification contract
- Property creation currently enforces agency membership via `users.agency_id`
- Agent promotion must atomically create an `agent_profiles` row in the same transaction
- Pagination and visibility assumptions should always be pulled from actual endpoint code, not memory
- Trailing slashes matter on authenticated endpoints because 308 redirects can drop Bearer headers on some clients; frontend OPEN-001 normalized paths and is deployed

## Phase G backlog

| Item | Description |
|---|---|
| DEF-G-INQ-002 | Inquiry property hydration / 204 investigation |
| DEF-G-TBT-001 | TBT < 100ms (RSC evaluation) |
| DEF-G-MOD-001 | Full moderation status enum |
| DEF-G-AG-001 | Agency name on property cards |
| DEF-G-POLYFILL-001 | Residual core-js |
| DEF-002 | Audit log retention |
| DEF-007 | psycopg3 dev restart |
| Phase G feature | Advanced map (Mapbox) |
| Phase G feature | Admin analytics |
| Phase G feature | Saved search notifications |
| Phase G feature | Custom domain |

## Locked Invariants

- Public registration must always downgrade requested role to `seeker`
- Admin and agent roles are internal grants, never browser-assigned
- Promoting a user to agent must leave both `users.user_role = 'agent'` and a live `agent_profiles` row
- Property creation for agents depends on `users.agency_id`
- Agency-wide inquiries remain deferred to Phase G; do not build aggregation shortcuts that create N+1 behavior

## Reference Data

- Production currently has 12 property types
- Production currently has 15 Lagos location records seeded for the current dropdown-based flow
- A full move to free-text geocoding is a later architectural change, not the current backend contract

## Backend Agent Protocol

When the frontend agent asks for backend truth, answer from code and live contracts:

- request/response payloads
- auth and middleware behavior
- RLS visibility rules
- pagination defaults and caps
- whether a missing field is intentional or an omission

Do not answer from stale docs when the router, schema, or CRUD layer says otherwise.

## CI And Quality Gates

- `pyright` must stay at zero errors
- `pytest` coverage should not regress
- Any non-obvious workaround, invariant, or guard clause added during a task must be documented inline in touched files

## Next Session Handover

- Start Phase G with `DEF-G-INQ-002`
- Keep production and dev Supabase separation strict during all work
- Treat agency card branding as blocked on backend enrichment until the response contract changes
- Use the Phase G backlog above as the opening queue
