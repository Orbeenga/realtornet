# RealtorNet — Phase K Opening Brief
## Production Data Repair + Product Completeness

**Date:** May 2026
**Railway:** Live — realtornet-production.up.railway.app
**Supabase production:** avkhpachzsbgmbnkfnhu — all DB work targets this project only
**Pre-flight law:** Read CLAUDE.md (root + backend + frontend) before starting any task. List what is locked. No workarounds.

---

## The Relationship Model — Definitive Reference

Before any work begins, confirm this is understood. It is the source of every issue below.

| Entity | What it is |
|---|---|
| **Agency** | An organisation. Not a user. Has a name, approved status, listings inventory, agent roster. |
| **Agency owner** | A user role. A person who runs one agency. Has all agent capabilities (creates listings) plus agency management (invites agents, manages roster). |
| **Agent** | A user operating under an agency. Creates listings carrying both `user_id` (who created it) and `agency_id` (which agency it belongs to). |
| **Seeker** | Public user. Browses, inquires, favourites. No listing rights. |

**The invariant:** Every listing belongs to exactly one agency via `agency_id`. An agent's listings belong to the agency they were a member of at time of creation. An agency_owner's listings belong to the agency they own. No listing should exist without a valid `agency_id` pointing to an approved agency.

**The promotion invariant:** When a user is promoted to `agency_owner` of Agency X, the following must all be true atomically:
- `users.user_role = agency_owner`
- `users.agency_id = X`
- An `agency_agent_memberships` row exists for `(user_id, agency_id=X, status=active)`
- `agent_profiles.agency_id = X`

If any of these is missing, the promotion is partial and stats will contradict.

---

## Task 1 — Backend: Hard Delete Generic/Smoke Users and Repair Data Integrity

**Owner:** Backend agent
**Requires:** Direct Supabase production access (`avkhpachzsbgmbnkfnhu`)
**Gate:** pyright → 0, pytest → all passing ≥ 95% after changes

### 1A — Hard delete generic/smoke users

Identify and hard delete all user records that are not real accounts. A real account is one with a genuine, unique display name that is not a numeric pattern, test string, or seed artifact.

**Hard delete criteria — a user row qualifies for hard deletion if ANY of the following is true:**
- `display_name` matches the pattern `Agent #\d+`, `A#\d+`, or any variant of `Agent` followed by a number
- `display_name` is null or empty string
- `email` domain is a test sink (e.g. `delivered@resend.dev`, `test@`, `smoke@`)
- The account was created during a known smoke test run and has no real inquiry, favourite, or listing activity

**The four real production accounts — DO NOT TOUCH:**

| user_id | email | role |
|---|---|---|
| 5 | apineorbeenga@gmail.com | admin |
| 74 | apineorbeenga@outlook.com | agency_owner |
| 76 | apineorbeenga@yahoo.com | seeker |
| 85 | godwinemagun@gmail.com | seeker |

**Hard delete execution:**

Because of RLS and foreign key constraints, deletion must happen in dependency order. For each target user:

1. Hard delete dependent rows first (in this order): `agent_membership_audit`, `agency_agent_memberships`, `agent_profiles`, `saved_searches`, `favorites`, `inquiries` (where sender), `audit_logs`
2. Hard delete `properties` rows owned by the user **only if** they are smoke/seed listings (no real inquiry activity). If a property has real inquiries attached, soft-delete instead and flag for manual review.
3. Hard delete the `users` row
4. Call `supabase.auth.admin.deleteUser(supabase_id)` to remove the Supabase Auth identity

**After deletion:** Run `SELECT COUNT(*) FROM users WHERE deleted_at IS NULL` to confirm remaining user count matches expectations. Report the before/after count explicitly.

### 1B — Repair user_id=74 promotion data

The promotion of `apineorbeenga@outlook.com` to `agency_owner` of Agency 9 was partial. The following inconsistency exists in production:

| Table | Current state | Required state |
|---|---|---|
| `users` | `user_role=agency_owner`, `agency_id=9` | ✅ Correct |
| `agency_agent_memberships` | Active row for `(user_id=74, agency_id=1)` only. No row for agency 9. | ❌ Missing agency 9 membership |
| `agent_profiles` | `agency_id=1` | ❌ Should be `agency_id=9` |
| `properties 3, 4` | `agency_id=1` | 🟡 Historical — these were created while member of agency 1. Leave as-is (snapshot is correct for time of creation). |
| `property 6` | `agency_id=9` | ✅ Correct — created after promotion |

**Repair steps — execute as a single transaction:**

```sql
BEGIN;

-- 1. Create agency 9 membership row for user 74
INSERT INTO agency_agent_memberships (user_id, agency_id, status, created_at)
VALUES (74, 9, 'active', NOW())
ON CONFLICT DO NOTHING;

-- 2. Update agent_profiles to point at agency 9
UPDATE agent_profiles
SET agency_id = 9
WHERE user_id = 74 AND deleted_at IS NULL;

-- 3. Write audit record for the corrected promotion
INSERT INTO agent_membership_audit
  (user_id, agency_id, action, actor_id, reason, prior_role, post_role, created_at)
VALUES
  (74, 9, 'joined', 5, 'Data repair: promotion to agency_owner of agency 9 was partial. Membership row and agent_profile corrected to match users.agency_id.', 'agent', 'agency_owner', NOW());

COMMIT;
```

**Verify after repair:**
- `SELECT * FROM agency_agent_memberships WHERE user_id = 74` — should show two rows: agency 1 (historical, can be deactivated if desired) and agency 9 (active)
- `SELECT agency_id FROM agent_profiles WHERE user_id = 74` — should return `9`
- `SELECT agency_id, COUNT(*) FROM properties WHERE user_id = 74 AND deleted_at IS NULL GROUP BY agency_id` — should show agency_id=1 (2 properties, historical) and agency_id=9 (1 property)

**Decision on agency 1 membership:** The agency 1 membership (membership_id=3) is now historical. The user is agency_owner of agency 9, not an agent at agency 1. Deactivate it:

```sql
UPDATE agency_agent_memberships
SET status = 'inactive', deleted_at = NOW()
WHERE membership_id = 3;

INSERT INTO agent_membership_audit
  (user_id, agency_id, action, actor_id, reason, prior_role, post_role, created_at)
VALUES
  (74, 1, 'left', 5, 'Data repair: user promoted to agency_owner of agency 9. Prior agency 1 membership deactivated.', 'agent', 'agency_owner', NOW());
```

### 1C — Fix property ID 3 data error

Property 3 has title "Modern 3 Bedroom for Rent" but `listing_type = 'for_sale'` (or equivalent enum value causing the "For Sale" badge). This is a data entry error.

Correct it:
```sql
UPDATE properties
SET listing_type = 'for_rent'  -- use the exact enum value your schema defines for rent
WHERE id = 3 AND deleted_at IS NULL;
```

Confirm the enum value by checking `\dT listing_type_enum` or equivalent before running.

### 1D — Backend quality gate

After all data changes:
- `pyright` → 0 errors
- `pytest -q` → all passing, coverage ≥ 95%
- Report: user count before/after hard delete, membership rows for user 74, property 3 listing_type confirmed

---

## Task 2 — Backend: Stats Canonical Source Fix

**Owner:** Backend agent
**Problem:** Agency stats (active listings count, roster agent count) return different numbers depending on which endpoint is called. Root cause: no single canonical query.

**The correct canonical sources:**

| Stat | Canonical query |
|---|---|
| Agency active listings count | `COUNT(*) FROM properties WHERE agency_id = X AND deleted_at IS NULL AND moderation_status = 'verified'` |
| Agency roster agent count | `COUNT(*) FROM agency_agent_memberships WHERE agency_id = X AND status = 'active' AND deleted_at IS NULL` |
| Agent's own active listings | `COUNT(*) FROM properties WHERE user_id = Y AND deleted_at IS NULL AND moderation_status = 'verified'` |

**What to fix:**

1. Audit every endpoint that returns agency stats: `GET /api/v1/agencies/{id}/`, `GET /api/v1/agencies/{id}/stats/`, the account dashboard aggregation, and any admin stats endpoint. Confirm each uses the canonical queries above.
2. Where they diverge, fix the query to match the canonical source.
3. The `agency_owner` account dashboard "Active listings" widget must query `properties WHERE agency_id = users.agency_id` — not `properties WHERE user_id = current_user.id`. An agency_owner's dashboard shows the agency's inventory, not just their personal listings.
4. The "Roster agents" widget must query `agency_agent_memberships WHERE agency_id = X AND status = 'active'` — the same query used by the public agency profile.

**Done-when:** Logging in as `apineorbeenga@outlook.com`, the agency dashboard "Active listings" and "Roster agents" counts match what `GET /api/v1/agencies/9/` returns for those same fields. No contradiction between account view and public view.

---

## Task 3 — Frontend: Navigation Restructure

**Owner:** Frontend agent
**Problem:** When logged in, the top nav shows 6–7 items mixing public discovery and account tools. It reads like an internal admin panel, not a marketplace.

**The fix — two-tier navigation:**

**Public top nav (visible to everyone, logged in or not):**
- Properties
- Agencies
- Agents
- (If logged out): Login | Register
- (If logged in): Avatar/name → dropdown containing account items

**Account dropdown (behind avatar, role-aware):**

| Role | Items |
|---|---|
| Seeker | My Favorites, Saved Searches, My Inquiries, Settings |
| Agent | My Listings, My Inquiries, My Favorites, Settings |
| Agency owner | My Listings, Agency Dashboard, My Inquiries, Settings |
| Admin | Property Moderation, User Management, Analytics, Settings |

**Implementation rules:**
- The public nav links come from `navigation.ts` constants — do not hardcode route strings
- The avatar dropdown uses shadcn/ui `DropdownMenu` — it handles keyboard navigation and click-outside close
- On mobile, the hamburger drawer (built in Phase K offline pass) shows public links first, then a divider, then account links — same two-tier logic in a single drawer
- `tsc --noEmit`, `lint`, `build` must pass

**Done-when:** A logged-in seeker sees Properties, Agencies, Agents in the top bar, and their account items only behind the avatar. A logged-out user sees Properties, Agencies, Agents plus Login and Register. The nav does not look like an internal dashboard.

---

## Task 4 — Frontend: Landing Page — Search-Led Hero

**Owner:** Frontend agent
**Problem:** The homepage leads with abstract "agency hierarchy" messaging. Users expect to search immediately.

**What to build:**

Replace the current hero content with a search-first layout:

```
[Hero section]
  Headline: "Find Your Next Property in Lagos"
  Subheadline: "Verified listings from trusted agencies"

  [Search bar — primary action]
    [ Location input — autocomplete via /api/v1/locations/search ]
    [ Buy / Rent toggle ]
    [ Search button → /properties?location_id=X&listing_type=Y ]

[Below hero — two sections, only shown if data exists]
  "Latest Verified Listings" — fetch GET /api/v1/properties/?page=1&page_size=6&moderation_status=verified
  "Trusted Agencies" — fetch GET /api/v1/agencies/?page=1&page_size=6

  If either returns empty array: hide the section entirely — do not show "No listings yet"
```

**Rules:**
- Location autocomplete uses `useLocationSearch()` hook (already built in Phase J) — no direct Nominatim calls
- The Buy/Rent toggle sets `listing_type` in the URL when Search is clicked
- Server-side fetch the initial data (SSR already restored in Phase J for these endpoints) — no skeleton on first load
- If the backend returns an error, hide the section silently — the hero search still works
- The gradient hero background (DEF-J-HERO-001 fallback) remains until a proper licensed image is sourced — do not reintroduce a hotlinked image

**Done-when:** Homepage hero has a working location search input and Buy/Rent toggle. Clicking Search navigates to /properties with the correct params. Featured sections only render if they have data. `tsc`, `lint`, `build` clean.

---

## Task 5 — Frontend: Agent Profile Completeness Gate

**Owner:** Frontend agent
**Problem:** `/agents/` shows `Agent #28`, `Agent #27`, `A#`, "Independent agent", 0.0 ratings, "Not recorded" everywhere. These are incomplete profiles being surfaced publicly.

**Two-part fix:**

**Part A — Public agents list: filter before displaying**

The `GET /api/v1/agents/` endpoint returns all agents. The frontend must not display agents who fail a minimum completeness check. Filter client-side (or request backend adds a `?complete_only=true` param — check which is simpler):

A profile is displayable if ALL of the following are true:
- `display_name` is not null, not empty, not matching `Agent #\d+` pattern
- `agency_id` is not null (agent belongs to an agency)
- `agency_name` is not null or empty

If an agent fails any check, exclude them from the public list silently. Do not show an error — just omit.

**Part B — Agent card redesign**

The current card shows too many "Not recorded" fields. Fix the display logic:

- Rating: only show the star rating if `review_count > 0`. If no reviews, show nothing — not "0.0"
- Phone/contact: only show if the field is populated
- Specialties: only show if populated
- Agency badge: show agency name and link to `/agencies/{agency_id}` — this is the trust signal, make it prominent
- Active listing count: show `X active listings` — fetch from the listings count, not a separate stat call
- Verified badge: show only if `is_verified = true`

**Done-when:** `/agents/` shows no card with a numeric/generic name. Cards show rating only if reviews exist. Every visible agent has an agency badge. `tsc`, `lint`, `build` clean.

---

## Task 6 — Frontend: Agency Card Polish + Stats

**Owner:** Frontend agent
**Problem:** Agency cards show "Not recorded" for listings and agent counts. This is because the public `/agencies/` endpoint does not return those counts (DEF-J-AGG-001 — N+1 issue deferred).

**Short-term fix while the aggregation endpoint is deferred:**

- If `listing_count` or `agent_count` is null/unavailable from the API response, hide those stat boxes entirely — do not render "Not recorded"
- Show: agency name, description (truncated to 2 lines), location if available, verified badge if `is_verified = true`, and a "View agency" CTA
- Do not show empty stat boxes. A clean card with fewer fields is better than a card with "Not recorded" repeated

**Longer-term fix (if backend adds counts to the agency list response in Task 2):** Wire the counts through once they're in the API response.

**Done-when:** `/agencies/` cards show no "Not recorded" text. Cards are clean and consistent. Verified agencies show a badge.

---

## Task 7 — Frontend: Account Dashboard Loading Polish

**Owner:** Frontend agent
**Problem:** `/account/agency/` shows a full-page centered spinner before content renders. Tab switches show "Loading..." text.

**Fix:**
- Replace full-page spinner with a skeleton that preserves layout — use the existing `Skeleton` component (built in Phase D) matching the dashboard grid shape
- Tab content: use per-tab skeletons, not a generic "Loading..." string
- Agency edit form: move out of inline expansion into a shadcn/ui `Sheet` (drawer) — keeps the dashboard layout stable while editing
- Cache tab data with TanStack Query — switching between tabs should not re-show a loading state if data was already fetched

**Done-when:** `/account/agency/` loads with a layout-preserving skeleton. Tab switches are instant if data is cached. No full-page spinner visible.

---

## Execution Order

Run in this sequence. Tasks with a 🔗 dependency cannot start until their dependency is done.

| Order | Task | Owner | Dependency | Can parallel? |
|---|---|---|---|---|
| 1 | Task 1A — Hard delete smoke users | Backend | None | No — do first |
| 2 | Task 1B — Repair user_id=74 promotion | Backend | 1A done | No |
| 3 | Task 1C — Fix property 3 listing_type | Backend | None | Yes, with 1A |
| 4 | Task 2 — Stats canonical source | Backend | 1B done | No — depends on clean data |
| 5 | Task 3 — Nav restructure | Frontend | None | Yes, with backend tasks |
| 6 | Task 4 — Landing page hero | Frontend | None | Yes, with Task 3 |
| 7 | Task 5 — Agent completeness gate | Frontend | 1A done (clean data) | Yes, with Task 6 |
| 8 | Task 6 — Agency card polish | Frontend | Task 2 done ideally | Yes, with Task 5 |
| 9 | Task 7 — Dashboard loading | Frontend | None | Yes, any time |

---

## Phase K Exit Criteria (preliminary)

Phase K is closed when:

| Criterion | Verification |
|---|---|
| No generic/numeric agent names in production | `GET /api/v1/agents/` returns no `Agent #\d+` names |
| Agency stats consistent across all views | Account dashboard matches public agency profile |
| Property 3 listing_type correct | Badge matches title |
| user_id=74 data consistent across all tables | Supabase query confirms membership, agent_profile, users all point agency 9 |
| Homepage has working search | Location input + Buy/Rent toggle → navigates to /properties with correct params |
| No "Not recorded" on agency cards | Visual check on /agencies/ |
| No generic agent cards on /agents/ | Visual check on /agents/ |
| Nav is two-tier | Logged-in user sees public links + avatar dropdown |
| pyright → 0 | venv pyright |
| pytest → ≥ 95% | pytest --cov |
| tsc → 0 | pnpm tsc --noEmit |
| pnpm build → clean | Next.js production build |
| DEFERRED.md updated | All Phase K items closed or promoted to Phase L |
| All CLAUDE.md files committed | Root, frontend, backend |

---

## What Remains in Phase J Until Email Domain Is Resolved

DEF-J-EMAIL-DOMAIN-001 is still the only open Phase J exit criterion. Once you verify a domain in Resend and update `MAIL_FROM` in Railway, Phase J formally closes and Phase K is the active phase. Everything in this brief is Phase K work.

**Resend domain verification — your action, no agent needed:**
1. Register any domain (realtornet.com.ng, realtornet.ng, or similar — ~$10-15)
2. Resend dashboard → Domains → Add Domain → add your domain
3. Add the 3 DNS records to your registrar
4. Wait 5-10 minutes for green verification status
5. Railway → backend service → environment variables → update `MAIL_FROM=noreply@yourdomain.com`
6. Dispatch backend agent to confirm `_sender_address()` returns the new value
7. Submit one inquiry → confirm email arrives in agent inbox → DEF-J-EMAIL-DOMAIN-001 closed
