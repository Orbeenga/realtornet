# RealtorNet — Phase P Workbook
## Membership Governance, Dashboard Separation & Admin Intelligence

Authoritative Preflight & Execution Reference

| Item | Value |
|---|---|
| Phase O closed | June 20, 2026 — notifications live, governance corrections applied, membership tracker and directory fix complete, PREFLIGHT.md invariants committed |
| Backend version | v0.5.3+ — 95.64% coverage, 0 Pyright errors, commit `df9ccf9` |
| Frontend version | Next.js — deployed to Vercel, commit `9f5587d` |
| Stack (locked) | Next.js · TypeScript · Supabase · TanStack Query · FastAPI · Resend email |
| Deploy targets | Vercel (frontend) · Railway (backend) · Supabase (DB + Auth) |
| Production Supabase | `fobvnshrqxduuhzgflvd` |
| Staging Supabase | `avkhpachzsbgmbnkfnhu` |
| Phase P opens | June 20, 2026 |

---

## 0. Phase O Exit State & Entry Conditions

Phase O is fully closed. The notification system is live and polling. Governance violations (Restore button, instruction ambience on live listings) are corrected. Membership listing counts are surfaced across agent and agency owner views. The agency affiliation invariant (`users.agency_id` for ownership, `agency_agent_memberships` for membership) is documented in PREFLIGHT.md and enforced in code.

Phase P is surgical and additive. The core membership state machine and the listing governance state machine are both in place. Phase P surfaces the existing membership states that are recorded in the database but not yet visible in any UI — specifically the enforcement states (rejected, suspended, left/cancelled, revoked, blocked) that currently have no tabs, no CTAs, and no appeal pathways for affected users. Phase P also resolves the information architecture problem on the agency owner page, where dashboard stats and roster governance are co-located on a single cluttered page.

### 0.1 Closed in Phase O

| Item | State |
|---|---|
| Notification bell, badge count, 60s polling, 7 event types | Closed |
| Admin Revoked tab: Restore button removed, CTA derivation corrected | Closed |
| Instruction ambience suppressed on live listings | Closed |
| Seeker join request tracker: nav link, cancel pending, resubmit after rejection | Closed |
| Agent membership tracker: listing_count per membership | Closed |
| Agency roster: listing_count per agent | Closed |
| GET /agents/ resolved from agency_agent_memberships | Closed |
| Agency stats: verified→live bug fixed, listings_by_status and agents_by_status breakdowns | Closed |
| PREFLIGHT.md: canonical rule 14 (Agency Affiliation Authority) | Closed |
| ModerationStatus serialization: .value not str() | Closed |

### 0.2 Phase P Opening Backlog

| ID | Item | Priority | Owner |
|---|---|---|---|
| DEF-P-SEEK-000 | Seeker: missing rejected tab | High | Frontend |
| DEF-P-DASH-001 | Agency owner: Dashboard and Membership Management on same page — must separate | High | Frontend |
| DEF-P-MEM-001 | Agency owner: enforcement tabs missing (Rejected, Suspended, Left/Cancelled, Revoked, Blocked) | High | Backend + Frontend |
| DEF-P-MEM-002 | Agent: enforcement membership tabs missing (Rejected, Suspended, Left/Cancelled, Revoked, Blocked) | High | Frontend |
| DEF-P-ADMIN-001 | Admin stats dashboard: listing state breakdown missing zero-value states | Medium | Frontend |
| DEF-P-TEST-001 | Stats endpoint missing regression test for ModerationStatus key format | Medium | Backend |
| DEF-J-EMAIL-DOMAIN-001 | MAIL_FROM domain verification — operator action, no code changes | High | Operator |

---

## 1. Governing Principle

Phase P makes the membership lifecycle as legible as the listing lifecycle. Every state a membership can be in is surfaced to the affected user with context, history, and an appropriate CTA. No user is left in an ambiguous dead end because the platform has no surface for their current membership state. The agency owner's operational context is split across two focused pages instead of one cluttered page. Admin has full visibility of all listing states including empty queues.

---

## 2. Membership State Reference — Design Specification

Read this before any P.1 through P.4 work begins. It defines the states, the data source for each, and the CTA each state surfaces to each actor.

### 2.1 Current Membership States in the System

The `agency_agent_memberships.status` field and `agent_membership_audit.action` field together record the full history. Confirm the exact enum values before implementing by running `\dT` on the relevant type in the DB. Based on existing implementation:

| Status | Meaning | Recorded by |
|---|---|---|
| `active` | Current member in good standing | `joined` / `reinstated` audit action |
| `suspended` | Temporarily suspended by agency owner | `suspended` audit action |
| `left` | Agent voluntarily left or cancelled their membership in an agency | `left` audit action |
| `revoked` | Membership revoked by agency owner or admin | `revoked` audit action |
| `inactive` | Membership ended — used for historical agency membership | `left` audit action |
| `pending` | Join request awaiting agency decision | join_requests table |
| `rejected` | Join request rejected by agency | join_requests table |
| `cancelled` | Seeker cancelled their own pending request | join_requests table (Phase O) |

`blocked` is not yet a confirmed enum value. P.1 verifies whether it exists before implementing any UI for it. If it does not exist, P.1 adds it as a new value via Alembic migration or defers it to Phase Q with documented rationale.

### 2.2 Tab Mapping per Actor

**Agent — Memberships page (currently at `/account/join-requests`, Memberships tab)**

```
Current:
  Active — own listings where membership status = active

Add in Phase P:
  Rejected    — join requests where status = rejected
                CTA: Apply Again → navigates to /agencies/{agency_id}/join
                (new application, fresh start)

  Suspended   — memberships where status = suspended
                CTA: Request Review → submits to that agency's review queue
                (returns as returning applicant with suspension history visible)

  Left/Cancelled — memberships where status = left
                CTA: Request Reinstatement → submits to that agency's review queue
                (returns as returning applicant with reason for leaving history visible)

  Revoked     — memberships where status = revoked
                CTA: Request Review → same review queue path as post-revocation
                (prior revocation reason shown; agency owner sees history on review)

  Blocked     — only if blocked status confirmed in schema
                Label only: "Your access to this agency has been blocked"
                No CTA — platform decision, no appeal within platform
```

**Agency Owner — Membership Management page (new page at `/account/agency/members`)**

```
Current tabs (move from /account/agency to /account/agency/members):
  Join Requests   — pending new applicants
  Review Requests — returning applicants requesting reinstatement
  Agent Roster    — active members
  Invitations     — pending invites sent by agency owner

Add in Phase P:
  Rejected    — applicants this agency has rejected
                Shows: applicant name, rejection date, reason if set
                CTA: Reconsider → moves to Join Requests for fresh review
                (read-mostly — action is optional, not required)

  Suspended   — currently suspended agents
                Shows: agent name, suspension date, reason, listing count frozen
                CTA: Reinstate / Continue Suspension

  Left/Cancelled — agents who left or cancelled membership
                Shows: agent name, leave/cancellation date, reason, listing count frozen
                CTA: Reinstate / Reject

  Revoked     — revoked memberships (historical)
                Shows: agent name, revocation date, reason
                CTA: Reinstate (creates new active membership if approved)
                This is separate from the review_requests flow — agency owner
                can directly reinstate without the agent needing to request it

  Blocked     — only if blocked status confirmed in schema
                Shows: blocked user, block reason
                CTA: Unblock
```

### 2.3 Appeal CTA Flow Design

Rejected application → Apply Again: navigates to `/agencies/{agency_id}/join`. Creates a new join request. The agency owner's Join Requests tab will surface the prior rejection history for context when reviewing (already implemented in Phase I — returning applicant detection).

Suspended membership → Request Review: calls `POST /agencies/{id}/review-requests/` (already exists from Phase I). The agency owner's Review Requests tab shows suspension history context on the review card.

Left/Cancelled membership → Request Reinstatement: calls `POST /agencies/{id}/review-requests/` (may already exist from Phase I). The agency owner's Review Requests tab shows leave/cancellation history context on the review card. If not already implemented, add the endpoint.

Revoked membership → Request Review: same endpoint. Agency owner sees prior revocation reason prominently (already implemented — Phase I Rule 5).

Blocked membership → No appeal CTA within platform. If block is admin-level, the display reads "Contact platform support." If agency-level, the display reads "This agency has restricted your access."

---

## 3. Phase P Work Plan — End to End

Six sequential tasks. P.1 (backend verification) must close before P.2 through P.4 begin. P.2 (routing restructure) is independent of P.3 and P.4 and can run in parallel once P.1 confirms schema state.

### P.1 — Backend: Schema Verification and Endpoint Audit

**Goal:** Confirm the exact enum values in production before any frontend work targets them. Identify any missing endpoints or schema fields. This is a read-and-report task — no code changes unless verification reveals a gap.

**Tasks:**

Confirm `agency_agent_memberships.status` enum values in production:
```sql
SELECT pg_enum.enumlabel
FROM pg_enum
JOIN pg_type ON pg_enum.enumtypid = pg_type.oid
WHERE pg_type.typname = 'agency_membership_status_enum';
```
Report exact values. If `blocked` is absent, document DEF-P-BLOCK-001 and defer blocked-tab implementation to Phase Q. Do not add it in Phase P unless it already exists.

Confirm `agency_join_requests.status` enum values include `cancelled` (added in Phase O). Confirm `rejected` exists as a join request status.

Confirm `left` is an appropriate industry-standard name for the "agent voluntarily leaves or cancels their membership" state. If the existing enum uses a different label (e.g. `cancelled`, `inactive`, `left`), use that value. If no appropriate value exists, add `left` via Alembic migration.

Confirm `GET /agency-memberships/mine/` returns `status` field on each membership. Confirm `GET /join-requests/mine/` returns `status` and `agency_id` on each request (agency_id was added in Phase O — verify it is in the response).

Confirm `POST /agencies/{id}/review-requests/` endpoint exists and is reachable from an agent with a revoked or suspended membership. Verify the response includes a confirmation state the frontend can use to show "Request submitted."

If any of the above are missing, add them in this task before P.2 through P.4 begin. pyright 0, pytest ≥ 95% after any additions.

**Done-when:** Complete schema report produced. All required fields confirmed present in API responses. Any gaps fixed or logged as deferred with DEF codes. No assumptions carried into frontend tasks.

---

### P.2 — Frontend: Agency Dashboard and Membership Management Separation

**Goal:** The agency owner's single `/account/agency` page is split into two focused pages. Agency Dashboard (stats and performance) lives at `/account/agency`. Membership Management (all roster and request tabs) lives at `/account/agency/members`. The agency owner avatar dropdown is updated to link to both.

**Pre-implementation verification (no code):**

Read the current `AgencyOwnerDashboardClient.tsx` and confirm which sections contain stats versus membership management. Confirm the current routing setup — is `/account/agency` a single page or are there already sub-routes? Report before writing any code.

**Frontend tasks:**

Create `/account/agency/members/page.tsx`:
- Move all membership management tabs out of `AgencyOwnerDashboardClient.tsx` into a new `AgencyMembersClient.tsx` component
- Tabs to move: Join Requests, Review Requests, Agent Roster, Invitations
- Tabs to add (from P.3): Rejected, Suspended, Left/Cancelled, Revoked, and Blocked (if schema confirms)
- Page title: "Membership Management — [Agency Name]"

Update `/account/agency/page.tsx`:
- Remove all membership management tabs
- Retain: stats overview cards (Live listings, Roster agents), listing state breakdown, agents_by_status breakdown
- Add: quick-link card to "/account/agency/members" — "Manage your roster and membership requests"
- Page title: "Agency Dashboard — [Agency Name]"

Update `navigation.ts` for agency_owner dropdown:
```
My Listings
Agency Dashboard      → /account/agency
Agency Members        → /account/agency/members
My Inquiries
My Favorites
My Reviews
Settings
Sign out
```

tsc 0, lint 0, build 0 before push.

**Done-when:** Log in as `apineorbeenga@outlook.com`. Avatar dropdown shows "Agency Dashboard" and "Agency Members" as separate links. `/account/agency` shows only stats and performance data. `/account/agency/members` shows only roster and request tabs. No content duplication between the two pages. Both pages load without error.

---

### P.3 — Frontend: Agency Owner Membership Enforcement Tabs

**Goal:** Agency owner's Membership Management page (`/account/agency/members`) gains enforcement-state tabs. Agency owners have full visibility of all membership states within their agency.

**Depends on:** P.1 (schema confirmed), P.2 (page exists).

**Frontend tasks:**

Add the following tabs to `AgencyMembersClient.tsx` (from P.2):

**Rejected tab:**
- Source: `GET /join-requests/mine/` filtered where `status === 'rejected'` on the agency owner side — or a dedicated `GET /agencies/{id}/join-requests/?status=rejected` endpoint (confirm with backend from P.1)
- Each card: applicant name, rejection date, rejection reason if set
- CTA: "Reconsider" — moves request back to pending for fresh review (confirm backend endpoint exists; if not, flag as DEF-P-RECONSIDER-001)
- If no rejected requests: empty state "No rejected applications."

**Suspended tab:**
- Source: `GET /agencies/{id}/agents/` filtered where membership `status === 'suspended'`
- Each card: agent name, suspension date, reason, listing count (frozen at suspension time)
- CTAs: "Reinstate" (calls existing reinstate endpoint) and "Revoke" (escalates to revocation)
- If no suspended agents: empty state "No suspended agents."

**Left/Cancelled tab:**
- Source: `GET /agencies/{id}/agents/` filtered where membership `status === 'left'`
- Each card: agent name, leave/cancellation date, reason, listing count (frozen at cancellation time)
- CTAs: "Reinstate" (calls existing reinstate endpoint) and "Reject"
- If no left/cancelled memberships: empty state "No departed members."

**Revoked tab:**
- Source: `GET /agencies/{id}/agents/` filtered where membership `status === 'revoked'`
- Each card: agent name, revocation date, reason
- CTA: "Reinstate" (creates new active membership via existing reinstate endpoint)
- Note: distinct from Review Requests — agency owner can directly reinstate without waiting for agent to request it
- If no revoked agents: empty state "No revoked memberships."

**Blocked tab (conditional):**
- Only render this tab if P.1 confirmed `blocked` exists as a schema status
- If schema confirms: source, display, and CTA as specified in Section 2.2
- If schema does not confirm: omit tab entirely and log DEF-P-BLOCK-001

For each tab, use TanStack Query with appropriate query keys. On any successful action (reinstate, revoke, reconsider), invalidate all membership-related query keys so all tabs refresh without page reload. Use the existing `AlertDialog` pattern (already in the codebase) for any destructive or irreversible action.

tsc 0, lint 0, build 0 before push.

**Done-when:** Log in as `apineorbeenga@outlook.com`. Navigate to `/account/agency/members`. All implemented tabs render with correct data from API responses. Confirm each CTA fires the correct endpoint from browser DevTools Network tab. Paste at least one API response per new tab as evidence.

---

### P.4 — Frontend: Agent Membership Enforcement Tabs

**Goal:** Agent's Memberships view gains enforcement-state tabs. Agents have full visibility of all their membership states across all agencies, with contextually appropriate appeal CTAs.

**Depends on:** P.1 (schema confirmed).

**Current location:** `/account/join-requests` — the "Memberships" tab in `MyJoinRequestsClient.tsx`.

**Frontend tasks:**

The existing Memberships tab shows active memberships. Restructure the Memberships section into sub-tabs:

**Active (current content — rename for clarity):**
- Existing content: active membership cards with listing_count
- No change to data or CTAs — this is the current Memberships tab

**Rejected (from join_requests where status = rejected):**
- Source: `GET /join-requests/mine/` filtered where `status === 'rejected'`
- Each card: agency name, rejection date, reason if provided by agency
- CTA: "Apply Again" → navigates to `/agencies/{agency_id}/join`
- Copy under CTA: "Submitting a new application will appear as a returning applicant to the agency."
- If no rejected requests: empty state "No rejected applications."

**Suspended (from memberships where status = suspended):**
- Source: `GET /agency-memberships/mine/` filtered where `status === 'suspended'`
- Each card: agency name, suspension date, reason
- CTA: "Request Review" → calls `POST /agencies/{id}/review-requests/` with the agent's message
- On success: CTA changes to "Review requested — awaiting agency response" (disabled button)
- Prevents duplicate review requests: if a pending review request already exists for this membership, show the disabled state immediately on load
- If no suspended memberships: empty state "No suspended memberships."

**Left/Cancelled (from memberships where status = left):**
- Source: `GET /agency-memberships/mine/` filtered where `status === 'left'`
- Each card: agency name, cancellation date, reason
- CTA: "Request Reinstatement" → calls `POST /agencies/{id}/review-requests/` with the agent's message
- On success: CTA changes to "Reinstatement requested — awaiting agency response" (disabled button)
- Prevents duplicate review requests: if a pending review request already exists for this membership, show the disabled state immediately on load
- If no left/cancelled memberships: empty state "No cancelled memberships."

**Revoked (from memberships where status = revoked):**
- Source: `GET /agency-memberships/mine/` filtered where `status === 'revoked'`
- Each card: agency name, revocation date, reason
- CTA: "Request Review" — same flow as suspended
- Copy under CTA: "Your revocation history will be visible to the agency during their review."
- If no revoked memberships: empty state "No revoked memberships."

**Blocked tab (conditional):**
- Only render if P.1 confirmed `blocked` exists as schema status
- If schema confirms: read-only card with block reason. No appeal CTA. Label: "Contact platform support if you believe this is an error."
- If schema does not confirm: omit and log DEF-P-BLOCK-001

The same page serves the seeker's join request tracking (Sent Requests sub-tab) and the agent's membership tracking (Active, Rejected, Suspended, Left/Cancelled, Revoked sub-tabs). These are two distinct user journeys sharing one page. The page-level tabs should make this clear — consider "My Applications" for seeker request tracking and "My Memberships" for the membership state tabs.

tsc 0, lint 0, build 0 before push.

**Done-when:** Log in as `apineorbeenga@yahoo.com`. Navigate via avatar dropdown → My Agencies. Confirm the enforcement tabs render (even if empty — the empty state is the correct result on production where no enforcement actions have been taken). Confirm the Active tab still shows Apine with listing_count: 3 (regression check). Confirm "Request Review" CTA is present on Revoked and Suspended tabs. Paste browser Network tab showing the correct API calls for each tab.

---

### P.5 — Frontend: Admin Stats Listing State Breakdown

**Goal:** Admin analytics page shows all listing state breakdown cards including zero-value states. Admin's view of the platform is a governance view — an empty queue is as meaningful as a full one.

**Context:** The agency owner dashboard correctly hides zero-value breakdown cards (noise, not information). Admin is different. "Agency Review: 0" tells admin the agency queue is clear. "Admin Review: 0" tells admin they have no pending approvals. Zeros are information for admin, not noise.

**Frontend tasks:**

Locate the admin analytics page component. Confirm whether a listing state breakdown section exists or whether this is a new section to add.

If no breakdown section exists: add a "Listing State Breakdown" section that calls `GET /api/v1/admin/properties/stats/` (or the relevant admin stats endpoint — confirm from codebase). Render a card for each state in the moderation enum with its count, including zero-count states.

If a breakdown section exists but filters zeros: remove the zero-filter. All states render. Use the human-readable `MODERATION_LABELS` map (already in the codebase) for card titles rather than raw enum values.

The full enum set to display:
```
Draft | Agency Review | Agency Rejected | Admin Review | Admin Rejected | Live | Revoked
```

Display order: match the state machine flow (draft first, live last, revoked at end).

tsc 0, lint 0, build 0 before push.

**Done-when:** Log in as `apineorbeenga@gmail.com`. Navigate to admin analytics. Confirm all 7 listing states appear as cards including states with zero count. Confirm human-readable labels are used (not raw enum strings). Paste a screenshot or DOM inspection showing all 7 cards.

---

### P.6 — Backend: Stats Regression Test

**Goal:** A test exists that would have caught the `ModerationStatus.live` vs `"live"` key serialization bug before it reached production.

**Tasks:**

In the appropriate test file for the agencies stats endpoint, add a test that calls `GET /agencies/{id}/stats/` and asserts:
- Response is 200
- `listings_by_status` keys are plain strings matching enum values (`"live"`, `"draft"`, etc.) — not prefixed with the class name
- `agents_by_status` keys are similarly plain strings

```python
def test_agency_stats_listing_status_keys_are_plain_strings(client, agency_owner_token, agency_with_listings):
    response = client.get(
        f"/api/v1/agencies/{agency_with_listings.agency_id}/stats",
        headers={"Authorization": f"Bearer {agency_owner_token}"}
    )
    assert response.status_code == 200
    data = response.json()
    for key in data["listings_by_status"].keys():
        assert "." not in key, f"Key '{key}' contains class prefix — use .value not str()"
    for key in data["agents_by_status"].keys():
        assert "." not in key, f"Key '{key}' contains class prefix — use .value not str()"
```

pyright 0, pytest ≥ 95%.

**Done-when:** Test exists, passes, and would fail if `.value` were changed back to `str()`. Coverage gate still ≥ 95%.

---

### P.7 — Integration Validation and Phase P Exit

**Goal:** All Phase P deliverables pass end to end. All 12 original journeys still pass. No regressions on Phase O work.

**Tasks:**

Walk the agency owner flow: log in as `apineorbeenga@outlook.com` → avatar dropdown shows Agency Dashboard and Agency Members → Dashboard page shows stats only → Members page shows all tabs including enforcement tabs → all tab counts correct.

Walk the agent flow: log in as `apineorbeenga@yahoo.com` → avatar dropdown → My Agencies → Active tab shows Apine with listing_count: 3 → other tabs render with appropriate empty states.

Walk the seeker flow: log in as `apineterngu19@gmail.com` → avatar dropdown → Join Requests → confirm seeker join request tracking unaffected by agent membership tab additions.

Walk admin analytics: log in as `apineorbeenga@gmail.com` → analytics → all 7 listing state cards visible.

Walk all 12 original journeys from Phase D.

`pnpm tsc --noEmit` → 0, `pnpm lint` → 0, `pnpm build` → 0, `pyright` → 0, `pytest --cov` → all passing ≥ 95%.

Update DEFERRED.md — all Phase P items closed or promoted to Phase Q.
Update all CLAUDE.md files and commit to both repos.

**Done-when:** All Phase P exit criteria below are true. Browser evidence for each criterion. CI green. CLAUDE.md committed.

---

## 4. Phase P Exit Criteria

| Criterion | Verification | Task |
|---|---|---|
| Schema report confirms exact membership status enum values | SQL query output | P.1 |
| All required API fields confirmed present | curl responses from staging | P.1 |
| `/account/agency` shows stats and performance only | Visual check as agency_owner | P.2 |
| `/account/agency/members` shows roster and request tabs | Visual check as agency_owner | P.2 |
| Agency owner dropdown has "Agency Dashboard" and "Agency Members" | Visual check | P.2 |
| Agency owner Rejected tab renders with correct data and Reconsider CTA | Network trace | P.3 |
| Agency owner Suspended tab renders with correct data and Reinstate CTA | Network trace | P.3 |
| Agency owner Left/Cancelled tab renders with correct data and Reinstate CTA | Network trace | P.3 |
| Agency owner Revoked tab renders with correct data and Reinstate CTA | Network trace | P.3 |
| Agent Active tab: Apine shows listing_count: 3 (regression) | API response | P.4 |
| Agent Rejected tab renders correct data and Apply Again CTA | Network trace | P.4 |
| Agent Suspended tab renders correct data and Request Review CTA | Network trace | P.4 |
| Agent Left/Cancelled tab renders correct data and Request Reinstatement CTA | Network trace | P.4 |
| Agent Revoked tab renders correct data and Request Review CTA | Network trace | P.4 |
| Request Review CTA disabled state when review already submitted | Visual check | P.4 |
| Admin analytics shows all 7 listing state cards including zeros | DOM inspection | P.5 |
| Admin stats card labels are human-readable not raw enum strings | Visual check | P.5 |
| Stats regression test exists and passes | pytest output | P.6 |
| Stats regression test would fail on str() regression | Manual verification | P.6 |
| All 12 original journeys passing | Manual walkthrough | P.7 |
| tsc → 0 | pnpm tsc --noEmit | All |
| pyright → 0 | venv pyright | All |
| pytest → all passing, coverage ≥ 95% | pytest --cov gate | All |
| pnpm build → 0 warnings | Next.js production build | All |
| DEFERRED.md updated | All Phase P items closed or promoted | All |
| All CLAUDE.md files committed | Root, frontend, backend — Phase P closed state | All |

---

## 5. Execution Sequence

| # | Task | Dependency | Parallel? |
|---|---|---|---|
| 1 | P.1 — Schema verification and endpoint audit | None — do first | No — P.2/P.3/P.4 depend on schema report |
| 2 | P.2 — Agency dashboard and members page separation | P.1 confirmed | No — P.3 depends on new page existing |
| 3 | P.3 — Agency owner enforcement tabs | P.1 + P.2 closed | Yes, parallel with P.4 |
| 4 | P.4 — Agent enforcement tabs | P.1 confirmed | Yes, parallel with P.3 |
| 5 | P.5 — Admin stats breakdown | None | Yes, parallel with P.3/P.4 |
| 6 | P.6 — Stats regression test | None | Yes, parallel with P.2/P.3 |
| 7 | P.7 — Integration validation and exit | P.1 through P.6 closed | No — final gate |

---

## 6. Items Deferred to Phase Q

| Item | Rationale |
|---|---|
| `blocked` membership status (if not in schema) | If P.1 confirms `blocked` does not exist as an enum value, adding it requires an Alembic migration and policy design (agency-level block vs admin-level block). Defer to Phase Q with DEF-P-BLOCK-001. |
| Reconsider CTA for rejected applicants (if backend endpoint missing) | Agency owner reconsidering a rejected application requires a status reset endpoint. If not in current schema, defer to Phase Q with DEF-P-RECONSIDER-001. |
| Real-time push notifications (WebSocket / SSE) | Phase O implements poll-based 60s interval. Real-time requires Redis pub/sub or Supabase Realtime. Defer until notification volume validates the investment. |
| Full elimination of users.agency_id for agent rows | Phase O migrated all consuming queries to agency_agent_memberships. Column removal requires confirming zero remaining callers — separate migration-level task. |
| Notification frequency preference (immediate vs digest) | Default to immediate. Preference UI requires scheduler logic. |
| In-app messaging / inquiry reply threads | Lead capture is MVP. Reply thread model requires its own data model. |
| Advanced agency analytics (cohort, retention, conversion) | Count-based stats are in place. Cohort and funnel analysis requires meaningful traffic volume. |
| Saved search notification frequency preference | Phase Q. |
| Custom domain setup | Operational task — no code changes. |
| Audit log retention (DEF-002) | Assess after 60 days real traffic. |
| TBT < 100ms | Revised target 300ms met. RSC migration required for 100ms. Phase Q after traffic data. |
| Agency N+1 on public directory | Phase Q after traffic data sizes the optimisation. |
| Admin analytics advanced cohort metrics | Requires real traffic data. |

---

## 7. Production Reference

| Service | URL / Reference |
|---|---|
| Frontend | https://realtornet-web.vercel.app |
| Backend (prod) | https://realtornet-production.up.railway.app |
| Backend (staging) | https://realtornet-staging.up.railway.app |
| Supabase (prod) | https://fobvnshrqxduuhzgflvd.supabase.co |
| Supabase (staging) | https://avkhpachzsbgmbnkfnhu.supabase.co |
| Supabase (dev) | umhtnqxdvffpifqbdtjs — do not use for production work |
| Email service | Resend — MAIL_FROM domain verification pending (DEF-J-EMAIL-DOMAIN-001 — operator action) |

### Production Accounts

| Email | Role | Agency |
|---|---|---|
| apineorbeenga@gmail.com | admin | NULL |
| apineorbeenga@outlook.com | agency_owner | Apine Real Estate (id=1) |
| apineorbeenga@yahoo.com | agent | Apine Real Estate (id=1) |
| apineterngu19@gmail.com | seeker | NULL |

---

## 8. Session Opening Template

Use this as the opening prompt for every Phase P session.

> "Opening RealtorNet Phase P. Phase O closed June 20 2026 — notifications live, governance corrections applied (Restore button removed, instruction ambience suppressed), membership listing_count surfaced, agency affiliation invariant in PREFLIGHT.md. Backend HEAD `df9ccf9` on Railway (`realtornet-production.up.railway.app`). Frontend HEAD `9f5587d` on Vercel (`realtornet-web.vercel.app`). Production Supabase `fobvnshrqxduuhzgflvd`. Staging `avkhpachzsbgmbnkfnhu`. Dev `umhtnqxdvffpifqbdtjs` — do not use.
>
> Locked invariants: users.agency_id is valid only for agency_owner ownership context. agency_agent_memberships is the sole source of truth for agent affiliation. ModerationStatus serialization uses .value not str(). detect-secrets pre-commit hook is active. Sequential deploy order: backend → Railway deploys → pnpm gen:types → frontend.
>
> Phase P governing principle: surface existing membership states that are recorded in the database but not visible in any UI. This is surgical and additive — the state machine is in place, the data is there, the tabs are the gap. No architectural changes required.
>
> First task in Phase P is P.1: schema verification — run the SQL query to confirm exact enum values in agency_agent_memberships.status before any frontend work begins. Report the output before writing any code.
>
> Attach Phase P workbook, PREFLIGHT.md, DEFERRED.md, and all CLAUDE.md files. Read CLAUDE.md non-negotiable rules before starting. Workflow: feature → staging → validate → main → production. Browser evidence required for all done-when criteria — code presence is not completion."

---

*RealtorNet — Phase P Workbook v1.0*
*Derived from Phase O close state | Backend HEAD `df9ccf9` | Frontend HEAD `9f5587d`*
