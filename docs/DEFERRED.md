# Deferred Items

## DEF-006: Supabase storage bucket provisioning and policy verification

Phase D fixed backend storage writes by switching all upload/delete operations to the admin client, but bucket existence, public exposure, and environment-side policy verification still live outside this repo.

Current expectation: `property-images`, `profile-images`, and `agency-logos` already exist in each target Supabase project before backend deploys.

Pre-launch: add deployment-time validation or provisioning automation so storage buckets and required access settings are checked explicitly per environment.

## DEF-007: psycopg3 prepared statement corruption in dev

Pattern: `DuplicatePreparedStatement`, `ProtocolViolation`, and `InFailedSqlTransaction` errors appearing after extended backend uptime or connection disruption.

Resolved by restarting Uvicorn.

Pre-launch: investigate `prepared_statement_cache_size=0` on the psycopg3 connection string or switch to `NullPool` for the dev engine to prevent statement caching across requests.

## DEF-008 (Resolved): Amenities checkbox grid not rendering in AmenitySelector

Phase D backend work removed the backend data blocker for the selector by ensuring the amenities catalogue is seeded with 15 items and the amenity payload shape is stable for consumers.

Resolved status: backend support is complete. Any future visual rendering-only regression should be tracked separately in the frontend workstream rather than kept open as a backend deferred item.

## RLS-001 (Resolved): RLS enabled and enforced on all 14 public tables

Completed on 2026-04-15 via Alembic migrations `9f2b7c1d4a10` and `a84d7e2c5b91`.

Resolved status:
- `agencies`, `agent_profiles`, `amenities`, `favorites`, `inquiries`, `locations`, `profiles`, `properties`, `property_amenities`, `property_images`, `property_types`, `reviews`, `saved_searches`, and `users` now all report `relrowsecurity = true`
- Public read grants and authenticated DML grants are now explicit, so the RLS policies are reachable instead of being blocked by missing table privileges
- Rolled-back production verification passed for anonymous public reads, anonymous private-table denial, seeker-owned writes, agent-owned property updates, and admin-only property-type writes

Verification snapshot:
- Catalog check: 14/14 target tables returned `relrowsecurity = true`
- Behavior check: `anon` can read public tables and is blocked from private tables; authenticated seeker can create favorites and inquiries for allowed records; agent can update own property; non-admin property-type writes fail; simulated admin write succeeds

Follow-up:
- Keep using `scripts/check_rls.sql` for future environment verification after restores, clones, or manual dashboard changes

## DEF-G-MOD-001: Full moderation status workflow

Phase G should replace the current `is_verified` boolean with an explicit `moderation_status` enum covering `pending_review`, `verified`, `rejected`, and `revoked`.

Scope:
- Add a rejection reason field
- Add backend-driven notifications
- Add an agent inbox experience contract
- Add moderation history
- Add admin moderation filters
- Add a resubmit flow

Constraint: design the backend schema and workflow contract first before any frontend work begins.

## DEF-002: Audit log retention

Deferred to Phase G. No real traffic data to size policy against.

Revisit after 60 days of production usage. Decision at that point:
- rolling window (e.g. 90 days)
- archive-to-cold-storage strategy

## DEF-G-INQ-002: Inquiry cards missing property title/link on agent inbox

Agent `/account/inquiries` cards currently show seeker contact details but no property title or property link.

Observed behavior:
- secondary fetch for `GET /api/v1/properties/{id}/` returns `204` with no body
- origin is still unknown
- backend route inspection rules out an intentional `204` from the FastAPI property handler
- frontend normalization was reviewed separately and reported clean
- suspected layer is Vercel -> Railway proxy behavior, but this is not yet proven

Backend gap also exists:
- `GET /api/v1/inquiries/received` does not join or serialize related property data
- current frontend relies on N+1 hydration using `property_id`

Phase decision:
- accept for Phase F
- defer full investigation and cleanup to Phase G

Next verification step:
- inspect the live browser Network tab with auth headers visible for the failing property fetches
