# RealtorNet - Backend CLAUDE.md

## Entry State

FastAPI backend deployed on Railway. Sentry is instrumented.
Phase F is closed. Phase G is closed as of April 29, 2026. Phase H is active.

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
- Production migration head: `a6b2d9f4c801`
- Public registration creates a Supabase Auth identity first, then mirrors that UUID into the local `users` row
- Registration rollback deletes the Supabase Auth user if the local DB write fails
- Runtime auth is still based on backend-issued JWTs after login, not direct validation of raw Supabase access tokens
- Legacy account reconciliation is still an open backend concern
- Never mix production and dev Supabase projects during cleanup, verification, or auth debugging

## RLS State

- RLS is enabled on all 14 public tables
- RLS was confirmed across all 14 Phase G tables at close
- `scripts/check_rls.sql` is the canonical verification query for future restores, clones, and manual dashboard edits

## Storage Buckets

- Required buckets: `property-images`, `profile-images`, `agency-logos`
- Buckets are auto-provisioned and validated at deploy/startup time
- Storage bootstrap must never take Railway health down with it

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
- `/api/v1/admin/properties` is admin-only and must serialize safely without leaking raw PostGIS objects
- `/api/v1/property-types/` is the source of truth for property type dropdowns
- `PATCH /api/v1/properties/{property_id}/verify` is the canonical listing moderation contract for UI review flows; admins can set all moderation states, while owning agents can publish or return their own listing to pending review.
- `PUT /api/v1/admin/properties/{property_id}/approve` is an admin-only legacy activation shortcut retained for back-office compatibility; it aligns the record to the verified moderation state and activates listing status.
- `/api/v1/agency-memberships/*` is the canonical authenticated membership visibility surface. The legacy `/api/v1/membership/*` alias was removed in Phase H B1 because frontend consumers use `/agency-memberships/*`.
- Property creation currently enforces agency membership via `users.agency_id`
- Agent promotion must atomically create an `agent_profiles` row in the same transaction
- Pagination and visibility assumptions should always be pulled from actual endpoint code, not memory
- Trailing slashes matter on authenticated endpoints because 308 redirects can drop Bearer headers on some clients; frontend OPEN-001 normalized paths and is deployed

## Phase H Endpoint Maps

### Analytics And Admin Stats

- Canonical admin dashboard analytics surface: `/api/v1/analytics/system/stats`, `/api/v1/analytics/system/usage`, and `/api/v1/analytics/system/integrity`; all are admin-only and return the typed `SystemStatsResponse`, `UsageMetricsResponse`, and `DataIntegrityResponse` contracts.
- `/api/v1/admin/stats` is an admin-only compatibility wrapper over the same system-stats service used by `/analytics/system/stats`.
- `/api/v1/admin/stats/overview` is intentionally smaller than analytics: it returns only `total_users`, `total_properties`, `approved_properties`, and `pending_properties` for quick back-office counters.

### Agent Profile Support

- `GET /api/v1/agent-profiles/{profile_id}/reviews` is public and paginated through the shared `skip`/`limit` dependency; it returns `AgentReviewResponse[]` for the profile user's agent reviews.
- `GET /api/v1/agent-profiles/{profile_id}/stats` is public and returns aggregate profile stats from `agent_profile_crud.get_stats`.

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

## Phase G Close State

- Four-role model is live: seeker / agent / agency_owner / admin
- `agency_agent_memberships` is the canonical multi-agency membership table
- Agency application, approval, invitation, acceptance, join request, membership review, featured property, and moderation enum flows are live
- Production G.7 smoke passed 12/12 on April 29, 2026
- New agency journey passed end to end on production: agency applied, admin approved, owner invited agent, agent accepted, agent listed property, property appeared in agency inventory, seeker sent inquiry
- Local pyright passed with 0 errors
- Local pytest passed after local PostGIS was started: coverage 92.99%
- G.7 smoke production cleanup completed: `agency_id=8`, `property_id=5`, `inquiry_id=5`, related invitation/membership rows, and disposable smoke users `86`, `87`, `88` are soft-deleted; the four real accounts remain active

## Phase H Active State

- Current migration head is `a6b2d9f4c801`
- Agency inquiry aggregation endpoint is live: `GET /api/v1/agencies/{agency_id}/inquiries/`
- Agency and user decision reasons are live: `agencies.status_reason`, `users.deactivation_reason`, and `users.role_change_reason`
- First-time agency owner approval flow is live: approved applicants can register with the approved owner email and receive `agency_owner` plus the approved `agency_id`
- Email provider is SendGrid via `SENDGRID_API_KEY` and `MAIL_FROM`/`EMAIL_FROM`
- Transactional email dispatch is fail-open: provider failures are logged and must not block the triggering API request

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

- Phase G is closed; start future work from Phase H only after Phase H scope is explicitly opened
- First Phase H action should verify the G.7 production smoke cleanup remains complete before new production work
- Keep production and dev Supabase separation strict during all work
- Treat agency card branding as blocked on backend enrichment until the response contract changes
- Keep Railway `/healthz` returning 200 in degraded mode; Redis rate limiting should connect through `REDIS_URL` or Railway `REDISHOST`/`REDISPORT`/`REDISUSER`/`REDISPASSWORD`
