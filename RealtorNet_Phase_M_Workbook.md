# RealtorNet — Phase M Workbook
## Listing Governance System

**Phase L closed:** June 2026 — infrastructure migrated, staging live, moderation backend and frontend complete, CLAUDE.md committed
**Backend version:** v0.5.3+ — 95%+ coverage, 0 Pyright errors
**Frontend version:** Next.js — deployed to Vercel
**Stack (locked):** Next.js · TypeScript · Supabase · TanStack Query · FastAPI · Resend email
**Deploy targets:** Vercel (frontend) · Railway (backend) · Supabase (DB + Auth)
**Production Supabase:** `fobvnshrqxduuhzgflvd` 
**Staging Supabase:** `avkhpachzsbgmbnkfnhu` 
**Phase M opens:** June 2026

---

## 0. Governing Principle

Phase M builds the listing governance system — the full end-to-end lifecycle through which a property moves from a private draft to public visibility across three actor types and seven states. Every dashboard tab, every CTA, and every permission check is derived from a single authoritative state machine. Tabs are filters on state. State is the only source of truth.

---

## 1. The Canonical Listing State Machine

This is the design specification for Phase M. Read it before any implementation begins. All backend migrations, endpoint designs, frontend tabs, and permission rules derive from this model.

### 1.1 States

```
draft
  The listing exists only for the creator. Nothing has been submitted.
  Not visible to agency, admin, or public.

agency_review
  Agent submitted the listing for agency approval.
  Visible to agent (creator) and agency owner only.
  Editing is locked — agent must Withdraw to edit.

agency_rejected
  Agency owner rejected with a reason.
  Visible to agent and agency owner only.
  Agent can edit and resubmit, or delete.

admin_review
  Agency approved. Listing is in admin moderation queue.
  Visible to agent, agency owner, and admin. Not public.

admin_rejected
  Admin rejected with a reason.
  Visible to agent, agency owner, and admin. Not public.
  Agent must edit — listing returns to draft. Full chain required on resubmit.

live
  Admin approved. Publicly visible on /properties/ and all agency inventory views.
  Visible to everyone including anonymous visitors.

revoked
  Admin removed from public view.
  Visible to agent, agency owner, and admin only.
  Listing is preserved — nothing is deleted.
```

### 1.2 Legal state transitions

```
draft → agency_review          (agent: Submit for Review)
draft → admin_review           (agency owner own listing: Submit to Admin)

agency_review → agency_rejected    (agency owner: Reject)
agency_review → admin_review       (agency owner: Approve)
agency_review → draft              (agent: Withdraw)

agency_rejected → agency_review    (agent: Resubmit)
agency_rejected → [deleted]        (agent: Delete)

admin_review → admin_rejected      (admin: Reject)
admin_review → live                (admin: Approve)
admin_review → agency_review       (agency owner: Recall)

admin_rejected → draft             (agent: Edit — full chain required on resubmit)
admin_rejected → admin_review      (admin: Reinstate)

live → revoked                     (admin: Revoke)

revoked → live                     (admin: Restore)
revoked → admin_rejected           (admin: Reject permanently)
```

Agency owner bypass: Agency owner's own listings skip `agency_review` entirely. DRAFT → ADMIN_REVIEW via "Submit to Admin". An agency owner cannot peer-review their own listing. No `agency_approved` intermediate step.

### 1.3 Visibility matrix

```
State             Agent(creator)  Agency owner  Admin  Public
draft             yes             no            no     no
agency_review     yes             yes           no     no
agency_rejected   yes             yes           no     no
admin_review      yes             yes           yes    no
admin_rejected    yes             yes           yes    no
live              yes             yes           yes    yes
revoked           yes             yes           yes    no
```

### 1.4 Transition authority matrix

```
State             Agent              Agency owner          Admin
draft             edit, submit,      edit, submit to       —
                  delete             admin, delete
agency_review     withdraw           approve, reject       —
agency_rejected   edit, resubmit,    view                  —
                  delete
admin_review      view               recall                approve, reject
admin_rejected    edit (→draft)      view                  reinstate
live              view               view                  revoke
revoked           view               view                  restore, reject permanently
```

### 1.5 Tab mapping per actor

**Agent — My Listings (6 views)**

```
1. Drafts
   Source: own listings where status = draft
   CTAs: Edit · Submit for Review · Delete

2. Under Review
   Source: own listings where status IN (agency_review, admin_review)
   Per-listing chip: "Awaiting agency review" or "Awaiting admin review"
   CTAs: Withdraw (only if status = agency_review)

3. Rejected
   Source: own listings where status IN (agency_rejected, admin_rejected)
   Per-listing chip: who rejected (Agency or Admin) and reason text
   CTAs: Edit · Resubmit · Delete

4. Live
   Source: own listings where status = live
   CTAs: View Listing

5. Agency Inventory  [market awareness — read only]
   Source: all listings where agency_id = agent's agency AND status = live
   Shows other agents' verified listings within the same agency
   CTAs: View

6. Public Marketplace  [market awareness — read only]
   Source: all listings where status = live, ordered by agency
   Shows verified inventory across all agencies on the platform
   CTAs: View
```

**Agency Owner — My Listings (6 views)**

```
1. Drafts
   Source: own listings where status = draft
   CTAs: Edit · Submit to Admin · Delete
   Note: "Submit to Admin" replaces "Submit for Review" — agency owner bypasses agency step

2. Agency Queue  [operational inbox]
   Source: all agency listings where status = agency_review
   Shows listings from agents who have submitted for approval
   CTAs: Approve · Reject (requires reason)

3. Pending Admin
   Source: all agency listings where status = admin_review
   Informational — shows what is waiting for platform decision
   Per-listing chip: "Awaiting admin review"
   CTAs: Recall (returns listing to agency_review)

4. Rejected
   Source: own listings where status = agency_rejected OR admin_rejected
   Also shows agent listings where status = admin_rejected (so agency owner is aware)
   Per-listing chip: "Agency rejected" or "Admin rejected"
   CTAs: View (for admin-rejected agent listings — agent must act)
         Edit · Resubmit (own admin-rejected listings)

5. Verified Inventory
   Source: all agency listings where status = live
   CTAs: View Listing

6. Public Marketplace  [same as agent market awareness view]
   Source: all listings where status = live, ordered by agency
   CTAs: View
```

**Admin — Moderation (5 views, already partially built)**

```
1. Review Queue
   Source: all listings where status = admin_review
   CTAs: Approve · Reject (requires reason)
   Badge: count of pending items

2. Live
   Source: all listings where status = live
   CTAs: Revoke (requires reason)

3. Rejected
   Source: all listings where status = admin_rejected
   CTAs: Reinstate · Approve directly

4. Revoked
   Source: all listings where status = revoked
   CTAs: Restore · Reject permanently

5. All
   Source: all listings regardless of status (audit view)
   Read-only with full status history
```

### 1.6 Badge and signal system

Every state transition recomputes badge counts for affected actor dashboards. No real-time websocket required for MVP — badge counts are computed on page load and after any mutation via TanStack Query cache invalidation.

```
draft → agency_review:
  Agency owner's "Agency Queue" tab badge increments

agency_review → admin_review:
  Admin's "Review Queue" tab badge increments
  Agent's per-listing chip changes to "Awaiting admin review"

admin_review → live:
  Agent receives email: "Your listing is now live"
  Agency owner sees listing appear in Verified Inventory

admin_review → admin_rejected:
  Agent receives email with rejection reason
  Agent's "Rejected" tab badge increments

live → revoked:
  Agent and agency owner receive email with reason
  Listing disappears from /properties/ immediately

agency_review → agency_rejected:
  Agent receives email with rejection reason
  Agent's "Rejected" tab badge increments
```

### 1.7 listing_events table (new — event sourcing)

Every state transition writes an immutable append-only row. Same pattern as `agent_membership_audit`.

```
listing_events
  event_id          BIGINT GENERATED ALWAYS AS IDENTITY (PK)
  listing_id        BIGINT FK → properties.property_id
  actor_id          BIGINT FK → users.user_id
  from_status       moderation_status_enum NULL
  to_status         moderation_status_enum NOT NULL
  reason            TEXT NULL
  created_at        TIMESTAMPTZ DEFAULT now()
```

Never update or delete. No trigger needed for this — write in the same transaction as the status update. RLS: agents see own listing events, agency owners see own agency's events, admin sees all.

---

## 2. Phase M Work Plan

### M.1 — Backend: New Enum Values and listing_events Table

Goal: database ready for the full state machine. No frontend work begins until M.1 is closed.

**Tasks:**

Add new enum values via Alembic migration:
```
ALTER TYPE moderation_status_enum ADD VALUE 'draft' BEFORE 'pending_review';
ALTER TYPE moderation_status_enum ADD VALUE 'agency_review' AFTER 'draft';
ALTER TYPE moderation_status_enum ADD VALUE 'agency_rejected' AFTER 'agency_review';
ALTER TYPE moderation_status_enum ADD VALUE 'admin_review' AFTER 'agency_rejected';
ALTER TYPE moderation_status_enum ADD VALUE 'admin_rejected' AFTER 'admin_review';
```

Rename `verified` to `live` is NOT safe in production with an ALTER — instead add `live` as a new value and update references in code. Existing `pending_review`, `agency_approved`, `verified` values remain in the enum for backwards compatibility until a data migration confirms zero rows use them. Since there are no real listings in production this is a clean slate — but the migration must be written safely regardless.

Create `listing_events` table via Alembic with schema from Section 1.7. RLS enabled on creation.

Change the default `moderation_status` on property creation from `pending_review` to `draft`.

Update the `PropertyResponse` serializer to include `moderation_status` using the full new enum vocabulary.

Run `pnpm gen:types` on frontend after this migration deploys.

**Done-when:** pyright 0, pytest ≥ 95%. New enum values visible in OpenAPI schema. `GET /api/v1/properties/` response includes `moderation_status` with `draft` as the value for a newly created listing. `listing_events` table exists in production with RLS enabled. No existing data corrupted.

---

### M.2 — Backend: Listing Lifecycle Endpoints

Goal: every legal state transition from Section 1.2 has an endpoint. All endpoints enforce the transition authority matrix.

**Endpoints to add or update:**

```
PATCH /api/v1/properties/{id}/submit-for-review/
  Role: agent who owns the listing
  Transition: draft → agency_review
  Writes: listing_events row

PATCH /api/v1/properties/{id}/submit-to-admin/
  Role: agency_owner whose agency_id matches listing agency_id
  Transition: draft → admin_review (agency owner bypass)
  Writes: listing_events row

PATCH /api/v1/properties/{id}/agency-approve/
  Role: agency_owner whose agency_id matches listing agency_id
  Transition: agency_review → admin_review
  Already exists — update to use new enum values and write listing_events

PATCH /api/v1/properties/{id}/agency-reject/
  Role: agency_owner whose agency_id matches listing agency_id
  Transition: agency_review → agency_rejected
  Already exists — update to require reason field, write listing_events

PATCH /api/v1/properties/{id}/withdraw/
  Role: agent who owns the listing
  Transition: agency_review → draft
  Writes: listing_events row

PATCH /api/v1/properties/{id}/resubmit/
  Role: agent who owns the listing
  Transition: agency_rejected → agency_review
  Writes: listing_events row

PATCH /api/v1/properties/{id}/recall/
  Role: agency_owner whose agency_id matches listing agency_id
  Transition: admin_review → agency_review
  Writes: listing_events row

PATCH /api/v1/properties/{id}/verify/
  Existing endpoint — update: only accepts listings at admin_review
  Transition: admin_review → live
  Write listing_events row

PATCH /api/v1/properties/{id}/admin-reject/
  Role: admin
  Transition: admin_review → admin_rejected
  Requires reason field
  Writes: listing_events row

PATCH /api/v1/properties/{id}/reinstate/
  Role: admin
  Transition: admin_rejected → admin_review
  Writes: listing_events row

PATCH /api/v1/properties/{id}/revoke/
  Already exists — update to write listing_events row, require reason

PATCH /api/v1/properties/{id}/restore/
  Role: admin
  Transition: revoked → live
  Writes: listing_events row
```

Update all property list queries to enforce visibility per Section 1.3. A listing at `draft` must never appear in any query unless the requesting user is the creator.

Add read endpoints for tab data sources:

```
GET /api/v1/properties/agency-inventory/
  Returns: live listings where agency_id = requesting user's agency_id
  Role: agent or agency_owner with active agency membership

GET /api/v1/properties/agency-queue/
  Returns: agency_review listings for requesting agency_owner's agency
  Role: agency_owner only

GET /api/v1/properties/pending-admin/
  Returns: admin_review listings for requesting agency_owner's agency
  Role: agency_owner only

GET /api/v1/properties/events/{listing_id}/
  Returns: listing_events for a given listing
  Role: creator (own listing), agency_owner (own agency), admin (all)
```

**Done-when:** pyright 0, pytest ≥ 95%. Every legal transition can be executed via API call with appropriate credentials. Every illegal transition returns 403 or 422. A full listing lifecycle (create → submit → agency approve → admin approve → live → revoke → restore) can be walked via API calls without any SQL. listing_events rows are written on every transition.

---

### M.3 — Frontend: Agent My Listings Dashboard

Goal: agent's My Listings page has the correct tab structure derived from Section 1.5. All CTAs call the correct endpoints from M.2.

**Tasks:**

Run `pnpm gen:types` first after M.2 is live on Railway.

Implement or restructure the My Listings page to have the following tabs in order: Drafts, Under Review, Rejected, Live, Agency Inventory, Public Marketplace.

Each tab is a TanStack Query hook fetching the appropriate endpoint with the correct status filter. Tab badge counts are fetched separately and refreshed on any mutation.

Drafts tab: each listing card shows Edit, Submit for Review, Delete. Delete shows a confirmation dialog. Submit for Review calls `PATCH /submit-for-review/`.

Under Review tab: each listing card shows a status chip ("Awaiting agency review" or "Awaiting admin review"). If status is `agency_review`, show Withdraw CTA. No edit button — editing is locked once submitted.

Rejected tab: each listing card shows the rejection reason, who rejected it (Agency or Admin), and CTAs Edit and Resubmit. Edit navigates to the listing edit form. Resubmit calls `PATCH /resubmit/`.

Live tab: each listing card shows View Listing CTA linking to the public listing page.

Agency Inventory and Public Marketplace: read-only grid views, no action CTAs, View links only.

On any successful CTA action, invalidate the relevant TanStack Query keys so badge counts and tab contents update without a page reload.

tsc 0, lint 0, build 0 before push.

**Done-when:** Agent can create a listing (lands in Drafts), submit it (disappears from Drafts, appears in Under Review with correct chip), see it rejected (appears in Rejected with reason), resubmit it, and eventually see it in Live. All six tabs render with correct data and zero console errors.

---

### M.4 — Frontend: Agency Owner My Listings Dashboard

Goal: agency owner's My Listings page has the correct tab structure from Section 1.5.

**Tasks:**

Implement tabs in order: Drafts, Agency Queue, Pending Admin, Rejected, Verified Inventory, Public Marketplace.

Drafts tab: same structure as agent Drafts but CTA says "Submit to Admin" (not "Submit for Review") and calls `PATCH /submit-to-admin/`.

Agency Queue: operational inbox. Each listing card shows the agent who created it, created date, and status chip "Awaiting agency review". CTAs: Approve (calls `PATCH /agency-approve/`) and Reject (opens AlertDialog with required reason field, calls `PATCH /agency-reject/`). On Approve, listing disappears from Agency Queue and appears in Pending Admin. On Reject, listing disappears and agent's Rejected tab updates.

Pending Admin: informational. Each listing shows "Awaiting admin review" chip and a Recall CTA (calls `PATCH /recall/`). No approve/reject actions here.

Rejected: shows own admin-rejected listings with Edit/Resubmit CTAs. Also shows agent listings that admin rejected (visible but no action available — agent must act).

Verified Inventory: all agency live listings. View Listing only.

Public Marketplace: same as agent market awareness view.

tsc 0, lint 0, build 0 before push.

**Done-when:** Agency owner can see agents' submitted listings in their Agency Queue, approve or reject them, see the listing move to Pending Admin on approval, see it move to Verified Inventory after admin approves. Own listings correctly bypass the Agency Queue and go directly to Pending Admin on submit.

---

### M.5 — Frontend: Admin Moderation Rewire

Goal: admin moderation page uses new state names and is connected to the correct data sources.

**Tasks:**

Update the admin moderation page to use `admin_review` as the queue source (was `agency_approved` in Phase L). The underlying data is the same — just the enum value name changes.

Update all status label references from the old enum vocabulary (`pending_review`, `agency_approved`, `verified`, `rejected`, `revoked`) to the new vocabulary (`draft`, `agency_review`, `admin_review`, `live`, `revoked`, `agency_rejected`, `admin_rejected`) using the `MODERATION_LABELS` map established in L.3.

Confirm all five admin tabs (Review Queue, Live, Rejected, Revoked, All) fetch from the correct status filters.

Add admin-rejected tab if not present. Ensure Reinstate CTA calls `PATCH /reinstate/`.

Add listing event history view accessible from the All tab — clicking a listing shows its `listing_events` timeline via `GET /properties/events/{id}/`.

tsc 0, lint 0, build 0 before push.

**Done-when:** Admin can see all listings at `admin_review` in their Review Queue, approve one (listing goes live, moves to Live tab), reject one (listing moves to Rejected tab with reason), revoke a live listing (moves to Revoked tab), and restore it. All tab counts are accurate. Listing event history is visible for any listing.

---

### M.6 — Backend: Notification Integration

Goal: every state transition that affects an actor triggers the correct email via the existing Resend/email task infrastructure.

**Tasks:**

Wire email tasks to the following transitions. Each fires async and is fail-open — email failure never blocks the primary endpoint action.

```
agency_review → agency_rejected:
  To: listing agent
  Subject: Your listing requires revision — [property title]
  Body: agency rejection reason, link to /account/listings

admin_review → live:
  To: listing agent
  Subject: Your listing is now live — [property title]
  Body: confirmation, public link to /properties/{id}
  Also notify: agency owner (FYI — their inventory grew)

admin_review → admin_rejected:
  To: listing agent AND agency owner
  Subject: Listing rejected by platform — [property title]
  Body: admin rejection reason, next steps

live → revoked:
  To: listing agent AND agency owner
  Subject: Listing removed from public view — [property title]
  Body: reason, options

revoked → live (restore):
  To: listing agent AND agency owner
  Subject: Your listing has been restored — [property title]
```

Raise test coverage on all new email tasks to ≥ 80%. Mock Resend client. Test fail-open behaviour — email error must not cause endpoint to return 5xx.

**Done-when:** pyright 0, pytest ≥ 95%. Each email type fires in staging. Resend dashboard confirms delivery. Failure of Resend call does not affect the state transition response code.

---

### M.7 — Integration Validation and Phase M Exit

Goal: the full listing lifecycle works end to end without SQL. All 12 original journeys pass for the first time against real production data.

**Tasks:**

Create one real listing as the outlook agent account. Walk the full lifecycle:
1. Create listing (lands in agent Drafts)
2. Submit for Review (moves to agent Under Review, appears in agency owner Agency Queue)
3. Agency owner approves (moves to agent Pending Admin chip, appears in admin Review Queue)
4. Admin approves (listing goes live on /properties/, agent sees it in Live tab)
5. Seeker visits /properties/ and sees the listing (Journey 3)
6. Seeker filters by location and property type (Journey 4)
7. Seeker clicks through to property detail (Journey 5)
8. Seeker submits inquiry (Journey 10)
9. Agent receives inquiry notification email
10. Admin revokes listing (disappears from /properties/)
11. Admin restores listing
12. Confirm all listing_events rows exist for every transition

Walk all 12 original journeys from Phase D:
1. Register new account (seeker)
2. Login and session refresh
3. Browse property listings
4. Search by location/price/type
5. View property detail
6. View agent profile
7. View agency profile
8. Save and remove favourite
9. View saved favourites
10. Submit inquiry
11. View sent inquiries
12. Agent manage own listings

tsc 0, lint 0, build 0. pyright 0. pytest ≥ 95%.

Update DEFERRED.md — all Phase M items closed or promoted to Phase N.
Update all CLAUDE.md files with Phase M closed state.

**Done-when:** Full listing lifecycle completes via UI with no SQL intervention. All 12 journeys pass. listing_events table has a complete record of every transition. CI green across both repos.

---

## 3. Phase M Exit Criteria

```
Criterion                                          Verification
----------------------------------------------------------
new enum values in DB and OpenAPI schema           pnpm gen:types shows draft, agency_review,
                                                   agency_rejected, admin_review, admin_rejected,
                                                   live, revoked in generated types

listing_events table exists with RLS               SQL query confirms table and policies

Property creation defaults to draft                New listing via API returns status: draft

Every legal transition has an endpoint             Walk full lifecycle via API calls — no SQL

Every illegal transition returns 403 or 422        Test with wrong role credentials

Agent My Listings has correct 6 tabs               Visual walkthrough as agent account

Agency Queue receives submitted listings           Agency owner sees agent's submitted listing

Agency owner Submit to Admin bypasses queue        Agency owner listing goes to admin_review
                                                   without appearing in agency queue

Admin Review Queue shows admin_review only         No draft or agency_review in admin queue

Full listing lifecycle via UI — no SQL             Create → submit → approve → approve → live

Admin revoke and restore work                      Listing disappears and reappears on /properties/

All notification emails fire in staging            Resend dashboard delivery confirmation

listing_events records every transition            SELECT COUNT(*) after full lifecycle walk

All 12 original journeys passing                   Manual walkthrough with real production data

tsc → 0                                            pnpm tsc --noEmit

pyright → 0                                        venv pyright

pytest ≥ 95%                                       pytest --cov gate

pnpm build → 0 warnings                            Next.js production build

DEFERRED.md updated                                All Phase M items closed or promoted

All CLAUDE.md files committed                      Root, frontend, backend — Phase M closed state
```

---

## 4. Items Deferred to Phase N

```
Item                                Rationale
----------------------------------------------------------
Three-tier listing moderation       Reserved for Phase N after Phase M MVP proves
(agent → agency → admin → public    the two-tier approval flow works in production.
upgrade path with agency_approved   Phase M uses the cleaner direct state machine.
as a separate inventory stage)

In-app inquiry reply threads        Lead capture is MVP. Reply thread model
                                    requires its own data model.

Saved search notifications on       Saved search email infra exists. Scheduler
new verified listings               wiring is Phase N after listing volume validates
                                    the investment.

Notification frequency preference   Saved search emails default to immediate.
(immediate vs daily digest)         Preference UI is Phase N.

Advanced map view (Mapbox)          Leaflet/OSM sufficient. Upgrade when tile
                                    quality is user-reported friction.

TBT < 100ms                         Revised target 300ms met. 100ms requires RSC
                                    migration. Phase N after traffic data.

Agency N+1 on public directory      Public agency cards compute stats per card.
                                    Phase N after traffic data sizes optimisation.

Custom domain setup                 Operational task. Phase N.

Audit log retention (DEF-002)       Assess after 60 days of real traffic from
                                    first live listings.
```

---

## 5. Production Reference

```
Service              URL / Reference
----------------------------------------------------------
Frontend             https://realtornet-web.vercel.app
Backend (prod)       https://realtornet-production.up.railway.app
Backend (staging)    https://realtornet-staging.up.railway.app
Supabase (prod)      https://fobvnshrqxduuhzgflvd.supabase.co
Supabase (staging)   https://avkhpachzsbgmbnkfnhu.supabase.co
Supabase (dev)       umhtnqxdvffpifqbdtjs — do not use for production work
Email service        Resend — MAIL_FROM domain verification still pending
                     (DEF-J-EMAIL-DOMAIN-001 — operator action required)
```

```
Production Accounts
user_id   email                          role            agency
1         apineorbeenga@gmail.com        admin           NULL
2         apineorbeenga@outlook.com      agency_owner    Apine Real Estate (id=1)
3         apineorbeenga@yahoo.com        agent           Apine Real Estate (id=1)
4         apineterngu19@gmail.com        seeker          NULL
```

---

## 6. Session Opening Template

Use this as the opening prompt for every Phase M session.

> "Continuing RealtorNet Phase M from [M.X]. Phase L closed June 2026 — infrastructure on new Supabase project fobvnshrqxduuhzgflvd, staging live at realtornet-staging.up.railway.app, L.2/L.3 moderation complete, smoke data cleaned, CLAUDE.md locked. Backend pyright 0, pytest ≥ 95%, on Railway at realtornet-production.up.railway.app. Frontend tsc 0, lint 0, build 0 on Vercel at realtornet-web.vercel.app. Production Supabase fobvnshrqxduuhzgflvd. Staging avkhpachzsbgmbnkfnhu. Dev umhtnqxdvffpifqbdtjs — do not use.
>
> Four roles: seeker / agent / agency_owner / admin. Current moderation enum: pending_review / agency_approved / verified / rejected / revoked — these are being REPLACED in Phase M by: draft / agency_review / agency_rejected / admin_review / admin_rejected / live / revoked.
>
> Governing decision for Phase M: the listing governance system is built on a single state machine. Tabs are filters on state. Every dashboard tab, every CTA, and every permission check derives from the transition authority matrix in Section 1.4 of the Phase M workbook. Read Sections 1.1 through 1.7 before any implementation begins.
>
> Today's task: [SPECIFIC TASK FROM PHASE M BACKLOG — start with M.1 backend migration].
>
> Attach Phase M workbook, PREFLIGHT.md, DEFERRED.md, and all CLAUDE.md files."

---

*RealtorNet — Phase M Workbook v1.0*
*Derived from Phase L close state*
