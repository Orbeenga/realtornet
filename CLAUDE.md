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
- **Never commit diagnostic scripts, one-off queries, or ad-hoc database checks to the repo.** Run them locally, read the output, delete the file. If a script is needed for reproducibility, it goes in `scripts/` with no hardcoded credentials and a corresponding `.env.example` entry.
- **Never hardcode credentials in committed files.** Any file containing a connection string, API key, or password must be caught by detect-secrets before commit.

## Deployment Workflow
- Work flows: feature -> staging -> validate -> merge to main -> production.
- Correct branch flow is staging first, manual validation second, then a deliberate merge or promotion to main for production.
- If staging and main both receive pushes, verify this is the intentional two-step promotion flow. Vercel may pick up each branch independently, but production must never be an accidental side effect of unvalidated staging work.
- **Commit order is strictly: backend first, then frontend.** Backend commit → push → wait for Railway deploy (green `/healthz`) → `pnpm gen:types` against production OpenAPI → if types changed, commit gen:types result → push → finally commit frontend logic changes. Never commit backend and frontend in the same batch. gen:types must resolve against a live, deployed backend, not a pending one.

## Current phase state
- Phase F closed April 25 2026
- Phase G closed April 29 2026
- Phase H closed May 6 2026
- Phase I closed May 2026
- Phase J closed May 2026; only `DEF-J-EMAIL-DOMAIN-001` (verified sender domain + Railway `MAIL_FROM`) remains open
- Phase K closed May 2026
- Phase L closed May 2026: clean-slate DB propagation on new Supabase project `fobvnshrqxduuhzgflvd`, staging environment live at `realtornet-staging.up.railway.app`, admin audit endpoint live, modals/tabs/detail frontend complete
- Phase M closed June 2026: listing governance system complete, state machine live (draft → agency_review → agency_rejected → admin_review → admin_rejected → live → revoked)
- Phase N closed June 2026 with post-close fixes 2026-06-16: listing instruction mediation system complete, `listing_instructions` table with `triggered_by_event_id` FK gating, reject-permanent transition (`revoked → admin_rejected`), mediated governance read endpoints (revocation-history, rejection-history, agency-queue, inventory, pending-admin), email notification wiring for instruction, frontend mediation CTAs and admin historical views
- Backend HEAD: `4dc6174` (fix: add joinedload for N.2 mediation endpoints)
- Frontend HEAD: `231c6b2` (fix: name resolution rewrite + agent Revoked tab)
- Backend Phase N: N.1 `listing_instructions` table with `triggered_by_event_id` FK (RLS enabled); N.2 mediated governance read endpoints (revocation-history, rejection-history, agency-queue, inventory, pending-admin); N.3 reject-permanent transition (`revoked → admin_rejected`); N.4 email notification wiring for instruction; N.5-N.7 frontend mediation CTAs, admin historical views, instruct-agent hooks
- Coverage: 96.07%; `.coveragerc` legitimately omits: `env.py`, `main.py`, `config.py`, `celery_worker.py`
- `owner_display_name` added to `PropertyResponse` (DEF-N-PROP-001 closed)
- `listing_events` table append-only, RLS enabled
- `listing_instructions` table append-only with `triggered_by_event_id` FK to listing_events, RLS enabled
- `has_instruction`, `instruction_text`, `latest_event_reason` fields on PropertyResponse for mediation context
- Final Phase N housekeeping deployed 2026-06-15: agency_owner visibility for non-public listings, edit-transition revoked→draft after instruction, N.9 walkthrough all 12 steps passed on staging, production deployment verified
- Post-close fixes deployed 2026-06-16: backend N.2 join fix (4dc6174) adds joinedload(Property.owner/agency) to N.2 inline queries fixing null owner_display_name/agency_name; frontend rewrite (231c6b2) replaces AGENCY_NAME_STATES set with tabIsPublicContext parameter in resolveListingDisplayName, adds agent Revoked tab with mediation CTAs, sets staleTime:0 + refetchOnWindowFocus:true on all 5 listing tab hooks
- Phase O closed June 2026: notification system model/migration/fire points/CRUD/hook/bell; O.1 Restore button removed; O.2 instruction box guard; O.3 cancel join request + CANCELLED status; O.4 listing_count aggregate subqueries + agents directory ordering; O.5 property_count stats (verified→live), listings_by_status breakdown; O.6 PREFLIGHT.md membership invariants; O.7 integration validation + ordering test fix + ModerationStatus prefix fix + dynamic breakdown rendering
- Phase Q closed June 21-22 2026: agency owner read endpoints (Q.2), reject-permanent (Q.3), blocked tabs (Q.4), reconsider CTA (Q.5), admin analytics listing breakdown fix, Revoked tab read-only fix, agent Agency Inventory/Public Marketplace dedicated queries, DEFERRED.md updated, all quality gates passed
- Backend HEAD: `1875fed` (fix: by_status groups by moderation_status + .value serialization)
- Frontend HEAD: `739bd1b` (fix: Revoked tab read-only + gen:types sync + agent listings dedicated queries)

## Locked environment decisions
- Production Supabase project ref: `fobvnshrqxduuhzgflvd`
- Dev Supabase project ref: `umhtnqxdvffpifqbdtjs`
- Local backend env had been pointed at dev during investigation; verify target project before any destructive or verification action
- Never mix production and dev Supabase projects during cleanup, verification, migrations, or auth debugging
- Railway backend service `imaginative-peace` must run with `ENV=production`
- Railway backend service `imaginative-peace` must include `RESEND_API_KEY` for transactional email delivery

### Staging environment
- Staging Supabase project ref: `avkhpachzsbgmbnkfnhu` (promoted from retiring project)
- Staging Railway service should target the staging Supabase project; all smoke and integration runs must hit staging, not production
- Smoke runner safeguards:
  - Script refuses to run when `ENV=production`
  - Default `SMOKE_BASE_URL` points to a safe non-production URL; set this explicitly to the staging Railway URL
  - Auto-teardown soft-deletes all smoke-created data (users, profiles, memberships, agencies, properties, inquiries)
- Operator action: run `alembic upgrade head` against `avkhpachzsbgmbnkfnhu`, confirm all migrations apply, then publish the staging Railway URL to agents for all test runs
- Staging accounts mirror production accounts (same emails and roles: admin apineorbeenga@gmail.com, agency_owner apineorbeenga@outlook.com, agent apineorbeenga@yahoo.com, seeker apineterngu19@gmail.com). The staging Supabase project may not have the exact same user_id values; identify staging users by email when running walkthroughs.

## Production accounts (new project fobvnshrqxduuhzgflvd)

| user_id | first_name | last_name | email | is_verified |
|---|---|---|---|---|
| 1 | Orbeenga | Apine | apineorbeenga@gmail.com | true |
| 2 | Orbeenga | Apine | apineorbeenga@outlook.com | true |
| 3 | Orbeenga | Apine | apineorbeenga@yahoo.com | true |
| 4 | Terngu | Apine | apineterngu19@gmail.com | true |

### Production agency

| name | is_verified |
|---|---|
| Apine Real Estate | true |

## Locked product decisions
- Agency-first public hierarchy is locked: Agencies -> Listings -> Agents
- `agency_owner` role is active in the user role enum; all four roles are active: seeker, agent, agency_owner, admin
- Multi-agency membership is represented by the `agency_agent_memberships` table; `users.agency_id` remains the legacy primary agency pointer
- Property moderation status enum is active: pending_review / verified / rejected / revoked
- Property moderation status enum updated (Phase M/N): draft / agency_review / agency_rejected / admin_review / admin_rejected / live / revoked
- Seeker join-request flow is live
- Agent invitation flow is live
- Membership-role resolution is backend-authoritative: membership state changes append to `agent_membership_audit`, last active membership revocation/leave demotes agents to `seeker`, and stale JWTs are rejected by `role_version`
- Agency application and admin approval flow is live
- Featured properties endpoint is live
- Agency branding is pre-launch scope on property detail only for now
- Property-card agency branding stays deferred until the property list response includes agency branding fields; do not introduce N+1 card fetches
- Agency-wide inquiry rollup is live; do not aggregate per-property inquiry calls in the frontend
- Public signup remains seeker-only; admin and agent are backend-authoritative roles
- Resend is the live transactional email provider, but `onboarding@resend.dev` is test-only for real-recipient delivery restrictions. Real user email delivery is blocked until a RealtorNet-controlled sender domain is verified and Railway `MAIL_FROM` is updated.
- Public `/agents` directory is now live (new Phase K endpoint)
- `/account/reviews` is live
- Public frontend hooks should use the `authMode: omit` pattern for public API surfaces
- Browser-direct geocoding is prohibited; all Nominatim/OSM resolution must happen server-side through backend contracts.
- Mobile total blocking time target was met in Phase I I.6 for the current revised threshold; deeper <100ms RSC work is Phase K unless fresh traces reprioritize it.

## Phase K close
- Stream A (settings/infrastructure): Settings class env variables confirmed correct; test telemetry isolated from production Sentry
- Stream B (data gaps): property_count added to agency list with canonical query; agents directory endpoint `/api/v1/agents/` deployed; 12 property types migration created
- Stream C (Sentry fixes): Image validation (imghdr) added before resize; stats overview error logging improved; test RuntimeError: surprise resolved by Sentry isolation
- Stream D (canonical sources): Agency detail and stats endpoints verified using canonical queries
- Backend pyright: 0 errors after all changes
- Coverage: raised to 95.23%; `pytest.ini --cov-fail-under` set to 95.0; new test `tests/core/test_exceptions.py` covers exception handler paths
- CI fix: `.github/workflows/ci.yml` now includes all required `POSTGRES_*` job-level env vars and a `pyright` step
- E.1–E.3 queries corrected: `display_name`→`first_name`/`last_name`, `WHERE id =`→`WHERE user_id =` / `WHERE property_id =`
- Production smoke passed 12/12; new agency journey passed end to end
- `DEF-L-ADMIN-AUDIT-001`: Admin audit endpoint `GET /api/v1/admin/audit/` implemented and tested
- `DEF-L-POSTGIS-001`: Closed by clean-slate migration on new production project

## Phase R opening backlog
See `DEFERRED.md` for current deferred items.
- `DEF-J-EMAIL-DOMAIN-001` — real-user email delivery is blocked until a verified sender domain is configured in Resend and Railway `MAIL_FROM` is updated (operator action).
- `DEF-R-MSG-001` — In-app messaging + auto Mark Responded on reply. Manual Mark Responded button is correct MVP behavior until this lands.
- `DEF-R-AGENT-STATS-001` — Agent personal stats tab (own listings by status, rejected/revoked breakdown, inquiries received, response rate, agency active memberships, rejected/revoked/blocked/left membership counts).
- `DEF-Q-UNBLOCK-001` — Agency-level unblock endpoint not implemented.
- `DEF-002` — Audit log retention policy. Trigger not reached (~31 creations, ~11 deletions in 30d at Phase Q close, 5 users). Revisit when audit_logs exceeds 10K rows or user count exceeds 500.

## Root-level Phase Q closed state
- Current phase: Q closed (June 22 2026)
- Production Supabase: `fobvnshrqxduuhzgflvd`
- Production Railway: `realtornet-production.up.railway.app`
- Staging Supabase: `avkhpachzsbgmbnkfnhu`
- Staging Railway: `realtornet-staging.up.railway.app`
- Four roles live: seeker / agent / agency_owner / admin
- Moderation enum: draft / agency_review / agency_rejected / admin_review / admin_rejected / live / revoked
- Backend HEAD: `1875fed`, Frontend HEAD: `739bd1b`
- Coverage: 95.28% (pytest 2059 passed at Q close)

## Pre-flight enforcement (derived from Phase R R.2 corrective)
- **Before any backend code is written**, the agent MUST output a pre-flight confirmation block listing at least 5 locked rules from PREFLIGHT.md. This forces explicit reading, not passive attachment.
- **No bare `id` in protected_fields**: All PK column names in `protected_fields` sets must be domain-qualified (`inquiry_id`, `reply_id`, `property_id`). Bare `id` violates PREFLIGHT.md Canonical Rule 2 and is a latent bug.
- **PREFLIGHT.md is law, not reference**: The agent must read PREFLIGHT.md independently before writing code. Attaching it is not sufficient — the pre-flight declaration above proves it was read.

## Review priorities
1. DB to ORM alignment
2. Migration safety
3. Enum/value correctness
4. Auth/token consistency
5. Test coverage for changed behavior
6. RLS/security implications
7. Minimal, maintainable diffs

## Next session handover
- Phase G through Phase O are closed; do not reopen unless investigating a regression
- Phase P is closed
- Phase Q is closed — June 22 2026
- Backend quality gates are now enforced at 95%: pyright 0 errors, pytest ≥ 95.0% coverage, CI passes with all required env vars
- Production SQL verification (E.1–E.3) has been corrected and executed against new project fobvnshrqxduuhzgflvd
- Keep production vs dev Supabase separation strict during all investigations
- Treat agency card branding as blocked on backend enrichment, not frontend fetch fan-out
- Use the backlog above as the opening queue for planning and execution
- All 12 N.9 integration journeys confirmed passing end to end
- Migration `f0a1b2c3d4e5` adds Phase M enum values and listing_events table (RLS enabled)
- Migration `a1b2c3d4e5f6` adds Phase N listing_instructions table with `triggered_by_event_id` FK (RLS enabled)
- Migration `b1c2d3e4f5a6` adds notifications table (RLS enabled) — Phase O
- Migration `c2d3e4f5a6b7` adds cancelled to agency_join_requests_status_check — Phase O
- **ModerationStatus serialization**: `str(ModerationStatus.live)` produces `"ModerationStatus.live"` — always use `.value` for clean enum-to-string conversion. This applies to any `(str, Enum)` pattern used as dict keys in API responses.

## Phase Q close summary
- Q.1 backend (notification email fire points) — all three fire points already wired and tested at HEAD `2aeddc2`. `DEF-N-NOTIFICATIONS-001` closed.
  - `draft → agency_review`: `send_submission_notification_email` fires to agency owner
  - `agency_review → admin_review`: `send_agency_approval_notification_email` fires to admin(s)
  - `agency_review → agency_rejected`: `send_property_moderation_email` fires to listing agent
- Q.1 operator action remaining: `DEF-J-EMAIL-DOMAIN-001` — Resend domain verification + Railway `MAIL_FROM` update
- Q.2 backend — three agency owner read endpoints implemented at commit `ac5546b`:
  - `GET /agency-queue/` — `agency_review` listings for agency_owner's agency
  - `GET /agency-inventory/` — `live` listings for agent/agency_owner's agency
  - `GET /pending-admin/` — `admin_review` listings for agency_owner's agency
  - `DEF-N-ENDPOINTS-001` closed
- Q.2 frontend — Agency Queue, Pending Admin, Agency Inventory sections added to `/account/agency` dashboard. 3 new hooks. Approve/Reject dialogs with reason. Recall CTA. Badge count on queue header.
- Q.3 frontend — Reject Permanently dialog wired in `AdminPropertiesClient.tsx` via `useRejectPermanent` hook on Revoked tab listings. `DEF-N-TRANSITIONS-001` closed
- Q.4 backend — `PATCH /block/` existed at HEAD; join request guard updated to return 403 for blocked users. `DEF-P-BLOCK-001` closed (backend)
- Q.4 frontend — Blocked tab added to agency owner members page. Blocked membership sub-tab in `/account/join-requests`. Agency profile header shows "You cannot apply" when user has blocked membership.
- Q.5 backend — `PATCH /reconsider/` endpoint added for rejected join requests. `DEF-P-RECONSIDER-001` closed
- Q.5 frontend — `useReconsiderJoinRequest` hook created. Reconsider button on each rejected join request card.
- Q.6 frontend — Audit Activity UI section already existed at HEAD `b04601d`. `DEF-L-ADMIN-AUDIT-001` closed
- Q.7 backend — operational hardening assessment:
  - `DEF-002` — deferred to Phase R (trigger unmet, ~31 creations, ~11 deletions in 30d, 5 users)
  - `DEF-006` — closed (bucket bootstrap working, tested)
  - `DEF-007` — closed (`prepare_threshold=None` already set)
  - `DEF-K-AUDIT-FK-001` — closed (FK design correct, cleanup scripts exist)
- Q.7 frontend — `DEF-FE-004A` closed (`core-js` not in dependency tree; Next.js internal only)
- Post-close fixes (June 22 2026): admin analytics listing breakdown `by_status` now groups by `moderation_status` (not `listing_status`) with `.value` serialization; Revoked tab cards are read-only (no form on restored listings); agent Agency Inventory uses dedicated `GET /agency-inventory/` endpoint; Public Marketplace uses `GET /properties/?moderation_status=live` platform-wide; DEFERRED.md updated with Phase R deferred items
