# RealtorNet - Backend CLAUDE.md

## Entry State

FastAPI backend deployed on Railway. Sentry is instrumented.
Phase D and Phase E are closed. Phase F is still active.

Use the root [CLAUDE.md](C:/Users/Apine/realtornet/CLAUDE.md) first, then this file for backend-specific state.

## Deployment

- Platform: Railway
- Health check: `GET /healthz`
- `/healthz` must return `200` even in degraded mode
- Storage bootstrap is fail-open during startup, so storage issues must not block process health

## Database And Auth

- Database: Supabase PostgreSQL
- Auth source of truth: Supabase Auth
- Public registration creates a Supabase Auth identity first, then mirrors that UUID into the local `users` row
- Registration rollback deletes the Supabase Auth user if the local DB write fails
- Runtime auth is still based on backend-issued JWTs after login, not direct validation of raw Supabase access tokens
- Legacy account reconciliation is still an open backend concern

## RLS State

F.1 is closed.

- RLS is enabled on all 14 public tables
- `scripts/check_rls.sql` is the canonical verification query for future restores, clones, and manual dashboard edits

## Storage Buckets

F.2 is closed.

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

## Open Backend Items

| ID | Item | Status |
|---|---|---|
| F.5 | Live end-to-end verification workflow still needs final production confirmation | Open |
| DEF-007 | psycopg3 prepared statement corruption in dev | Monitor |
| Auth bridge | Legacy/stale account reconciliation between Supabase UUIDs and local rows | Open |
| Production cleanup | Test-user cleanup plan prepared; production execution still pending | Open |
| Location architecture | Nominatim/OSM free-text geocoding is deferred to Phase G | Open |

## Locked Invariants

- Public registration must always downgrade requested role to `seeker`
- Admin and agent roles are internal grants, never browser-assigned
- Promoting a user to agent must leave both `users.user_role = 'agent'` and a live `agent_profiles` row
- Property creation for agents depends on `users.agency_id`

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
