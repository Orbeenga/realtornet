# REALTORNET

Phase J — Dynamic Location, Email Infrastructure & Production Readiness

Authoritative Preflight & Execution Reference

| Item | Value |
| --- | --- |
| Phase I closed | May 2026 — all exit criteria met, CLAUDE.md committed to both repos |
| Backend version | v0.5.3+ — 1866 tests, 95.03% coverage, 0 Pyright errors |
| Frontend version | Next.js 16.2.1 — deployed to Vercel |
| Stack (locked) | Next.js · TypeScript · Supabase · TanStack Query · FastAPI · Resend email |
| Deploy targets | Vercel (frontend) · Railway (backend) · Supabase (DB + Auth) |
| Production Supabase | avkhpachzsbgmbnkfnhu — do not mix with dev (umhtnqxdvffpifqbdtjs) |
| Production DB head | a9d1f3c7b482 (location_name migration) |
| Phase J opens | May 2026 |

## 0. Phase I Exit State & Entry Conditions

> Phase J converts the location-agnostic architecture into a fully communicating marketplace. Dynamic location resolution replaces all manual seeding. Email infrastructure is verified and delivering to real inboxes. Platform is production-ready for real users.

### 0.1 Closed in Phase I

| Item | State |
| --- | --- |
| Inquiry received → agent email notification | ✅ Closed |
| Property moderation outcome → agent email | ✅ Closed |
| Role change → email affected user | ✅ Closed |
| Saved search notifications with unsubscribe token | ✅ Closed |
| agent_membership_audit table — append-only, RLS enabled | ✅ Closed |
| role_version JWT invalidation on demotion | ✅ Closed |
| Atomic last-membership revocation → seeker demotion | ✅ Closed |
| PostRevocationDashboard — history-aware, agency-specific | ✅ Closed |
| Agency page CTA intelligence (Apply/Rejoin/Pending/Active) | ✅ Closed |
| Agency review-request flow (submit/accept/decline) | ✅ Closed |
| Mobile TBT — /properties 42ms, /agencies 0ms, /agents 0ms | ✅ Closed |
| DEF-I-MEM-SMOKE-001 — multi-agency revocation verified in production | ✅ Closed |
| DEF-I-COV-001 — coverage raised to 95.03% | ✅ Closed |

### 0.2 Phase J Opening Backlog

| ID | Item | Priority | Owner |
| --- | --- | --- | --- |
| DEF-J-EMAIL-DOMAIN-001 | Real-user email delivery blocked — MAIL_FROM=onboarding@resend.dev is test-only sender. Verified domain required. | 🔴 High | Ops + Backend |
| DEF-J-LOC-001 | Location data breadth — 1 seeded record, grows dynamically as agents list properties via Nominatim resolver | 🟡 Medium | Self-resolving |
| DEF-J-MAP-001 | Interactive map view (Leaflet/Mapbox) — property discovery on map, click to resolve location | 🟡 Medium | Frontend |
| DEF-G-TBT-001 | TBT < 100ms — requires RSC migration. Currently ~300ms revised target met. | 🟡 Medium | Frontend |
| DEF-J-FREQ-001 | Notification frequency preference UI — saved search emails default to immediate. Seeker preference (immediate/digest) Phase K. | 🟢 Low | Backend + Frontend |
| DEF-J-MSG-001 | In-app messaging / inquiry reply thread model — lead capture is MVP, reply is Phase K | 🟢 Low | Both |
| DEF-J-AGG-001 | Agency N+1 on public directory — stats computed per card. Phase K after traffic data. | 🟢 Low | Backend |
| DEF-002 | Audit log retention — 60-day traffic clock. Implement age-based job or defer to Phase K. | 🟢 Low | Backend |
| DEF-H-DOMAIN | Custom domain on Vercel/Railway — operational task, not a code deliverable | 🟢 Low | Ops |

## 1. Governing Principle

> Phase J closes the gap between a technically complete system and a production-ready platform. Email reaches real inboxes. Location is dynamic and self-populating. The platform is safe to open to real users.

## 2. What Was Built in Phase J

### 2.1 Dynamic Location Resolution — Nominatim Server-Side

The platform previously relied on 15 hardcoded Lagos location strings. Phase J replaced this entirely with a PostGIS-backed, Nominatim-powered location system that is location-agnostic and self-populating.

| Component | Detail |
| --- | --- |
| location_resolution_service.py | Server-side Nominatim resolver. Descriptive User-Agent, 1 req/sec throttle, 5-minute in-memory cache, graceful fallback (never blocks property creation). |
| PropertyCreate.location_name | Agents type any free-text location. Backend resolves via Nominatim, calls location_crud.get_or_create(), links property.location_id automatically. |
| GET /api/v1/locations/search?q= | Backend-powered autocomplete endpoint. Frontend calls this — no browser-direct geocoding. Returns LocationResponse[] from DB or Nominatim resolution. |
| LocationResponse coordinates | latitude/longitude now serialised correctly from PostGIS geom column. Coordinates returned on every location record. |
| LocationCascadeSelector | Frontend reusable component — cascading state/city/neighbourhood from live backend endpoints. Used on property filter and listing form. |
| useLocationSearch() hook | Debounced TanStack Query hook. Calls backend search endpoint. No external geocoding from browser. |
| Production smoke | Property created with location_name='Victoria Island Lagos' → resolved to location_id=7, state=lagos, city=itirin, neighbourhood=victoria island, lat/lng confirmed. |

### 2.2 Email Infrastructure — Diagnosis & Hardening

| Item | Finding / Action |
| --- | --- |
| dispatch_email_task branch | Confirmed branches correctly on EMAIL_DELIVERY_MODE. Sync mode uses Celery .apply() in-process — no Redis worker needed. Not broken. |
| App logger wiring | Email dispatch logs now route through app logger — Railway can surface dispatch evidence. |
| Sync dispatch test | New test proves sync mode calls .apply() and never .delay(). Contract is now provable. |
| MAIL_FROM=onboarding@resend.dev | Confirmed as Resend test sender — only delivers to delivered@resend.dev sink. Cannot deliver to real inboxes. Documented as DEF-J-EMAIL-DOMAIN-001. |
| Resend API key scope | Send-only key — cannot inspect domain list via API. Requires dashboard access to configure verified domain. |
| Production email path | Code path correct end to end. Blocker is sender domain verification only — not a code issue. |

### 2.3 UI Fixes & Polish

| Fix | Detail |
| --- | --- |
| Filter layout — horizontal two-row | Row 1: search + Search button. Row 2: Property Type, Min/Max Price, Bedrooms, Filters, Save Search. Sidebar removed entirely. |
| Filter dropdowns — click-outside close | Each pill opens/closes independently. Opening one closes others. No persistent-open panel. |
| Agency owner session persistence | Root cause: omitted-auth agency stats request returned 401, apiClient cleared real session. Fixed: omitted-auth 401s no longer clear authenticated sessions. |
| Featured analytics widget | limit=100 caused 422. Fixed to limit=10. Empty state shows 0, not 'Unavailable'. |
| Admin inquiries page | Secondary property/image enrichment 404s no longer collapse the whole page. |
| Agency cards public stats | No longer calls protected /agencies/{id}/stats/ anonymously. Shows 'Not recorded' instead of error state. |

### 2.4 DEF-I-MEM-SMOKE-001 — Multi-Agency Revocation Verified

Production smoke test confirmed Rule 2 of the Membership Resolution Model: revoking one membership from an agent with two active memberships does not demote their role.

| Evidence | Result |
| --- | --- |
| Agent user_id=90 before smoke | role=agent, role_version=6, one active membership (agency 1) |
| Second membership created | Temporary agency 12 created, owner invited agent, agent accepted |
| After second membership | role=agent, role_version=6, two active memberships |
| Temporary membership revoked | PATCH /agencies/12/agents/{membership_id}/revoke/ via owner token |
| Assertion: user_role_remains_agent | ✅ PASSED — user_role=agent (unchanged) |
| Assertion: role_version_not_incremented | ✅ PASSED — role_version=6 (unchanged) |
| Assertion: temporary_membership_revoked | ✅ PASSED — membership status=inactive |
| Assertion: other_active_membership_intact | ✅ PASSED — original membership still active |
| Cleanup | Temporary agency 12, owner 92, invite 4, membership 7 — all soft-deleted |

## 3. DEF-J-EMAIL-DOMAIN-001 — Email Domain Blocker

> This is the single item that must be resolved before real users receive email notifications. It is not a code problem. It is a configuration prerequisite.

### 3.1 Root Cause

MAIL_FROM=onboarding@resend.dev is Resend's shared test sender address. Resend's policy restricts this sender to delivering only to delivered@resend.dev (their test sink). Emails to any real inbox are silently discarded. All platform email code is correct and the Resend API accepts the sends — but they go nowhere real.

### 3.2 Resolution Path

| # | Action | Who |
| --- | --- | --- |
| 1 | Register a domain (e.g. realtornet.com.ng — ~$10-15/year at any Nigerian registrar) | Platform operator |
| 2 | Go to Resend dashboard → Domains → Add Domain → enter the domain | Platform operator |
| 3 | Add the 3 DNS records Resend provides to your domain registrar's DNS panel | Platform operator |
| 4 | Wait 5-10 minutes for Resend to verify the domain (status turns green) | Platform operator |
| 5 | Update Railway env var: MAIL_FROM=noreply@yourdomain.com (or hello@, support@) | Platform operator |
| 6 | Dispatch backend agent to confirm _sender_address() returns the new value and remove onboarding@resend.dev from PLACEHOLDER_SENDER_VALUES if present | Backend agent |
| 7 | Submit one inquiry and confirm email arrives in the agent's real inbox | Platform operator |

### 3.3 Impact While Blocked

| Feature | Status without verified domain |
| --- | --- |
| Inquiry received → agent notification | Internal dashboard only — no email |
| Property verified/rejected → agent notification | Internal dashboard only — no email |
| Role change → user notification | Internal dashboard only — no email |
| Saved search match → seeker notification | Not delivered |
| Agency approval/rejection | Not delivered to real inboxes |
| Agent invitation | Not delivered to real inboxes |

## 4. Phase J Structure — Two Streams

| Stream | Focus | Phases | Blocks launch? |
| --- | --- | --- | --- |
| Stream A | Email domain + production readiness | J.1 | Yes — users need real emails |
| Stream B | Feature completion & platform maturity | J.2 — J.4 | No — can parallel |

## 5. Phase J Work Plan — End to End

### J.1 — Email Domain Verification & Production Email Confirmation (Stream A)

Goal: real users receive email notifications. MAIL_FROM points to a verified sender domain. End-to-end delivery confirmed to a real inbox.

| Task | Notes |
| --- | --- |
| Platform operator: register domain and verify in Resend dashboard | See Section 3.2 — steps 1-4. No code changes needed until domain is verified. |
| Platform operator: update MAIL_FROM in Railway env vars | Set to noreply@yourdomain.com (or preferred sender address). Railway redeploys automatically. |
| Backend agent: confirm sender address resolves correctly | Check _sender_address() returns the new MAIL_FROM value. Confirm onboarding@resend.dev is not in PLACEHOLDER_SENDER_VALUES (it currently is not — verify this is still true after domain update). |
| End-to-end smoke: submit inquiry → confirm email in agent inbox | This is the done-when gate. Resend dashboard should show delivery to the real agent email address, not to delivered@resend.dev. |
| Update DEFERRED.md — close DEF-J-EMAIL-DOMAIN-001 | Mark closed with evidence: Resend message ID showing delivery to real inbox. |

> Done-when: Resend dashboard shows email delivered to a real inbox (not delivered@resend.dev). Agent receives inquiry notification email. DEF-J-EMAIL-DOMAIN-001 closed with evidence.

### J.2 — Interactive Map View (Stream B)

Goal: property discovery on a map. Leaflet is already in the stack from Phase D. This is the map harness the location architecture was designed for.

| Task | Notes |
| --- | --- |
| Add map toggle to /properties — switch between grid and map view | URL state: ?view=map vs ?view=grid. Default: grid. Map view shows properties as pins at their lat/lng coordinates. |
| Wire property pins to LocationResponse coordinates | Properties with location_id and resolved lat/lng appear as pins. Properties without coordinates appear in a sidebar list. Never show a pin at 0,0. |
| Pin click: property card popover | Clicking a pin shows a mini PropertyCard (image, title, price, beds, link to detail page). Same data as grid card. |
| Map filter integration | Active filters (price, bedrooms, type) apply to map pins as well as grid. Map shows only filtered results. |
| Mobile map view | Full-screen map on mobile with a bottom drawer for the property list. Standard pattern (Zillow mobile, Property24 mobile). |
| OSM tile attribution | Use OpenStreetMap tiles via react-leaflet. Add required attribution: © OpenStreetMap contributors. This is a legal requirement. |
| No Mapbox API key required | Leaflet + OSM tiles are free. Mapbox is Phase K only if tile quality becomes user-reported friction. |

> Done-when: Map view renders on /properties. Properties with coordinates appear as pins. Pin click shows property card. Filters apply to map. OSM attribution visible. tsc and build clean.

### J.3 — Location Data Breadth (Stream B)

Goal: the location system self-populates as agents list properties. No manual seeding. This section documents the expected behaviour and the monitoring approach.

| Task | Notes |
| --- | --- |
| Monitor location table growth | Every property created with a location_name resolves via Nominatim and adds a location record if new. Check GET /api/v1/locations/states monthly to track breadth. |
| Agent UX: location autocomplete guidance | The location search input should show a helper text: 'Type a city, neighbourhood, or area in Nigeria' — guides agents toward useful search terms. |
| Broader location search terms | The backend agent noted broad terms (e.g. 'lekki') can return global matches. Frontend should append context: 'Lekki Lagos' not just 'Lekki'. Add this as a UI hint or implement client-side result filtering to prefer Nigerian results (address.country_code === 'ng'). |
| Filter result quality | On /api/v1/locations/search results, filter out any result where the resolved country is not Nigeria unless the user explicitly removed the country context. This prevents global pollution of the location DB. |

> Done-when: Location autocomplete shows Nigerian-relevant results. Filter query hints guide agents toward specific terms. Location table grows without manual intervention as properties are created.

### J.4 — Operational Closure (Stream B)

Goal: close remaining operational items carried from Phase H and I.

| Task | Notes |
| --- | --- |
| Audit log retention decision (DEF-002) | 60-day traffic clock started at Phase H close. Assess audit_logs table volume. If growing materially: implement age-based soft-delete job (records older than 180 days). If volume is low: defer to Phase K with documented decision. |
| Custom domain on Vercel and Railway (DEF-H-DOMAIN) | After email domain is verified (J.1), configure the same or a related domain on Vercel (frontend) and Railway (backend CORS). Update NEXT_PUBLIC_API_URL. Not a code task — operational. |
| CLAUDE.md files current | Update root, frontend, backend CLAUDE.md to reflect Phase J closed state. Navigation contract must include agency_owner routes. Open bugs table must reflect current codebase state. |
| DEFERRED.md audit | All Phase J items either closed with evidence or promoted to Phase K with rationale. No orphaned DEF items. |

> Done-when: Audit log retention decision documented with evidence. Custom domain live (if pursued). All three CLAUDE.md files committed. DEFERRED.md clean.

## 6. Phase J Exit Criteria

> Phase J is closed when every item below is true. Phase K does not open until this list is complete.

| Exit Criterion | Verification | Stream |
| --- | --- | --- |
| Real-user email delivered to actual inbox | Resend dashboard shows delivery to real address — not delivered@resend.dev | A |
| MAIL_FROM is a verified sender domain | Railway env var confirmed, _sender_address() returns non-placeholder | A |
| DEF-J-EMAIL-DOMAIN-001 closed with evidence | DEFERRED.md updated, Resend message ID recorded | A |
| Map view renders on /properties with property pins | Manual walkthrough — pins visible, click shows card | B |
| Map pins use resolved coordinates only — no 0,0 pins | Visual check — no pins in Gulf of Guinea | B |
| Filter integration on map view | Apply price filter — pins update to match | B |
| OSM attribution visible on map | © OpenStreetMap contributors visible on tile layer | B |
| Location autocomplete returns Nigerian-relevant results | Type 'Lekki' → first results are Lagos/Nigeria locations | B |
| Audit log retention decision documented | DEFERRED.md entry with volume evidence and decision | B |
| tsc --noEmit → 0 errors | pnpm tsc --noEmit | B |
| pyright → 0 errors | venv pyright | A |
| pytest → all passing, coverage ≥ 95% | pytest --cov gate | A |
| pnpm build → 0 warnings | Next.js production build | B |
| DEFERRED.md updated | All Phase J items closed or promoted to Phase K | All |
| All CLAUDE.md files committed | Root, frontend, backend — Phase J closed state | All |

## 7. Execution Sequence

| # | Phase | Dependency | Parallel? |
| --- | --- | --- | --- |
| 1 | J.1 — Email domain verification | None — operator action first | No — must close before real user launch |
| 2 | J.2 — Interactive map view | J.1 in progress | Yes — parallel with J.3/J.4 |
| 3 | J.3 — Location data breadth | J.2 location architecture confirmed | Yes — parallel with J.2/J.4 |
| 4 | J.4 — Operational closure | Runs throughout | Yes — parallel with all |
| 5 | Exit sweep | J.1–J.4 all closed | No — final gate |

## 8. Items Deferred to Phase K

| Item | Rationale |
| --- | --- |
| TBT < 100ms (DEF-G-TBT-001) | Phase I/J target revised to 300ms. 100ms requires full RSC migration. Phase K after traffic validates the investment. |
| Notification frequency preference UI | Saved search emails default to immediate. Seeker preference (immediate vs daily digest) requires preference storage and scheduler logic. Phase K. |
| In-app messaging / inquiry reply | Lead capture is MVP. Reply thread model requires its own data model (threads, messages, read receipts). Significant feature — Phase K. |
| Agency N+1 on public directory | Public agency cards compute stats per agency. Aggregation endpoint optimisation requires traffic data to size correctly. |
| Admin analytics — advanced cohort metrics | Current analytics page exists. Advanced cohort/retention metrics require real traffic data to design meaningfully. |
| Nominatim self-hosted instance | Public Nominatim is sufficient at current scale. If rate limiting becomes a constraint, evaluate self-hosted Nominatim or Photon on Phase K. |
| Agency owner self-service onboarding | Phase G built admin-governed path. Self-service needs abuse prevention, duplicate detection, email verification gate. |
| Saved search notifications — frequency preference | Emails send immediately. Daily digest preference requires scheduler + preference UI. |
| Audit log retention (DEF-002) | Implement in J.4 if volume warrants. Otherwise Phase K with 60-day data. |

## 9. Session Opening Template

> Session opening template: "Continuing RealtorNet Phase J from [J.X]. Phase I closed May 2026 — all exit criteria met, DEF-I-MEM-SMOKE-001 and DEF-I-COV-001 closed, CLAUDE.md committed to both repos. Backend v0.5.3+ on Railway (realtornet-production.up.railway.app), pytest passing, coverage 95.03%, pyright 0. Frontend Next.js 16.2.1 on Vercel (realtornet-web.vercel.app), tsc 0, lint clean, build clean. Production Supabase: avkhpachzsbgmbnkfnhu. Production DB head: a9d1f3c7b482. Four roles: seeker / agent / agency_owner / admin. Moderation enum: pending_review / verified / rejected / revoked. Resend email live (sync mode, code correct). CRITICAL: MAIL_FROM=onboarding@resend.dev — email blocked for real inboxes until verified domain configured (DEF-J-EMAIL-DOMAIN-001). Location system: PostGIS + Nominatim server-side resolver live, dynamic self-populating, no manual seeding. Today's task: [SPECIFIC TASK FROM WORK PLAN]. Attach Phase J workbook, DEFERRED.md, and all three CLAUDE.md files."

## 10. Production Reference

| Service | URL / Reference |
| --- | --- |
| Frontend | https://realtornet-web.vercel.app |
| Backend | https://realtornet-production.up.railway.app |
| Supabase (production) | https://avkhpachzsbgmbnkfnhu.supabase.co |
| Supabase (dev — deprecated) | umhtnqxdvffpifqbdtjs — do not use for production diagnostics |
| Email service | Resend — sync mode. MAIL_FROM=onboarding@resend.dev (test only — see DEF-J-EMAIL-DOMAIN-001) |
| Location resolution | Nominatim public API — server-side only, 1 req/sec, 5-min cache, Nigerian-first results |

### Production Accounts

| user_id | Email | Role | Agency |
| --- | --- | --- | --- |
| 5 | apineorbeenga@gmail.com | admin | NULL |
| 74 | apineorbeenga@outlook.com | agency_owner | 9 |
| 76 | apineorbeenga@yahoo.com | seeker | NULL |
| 85 | godwinemagun@gmail.com | seeker | NULL |

RealtorNet — Phase J Workbook v1.0

_Derived from Phase I close state  |  Backend v0.5.3+  |  Frontend Next.js 16.2.1_
