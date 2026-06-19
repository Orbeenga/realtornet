# RealtorNet — Phase O Workbook
## Notification Delivery, Governance Corrections & Membership Completeness

Authoritative Preflight & Execution Reference

| Item | Value |
|---|---|
| Phase N closed | June 17, 2026 — listing governance state machine, instruction mediation, admin historical tabs, creator/agency name resolution all live |
| Backend version | v0.5.3+ — 96.15% coverage, 0 Pyright errors, commit `88222f5` |
| Frontend version | Next.js — deployed to Vercel, commit `51deb96` |
| Stack (locked) | Next.js · TypeScript · Supabase · TanStack Query · FastAPI · Resend email |
| Deploy targets | Vercel (frontend) · Railway (backend) · Supabase (DB + Auth) |
| Production Supabase | `fobvnshrqxduuhzgflvd` |
| Staging Supabase | `avkhpachzsbgmbnkfnhu` (password rotated June 17) |
| Phase O opens | June 19, 2026 |

---

## 0. Phase N Exit State & Entry Conditions

Phase N is closed. The seven-state listing governance system, instruction mediation layer, admin historical tabs, and creator/agency name resolution utility are all live. Three classes of work carry into Phase O: one feature built locally but never deployed (notification system), two governance corrections identified post-close (unilateral Restore button and persistent instruction ambience on live listings), and membership completeness gaps identified via verification sweep.

### 0.1 Closed in Phase N

| Item | State |
|---|---|
| listing_instructions table — append-only, RLS, trigger | Closed |
| Instruction mediation: agency instructs agent post-revocation, CTA gated on triggered_by_event_id | Closed |
| Admin Revoked and Rejected tabs — historical views, CTA derived from current_moderation_status | Closed |
| resolveListingDisplayName utility with tabIsPublicContext parameter | Closed |
| Agent Revoked tab with two-state mediation card | Closed |
| has_instruction extended to agency_owner | Closed |
| latest_event_reason populated on list queries | Closed |
| N.2 endpoints enriched with owner and agency joinedload | Closed |
| Trailing slash on useInstructAgent removed | Closed |
| staleTime: 0 + refetchOnWindowFocus on listing tab queries | Closed |
| Open Item 1 — actor display name in admin history tabs | Closed (51deb96) |
| Open Item 2 — agent Revoked CTA unlock via enrich_property_with_instruction_fields | Closed (88222f5) |
| Security incident — git history scrub, staging password rotation, detect-secrets hook, SUPABASE_SECRET_KEY migration, 33 test accounts deleted, production registration guard | Closed |

### 0.2 Phase O Opening Backlog

| ID | Item | Priority | Owner |
|---|---|---|---|
| DEF-M-NOTIF-001 | In-platform notifications — built locally, never committed or deployed | High | Backend + Frontend |
| DEF-O-GOV-001 | Admin Revoked tab: Restore button should not exist — admin never unilaterally restores | High | Frontend + Backend |
| DEF-O-GOV-002 | Instruction ambience persisting on live listings — must suppress when status = live | High | Frontend |
| DEF-O-JOIN-001 | Seeker join request tracker: nav link missing, no cancel-pending, no resubmit-after-rejection | Medium | Frontend |
| DEF-O-MEM-001 | Agent membership tracker: listing_count missing from MyAgencyMembershipResponse and AgencyAgentRosterResponse | Medium | Backend + Frontend |
| DEF-O-MEM-002 | GET /agents/ uses users.agency_id not agency_agent_memberships — multi-tenancy misrepresentation | Medium | Backend |
| DEF-O-AGENCY-001 | Agency owner stats and roster governance — verify current state, close gaps | Medium | Backend + Frontend |
| DEF-J-EMAIL-DOMAIN-001 | MAIL_FROM domain verification — operator action, no code changes | High | Operator |

---

## 1. Governing Principle

Phase O makes the platform self-reporting and structurally honest. Notifications reach users in-platform. Governance corrections close two design violations introduced in Phase N. Membership representations match the multi-tenancy reality: `agency_agent_memberships` is the sole source of truth for agent-agency relationships. The agency owner has full visibility of their operational context.

---

## 2. The Agency Authority Model — Locked Invariants

Two structural invariants must be understood before any O.4, O.5, or O.6 work begins. They govern which fields are authoritative for which role.

### 2.1 users.agency_id — Ownership, Not Membership

`users.agency_id` is **only** semantically correct for the `agency_owner` role. It means: the agency this person owns and operates. An agency_owner owns exactly one agency. This is an ownership relation, not a membership.

`users.agency_id` is **not** authoritative for the `agent` role. It is a legacy field from before multi-tenancy was implemented. It may reflect the first agency an agent joined and has not been updated as memberships changed. Any query that resolves an agent's current agency via `users.agency_id` is reading a field that can be stale.

### 2.2 agency_agent_memberships — Agent Affiliation Truth

For agents, current agency affiliation is exclusively determined by:

```sql
SELECT agency_id FROM agency_agent_memberships
WHERE user_id = :agent_id
AND status = 'active'
AND deleted_at IS NULL
```

This supports multi-tenancy: one agent may have multiple active memberships simultaneously, each with a unique membership ID.

**The locked invariant (committed to PREFLIGHT.md at Phase O close):**
- `agency_owner` role: `users.agency_id` = the agency they own. Valid. Used only for agency_owner context.
- `agent` role: `agency_agent_memberships` is the sole source of truth. `users.agency_id` is not read for agent context anywhere in Phase O or later.
- Callers that still use `users.agency_id` for agent context are bugs and must be fixed in O.4.

---

## 3. Phase O Work Plan — End to End

Seven sequential phases. Each has a goal, task list, and done-when criterion.

### O.0 — Commit, Push, and Validate Notification System

**Goal:** The notification system built locally during Phase N housekeeping is committed, pushed to both repos, migrated to staging, and validated against the done-when criteria from the original spec.

**Context:** Backend HEAD `88222f5` and frontend HEAD `51deb96`. Notification work is local only. No files are in git. No migration has run on staging.

**Backend tasks:**

Commit all local notification files:
- `app/models/notifications.py`
- `app/db/migrations/versions/20260618_1000-....py`
- `app/schemas/notifications.py`
- `app/crud/notifications.py`
- `app/api/endpoints/notifications.py`
- Changes to `app/api/api.py` (router registration)
- Changes to `app/api/endpoints/properties.py` (7 notification write points)
- Changes to `app/db/migrations/env.py` (Notification import)
- Changes to `tests/conftest.py` (Notification import)

Before committing: run `pyright` — confirm 0 new errors introduced by notification files. Run `pytest` — confirm all passing, coverage ≥ 95%. If either fails, fix before commit.

Push to both `main` and `staging` on the `realtornet` repo. Apply migration on Railway staging: `alembic upgrade head`. Confirm `notifications` table exists in staging Supabase.

**Frontend tasks:**

Commit all local notification frontend files:
- `src/features/notifications/hooks/useNotifications.ts`
- `src/features/notifications/components/NotificationBell.tsx`
- Changes to `src/components/Navbar.tsx`

Before committing: run `pnpm tsc --noEmit` → 0 errors, `pnpm lint` → 0 warnings, `pnpm build` → 0 warnings. Fix any failures before commit.

Push to both `main` and `staging` on `realtornet-web`. Confirm Vercel staging deployment is green.

**Validation (done-when gate — run after both deploys are confirmed healthy):**

Log in as agent. Submit a listing for review. Agency owner should see a notification badge increment within 60 seconds (poll interval). Open bell — verify notification appears with body text and link. Click notification — confirm marks read, badge decrements. Agency owner approves listing — admin receives notification. Admin approves — agent receives "Your listing is now live" notification. Mark all read — badge clears.

**Done-when:** All 7 notification event types (submit, agency_approve, agency_reject, admin_approve, admin_reject, revoke, instruct) produce notifications for the correct recipients. Badge polls every 60 seconds. Mark-read and mark-all-read work. pyright 0, pytest ≥ 95%, tsc 0, lint 0, build 0.

---

### O.1 — Admin Revoked Tab: Remove Unilateral Restore

**Goal:** Admin can never unilaterally restore a revoked listing. The `PATCH /restore/` (revoked → live) path is removed from the governance flow. The admin Revoked tab is corrected to show no action CTA at any point. The listing's path back to `live` is always: agency instructs → agent edits → draft → agency_review → admin_review → admin approves via normal `/verify/` → live.

**Why this is wrong by design:** The Phase N workbook's CTA derivation map included "Restore" as a valid admin action when `status = revoked && !has_instruction`. This was a design error. The governance model requires the agency to own the communication channel back to the agent after any enforcement action. Admin bypassing this collapses the three-tier accountability structure.

**Backend tasks:**

Deprecate `PATCH /api/v1/properties/{id}/restore/`. Do not delete the endpoint — it may be needed for future administrative emergency tooling. Instead:
- Add a comment in the router: `# Deprecated: not used in governance flow. Admin restoration goes via /verify/ after full chain restart.`
- Add a 410 Gone response or keep as-is but confirm no frontend calls it after O.1 frontend fix

If tests rely on the restore endpoint to assert the `revoked → live` transition, update those tests to use the full chain (revoke → instruct → edit → submit → agency_approve → admin_verify). Do not delete tests — rewrite them to reflect the correct flow.

pyright 0, pytest ≥ 95%.

**Frontend tasks:**

In `moderation.ts` (or wherever `getAdminRevocationCta` is defined), replace the current derivation function with the corrected map:

```ts
export const getAdminRevocationCta = (
  status: ModerationStatus,
  hasInstruction: boolean,
): { label: string; action: string | null } => {
  if (status === 'revoked' && !hasInstruction) {
    return { label: 'Awaiting agency instruction', action: null }
  }
  if (status === 'revoked' && hasInstruction) {
    return { label: 'Awaiting agent action', action: null }
  }
  if (['draft', 'agency_review', 'admin_review'].includes(status)) {
    return { label: 'In progress', action: null }
  }
  if (status === 'live') {
    return { label: 'Restored', action: null }
  }
  if (status === 'admin_rejected') {
    return { label: 'Rejected', action: null }
  }
  return { label: status, action: null }
}
```

No CTA has `action !== null`. Remove any button rendering that calls `/restore/`. The admin Revoked tab is read-only in every state.

Search `AdminPropertiesClient.tsx` and any related admin moderation components for the "Restore" button render and remove it. Confirm via grep: `grep -r "restore" src/` — no results in any admin moderation component.

tsc 0, lint 0, build 0.

**Done-when:** Admin Revoked tab shows no interactive button at any point in the listing's lifecycle. A listing at `revoked` (no instruction) shows "Awaiting agency instruction" — read-only. A listing that has gone through the full chain and returned to `live` shows "Restored" — read-only. No call to `/restore/` is ever issued from the frontend.

---

### O.2 — Suppress Instruction Ambience on Live Listings

**Goal:** When a listing has completed the restoration chain and returned to `live`, the instruction text and `has_instruction` indicators are not shown on listing cards in agent Live tab, agency Verified Inventory, agency Public Marketplace, or any public-facing surface.

**Root cause:** The instruction was written during the `revoked` / `admin_rejected` phase. After the listing returns to `live`, the `has_instruction` field from the backend still returns `true` (correctly — the instruction record exists and is immutable). But the frontend should not render it once the listing is live.

**Frontend tasks only:**

In every listing card component that renders instruction state — identify them by grep: `grep -r "has_instruction\|instruction_text" src/` — add a guard on `moderation_status`:

```ts
// Instruction display is only valid during enforcement states
const showInstruction =
  listing.has_instruction &&
  ['revoked', 'admin_rejected'].includes(listing.moderation_status)

// Do NOT render instruction box when showInstruction is false
```

This applies to:
- Agent listing cards in Revoked tab, Rejected tab (already gating correctly by being in those tabs)
- Agent listing cards in Live tab — must suppress
- Agency owner Verified Inventory cards — must suppress
- Public Marketplace cards (both agent and agency owner views) — must suppress

Additionally: when `moderation_status === 'live'` and the listing previously had an instruction, the card should show nothing related to the instruction cycle. The listing is simply live. No "restored" ambience either — that is only the admin Revoked tab's label for historical tracking. From the agent and agency owner perspective, a live listing is just live.

tsc 0, lint 0, build 0.

**Done-when:** A listing that was revoked, received an agency instruction, was edited by the agent, went through the full chain, and returned to `live` shows no instruction box, no `has_instruction` indicator, and no instruction-related copy in any listing card for any role. The listing card is identical to any other listing that went live without ever being revoked.

---

### O.3 — Seeker Join Request Tracker: Close Remaining Gaps

**Goal:** Seekers have a complete, navigable join request experience. They can reach their requests via the nav, cancel a pending request, and resubmit after a rejection without manually finding the agency page.

**Current state (confirmed):** The flow is fully implemented end to end. Three gaps remain:
1. `/account/join-requests` has no nav link in the seeker avatar dropdown
2. No cancel action on a pending join request
3. No resubmit-after-rejection CTA (user must navigate back to the agency page manually)

**Backend tasks:**

Add `DELETE /api/v1/agencies/{id}/join-requests/{request_id}/` endpoint:
- Role gate: seeker who created the request
- Accepted state: request status must be `pending` (cannot cancel after agency has acted)
- Action: sets request status to `cancelled`, writes an audit note
- Returns: 204 No Content
- pyright 0, pytest ≥ 95%

Confirm whether `GET /join-requests/mine/` returns the `agency_id` for each request. If not, add it to `MyJoinRequestResponse` — it is needed for the resubmit CTA to construct the link to the agency page.

**Frontend tasks:**

Add "Join Requests" to the seeker avatar dropdown in `navigation.ts` and the avatar dropdown component:
```
Seeker dropdown (updated):
My Favorites | Saved Searches | My Inquiries | My Reviews | Join Requests | Settings | Sign out
```
Route: `/account/join-requests`.

In `MyJoinRequestsClient.tsx`, on cards where `status === 'pending'`, add a "Cancel" CTA that calls the new delete endpoint. Confirmation dialog required before firing. On success: card updates to `cancelled` status or disappears from list.

On cards where `status === 'rejected'`, add a "Resubmit" CTA that navigates to `/agencies/{agency_id}/join` (the join request form for that specific agency). This is a navigation action — no new endpoint. The agency_id must come from the response (see backend task above).

tsc 0, lint 0, build 0.

**Done-when:** Seeker avatar dropdown contains "Join Requests" linking to `/account/join-requests`. A pending request card shows "Cancel" — clicking it prompts confirmation and cancels the request. A rejected request card shows "Resubmit" — clicking navigates to the agency's join form.

---

### O.4 — Agent Membership Tracker and Directory Correction

**Goal:** Agent membership cards show listing counts per membership. The public agents directory uses `agency_agent_memberships` as the source of truth, not `users.agency_id`. This implements the invariant from Section 2.2.

**Backend tasks:**

In `app/schemas/agencies.py`, add `listing_count: int` to `MyAgencyMembershipResponse`. The value is: count of listings where `user_id = member.user_id AND agency_id = member.agency_id AND deleted_at IS NULL AND moderation_status = 'live'`.

In `app/api/endpoints/agency_memberships.py`, add a subquery or annotation to the `GET /agency-memberships/mine/` query to populate `listing_count` for each membership row. Do not use N+1 queries — use a single aggregation subquery. Confirm with EXPLAIN ANALYZE.

In `app/schemas/agencies.py`, add `listing_count: int` to `AgencyAgentRosterResponse` (the response shape used when an agency owner views their roster). Same aggregation: listings for that agent under that agency at `live` status.

Fix `GET /api/v1/agents/` to resolve agency affiliation from `agency_agent_memberships` not `users.agency_id`:
- The endpoint currently joins or reads `users.agency_id` to populate `agency_id` and `agency_name` on the agent response
- Replace with a join or subquery against `agency_agent_memberships WHERE status = 'active'`
- For agents with multiple active memberships, use the most recently joined active membership as the display agency, or return a list — decide and document before implementing
- Simplest correct approach: return the most recent active membership's agency as the agent's primary display agency. Add a note to the response: this is the agent's primary active agency, not necessarily their only one.

pyright 0, pytest ≥ 95%.

**Frontend tasks:**

Run `pnpm gen:types` after backend changes deploy to staging. `listing_count` will appear on both response types.

In `MyJoinRequestsClient.tsx` (the Memberships tab), render `listing_count` on each membership card: "X active listings under this agency."

In the agency owner roster view (agency owner dashboard Roster tab), render `listing_count` per agent: "X active listings."

tsc 0, lint 0, build 0.

**Done-when:** Agent's Memberships tab shows each active agency membership with its listing count. Agency owner's Roster tab shows each agent's active listing count under that agency. `GET /api/v1/agents/` returns agents whose `agency_name` is resolved from their active `agency_agent_memberships`, not from `users.agency_id`. EXPLAIN ANALYZE confirms no N+1 on any of these queries.

---

### O.5 — Agency Owner Stats and Roster Governance

**Goal:** Agency owner has a complete view of their agency's operational performance. Before implementing anything, verify what currently exists on `/account/agency/`. Implement only confirmed gaps.

**Pre-implementation verification (no code — read only):**

Before any backend or frontend work begins on O.5, verify the current state of:
- `/account/agency/` page tabs and their data sources
- What stats the agency owner can already see (listing counts, agent counts, moderation states)
- Whether a dedicated agency stats endpoint exists beyond `GET /agencies/{id}/stats/`
- The roster management capabilities currently available (suspend, remove, view per-agent listing counts)

Report the current state gap list before writing any code. This is the dispatch instruction to the agent: read and report first, implement second.

**Expected gap areas based on prior phases (implement only what verification confirms is missing):**

Agency performance dashboard: a view showing for the agency owner's agency — total listings by status (draft, under review, live, revoked), total agents, agents by status (active, suspended), inquiries received across all agency listings this month, and agency listing count trend (simple: count by week for last 4 weeks). If a stats endpoint already returns some of this, extend it rather than creating a new one.

Roster governance completeness: agency owner can currently suspend and remove agents. Verify whether they can also view a per-agent breakdown (agent name, listing count, inquiry count, join date, membership status) in the roster tab. If not, add it.

Agency moderation visibility: agency owner should see their agents' listings across all states (draft is agent-only, but agency_review through live and revoked should be visible). Verify the current agency queue tabs cover this per the Phase M tab spec.

pyright 0 and pytest ≥ 95% for any backend additions. tsc 0, lint 0, build 0 for any frontend additions.

**Done-when:** Agency owner's dashboard shows accurate counts for all listing states within their agency. Roster tab shows per-agent listing and inquiry counts. All caps specified in the Phase K capability matrix are met for the agency_owner role. No "Not recorded" or zeroes where real data exists.

---

### O.6 — PREFLIGHT.md: Document Membership Invariants

**Goal:** The `users.agency_id` vs `agency_agent_memberships` resolution from Section 2 is committed to PREFLIGHT.md as a locked canonical rule. All agents reference this before any future membership-touching work.

**Tasks:**

Add to PREFLIGHT.md under Canonical Rules:

```
Agency Affiliation Authority (Locked — Phase O)
- users.agency_id is authoritative ONLY for the agency_owner role.
  It means "the agency this person owns." Never read for agent context.
- agency_agent_memberships is the sole source of truth for agent-agency
  relationships. All agent-context queries must join this table.
- An agent may have multiple simultaneous active memberships.
  Display primary agency = most recent active membership by joined_at.
- Any code that uses users.agency_id to resolve an agent's current
  agency is a bug. Fix on discovery.
```

Also update the Audit Trail table to include `notifications` table with correct columns and audit pattern. Update Common Pitfalls section to add: "Using users.agency_id to resolve agent's current agency — use agency_agent_memberships instead."

**Done-when:** PREFLIGHT.md committed to both repos with updated canonical rules. `grep -r "users.agency_id" app/` on the backend returns results only in agency_owner-context code paths.

---

### O.7 — Integration Validation and Phase O Exit

**Goal:** All Phase O deliverables pass end to end. All 12 original journeys still pass. No regressions.

**Tasks:**

Walk the full notification lifecycle: agent submits → agency owner bell increments → agency approves → admin bell increments → admin approves → agent bell shows "Your listing is now live" → mark all read → badge clears.

Walk the governance correction: admin revokes listing → admin Revoked tab shows "Awaiting agency instruction" with no button → agency writes instruction → admin tab shows "Awaiting agent action" → agent edits → full chain completes → admin Revoked tab shows "Restored" with no button throughout.

Confirm instruction ambience is absent on live listings: navigate to agent Live tab, agency Verified Inventory, Public Marketplace — no instruction box visible on any live listing card.

Seeker join request flow: submit request → nav dropdown shows "Join Requests" → track request → cancel pending request → find agency again → resubmit → agency owner approves → seeker's membership tab shows the new active membership.

Agent membership tab: shows all active memberships with listing counts. Public agents directory shows agents resolved from membership table.

Run all 12 original journeys.

`pnpm tsc --noEmit` → 0, `pnpm lint` → 0, `pnpm build` → 0, `pyright` → 0, `pytest --cov` → all passing ≥ 95%.

Update DEFERRED.md — all Phase O items closed or promoted to Phase P.
Update all CLAUDE.md files and commit to both repos.

**Done-when:** All Phase O exit criteria below are true. CI green. CLAUDE.md committed.

---

## 4. Phase O Exit Criteria

| Criterion | Verification | Task |
|---|---|---|
| Notification bell in nav, badge polls every 60s | Badge increments after relevant transition — wait 60s | O.0 |
| All 7 notification event types produce correct notifications | Walk each transition, confirm recipient and body | O.0 |
| Mark-read and mark-all-read work | Badge decrements correctly | O.0 |
| notifications table exists in production with RLS | Supabase SQL query confirms | O.0 |
| Admin Revoked tab: no Restore button at any state | Visual check — no interactive element in Revoked tab | O.1 |
| `revoked && !has_instruction` shows "Awaiting agency instruction" | Visual check as admin | O.1 |
| No call to `/restore/` from any frontend path | `grep -r "restore" src/` — no admin moderation component results | O.1 |
| Live listing cards show no instruction text or has_instruction indicator | Visual check — agent Live, agency Inventory, Public Marketplace | O.2 |
| Seeker avatar dropdown contains "Join Requests" | Visual check as seeker | O.3 |
| Cancel pending join request works | Submit → cancel → status updates | O.3 |
| Resubmit after rejection navigates to agency join form | Click Resubmit → lands on /agencies/{id}/join | O.3 |
| Agent membership cards show listing_count per membership | Visual check — Memberships tab | O.4 |
| Agency roster cards show listing_count per agent | Visual check — agency owner Roster tab | O.4 |
| GET /agents/ resolves agency from agency_agent_memberships | Backend query confirmed via EXPLAIN ANALYZE | O.4 |
| Agency owner dashboard shows accurate listing stats by state | Visual check — all tabs accurate | O.5 |
| PREFLIGHT.md updated with membership invariants | Committed to both repos | O.6 |
| All 12 original journeys passing | Manual walkthrough | O.7 |
| tsc → 0 | pnpm tsc --noEmit | All |
| pyright → 0 | venv pyright | All |
| pytest → all passing, coverage ≥ 95% | pytest --cov gate | All |
| pnpm build → 0 warnings | Next.js production build | All |
| DEFERRED.md updated | All Phase O items closed or promoted to Phase P | All |
| All CLAUDE.md files committed | Root, frontend, backend — Phase O closed state | All |

---

## 5. Execution Sequence

| # | Task | Dependency | Parallel? |
|---|---|---|---|
| 1 | O.0 — Commit, push, validate notifications | None — do first | No — confirm gates pass before moving on |
| 2 | O.1 — Remove Restore button | None | Yes, parallel with O.2 |
| 3 | O.2 — Suppress instruction ambience on live | None | Yes, parallel with O.1 |
| 4 | O.3 — Seeker join request gaps | None | Yes, parallel with O.4 |
| 5 | O.4 — Agent membership tracker + directory fix | None | Yes, parallel with O.3 |
| 6 | O.5 — Agency owner stats (verify first) | O.4 backend confirmed | Yes, parallel with O.3 |
| 7 | O.6 — PREFLIGHT.md membership invariants | O.4 closed | Yes, parallel with O.5 |
| 8 | O.7 — Integration validation and exit | O.0 through O.6 closed | No — final gate |

---

## 6. Items Deferred to Phase P

| Item | Rationale |
|---|---|
| Real-time push notifications (WebSocket / SSE) | Phase O implements poll-based 60s interval. Real-time requires Redis pub/sub or Supabase Realtime. Defer until notification volume validates the investment. |
| Full elimination of users.agency_id for agent rows | Phase O migrates all consuming queries to use agency_agent_memberships. Removing the column itself requires confirming zero remaining callers across all code paths — a separate migration-level task. |
| Notification frequency preference (immediate vs digest) | Emails and in-platform notifications default to immediate. Seeker preference UI is Phase P. |
| In-app messaging / inquiry reply threads | Lead capture is MVP. Reply thread model requires its own data model. |
| Advanced agency analytics (cohort, retention, conversion) | Current stats are count-based. Cohort and funnel analysis requires meaningful traffic volume. |
| TBT < 100ms | Revised target 300ms met. 100ms requires RSC migration. Phase P after traffic data. |
| Saved search notification frequency preference | Phase P. |
| Custom domain setup | Operational task — no code changes. Phase P when ready to go fully public. |
| Audit log retention (DEF-002) | Assess after 60 days real traffic. |
| Nominatim self-hosted | Public API sufficient at current scale. |
| Agency N+1 on public directory | Phase P after traffic data sizes the optimisation. |

---

## 7. Production Reference

| Service | URL / Reference |
|---|---|
| Frontend | https://realtornet-web.vercel.app |
| Backend (prod) | https://realtornet-production.up.railway.app |
| Backend (staging) | https://realtornet-staging.up.railway.app |
| Supabase (prod) | https://fobvnshrqxduuhzgflvd.supabase.co |
| Supabase (staging) | https://avkhpachzsbgmbnkfnhu.supabase.co (password rotated June 17) |
| Supabase (dev) | umhtnqxdvffpifqbdtjs — do not use for production work |
| Email service | Resend — MAIL_FROM domain verification pending (DEF-J-EMAIL-DOMAIN-001 — operator action) |

### Production Accounts

| Email | Role | Agency |
|---|---|---|
| apineorbeenga@gmail.com | admin | NULL |
| apineorbeenga@outlook.com | agency_owner | Apine Real Estate (id=1) |
| apineorbeenga@yahoo.com | agent | Apine Real Estate (id=1) |
| apineterngu19@gmail.com | seeker | NULL |

### Current HEADs

| Repo | HEAD |
|---|---|
| Backend (realtornet) | `88222f5` (notification work is local only, not committed) |
| Frontend (realtornet-web) | `51deb96` (notification work is local only, not committed) |

> **Note:** All agents must re-clone `realtornet` before starting any backend work. Git history was scrubbed in the Phase N session. Pre-scrub local copies have diverged commit hashes and cannot push cleanly.

---

## 8. Session Opening Template

Use this as the opening prompt for every Phase O session.

> "Opening RealtorNet Phase O. Phase N closed June 17 2026 — listing governance, instruction mediation, admin historical tabs, creator/agency name resolution, security incident resolved. Backend HEAD `88222f5` on Railway (`realtornet-production.up.railway.app`). Frontend HEAD `51deb96` on Vercel (`realtornet-web.vercel.app`). Production Supabase `fobvnshrqxduuhzgflvd`. Staging `avkhpachzsbgmbnkfnhu`. Dev `umhtnqxdvffpifqbdtjs` — do not use.
>
> **Critical: all agents must re-clone `realtornet` before starting** — git history was scrubbed, commit hashes changed. Railway env uses `SUPABASE_SECRET_KEY` not `SUPABASE_SERVICE_ROLE_KEY`. `detect-secrets` pre-commit hook is active — any commit with a credential pattern will be blocked.
>
> **Notification work (DEF-M-NOTIF-001) is local only — NOT pushed, NOT migrated.** First task in Phase O is O.0: review local notification files for correctness, run gates (pyright 0, pytest ≥ 95%), commit, push, apply migration to staging, validate done-when criteria.
>
> Governance corrections: O.1 removes the unilateral Restore button from admin Revoked tab (admin never directly restores — full chain only). O.2 suppresses instruction ambience on live listings. Both are frontend-first, surgical fixes.
>
> Membership completeness: O.3 closes seeker join request tracker gaps. O.4 adds listing counts to membership responses and migrates GET /agents/ to use agency_agent_memberships as the sole source of truth for agent affiliation. O.5 verifies and completes agency owner stats. O.6 commits the agency affiliation invariant to PREFLIGHT.md.
>
> Governing invariant for Phase O (Section 2): users.agency_id is valid only for agency_owner role. For agent role, agency_agent_memberships is the sole source of truth. Any code reading users.agency_id in agent context is a bug.
>
> Today's task: [O.0 — commit and validate notification system]. Attach Phase O workbook, PREFLIGHT.md, DEFERRED.md, and all CLAUDE.md files. Read CLAUDE.md non-negotiable rules before starting."

---

*RealtorNet — Phase O Workbook v1.0*
*Derived from Phase N close state | Backend HEAD `88222f5` | Frontend HEAD `51deb96`*
