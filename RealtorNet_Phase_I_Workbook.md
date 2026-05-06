# RealtorNet Phase I Workbook

Communications Completion, Membership Intelligence, and Mobile Performance

Authoritative preflight and execution reference.

## Current Baseline

| Item | Value |
| --- | --- |
| Phase H closed | May 2026; all exit criteria met, `DEFERRED.md` updated, `CLAUDE.md` committed to both repos |
| Backend version | v0.5.3+; 1856 tests, 94.54% coverage, 0 Pyright errors |
| Frontend version | Next.js 16.2.1; deployed to Vercel, Lighthouse mobile LCP 1.5s |
| Stack locked | Next.js, TypeScript, Supabase, TanStack Query, FastAPI, Resend email |
| Deploy targets | Vercel frontend, Railway backend, Supabase DB/Auth |
| Production Supabase | `avkhpachzsbgmbnkfnhu`; do not mix with dev project `umhtnqxdvffpifqbdtjs` |
| Production DB head | `a6b2d9f4c801` |
| Phase I opens | May 2026 |

## 0. Phase H Exit State And Entry Conditions

Phase I converts the platform into a fully communicating, self-aware marketplace. Every user type has a complete email voice. Membership dynamics govern role state in real time. Mobile performance reaches parity with desktop.

### 0.1 Closed In Phase H

| Item | State |
| --- | --- |
| Email infrastructure: Resend wired, all six email types delivered | Closed |
| Agency inquiry aggregation: `GET /agencies/{id}/inquiries/` live | Closed |
| Moderation UI consistency: `is_verified` replaced with full enum | Closed |
| TBT reduction: desktop under 300ms target | Closed on desktop |
| UX completeness: all error and empty states handled | Closed |
| Listing filter enums: API-driven, not hardcoded | Closed |
| `storage_services.py`: 89% coverage, target >= 80% | Closed |
| DEF-007 psycopg3: `prepare_threshold=None` validated | Closed |
| `ENV=production` confirmed on Railway | Closed |
| Landing page redirect fix: route-agnostic `AuthContext` guard removed | Closed |
| Backend contract sweep B1-B3: `property_type_id`, agent directory, agency edit | Closed |
| Frontend endpoint wiring F1-F3: `/agents`, reviews, favorites, analytics, N+1 removed | Closed |

### 0.2 Phase I Opening Backlog

| ID | Item | Priority | Owner |
| --- | --- | --- | --- |
| DEF-I-EMAIL-001 | Inquiry received -> agent email notification; agents miss leads without this | High | Backend |
| DEF-I-EMAIL-002 | Property moderation outcome -> agent email for verified/rejected/revoked | High | Backend |
| DEF-I-EMAIL-003 | Role change -> email affected user for promote/demote/deactivate | High | Backend |
| DEF-I-MEM-001 | Membership-driven role resolution; auto-demotion on last membership revoked | High | Backend + Frontend |
| DEF-I-MEM-002 | Membership audit trail; omniscient history for all user-agency relationships | High | Backend |
| DEF-I-MEM-003 | Contextual post-revocation dashboard; seeker landing with history-aware CTAs | High | Frontend |
| DEF-I-MEM-004 | Agency page CTA intelligence; Apply vs Request to Rejoin vs Pending | High | Frontend |
| DEF-H4-MOBILE-TBT | Mobile TBT: `/properties` 2966ms, `/agencies` 2033ms, `/agents` 3968ms | Medium | Frontend |
| DEF-I-LOC-001 | Location hierarchy; flat Lagos seeded list only, no cascading UI possible | Medium | Backend + Frontend |
| DEF-H-SMOKE | Smoke runner auto-teardown; cleanup step not yet added to phase_g7 script | Medium | Backend |
| DEF-I-SEARCH-001 | Saved search notifications; email infra now live, scheduler can be wired | Medium | Backend + Frontend |
| DEF-G-POLYFILL-001 | Residual core-js from third-party deps; `polyfills-*.js` at about 112 KB | Low | Frontend |
| DEF-002 | Audit log retention policy; 60-day traffic check, implement age-based job | Low | Backend |
| DEF-H-DOMAIN | Custom domain setup; operational task | Low | Ops |
| DEF-H-MAP-001 | Advanced map view with Mapbox; Leaflet/OSM in place for MVP | Low | Frontend |

## 1. Governing Principle

Phase I makes the platform self-aware and communicating. Users receive email for every significant event. Membership dynamics govern role state in real time: the system knows every user's full history and acts on it. Mobile performance closes the gap with desktop.

## 2. Membership Resolution Model

This model is the architectural centerpiece of Phase I. It must be read and fully understood before any I.3-I.5 implementation begins. It governs backend schema, role resolution logic, JWT invalidation, and all contextual frontend surfaces.

### 2.1 Core Principle

A user's effective role is not a static field on the `users` table. It is the computed intersection of their `user_role` enum value and their current active membership state. The system must know this at all times and act on it immediately when membership state changes.

### 2.2 Five Membership Rules

#### Rule 1: Single Active Membership, Revoked

Agent has exactly one active membership. That membership is revoked. The system atomically:

1. Counts active memberships for the user.
2. Finds zero active memberships.
3. Updates `user_role` to `seeker`.
4. Increments `role_version` on the user record to invalidate the current JWT.
5. Writes a `revoked` record to `agent_membership_audit` with `actor_id` and `reason`.

On the agent's next request, JWT middleware detects the `role_version` mismatch and forces re-authentication or refresh. The user lands on a contextual post-revocation dashboard, not a blank seeker home.

The dashboard message should say:

> Your membership with [Agency Name] has been revoked. You are currently browsing as a seeker.

Required CTAs:

| CTA | Behavior |
| --- | --- |
| Browse agencies to join | Links to `/agencies`; previous agency is pre-filtered out or flagged as previously joined |
| Request review | Sends a review request/message to the revoking agency |

#### Rule 2: Multiple Active Memberships, One Revoked

Agent has memberships with Agency A and Agency B. Agency A revokes membership. The system does not demote the user role. The user remains an agent.

What changes:

| Area | Behavior |
| --- | --- |
| Membership record | Agency A membership is marked revoked/inactive and audit is written |
| Listings under Agency A | Suspended or re-attributed according to product policy |
| Agency A context | User sees: "Your membership with Agency A has ended." with Request Review / Apply to Rejoin |
| Agency B context | Fully unaffected |

#### Rule 3: New User, No Membership History

When a seeker visits an agency page or applies to join an agency for the first time, the system checks `agent_membership_audit`. If no history exists for this user and agency, the UI renders a clean Apply to Join flow with no pre-filled historical context.

This is the only blank-slate membership scenario.

#### Rule 4: Returning Applicant, Prior Membership Exists

A user who was previously a member of an agency returns to that agency page. The system checks audit history and finds prior membership.

The CTA changes from Apply to Join to Request to Rejoin.

The request carries prior membership context to the agency owner's review queue:

| Context | Why It Matters |
| --- | --- |
| Prior tenure dates | Owner sees this is a returning applicant |
| Departure type | Owner can distinguish voluntary departure from revocation |
| Original revocation reason | Owner has the prior enforcement context |

First-time applicants and returning applicants must never be conflated.

#### Rule 5: Voluntary Departure vs Revocation

The audit trail distinguishes `left` from `revoked`.

| Action | Meaning | Review Queue Presentation |
| --- | --- | --- |
| `left` | Voluntary departure | Former member in good standing, simpler re-application |
| `revoked` | Enforced removal | Original revocation reason surfaced prominently |

The platform treats these as meaningfully different histories and never collapses them.

### 2.3 Agent Membership Audit Table

The required memory layer is an append-only audit table, either as a new `agent_membership_audit` table or an equivalent full-history extension of `agency_agent_memberships`.

Preferred table:

| Column | Type | Purpose |
| --- | --- | --- |
| `id` | `BIGSERIAL PRIMARY KEY` | Row identifier |
| `user_id` | FK -> `users.user_id` | Agent whose membership changed |
| `agency_id` | FK -> `agencies.agency_id` | Agency the event concerns |
| `action` | Enum or checked text | `invited`, `joined`, `suspended`, `revoked`, `left`, `reinstated` |
| `actor_id` | FK -> `users.user_id`, nullable | Admin or agency owner who performed the action |
| `reason` | `TEXT`, nullable | Required for revoked/suspended, optional otherwise |
| `prior_role` | `user_role_enum`, nullable | Role before event |
| `post_role` | `user_role_enum`, nullable | Role after event |
| `created_at` | `TIMESTAMPTZ DEFAULT now()` | Immutable event timestamp |

Required invariants:

- Append-only: no updates, no deletes.
- Every membership state change writes one audit record.
- Revocation and role demotion happen in the same transaction.
- Audit rows are the source for contextual frontend state.

### 2.4 JWT Invalidation Strategy

Supabase does not support server-side JWT blacklisting natively. The correct pattern for this stack is role-version invalidation.

| Step | Implementation |
| --- | --- |
| Add `role_version` column | `ALTER TABLE users ADD COLUMN role_version INTEGER NOT NULL DEFAULT 1` |
| Include in JWT claims | `role_version` is included in Supabase custom JWT claims alongside `user_role` |
| Verify in middleware | JWT middleware compares token `role_version` claim against DB value on authenticated requests |
| Increment on demotion | Atomically increment `role_version` when `user_role` is downgraded |
| Frontend on 401 | Silent refresh runs; new token carries updated role/version; seeker routes to contextual dashboard |

Supabase-specific note: authorization data must live in trusted app metadata or the application database, not user-editable metadata.

### 2.5 Contextual Dashboard States

| User State | Dashboard Landing | Available CTAs |
| --- | --- | --- |
| Active agent, all memberships intact | Normal agent dashboard: My Listings, Inquiries, Agency | Standard agent actions |
| Agent, one of many memberships revoked | Normal agent dashboard; revoked agency flagged in membership list | Request Review, Apply to Rejoin for that agency, Dismiss |
| Agent demoted to seeker after last membership revoked | Contextual seeker landing naming the revoked agency and current seeker state | Browse Agencies, Request Review, Apply to Join a New Agency |
| Seeker, no membership history | Standard seeker dashboard | Browse Agencies, Apply to Join |
| Seeker, prior voluntary departure | Standard seeker dashboard; agency history visible in profile | Request to Rejoin prior agencies |

### 2.6 Repo-Aware Implementation Notes

This repo already contains partial membership infrastructure. Treat these as existing anchors, not as final Phase I completion:

| Current Anchor | Path |
| --- | --- |
| Membership visibility endpoints | `app/api/endpoints/agency_memberships.py` |
| Agency membership management endpoints | `app/api/endpoints/agencies.py` |
| Membership, review request, invitation models | `app/models/agency_join_requests.py` |
| Agency membership schemas | `app/schemas/agencies.py` |
| Prior membership migrations | `app/db/migrations/versions/20260426_0900-2b61d5a8c9f0_add_agency_join_requests.py`, `app/db/migrations/versions/20260427_0100-a1c9e7d4b832_extend_agency_memberships_audit.py`, `app/db/migrations/versions/20260429_0900-b84c3e9a7d21_add_agency_membership_management.py` |
| Existing tests around revoke/demote/multi-agency behavior | `tests/api/endpoints/test_agencies.py` |

Important current-route note: the backend currently exposes membership actions by `membership_id` under routes like:

```text
PATCH /api/v1/agencies/{agency_id}/agents/{membership_id}/revoke/
POST  /api/v1/agencies/{agency_id}/agents/{membership_id}/review-request/
```

The workbook mentions `/agencies/{id}/members/{user_id}/revoke/` as the contract shape. During implementation, either add a compatibility route or explicitly standardize on the existing `membership_id` route while preserving the behavior required by this contract.

## 3. Phase I Structure

| Stream | Focus | Phases | Owner | Blocks? |
| --- | --- | --- | --- | --- |
| Stream A | Communications completion | I.1-I.2 | Backend | Yes |
| Stream B | Membership intelligence and role resolution | I.3-I.5 | Backend + Frontend | Yes |
| Stream C | Mobile performance | I.6 | Frontend | No, but required before scaling |
| Stream D | Operational and deferred items | I.7 | Both | No, runs throughout |

Stream B depends on Stream A backend stability. I.1 must close before I.3 begins. Streams C and D can run in parallel once I.1 is closed.

## 4. Phase I Work Plan

### I.1 Inquiry And Moderation Email Notifications

Goal: agents receive email when a lead arrives. Agents are notified of every moderation outcome. Affected users are notified of every role change.

| Task | Notes |
| --- | --- |
| Add `inquiry_received_email` task on `POST /api/v1/inquiries/` | To listing agent. Subject: New inquiry on `[Property Title]`. Body includes seeker name, contact details, message, and link to `/account/inquiries`. |
| Add `property_verified_email` task | Fires when `moderation_status` becomes `verified`. Includes public property link. |
| Add `property_rejected_email` task | Fires when `moderation_status` becomes `rejected`. Includes required moderation reason and next steps. |
| Add `property_revoked_email` task | Fires when `moderation_status` becomes `revoked`. Includes reason and appeal path. |
| Add `role_change_email` task | Fires on admin role changes. Includes prior role, new role, and platform context. |
| Wire all tasks to endpoint events | Follow existing Resend task pattern. Do not invent new infrastructure. |
| Raise coverage for email tasks to >= 80% | Mock Resend client. Verify recipient, subject, body interpolation, and fail-open behavior. |

Done when:

- All five email types deliver in staging.
- Resend dashboard confirms delivery.
- Inquiry submitted -> agent receives email within 60 seconds.
- Moderation outcome -> agent receives email.
- Role change -> user receives email.
- Email failures never block the primary endpoint action.

### I.2 Saved Search Notifications

Goal: seekers with saved searches receive email when matching listings are published.

| Task | Notes |
| --- | --- |
| Audit saved searches table | Confirm criteria schema: price range, bedrooms, location, property type. |
| Add match-detection logic | Runs when property status changes to `verified`; batch query saved searches, no per-seeker queries. |
| Add `saved_search_match_email` task | Includes property thumbnail if available, title, price, link, and unsubscribe link. |
| Respect notification frequency preference | If absent, default to immediate and log a DEF for preference UI. |
| Add `unsubscribe_token` to saved searches | UUID token for one-click unsubscribe without login. |
| Add public unsubscribe endpoint | `GET /api/v1/saved-searches/unsubscribe/{token}/` sets `is_active = false`. |

Done when:

- Matching verified listing sends seeker email.
- Unsubscribe link works without login.
- Match detection avoids N+1 queries.

### I.3 Membership Audit Table And Backend Role Resolution

Goal: the database has a complete immutable audit trail of every user-agency relationship. The backend atomically resolves role changes when membership state changes.

| Task | Notes |
| --- | --- |
| Create `agent_membership_audit` | Columns: `id`, `user_id`, `agency_id`, `action`, `actor_id`, `reason`, `prior_role`, `post_role`, `created_at`. Append-only. |
| Add `users.role_version` | `INTEGER NOT NULL DEFAULT 1`; used for JWT invalidation on role demotion. |
| Update Supabase JWT custom claims | Include `role_version` alongside `user_role`. |
| Update JWT middleware | Compare token `role_version` to DB value on authenticated requests; mismatch returns 401. |
| Update revocation endpoint | After revocation: count active memberships; if zero, set `user_role = seeker` and increment `role_version`; write audit record. All in one transaction. |
| Update all membership state changes | `invited`, `joined`, `suspended`, `left`, `reinstated` each writes audit. |
| Add `GET /api/v1/users/me/membership-history/` | Returns authenticated user's full audit history across agencies. |
| Add agency member history endpoint | `GET /api/v1/agencies/{id}/member-history/{user_id}/`; agency owner of that agency and admin only. |
| Backfill existing memberships | Insert `joined` audit rows for existing active memberships with original membership `created_at`; `actor_id = NULL`. |
| Keep gates green | Pyright 0 errors and pytest passing after each meaningful change. |

Done when:

- `agent_membership_audit` exists and is written on every membership event.
- `role_version` is in JWT claims and verified by middleware.
- Revoking an agent's last membership demotes them to seeker and invalidates token freshness atomically.
- User membership-history endpoint returns complete history.
- Backfill is confirmed by SQL query.

### I.4 Contextual Post-Revocation Frontend

Goal: the frontend surfaces correct contextual state based on full membership history. No user sees a generic blank state when their situation has history.

| Task | Notes |
| --- | --- |
| Add `useMembershipHistory()` hook | Calls `GET /api/v1/users/me/membership-history/`; cached via TanStack Query. |
| Build `PostRevocationDashboard` | Renders when user role is seeker and history contains revoked record. Shows agency, reason, revocation date, Browse Agencies, Request Review. |
| Update account dashboard routing | If last session was agent and current token/user is seeker, show contextual dashboard instead of seeker home. |
| Add agency page CTA intelligence | Render Apply, Request to Rejoin, Rejoin Request Pending, or Active Member based on history and current state. |
| Add Membership History tab | Shows agency relationships, status, tenure dates, and reason if revoked. |
| Enhance agency owner review queue | Returning applicants show prior membership dates, departure type, and revocation reason. |
| Prevent CTA flash | Unauthenticated users see Apply to Join; authenticated users with history see contextual CTA after auth state resolves. |

Done when:

- Demoted agent lands on `PostRevocationDashboard` with agency-specific context.
- Agency page CTAs correctly distinguish Apply, Request to Rejoin, Pending, and Active.
- Membership History tab shows complete audit.
- Agency owner review queue surfaces prior history for returning applicants.

### I.5 Multi-Agency Agent Revocation And Review Flow

Goal: agents with multiple active memberships are handled correctly when one is revoked. Review and rejoin flow works end to end.

| Task | Notes |
| --- | --- |
| Add review request creation | `POST /api/v1/agencies/{id}/review-requests/`; any authenticated user can submit optional message. |
| Add review request listing | `GET /api/v1/agencies/{id}/review-requests/`; agency owner/admin only; includes requestor membership history. |
| Add accept endpoint | Accept creates/restores active membership, writes `reinstated` audit, sends role-change email if demotion is reversed. |
| Add decline endpoint | Decline updates request status and sends decline email with optional reason. |
| Add frontend Review Requests tab | Shows pending requests, applicant name, prior history, message, Accept/Decline, badge count. |
| Wire Request Review CTA | Submits review request for revoking agency; prevents duplicate submissions and shows pending state. |
| Test multi-agency revocation | Agency A revoke leaves Agency B intact and `user_role` remains `agent`. |

Done when:

- Multi-agency agent remains agent after one membership is revoked.
- Single-agency demoted agent can submit review request.
- Agency owner sees request with full history context.
- Accept reinstates role when applicable.
- Decline notifies user.
- Duplicate review requests are prevented.

### I.6 Mobile TBT Reduction

Goal: mobile TBT below 300ms on `/properties`, `/agencies`, and `/agents`.

Current values:

| Route | Mobile TBT |
| --- | --- |
| `/properties` | 2966ms |
| `/agencies` | 2033ms |
| `/agents` | 3968ms |

| Task | Notes |
| --- | --- |
| Run Chrome DevTools Performance traces | Identify exact long tasks before optimizing. |
| Evaluate RSC migration | Convert data-fetch-only route components to React Server Components where practical. |
| Dynamic import Zod on non-form routes | Zod is only needed on form-heavy pages; about 30 KB recoverable. |
| Dynamic import React Hook Form | About 24 KB recoverable on non-form routes. |
| Audit large `2786-...js` chunk | Run `NEXT_ANALYZE=true pnpm build`; split or lazy-load heavy modules. |
| Eliminate residual core-js | Identify third-party dependencies pulling about 112 KB polyfills. |
| Rerun Lighthouse after each change | Record before/after per route and per change. |

Done when:

- Lighthouse mobile TBT below 300ms on all three routes.
- Before/after scores recorded.
- Bundle analyzer shows no unexpected large modules on critical path.
- Any target that requires full RSC migration is documented and promoted to Phase J.

### I.7 Operational And Deferred Items

Goal: close operational items carried from Phase H. Runs in parallel with all streams.

| Task | Notes |
| --- | --- |
| Smoke runner auto-teardown | Add cleanup to `scripts/phase_g7_production_smoke.py` so smoke-created records are soft-deleted automatically. |
| Audit log retention decision | Assess volume. If material, implement age-based soft-delete job. If low, defer with evidence. |
| Location hierarchy assessment | Decide whether flat Lagos list is sufficient or Nominatim design should begin. |
| Custom domain setup | Configure Vercel/Railway domains, CORS, and `NEXT_PUBLIC_API_URL`; document in `CLAUDE.md`. |
| Update `CLAUDE.md` files | Root, frontend, backend reflect Phase I in-progress state and new routes. |

Done when:

- Smoke runner teardown is automatic.
- Audit retention decision is documented with evidence.
- Location hierarchy assessment is complete.
- Custom domain is live if pursued.
- `CLAUDE.md` files are current.

## 5. Phase I Exit Criteria

Phase I is closed when every item below is true. Phase J does not open until this list is complete.

| Exit Criterion | Verification | Stream |
| --- | --- | --- |
| Inquiry received -> agent email delivered within 60 seconds | Submit inquiry and check agent inbox | A |
| Property moderation outcome -> agent email for all relevant states | Admin sets verified/rejected/revoked and agent receives each email | A |
| Role change -> email to affected user | Admin promotes/demotes/deactivates and user receives email | A |
| Saved search match -> seeker email on new verified listing | Create matching listing, verify it, check seeker inbox | A |
| Unsubscribe link works without login | Click unsubscribe token URL and confirm saved search deactivated | A |
| `agent_membership_audit` records all membership events | SQL confirms rows for invited/joined/revoked/left after test flows | B |
| `role_version` in JWT claims and verified by middleware | Increment `role_version`; old JWT returns 401 | B |
| Last-membership revocation atomically demotes role to seeker | Revoke final membership; role changes, version increments, audit writes in one transaction | B |
| Multi-agency revocation does not demote agent | Agent with two memberships loses one and remains agent | B |
| `PostRevocationDashboard` renders with agency-specific context | Demoted agent logs in and sees agency name, reason, and correct CTAs | B |
| Agency page CTAs all correct | Apply, Request to Rejoin, Pending, and Active scenarios verified | B |
| Membership History tab shows complete audit | All membership events visible in `/account` history tab | B |
| Agency owner review queue surfaces prior history | Revoked agent submits rejoin request; owner sees prior context | B |
| Review request accept/decline works end to end | Accept reinstates; decline notifies | B |
| Mobile TBT < 300ms on `/properties`, `/agencies`, `/agents` | Lighthouse mobile scores recorded | C |
| Smoke runner auto-teardown confirmed | Smoke script leaves no manual cleanup | D |
| `tsc --noEmit` -> 0 errors | `pnpm tsc --noEmit` | B/C |
| Pyright -> 0 errors | venv Pyright | A/B |
| pytest -> all passing, coverage >= 95% | pytest coverage gate | A/B |
| `pnpm build` -> 0 warnings | Next.js production build | C |
| `DEFERRED.md` updated | All Phase I items closed or promoted to Phase J | All |
| All `CLAUDE.md` files committed | Root, frontend, backend Phase I closed state | All |

## 6. Execution Sequence

| # | Phase | Dependency | Parallel? | Stream |
| --- | --- | --- | --- | --- |
| 1 | I.1 Inquiry and moderation emails | None; start immediately | No, backend sequential with I.2 | A |
| 2 | I.2 Saved search notifications | I.1 Resend pattern stable | Yes, parallel with I.3 | A |
| 3 | I.3 Membership audit and role resolution | I.1 closed | No, I.4/I.5 depend on this | B |
| 4 | I.4 Contextual frontend | I.3 closed | Yes, parallel with I.5 | B |
| 5 | I.5 Multi-agency revocation and review | I.3 closed | Yes, parallel with I.4 | B |
| 6 | I.6 Mobile TBT reduction | I.1 closed | Yes, parallel with I.4/I.5 | C |
| 7 | I.7 Operational and deferred items | Runs throughout | Yes, parallel with all | D |
| 8 | Exit sweep | I.1-I.7 all closed | No, final gate | All |

## 7. Items Deferred To Phase J

| Item | Rationale |
| --- | --- |
| Advanced map view with Mapbox | Leaflet/OSM is sufficient for Lagos MVP. Upgrade when tile quality becomes user-reported friction. |
| Nominatim/OSM geocoding | Seeded 15-location list is sufficient for now; Phase I only assesses need. |
| Agency owner self-service onboarding | Needs abuse prevention, email verification, duplicate org detection. |
| TBT < 100ms | Phase I targets 300ms. 100ms likely needs fuller RSC migration. |
| Admin analytics cohorts and retention | Requires real traffic data. |
| Agency N+1 aggregation on public directory | Optimize after traffic data sizes the problem. |
| Notification frequency preference UI | Saved search emails default to immediate in Phase I. |
| In-app messaging / inquiry reply | Lead capture is MVP; thread model belongs in later phase. |
| Audit log retention | Implement in I.7 only if volume warrants; otherwise Phase J with evidence. |

## 8. Session Opening Template

Use this as the opening prompt for every Phase I session. Replace `[I.X]` and `[SPECIFIC TASK]`.

```text
Continuing RealtorNet Phase I from [I.X].

Phase H closed May 2026: all exit criteria met, DEFERRED.md updated,
CLAUDE.md committed to both repos.

Backend v0.5.3+ on Railway (realtornet-production.up.railway.app),
pytest 1856, coverage 94.54%, pyright 0.

Frontend Next.js 16.2.1 on Vercel (realtornet-web.vercel.app),
tsc 0, lint clean, build clean.

Production Supabase: avkhpachzsbgmbnkfnhu.
DB head: a6b2d9f4c801.

Four roles live: seeker / agent / agency_owner / admin.
Moderation enum: pending_review / verified / rejected / revoked.
Resend email live. Redis-backed rate limiting live.

Governing model: Membership-driven role resolution is the centrepiece of
Phase I. A user's effective role is computed from their current active
membership state. The system acts on membership changes immediately.
Read Section 2 of the Phase I workbook before any I.3-I.5 work begins.

Today's task: [SPECIFIC TASK FROM WORK PLAN].
Attach Phase I workbook, DEFERRED.md, and all three CLAUDE.md files.
```

## 9. Production Reference

| Service | URL / Reference |
| --- | --- |
| Frontend | `https://realtornet-web.vercel.app` |
| Backend | `https://realtornet-production.up.railway.app` |
| Supabase production | `https://avkhpachzsbgmbnkfnhu.supabase.co` |
| Supabase dev, deprecated | `umhtnqxdvffpifqbdtjs`; do not use for production diagnostics |
| Email service | Resend; confirmed live, message ID `c781de39-42d6-4a58-9ec3-4a774f8f53c3` |

### Production Accounts

| user_id | Email | Role | Agency |
| --- | --- | --- | --- |
| 5 | `apineorbeenga@gmail.com` | admin | NULL |
| 74 | `apineorbeenga@outlook.com` | agent | 1 |
| 76 | `apineorbeenga@yahoo.com` | seeker | NULL |
| 85 | `godwinemagun@gmail.com` | seeker | NULL |

## Working Rule For Future Sessions

When implementing Phase I, this markdown file is the local contract. The core membership interpretation is:

- Audit history is the platform memory layer.
- Active memberships determine whether an agent remains an agent.
- Last active membership revocation demotes to seeker and increments `role_version` atomically.
- Multi-agency revocation is agency-scoped, not role-global.
- Returning applicants must carry prior membership context into review.
- Post-revocation frontend state must explain what happened and offer agency-aware CTAs.

RealtorNet Phase I Workbook v1.0, converted to markdown from the Phase I DOCX and extended with repo-aware implementation notes.
