# Deferred Items

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

## Phase H backend B1-B3 close update (May 3, 2026)

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

Remaining Phase H/backlog items after B1-B3:
- Frontend-only TBT and `core-js` cleanup remain outside this backend batch.
- Audit log retention remains deferred until enough production traffic exists to size policy.
- psycopg3 dev prepared-statement investigation remains a dev-environment follow-up.
- Advanced map view, saved search notifications, Nominatim/OSM geocoding, custom domain setup, and external storage bucket policy automation remain open.
- Email notification service is code-complete for SendGrid but still depends on live provider/sender verification confirmation.

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

## DEF-002: Audit log retention (Promoted to Phase H)

No real traffic data yet to size policy against.

Revisit after 60 days of production usage. Decision at that point:
- rolling window (e.g. 90 days)
- archive-to-cold-storage strategy

## DEF-G-INQ-002 (Resolved): Inquiry cards missing property title/link on agent inbox

Agent `/account/inquiries` cards are backed by received-inquiry responses that include nested property data.

Resolved status:
- `GET /api/v1/inquiries/received` serializes the related property payload.
- Production G.7 smoke confirmed the agent received-inquiries endpoint returns successfully after a seeker inquiry.
