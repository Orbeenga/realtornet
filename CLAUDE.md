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
- Phase I closed May 2026
- Phase J closed May 2026; only `DEF-J-EMAIL-DOMAIN-001` (verified sender domain + Railway `MAIL_FROM`) remains open
- Phase K closed May 2026
- Phase L closed May 2026: clean-slate DB propagation on new Supabase project `fobvnshrqxduuhzgflvd`, staging environment live at `realtornet-staging.up.railway.app`, admin audit endpoint live, modals/tabs/detail frontend complete
- Phase M closed June 2026: listing governance system complete, state machine live (draft → agency_review → agency_rejected → admin_review → admin_rejected → live → revoked)
- Phase N closed June 2026: listing instruction mediation system complete, `listing_instructions` table with `triggered_by_event_id` FK gating, reject-permanent transition (`revoked → admin_rejected`), mediated governance read endpoints (revocation-history, rejection-history, agency-queue, inventory, pending-admin), email notification wiring for instruction, frontend mediation CTAs and admin historical views
- Backend HEAD: `cb66f2c`
- Frontend HEAD: `5c2975b`
- Backend Phase N: N.1 `listing_instructions` table with `triggered_by_event_id` FK (RLS enabled); N.2 mediated governance read endpoints (revocation-history, rejection-history, agency-queue, inventory, pending-admin); N.3 reject-permanent transition (`revoked → admin_rejected`); N.4 email notification wiring for instruction; N.5-N.7 frontend mediation CTAs, admin historical views, instruct-agent hooks
- Coverage: 96.07%; `.coveragerc` legitimately omits: `env.py`, `main.py`, `config.py`, `celery_worker.py`
- `owner_display_name` added to `PropertyResponse` (DEF-N-PROP-001 closed)
- `listing_events` table append-only, RLS enabled
- `listing_instructions` table append-only with `triggered_by_event_id` FK to listing_events, RLS enabled
- `has_instruction`, `instruction_text`, `latest_event_reason` fields on PropertyResponse for mediation context
- Final Phase N housekeeping deployed 2026-06-15: agency_owner visibility for non-public listings, edit-transition revoked→draft after instruction, N.9 walkthrough all 12 steps passed on staging, production deployment verified

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

## Phase N opening backlog
See `DEFERRED.md` for current deferred items.
- `DEF-J-EMAIL-DOMAIN-001` - real-user email delivery is blocked until a RealtorNet-controlled sender domain is verified in Resend and Railway `MAIL_FROM` is updated.
- `DEF-002` - audit log retention decision after enough production volume exists.
- `DEF-007` - psycopg3 dev restart investigation.
- `DEF-FE-004A` - residual third-party `core-js` dependency audit.
- Custom frontend/backend domain setup.
- Frontend agency-queue/inventory/pending-admin dashboards — user-facing dashboard views for ownership status tabs

## Root-level Phase N closed state
- Current phase: N closed
- Production Supabase: `fobvnshrqxduuhzgflvd`
- Production Railway: `realtornet-production.up.railway.app`
- Staging Supabase: `avkhpachzsbgmbnkfnhu`
- Staging Railway: `realtornet-staging.up.railway.app`
- Four roles live: seeker / agent / agency_owner / admin
- Moderation enum: draft / agency_review / agency_rejected / admin_review / admin_rejected / live / revoked
- Backend HEAD: `cb66f2c`, Frontend HEAD: `5c2975b`

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
- Phase I is closed; do not reopen Phase I unless investigating a regression from the closed state
- Phase J is closed except `DEF-J-EMAIL-DOMAIN-001`; do not reopen Phase J scope unless investigating a regression
- Phase K is closed
- Phase L is closed
- Phase M is closed; use the opening backlog above for any Phase N planning
- Phase N is closed; use the opening backlog above for future planning
- Backend quality gates are now enforced at 95%: pyright 0 errors, pytest ≥ 95.0% coverage, CI passes with all required env vars
- Production SQL verification (E.1–E.3) has been corrected and executed against new project fobvnshrqxduuhzgflvd
- Keep production vs dev Supabase separation strict during all investigations
- Treat agency card branding as blocked on backend enrichment, not frontend fetch fan-out
- Use the backlog above as the opening queue for planning and execution
- N.9 integration validation passed all 12 steps against staging: full mediation lifecycle (create → submit → agency-approve → admin-verify → revoke → blocked-edit → owner-view → instruct → edit → resubmit → admin-history → listing-events) confirmed end-to-end via API with 9 listing_events rows
- Migration `f0a1b2c3d4e5` adds Phase M enum values and listing_events table (RLS enabled)
- Migration `a1b2c3d4e5f6` adds Phase N listing_instructions table with `triggered_by_event_id` FK (RLS enabled)
