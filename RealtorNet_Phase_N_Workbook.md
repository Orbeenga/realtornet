# RealtorNet — Phase N Workbook
## Listing Intelligence, Mediated Governance & Notification Completion

Authoritative Preflight & Execution Reference

| Item | Value |
|---|---|
| Phase M closed | June 14, 2026 — all exit criteria met, listing governance state machine live, CLAUDE.md committed |
| Backend version | v0.5.3+ — 96.15% coverage, 0 Pyright errors, commit 13ae557 |
| Frontend version | Next.js — deployed to Vercel, commit 04dfa8a |
| Stack (locked) | Next.js · TypeScript · Supabase · TanStack Query · FastAPI · Resend email |
| Deploy targets | Vercel (frontend) · Railway (backend) · Supabase (DB + Auth) |
| Production Supabase | fobvnshrqxduuhzgflvd |
| Staging Supabase | avkhpachzsbgmbnkfnhu |
| Phase N opens | June 14, 2026 |

---

## 0. Phase M Exit State & Entry Conditions

Phase N inherits a fully functional listing governance system. The seven-state machine (`draft → agency_review → agency_rejected → admin_review → admin_rejected → live → revoked`) is live on backend and frontend. `listing_events` is writing an append-only audit row on every state transition. The admin All tab already surfaces the full audit trail by listing, confirmed via production inspection.

Three classes of gap carry forward into Phase N: governance intelligence (the system does not yet mediate between admin enforcement actions and agent response), display correctness (creator versus agency name logic not yet state-aware, agent tab cache stale after remote mutations), and notification completion (submission and approval emails not yet wired, in-platform notifications deferred from Phase M).

### 0.1 Closed in Phase M

| Item | State |
|---|---|
| Seven-state moderation enum live in DB and OpenAPI schema | Closed |
| listing_events table — append-only, RLS enabled, writing on every transition | Closed |
| All lifecycle endpoints (submit, approve, reject, withdraw, recall, reinstate, revoke, restore) | Closed |
| Centralised transition guard in listing_moderation_guard.py | Closed |
| Agent My Listings — 6-tab dashboard | Closed |
| Agency Owner My Listings — 6-tab dashboard | Closed |
| Admin moderation — 5-tab rewire using new enum vocabulary | Closed |
| owner_display_name in PropertyResponse via user join | Closed |
| property_count on agency list response | Closed |
| Draft visibility restricted to creator only | Closed |
| Coverage at 96.15%, gates green | Closed |

### 0.2 Phase N Opening Backlog

| ID | Item | Priority | Owner |
|---|---|---|---|
| Issue-N-1 | Creator vs agency name display not state-aware — wrong name shown across dashboard tabs | High | Frontend |
| Issue-N-2 | Agent tab cache stale after admin or agency mutation — Live, Agency Inventory, Public Marketplace show wrong count | High | Frontend |
| Issue-N-3 | Revocation and rejection mediation model — agent locked out with no instruction pathway, admin Revoked tab not historically omniscient | High | Backend + Frontend |
| DEF-N-ENDPOINTS-001 | Three read endpoints deferred from M.2: agency-queue, agency-inventory, pending-admin | High | Backend |
| DEF-N-TRANSITIONS-001 | revoked → admin_rejected transition endpoint deferred from M.2 | Medium | Backend |
| DEF-N-NOTIFICATIONS-001 | Submission and approval notification emails not yet wired | High | Backend |
| DEF-M-NOTIF-001 | In-platform notifications deferred from Phase M | Medium | Backend + Frontend |
| DEF-J-EMAIL-DOMAIN-001 | MAIL_FROM domain verification — operator action, no code changes needed | High | Operator |

---

## 1. The Mediated Governance Model — Design Specification

This section is the governing design for N.1, N.2, N.3, and N.7. Read it fully before any implementation begins.

### 1.1 The Problem with the Current Post-Enforcement State

When admin revokes a listing or rejects it at `admin_rejected`, the current system puts the agent in an ambiguous dead end. The agent can see the listing is revoked or rejected but has no structured pathway for what happens next. The Phase M state machine defined the transitions but not the mediation layer that governs when and how the agent is permitted to re-enter the chain.

The same gap exists for the admin Revoked and Rejected tabs. Currently these are current-state filters. Once a listing leaves the `revoked` or `admin_rejected` state through the chain, it disappears from those tabs — losing the historical record the admin cares about.

### 1.2 The Instruction Mediation Flow

The governing principle: when enforcement comes from outside the agency (admin revokes or admin rejects), the agency owns the communication channel back to the agent. The agent cannot act on a revoked or admin_rejected listing until their agency has instructed them. The platform mediates this — it does not assume the agent knows what to do.

```
Admin revokes listing
      |
      v
Listing status: revoked
Agent tab: "Revoked" — ambient message only, no action CTAs
Agency tab: "Revoked" — Instruct button + View button
      |
Agency owner clicks Instruct
Writes instruction text (direct agent to edit + resubmit, or delete)
      |
      v
listing_instructions row created, referencing the revocation event
Agent tab: "Revoked" — instruction text now visible, CTAs unlock (Edit + Resubmit / Delete)
      |
Agent acts: edits listing
      |
      v
Full chain restarts: draft → agency_review → admin_review → live (or admin_rejected)
      |
Admin Revoked tab: listing remains in historical record throughout
Restore button tracks automatically:
  current status = revoked, no instruction yet  → "Restore" button active
  current status = revoked, instruction written  → "Awaiting agent action"
  current status = draft / agency_review / admin_review  → "In progress"
  current status = live  → "Restored" label (no button)
  current status = admin_rejected  → "Rejected"
Admin never manually updates the Revoked tab — the system derives CTA from current moderation_status.
```

The same mediation applies when admin rejects (`admin_rejected`). Agency instructs. Agent's edit CTA is gated on instruction existence. Admin Rejected tab becomes historically omniscient by the same mechanism.

For `agency_rejected`, no instruction mediation is required. The rejection originates within the agency, the reason is already visible to the agent, and the agent can edit and resubmit directly. The agency IS the communication channel in this case.

### 1.3 listing_instructions Table

```
listing_instructions
  instruction_id          BIGINT GENERATED ALWAYS AS IDENTITY (PK)
  listing_id              BIGINT FK → properties.property_id NOT NULL
  agency_id               BIGINT FK → agencies.agency_id NOT NULL
  actor_id                BIGINT FK → users.user_id NOT NULL
  triggered_by_event_id   BIGINT FK → listing_events.event_id NOT NULL
  instruction_text        TEXT NOT NULL
  created_at              TIMESTAMPTZ DEFAULT now()
```

Append-only. Never updated, never deleted. `triggered_by_event_id` ties the instruction to the specific revocation or rejection event that prompted it. This enables precise gating across multiple lifecycle cycles — an instruction from a prior revocation cycle does not unlock CTAs for a new one.

RLS: agents see own listing's instructions. Agency owners see all instructions for their agency's listings. Admins see all.

### 1.4 CTA Gating Logic

An agent's action CTAs on a `revoked` or `admin_rejected` listing are unlocked when and only when a `listing_instructions` row exists where:

- `listing_id` matches the listing
- `triggered_by_event_id` matches the most recent `listing_events` row with `to_status IN ('revoked', 'admin_rejected')` for this listing

The backend includes `has_instruction: bool` and `instruction_text: str | null` in `PropertyResponse` when returned to the listing's creator. These fields are derived server-side to avoid N+1 fetches on the dashboard tab queries. They are absent from responses to other actors.

### 1.5 Admin Historical Tab Tracking

Admin Revoked tab and Admin Rejected tab are redefined as historical views, not current-state filters.

**Admin Revoked tab** — query: all listings where `listing_events` contains at least one row with `to_status = 'revoked'` for that listing, regardless of current `moderation_status`. Ordered by most recent revocation event descending.

**Admin Rejected tab** — query: all listings where `listing_events` contains at least one row with `to_status = 'admin_rejected'`, regardless of current `moderation_status`.

Each listing in these tabs carries its `current_moderation_status` and `revocation_reason` (or `rejection_reason`) from the most recent relevant event. The frontend derives the CTA from `current_moderation_status`.

### 1.6 CTA Derivation Map for Admin Historical Tabs

```
current_moderation_status        CTA on admin Revoked tab
revoked, no instruction          "Restore" button active
revoked, instruction exists      "Awaiting agent action" (no button)
draft                            "In progress — agent editing"
agency_review                    "In progress — agency review"
admin_review                     "In progress — admin queue"
live                             "Restored" (label only)
admin_rejected                   "Rejected" (label only)

current_moderation_status        CTA on admin Rejected tab
admin_rejected, no instruction   "Reinstate" button active
admin_rejected, instruction      "Awaiting agent action"
draft                            "In progress — agent editing"
agency_review                    "In progress — agency review"
admin_review                     "In progress — admin queue"
live                             "Resolved — listing live"
revoked                          "Revoked" (label only)
```

### 1.7 Creator vs Agency Name Display Rule

What name appears on a listing card in any dashboard tab is determined by the listing's current `moderation_status`, not by the tab it appears in. The rule is:

- States visible only inside the agency: `draft`, `agency_review`, `agency_rejected` → show `owner_display_name` (creator name)
- States visible to admin and/or public: `admin_review`, `admin_rejected`, `live`, `revoked` → show `agency_name`

This is computed as a constant map in a shared utility. Every listing card component consumes this utility. The display updates automatically as `moderation_status` changes — no hardcoding per tab.

```ts
const AGENCY_NAME_STATES: ReadonlySet<ModerationStatus> = new Set([
  'admin_review',
  'admin_rejected',
  'live',
  'revoked',
])

export const resolveListingDisplayName = (
  status: ModerationStatus,
  ownerDisplayName: string | null,
  agencyName: string | null,
): string => {
  if (AGENCY_NAME_STATES.has(status)) {
    return agencyName ?? 'Agency'
  }
  return ownerDisplayName ?? 'Agent'
}
```

This function is the single source of truth. It is imported everywhere a listing card renders a name. No inline ternaries, no per-tab logic.

---

## 2. Phase N Work Plan

### N.1 — Backend: listing_instructions Table and Mediation Endpoints

Goal: database and API support the instruction mediation layer. No frontend mediation UI begins until N.1 is closed.

**Tasks:**

Alembic migration: CREATE TABLE listing_instructions with schema from Section 1.3. RLS enabled on creation. Append-only constraint enforced at DB level (trigger or policy — do not rely on application layer alone). Same pattern as `agent_membership_audit`.

Add `has_instruction: bool` and `instruction_text: str | null` to `PropertyResponse`. These fields are computed via a LEFT JOIN to `listing_instructions` on the most recent relevant event. They are populated only when `current_user` is the listing creator (agent or agency_owner who created it). For all other actors, these fields are absent or null. Implement as a server-side computation in the CRUD layer — no separate endpoint call required for tab rendering.

Add `POST /api/v1/properties/{id}/instruct/` endpoint:
- Role gate: `agency_owner` whose `agency_id` matches the listing's `agency_id`
- Accepted states: listing must be at `revoked` or `admin_rejected`
- Payload: `instruction_text: str` (non-empty, required)
- Writes: `listing_instructions` row with `triggered_by_event_id` set to the most recent `listing_events` row where `to_status IN ('revoked', 'admin_rejected')` for this listing
- Writes: `listing_events` row with `from_status = current_status`, `to_status = current_status`, `reason = 'Agency instruction written'` (status does not change — this is a communication event, not a transition)
- Returns: updated `PropertyResponse`

Update the agent's edit CTA gate on `revoked` and `admin_rejected` listings. Currently agents can edit `admin_rejected` listings directly (Phase M behaviour). After N.1, the CRUD layer enforces: `PATCH /properties/{id}/` (edit) and `PATCH /properties/{id}/resubmit/` on a `revoked` or `admin_rejected` listing must confirm `has_instruction = true` before proceeding. If no instruction, return 422 with `detail: "Await agency instruction before resubmitting."`.

Add `GET /api/v1/properties/{id}/instructions/` endpoint:
- Returns all `listing_instructions` rows for this listing, ordered by `created_at` ascending
- Role gate: creator (own listing), agency_owner (own agency), admin (all)
- Used by the history/audit view, not for CTA gating (that is covered by `has_instruction` in PropertyResponse)

pyright 0, pytest ≥ 95% after every endpoint added.

**Done-when:** pyright 0, pytest ≥ 95%. Agency owner can POST an instruction to a revoked listing. Agent's `PropertyResponse` includes `has_instruction: true` and `instruction_text` after instruction is written. Agent's PATCH edit on a revoked listing without an instruction returns 422. With an instruction, edit proceeds. `listing_instructions` table exists in production with RLS enabled.

---

### N.2 — Backend: Missing State Machine Endpoints and Transitions

Goal: close DEF-N-ENDPOINTS-001 and DEF-N-TRANSITIONS-001. All read endpoints and the permanent rejection transition are live.

**Tasks (DEF-N-ENDPOINTS-001):**

`GET /api/v1/properties/agency-queue/`
- Returns: listings where `moderation_status = 'agency_review'` AND `agency_id = current_user.agency_id`
- Role gate: `agency_owner` only
- Pagination: page/page_size, default 20, cap 100
- Same response shape as existing property list endpoints

`GET /api/v1/properties/agency-inventory/`
- Returns: listings where `moderation_status = 'live'` AND `agency_id = current_user.agency_id`
- Role gate: `agent` or `agency_owner` with active membership in that agency
- Pagination: same as above

`GET /api/v1/properties/pending-admin/`
- Returns: listings where `moderation_status = 'admin_review'` AND `agency_id = current_user.agency_id`
- Role gate: `agency_owner` only
- Pagination: same as above

**Tasks (DEF-N-TRANSITIONS-001):**

`PATCH /api/v1/properties/{id}/reject-permanent/`
- Role gate: `admin` only
- Accepted state: `revoked`
- Transition: `revoked → admin_rejected`
- Requires: `reason` field (non-empty)
- Writes: `listing_events` row with reason
- Returns: updated `PropertyResponse`

Note: the standard `admin_rejected` mediation rules from N.1 then apply — agency must instruct before agent can act.

pyright 0, pytest ≥ 95%.

**Done-when:** All three read endpoints return correct scoped results. `PATCH /reject-permanent/` transitions a `revoked` listing to `admin_rejected` and writes the event. Wrong-role attempts return 403. Wrong-state attempts return 422 from the transition guard.

---

### N.3 — Backend: Admin Historical Tab Endpoints

Goal: admin Revoked and Rejected tabs query historical records rather than current-state snapshots.

**Tasks:**

Add `GET /api/v1/admin/properties/revocation-history/` endpoint:
- Returns: all listings where `listing_events` contains at least one row with `to_status = 'revoked'`, regardless of current `moderation_status`
- Join to `listing_events` to include: `revoked_at` (timestamp of most recent revocation event), `revocation_reason` (reason from that event), `revoked_by_actor_id`
- Include current `moderation_status` on each listing — this is the field from which frontend derives the CTA
- Include `has_instruction: bool` — true if a `listing_instructions` row exists referencing the most recent revocation event
- Order by most recent revocation event descending
- Pagination: page/page_size, default 20, cap 100
- Role gate: admin only

Add `GET /api/v1/admin/properties/rejection-history/`
- Same pattern but for `to_status = 'admin_rejected'`
- Includes `rejected_at`, `rejection_reason`, `has_instruction`, current `moderation_status`
- Role gate: admin only

Both endpoints must perform efficiently. Use a subquery or window function to identify the most recent relevant event per listing — do not issue N queries for N listings.

Confirm with EXPLAIN ANALYZE that query cost is bounded regardless of listing count.

pyright 0, pytest ≥ 95%.

**Done-when:** `GET /revocation-history/` returns all listings ever revoked with their current status and revocation metadata. A listing that was revoked, went through the chain, and returned to live appears in this endpoint with `moderation_status: 'live'`. EXPLAIN ANALYZE confirms no N+1. Same for rejection-history.

---

### N.4 — Backend: Notification Wiring (DEF-N-NOTIFICATIONS-001)

Goal: agents know when their listing enters the agency queue. Agency owners know when their queue grows. Agents know when an instruction has been written for them. All emails are fail-open.

**Tasks:**

`submission_notification_email` task — fires on `PATCH /submit-for-review/`:
- To: agency owner of the listing's agency
- Subject: New listing submitted for review — [property title]
- Body: agent name, property title, link to `/account/agency` (agency queue tab), submission timestamp

`agency_approval_notification_email` task — fires on `PATCH /agency-approve/`:
- To: admin (platform notification — use a configured `ADMIN_NOTIFICATION_EMAIL` env var)
- Subject: Listing ready for platform review — [property title]
- Body: agency name, property title, link to admin moderation queue

`instruction_notification_email` task — fires on `POST /instruct/`:
- To: listing agent (creator)
- Subject: Agency instruction on your listing — [property title]
- Body: instruction text verbatim, agency owner name, link to `/account/listings` (revoked/rejected tab)

All three tasks follow the existing Resend/email_tasks pattern. Fail-open: email failure never blocks the primary endpoint action. Test coverage ≥ 80% per task.

Confirm existing email tasks from Phase M are still wired and firing:
- `agency_rejected` → agent email (rejection reason)
- `admin_review → live` → agent email
- `admin_review → admin_rejected` → agent + agency owner email
- `live → revoked` → agent + agency owner email

If any of the Phase M email wires are disconnected, reconnect before adding N.4 tasks.

pyright 0, pytest ≥ 95%.

**Done-when:** Agent submits listing → agency owner receives email within 60 seconds. Agency approves → admin notification email fires. Agency writes instruction → agent receives email with instruction text. All three confirmed via Resend dashboard. Email failure returns 200 from primary endpoint.

---

### N.5 — Frontend: Creator vs Agency Name Display

Goal: every listing card across all dashboard tabs shows the correct display name derived from the listing's current `moderation_status`. No hardcoded per-tab logic.

**Tasks:**

Create `src/lib/listing-display.ts` (or equivalent shared utility):

```ts
import type { ModerationStatus } from '@/types/api.generated'

const AGENCY_NAME_STATES = new Set<ModerationStatus>([
  'admin_review',
  'admin_rejected',
  'live',
  'revoked',
])

export const resolveListingDisplayName = (
  status: ModerationStatus,
  ownerDisplayName: string | null | undefined,
  agencyName: string | null | undefined,
): string => {
  if (AGENCY_NAME_STATES.has(status)) {
    return agencyName ?? 'Agency'
  }
  return ownerDisplayName ?? 'Agent'
}
```

Audit every component that renders a listing card name across all dashboard tabs:
- Agent: Drafts, Under Review, Rejected, Live, Agency Inventory, Public Marketplace
- Agency owner: Drafts, Agency Queue, Pending Admin, Rejected, Verified Inventory, Public Marketplace
- Admin: Review Queue, Live, Rejected, Revoked, All

Replace every inline name resolution with a call to `resolveListingDisplayName(listing.moderation_status, listing.owner_display_name, listing.agency_name)`.

Run: `grep -r "owner_display_name\|agency_name" src/` — every occurrence must go through this utility, not be inlined.

`pnpm gen:types` after N.1 backend changes deploy (has_instruction field will appear in generated types).

tsc 0, lint 0, build 0 before push.

**Done-when:** A listing at `draft` shows the creator's name in the agent Drafts tab. The same listing at `live` shows the agency name in the agent Live tab. Changing the status in the database and refreshing the dashboard reflects the correct name. No tab-specific name logic anywhere in the codebase.

---

### N.6 — Frontend: Agent Tab Cache Invalidation Fix

Goal: when admin or agency owner mutates a listing's state, the agent's dashboard tabs reflect the change without requiring a page reload or manual refresh.

**Root cause:** TanStack Query cache invalidation after mutations is scoped to the acting user's query keys. When admin revokes a listing, the admin's cache is invalidated, but the agent's cached queries for `live`, `agency-inventory`, and `marketplace` tabs are unaware and remain stale.

**Fix — broaden invalidation scope:**

After any successful mutation on a listing (any PATCH to a lifecycle endpoint), the invalidation must cover all query keys that could reference that listing:

```ts
// After any successful moderation mutation:
await queryClient.invalidateQueries({ queryKey: ['properties'] })
await queryClient.invalidateQueries({ queryKey: ['agency-inventory'] })
await queryClient.invalidateQueries({ queryKey: ['agency-queue'] })
await queryClient.invalidateQueries({ queryKey: ['pending-admin'] })
await queryClient.invalidateQueries({ queryKey: ['admin-properties'] })
```

This is a deliberate over-invalidation. The queries will refetch on next access, ensuring correctness across all actor perspectives. TanStack Query will not re-fetch queries that are not currently mounted — this only triggers refetches for tabs the user currently has open.

Additionally, for the agent dashboard: the stale-time on listing tab queries must be set low enough that returning to a tab after another actor's mutation does not serve a stale cache. Set `staleTime: 30_000` (30 seconds) on all listing tab queries. This bounds the maximum staleness when cross-actor mutations happen.

tsc 0, lint 0, build 0 before push.

**Done-when:** Admin revokes one of three live listings. Agent's Live tab, Agency Inventory tab, and Public Marketplace tab all show two listings after next navigation to those tabs — without a page reload. Agency owner's live inventory count also correct. No count discrepancy between any two actor perspectives on the same data.

---

### N.7 — Frontend: Mediation UI — Agent, Agency Owner, Admin

Goal: the instruction mediation flow is fully surfaced in all three actor dashboards. Agents see ambient state messages and unlocked CTAs after instruction. Agency owners can write instructions. Admin historical tabs are omniscient.

**Depends on:** N.1 and N.3 live on Railway. `pnpm gen:types` run after N.1 deploys.

**Agent — Revoked and Rejected tab cards:**

When `moderation_status` is `revoked` or `admin_rejected`, the listing card renders in two states:

State A — `has_instruction: false`:
- Status chip: "Revoked" or "Admin rejected"
- Body copy: "Your listing has been reviewed by the platform. Your agency will provide further instructions."
- No action CTAs visible. No Edit, no Resubmit, no Delete.
- The card is read-only. This is deliberate — do not add escape hatches.

State B — `has_instruction: true`:
- Status chip: "Revoked — instruction received" or "Rejected — instruction received"
- Instruction box: renders `instruction_text` in a visually distinct container (e.g. a bordered card or alert block) labeled "From your agency:"
- CTAs: Edit (navigates to listing edit form) and Delete (confirmation dialog required). If `moderation_status = agency_rejected` or after resubmission paths where applicable, Resubmit is also shown.
- On Edit: listing enters `draft` state (existing Phase M behaviour — edit resets to draft). The card should disappear from the Revoked/Rejected tab and appear in Drafts.

**Agency Owner — Revoked tab:**

The Revoked tab currently shows listings at `moderation_status = 'revoked'`. Keep this as a current-state view for the agency owner — they only need to see what is currently in their queue. This is different from admin (who needs the historical view).

For each listing in the agency Revoked tab:
- Status chip: "Revoked by admin"
- Show admin's revocation reason (available from the listing's most recent `listing_events` row with `to_status = 'revoked'` — fetch via `GET /properties/{id}/instructions/` or include reason in PropertyResponse)
- Buttons:
  - "Instruct agent" — opens a `Sheet` or `AlertDialog` with a required text area. Submit calls `POST /api/v1/properties/{id}/instruct/`. On success: the card updates to show "Instruction sent" and the Instruct button disables.
  - "View listing" — navigates to the listing detail page (account-scoped view, not public)

Note: revocation reason from admin must be surfaced to the agency owner. If `PropertyResponse` does not currently include the most recent event reason, add `latest_event_reason: str | null` to the response for agency owner and admin roles.

**Admin — Revoked and Rejected tabs (historical):**

Switch the admin Revoked tab query from `?moderation_status=revoked` to `GET /api/v1/admin/properties/revocation-history/` (from N.3).

Switch the admin Rejected tab query from `?moderation_status=admin_rejected` to `GET /api/v1/admin/properties/rejection-history/` (from N.3).

For each listing in either historical tab, CTA is derived from `current_moderation_status` per the derivation map in Section 1.6:

```ts
const getRevocationCta = (status: ModerationStatus, hasInstruction: boolean) => {
  if (status === 'revoked' && !hasInstruction) return { label: 'Restore', action: 'restore' }
  if (status === 'revoked' && hasInstruction) return { label: 'Awaiting agent action', action: null }
  if (['draft', 'agency_review', 'admin_review'].includes(status)) return { label: 'In progress', action: null }
  if (status === 'live') return { label: 'Restored', action: null }
  if (status === 'admin_rejected') return { label: 'Rejected', action: null }
  return { label: status, action: null }
}
```

Admin does not manually update the Revoked tab to reflect restoration. The tab re-derives CTA from current status on every load.

tsc 0, lint 0, build 0 before push.

**Done-when:** Agent sees ambient message on revoked listing with no CTAs. After agency writes instruction, agent refreshes and sees instruction text with Edit and Delete CTAs. Agency owner sees Instruct and View buttons on revoked listings. After instruction, Instruct button shows "Instruction sent". Admin Revoked tab shows a listing that has since gone live with "Restored" label instead of "Restore" button. Admin Rejected tab shows same historical pattern.

---

### N.8 — Frontend + Backend: In-Platform Notifications (DEF-M-NOTIF-001)

Goal: every actor has a notification bell in the nav that surfaces actionable events without requiring dashboard polling. MVP scope: badge count + notification list. Real-time push is Phase O.

This section is parallel-able with N.5 and N.6 and does not block N.9 if the MVP scope is met. If N.8 scope proves too large for this phase, the done-when criteria can be moved to Phase O with DEFERRED.md documentation.

**Backend tasks:**

Alembic migration: CREATE TABLE notifications:
```
notifications
  notification_id    BIGINT GENERATED ALWAYS AS IDENTITY (PK)
  user_id            BIGINT FK → users.user_id NOT NULL
  event_type         TEXT NOT NULL  (e.g. 'listing_submitted', 'agency_approved', 'instruction_received', 'listing_live', 'listing_revoked', 'listing_rejected')
  listing_id         BIGINT FK → properties.property_id NULL
  body_text          TEXT NOT NULL
  is_read            BOOLEAN NOT NULL DEFAULT false
  created_at         TIMESTAMPTZ DEFAULT now()
```

RLS: users see only their own notifications.

`GET /api/v1/notifications/` — returns unread notifications for current user, ordered by `created_at` descending. Pagination: default 20, cap 50.

`PATCH /api/v1/notifications/{id}/read/` — marks a single notification as read.

`PATCH /api/v1/notifications/read-all/` — marks all as read.

`GET /api/v1/notifications/unread-count/` — returns `{ count: int }`. Used for badge count in nav. Must be fast — no joins beyond the notifications table itself.

Write a notification row in the same transaction as each state transition event. Follow the same fail-open pattern as email tasks — a notification write failure must not block the primary action. Notifications to create:

```
Transition                      Recipient           event_type
draft → agency_review           agency_owner        listing_submitted
agency_review → admin_review    admin               listing_agency_approved
agency_review → agency_rejected agent               listing_agency_rejected
admin_review → live             agent               listing_live
admin_review → admin_rejected   agent + agency_owner listing_admin_rejected
live → revoked                  agent + agency_owner listing_revoked
POST /instruct/                 agent               instruction_received
```

pyright 0, pytest ≥ 95%.

**Frontend tasks:**

Add notification bell icon to nav (public top nav, visible when logged in). Badge shows unread count from `GET /notifications/unread-count/`. Poll every 60 seconds with TanStack Query `refetchInterval: 60_000`. On badge click: open a dropdown or drawer with the notification list from `GET /notifications/`.

Notification list item: body_text, relative timestamp (e.g. "2 hours ago"), link to relevant page (the listing detail or dashboard tab). Clicking an item marks it read (`PATCH /{id}/read/`) and navigates to the link.

"Mark all read" action in the notification dropdown calls `PATCH /notifications/read-all/`.

Empty state: "You're up to date." — no notification count badge when unread count is 0.

tsc 0, lint 0, build 0 before push.

**Done-when (MVP):** Logged-in agent sees unread badge increment after admin approves their listing. Clicking bell shows the notification with body text and link. Clicking notification marks it read and badge decrements. "Mark all read" clears badge. Notification is written in the same transaction as the state transition — no orphaned transitions without notifications.

---

### N.9 — Integration Validation and Phase N Exit

Goal: the full mediation lifecycle works end to end without SQL. All 12 original journeys still pass. Notification bell is functional.

**Tasks:**

Walk the full mediation lifecycle using real production accounts:

1. Agent creates listing (Drafts tab — creator name shown)
2. Agent submits for review (agency owner receives submission email and notification)
3. Agency owner approves (admin receives notification, listing moves to admin_review — agency name now shown)
4. Admin approves — listing goes live. Agent receives live email and notification.
5. Admin revokes listing with reason. Agent and agency owner receive revocation email and notification.
6. Agent sees revoked listing in Revoked tab — ambient message only, no CTAs.
7. Agency owner sees listing in agency Revoked tab — Instruct + View buttons visible.
8. Agency owner writes instruction. Agent receives instruction email and notification. CTAs unlock.
9. Agent edits listing. Listing enters draft.
10. Agent resubmits through full chain: agency_review → admin_review → live.
11. Admin Revoked tab shows the listing with "Restored" label throughout step 10 and after step 10 completes.
12. listing_events table has a complete immutable record of every transition throughout steps 1–10.

Walk all 12 original journeys from Phase D.

Run `pnpm gen:types` — confirm `has_instruction` and `instruction_text` are in generated types.

`pnpm tsc --noEmit` → 0 errors.
`pnpm lint` → 0 warnings.
`pnpm build` → 0 warnings.
`pyright` → 0 errors.
`pytest --cov` → all passing, ≥ 95%.

Update DEFERRED.md — all Phase N items closed or promoted to Phase O.
Update all CLAUDE.md files with Phase N closed state and commit to both repos.

**Done-when:** Full mediation lifecycle completes via UI with no SQL. Admin Revoked tab shows historical record throughout. All 12 original journeys pass. listing_events has complete record. CI green across both repos. CLAUDE.md committed.

---

## 3. Phase N Exit Criteria

| Criterion | Verification |
|---|---|
| listing_instructions table exists with RLS, append-only | SQL query confirms table, policies, trigger |
| Agency owner can instruct on revoked listing | POST /instruct/ returns 200, row in listing_instructions |
| Agent CTA locked on revoked with no instruction | PATCH edit returns 422 without instruction |
| Agent CTA unlocked on revoked after instruction | PATCH edit proceeds after instruction written |
| has_instruction and instruction_text in PropertyResponse for creator | pnpm gen:types confirms fields, curl confirms values |
| agency-queue, agency-inventory, pending-admin read endpoints live | GET each — correct scoped results |
| revoked → admin_rejected endpoint live | PATCH /reject-permanent/ transitions correctly |
| Admin revocation-history and rejection-history endpoints | GET each — historically-revoked/rejected listings returned |
| Submission email fires on agent submit | Agency owner receives email within 60s |
| Agency approval email fires on agency approve | Admin notification email fires |
| Instruction email fires on agency instruct | Agent receives instruction email with text |
| Creator vs agency name display correct across all tabs | Listings at draft show creator name, listings at live show agency name |
| Agent tab cache invalidates after remote mutation | Admin revokes → agent Live tab count correct without page reload |
| Agent Revoked tab: ambient message, no CTAs | Visual check as agent with revoked listing |
| Agent Revoked tab: CTAs unlock after instruction | Visual check as agent after agency writes instruction |
| Agency Revoked tab: Instruct + View buttons | Visual check as agency owner |
| Admin Revoked tab: historical, CTA derived from current status | Revoked-then-restored listing shows "Restored" |
| Admin Rejected tab: historical view | Rejected-then-resolved listing shows correct derived CTA |
| Notification bell in nav, badge count live | Badge increments on new notification |
| Notification list shows events with links | Click notification → marks read → navigates |
| Full mediation lifecycle via UI — no SQL | Complete walkthrough per N.9 |
| listing_events complete record for lifecycle walk | SELECT COUNT from listing_events after walk |
| All 12 original journeys passing | Manual walkthrough |
| tsc → 0 | pnpm tsc --noEmit |
| pyright → 0 | venv pyright |
| pytest ≥ 95% | pytest --cov gate |
| pnpm build → 0 warnings | Next.js production build |
| DEFERRED.md updated | All Phase N items closed or promoted |
| All CLAUDE.md files committed | Root, frontend, backend — Phase N closed state |

---

## 4. Execution Sequence

| # | Task | Dependency | Parallel? |
|---|---|---|---|
| 1 | N.1 — listing_instructions + mediation endpoints | None — start immediately | No — N.7 and N.5 depend on it |
| 2 | N.2 — Missing endpoints and transitions | None | Yes, parallel with N.1 |
| 3 | N.3 — Admin historical tab endpoints | N.1 closed | No — N.7 admin section depends on it |
| 4 | N.4 — Notification email wiring | N.1 closed | Yes, parallel with N.3 |
| 5 | N.5 — Creator vs agency name | N.1 live (gen:types run) | Yes, parallel with N.6 |
| 6 | N.6 — Cache invalidation fix | None | Yes, parallel with N.5 |
| 7 | N.7 — Mediation UI | N.1 + N.3 live, gen:types run | No — depends on backend N.1/N.3 |
| 8 | N.8 — In-platform notifications | N.4 in progress | Yes, parallel with N.7 |
| 9 | N.9 — Integration validation and exit | N.1 through N.8 all closed | No — final gate |

Backend stream (N.1, N.2, N.3, N.4) dispatches first. Frontend stream (N.5, N.6, N.7, N.8) dispatches after N.1 is confirmed live on Railway and `pnpm gen:types` is run.

---

## 5. Items Deferred to Phase O

| Item | Rationale |
|---|---|
| Real-time push notifications (WebSocket / SSE) | Phase N implements poll-based badge count at 60s interval. Real-time push requires infrastructure additions (Redis pub/sub, Supabase Realtime, or SSE). Defer until notification volume validates the investment. |
| Notification frequency preference (immediate vs digest) | Saved search emails default to immediate. Seeker preference UI is Phase O. |
| In-app messaging / inquiry reply threads | Lead capture is MVP. Reply thread model requires its own data model. |
| TBT < 100ms | Revised target 300ms met. 100ms requires RSC migration. Phase O after traffic data. |
| Agency N+1 on public directory | Public agency cards compute stats per card. Phase O after traffic data sizes the optimisation. |
| Advanced map view (Mapbox) | Leaflet/OSM sufficient for current scale. |
| Nominatim self-hosted instance | Public API sufficient at current scale. |
| Audit log retention (DEF-002) | Assess after 60 days of real traffic from first live listings. |
| Custom domain setup (DEF-H-DOMAIN) | Operational task — no code changes. |
| Saved search notification frequency preference | Phase O. |
| DEF-J-EMAIL-DOMAIN-001 | Operator action: register domain, update MAIL_FROM in Railway. No code changes needed. Must be done before real users receive email. |

---

## 6. Production Reference

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

### Final Phase M HEADs

| Repo | Commit |
|---|---|
| Backend (realtornet) | 13ae557 |
| Frontend (realtornet-web) | 04dfa8a |

---

## 7. Session Opening Template

Use this as the opening prompt for every Phase N session.

> "Continuing RealtorNet Phase N from [N.X]. Phase M closed June 14 2026 — seven-state listing governance system live, listing_events writing on every transition, owner_display_name in PropertyResponse, gates green. Backend pyright 0, coverage 96.15%, commit 13ae557 on Railway (realtornet-production.up.railway.app). Frontend tsc 0, lint 0, build 0, commit 04dfa8a on Vercel (realtornet-web.vercel.app). Production Supabase fobvnshrqxduuhzgflvd. Staging avkhpachzsbgmbnkfnhu. Dev umhtnqxdvffpifqbdtjs — do not use.
>
> Four roles: seeker / agent / agency_owner / admin. Moderation enum: draft / agency_review / agency_rejected / admin_review / admin_rejected / live / revoked.
>
> Governing decision for Phase N: the instruction mediation model is the centrepiece. When admin enforces (revokes or rejects), the agency mediates the agent's response pathway via listing_instructions. Agents cannot act on revoked or admin_rejected listings until their agency instructs them. Admin Revoked and Rejected tabs are historical views, not current-state filters. CTA is derived from current moderation_status. Read Sections 1.1 through 1.7 of the Phase N workbook before any N.1, N.3, or N.7 work begins.
>
> Today's task: [SPECIFIC TASK FROM PHASE N BACKLOG — dispatch N.1 and N.2 to backend agent first].
>
> Attach Phase N workbook, PREFLIGHT.md, DEFERRED.md, and all CLAUDE.md files."

---

*RealtorNet — Phase N Workbook v1.0*
*Derived from Phase M close state | Backend commit 13ae557 | Frontend commit 04dfa8a*
