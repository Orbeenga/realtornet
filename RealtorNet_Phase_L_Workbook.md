# RealtorNet — Phase L Workbook
## Moderation Maturity, Query Performance & Platform Hardening

Authoritative Preflight & Execution Reference

| Item | Value |
|---|---|
| Phase K closed | May 30, 2026 — all exit criteria met, CLAUDE.md committed to both repos |
| Backend version | v0.5.3+ — 1866+ tests, 95.21% coverage, 0 Pyright errors |
| Frontend version | Next.js — deployed to Vercel, commit b6b3c40 |
| Stack (locked) | Next.js · TypeScript · Supabase · TanStack Query · FastAPI · Resend email |
| Deploy targets | Vercel (frontend) · Railway (backend) · Supabase (DB + Auth) |
| Production Supabase | fobvnshrqxduuhzgflvd — do not mix with dev (umhtnqxdvffpifqbdtjs) or archived prod (avkhpachzsbgmbnkfnhu) |
| Production DB head | b3b3424176c3 (update_audit_views_actor_name) |
| Phase L opens | May 30, 2026 |

---

## 0. Phase K Exit State & Entry Conditions

Phase K is fully closed. The session that closed Phase K also resolved a major infrastructure debt: PostGIS was discovered in the public schema on the original production project, requiring a clean-slate migration to a new Supabase project before Phase L could begin on stable ground.

### 0.1 Closed in Phase K (including this session's infrastructure work)

| Item | State |
|---|---|
| PostGIS migrated to extensions schema — new project fobvnshrqxduuhzgflvd | Closed |
| All Alembic migrations applied fresh to new project | Closed |
| 24 missing performance indexes added across 7 tables | Closed |
| 4 real production accounts seeded with correct roles | Closed |
| 12/12 smoke test passing on new project | Closed |
| Railway and Vercel env vars updated to new project | Closed |
| PREFLIGHT.md updated to v2.0 | Closed |
| DEF-L-ADMIN-AUDIT-001 backend — GET /api/v1/admin/audit/ | Closed |
| DEF-L-ADMIN-AUDIT-001 frontend — Audit Activity section on admin analytics | Closed |
| Actor name resolution on audit view — LEFT JOIN users, actor_name field | Closed |
| DEF-L-POSTGIS-001 — PostGIS schema correction | Closed |
| DEF-L-SEARCH-001 — 5 public functions patched with SET search_path = '' | Closed |
| Supabase advisor items — agent_public_profiles, rls_auto_enable, leaked password | Closed |

### 0.2 Phase L Opening Backlog

| ID | Item | Priority | Owner |
|---|---|---|---|
| DEF-J-EMAIL-DOMAIN-001 | Resend domain verification — MAIL_FROM blocked for real inboxes | High | Operator |
| DEF-L-MOD-001 | Three-tier listing moderation — agent creates, agency approves, admin publishes | High | Backend + Frontend |
| DEF-L-N1-001 | N+1 query investigation on /properties/ and /agencies/ endpoints | Medium | Backend |
| DEF-L-ADMIN-MOD-001 | Admin moderation page — change to server-side moderation_status query params | Medium | Frontend |
| DEF-K-AGENT-DIR-001 | /agents/ directory data quality — agents need complete profiles to appear | Medium | Backend + Frontend |
| DEF-K-AGENCY-COUNTS-001 | Agency property_count missing from list response | Medium | Backend |
| DEF-L-ROBOTS-001 | Add robots.txt via Next.js app/robots.ts | Low | Frontend |
| DEF-002 | Audit log retention policy — assess after 60 days real traffic | Low | Backend |

---

## 1. Governing Principle

Phase L converts a secure and structurally correct platform into one that is operationally mature. Moderation workflow reaches its final three-tier form. Query performance gaps are closed before user growth makes them visible. The remaining operator tooling gaps are resolved.

---

## 2. The Three-Tier Moderation Model — Design Specification

This model is the governing design decision for L.1 and L.2. Read it fully before any moderation implementation begins.

### 2.1 The Problem with the Current Two-Tier Model

The current model has two states that matter publicly: `pending_review` (hidden) and `verified` (visible). Admin is the only approver. This means:

- Agency owners have no governance over their own agents' listings before they go to admin review
- Admin sees every listing from every agency in one undifferentiated queue
- An agent's listing goes directly from creation to admin review with no agency-level quality check

### 2.2 The Three-Tier Flow

```
Agent creates listing
        |
        v
  pending_review          <- not visible publicly, not visible in agency queue
        |
        v
Agency owner reviews (own agency listings only)
        |
   approve / reject
        |
        v
  agency_approved         <- NEW STATE: visible to agency owner, not public
        |
        v
Admin reviews (agency_approved listings only — not raw pending_review)
        |
   verify / reject / revoke
        |
        v
    verified              <- visible publicly in /properties/ feed
```

### 2.3 The New Enum State

The `moderation_status` enum requires one new value: `agency_approved`.

Full enum after migration: `pending_review / agency_approved / verified / rejected / revoked` 

### 2.4 Visibility Rules (Locked)

| Status | Agent (own listing) | Agency owner (own agency) | Admin | Public |
|---|---|---|---|---|
| pending_review | sees it | sees it in agency queue | does not see it | hidden |
| agency_approved | sees it | sees it | sees it in admin queue | hidden |
| verified | sees it | sees it | sees it | visible |
| rejected | sees it | sees it | sees it | hidden |
| revoked | sees it | sees it | sees it | hidden |

Key rule: admin only sees listings at `agency_approved` or later in their moderation queue. Admin does not moderate raw `pending_review` listings — that is the agency owner's responsibility.

### 2.5 What This Does Not Change

- Listings already `verified` are unaffected — no backfill required
- Listings at `pending_review` remain at `pending_review` — they will need agency owner action to progress
- The `rejected` and `revoked` states and their existing endpoints are unchanged
- Public feed filter remains: only `verified` listings appear

---

## 3. Phase L Work Plan — End to End

Six sequential phases. Each has a goal, task list, and done-when criterion. No phase begins until the previous is closed.

### L.1 — Email Domain Verification (Operator prerequisite)

Goal: real users receive email notifications. This is an operator action, not a code task. It is listed first because it is the only remaining Phase J exit criterion and should be resolved before L.2 begins.

| Task | Notes |
|---|---|
| Register a domain (e.g. realtornet.com.ng or realtornet.ng — ~$10-15) | Any Nigerian registrar |
| Resend dashboard → Domains → Add Domain → verify DNS records | 3 DNS records, 5-10 minutes to verify |
| Update MAIL_FROM in Railway environment variables | Set to noreply@yourdomain.com or similar |
| Backend agent: confirm _sender_address() returns the new value | Check no placeholder values remain |
| Submit one inquiry → confirm email arrives in agent's real inbox | Done-when gate |
| Update DEFERRED.md — close DEF-J-EMAIL-DOMAIN-001 with Resend message ID as evidence | |

**Done-when:** Resend dashboard shows delivery to a real inbox. Agent receives inquiry notification email. Phase J formally closes simultaneously.

---

### L.2 — Three-Tier Moderation Backend (Backend)

Goal: the database and API support the full three-tier moderation flow. No frontend work begins until L.2 is closed.

| Task | Notes |
|---|---|
| Alembic migration: ADD VALUE 'agency_approved' to moderation_status_enum | Use ADD VALUE — never drop and recreate in production |
| Update public feed filter: WHERE moderation_status = 'verified' — confirm this is already the filter and agency_approved is excluded | Verify no regression |
| Update agency owner listing view: WHERE moderation_status IN ('pending_review', 'agency_approved', 'rejected', 'revoked') AND agency_id = current_user.agency_id | Agency owners see their full queue |
| Update admin moderation queue: WHERE moderation_status = 'agency_approved' | Admin only sees agency-approved listings — not raw pending_review |
| Add PATCH /api/v1/properties/{id}/agency-approve/ endpoint — role-gated to agency_owner of that listing's agency | Sets moderation_status = 'agency_approved', writes audit record |
| Add PATCH /api/v1/properties/{id}/agency-reject/ endpoint — role-gated to agency_owner | Sets moderation_status = 'rejected', requires reason field |
| Existing PATCH /api/v1/properties/{id}/verify/ — update to only accept listings at agency_approved status for admin verification | Admin cannot skip the agency_approved stage |
| Update PropertyResponse to return moderation_status — confirm agency_approved is serialised correctly | gen:types will need to run after this |
| pyright → 0 errors, pytest → all passing ≥ 95% after each endpoint added | |

**Done-when:** pyright 0, pytest ≥ 95%. Agent creates listing → appears in agency queue at pending_review → agency owner approves → moves to agency_approved → admin verifies → appears in public feed. Full path confirmed via API calls, no SQL required.

---

### L.3 — Three-Tier Moderation Frontend (Frontend)

Goal: all three roles have the correct UI surfaces for the three-tier flow. Depends on L.2 being live on Railway.

**Run pnpm gen:types first** — agency_approved will appear in the ModerationStatus enum after the L.2 backend migration.

| Task | Notes |
|---|---|
| Agent listing dashboard: show pending_review status and explain agency review is next step | Replace generic "Pending" label with "Awaiting agency review" |
| Agency owner dashboard — Pending queue tab: show listings at pending_review for own agency | Approve and Reject actions — call new endpoints from L.2 |
| Agency owner dashboard — show agency_approved listings separately as "Sent to admin" | Agent and owner can both see this state |
| Admin moderation page: change queue source to agency_approved listings only | Remove pending_review listings from admin view |
| Admin moderation page: change to server-side ?moderation_status=agency_approved query param (closes DEF-L-ADMIN-MOD-001) | Replaces current client-side filtering |
| Update all status badge labels: pending_review → "Agency review", agency_approved → "Admin review", verified → "Live", rejected → "Rejected", revoked → "Revoked" | Consistent human-readable labels everywhere |
| Smoke test the full three-tier flow end to end via UI — no SQL | Agent creates → agency approves → admin verifies → appears in /properties/ |
| tsc 0, lint 0, build 0 before push | |

**Done-when:** Full three-tier flow works end to end via UI. No listing reaches admin queue without agency approval. Public feed shows only verified listings. All status labels are human-readable.

---

### L.4 — N+1 Query Investigation & Fix (Backend)

Goal: /properties/ and /agencies/ endpoints do not issue N+1 queries. Current state unconfirmed — investigation required first.

| Task | Notes |
|---|---|
| Enable SQLAlchemy query logging locally: set echo=True on engine for one request trace | Log all queries issued during GET /api/v1/properties/ and GET /api/v1/agencies/ |
| Identify N+1 patterns — look for repeated identical queries differing only by ID | Common sources: agency_name on PropertyResponse, agent count on AgencyResponse, image fetch per property |
| Fix with selectinload or joinedload — do not use lazy loading for relationships accessed on every response item | |
| Confirm with EXPLAIN ANALYZE on the fixed query — single query or bounded number, never N queries for N results | |
| Add DEF-L-N1-001 resolution notes to DEFERRED.md | |
| pyright 0, pytest ≥ 95% | |

**Done-when:** EXPLAIN ANALYZE confirms no unbounded query multiplication on either endpoint. Before/after query count recorded.

---

### L.5 — Agent Directory & Agency Counts (Backend + Frontend)

Goal: /agents/ directory shows complete, real agent profiles. Agency list response includes property and agent counts.

**Backend tasks:**

| Task | Notes |
|---|---|
| GET /api/v1/agents/ — confirm response includes agency_name, display_name, and active listing count | These fields were added but data quality depends on agents having complete profiles |
| GET /api/v1/agencies/ list response — confirm property_count and agent_count are returned per agency | This was partially fixed in Phase K (property_count added) — verify agent_count is also included |
| If agent_count missing from list response: add via subquery or annotation in the agencies CRUD — same pattern as property_count | Avoid N+1 — use a single aggregation query |
| pyright 0, pytest ≥ 95% | |

**Frontend tasks:**

| Task | Notes |
|---|---|
| /agents/ completeness filter — only hide agents with numeric/generic names (Agent #N pattern). Do not hide agents with null agency_name — show card without agency badge instead | Current filter may be too aggressive |
| Agency cards — render agent_count once confirmed in list response | Zero is a valid value — display "0 agents", not hidden |
| tsc 0, lint 0, build 0 | |

**Done-when:** /agents/ shows all agents with real display names. Agency cards show both listing and agent counts. No "Not recorded" text on any card.

---

### L.6 — Operational Hardening (Frontend + Backend)

Goal: close the remaining low-priority operational items. Can run in parallel with L.4 and L.5.

| Task | Owner | Notes |
|---|---|---|
| Add robots.txt via Next.js app/robots.ts (DEF-L-ROBOTS-001) | Frontend | Allow all crawlers on public routes. Disallow /account/ and /api/. |
| Audit log retention decision (DEF-002) | Backend | Query audit_logs row count and growth rate. If growing materially: implement age-based soft-delete job for records older than 180 days. If low volume: defer to Phase M with documented decision. |
| Update all CLAUDE.md files — root, frontend, backend | Both | Ensure Phase L in-progress state is captured. Close any open bug items resolved this phase. |

**Done-when:** robots.txt live and crawlable. Audit log retention decision documented with evidence. CLAUDE.md files current.

---

### L.7 — Integration Validation & Phase L Exit (Both)

Goal: all new journeys pass end to end. No regressions on existing 12 journeys.

| Task | Notes |
|---|---|
| Full smoke test — all 12 original journeys still passing | Playwright or manual |
| New moderation journey: agent creates → agency approves → admin verifies → listing appears in public feed → seeker inquires | Full flow without SQL |
| tsc --noEmit → 0 errors | pnpm tsc --noEmit |
| pyright → 0 errors | venv pyright |
| pytest → all passing, coverage ≥ 95% | pytest --cov gate |
| pnpm build → 0 warnings | Next.js production build |
| Lighthouse mobile LCP still < 2.5s | Confirm no regression from new moderation components |
| DEFERRED.md updated | All Phase L items closed or promoted to Phase M |
| All CLAUDE.md files committed | Root, frontend, backend — Phase L closed state |

**Done-when:** New moderation journey passes end to end. All 12 original journeys unbroken. CI green. CLAUDE.md committed.

---

## 4. Phase L Exit Criteria

Phase L is closed when every item below is true. Phase M does not open until this list is complete.

| Exit Criterion | Verification | Owner |
|---|---|---|
| Real-user email delivered to actual inbox | Resend dashboard shows delivery to real address | Operator |
| agency_approved enum value live in DB and serialised | pnpm gen:types shows it in ModerationStatus enum | Backend |
| Agency owner can approve/reject own agents' listings via UI | End-to-end: pending_review → agency_approved via UI | Backend + Frontend |
| Admin moderation queue shows only agency_approved listings | Visual check — no pending_review in admin queue | Frontend |
| Full three-tier flow works without SQL | Agent → agency → admin → public in one sitting | Both |
| N+1 queries eliminated on /properties/ and /agencies/ | EXPLAIN ANALYZE confirms — before/after recorded | Backend |
| /agents/ shows real agent cards, completeness filter not over-aggressive | Visual check | Frontend |
| Agency list response includes both property_count and agent_count | curl GET /api/v1/agencies/ — both fields present | Backend |
| robots.txt live | curl https://realtornet-web.vercel.app/robots.txt | Frontend |
| Audit log retention decision documented | DEFERRED.md entry with volume evidence | Backend |
| All 12 original journeys still passing | Smoke test | Both |
| tsc --noEmit → 0 errors | pnpm tsc --noEmit | Frontend |
| pyright → 0 errors | venv pyright | Backend |
| pytest → all passing, coverage ≥ 95% | pytest --cov gate | Backend |
| pnpm build → 0 warnings | Next.js production build | Frontend |
| DEFERRED.md updated | All Phase L items closed or promoted to Phase M | Both |
| All CLAUDE.md files committed | Root, frontend, backend — Phase L closed state | Both |

---

## 5. Execution Sequence

| # | Phase | Dependency | Parallel? |
|---|---|---|---|
| 1 | L.1 — Email domain | None — operator action | No — do first |
| 2 | L.2 — Moderation backend | L.1 in progress | No — L.3 depends on it |
| 3 | L.3 — Moderation frontend | L.2 live on Railway | No — depends on L.2 |
| 4 | L.4 — N+1 investigation | L.2 closed | Yes — parallel with L.5/L.6 |
| 5 | L.5 — Agent directory & counts | L.2 backend confirmed | Yes — parallel with L.4/L.6 |
| 6 | L.6 — Operational hardening | Runs throughout | Yes — parallel with all |
| 7 | L.7 — Integration & exit | L.2 through L.6 all closed | No — final gate |

---

## 6. Items Deferred to Phase M

| Item | Rationale |
|---|---|
| TBT < 100ms (DEF-G-TBT-001) | Target revised to 300ms. 100ms requires full RSC migration. Phase M after traffic validates the investment. |
| In-app messaging / inquiry reply threads | Lead capture is MVP. Reply thread model requires its own data model. Significant feature. |
| Notification frequency preference UI | Saved search emails default to immediate. Seeker preference (immediate vs daily digest) requires scheduler + preference UI. |
| Agency N+1 on public directory | Public agency cards compute stats per agency. L.4 closes the endpoint N+1. Public directory page-level optimisation is Phase M. |
| Advanced map view (Mapbox) | Leaflet/OSM sufficient for current scale. Upgrade when tile quality is user-reported friction. |
| Nominatim self-hosted instance | Public API sufficient at current scale. Evaluate if rate limiting becomes a constraint. |
| Admin analytics advanced cohort metrics | Current analytics page exists. Advanced metrics require real traffic data. |
| Agency owner self-service onboarding | Phase G built admin-governed path. Self-service needs abuse prevention design. |
| core-js polyfill full elimination | Requires dependency audit — third-party deps pulling in core-js. |
| Audit log retention (DEF-002) | Implement in L.6 if volume warrants. Otherwise Phase M with traffic data. |
| Custom domain setup | Operational task — not a code deliverable. |

---

## 7. Production Reference

| Service | URL / Reference |
|---|---|
| Frontend | https://realtornet-web.vercel.app |
| Backend | https://realtornet-production.up.railway.app |
| Supabase (production) | https://fobvnshrqxduuhzgflvd.supabase.co |
| Supabase (dev) | umhtnqxdvffpifqbdtjs — do not use for production work |
| Supabase (archived prod) | avkhpachzsbgmbnkfnhu — cold backup only, do not use |
| Email service | Resend — code correct. MAIL_FROM domain verification pending (DEF-J-EMAIL-DOMAIN-001) |
| Location resolution | Nominatim public API — server-side only, 1 req/sec, 5-min cache |

### Production Accounts

| Email | Role | Agency |
|---|---|---|
| apineorbeenga@gmail.com | admin | NULL |
| apineorbeenga@outlook.com | agency_owner | Apine Real Estate |
| apineorbeenga@yahoo.com | agent | Apine Real Estate |
| apineterngu19@gmail.com | seeker | NULL |

---

## 8. Session Opening Template

Use this as the opening prompt for every Phase L session.

> "Continuing RealtorNet Phase L from [L.X]. Phase K closed May 30 2026 — infrastructure migrated to clean Supabase project fobvnshrqxduuhzgflvd (PostGIS in extensions schema), all migrations applied, CLAUDE.md committed across all four files. Backend pyright 0, pytest 95.21%, alembic head b3b3424176c3 on Railway (realtornet-production.up.railway.app). Frontend tsc 0, lint 0, build 0, commit b6b3c40 on Vercel (realtornet-web.vercel.app). Production Supabase: fobvnshrqxduuhzgflvd. Dev umhtnqxdvffpifqbdtjs and archived prod avkhpachzsbgmbnkfnhu — do not use. Four roles: seeker / agent / agency_owner / admin. Moderation enum: pending_review / verified / rejected / revoked (agency_approved to be added in L.2). Resend email live — MAIL_FROM domain verification pending (DEF-J-EMAIL-DOMAIN-001). Governing decision for this phase: three-tier moderation is the central feature. Read Section 2 of the Phase L workbook before any L.2 or L.3 work begins. Today's task: [SPECIFIC TASK FROM PHASE L BACKLOG]. Attach Phase L workbook, PREFLIGHT.md, DEFERRED.md, and all CLAUDE.md files."

---

*RealtorNet — Phase L Workbook v1.0*
*Derived from Phase K close state | Backend v0.5.3+ | Frontend Next.js commit b6b3c40*
