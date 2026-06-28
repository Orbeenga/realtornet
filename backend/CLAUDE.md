# RealtorNet - Backend CLAUDE.md

## Entry State

FastAPI backend deployed on Railway. Sentry is instrumented.
Phase F through Phase Q are closed. Phase R is closed as of June 23, 2026.
Phase S open — Schema Hardening, User Intelligence & Communications Completion.
Backend HEAD: `4eb6ba3` (fix: add savepoint retry for pg_proc contention).
Migration head: `3a7b9c1d2e4f` (revoke EXECUTE on trigger functions + alter default privileges).

Use the root [CLAUDE.md](C:/Users/Apine/realtornet/CLAUDE.md) first, then this file for backend-specific state.

## Deployment

- Platform: Railway
- Health check: `GET /healthz`
- `/healthz` must return `200` even in degraded mode
- Storage bootstrap is fail-open during startup, so storage issues must not block process health
- Work flows: feature -> staging -> validate -> merge to main -> production.
- Correct branch flow is staging first, manual validation second, then a deliberate merge or promotion to main for production.
- If staging and main both receive pushes, verify this is the intentional two-step promotion flow. Railway/Vercel may pick up branches independently, but production must never be an accidental side effect of unvalidated staging work.
- **Commit order is strictly: backend first, then frontend.** Backend commit → push → wait for Railway deploy (green `/healthz`) → `pnpm gen:types` against production OpenAPI → if types changed, commit gen:types result → push → finally commit frontend logic changes. Never commit backend and frontend in the same batch. gen:types must resolve against a live, deployed backend, not a pending one.

## Database And Auth

- Database: Supabase PostgreSQL
- Auth source of truth: Supabase Auth
- Production Supabase project ref: `fobvnshrqxduuhzgflvd`
- Dev Supabase project ref: `umhtnqxdvffpifqbdtjs`
- Production migration head: `3a7b9c1d2e4f` (revoke EXECUTE on trigger functions + alter default privileges)
- Current quality gate: pyright 0 errors; pytest passed; total coverage 95.16%
- Public registration creates a Supabase Auth identity first, then mirrors that UUID into the local `users` row
- Registration rollback deletes the Supabase Auth user if the local DB write fails
- Runtime auth is still based on backend-issued JWTs after login, not direct validation of raw Supabase access tokens
- Legacy account reconciliation is still an open backend concern
- Never mix production and dev Supabase projects during cleanup, verification, or auth debugging

## RLS State

- RLS is enabled on all exposed public tables, including Phase I `agent_membership_audit` and `review_requests`
- RLS was confirmed across all 14 Phase G tables at close
- `scripts/check_rls.sql` is the canonical verification query for future restores, clones, and manual dashboard edits

## Storage Buckets

- Required buckets: `property-images`, `profile-images`, `agency-logos`
- Buckets are auto-provisioned and validated at deploy/startup time
- Storage bootstrap must never take Railway health down with it

## Append-Only Tables

The following tables are append-only — never UPDATE or DELETE rows in production code:
- `agent_membership_audit` — membership state change history
- `listing_events` — listing lifecycle events
- `listing_instructions` — mediation instructions with `triggered_by_event_id` FK
- `notifications` — in-platform notification records
- `inquiry_replies` — inquiry reply threading (Phase R)

## Endpoint Contracts

- `POST /api/v1/agencies/apply/` creates pending agency applications
- `PATCH /api/v1/admin/agencies/{agency_id}/approve/` approves applications and promotes the owner to `agency_owner`
- `PATCH /api/v1/admin/agencies/{agency_id}/reject/` rejects agency applications
- `POST /api/v1/agencies/{agency_id}/invite/` creates agency invitations
- `POST /api/v1/agencies/accept-invite/` accepts invitation tokens and promotes users to agency agents
- `GET /api/v1/properties/featured` returns featured public listings
- `GET /api/v1/agencies/{agency_id}/inquiries/` returns paginated agency-wide inquiry rollup for agency owners and admins
- `PATCH /api/v1/properties/{property_id}/verify` accepts moderation status values: pending_review / verified / rejected / revoked
- `GET /api/v1/properties/` accepts `property_type_id` as a public query filter; the endpoint forwards it through the shared `PropertyFilter` contract to the canonical property CRUD query.
- `GET /api/v1/properties/` accepts `agency_id` for agent, agency_owner, and admin callers only; seekers and anonymous users receive 403 when `agency_id` is supplied.
- `/api/v1/admin/properties` is admin-only and must serialize safely without leaking raw PostGIS objects
- `/api/v1/property-types/` is the source of truth for property type dropdowns
- `PATCH /api/v1/properties/{property_id}/verify` is the canonical listing moderation contract for UI review flows; admins can set all moderation states, while owning agents can publish or return their own listing to pending review.
- `PUT /api/v1/admin/properties/{property_id}/approve` is an admin-only legacy activation shortcut retained for back-office compatibility; it aligns the record to the verified moderation state and activates listing status.
- `/api/v1/agency-memberships/*` is the canonical authenticated membership visibility surface. The legacy `/api/v1/membership/*` alias was removed in Phase H B1 because frontend consumers use `/agency-memberships/*`.
- `GET /api/v1/users/me/membership-history/` returns the authenticated user's membership audit history.
- `GET /api/v1/agencies/{agency_id}/member-history/{user_id}/` returns agency-owner/admin scoped membership audit history for a specific user in that agency.
- `PATCH /api/v1/agency-memberships/{membership_id}/leave/` lets the authenticated member voluntarily leave an active membership and records audit action `left`.
- `POST /api/v1/agencies/{agency_id}/review-requests/` creates a generic agency review/rejoin request for the authenticated user and returns 409 when a pending request already exists for the user+agency pair.
- `GET /api/v1/agencies/{agency_id}/review-requests/` returns pending review requests with membership audit history for agency owners/admins.
- `PATCH /api/v1/agencies/{agency_id}/review-requests/{request_id}/accept/` accepts a pending request, reinstates membership, records audit action `reinstated`, increments `role_version` if seeker access is restored to agent, syncs Supabase Auth metadata, and sends role-change email when the role changes.
- `PATCH /api/v1/agencies/{agency_id}/review-requests/{request_id}/decline/` declines a pending request and sends the requester a review-request decision email.
- Property creation currently enforces agency membership via `users.agency_id`
- Agent promotion must atomically create an `agent_profiles` row in the same transaction
- Pagination and visibility assumptions should always be pulled from actual endpoint code, not memory
- Trailing slashes matter on authenticated endpoints because 308 redirects can drop Bearer headers on some clients; frontend OPEN-001 normalized paths and is deployed

### Inquiry Reply Endpoints (Phase R)

- `POST /api/v1/inquiries/{inquiry_id}/replies/` — create reply (agent/agency_owner only, must own the inquiry)
- `GET /api/v1/inquiries/{inquiry_id}/replies/` — list replies (authenticated, owner or admin)
- **mark-responded endpoint is deprecated**: `PATCH /api/v1/inquiries/{inquiry_id}/mark-responded` exists but should not be called from frontend. Reply creation in `inquiry_replies` now handles response tracking. Do not remove the endpoint.

### Agent Stats Endpoint (Phase R)

- `GET /api/v1/analytics/agents/me/stats/` — agent personal stats (own listings by status, rejected/revoked breakdown, inquiries received, response rate, agency active memberships, rejected/revoked/blocked/left membership counts)

## Phase H Endpoint Maps

### Analytics And Admin Stats

- Canonical admin dashboard analytics surface: `/api/v1/analytics/system/stats`, `/api/v1/analytics/system/usage`, and `/api/v1/analytics/system/integrity`; all are admin-only and return the typed `SystemStatsResponse`, `UsageMetricsResponse`, and `DataIntegrityResponse` contracts.
- `/api/v1/admin/stats` is an admin-only compatibility wrapper over the same system-stats service used by `/analytics/system/stats`.
- `/api/v1/admin/stats/overview` is intentionally smaller than analytics: it returns only `total_users`, `total_properties`, `approved_properties`, and `pending_properties` for quick back-office counters.

### Agent Profile Support

- `GET /api/v1/agent-profiles/` is the public agent directory contract. It supports shared `skip`/`limit` pagination plus optional `agency_id` and `location_id` filters. The `location_id` filter is inventory-derived because `agent_profiles` has no location column: an agent matches when they have at least one verified, non-deleted listing in that location.
- `GET /api/v1/agent-profiles/{profile_id}/reviews` is public and paginated through the shared `skip`/`limit` dependency; it returns `AgentReviewResponse[]` for the profile user's agent reviews.
- `GET /api/v1/agent-profiles/{profile_id}/stats` is public and returns aggregate profile stats from `agent_profile_crud.get_stats`.

### Agency Profile Editing

- `PUT /api/v1/agencies/{agency_id}` is available to admins for any agency and to `agency_owner` users for their own agency only.
- Agency owners may edit public profile fields such as name, email, phone, address, description, logo, and website.
- Only admins may change agency status, verification, owner identity, rejection reason, or status decision fields.

### Inquiry And Review Support

- `GET /api/v1/inquiries/by-property/{property_id}` is authenticated; only the property owner or an admin can read the non-deleted inquiries for that listing.
- `GET /api/v1/reviews/by-user/property/` and `/api/v1/reviews/by-user/agent/` are authenticated owner-scoped endpoints; they return the current user's own non-deleted property and agent reviews.

### Amenities And Favorites Support

- `GET /api/v1/amenities/categories` is public and returns distinct amenity category strings.
- `GET /api/v1/amenities/stats/popular` is public and returns amenities sorted by active-property usage count.
- `GET /api/v1/favorites/is-favorited` is authenticated and returns `{"is_favorited": bool}` for the current user.
- `GET /api/v1/favorites/count/{property_id}` is public and returns `{"property_id": int, "favorite_count": int}` after confirming the property exists.
- `GET /api/v1/favorites/count/user/{user_id}` is authenticated and owner/admin scoped.
- `DELETE /api/v1/favorites/bulk` is authenticated and atomically soft-deletes the current user's favorites for the supplied `property_ids` query list.

### Location Hierarchy

- The current DB contract stores locations as normalized row values, not separate state/city/neighborhood ID tables.
- `GET /api/v1/locations/states` returns distinct state strings.
- `GET /api/v1/locations/cities?state={state}` returns distinct city strings, optionally filtered by normalized state string.
- `GET /api/v1/locations/neighborhoods?state={state}&city={city}` returns distinct neighborhood strings, optionally filtered by normalized state and/or city strings.
- `GET /api/v1/locations/search?q=&limit=` resolves free-text locations server-side through Nominatim and returns reusable `LocationResponse` rows. Browser-direct geocoding is prohibited.
- Property create/update accepts `location_id` for existing records or `location_name` for server-side resolution. When `location_name` resolves, the backend calls `location_crud.get_or_create()` and links the property to the returned `location_id`; if resolution fails, property creation must not be blocked.

### Saved Searches

- `GET /api/v1/saved-searches/{search_id}` returns the authenticated user's own saved search; admins may access any saved search.
- `PUT /api/v1/saved-searches/{search_id}` updates the authenticated user's own saved search; admins may update any saved search.
- `GET /api/v1/saved-searches/unsubscribe/{token}/` is public and soft-deletes the matching saved search by `unsubscribe_token`.
- Saved search criteria remain JSONB and execution reuses the canonical property filter path.
- Saved-search match emails are sent when a property first transitions to `verified`; match detection batches saved-search/user loading and does not query per seeker.

## Phase G Close State

- Four-role model is live: seeker / agent / agency_owner / admin
- `agency_agent_memberships` is the canonical multi-agency membership table
- Agency application, approval, invitation, acceptance, join request, membership review, featured property, and moderation enum flows are live
- Production G.7 smoke passed 12/12 on April 29, 2026
- New agency journey passed end to end on production: agency applied, admin approved, owner invited agent, agent accepted, agent listed property, property appeared in agency inventory, seeker sent inquiry
- Local pyright passed with 0 errors
- Local pytest passed after local PostGIS was started: coverage 92.99%
- G.7 smoke production cleanup completed: `agency_id=8`, `property_id=5`, `inquiry_id=5`, related invitation/membership rows, and disposable smoke users `86`, `87`, `88` are soft-deleted; the four real accounts remain active

## Phase H Closed State

- Current migration head is `a6b2d9f4c801`
- Final local backend gate: pyright 0 errors; pytest 1856 passed; coverage 94.54%
- Agency inquiry aggregation endpoint is live: `GET /api/v1/agencies/{agency_id}/inquiries/`
- Backend B1/B2/B3 contracts are closed: membership alias removed, property type property-list filter live, storage service coverage raised, canonical endpoint maps documented, agency-owner profile edit live, agent directory `agency_id`/`location_id` filters live, location hierarchy contract documented, and saved-search detail/update reconfirmed.
- Public `/agents` directory backend contract is live through `GET /api/v1/agent-profiles/` with pagination, agency filtering, and inventory-derived location filtering.
- `/account/reviews` backend support is live through authenticated current-user review endpoints for property and agent reviews.
- Agency and user decision reasons are live: `agencies.status_reason`, `users.deactivation_reason`, and `users.role_change_reason`
- First-time agency owner approval flow is live: approved applicants can register with the approved owner email and receive `agency_owner` plus the approved `agency_id`
- Email provider is Resend via `RESEND_API_KEY` and `MAIL_FROM`/`EMAIL_FROM`; `RESEND_API_KEY` must be set in Railway service `imaginative-peace` Variables
- Current sender is `onboarding@resend.dev`, which is test-only for real-recipient delivery restrictions. Real user email delivery is blocked until a custom RealtorNet sender domain is registered, verified in Resend, and set in Railway `MAIL_FROM`.
- Transactional email dispatch is fail-open: provider failures are logged and must not block the triggering API request
- Railway backend now runs with `ENV=production`; do not allow production deploys to fall back to the development default.

## Phase I I.2 Saved Search Notifications

- I.2 migration head was `b1f4a9c7e2d3`
- `saved_searches.unsubscribe_token` is a non-null UUID with a unique index.
- Saved-search unsubscribe uses the existing soft-delete lifecycle because there is no `is_active` column on `saved_searches`.
- Notification frequency preferences are deferred as `DEF-I-SEARCH-FREQ-001`; until that preference exists, saved-search match notifications send immediately.

## Phase I I.3 Membership Audit And Role Resolution

- Current migration head is `d3e7c5a1b9f2`
- `agent_membership_audit` is the append-only membership memory layer with actions: `invited`, `joined`, `suspended`, `revoked`, `left`, `reinstated`.
- Production migration verified on new project `fobvnshrqxduuhzgflvd`: Alembic head `49e4e5adc1c7` (add_audit_views), `users.role_version` present, audit table present, RLS enabled, two append-only triggers present, and backfilled `joined` rows for active memberships.
- Backend-issued JWTs include `role_version`; `get_current_user` rejects access tokens whose `role_version` no longer matches the database user row.
- Last active membership revocation or voluntary leave demotes non-owner/non-admin agents to `seeker`, clears `users.agency_id`, increments `users.role_version`, writes audit, and syncs Supabase Auth `app_metadata.role_version`.
- Revoking one membership while another active membership remains does not demote the user; it switches `users.agency_id` to the remaining active membership if needed.
- Agency invitation, invite acceptance, join approval, suspension, revocation/block, restore, review approval, and voluntary leave now write audit rows.
- Final local backend gate: pyright 0 errors; pytest 1866 passed; coverage 94.15%.

## Phase I I.5 Generic Review Requests

- Current migration head is `f4a8c2d9e5b1`
- `review_requests` is the agency-level review/rejoin queue used by the contextual post-revocation frontend flow.
- Production migration verified on new project `fobvnshrqxduuhzgflvd`: Alembic head `49e4e5adc1c7`, `review_requests` present, RLS enabled, three RLS policies present, pending user+agency unique index present, and columns match the I.5 schema.
- Duplicate pending review requests for the same user+agency pair return 409.
- Accepting a review request reinstates or creates the agency membership, writes `agent_membership_audit.action = 'reinstated'`, increments `users.role_version` when `seeker` is restored to `agent`, syncs Supabase Auth app metadata, and dispatches `send_role_change_email` when the role changes.
- Declining a review request records status `declined`, stores the decision reason, and dispatches `send_review_request_status_email`.
- Final local backend gate: pyright 0 errors; `pytest -q` passed; coverage 93.97%.

## Phase J Closed State

- Phase J scope is closed at backend commit `c34bca9` (v0.5.3+): dynamic location resolution, map coordinate serialization, coverage gate, and multi-agency revocation smoke are complete.
- Dynamic location resolution is live: `location_resolution_service.py` calls Nominatim server-side with caching/throttling, `PropertyCreate.location_name` is accepted, and `GET /api/v1/locations/search?q=&limit=` powers frontend autocomplete.
- Email dispatch code is correct for sync mode: `dispatch_email_task` branches on `EMAIL_DELIVERY_MODE` and sync mode runs tasks in-process without requiring a Railway Celery worker.
- Sole remaining Phase J exit criterion: `DEF-J-EMAIL-DOMAIN-001`. Real-user email delivery stays blocked while `MAIL_FROM=onboarding@resend.dev` until a verified sender domain is configured in Resend/Railway and a real inbox delivery is confirmed.
- `DEF-I-MEM-SMOKE-001` is closed with production evidence: agent `user_id=90` retained `user_role=agent` and `role_version=6` after one of two active memberships was revoked; temporary agency `12`, owner `92`, invite `4`, and membership `7` were soft-deleted after verification.
- `DEF-I-COV-001` is closed: commit `7e8fd35` raised coverage to 95.03%, full `pytest -q` passed, and `pyright` returned 0 errors.

## Phase K Closed State

- Backend Stream A–D completed: settings env vars confirmed, property_count in agency list, `/api/v1/agents/` deployed, 12 property types seeded, Sentry fixes, canonical stats sources
- Coverage gate raised to 95.23%; pyright 0 errors; CI fixed with POSTGRES_* env vars and pyright step
- E.1–E.3 queries corrected; production smoke 12/12 passed; new agency journey passed
- `DEF-L-ADMIN-AUDIT-001`: Admin audit endpoint `GET /api/v1/admin/audit/` implemented, tested, and deployed
- `DEF-L-POSTGIS-001`: Closed by clean-slate migration on new production project

## Phase L Opening State

- Phase L execution reference: `docs/DEFERRED.md` and root `CLAUDE.md`
- Promoted K items: audit activity UI frontend, Railway env cut-over to new Supabase project, clean-slate DB propagation verification

## Phase R Closed State

- R.2: `inquiry_replies` table + `POST /inquiries/{id}/replies/` + `GET /inquiries/{id}/replies/` + email task — 27 tests, append-only, RLS enabled
- R.3: Reply composer (agent) + reply display (seeker) — `latest_reply`/`reply_count` wiring confirmed
- R.4: `GET /api/v1/analytics/agents/me/stats/` — agent personal stats endpoint
- R.5: `PATCH /agencies/{id}/agents/{membership_id}/unblock/` — unblock endpoint with role gate + state gate
- R.6: Operational closure — production audit counts, location count (63), Nominatim status confirmed
- R.7: 12-journey integration validation — all parts passed
- Migration head: `d3e4f5a6b7c8` (inquiry_replies)
- Coverage: 95.16%

## Phase S Open Items

| ID | Item | Status |
|---|---|---|
| S.1 | Move prevent_listing_instructions_mutation, prevent_notifications_delete, prevent_inquiry_replies_mutation from public to internal schema. Drop public versions. Update trigger definitions. | Phase S — first task |

## Schema Security

- `internal` schema: trigger functions and utility functions. Not exposed via PostgREST.
  Never place trigger functions in `public`.
- `public` schema: application tables, views, API-callable functions only.
- `extensions` schema: PostGIS and other extensions.
- Hosted Supabase does not permit ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin.
  Schema separation is the only durable privilege boundary for trigger functions.

## Locked Invariants

- Public registration must always downgrade requested role to `seeker`
- Admin and agent roles are internal grants, never browser-assigned
- Promoting a user to agent must leave both `users.user_role = 'agent'` and a live `agent_profiles` row
- Property creation for agents depends on `users.agency_id`
- Agency-wide inquiries remain deferred to Phase G; do not build aggregation shortcuts that create N+1 behavior
- `agent_membership_audit`, `listing_events`, `listing_instructions`, `notifications`, `inquiry_replies` are append-only — never UPDATE or DELETE
- `ModerationStatus` serialisation uses `.value` not `str()`
- `users.agency_id` is valid only for `agency_owner` ownership context — `agency_agent_memberships` is sole source of truth for agent affiliation
- No `@property` on SQLAlchemy ORM models
- `detect-secrets` pre-commit hook is active — any credential pattern blocks commit
- Sequential deploy order: backend → Railway deploys → `pnpm gen:types` → frontend
- **mark-responded endpoint is deprecated**: `PATCH /api/v1/inquiries/{inquiry_id}/mark-responded` exists but do not call from frontend. Reply creation in `inquiry_replies` now handles response tracking. Do not remove.

## Reference Data

- Production currently has 12 property types
- Location data is dynamic and self-populating through server-side Nominatim resolution; do not manually seed broad location data as a substitute for the resolver.

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

- Phase H is closed; do not reopen Phase H unless investigating a regression from the closed Phase H state
- Phase I is closed; Phase J is closed except `DEF-J-EMAIL-DOMAIN-001`
- Phase K is closed; Phase L is closed; Phase M is closed; Phase N is closed; Phase O is closed
- Phase P is closed; Phase Q is closed (June 22 2026)
- Phase R is closed (June 23 2026)
- Phase S is open — current phase
- Keep production and dev Supabase separation strict during all work
- Treat agency card branding as blocked on backend enrichment until the response contract changes
- Keep Railway `/healthz` returning 200 in degraded mode; Redis rate limiting should connect through `REDIS_URL` or Railway `REDISHOST`/`REDISPORT`/`REDISUSER`/`REDISPASSWORD`
- **ModerationStatus serialization**: `str(ModerationStatus.live)` produces `"ModerationStatus.live"` — always use `.value` for clean enum-to-string conversion in dict keys
- **mark-responded is deprecated**: Do not remove, do not call from frontend