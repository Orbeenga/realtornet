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
- Phase K closed May 2026; Phase L is active
- Backend v0.5.3+ at commit `c34bca9`
- Backend G.7 exit sweep passed: pyright 0 errors; pytest passed with 92.99% coverage; production smoke 12/12; new agency journey passed end to end
- Frontend G.7 closed in commit `d74806f`: tsc 0 errors, production build clean, Lighthouse mobile LCP 1.5s, accessibility 1.00, production routes 200
- Backend Phase H B1/B2/B3 completed in May 2026: membership alias clarified, `property_type_id` property filter live, storage service tests raised, endpoint maps documented, agency-owner profile edit live, public agent directory filters live, location hierarchy documented, and saved-search owner detail/update confirmed
- Phase H close gate: Resend email delivery confirmed, production smoke passed, backend pyright 0 errors, pytest 1856 passed, total coverage 94.54%
- Backend Phase I I.2 completed May 6 2026: saved-search match emails fire on first transition to `verified`, `saved_searches.unsubscribe_token` is live, and public unsubscribe is available at `GET /api/v1/saved-searches/unsubscribe/{token}/`
- Backend Phase I I.3 completed May 6 2026: membership audit table and `users.role_version` are live in production at migration `d3e7c5a1b9f2`; backend pyright 0 errors; pytest 1866 passed; total coverage 94.15%
- Backend Phase I I.5 completed May 6 2026: generic agency review requests are live in production at migration `f4a8c2d9e5b1`; `review_requests` has RLS enabled, duplicate pending user+agency requests are blocked, accept/decline endpoints are available for agency-owner/admin review queues, pyright 0 errors, pytest passed with 93.97% coverage.
- Backend Phase J location work completed May 2026: property create/update accepts `location_name`, resolves it server-side through Nominatim, stores dynamic locations through `location_crud.get_or_create()`, and exposes `GET /api/v1/locations/search?q=&limit=`.
- Backend Phase J closeout items completed May 8 2026: `DEF-I-MEM-SMOKE-001` multi-agency revocation smoke passed in production, `DEF-I-COV-001` coverage was raised to 95.03%, pyright stayed at 0, and commit `7e8fd35` was pushed.

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

## Phase L opening backlog
- `DEF-J-EMAIL-DOMAIN-001` - real-user email delivery is blocked until a RealtorNet-controlled sender domain is verified in Resend and Railway `MAIL_FROM` is updated.
- Phase L work queue: audit activity UI frontend, clean-slate DB propagation, Railway env cut-over to new project.
- `DEF-002` - audit log retention decision after enough production volume exists.
- `DEF-007` - psycopg3 dev restart investigation.
- `DEF-FE-004A` - residual third-party `core-js` dependency audit.
- Custom frontend/backend domain setup.

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
- Phase K is closed; Phase L is active
- Backend quality gates are now enforced at 95%: pyright 0 errors, pytest ≥ 95.0% coverage, CI passes with all required env vars
- Production SQL verification (E.1–E.3) has been corrected and executed against new project fobvnshrqxduuhzgflvd
- Keep production vs dev Supabase separation strict during all investigations
- Treat agency card branding as blocked on backend enrichment, not frontend fetch fan-out
- Use the backlog above as the opening queue for planning and execution
