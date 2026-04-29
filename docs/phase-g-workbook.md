<!-- Source: C:\Users\Apine\Downloads\RealtorNet_Phase_G_Workbook.docx -->
<!-- Converted to Markdown for agent-readable Phase G reference. -->

REALTORNET

Phase G — Agency-First Refactor & Feature Completion

Authoritative Preflight & Execution Reference

| Phase F closed | April 25, 2026 — all exit criteria met, CLAUDE.md committed |
| --- | --- |
| Backend version | v0.5.3 — 1737 tests, 92.87% coverage, 0 Pyright errors |
| Frontend version | Next.js 16.2.1 — deployed to Vercel |
| Stack (locked) | Next.js · TypeScript · Supabase · TanStack Query · FastAPI |
| Deploy targets | Vercel (frontend) · Railway (backend) · Supabase (DB + Auth) |
| Production Supabase | avkhpachzsbgmbnkfnhu — do not mix with dev project |
| Phase G opens | April 25, 2026 |



| Phase G converts a working product into a trust-layered marketplace. Agency-first architecture is the governing design decision. Everything else follows from it. |
| --- |



# 0. Phase F Exit State

Phase F is fully closed. The system is live, secure, and passing all 12 user journeys. The following items carry forward as the Phase G opening inventory.


## 0.1 Closed in Phase F

| Item | State |
| --- | --- |
| RLS — all 14 tables | ✅ Enabled and verified |
| Storage bucket auto-provisioning | ✅ Deploy-time script wired to Railway |
| Mobile LCP | ✅ 2.0s (target < 2.5s) |
| Silent JWT refresh on 401 | ✅ Intercept → refresh → retry → logout |
| Listing verification UI | ✅ Admin verifies, agent sees badge |
| Accessibility — Lighthouse 1.00 | ✅ Zero critical violations |
| Anon user data exposure (P1 security) | ✅ REVOKE on public.users, agent_public_profiles view created |
| Health endpoint leak (P2 security) | ✅ Returns fixed string, not str(e) |
| Inquiry role model | ✅ Seeker sent / agent received / admin all |
| Admin user promotion | ✅ Supabase Auth sync atomic, rollback on failure |
| Production DB cleanup | ✅ 77 test rows soft-deleted, 4 real accounts preserved |


## 0.2 Carried Forward — Phase G Backlog

| ID | Item | Priority |
| --- | --- | --- |
| DEF-G-INQ-002 | Inquiry property hydration — 204 on /properties/{id}, suspected Vercel→Railway proxy | 🔴 High |
| DEF-G-AG-001 | Agency name on property cards — requires agency_name in PropertyResponse | 🔴 High |
| DEF-G-AG-002 | Agency creation UI — currently operator-only via DB/dashboard | 🔴 High |
| DEF-G-MOD-001 | Full moderation status enum — pending/verified/rejected/revoked with notifications | 🟡 Medium |
| DEF-G-TBT-001 | TBT < 100ms — requires RSC migration or islands pattern evaluation | 🟡 Medium |
| DEF-G-POLYFILL-001 | Residual core-js from third-party deps — full elimination | 🟢 Low |
| DEF-002 | Audit log retention at scale — revisit after 60 days real traffic | 🟢 Low |
| DEF-007 | psycopg3 dev restart workaround — monitor | 🟢 Low |



# 1. The Governing Product Decision — Agency-First Architecture

This decision is made here, once, before any Phase G implementation begins. It is not revisited during implementation.


| RealtorNet is not a listing board. It is a trust-layered marketplace where verified agencies hold inventory, agents operate inside agency structures, and seekers interact through trusted institutional containers. |
| --- |


## 1.1 The Product Hierarchy

Public discovery follows a single top-down hierarchy:


| AGENCIESTrust containers | LISTINGSAgency inventory | AGENTSOperating actors |
| --- | --- | --- |


In user-facing language: Meet our agencies → Explore their inventory → Meet the listing agent


## 1.2 Why Agency-First for the Nigerian Market

Trust is the primary friction in Nigerian real estate. An individual agent listing alone provides no institutional accountability.

An agency layer creates a verifiable, accountable container — the public sees listings backed by an organisation, not an isolated user.

Agents inherit credibility from their agency. A listing by Agent X at Agency Y is trusted differently than Agent X alone.

Admin governance scales better by approving organisations, not every individual agent. Once an agency is approved, it manages its own team.


## 1.3 Operational Hierarchy (Locked)

| Level | Role & Responsibility |
| --- | --- |
| Admin | Platform operator. Approves agencies, manages platform integrity, has override on all entities. |
| Agency Owner | Approved organisation representative. Invites and manages agents under their agency. |
| Agent | Invited or admin-promoted under an approved agency. Creates and manages listings. |
| Seeker | Public user. Browses listings, sends inquiries, saves favourites. |


## 1.4 Onboarding Model (Phase G)

The mature default flow replaces admin-promotes-every-agent as the primary path:


| Step | Action | Who |
| --- | --- | --- |
| 1 | Agency applies — submits name, credentials, contact | Agency owner (new user or existing seeker) |
| 2 | Admin reviews and approves/rejects agency application | Admin |
| 3 | Approved agency gets an agency_owner role, agency is live | System (automatic on approval) |
| 4 | Agency owner invites agents by email or internal promotion | Agency owner |
| 5 | Invited user accepts — becomes agent under that agency | Invited user |
| 6 | Agent creates listings under their agency | Agent |
| 7 | Listings appear in public agency inventory | System |


| Admin override remains: admin can still directly promote a seeker to agent and assign an agency. This is the fallback path, not the primary path. The primary path is agency-led. |
| --- |


## 1.5 What Does Not Change

Seeker public signup remains seeker-only. No role self-elevation.

Agency is not a user entity — it remains an operator-created org. The new flow adds a governed application path, not open self-service.

Listings still belong to the creating agent (user_id). Phase G adds properties.agency_id as a snapshot so listings retain historical agency context if an agent later moves.

Admin retains full override capability across all entities.



# 2. Role Model Update

The existing three-role model (seeker, agent, admin) gains a fourth role in Phase G. The DB enum must be extended.


## 2.1 Updated Role Enum

| Role | Source | Capability |
| --- | --- | --- |
| seeker | Public signup (unchanged) | Browse, inquire, favourite |
| agent | Agency invitation OR admin override | Create listings under their agency, manage leads |
| agency_owner | NEW — admin approval of agency application | All agent capabilities + invite/manage agents in own agency |
| admin | Internal only (unchanged) | Full platform access, approve agencies, manage all entities |


## 2.2 Migration Strategy

The existing user_role_enum in PostgreSQL must be altered. This is a backend migration task:

Add ALTER TYPE user_role_enum ADD VALUE 'agency_owner' migration

Existing agents are unaffected — their role stays 'agent'

Supabase Auth custom claims must be updated to recognise agency_owner

Backend JWT middleware must permit agency_owner on all agent-permitted endpoints

Frontend navigation contract must add agency_owner routes (same as agent + agency management)



# 3. What Needs to Be Built — Gap Analysis


## 3.1 Backend Gaps

| Item | Current State | Phase G Target |
| --- | --- | --- |
| user_role_enum | seeker / agent / admin | Add agency_owner |
| Agency application endpoint | Does not exist | POST /api/v1/agencies/apply/ |
| Agency approval endpoint | Does not exist | PATCH /api/v1/admin/agencies/{id}/approve/ |
| Agent invitation endpoint | Does not exist | POST /api/v1/agencies/{id}/invite/ |
| Invite acceptance endpoint | Does not exist | POST /api/v1/agencies/accept-invite/ |
| properties.agency_id | Derived from agent at query time | Add as snapshot column with migration |
| Agency name in PropertyResponse | Not returned (DEF-G-AG-001) | Add agency_name to serializer |
| Inquiry property join on /received | Not joined (DEF-G-INQ-002) | Eager-load property or resolve 204 proxy issue |


## 3.2 Frontend Gaps

| Item | Current State | Phase G Target |
| --- | --- | --- |
| / (landing page) | Redirects to /properties | Agencies directory as default landing |
| /agencies | Exists but not primary nav | Promote to primary discovery surface |
| /agencies/[id] | Live and wired | Add agent roster, listings grid, apply-to-join CTA |
| Agency application form | Does not exist | /agencies/apply — public form, admin-reviewed |
| Admin agency management UI | Does not exist | Pending applications list, approve/reject actions |
| Agency owner dashboard | Does not exist | Invite agents, view team, manage agency profile |
| Agent invitation flow | Does not exist | Email invite → accept page → role upgrade |
| Agency name on property cards | Missing (DEF-G-AG-001) | Render once agency_name in PropertyResponse |
| Navigation for agency_owner | Not defined | Same as agent + /account/agency dashboard |



# 4. Phase G Work Plan — End to End

Seven sequential phases. Each has a goal, task list, and done-when criterion. No phase begins until the previous is closed.


## G.1 — Backend Role & Schema Foundation

Goal: database and backend ready for the agency-first role model. No frontend work begins until G.1 is closed.


Alembic migration: ALTER TYPE user_role_enum ADD VALUE 'agency_owner'

Alembic migration: ALTER TABLE properties ADD COLUMN agency_id INTEGER REFERENCES agencies(id) — backfill from agent's agency_id

Update JWT middleware: agency_owner has all agent permissions plus agency management scope

Add agency_name to PropertyResponse serializer (closes DEF-G-AG-001)

POST /api/v1/agencies/apply/ — public endpoint, creates agency row with status='pending'

PATCH /api/v1/admin/agencies/{id}/approve/ — role-gated to admin, sets status='approved', promotes applicant to agency_owner atomically

PATCH /api/v1/admin/agencies/{id}/reject/ — role-gated to admin

POST /api/v1/agencies/{id}/invite/ — role-gated to agency_owner, creates invite token

POST /api/v1/agencies/accept-invite/ — public endpoint, validates token, promotes user to agent under agency

pyright → 0 errors, pytest → all passing after each endpoint added


| G.1 done-when: pyright clean, all new endpoints tested, properties.agency_id backfilled, agency_owner role visible in JWT claims on a test promotion. |
| --- |


## G.2 — Inquiry Property Hydration Fix (DEF-G-INQ-002)

Goal: agent inquiry cards show property title and link. Current state: property returns 204, cause unknown.


Investigate the 204 on GET /api/v1/properties/{id}/ for authenticated agents — trace through Vercel rewrite → Railway proxy layer

If proxy issue: fix Vercel rewrite config for this route pattern

If backend issue: add property joinedload to /inquiries/received/ CRUD query as fallback

Confirm inquiry cards in UI render property title and link to /properties/[id]


| G.2 done-when: agent Inquiries page shows property title on every inquiry card. No 204 responses on property fetches from authenticated sessions. |
| --- |


## G.3 — Public Agency Discovery (Frontend)

Goal: agencies are the primary discovery surface. Landing page and navigation restructured.


/ (root) — redesign as landing page: hero, agencies directory preview, how it works, CTA

/agencies — paginated agency directory with search, logo, listing count, agent count

/agencies/[id] — enhance: add active listings grid, agent roster with avatars, Apply to Join CTA

Primary navbar: Agencies | Properties | (role-specific items)

Property cards: render agency name and logo now that agency_name is in PropertyResponse (closes DEF-G-AG-001)

pnpm gen:types after G.1 backend changes — regenerate api.generated.ts


| G.3 done-when: a logged-out visitor lands on /, sees agency directory, can navigate Agencies → Listings → Agent contact without logging in. |
| --- |


## G.4 — Agency Application & Admin Approval Flow

Goal: the governed path for new agencies to join the platform is fully functional end to end.


/agencies/apply — public form: agency name, description, address, owner contact, supporting details

Form uses React Hook Form + Zod mirroring the backend agency application schema

On submit: POST /api/v1/agencies/apply/ → success state + 'We will review your application' message

Admin UI: /account/admin/agencies — pending applications list with approve/reject actions

On approval: applicant's role upgrades to agency_owner, agency status becomes 'approved'

Email notification on approval/rejection (if email service available, else log for Phase H)

Smoke test: submit application → admin approves → applicant now has agency_owner role → agency appears in public directory


| G.4 done-when: full application-to-approval flow works end to end without SQL intervention. Admin sees pending queue. Applicant role upgrades on approval. |
| --- |


## G.5 — Agent Invitation Flow

Goal: agency owners can build their team through the platform UI.


/account/agency — agency owner dashboard: team roster, invite form, listing summary

Invite form: enter email → POST /api/v1/agencies/{id}/invite/ → invite token created

Invited user receives link: /agencies/accept-invite?token=... (or email if mail service available)

/agencies/accept-invite — validates token, upgrades user role to agent under the agency

If invited email has no account: redirect to /register, post-register completes invite acceptance

Agency owner dashboard updates in real time: invitee appears as pending, then active on acceptance

Admin override path remains: admin can still directly promote and assign via Users UI


| G.5 done-when: agency owner invites a user → user accepts → user appears as agent under the agency → agent can create listings under that agency. |
| --- |


## G.6 — Moderation & Listing Quality (DEF-G-MOD-001)

Goal: replace the is_verified boolean with a proper moderation status enum.


Backend: ALTER TYPE — add moderation_status enum: pending_review / verified / rejected / revoked

Add reason field to properties: moderation_reason TEXT NULL

Update PATCH /properties/{id}/verify/ to accept status + reason

Admin moderation UI: show status badge, reason input on reject/revoke

Agent dashboard: show full status (not just verified/unverified badge)

Seeker-facing: unverified/rejected/revoked listings remain hidden from public feed


| G.6 done-when: admin can set any of the four statuses with a reason. Agent sees their listing's current moderation state. Public feed excludes non-verified listings. |
| --- |


## G.7 — Integration Validation & Phase G Exit

Goal: all new journeys pass end to end. No regressions on existing 12 journeys.


Full smoke test: all 12 original journeys still passing

New journey: agency applies → admin approves → agency owner invites agent → agent lists property → property appears in agency inventory → seeker inquires

tsc --noEmit → 0 errors across entire frontend

pyright → 0 errors on backend

pnpm build → 0 warnings

Lighthouse: mobile LCP still < 2.5s, accessibility still 1.00

DEFERRED.md updated — all Phase G items marked closed or promoted to Phase H

All three CLAUDE.md files updated and committed


| G.7 done-when: new agency journey passes end to end, all 12 original journeys unbroken, CI green, CLAUDE.md committed. |
| --- |



# 5. Execution Sequence

| # | Phase | Dependency | Parallel? | Blocks launch? |
| --- | --- | --- | --- | --- |
| 1 | G.1 — Role & Schema | None — start immediately | No — must close first | Yes |
| 2 | G.2 — Inquiry fix | G.1 closed | No — backend stream | Yes |
| 3 | G.3 — Public discovery | G.1 closed | Yes — parallel with G.4 | Yes |
| 4 | G.4 — Agency apply/approve | G.1 closed | Yes — parallel with G.3 | Yes |
| 5 | G.5 — Agent invitation | G.4 closed | Yes — parallel with G.6 | Yes |
| 6 | G.6 — Moderation enum | G.1 closed | Yes — parallel with G.5 | No |
| 7 | G.7 — Integration & exit | G.5 + G.6 closed | No — final sweep | Yes |



# 6. Phase G Exit Criteria

Phase G is closed when every item below is true. Not before.


| Exit Criterion | Verification |
| --- | --- |
| agency_owner role live in DB and JWT | Supabase enum query + test promotion |
| properties.agency_id backfilled and enforced | SQL query on all non-deleted properties |
| Agency name on property cards | Visual check on /properties and /agencies/[id] |
| Agency application → approval → agency_owner flow | End-to-end smoke test, no SQL required |
| Agent invitation flow end to end | Invite sent → accepted → agent lists property |
| Full moderation status enum live | Admin sets all 4 states, agent sees status |
| Inquiry cards show property title | Agent Inquiries page — no null property |
| All 12 original journeys still passing | Playwright or manual smoke test |
| New agency journey passes end to end | Full flow without SQL intervention |
| tsc --noEmit → 0 errors | pnpm tsc --noEmit |
| pyright → 0 errors | venv pyright |
| pnpm build → 0 warnings | Next.js production build |
| Mobile LCP still < 2.5s | Lighthouse mobile on /agencies |
| DEFERRED.md updated | All Phase G items closed or promoted to Phase H |
| All CLAUDE.md files committed | Both repos — root, frontend, backend |



# 7. Items Deferred to Phase H

| Item | Rationale |
| --- | --- |
| Agency owner onboarding self-service | Phase G builds admin-governed path. Self-service needs abuse prevention, invite state, duplicate detection. |
| Advanced map view (Mapbox) | MVP uses Leaflet. Mapbox post-launch if tile quality matters. |
| Admin analytics dashboard | Requires real traffic data to design meaningfully. |
| Saved search notifications | Post-MVP scope. |
| Nominatim/OSM geocoding | Seeded list sufficient for Lagos MVP. Phase H when expanding. |
| Email notification service | Phase G can log email events. Phase H implements SMTP/Resend. |
| Agency N+1 aggregation endpoint | DEF-G-INQ-001 — requires usage data to size correctly. |
| TBT < 100ms (DEF-G-TBT-001) | Requires RSC migration. Phase H after traffic validation. |
| Custom domain setup | Operational task — not a code deliverable. |
| Audit log retention (DEF-002) | Revisit after 60 days real traffic. |



# 8. Session Opening Template

Use this as the opening prompt for every Phase G session.


| Session opening template:"Continuing RealtorNet Phase G from [G.X]. Phase F closed April 25 2026 — all exit criteria met, CLAUDE.md committed to both repos. Backend v0.5.3 on Railway (realtornet-production.up.railway.app). Frontend Next.js 16.2.1 on Vercel (realtornet-web.vercel.app). Production Supabase: avkhpachzsbgmbnkfnhu. Dev Supabase umhtnqxdvffpifqbdtjs — do not use for any production work.Governing decision: Agency-first architecture is locked. Public hierarchy: Agencies → Listings → Agents. Operational hierarchy: Admin → Agency Owner → Agent → Listing. Today's task: [SPECIFIC TASK FROM WORK PLAN].Attach Phase G workbook, DEFERRED.md, and all three CLAUDE.md files." |
| --- |



# 9. Production Reference

| Service | URL / Reference |
| --- | --- |
| Frontend | https://realtornet-web.vercel.app |
| Backend | https://realtornet-production.up.railway.app |
| Supabase (production) | https://avkhpachzsbgmbnkfnhu.supabase.co |
| Supabase (dev — deprecated) | umhtnqxdvffpifqbdtjs — do not use for production diagnostics |


## Production Accounts

| user_id | Email | Role | Agency |
| --- | --- | --- | --- |
| 5 | apineorbeenga@gmail.com | admin | NULL |
| 74 | apineorbeenga@outlook.com | agent | 1 |
| 76 | apineorbeenga@yahoo.com | seeker | NULL |
| 85 | godwinemagun@gmail.com | seeker | NULL |



RealtorNet — Phase G Workbook v1.0

Derived from Phase F close state  |  Backend v0.5.3  |  Frontend Next.js 16.2.1

