# Deferred Items

## DEF-L-ADMIN-AUDIT-001: Admin dashboard audit activity

Phase L dispatch item. The audit views are present in the database, but admins
should not need direct SQL access for routine activity review.

Backend brief:
"Add GET /api/v1/admin/audit/ endpoint — role-gated to admin only. Query all
three audit views (audit_creations, audit_deletions, audit_recent_changes) and
return a combined response: creation count (last 30 days), deletion count (last
30 days), and a paginated list of recent changes (default 20 rows). Pyright 0,
pytest ≥ 85% on the new router."

Frontend brief:
"Add an 'Audit Activity' section to /account/admin/analytics. Use existing
StatCard components for the two counts and a simple table for recent changes —
same visual pattern as current analytics sections. Source: the new audit
endpoint above. Only visible to admin role. tsc 0, lint 0, build 0."

## Phase G close update (April 29, 2026)

Phase G backend exit is closed after production smoke validation.
Post-close cleanup is complete: the G.7 smoke agency (`agency_id=8`), property (`property_id=5`), inquiry (`inquiry_id=5`), related invitation/membership records, and disposable smoke users `86`, `87`, and `88` were soft-deleted. The four real production accounts remained active.

Closed in Phase G:
- `DEF-G-INQ-002`: Inquiry property hydration fixed by serializing related property data on received inquiries.
- `DEF-G-AG-001`: Agency identity is live where the current response contract supports it; property-card-wide branding remains blocked until the property list contract is expanded without N+1 fetches.
- `DEF-G-AG-002`: Agency application and admin approval flow is live.
- `DEF-G-MOD-001`: Moderation status enum is live: pending_review / verified / rejected / revoked.

Promoted to Phase H:
- `DEF-G-TBT-001`: TBT < 100ms remains frontend architecture work after launch.
- `DEF-G-POLYFILL-001`: Residual third-party `core-js` cleanup remains post-launch dependency work.
- `DEF-002`: Audit log retention remains deferred until 60 days of real traffic.
- `DEF-007`: psycopg3 dev restart workaround remains a development-environment follow-up.
- Agency owner onboarding self-service, advanced map view, admin analytics, saved search notifications, Nominatim/OSM geocoding, email notification service, agency aggregation optimization, custom domain setup.

## Phase H close update (May 6, 2026)

Phase H is closed after backend B1-B3, frontend F1-F3, Resend delivery confirmation, and production smoke validation.

Closed in H.1 email:
- H.1 transactional email infrastructure is formally closed: Resend is live, a test email was delivered through the verified temporary sender, and the production smoke passed.
- Resend is the canonical provider. `MAIL_FROM=onboarding@resend.dev` is temporary until a custom RealtorNet sender domain is registered and verified.
- Railway backend service `imaginative-peace` now requires `RESEND_API_KEY` in Variables; the propagation issue was resolved and verified during the provider swap.
- Railway `ENV=production` drift was caught and fixed; the backend was previously booting from the development default.

Closed in backend B1:
- Membership alias ambiguity resolved: `/api/v1/agency-memberships/*` is canonical and the legacy `/api/v1/membership/*` router registration was removed.
- Public property list filtering by `property_type_id` is live and covered by endpoint tests.
- Property moderation contract clarified: `PATCH /api/v1/properties/{property_id}/verify` is canonical for UI moderation; `PUT /api/v1/admin/properties/{property_id}/approve` remains a legacy admin activation shortcut.
- `app/services/storage_services.py` coverage raised above 80% with mocked Supabase storage upload/delete/URL tests.

Closed in backend B2:
- Admin analytics backend contracts documented: `/analytics/system/*` is canonical for dashboard analytics, `/admin/stats` is a compatibility wrapper, and `/admin/stats/overview` is a small counter payload.
- Agent profile reviews/stats, inquiry-by-property, current-user review lists, amenity categories/popular stats, and favorite enrichment endpoints are implemented, tested, and documented for frontend consumers.

Closed in backend B3:
- Agency profile editing is live for admins and for an agency owner editing their own public agency fields; agency status, verification, and owner decision fields remain admin-only.
- Public agent directory supports pagination, `agency_id`, and inventory-derived `location_id` filtering.
- Location hierarchy contract is documented as string-based state/city/neighborhood filtering because the current DB does not have separate state_id/city_id tables.
- Saved search detail and update owner/admin contracts are implemented and covered by endpoint tests.

Promoted to Phase I:
- `DEF-H4-MOBILE-TBT`: Mobile total blocking time remains Phase I frontend performance work.
- `DEF-I-LOC-001`: Location hierarchy/geocoding remains Phase I location architecture work.
- Audit log retention remains deferred until enough production traffic exists to size policy.
- psycopg3 dev prepared-statement investigation remains a dev-environment follow-up.
- Advanced map view, saved search notifications, Nominatim/OSM geocoding, custom domain setup, and external storage bucket policy automation remain open.

## Phase I saved-search notifications update (May 6, 2026)

Implemented in I.2:
- Saved-search match notifications default to immediate delivery when a listing first transitions to `verified`.
- Unsubscribe uses the existing saved-search soft-delete lifecycle because the table does not have an `is_active` column.

Deferred to Phase J:
- `DEF-I-SEARCH-FREQ-001`: Add saved-search notification frequency preferences and UI. Until that preference exists, Phase I sends immediately and records this default in backend behavior/tests.

## Phase J workbook and closeout update (May 13, 2026)

The Phase J workbook is now attached at repository root as `RealtorNet_Phase_J_Workbook.md` and is the current execution reference.

Closed before Phase J active dispatch:
- `DEF-I-MEM-SMOKE-001`: Multi-agency revocation smoke passed in production. Agent `user_id=90` had two active memberships; revoking the temporary second membership left `user_role=agent`, kept `role_version=6`, marked only the temporary membership inactive, and left the original active membership intact. Temporary agency `12`, owner `92`, invite `4`, and membership `7` were soft-deleted after verification.
- `DEF-I-COV-001`: Coverage gate is closed. Commit `7e8fd35` raised backend coverage to 95.03%; `pyright` returned 0 errors and full `pytest -q` passed.
- `DEF-I-LOC-001`: Dynamic location resolution is live. Property create/update accepts `location_name`; backend resolves server-side through Nominatim, stores rows through `location_crud.get_or_create()`, and exposes `GET /api/v1/locations/search?q=&limit=` for frontend autocomplete. No manual broad seeding is required.

Phase J active backlog:
- `DEF-J-EMAIL-DOMAIN-001`: Real-user email delivery remains blocked until a verified sender domain is configured in Resend and Railway `MAIL_FROM` is updated.
- `DEF-J-MAP-001`: Interactive `/properties` map view with Leaflet/OSM pins from resolved coordinates.
- `DEF-J-LOC-001`: Location breadth/result-quality monitoring; prefer Nigerian-relevant Nominatim results and prevent global location pollution.
- `DEF-J-FREQ-001`: Saved-search notification frequency preferences; current behavior remains immediate delivery.
- `DEF-J-MSG-001`: In-app messaging / inquiry reply thread model.
- `DEF-J-AGG-001`: Agency public-directory aggregation optimization after traffic data.
- `DEF-002`: Audit log retention decision after enough production volume exists.

## Phase K Stream A-C backend update (May 25, 2026)

Backend infrastructure and data-gap items deployed in commit `52f14b5`:

Stream A — Settings & Infrastructure:
- A.1: Settings class environment variable names confirmed aligned (SUPABASE_SERVICE_ROLE_KEY, REDIS_URL); redis://localhost:6379 defaults are intentional fallbacks replaced if platform Redis available
- A.2: Test telemetry isolated — `SENTRY_DSN=""` added to conftest.py to prevent test errors (including RuntimeError: surprise from test mocks) leaking to production Sentry

Stream B — Frontend-Blocking Data Gaps:
- B.1: `property_count` added to agency list response via canonical query (verified + not deleted); CRUD layer computes per agency in get_multi()
- B.2: New public `/api/v1/agents/` directory endpoint deployed; returns agent display_name (first_name + last_name) with agency_name affiliation; no generic/null names filtered
- B.3: 12 property types seeded via Alembic migration (20260524_0000): Apartment, House, Bungalow, Duplex, Condo, Townhouse, Land, Commercial, Office, Warehouse, Shop, Semi-detached

Stream C — Sentry Code Fixes:
- C.1: Image format validation (imghdr magic-bytes check) added before resize_image() to reject non-image files early with clear error
- C.2: Storage delete confirmed using service role client; buckets still need RLS policies (0 → 4 each) via operator action in Supabase dashboard
- C.3: RuntimeError: surprise was from test_property_amenities.py mock; resolved by A.2 Sentry isolation (tests no longer leak to production)
- C.4: Stats overview error logging improved with exc_info=True and error_type context

Stream D — Stats Canonical Sources:
- Agency detail (GET /agencies/{id}) and stats (GET /agencies/{id}/stats) endpoints both use agency_crud.get_stats() with canonical queries
- agent_count: count_active_members (distinct users with active non-deleted memberships)
- property_count: count(property_id) WHERE agency_id=X AND moderation_status=verified AND deleted_at IS NULL

Pending completion:
- Railway deployment confirmation: migration must complete and property-types endpoint must return 12 types
- E.1–E.3: Production SQL verification (smoke user deletion, user_id=74 data consistency, property 3 listing_type) — queries corrected (display_name→first_name/last_name, id→user_id/property_id), ready for Supabase SQL editor execution
- F: N+1 query investigation — enable locally via DEBUG=true + SQLAlchemy echo (already configured in database.py line 24)
- Frontend action: After B.1 confirmed live on Railway, run `pnpm gen:types` to regenerate API types from updated OpenAPI schema

## Phase K quality gate update (May 26, 2026)

Backend quality gates now fully enforced:
- Coverage: raised from 94.97% → 95.23%; `pytest.ini --cov-fail-under` updated from 92.78 to 95.0
- New test: `tests/core/test_exceptions.py` covers `ErrorHandler.global_exception_handler` (all 3 dispatch paths) and `ValidationException`, `AuthorizationException`, `ResourceNotFoundException` constructors
- pyright: 0 errors confirmed after new test file
- CI fix: `.github/workflows/ci.yml` now exports `POSTGRES_SERVER`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, `POSTGRES_PORT` at job-runner level so pydantic-settings `Settings()` instantiates cleanly without a `.env` file; added `pyright` step and `alembic upgrade head` before tests
- E.1–E.3 query bugs fixed in `scripts/PRODUCTION_VERIFICATION.md`: `display_name` column does not exist on `users` table (correct: `first_name`/`last_name` concat); `WHERE id =` corrected to `WHERE user_id =` (E.2) and `WHERE property_id =` (E.3)

## DEF-L-POSTGIS-001: Move PostGIS to extensions schema (Phase L)

PostGIS is currently installed in the `public` schema. Best practice is to install
it in a dedicated `extensions` schema so PostGIS objects do not pollute the public
namespace and do not interact with `SET search_path = ''` function hardening.

Blocked on: operator action to reinstall PostGIS into the `extensions` schema in
Supabase project `avkhpachzsbgmbnkfnhu`. Cannot be done via Alembic migration alone
because PostGIS extension installation requires superuser privileges.

Action required (Phase L):
1. Create `extensions` schema if not present.
2. Drop and reinstall PostGIS into `extensions` schema via Supabase dashboard or
   `psql` with superuser: `CREATE EXTENSION postgis SCHEMA extensions;`
3. Update any Alembic migrations or ORM code that reference `public.geometry` or
   `public.geography` types to use `extensions.geometry` / `extensions.geography`.
4. Verify `scripts/check_rls.sql` still passes after schema move.

## DEF-K-AUDIT-FK-001: Smoke-user hard delete blocked by immutable membership audit

Phase K Task 1A cleaned production Codex smoke accounts `user_id=90` and `user_id=91`
from live operational tables and deleted their Supabase Auth identities. The local
`users` rows were soft-deleted, not hard-deleted, because `agent_membership_audit`
is intentionally append-only and its `user_id` foreign key is `ON DELETE CASCADE`
with a non-null column. Hard-deleting those users would cascade into the immutable
audit table and correctly fire `prevent_agent_membership_audit_mutation()`.

Deferred to Phase L: decide whether membership audit should support orphaned
historical records through a nullable `user_id` / non-cascading FK, or keep the
current schema and retain soft-deleted smoke users as historical principals.

## DEF-J-EMAIL-DOMAIN-001: Verify RealtorNet transactional sender domain

Current production sender remains `MAIL_FROM=onboarding@resend.dev`, which is Resend's temporary sender. This is only suitable for Resend test/sink delivery and is not a production sender for real user inboxes.

Email delivery to real inboxes is blocked pending a verified RealtorNet-controlled sender domain. Resend requires a verified custom domain to send reliably to recipients outside its allowed testing flow. Estimated cost: roughly $10-15/year for a basic `.com.ng` or `.com` domain, plus DNS verification time.

Until resolved, platform email notifications must be treated as non-functional for real users even though the backend Resend integration and sync dispatch path are operational. After the domain is verified in Resend, update Railway `MAIL_FROM` to the verified sender, for example `noreply@realtornet.com.ng`. Keep this as an environment variable; do not hardcode the sender in application code.

## DEF-006: Supabase storage bucket provisioning and policy verification

Phase D fixed backend storage writes by switching all upload/delete operations to the admin client, but bucket existence, public exposure, and environment-side policy verification still live outside this repo.

Current expectation: `property-images`, `profile-images`, and `agency-logos` already exist in each target Supabase project before backend deploys.

Pre-launch: add deployment-time validation or provisioning automation so storage buckets and required access settings are checked explicitly per environment.

## DEF-007: psycopg3 prepared statement corruption in dev (Promoted to Phase H)

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

## DEF-G-MOD-001 (Resolved): Full moderation status workflow

Phase G replaced the previous boolean-only workflow with an explicit `moderation_status` enum covering `pending_review`, `verified`, `rejected`, and `revoked`.

Resolved status:
- `PATCH /api/v1/properties/{property_id}/verify` accepts moderation status and reason
- Admin can set verified/rejected/revoked/pending_review
- Agent-facing status is backed by the enum contract
- Public feed excludes non-verified listings

## DEF-002: Audit log retention

Assessed at Phase J close (May 2026). Production volume too low to warrant
a retention policy: 7 registered users, 2 properties, 4 inquiries at time
of assessment. No material growth in audit_logs table observed.
Decision: defer to Phase K. Trigger for implementation:
audit_logs table exceeds 10,000 rows OR production user count exceeds 500.
Revisit at Phase K open.

## DEF-G-INQ-002 (Resolved): Inquiry cards missing property title/link on agent inbox

Agent `/account/inquiries` cards are backed by received-inquiry responses that include nested property data.

Resolved status:
- `GET /api/v1/inquiries/received` serializes the related property payload.
- Production G.7 smoke confirmed the agent received-inquiries endpoint returns successfully after a seeker inquiry.
