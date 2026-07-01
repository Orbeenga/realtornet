# RealtorNet Repository Guidance

## Core architecture

- Database-first architecture: the database is the single source of truth
- FastAPI backend, SQLAlchemy 2.x ORM, Pydantic v2, Alembic migrations
- Supabase/Postgres with RLS aligned to Supabase Auth via `users.supabase_id` bridge
- Next.js frontend (App Router, TypeScript strict, TanStack Query v5)

## Non-negotiable rules

- Do not invent fields not present in the DB schema
- Preserve PK/FK type parity exactly (BIGINT FK → BIGINT PK; UUID FK → UUID PK)
- Use timezone-aware datetime handling for all `timestamptz` fields
- Respect existing enum values exactly as stored in Postgres
- Avoid broad rewrites when a narrow fix is sufficient
- No `create_all` in production code — Alembic is the only schema management tool
- Prefer migration-safe, dependency-ordered changes
- Flag any ORM/schema/router drift from DB truth
- **Never commit diagnostic scripts, one-off queries, or ad-hoc database checks.**
  Run locally, read output, delete the file. Reproducible scripts go in `scripts/`
  with no hardcoded credentials and a corresponding `.env.example` entry.
- **Never hardcode credentials in committed files.** `detect-secrets` pre-commit
  hook is active — any commit with a credential pattern is blocked.

## Deployment workflow

- Work flows: `feature → staging → validate → merge to main → production`
- Staging first, manual validation second, deliberate merge/promotion to main
- **Commit order is strictly: backend first, then frontend.**
  Backend commit → push → wait for Railway deploy (green `/healthz`) →
  `pnpm gen:types` against production OpenAPI → if types changed, commit result →
  push → finally commit frontend logic changes.
  Never batch backend and frontend in the same commit.
  `gen:types` must resolve against a live deployed backend, not a pending one.

## Current phase

**Phase T — Admin Membership View & Conversational Reply Threading**
Phase S closed: June 30 2026 — internal schema migration, user activity tracking,
admin user segmentation, multi-turn inquiry reply threading, production data gating,
Docker PostGIS local test infrastructure restored, full suite at 95.35% coverage.

## Locked environment decisions

| Environment | Supabase ref | Notes |
|---|---|---|
| Production | `fobvnshrqxduuhzgflvd` | Railway service `imaginative-peace`, `ENV=production` |
| Staging | `avkhpachzsbgmbnkfnhu` | Pooler-only from local Windows (see note below) |
| Dev | `umhtnqxdvffpifqbdtjs` | Never use for any real work |

- Never mix production and dev Supabase projects during cleanup, verification,
  migrations, or auth debugging
- Railway backend service `imaginative-peace` must include `RESEND_API_KEY`
- **Staging connectivity (locked June 30 2026):** The direct-connect endpoint
  `db.avkhpachzsbgmbnkfnhu.supabase.co:5432` is IPv6-only and unreachable from
  the local Windows network. Use the pooler for all Alembic operations against
  staging: `aws-0-eu-west-1.pooler.supabase.com:6543`. Tests run against local
  Docker PostGIS only — never against remote Supabase directly.

### Staging environment

- Staging Railway service targets `avkhpachzsbgmbnkfnhu`; all smoke and integration
  runs must hit staging, not production
- Smoke runner safeguards: refuses to run when `ENV=production`; auto-teardown
  soft-deletes all smoke-created data
- Staging accounts mirror production accounts (identify by email, not user_id)

## Local test infrastructure (restored June 30 2026)

- **Target:** Docker PostGIS container `local-postgis`, database `testdb`
- **Connection:** `postgresql+psycopg://postgres:postgres@localhost:5432/testdb`
- **How it's selected:** `TEST_DATABASE_URL` env var; defaults to localhost if unset
- **Full suite runtime:** minutes locally vs 2-3 hours against remote Supabase
- **Coverage baseline:** 95.35%, zero pytest errors, zero pyright errors (HEAD `8330285`)

### Bootstrapping a fresh Docker PostGIS instance

```powershell
docker run --name local-postgis -e POSTGRES_PASSWORD=postgres -p 5432:5432 -d postgis/postgis

docker exec local-postgis psql -U postgres -c "CREATE DATABASE testdb;"
docker exec local-postgis psql -U postgres -d testdb -c "CREATE EXTENSION IF NOT EXISTS postgis;"
docker exec local-postgis psql -U postgres -d testdb -c "CREATE SCHEMA IF NOT EXISTS internal;"
docker exec local-postgis psql -U postgres -d testdb -c "CREATE SCHEMA IF NOT EXISTS extensions;"

# Supabase-reserved roles — vanilla Postgres lacks these, migrations require them
docker exec local-postgis psql -U postgres -d testdb -c "
CREATE ROLE anon NOLOGIN;
CREATE ROLE authenticated NOLOGIN;
CREATE ROLE service_role NOLOGIN;"

$env:DATABASE_URL = "postgresql+psycopg://postgres:postgres@localhost:5432/testdb"
.venv\Scripts\python -m alembic upgrade head
```

### Running the full test suite

```powershell
$env:TEST_DATABASE_URL = "postgresql+psycopg://postgres:postgres@localhost:5432/testdb"
$env:PYTHONPATH = "."
.venv\Scripts\python -m pytest --cov=app --cov-report=term-missing --cov-fail-under=95.0 -q
```

## Production accounts

| user_id | email | role | agency |
|---|---|---|---|
| 1 | apineorbeenga@gmail.com | admin | NULL |
| 2 | apineorbeenga@outlook.com | agency_owner | Apine Real Estate (id=1) |
| 3 | apineorbeenga@yahoo.com | agent | Apine Real Estate (id=1) |
| 4 | apineterngu19@gmail.com | seeker | NULL |

## Locked product decisions

- Agency-first public hierarchy: Agencies → Listings → Agents
- Four active roles: `seeker`, `agent`, `agency_owner`, `admin`
- `users.agency_id` is authoritative only for `agency_owner` (ownership context);
  `agency_agent_memberships` is the sole source of truth for agent affiliation
- Admin's only user-level power is `is_active` (deactivate/reactivate);
  all role transitions are membership-driven and owned by agencies —
  promote/demote buttons are permanently removed from the admin UI
- Property moderation enum (Phase M/N): `draft / agency_review / agency_rejected /
  admin_review / admin_rejected / live / revoked`
- Append-only tables (never UPDATE or DELETE):
  `agent_membership_audit`, `listing_events`, `listing_instructions`,
  `notifications`, `inquiry_replies`
- **Schema topology (locked Phase S):** trigger functions, utility functions, and
  scheduled job procedures go in the `internal` schema, never `public`.
  `public` is the PostgREST API exposure layer. `internal` is invisible to the
  REST API by design. See PREFLIGHT.md PostgREST Schema Topology Standard.
- **Production gating (Phase S.8):** `app/utils/validation.py` rejects placeholder
  names (`Preview`, `Test`, `Smoke` at word boundaries) and test emails on all
  creation schemas. Gate is skipped when `ENV != "production"`.
- **ModerationStatus serialization:** always use `.value`, never `str()`.
  `str(ModerationStatus.live)` produces `"ModerationStatus.live"` which breaks
  dict keys in API responses.
- **Notifications trigger:** `prevent_notifications_delete` fires `BEFORE DELETE`
  only (not UPDATE). Migration `7d8c295c7ef6` corrected the S.1 regression that
  had it blocking UPDATE, which was silently breaking `PATCH /notifications/read`.
- **`mark-responded` endpoint:** deprecated. Do not call from frontend. Reply
  creation in `inquiry_replies` handles status transition automatically.
- **Reply thread polling:** currently 30s. Phase T.2 targets 10s or Supabase
  Realtime/SSE for conversational feel.
- All other locked decisions from Phases G–R remain in force. See DEFERRED.md.

## Phase S close summary

| Task | Delivery |
|---|---|
| S.1 | Trigger functions moved from `public` → `internal` schema |
| S.2 | `last_login` + `is_active`, login tracking on `/users/me`, deactivate/reactivate endpoints, middleware gate |
| S.3 | Admin user segmentation backend — role/activity_state filters, counts endpoint |
| S.4 | Admin Users page — six tabs, deactivate/reactivate, promote/demote permanently removed |
| S.5 | Agency owner Inactive agent tab — `last_login` in roster, 90-day client-side filter |
| S.6 | Multi-turn reply threading backend — seeker reply, `author_role`, PATCH edit, trigger softened |
| S.7 | Reply thread UI — `ReplyThread` component, bubble styling, composer for both parties |
| S.8 | Production gating — placeholder name/email validation on all creation schemas |
| Infra | Docker PostGIS local test infrastructure restored; full suite in minutes, 95.35% coverage |

Backend HEAD at Phase S close: `8330285`
Frontend HEAD at Phase S close: `e1d2f04`
Migration head: `7d8c295c7ef6`

## Phase T close summary

| Task | Delivery |
|---|---|
| T.1 / DEF-S-ADMIN-MEM-001 | `GET /api/v1/admin/users/{id}/memberships/` endpoint + frontend wiring. Backend merged via PR #9. Auth issue (401 admin vs 403 non-admin) confirmed to be a JWT/token configuration mismatch on staging — code behaviour is correct. |
| T.2 | `parent_reply_id` FK on `inquiry_replies`, self-referential relationship, validation, eager-loading, recursive schema. Backend commit `76d6d1f` on `feature/t-2-conversational-threading`, PR #11 to staging. Frontend (quoted reply preview, reply action on bubbles, 10s polling) deferred. |
| T.2-frontend | Quoted reply preview, reply action on bubbles, 10s polling — pending Railway deploy → `pnpm gen:types` → frontend logic |
| Infra | Docker PostGIS local test infrastructure restored; full suite runs locally in minutes, 95%+ coverage maintained. |

Backend HEAD at Phase T close: `76d6d1f`
Frontend HEAD at Phase T close: `e1d2f04`
Migration head: `a4de654baa02`

## Phase T opening backlog

| ID | Item | Priority |
|---|---|---|
| T.2-frontend | Quoted reply preview, reply action on bubbles, 10s polling | High |
| DEF-J-EMAIL-DOMAIN-001 | Resend domain verification — operator action, no code changes | High |
| DEF-Q-UNBLOCK-002 | Multi-membership edge case in `_apply_membership_role_after_status_change` | Medium |

## Pre-flight enforcement

- **Before any backend code is written**, the agent MUST output a pre-flight
  confirmation block listing at least 5 locked rules from PREFLIGHT.md.
- **No bare `id` in protected_fields.** All PK column names must be
  domain-qualified: `inquiry_id`, `reply_id`, `property_id`. Bare `id` violates
  PREFLIGHT.md Canonical Rule 2.
- **PREFLIGHT.md is law, not reference.** Read it independently before writing
  code. Attaching it is not sufficient.

## Review priorities

1. DB to ORM alignment
2. Migration safety
3. Enum/value correctness
4. Auth/token consistency
5. Test coverage for changed behaviour
6. RLS/security implications
7. Minimal, maintainable diffs

## Next session handover

- Phases G through S are closed. Do not reopen unless investigating a regression.
- Phase T is active. `T.1` backend is merged (PR #9), `T.2` backend is PR'd (#11 to staging).
  Next: validate PR #11 on staging, run `pnpm gen:types`, then commit frontend for
  T.1 wiring + T.2 quoted reply preview, reply action on bubbles, 10s polling.
- `T.1` admin JWT 401-401 issue confirmed to be staging JWT secret mismatch — not a code bug.
- Docker PostGIS is the local test target. Staging Supabase is for deployed
  environment validation only, via pooler connection.
- `detect-secrets` pre-commit hook is active on the backend repo.
- Sequential deploy order is non-negotiable: backend → Railway green → gen:types → frontend.
- Browser evidence is required for all done-when criteria — code presence alone
  is not completion.